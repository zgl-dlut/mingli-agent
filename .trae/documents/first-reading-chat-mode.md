# 首次解读改为聊天对话模式

## 摘要

用户点击"开始解读"后，应进入聊天对话界面（像微信聊天一样），先自动发送一条用户消息（包含出生年月和地点），然后 AI 流式回复报告。而不是直接在空白区域展示 AI 回复。

## 现状问题

当前 `handleGenerateFirstReading` 的流程：
1. 点击"开始解读" → 卡片退出
2. 直接开始 AI 流式生成，回复显示在空白区域（没有用户消息气泡）
3. 看起来像"生成了一个页面"，而不是"聊天对话"

## 改动方案

### 文件：`frontend/src/pages/Chat.tsx`

**改动 1：`handleGenerateFirstReading` 中先添加用户消息**

在调用 AI 之前，先 `addMessage(person.id, 'user', userMessage)` 添加一条用户消息气泡，内容类似：
```
请为我分析命理：
👤 姓名：张女士
🎂 出生日期：1990年11月10日 08:00
📍 出生地：山西省 晋中市
```

这样用户能看到自己"发送"了信息，AI 回复才是对话形式。

**改动 2：输入框在首次生成时也显示**

当前输入框只在 `hasGenerated` 时显示（第 420 行）。改为：`cardPhase === 'done'` 时也显示输入框（即使还在生成中，输入框 disabled 即可），这样用户能看到完整的聊天界面。

具体改动：
- 第 420 行：`{hasGenerated && (` → `{(hasGenerated || cardPhase === 'done') && (`
- 输入框在 `isGenerating` 时已经是 disabled 状态，无需额外处理
