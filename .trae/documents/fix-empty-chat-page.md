# 修复点击开始推算后页面空白

## 摘要
用户点击"开始推算"后跳转到 Chat 页面，如果 `analyzeBazi` 失败或返回异常，页面会完全空白（无加载动画、无卡片、无对话内容）。

## 问题分析
Chat.tsx 中 `cardPhase` 状态机存在漏洞：
- `analyzeBazi` 失败时：`cardPhase = 'done'`，`baziResult = null`
- 此时翻牌卡片条件 `baziResult && ...` 不满足（不显示）
- 加载动画条件 `cardPhase === 'loading'` 不满足（不显示）
- 对话区域条件 `cardPhase === 'done'` 满足，但 `messages` 为空（无内容）
- **结果：页面完全空白**

## 修复方案

### 文件：`frontend/src/pages/Chat.tsx`

**改动 1：`analyzeBazi` 失败时不要设 `cardPhase = 'done'`**
- 失败时保持 `cardPhase = 'loading'`，并显示错误提示
- 或者新增一个 `'error'` 状态

**改动 2：对话区域为空时显示提示**
- 当 `cardPhase === 'done'` 且 `messages.length === 0` 且 `!isGenerating` 时，显示"暂无对话内容"或引导用户返回

**改动 3：`cardPhase === 'done'` 但 `baziResult === null` 时，显示"排盘失败"提示和重试按钮**
