from typing import AsyncGenerator, List, Dict, Optional, Any
from openai import AsyncOpenAI, APIConnectionError, APIStatusError, AuthenticationError
from pydantic import BaseModel
import asyncio
import logging
import time

from app.config import settings

logger = logging.getLogger(__name__)
# 确保 logger.info 能输出到 stdout（uvicorn 默认不配置 app 子 logger 的 handler，
# 不挂 handler 时 INFO 日志会被丢弃，无法判断 LLM 是在生成还是卡住）
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setLevel(logging.INFO)
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
    logger.addHandler(_h)
    # 日志持久化到文件，便于排查生成状态
    import os
    os.makedirs("logs", exist_ok=True)
    _fh = logging.FileHandler("logs/ai_service.log", encoding="utf-8")
    _fh.setLevel(logging.INFO)
    _fh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
    logger.addHandler(_fh)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # 避免重复输出


def build_llm_extra_body(model_name: str) -> dict:
    """构建 extra_body：Qwen 系模型关闭思考模式。

    思考模式消耗大量 tokens 和时间，且曾导致输出内容为空（tokens 被思考耗尽）；
    非 Qwen 模型（如 GPT）不传 enable_thinking，避免参数校验错误。
    """
    if "qwen" in (model_name or "").lower():
        return {"enable_thinking": False}
    return {}


def build_cache_control_messages(system_prompt: str, user_messages: list) -> list:
    """构造带显式缓存标记的 messages 数组。

    阿里云百炼显式缓存要求 content 为数组格式，并在 text block 上加
    cache_control: {"type": "ephemeral"} 标记。缓存最小 1024 tokens，
    有效期 5 分钟，命中部分按输入价 10% 计费（隐式为 20%）。

    在 "# 本次会话信息" 处拆分 system_prompt 为两个 system message：
    第一个 message 包含固定规则段（约 8000+ tokens），用 content 数组格式
    加 cache_control 标记；第二个 message 包含动态命盘数据，用字符串格式。
    实测单 system message 多 content block 结构缓存不命中，拆成两个 system
    message 后缓存正常工作。
    """
    SPLIT_MARKER = "# 本次会话信息"
    split_idx = system_prompt.find(SPLIT_MARKER)

    if split_idx > 0:
        fixed_part = system_prompt[:split_idx].rstrip()
        dynamic_part = system_prompt[split_idx:]
        return [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": fixed_part,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
            {"role": "system", "content": dynamic_part},
        ] + user_messages
    else:
        # 兜底：无分隔符时整体标记
        return [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ] + user_messages


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
    # max_retries=0：禁止SDK静默重试（默认重试2次会把超时放大3倍，用户空等且无日志）
    return AsyncOpenAI(api_key=model_config.api_key, base_url=model_config.base_url, max_retries=0)


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
    messages_list = build_cache_control_messages(system_prompt, messages)
    
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
                    timeout=120,
                    extra_body=build_llm_extra_body(model_config.name)
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
                    timeout=120,
                    extra_body=build_llm_extra_body(model_config.name)
                )
                elapsed = time.time() - start_ts
                # 兼容不同 endpoint 的响应格式：标准格式用 choices，部分自定义 endpoint 用 text 字段
                if response.choices:
                    _content = response.choices[0].message.content or ""
                else:
                    _content = getattr(response, "text", None) or ""
                content_len = len(_content)
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
                    # 兼容自定义 endpoint：内容可能在 text 字段而非 choices
                    yield getattr(response, "text", None) or ""

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

    # gender_cn 仅用于 prompt 展示（build_commercial_prompt 给 LLM 看中文）；
    # 喂 generate_full_analysis 用英文 gender（编排层内部 normalize 兜底转英文喂算法）
    gender_cn = "男" if gender in ("male", "男") else "女"

    # 重新生成完整分析数据（build_commercial_prompt需要完整analysis_data）
    analysis_data = generate_full_analysis(
        birth_date=birth_date,
        birth_time=time_str,
        longitude=longitude,
        latitude=latitude,
        gender=gender,
        location=location,
    )

    system_prompt = build_commercial_prompt(
        analysis_data, gender_cn, birth_date, time_str, location
    )
    messages = [{"role": "user", "content": f"请为我进行整体命理解读\n出生时间：{birth_time}\n出生地点：{location}"}]
    async for content in generate_ai_response(system_prompt, messages):
        yield content


