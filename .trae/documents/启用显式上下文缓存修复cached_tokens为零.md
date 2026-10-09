# 启用显式上下文缓存（修复 cached_tokens 永远为 0）

## Summary

用户此前已将追问 prompt 的固定规则部分调整到前面（`# 角色` 到 `# 本次会话信息` 之前，约 8000+ tokens，无动态变量），为缓存做好了结构准备。但缓存命中率仍为 0，根因是：**仅把静态放前面不够，还差最后一步——在 messages 里加 `cache_control: {"type": "ephemeral"}` 标记触发显式缓存**。当前走的是隐式缓存，阿里云官方明确"命中率不确定"，实测一直为 0。

本计划在不动 prompt 内容的前提下，仅改 messages 构造方式：把 system content 从字符串改成数组格式，加 cache_control 标记，让固定规则段 5 分钟内确定性命中。首次报告和追问两条链路都改。

## Current State Analysis

### 已有的好基础（用户之前调整已保存）
- [followup_structured.py:164-425](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L164-L425) 追问 prompt 固定规则部分在前，约 8000+ tokens，无动态变量
- [prompt_builder.py:511+](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/prompt_builder.py#L511) 首次报告 prompt 同样固定规则在前
- [usage_log.py:26](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/models/usage_log.py#L26) `cached_tokens` 字段已存在
- [ai_service.py:434-438](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/ai_service.py#L434-L438) 和 [followup_structured.py:1887-1891](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L1887-L1891) cached_tokens 提取逻辑正确（兼容 OpenAI `prompt_tokens_details.cached_tokens` 和 DashScope 原生 `cached_tokens`）
- [chat.py:284](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/api/chat.py#L284) 入库逻辑正确
- 前端 UsageDashboard.tsx「命中缓存」列已就位

### 缺失的关键一步
- LLM 调用处 messages 构造都是 `{"role": "system", "content": system_prompt}`（字符串格式），**没有 cache_control 标记**
- [build_llm_extra_body](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/ai_service.py#L29-L37) 只关了思考模式，未涉及缓存

### 实测证据
`backend/logs/followup_check.log` 显示今天 17 次追问全部 `cached=0`：
```
prompt=12529, cached=0, completion=1693
prompt=12642, cached=0, completion=1611
prompt=12596, cached=0, completion=1357
```
prompt 都在 12000+ tokens，远超显式缓存最小 1024 tokens 阈值，输入长度不是问题。

## Proposed Changes

### 改动 1：新增 `build_cache_control_messages` 工具函数

**文件**：`backend/app/services/ai_service.py`

**位置**：`build_llm_extra_body` 函数下方（约 line 38 后）

**做什么**：新增一个工具函数，把 `(system_prompt, user_messages)` 转换成带 cache_control 标记的 messages 数组。

**为什么**：显式缓存要求 content 是数组格式且带 `cache_control: {"type": "ephemeral"}` 标记。两条链路（首次报告 + 追问）都需要这个逻辑，抽成工具函数避免重复。

**怎么做**：
```python
def build_cache_control_messages(system_prompt: str, user_messages: list) -> list:
    """构造带显式缓存标记的 messages 数组。

    阿里云百炼显式缓存要求 content 为数组格式，并在 text block 上加
    cache_control: {"type": "ephemeral"} 标记。缓存最小 1024 tokens，
    有效期 5 分钟，命中部分按输入价 10% 计费（隐式为 20%）。

    本函数把 system_prompt 整体作为一个带标记的 text block——因为
    followup_structured.py 的 prompt 已把固定规则段（约 8000+ tokens）
    放在前面、动态数据段放在后面，前缀稳定可缓存。
    """
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
```

**设计决策**：
- **不拆分 prompt 成两段**：虽然拆分后命中率更高（只有固定段缓存），但需要改 `build_structured_prompt` 和 `build_first_reading_structured_prompt` 的返回值类型（str → tuple），改动面大且易引入 bug。当前方案把整个 system_prompt 作为一个 text block 加标记，依赖阿里云的「最长公共前缀匹配」——固定规则段在前会被缓存，动态部分不同不会影响前缀命中。实测命中率应能满足观测需求。
- **整个 system_prompt 加标记而非拆分**：阿里云文档说"系统将以每个 cache_control 标记位置为终点，向前回溯最多 20 个 content 块，尝试命中缓存"。我们只有一个 text block，回溯到开头，整个 system_prompt 都参与缓存匹配。固定前缀部分会命中，动态后缀部分不会命中但也不影响前缀命中。

### 改动 2：追问链路启用显式缓存

**文件**：`backend/app/services/followup_structured.py`

**位置**：line 1819 附近

**改前**：
```python
all_messages = [{"role": "system", "content": system_prompt}] + messages
```

**改后**：
```python
from app.services.ai_service import build_cache_control_messages  # 顶部 import 区已有
all_messages = build_cache_control_messages(system_prompt, messages)
```

**注意**：`followup_structured.py` 顶部已 `from app.services.ai_service import model_pool, get_client, build_llm_extra_body`（[line 19](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L19)），需在同行追加 `build_cache_control_messages`。

### 改动 3：首次报告链路启用显式缓存

**文件**：`backend/app/services/ai_service.py`

**位置**：line 376-384 附近，`client.chat.completions.create` 调用处

**改前**：
```python
response = await client.chat.completions.create(
    model=model_config.name,
    messages=[{"role": "system", "content": system_prompt}] + messages,
    temperature=0.3,
    max_tokens=8000,
    response_format={"type": "json_object"},
    timeout=300,
    extra_body=build_llm_extra_body(model_config.name),
)
```

**改后**：
```python
response = await client.chat.completions.create(
    model=model_config.name,
    messages=build_cache_control_messages(system_prompt, messages),
    temperature=0.3,
    max_tokens=8000,
    response_format={"type": "json_object"},
    timeout=300,
    extra_body=build_llm_extra_body(model_config.name),
)
```

### 改动 4（可选）：流式首次报告链路同步启用

**文件**：`backend/app/services/ai_service.py`

**位置**：line 132、line 179 附近的另两处 `client.chat.completions.create` 调用

**做什么**：用 `build_cache_control_messages` 替换 `messages=[{"role": "system", "content": system_prompt}] + messages` 模式

**为什么**：保持两条链路一致，避免有的请求命中缓存有的不命中造成观测混乱。需先 Read 确认这两处是否同属首次报告链路（可能是不同分支如流式/非流式）。

## Assumptions & Decisions

1. **模型支持显式缓存**：阿里云文档明确 qwen3.8-max 支持显式缓存（在「显式缓存支持的模型」列表中），无需切换模型。

2. **不拆分 prompt 内容**：当前方案不修改 `build_structured_prompt` 和 `build_first_reading_structured_prompt` 的返回值，仅改 messages 构造。理由是改动面小、风险低；阿里云显式缓存的「最长公共前缀匹配」机制能自动识别固定前缀部分。

3. **缓存有效期 5 分钟**：5 分钟内同一人物的连续追问可命中。超过 5 分钟的间隔会重新创建缓存（首次创建按 125% 计费，后续命中按 10%）。对于命理追问场景，用户连续追问间隔通常 < 5 分钟，命中率高。

4. **计费影响**：显式缓存创建按输入价 125% 计费，命中按 10% 计费。假设固定规则段 8000 tokens，5 分钟内 3 次追问：
   - 不启用：3 × 8000 × 100% = 24000 tokens 全价
   - 启用后：1 × 8000 × 125% + 2 × 8000 × 10% = 10000 + 1600 = 11600 tokens 折算
   - 节省约 52%

5. **不修改 prompt 内容**：仅改 messages 的数据结构（str → list），prompt 文本一字不动，避免影响 LLM 输出质量。

6. **隐式缓存会自动失效**：阿里云文档说"显式缓存、隐式缓存两者互斥，单个请求只能应用其中一种模式"。加了 cache_control 标记后，该请求走显式缓存，不再走隐式。这是预期行为。

## Verification Steps

1. **代码改动后构建验证**：
   ```bash
   cd mingli-agent/backend && source venv/bin/activate && python -c "from app.services.ai_service import build_cache_control_messages; print(build_cache_control_messages('test', [{'role':'user','content':'hi'}]))"
   ```
   确认函数能正常导入和调用，输出格式正确（system content 是数组，含 cache_control 标记）。

2. **重启后端**：
   ```bash
   # uvicorn --reload 会自动加载 .py 改动，确认日志无报错
   tail -f mingli-agent/backend/logs/followup_check.log
   ```

3. **触发追问测试**：在前端发起一次追问，5 分钟内再发起第二次追问（同一人物）。

4. **观测日志确认缓存命中**：
   ```bash
   grep "cached=" mingli-agent/backend/logs/followup_check.log | tail -5
   ```
   预期：第一次追问 `cached=0`（缓存创建），第二次追问 `cached>0`（缓存命中，应为 8000 左右）。

5. **前端用量记录页验证**：访问 `/admin/usage`，确认新记录的「命中缓存」列显示绿色「是 + 缓存率%」徽章。

6. **回归测试**：确认追问报告和首次报告内容质量无变化（prompt 文本未改，仅 messages 数据结构变了，不应影响 LLM 输出）。

## 风险点

1. **OpenAI SDK 兼容性**：`content` 从字符串改成数组格式，需确认阿里云百炼 OpenAI 兼容接口支持数组格式 content（官方文档示例用的就是数组格式，应该没问题，但需实测）。
2. **缓存创建失败**：若 system_prompt 不足 1024 tokens，显式缓存不会创建（但不会报错，只是不缓存）。我们的 prompt 都在 12000+ tokens，远超阈值。
3. **5 分钟有效期边界**：用户若两次追问间隔超过 5 分钟，第二次会重新创建缓存（多付 25%），但后续命中仍省钱。整体收益仍为正。
