# 模型切换 qwen3.8-max → qwen-max 兼容性验证

## Summary

**只需改 .env 配置，不需要改代码逻辑。** 代码中无硬编码模型名，全部从配置读取。有一个小风险点：`enable_thinking` 参数对 qwen-max 不必要但大概率被忽略。建议做一个小优化：让 `build_llm_extra_body` 只对 qwen3.x 系列加 `enable_thinking`，避免对 qwen-max 传无用参数。

## Current State Analysis

### 模型配置位置（.env）
```
AI_MODEL=qwen3.8-max
AI_MODELS=qwen3.8-max
AI_BASE_URL=https://ws-ekdxihtd67l14sw6.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

### 代码中模型名来源
- [config.py:13](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/config.py#L13)：默认值 `qwen-3.6-flash`，被 .env 覆盖
- [ai_service.py:116](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/ai_service.py#L116)：`model_pool = parse_models()` 从 settings 读取
- [ai_service.py:80-112](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/ai_service.py#L80)：`parse_models()` 解析 `AI_MODELS` 环境变量
- **全局搜索结果：代码中无硬编码 `qwen3.8-max`**（仅 .env 和日志注释中有）

### 兼容性分析

| 功能 | qwen3.8-max | qwen-max | 风险 |
|---|---|---|---|
| OpenAI 兼容接口 | 支持 | 支持 | 无 — 同一 Base URL |
| `response_format=json_object` | 支持 | 支持 | 无 |
| `temperature` / `max_tokens` | 支持 | 支持 | 无 |
| `enable_thinking: False` | 需要（qwen3.x有思考模式） | 不必要（qwen-max无思考模式） | **低风险** — 大概率被忽略，但建议精确匹配 |
| `cache_control: ephemeral` | 支持 | 支持（qwen-max-2025-04-24+） | **低风险** — `qwen-max` 默认指向最新版本应支持 |

### 唯一风险点：enable_thinking

[ai_service.py:35-36](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/ai_service.py#L35)：
```python
if "qwen" in (model_name or "").lower():
    return {"enable_thinking": False}
```

qwen-max 没有思考模式，传 `enable_thinking: False` 是无用的。阿里云 OpenAI 兼容接口通常会忽略不支持的参数，大概率不报错。但为了严谨，建议改为只对 qwen3.x 系列加此参数。

## Proposed Changes

### 改动1：修改 .env 模型配置（必须）

**文件**：`backend/.env`

```diff
- AI_MODEL=qwen3.8-max
- AI_MODELS=qwen3.8-max
+ AI_MODEL=qwen-max
+ AI_MODELS=qwen-max
```

注意：修改 .env 后需手动重启 uvicorn（--reload 只监视 .py 文件，不监视 .env）。

### 改动2：精确化 enable_thinking 匹配（建议，非必须）

**文件**：`backend/app/services/ai_service.py`（line 35-36）

```diff
- if "qwen" in (model_name or "").lower():
-     return {"enable_thinking": False}
+ if "qwen3" in (model_name or "").lower():
+     return {"enable_thinking": False}
```

只对 qwen3.x 系列（qwen3.8-max、qwen3.7-flash 等）加 `enable_thinking: False`，qwen-max 不加。避免传无用参数。

### 不需要改动的部分
- API Key：通用，不需要换
- Base URL：同一接口，不需要换
- cache_control：qwen-max 支持，不需要改
- response_format：qwen-max 支持，不需要改
- 代码中的模型调用逻辑：全部从 model_pool 读取，不需要改

## Assumptions & Decisions

1. **qwen-max 默认指向最新版本**：阿里云百炼中 `qwen-max` 是快照模型，默认指向最新版本（当前 qwen-max-2025-04-24），支持上下文缓存。

2. **enable_thinking 改为 qwen3 匹配**：原逻辑 `"qwen" in model_name` 会对所有 qwen 系列加 enable_thinking，但只有 qwen3.x 系列有思考模式。改为 `"qwen3" in model_name` 更精确。

3. **修改 .env 需重启**：uvicorn --reload 不监视 .env 文件，修改后需手动重启后端。

## Verification Steps

1. 修改 .env 中 AI_MODEL 和 AI_MODELS 为 qwen-max
2. 修改 ai_service.py 中 enable_thinking 匹配条件
3. 重启 uvicorn（停掉旧进程，重新启动）
4. 触发一次追问，确认无报错
5. 检查日志 `grep "模型=" logs/followup_check.log | tail -3` 确认模型名为 qwen-max
6. 检查 cached 值确认缓存功能正常
