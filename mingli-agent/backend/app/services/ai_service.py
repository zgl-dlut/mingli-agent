from typing import AsyncGenerator, List, Dict, Optional, Any
from openai import AsyncOpenAI, APIConnectionError, APIStatusError, AuthenticationError
from pydantic import BaseModel
import asyncio
import logging
import time

from app.config import settings

logger = logging.getLogger(__name__)


class ModelConfig(BaseModel):
    name: str
    api_key: str
    base_url: str


def parse_models() -> List[ModelConfig]:
    models = []
    
    model_names = [m.strip() for m in settings.AI_MODELS.split(",") if m.strip()]
    api_keys = [k.strip() for k in settings.AI_API_KEYS.split(",")] if settings.AI_API_KEYS else []
    base_urls = [u.strip() for u in settings.AI_BASE_URLS.split(",")] if settings.AI_BASE_URLS else []
    
    for i, model_name in enumerate(model_names):
        api_key = api_keys[i] if i < len(api_keys) else settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY
        base_url = base_urls[i] if i < len(base_urls) else settings.AI_BASE_URL
        
        if not api_key:
            logger.warning(f"模型 {model_name} 未配置API Key，跳过")
            continue
            
        models.append(ModelConfig(name=model_name, api_key=api_key, base_url=base_url))
    
    if not models:
        if settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY:
            models.append(ModelConfig(
                name=settings.AI_MODEL,
                api_key=settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY,
                base_url=settings.AI_BASE_URL
            ))
    
    return models


# 模型池（按配置顺序）
model_pool: List[ModelConfig] = parse_models()

# 动态优先级顺序：初始与配置顺序相同
# 当某个模型失败后，会被移到列表末尾，下次优先使用前面的模型
model_order: List[int] = list(range(len(model_pool)))

# 模型健康状态（仅用于监控展示，不影响切换逻辑）
model_health: Dict[str, bool] = {m.name: True for m in model_pool}


async def get_client(model_config: ModelConfig) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=model_config.api_key, base_url=model_config.base_url)


