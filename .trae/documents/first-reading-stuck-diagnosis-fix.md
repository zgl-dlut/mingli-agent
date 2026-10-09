# 首次报告卡住排查与修复（含关闭思考模式）

## 排查结论（根因已锁定）

### 现象
session 18（2021-07-06 出生）的首次报告一直无法完成，数据库里只有 user 消息、没有 assistant 消息。

### 根因链（有日志证据）

1. **LLM 请求超时**：日志 `[StructuredFirstReading] LLM请求失败: 模型=qwen3.8-max, 耗时=362.8s, 错误=APITimeoutError`
2. **为什么是362秒而不是120秒**：代码 `timeout=120`，但 OpenAI SDK 默认 `max_retries=2`，3次 × 120秒 ≈ 360秒静默重试
3. **失败被吞掉**：异常发生在旧版 SSE 内联路径，前端没收到错误，进度条永远转圈
4. **追问报告同样的坑**：追问主调用 `timeout=600` × 3次尝试 = 最坏30分钟（之前"追问20分钟"的原因）
5. **观测盲区**：`ai_service.py` logger 没挂 handler，INFO 日志全部被丢弃
6. **思考模式拖慢 + 导致空内容**：qwen3.8-max 默认开启思考模式，证据是之前追问报告 `completion=368 tokens 但内容只有42字`——tokens 全被思考过程消耗，输出为空 JSON

## 修复方案（4个改动）

### 改动1：全部 LLM 调用关闭思考模式（本次补充）

**全部7处调用点**：
| 文件 | 行号 | 用途 | 模型 |
|------|------|------|------|
| ai_service.py | 94 | 通用对话流式 | 模型池 |
| ai_service.py | 142 | 通用对话非流式 | 模型池 |
| ai_service.py | 332 | 首次报告 | qwen3.8-max |
| followup_structured.py | 1559 | 矛盾检测 | qwen-flash（同步client） |
| followup_structured.py | 1806 | 追问主调用（带tools） | qwen3.8-max |
| followup_structured.py | 1934 | 违规重试 | qwen3.8-max |
| followup_structured.py | 2123 | 空内容重试 | qwen3.8-max |

**实现**：在 `ai_service.py` 新增辅助函数（按模型名判断，避免未来接 GPT 等非 Qwen 模型时传参报错）：

```python
def build_llm_extra_body(model_name: str) -> dict:
    """构建 extra_body：Qwen 系模型关闭思考模式。
    思考模式消耗大量 tokens 和时间，且曾导致输出内容为空（tokens 被思考耗尽）；
    非 Qwen 模型不传 enable_thinking，避免参数校验错误。"""
    if "qwen" in (model_name or "").lower():
        return {"enable_thinking": False}
    return {}
```

每处调用加 `extra_body=build_llm_extra_body(模型名)`（followup_structured.py 从 ai_service 导入；1559处矛盾检测模型固定 "qwen-flash" 直接传）。

### 改动2：ai_service.py — 禁止SDK静默重试 + 放宽单次超时 + 应用层可见重试

`generate_first_reading_structured`（ai_service.py:330-346）：
1. LLM 调用加 `max_retries=0`（禁止SDK静默重试，失败立即可见）
2. `timeout=120` → `timeout=300`（单次给够；关闭思考模式后实际耗时会明显下降）
3. 应用层重试最多2次，每次打日志：`LLM尝试 {n}/2 开始/失败, 耗时={elapsed}s`
4. 全部失败才 raise（任务层存入 `_generating_errors`，前端轮询可见"生成失败"）

### 改动3：ai_service.py — logger 挂 handler（观测修复）

参照 followup_structured.py:20-35 的模式，给 `ai_service.py` 的 logger 挂 StreamHandler + FileHandler（写入 `logs/ai_service.log`）。效果：`开始生成`/`LLM响应: ... 耗时=...` 落盘，以后可直接判断"正在生成还是卡住"。

### 改动4：followup_structured.py — 追问调用禁止SDK静默重试

三处 `client.chat.completions.create`（1806/1934/2123行）加 `max_retries=0`。不改 timeout（600秒足够），只消除静默重试放大（最坏30分钟 → 600秒可见失败）。

## 假设与决策

- `enable_thinking` 参数通过 `extra_body` 传递（DashScope/MaaS OpenAI 兼容端点的标准方式）
- 按模型名包含 "qwen" 判断是否传参，保证未来接入非 Qwen 模型不报错
- 矛盾检测的 qwen-flash 也关闭思考（若该模型无思考模式，参数会被忽略，无副作用）
- chat.py 任务化代码已部署生效，无需再改

## 修复后的判断方法

- 前端：进度条转圈=后台真实运行；900秒自动标记失败
- 后端：`tail -f logs/ai_service.log | grep StructuredFirstReading`
  - 有 `开始生成` 无 `LLM响应` → 正在生成中（单次最长300秒）
  - 有 `LLM尝试 n/2 失败` → 在重试
  - 有 `LLM响应: 状态=成功` → 完成
- 关闭思考模式后，预期生成耗时大幅下降（思考 tokens 不再消耗）

## 验证步骤

1. 语法检查：`python3 -c "import py_compile; py_compile.compile('app/services/ai_service.py', doraise=True); py_compile.compile('app/services/followup_structured.py', doraise=True)"`
2. 快速验证网关接受 enable_thinking 参数：用 python 直接调一次 qwen3.8-max（短prompt + extra_body），确认不报参数错误
3. 前端硬刷新，点击"查看完整解读"触发 session 18 重新生成
4. 检查 `logs/ai_service.log` 出现 `开始生成` 日志；成功则报告落库，失败则前端显示"生成失败"（不再永远转圈）
