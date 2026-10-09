# 修复追问未按 skill prompt 结构输出问题

## 问题现象

用户基于"1992年12月19日公历，吉林省吉林市"进行追问："我适合在当前公司还是换公司，在当前公司的话什么时候涨薪，要不要公司内部换部门，如果换公司的话什么时候可以找到工作，熟人介绍的吗"，返回的内容没有按照 career 专项 prompt 的结构输出，也没有进行问题拆解。

## 根因分析

### 核心问题：历史消息重复注入 + 过长上下文稀释 system prompt 指令权重

追问时，历史对话被**双重注入**，导致 system prompt 中的结构化输出指令被大量历史内容淹没，AI 模型"遗忘"了输出格式要求。

**重复注入路径：**

1. **路径 A — system prompt 内部**：`build_skill_prompt()` 将最近 5 轮历史以 `## 历史对话上下文` 追加到 system prompt 末尾
2. **路径 B — messages 列表**：`chat_lite.py` 第 67 行将完整 history 作为 user/assistant 消息传入，`ai_service.py` 拼接到 system prompt 之后

**结果**：发给 AI 的消息序列中，首次回答（1500-2200字）紧贴 system prompt，加上用户问题被发送两次，严重干扰 AI 对结构化指令的遵循。

### 设计问题：追问不需要注入历史上下文

每次追问时，`build_skill_prompt()` 已经将**完整的命盘数据**（四柱、旺衰、格局、用神、大运、流年等）注入 system prompt。这些才是命理推演的核心依据。历史对话对推演没有增量价值，反而：
- 占用大量 token，推高成本
- 稀释结构化指令的权重
- 首次回答的长文本让 AI 倾向于"延续上次的风格"而非遵循新的专项 prompt

## 修复方案

### 修改 1：`chat_lite.py` — 追问时 messages 只传当前问题

**文件**：`backend/app/api/chat_lite.py`
**第 67 行**，将：
```python
messages = request.history + [{"role": "user", "content": request.question}]
```
改为：
```python
messages = [{"role": "user", "content": request.question}]
```

**原因**：追问是独立的专项报告生成，命盘数据已在 system prompt 中，只需传当前问题即可。

### 修改 2：`skill_prompts.py` — 去掉历史对话上下文注入

**文件**：`backend/app/services/skill_prompts.py`
**`build_skill_prompt()` 函数**，删除第 519-541 行的历史对话上下文构建和追加逻辑：

删除以下代码块：
```python
    # 5. 追加历史对话上下文（如果有）
    history_section = ""
    if history and len(history) > 0:
        history_lines = []
        # 取最近5轮对话
        recent_history = history[-5:] if len(history) > 5 else history
        for turn in recent_history:
            if isinstance(turn, dict):
                role = turn.get("role", "")
                content = turn.get("content", "")
                if role and content:
                    history_lines.append(f"【{role}】：{content}")
            elif isinstance(turn, (list, tuple)) and len(turn) >= 2:
                history_lines.append(f"【{turn[0]}】：{turn[1]}")
        if history_lines:
            history_section = "\n## 历史对话上下文\n" + "\n".join(history_lines) + "\n"

    # 6. 追加排版指令
    prompt_body += FORMAT_DIRECTIVE

    # 7. 追加历史对话
    if history_section:
        prompt_body += history_section
```

替换为：
```python
    # 5. 追加排版指令
    prompt_body += FORMAT_DIRECTIVE
```

同时，`build_skill_prompt()` 函数签名中 `history` 参数保留但标记为未使用（保持接口兼容），或直接移除（需同步修改 `chat_lite.py` 和 `chat.py` 的调用处）。

**推荐**：保留参数但不再使用，添加注释说明设计意图，避免大范围接口变更。

### 修改 3：`ai_service.py` — 提高 max_tokens 上限

**文件**：`backend/app/services/ai_service.py`
**第 36 行和第 47 行**，将 `max_tokens=4000` 改为 `max_tokens=6000`

**原因**：多问题拆解时输出较长，4000 tokens 可能截断。

### 修改 4：`skill_prompts.py` — 强化多问题拆解指令

**文件**：`backend/app/services/skill_prompts.py`

在 career prompt 和 GENERAL_FOLLOWUP_PROMPT 的 `{user_question}` 之后，增加强制拆解指令：

```
**【强制拆解要求 - 不可跳过】**
上述客户一次性提出了多个问题，你必须严格按以下步骤执行：
1. 先用编号列表（①②③④⑤）逐一列出你识别到的所有子问题
2. 然后为每个子问题设立独立的 ### 三级标题，标题内容要具体（如"### 内部留任路径分析"），禁止使用"问题一""模块一"等泛泛标题
3. 每个子问题严格按"结论→命理逻辑→流月细节→行动方案"四段式展开
4. 严禁将多个子问题合并回答或笼统概括，必须逐一单独解答
```

## 涉及文件清单

| 文件 | 修改内容 |
|------|----------|
| `backend/app/api/chat_lite.py` 第 67 行 | messages 只传当前问题 |
| `backend/app/services/skill_prompts.py` `build_skill_prompt()` | 删除历史对话上下文注入逻辑 |
| `backend/app/services/skill_prompts.py` career prompt | `{user_question}` 后增加强制拆解指令 |
| `backend/app/services/skill_prompts.py` GENERAL_FOLLOWUP_PROMPT | 同上 |
| `backend/app/services/ai_service.py` 第 36、47 行 | max_tokens 4000 → 6000 |

## 验证步骤

1. 保存文件后等待 uvicorn --reload 自动重载
2. 在前端输入"1992年12月19日公历，吉林省吉林市"，生成首次解读
3. 追问："我适合在当前公司还是换公司，在当前公司的话什么时候涨薪，要不要公司内部换部门，如果换公司的话什么时候可以找到工作，熟人介绍的吗"
4. 验证返回内容：
   - 包含开头段（时空背景+格局定调）
   - 包含总纲段（一句话策略方向）
   - 包含多个 ### 三级标题子问题（留任分析、涨薪分析、转岗分析、求职分析等）
   - 每个子问题有明确结论→命理逻辑→流月细节→行动方案
   - 包含综合建议段（路径A vs 路径B）
   - 全文 1500-2500 字，无表格
5. 浏览器 console 无 mock fallback 警告（`后端流式接口失败`）