async def generate_ai_response(
    system_prompt: str,
    messages: List[dict],
    stream: bool = True,
) -> AsyncGenerator[str, None]:
    """
    生成 AI 响应，支持动态模型切换：
    - 按 model_order 优先级顺序尝试
    - 成功的模型保持高优先级
    - 失败的模型降级到末尾
    - 最多尝试 len(model_pool) 次
    """
    global model_order, model_health
    
    if not model_pool:
        yield "抱歉，AI 模型服务未配置，请联系管理员。"
        return
    
    max_attempts = len(model_pool)
    messages_list = [{"role": "system", "content": system_prompt}] + messages
    
    for attempt in range(max_attempts):
        # 获取当前优先级最高的模型
        current_idx = model_order[0]
        model_config = model_pool[current_idx]
        
        try:
            client = await get_client(model_config)
            logger.info(f"[AI] 尝试模型: {model_config.name} (第{attempt + 1}次)")

            start_ts = time.time()
            if stream:
                stream_response = await client.chat.completions.create(
                    model=model_config.name,
                    messages=messages_list,
                    stream=True,
                    temperature=0.2,
                    max_tokens=6000,
                    # 抑制长段落末尾的重复采样循环（避免"职场权力稳固期"等整段重复2-3次）
                    frequency_penalty=0.5,
                    presence_penalty=0.3,
                    timeout=120
                )
                first_chunk_ts = None
                chunk_count = 0
                total_chars = 0
                stream_usage = None
                async for chunk in stream_response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        if first_chunk_ts is None:
                            first_chunk_ts = time.time()
                        chunk_count += 1
                        total_chars += len(chunk.choices[0].delta.content)
                        yield chunk.choices[0].delta.content
                    # 捕获流末尾的 usage（部分模型在最后一个 chunk 携带）
                    _usage = getattr(chunk, "usage", None)
                    if _usage is not None:
                        stream_usage = _usage
                elapsed = time.time() - start_ts
                ttft = (first_chunk_ts - start_ts) if first_chunk_ts else None
                ttft_str = f"{ttft:.2f}s" if ttft is not None else "N/A"
                # token 用量：流式响应 usage 可能为 None（多数 OpenAI 兼容端点不返回），尽力读取
                usage = stream_usage
                if usage is not None:
                    p_tok = getattr(usage, "prompt_tokens", 0) or 0
                    c_tok = getattr(usage, "completion_tokens", 0) or 0
                    t_tok = getattr(usage, "total_tokens", 0) or (p_tok + c_tok)
                    logger.info(
                        f"[AI] 模型 {model_config.name} 流式调用成功: 状态=成功, 耗时={elapsed:.1f}s, "
                        f"首token={ttft_str}, "
                        f"chunk数={chunk_count}, 字符数={total_chars}, "
                        f"token用量: prompt={p_tok}, completion={c_tok}, total={t_tok}"
                    )
                else:
                    logger.info(
                        f"[AI] 模型 {model_config.name} 流式调用成功: 状态=成功, 耗时={elapsed:.1f}s, "
                        f"首token={ttft_str}, "
                        f"chunk数={chunk_count}, 字符数={total_chars}, token用量: 未返回"
                    )
            else:
                response = await client.chat.completions.create(
                    model=model_config.name,
                    messages=messages_list,
                    temperature=0.2,
                    max_tokens=6000,
                    frequency_penalty=0.5,
                    presence_penalty=0.3,
                    timeout=120
                )
                elapsed = time.time() - start_ts
                content_len = len(response.choices[0].message.content or "") if response.choices else 0
                usage = getattr(response, "usage", None)
                if usage is not None:
                    p_tok = getattr(usage, "prompt_tokens", 0) or 0
                    c_tok = getattr(usage, "completion_tokens", 0) or 0
                    t_tok = getattr(usage, "total_tokens", 0) or (p_tok + c_tok)
                    logger.info(
                        f"[AI] 模型 {model_config.name} 非流式调用成功: 状态=成功, 耗时={elapsed:.1f}s, "
                        f"长度={content_len}, token用量: prompt={p_tok}, completion={c_tok}, total={t_tok}"
                    )
                else:
                    logger.info(
                        f"[AI] 模型 {model_config.name} 非流式调用成功: 状态=成功, 耗时={elapsed:.1f}s, "
                        f"长度={content_len}, token用量: 未返回"
                    )
                if response.choices:
                    yield response.choices[0].message.content or ""
                else:
                    yield ""

            # 成功：更新健康状态，模型保持在首位
            model_health[model_config.name] = True
            return

        except (APIConnectionError, APIStatusError, AuthenticationError) as e:
            elapsed = time.time() - start_ts
            logger.warning(f"[AI] 模型 {model_config.name} 失败: 状态=异常, 耗时={elapsed:.1f}s, 错误={str(e)[:200]}")
            model_health[model_config.name] = False

            # 失败：将模型移到末尾，降低优先级
            model_order.pop(0)
            model_order.append(current_idx)

            # 继续尝试下一个模型（不向前端暴露切换细节，仅记录日志）
            if attempt < max_attempts - 1:
                next_model = model_pool[model_order[0]]
                logger.info(f"[AI] 切换到下一个模型: {next_model.name}")
                continue
            else:
                # 所有模型都已尝试：向前端返回笼统提示，不暴露内部错误
                logger.error(f"[AI] 所有 {max_attempts} 个模型均不可用")
                yield "抱歉，服务器当前异常，请稍后重试。"
                return

        except Exception as e:
            elapsed = time.time() - start_ts
            logger.error(f"[AI] 未知错误: 状态=异常, 耗时={elapsed:.1f}s, 错误={str(e)[:200]}")
            yield "抱歉，服务器当前异常，请稍后重试。"
            return


async def generate_first_reading(
    bazi_data: Dict,
    astro_data: Dict,
    gender: str,
    birth_time: str,
    location: str,
    longitude: float,
    latitude: float,
) -> AsyncGenerator[str, None]:
    from app.services.prompt_builder import build_commercial_prompt
    from app.skills.orchestrator import generate_full_analysis

    # birth_time格式: "1992-12-19 19:35"
    parts = birth_time.split(' ')
    birth_date = parts[0] if len(parts) > 0 else ''
    time_str = parts[1] if len(parts) > 1 else ''

    # gender统一为中文
    gender_cn = "男" if gender in ("male", "男") else "女"

    # 重新生成完整分析数据（build_commercial_prompt需要完整analysis_data）
    analysis_data = generate_full_analysis(
        birth_date=birth_date,
        birth_time=time_str,
        longitude=longitude,
        latitude=latitude,
        gender=gender_cn,
        location=location,
    )

    system_prompt = build_commercial_prompt(
        analysis_data, gender_cn, birth_date, time_str, location
    )
    messages = [{"role": "user", "content": f"请为我进行整体命理解读\n出生时间：{birth_time}\n出生地点：{location}"}]
    async for content in generate_ai_response(system_prompt, messages):
        yield content


def get_model_status() -> Dict[str, Any]:
    """获取所有模型状态及当前优先级"""
    ordered_models = [model_pool[i].name for i in model_order] if model_pool else []
    
    return {
        "current_model": model_pool[model_order[0]].name if model_pool else "无",
        "model_order": ordered_models,
        "models": [
            {
                "name": m.name,
                "base_url": m.base_url,
                "healthy": model_health.get(m.name, True),
                "priority": model_order.index(i) if i in model_order else -1
            }
            for i, m in enumerate(model_pool)
        ],
        "count": len(model_pool),
        "max_attempts": len(model_pool)
    }