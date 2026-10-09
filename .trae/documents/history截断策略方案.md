# history（对话历史）截断策略方案

## 问题背景

换 qwen-max 后报错 `Range of input length should be [1, 30720]`，根因是 history 累积过长。

## 现状分析

### history 的构建
- **位置**：`chat.py` 第170-178行
- **逻辑**：取该 session（人物会话）下**所有** ChatMessage（按时间排序），包括所有 user 和 assistant 消息
- **传给 LLM**：在 `followup_structured.py` 第567行，`messages = truncated_history + [当前问题]`，作为 OpenAI messages 数组的标准上下文

### history 的作用
- system_prompt（build_structured_prompt 返回）里**完全没有**引用 history，只有命盘数据 + 用户问题 + 输出规则
- history 的唯一作用是 OpenAI messages 数组的标准上下文：让 LLM"看到"之前聊了什么，维持对话连贯性
- 首次报告（generate_first_reading）**不传 history**，只有一条 user 消息

### session 13 实际情况（查数据库确认）
- 首次报告 1 条（2797字）+ 追问 2 条（1271+1126字）
- 同一个4子点问题**重复发送 20+ 次**，每次生成 1700-2500 字 JSON 报告
- 总 history 字符量约 4 万+，远超 qwen-max 的 30720 tokens 限制
- **重复消息堆积有害**：LLM 看到一堆相同问答，会"参考"之前的开头结构，导致输出雷同（日志显示 LLM 一直重复"你怕的被动裁员和返岗换组"开头）

### 核心判断
- 用户问题本身自包含（"26年9月返岗后..."已包含所有上下文）
- system_prompt 有完整命盘数据，不依赖 history
- history 在这个 case 里价值有限，甚至有害（导致输出重复）

## 方案：保留最近 1 轮对话

### 决策理由
- 完全不传 history：如果用户追问基于之前回答的延伸（如"你说的11月离职，那12月呢"），LLM 不知道之前说了什么
- 保留最近 1 轮（1个 user + 1个 assistant）：足够维持连贯性，又不会让重复问答堆积影响输出
- 比"6000字"截断更可控：6000字可能包含 3-4 轮重复问答，1 轮更干净

### 涉及文件
`/Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py`

### 主要改动

**替换当前 6000 字符截断逻辑（第549-567行）为：保留最近 1 轮对话**

```python
# 3. 构建 messages（history + user_question）
# 截断 history：qwen-max 上下文限制 30720 tokens，system_prompt 约 14000 tokens，
# completion 预留 6000，history+question 最多约 10000 tokens。
# 只保留最近 1 轮对话（1个 assistant + 1个 user），维持追问连贯性即可。
# 完整历史不传：避免重复问答堆积导致输出雷同 + 上下文超限。
_MAX_HISTORY_ROUNDS = 1  # 保留最近几轮（1轮 = 1个assistant + 1个user）
# 从末尾往前取：跳过最后的 user（当前问题单独加），往前找最近的 assistant+user 对
truncated_history = []
# history 末尾可能是连续的 user（重试未回答），跳过末尾 user 找最近的 assistant
_hist_reversed = list(reversed(history))
_assistant_found = False
for msg in _hist_reversed:
    if msg.get("role") == "assistant" and not _assistant_found:
        truncated_history.insert(0, msg)
        _assistant_found = True
    elif msg.get("role") == "user" and _assistant_found:
        truncated_history.insert(0, msg)
        break  # 取到 assistant + 对应的 user，凑齐 1 轮
# 如果没找到 assistant（首次追问无历史），truncated_history 为空
messages = truncated_history + [{"role": "user", "content": user_question}]
```

### 日志保留
保留截断日志，打印原始/保留条数：
```python
logger.info(
    f"[StructuredFollowup][排查] history截断: 原始{len(history)}条 → "
    f"保留最近1轮{len(truncated_history)}条"
)
```

## 假设与决策
- **假设**：用户追问通常自包含，最近 1 轮对话足以维持连贯性
- **决策**：不用"字数"截断（不可控），用"轮数"截断（1轮 = 1 assistant + 1 user），语义更清晰
- **风险**：如果用户追问依赖 2 轮以前的回答，可能丢失上下文。但命理追问场景下概率低，且 system_prompt 有完整命盘数据兜底

## 验证步骤
1. 改完后 uvicorn --reload 自动加载
2. 重新发送4子点问题
3. 读 backend.log 确认：
   - `history截断` 日志显示保留 1-2 条
   - LLM 不再报 30720 超限
   - LLM 输出开头不再重复"你怕的被动裁员"（因为看不到一堆重复历史了）
   - 拆解是否拆出 4 个 subtopic
   - closing 是否被后端兜底清空
