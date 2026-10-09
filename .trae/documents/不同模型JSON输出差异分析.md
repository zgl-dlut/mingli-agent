# 不同模型 JSON 输出差异分析与解决方案

## Summary

**是的，不同模型对 JSON 的输出能力差异很大。** qwen-max 输出的不是标准 JSON 嵌套数组，而是混乱的多行文本格式，后端兼容层无法修复。建议换回 qwen3.8-max（等额度恢复或充值），或改用 function calling 强制结构化输出。

## Current State Analysis

### 两个模型的 JSON 输出对比

**qwen3.8-max**（之前用的，输出正常）：

```json
"blocks": [
  {"type": "keyword", "keyword": "真实态度", "narrative": "..."},
  {"type": "keyword", "keyword": "表达方式", "narrative": "..."}
]
```

* 标准嵌套 JSON 数组

* completion 通常 1300+ tokens，内容完整

**qwen-max**（当前用的，输出异常）：

第一次返回 — blocks 为 JSON 字符串（可通过 json.loads 修复）：

```json
"blocks": "[{\"type\": \"keyword\", \"keyword\": \"...\", \"narrative\": \"...\"}]"
```

第二次返回 — blocks 为多行文本（完全非 JSON，无法修复）：

```json
"blocks": 
  "type: keyword, keyword: 对生孩子的渴望, narrative: 他命盘中有正官...",
  "type: keyword, keyword: 表达方式, narrative: 他的日主是己土..."
:
"closing: 他其实很在意..."
```

* 不是 JSON 数组，不是 JSON 字符串，而是类似 YAML/冒号分隔的多行文本

* `closing` 混在 blocks 内部

* items 也是字符串数组 `"keyword: xxx, text: xxx"` 而非对象数组

* completion 只有 328/757 tokens，内容极短

### 根本原因

* **qwen3.8-max** 是新一代模型（qwen3.x 系列），对复杂嵌套 JSON schema 的理解和输出能力强

* **qwen-max** 是上一代商业模型，对复杂嵌套 JSON 的输出能力不足，倾向于输出扁平的冒号分隔文本

* `response_format=json_object` 只保证顶层是合法 JSON，不保证嵌套结构的正确性

* 后端 `_normalize_report_data` 只能处理"JSON 字符串"类型的异常（已修复），无法处理"多行冒号文本"这种完全非 JSON 的输出

### 后端兼容层的局限

已实现的修复（[followup\_structured.py:473-478](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L473)）：

```python
if isinstance(sub.get("blocks"), str):
    sub["blocks"] = json.loads(sub["blocks"])
```

* ✅ 能处理：blocks 为 JSON 字符串（第一次返回的类型）

* ❌ 不能处理：blocks 为多行冒号文本（第二次返回的类型）

要处理第二种情况，需要写一个"冒号文本→JSON 数组"的解析器，成本高且脆弱（格式不固定）。

## Proposed Changes

### 方案A：换回 qwen3.8-max（推荐，最简单）

**文件**：`backend/.env`

```diff
- AI_MODEL=qwen-max
- AI_MODELS=qwen-max
+ AI_MODEL=qwen3.8-max
+ AI_MODELS=qwen3.8-max
```

**前提**：需要在阿里云百炼控制台充值或关闭"仅使用免费层"模式，恢复 qwen3.8-max 的调用额度。

**优点**：零代码改动，JSON 输出质量有保障
**缺点**：需要付费

### 方案B：保留 qwen-max + 增强后端兼容层（不推荐）

需要增加"冒号文本→JSON 数组"的解析器，处理 qwen-max 的各种非标准输出格式。

**优点**：可用免费额度
**缺点**：

* 兼容成本高，格式不固定，维护困难

* qwen-max 的 completion 只有 300-700 tokens，内容质量远不如 qwen3.8-max

* 即使格式修复了，内容也太短太浅

### 方案C：改用 function calling 强制结构化输出（长期方案）

把当前的 `response_format=json_object` 改为 tool calling，让 API 层强制结构化输出。

**优点**：JSON 格式由 API 层保证，不依赖模型能力
**缺点**：改动大，需要重构追问链路；且 qwen-max 对 tool calling 的支持也不如 qwen3.8-max

## Assumptions & Decisions

1. **推荐方案A**：qwen3.8-max 的 JSON 输出能力和内容质量都远优于 qwen-max。等额度恢复后换回是最简单的解决方案。

2. **不推荐方案B的理由**：qwen-max 的问题不只是格式异常（可以通过兼容层修复），还有内容质量差（completion 只有 300-700 tokens vs qwen3.8-max 的 1300+ tokens）。即使格式修复了，报告内容也太短太浅。

3. **保留已实现的兼容层**：`_normalize_report_data` 中的 JSON 字符串二次解析逻辑保留，作为防御性兜底（即使 qwen3.8-max 偶发输出字符串也能处理）。

4. **不推荐方案C的理由**：改动太大，当前优先级不高。如果未来要支持更多模型，可以考虑。

## Verification Steps

1. 在阿里云百炼控制台充值或关闭"仅使用免费层"模式
2. 修改 .env 换回 qwen3.8-max
3. 重启 uvicorn（.env 改动不会被 --reload 加载）
4. 触发追问，确认 JSON 输出正常（blocks 为标准数组，内容完整）
5. 检查日志确认 completion tokens > 1000

