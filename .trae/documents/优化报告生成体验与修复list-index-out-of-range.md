# 优化报告生成体验与修复 list index out of range

## 任务概述

1. **体验优化**：报告生成时，先展示"正在生成中"的动态提示（告知用户需等待几分钟），生成完毕后再完整输出
2. **Bug修复**：解决生成过程中的 `list index out of range` 错误

## 当前状态分析

### 问题1：`list index out of range` 根因

**根因位置**：`backend/app/services/ai_service.py` 第 39 行

```python
if chunk.choices[0].delta.content:  # ← choices 可能为空列表 []
    yield chunk.choices[0].delta.content
```

OpenAI 兼容接口的流式响应中，最后一个 chunk 通常只包含 `finish_reason`，`choices` 为空列表 `[]`。直接访问 `choices[0]` 会触发 `IndexError`。

### 问题2：首次生成缺少 Loading 过渡

用户点击"查看完整解读"后，命格卡片立即消失（`cardPhase` 设为 `'done'`），进入对话视图。但在 AI 第一个 token 到达之前，`currentMessage` 为空字符串，用户看到的是**空白页面**，没有"正在生成"的提示。

当前前端只有：
- 排盘阶段的太极旋转动画（`cardPhase === 'loading'`）
- 流式输出末尾的灰色小圆点脉冲（`isGenerating && currentMessage`）

**缺失**：`isGenerating` 为 true 但 `currentMessage` 为空时的过渡提示。

## 实施方案

### 修改1：修复 `ai_service.py` 中的 `list index out of range`

**文件**：`backend/app/services/ai_service.py`

**改动**：在流式和非流式两个分支中，增加 `choices` 非空检查。

```python
# 流式分支（第 38-40 行）
async for chunk in stream_response:
    if chunk.choices and chunk.choices[0].delta.content:
        yield chunk.choices[0].delta.content

# 非流式分支（第 47-48 行）
if response.choices:
    yield response.choices[0].message.content or ""
else:
    yield ""
```

### 修改2：前端增加"正在生成"动态提示

**文件**：`frontend/src/pages/Chat.tsx`

**改动位置**：在消息列表渲染区域，当 `isGenerating` 为 true 且 `currentMessage` 为空时，展示生成中提示。

在现有消息气泡渲染之前（约第 389 行 `{currentMessage && (...)}` 之前），添加：

```tsx
{/* 正在生成提示 */}
{isGenerating && !currentMessage && (
  <div className="flex items-start gap-3 mb-4">
    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center flex-shrink-0">
      <span className="text-white text-xs">☯</span>
    </div>
    <div className="bg-white/80 backdrop-blur-sm rounded-2xl rounded-tl-sm px-5 py-4 shadow-sm border border-indigo-100/50 max-w-[85%]">
      <div className="flex items-center gap-2">
        <div className="bazi-loading-mystic text-indigo-400">☯</div>
        <span className="text-indigo-400 text-sm animate-pulse">正在生成命理报告，预计需要 2-3 分钟，请稍候...</span>
      </div>
    </div>
  </div>
)}
```

**效果**：用户点击"查看完整解读"后，立即看到一个带旋转太极符号的提示气泡，告知用户正在生成且需等待 2-3 分钟。当第一个 token 到达后，提示自动被实际内容替换（因为 `currentMessage` 变为非空，条件 `!currentMessage` 不再满足）。

## 涉及文件

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/app/services/ai_service.py` | Bug修复 | 增加 `choices` 非空检查，防止 IndexError |
| `frontend/src/pages/Chat.tsx` | 体验优化 | 增加"正在生成中"动态提示气泡 |

## 验证步骤

1. 启动后端和前端，输入生辰信息进行排盘
2. 点击"查看完整解读"，确认出现"正在生成命理报告"的提示气泡
3. 等待模型返回第一个 token 后，确认提示气泡自动消失，流式内容正常显示
4. 等待报告生成完毕，确认完整输出无 `list index out of range` 错误
5. 检查后端日志，确认无 `IndexError` 异常