async def generate_first_reading_structured(
    gender: str,
    birth_date: str,
    birth_time: str,
    location: str,
    longitude: float,
    latitude: float,
    usage_holder: Optional[dict] = None,
) -> AsyncGenerator[str, None]:
    """首次命理报告结构化生成：输出FollowupReport JSON字符串（非流式）。

    复用追问报告的 FollowupReport schema + 容错提取 + 规范化链路，
    与 generate_followup_structured 的 LLM 调用模式一致。

    usage_holder: 可选 dict，LLM 调用成功后填充用量信息（供调用方落库 ai_usage_logs）；
    未填充或无 success 键视为失败记录。
    """
    import json
    from app.services.prompt_builder import build_first_reading_structured_prompt
    from app.services.followup_structured import _normalize_report_data, _extract_and_fix_json
    from app.services.chart_validator import validate_chart_data, get_chart_fingerprint
    from app.schemas.report_schema import FollowupReport
    from app.skills.orchestrator import generate_full_analysis
    from pydantic import ValidationError

    # gender_cn 仅用于 prompt 展示（build_first_reading_structured_prompt 给 LLM 看中文）；
    # 喂 generate_full_analysis 用英文 gender（编排层内部 normalize 兜底转英文喂算法）
    gender_cn = "男" if gender in ("male", "男") else "女"

    # 1. 现场重算命盘（加异常兜底，排盘失败不崩溃）
    try:
        analysis_data = generate_full_analysis(
            birth_date=birth_date,
            birth_time=birth_time,
            longitude=longitude,
            latitude=latitude,
            gender=gender,
            location=location,
        )
    except Exception as e:
        logger.error(
            f"[StructuredFirstReading] generate_full_analysis 异常: {type(e).__name__}: {e}"
        )
        analysis_data = {}  # 降级为空，后续校验会记录所有字段缺失

    # 2. 命盘数据完整性校验（代码层 check，不依赖 prompt）
    chart_ok, missing = validate_chart_data(analysis_data)
    if not chart_ok:
        # 关键字段（日主/四柱/用神/当前大运）缺失升 error，便于重点排查；其余 warning
        _CRITICAL_FIELDS = {"日主", "四柱", "用神", "当前大运"}
        _log_fn = logger.error if any(m in _CRITICAL_FIELDS for m in missing) else logger.warning
        _log_fn(
            f"[StructuredFirstReading] 命盘数据缺失: {missing}，降级生成（缺失字段在prompt标注），"
            f"指纹: {get_chart_fingerprint(analysis_data)}"
        )
    else:
        logger.info(
            f"[StructuredFirstReading] 命盘校验通过, 指纹: {get_chart_fingerprint(analysis_data)}"
        )
    logger.info(
        f"[StructuredFirstReading][排查] 命盘上下文构建: 日主={analysis_data.get('日主')}, "
        f"用神={analysis_data.get('用神')}, 忌神={analysis_data.get('忌神')}, "
        f"当前大运={analysis_data.get('当前大运')}, "
        f"重点流年={str(analysis_data.get('重点流年', ''))[:120]}"
    )

    # 3. 构建 prompt
    system_prompt = build_first_reading_structured_prompt(
        analysis_data, gender_cn, birth_date, birth_time, location
    )
    messages = [{"role": "user", "content": f"请为我进行整体命理解读\n出生时间：{birth_date} {birth_time}\n出生地点：{location}"}]
    logger.info(
        f"[StructuredFirstReading] 开始生成, 模型={model_pool[0].name if model_pool else '无'}, "
        f"prompt长度: {len(system_prompt)}"
    )

    # 3. 调用 LLM（response_format=json_object，非流式）
    if not model_pool:
        logger.error("[StructuredFirstReading] model_pool为空: AI模型未配置，返回错误JSON")
        yield json.dumps(
            {"opening": {"lead": "AI模型未配置"}, "subtopics": [], "summary": {"title": "错误"}},
            ensure_ascii=False,
        )
        return

    model_config = model_pool[0]
    client = await get_client(model_config)

    # 应用层可见重试（最多2次）：禁止SDK静默重试（max_retries=0），
    # 避免 timeout×3次静默重试导致用户空等6分钟且无任何日志
    _MAX_ATTEMPTS = 2
    start = time.time()
    response = None
    last_error = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        attempt_start = time.time()
        logger.info(
            f"[StructuredFirstReading] LLM尝试 {attempt}/{_MAX_ATTEMPTS} 开始, "
            f"模型={model_config.name}, timeout=300s"
        )
        try:
            response = await client.chat.completions.create(
                model=model_config.name,
                messages=build_cache_control_messages(system_prompt, messages),
                temperature=0.3,
                max_tokens=8000,
                response_format={"type": "json_object"},
                timeout=300,
                extra_body=build_llm_extra_body(model_config.name),
            )
            break  # 成功
        except Exception as e:
            last_error = e
            attempt_elapsed = time.time() - attempt_start
            logger.error(
                f"[StructuredFirstReading] LLM尝试 {attempt}/{_MAX_ATTEMPTS} 失败: "
                f"模型={model_config.name}, 耗时={attempt_elapsed:.1f}s, "
                f"错误={type(e).__name__}: {str(e)[:200]}"
            )
    if response is None:
        elapsed = time.time() - start
        logger.error(
            f"[StructuredFirstReading] LLM请求失败: 模型={model_config.name}, 状态=异常, "
            f"总耗时={elapsed:.1f}s, 尝试次数={_MAX_ATTEMPTS}, 最后错误={type(last_error).__name__}: {str(last_error)[:200]}"
        )
        raise last_error

    # 兼容不同 endpoint 的响应格式：标准格式用 choices，部分自定义 endpoint 用 text 字段
    if response.choices:
        raw_content = response.choices[0].message.content or ""
        finish_reason = response.choices[0].finish_reason
    else:
        raw_content = getattr(response, "text", None) or ""
        finish_reason = getattr(response, "finish_reason", "stop")
        if not raw_content:
            _model = getattr(response, "model", "unknown")
            _id = getattr(response, "id", "unknown")
            logger.error(
                f"[StructuredFirstReading] LLM返回空响应: model={_model}, id={_id}, "
                f"config_model={model_config.name}, choices={response.choices}"
            )
            raise RuntimeError(
                f"LLM 返回空响应（choices 为空），可能原因：模型 {model_config.name} 不支持 JSON 模式或 API 配额异常"
            )
    elapsed = time.time() - start
    logger.info(
        f"[StructuredFirstReading] LLM响应: 模型={model_config.name}, 状态=成功, "
        f"finish_reason={finish_reason}, 长度={len(raw_content)}, 耗时={elapsed:.1f}s"
    )

    # token 用量统计（含上下文缓存命中观测）
    # 注意：OpenAI SDK 1.35.3 的 CompletionUsage 未定义 prompt_tokens_details 字段，
    # 阿里云返回的 prompt_tokens_details 被 SDK 存为原始 dict（而非对象），
    # 必须用 dict.get() 取值，getattr() 在 dict 上取不到 key。
    prompt_tokens = completion_tokens = total_tokens = cached_tokens = 0
    usage = getattr(response, "usage", None)
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)
        details = getattr(usage, "prompt_tokens_details", None)
        if details is not None:
            if isinstance(details, dict):
                cached_tokens = details.get("cached_tokens", 0) or 0
            else:
                cached_tokens = getattr(details, "cached_tokens", 0) or 0
        if not cached_tokens:
            if isinstance(usage, dict):
                cached_tokens = usage.get("cached_tokens", 0) or 0
            else:
                cached_tokens = getattr(usage, "cached_tokens", 0) or 0
        logger.info(
            f"[StructuredFirstReading] token用量: prompt={prompt_tokens}, cached={cached_tokens}, "
            f"completion={completion_tokens}, total={total_tokens}"
        )
    # 填充用量钩子（供调用方落库 ai_usage_logs）
    if usage_holder is not None:
        usage_holder.update({
            "success": True,
            "model": model_config.name,
            "input_chars": len(system_prompt),
            "output_chars": len(raw_content),
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
        })

    # 4. 解析 + 容错提取
    try:
        data = json.loads(raw_content)
        logger.info("[StructuredFirstReading] JSON直接解析成功")
    except json.JSONDecodeError:
        logger.info("[StructuredFirstReading] JSON直接解析失败，启动容错修复...")
        fixed = _extract_and_fix_json(raw_content)
        try:
            data = json.loads(fixed)
            logger.info("[StructuredFirstReading] 容错修复后解析成功")
        except json.JSONDecodeError as e:
            logger.error(f"[StructuredFirstReading] JSON解析彻底失败: {e}")
            error_report = {
                "opening": {"lead": "报告生成异常，请稍后重试。"},
                "subtopics": [],
                "summary": {"title": "生成失败"},
            }
            yield json.dumps(error_report, ensure_ascii=False)
            return

    # 5. 字段规范化（复用追问报告的规范化逻辑）
    _normalize_report_data(data)
    logger.info("[StructuredFirstReading] 字段规范化完成")

    # 6. Pydantic 校验
    try:
        report = FollowupReport.model_validate(data)
        logger.info(
            f"[StructuredFirstReading] Pydantic校验通过, subtopics={len(report.subtopics)}"
        )
    except ValidationError as e:
        logger.error(f"[StructuredFirstReading] Pydantic校验失败: {e}")
        logger.error(
            f"[StructuredFirstReading] 规范化后data片段: {json.dumps(data, ensure_ascii=False)[:800]}"
        )
        error_report = {
            "opening": {"lead": "报告格式异常，请稍后重试。"},
            "subtopics": [],
            "summary": {"title": "校验失败"},
        }
        yield json.dumps(error_report, ensure_ascii=False)
        return

    # 6.5 大运编造检测 + 重试（复用追问链路检测器纯函数，不改 followup_structured.py，不影响追问链路）
    # 背景：首次报告链路此前只有 LLM 网络层重试，无内容层编造检测，导致 LLM 凭记忆编造大运干支直达用户
    try:
        # 只 import 纯函数 _collect_report_texts 和 _detect_shensha_mismatch（不改追问链路）
        from app.services.followup_structured import _collect_report_texts, _detect_shensha_mismatch
        import re as _re

        def _detect_dayun_ganzhi_not_in_chart(report_data, chart_data):
            """首次报告专用：报告中"X大运"的干支必须在命盘大运列表内（含当前大运）。

            比追问的 _detect_dayun_ganzhi_mismatch 更宽松——追问版只跟"当前大运"比对，
            会把合法的"未来大运"引用（如"2030年后进入癸巳大运"）误判成编造；
            首次报告常推演未来大运走向，故改为校验干支是否在大运列表内，
            既抓编造（列表外干支，如列表是丙戌却写壬辰）又不误伤未来大运。
            """
            valid = set()
            cur = chart_data.get("当前大运", "")
            if cur:
                cg = cur.split()[0] if " " in cur else cur
                if len(cg) == 2:
                    valid.add(cg)
            for d in chart_data.get("大运列表", []) or []:
                if isinstance(d, dict) and d.get("ganzhi"):
                    valid.add(d["ganzhi"])
            if not valid:
                return []
            pat = _re.compile(r'([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])大运')
            res = []
            for path, text, _ctx in _collect_report_texts(report_data):
                if not text:
                    continue
                for m in pat.finditer(text):
                    g = m.group(1)
                    if g not in valid:
                        snip = text[max(0, m.start() - 10):m.end() + 20].replace("\n", "")
                        res.append(
                            f"{path}: 大运干支编造——'{g}大运'不在命盘大运列表内"
                            f"(合法大运: {sorted(valid)})，原文:...{snip}..."
                        )
            return res

        dayun_violations = _detect_dayun_ganzhi_not_in_chart(data, analysis_data)
        if dayun_violations:
            logger.warning(
                f"[StructuredFirstReading] 大运编造检测命中{len(dayun_violations)}项，启动重试: "
                f"{[v[:120] for v in dayun_violations]}"
            )
            current_dayun = analysis_data.get("当前大运", "")
            dayun_list = analysis_data.get("大运列表", [])
            retry_hint = (
                "上一次生成的报告存在大运干支编造，必须严格按排盘数据重写，"
                "禁止凭记忆编造大运干支。\n\n"
                f"【排盘真实数据·大运干支必须取自此处】\n"
                f"当前大运：{current_dayun}\n"
                f"大运列表（只能引用其中的干支）：{dayun_list}\n\n"
                "【检测到的违规】\n"
                + "\n".join(f"- {v}" for v in dayun_violations)
                + "\n\n请基于上述真实数据重新生成完整报告，确保文中所有“X大运”的干支"
                "均取自大运列表，不得自行推断或臆造列表外的干支。"
            )
            _DAYUN_MAX_RETRY = 2
            for attempt in range(1, _DAYUN_MAX_RETRY + 1):
                try:
                    retry_resp = await client.chat.completions.create(
                        model=model_config.name,
                        messages=build_cache_control_messages(
                            system_prompt, messages + [{"role": "user", "content": retry_hint}]
                        ),
                        temperature=0.2,
                        max_tokens=8000,
                        response_format={"type": "json_object"},
                        timeout=300,
                        extra_body=build_llm_extra_body(model_config.name),
                    )
                    if retry_resp.choices:
                        retry_raw = retry_resp.choices[0].message.content or ""
                    else:
                        retry_raw = getattr(retry_resp, "text", None) or ""
                    if not retry_raw:
                        logger.error(f"[StructuredFirstReading] 大运重试第{attempt}次返回空响应，终止")
                        break
                    try:
                        retry_data = json.loads(retry_raw)
                    except json.JSONDecodeError:
                        retry_data = json.loads(_extract_and_fix_json(retry_raw))
                    _normalize_report_data(retry_data)
                    new_v = _detect_dayun_ganzhi_not_in_chart(retry_data, analysis_data)
                    if not new_v:
                        try:
                            FollowupReport.model_validate(retry_data)
                            data = retry_data
                            logger.info(
                                f"[StructuredFirstReading] 大运重试第{attempt}次成功，原违规已清除"
                            )
                            break
                        except ValidationError:
                            logger.error(
                                f"[StructuredFirstReading] 大运重试第{attempt}次无大运违规但Pydantic校验失败"
                            )
                    else:
                        logger.error(
                            f"[StructuredFirstReading] 大运重试第{attempt}次仍违规{len(new_v)}项: "
                            f"{[v[:100] for v in new_v]}"
                        )
                        # 降级采用最新重试结果（比首次更接近正确），继续下次重试
                        try:
                            FollowupReport.model_validate(retry_data)
                            data = retry_data
                        except ValidationError:
                            pass
                except Exception as e:
                    logger.error(
                        f"[StructuredFirstReading] 大运重试第{attempt}次异常: {type(e).__name__}: {str(e)[:200]}"
                    )
                    break
            else:
                logger.error(
                    f"[StructuredFirstReading] 大运重试{_DAYUN_MAX_RETRY}次后仍编造，降级返回最新结果(已告警)"
                )
        else:
            logger.info("[StructuredFirstReading] 大运编造检测通过，无违规")
    except Exception as dayun_e:
        logger.error(f"[StructuredFirstReading] 大运编造检测异常(不阻断): {type(dayun_e).__name__}: {dayun_e}")

    # 6.6 神煞编造检测 + 重试（复用追问链路 _detect_shensha_mismatch 纯函数）
    # 背景：LLM 为迎合用户"太乙贵人"等问题，编造命盘不存在的天乙贵人等神煞
    try:
        shensha_violations = _detect_shensha_mismatch(data, analysis_data)
        if shensha_violations:
            logger.warning(
                f"[StructuredFirstReading] 神煞编造检测命中{len(shensha_violations)}项，启动重试: "
                f"{[v[:120] for v in shensha_violations]}"
            )
            # 拼命盘真实神煞提示
            shensha = analysis_data.get("神煞", {})
            chart_ss_lines = []
            for pos in ("年", "月", "日", "时"):
                ss_list = shensha.get(pos, shensha.get({"年": "year", "月": "month", "日": "day", "时": "hour"}.get(pos, ""), []))
                if isinstance(ss_list, list) and ss_list:
                    chart_ss_lines.append(f"{pos}:{'/'.join(map(str, ss_list))}")
            chart_ss_hint = "；".join(chart_ss_lines) if chart_ss_lines else "（无）"
            retry_hint = (
                "上一次生成的报告存在神煞编造，必须严格按排盘数据重写，"
                "禁止凭记忆或迎合用户问题编造命盘不存在的神煞。\n\n"
                f"【排盘真实数据·神煞只能取自此处】\n"
                f"命盘神煞（只能引用其中已列出的名称）：{chart_ss_hint}\n\n"
                "【检测到的违规】\n"
                + "\n".join(f"- {v}" for v in shensha_violations)
                + "\n\n请基于上述真实数据重新生成完整报告，确保文中所有神煞名称"
                "均取自命盘神煞字段，不得自行推断或臆造命盘没有的神煞。"
                "用户问及命盘未带的神煞（如太乙贵人/天乙贵人）时，应如实说明命盘该柱未带，"
                "可从已有的德秀贵人/月德合等神煞解释贵人特质，禁止编造命盘没有的神煞名称。"
            )
            _SHENSHA_MAX_RETRY = 2
            for attempt in range(1, _SHENSHA_MAX_RETRY + 1):
                try:
                    retry_resp = await client.chat.completions.create(
                        model=model_config.name,
                        messages=build_cache_control_messages(
                            system_prompt, messages + [{"role": "user", "content": retry_hint}]
                        ),
                        temperature=0.2,
                        max_tokens=8000,
                        response_format={"type": "json_object"},
                        timeout=300,
                        extra_body=build_llm_extra_body(model_config.name),
                    )
                    if retry_resp.choices:
                        retry_raw = retry_resp.choices[0].message.content or ""
                    else:
                        retry_raw = getattr(retry_resp, "text", None) or ""
                    if not retry_raw:
                        logger.error(f"[StructuredFirstReading] 神煞重试第{attempt}次返回空响应，终止")
                        break
                    try:
                        retry_data = json.loads(retry_raw)
                    except json.JSONDecodeError:
                        retry_data = json.loads(_extract_and_fix_json(retry_raw))
                    _normalize_report_data(retry_data)
                    new_v = _detect_shensha_mismatch(retry_data, analysis_data)
                    if not new_v:
                        try:
                            FollowupReport.model_validate(retry_data)
                            data = retry_data
                            logger.info(
                                f"[StructuredFirstReading] 神煞重试第{attempt}次成功，原违规已清除"
                            )
                            break
                        except ValidationError:
                            logger.error(
                                f"[StructuredFirstReading] 神煞重试第{attempt}次无神煞违规但Pydantic校验失败"
                            )
                    else:
                        logger.error(
                            f"[StructuredFirstReading] 神煞重试第{attempt}次仍违规{len(new_v)}项: "
                            f"{[v[:100] for v in new_v]}"
                        )
                        try:
                            FollowupReport.model_validate(retry_data)
                            data = retry_data
                        except ValidationError:
                            pass
                except Exception as e:
                    logger.error(
                        f"[StructuredFirstReading] 神煞重试第{attempt}次异常: {type(e).__name__}: {str(e)[:200]}"
                    )
                    break
            else:
                logger.error(
                    f"[StructuredFirstReading] 神煞重试{_SHENSHA_MAX_RETRY}次后仍编造，降级返回最新结果(已告警)"
                )
        else:
            logger.info("[StructuredFirstReading] 神煞编造检测通过，无违规")
    except Exception as shensha_e:
        logger.error(f"[StructuredFirstReading] 神煞编造检测异常(不阻断): {type(shensha_e).__name__}: {shensha_e}")

    # 7. 命盘指纹审计（事后核对 LLM 输出是否与命盘一致，不强制拦截）
    logger.info(
        f"[StructuredFirstReading] 命盘指纹审计: {get_chart_fingerprint(analysis_data)}, "
        f"LLM输出摘要: {raw_content[:200]}"
    )

    # 8. yield JSON 字符串（存库用，前端 isStructuredReport 自动识别 JSON 走结构化渲染）
    yield json.dumps(data, ensure_ascii=False)


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