# 修复：生成过程中进度面板只显示"正在准备中"不动态更新

## 根因

**nginx 默认对代理响应做缓冲**，SSE 小数据块（`__PROGRESS__正在分析需求\n` 约 30 字节）被攒在 nginx 缓冲区里不推给前端，直到缓冲区满（4-8KB）或响应结束才一起发。

前端在整个生成过程中收不到任何 `__PROGRESS__` 标记 → `agentSteps` 为空 → 一直显示兜底文案"正在准备…"。

证据：
- nginx 配置 `/api/` location 没有 `proxy_buffering off`
- 后端 `StreamingResponse` 没有设置 `X-Accel-Buffering: no` header
- JSON 内容块较大能触发缓冲区刷新所以看起来"能流式"，但 progress 标记太小被吞

## 修改方案

### 1. 后端：StreamingResponse 加 `X-Accel-Buffering: no` header

**文件**：`backend/app/api/chat.py`

3 处 `StreamingResponse` 调用（行 183、371、707）都加 header：

```python
return StreamingResponse(
    stream_response(),
    media_type="text/event-stream",
    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
)
```

`X-Accel-Buffering: no` 是 nginx 识别的特殊响应头，告诉 nginx 对这个响应禁用缓冲，每个 chunk 立即透传给客户端。

### 2. 前端：兜底文案改为更动态的等待提示

**文件**：`frontend/src/pages/Chat.tsx` 行 1585

兜底面板（还没收到任何 progress 标记时）从静态"正在准备…"改为带省略号动画的"正在准备中…"（已有 `animate-pulse`），与豆包式面板风格一致。这是体验优化，不是核心修复。

## 验证

1. 部署后端 + nginx 重启
2. 微信发一条择日问题，观察进度面板是否动态显示步骤（"正在分析需求" → "获取命盘数据" → "列出候选日期" → …）
3. 微信发一条普通追问，观察进度面板是否显示"AI 生成解读" → "整理结果"
