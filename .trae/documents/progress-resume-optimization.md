# 刷新后进度条不重置 + 首次报告防中断优化

## 回答用户问题：PC 和 H5 都生效吗？

**是的**。项目只有一套前端代码（Vite + React + Tailwind，响应式设计），PC 和 H5 共用同一个 `Chat.tsx`。`Layout.tsx` 仅用 `window.innerWidth >= 768` 决定侧边栏展示方式，进度条逻辑完全共用。改一处两端都生效。

## 问题诊断（基于代码探索）

### 问题1：追问报告刷新后进度条从10%重置
- 进度是前端模拟的（`startProgress` 从 `elapsed=0` 开始计时，[Chat.tsx:269-294](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/pages/Chat.tsx#L269-L294)）
- 后端 `_generating_start` 已存了任务开始时间戳（[chat.py:249](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/api/chat.py#L249)），但 `generating-status` 接口没返回给前端

### 问题2（更严重）：首次报告刷新会中断生成
- 首次报告走 SSE 内联生成（[chat.py:351-432](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/api/chat.py#L351-L432)），**没有注册到 `_generating_tasks`**
- SSE 绑定请求连接：用户刷新 → 连接断开 → 生成被取消 → **每次刷新都是从头重新生成**
- 这正是"首次报告20分钟没完成"的根因：用户多次刷新，每次都重启生成，永远跑不完
- 刷新后 `generating-status` 返回 `generating=false`，进度条无法恢复

## 方案

### 改动1：后端 `chat.py` — 首次报告任务化（仿照 send_message 模式）

把 `get_first_reading` 端点从"SSE 内联生成"改为"后台任务 + 队列流式推送"，与 `send_message`（第230-249行）模式一致：

1. 新增 `_generate_and_save_first_reading(session_id, person, queue)` 后台任务函数：
   - 独立 `async_session()` 数据库会话（不依赖请求级 session）
   - 先检查是否已有 assistant 消息（防重复生成），有则直接结束
   - 调用 `generate_first_reading_structured` 生成，chunk 写入 queue
   - 完成后存库，finally 中清理 `_generating_tasks`/`_generating_start`
2. `get_first_reading` 端点改造：
   - 已有 assistant 消息 → 直接返回（保持原逻辑）
   - `session_id in _generating_tasks` 且未超时 → 返回 409（防止刷新后重复点击触发第二次生成）
   - 否则创建后台任务，注册到 `_generating_tasks[session_id]` 和 `_generating_start[session_id]`，从 queue 读取 chunk 流式推送
   - 客户端断开后任务继续运行（与追问报告一致）

复用同一个 `_generating_tasks` 字典是安全的：首次报告完成前不会有追问（追问前提是有首次报告），两者不会并发；且 `send_message` 的 409 检查会自动阻止"首次报告生成中发追问"。

### 改动2：后端 `chat.py` — `generating-status` 返回已耗时

在返回体中增加 `elapsed_seconds`（[chat.py:348](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/api/chat.py#L348)）：

```python
elapsed = int(time.time() - _generating_start.get(session_id, time.time())) if generating else 0
return {"generating": generating, "error": error, "elapsed_seconds": elapsed}
```

### 改动3：前端 `api/chat.ts` — 类型更新（第80-84行）

`getGeneratingStatus` 返回类型增加 `elapsed_seconds?: number`

### 改动4：前端 `Chat.tsx` — `startProgress` 支持已耗时偏移

1. `startProgress(personId: number, elapsedOffset = 0)`（[Chat.tsx:270](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/pages/Chat.tsx#L270)）：
   - `let elapsed = elapsedOffset`（不再固定从0开始）
   - 初始 percent/time 按 offset 立即计算（抽出计算逻辑为内部函数，初始化和定时器共用），不再固定显示10%
2. 刷新恢复处（[Chat.tsx:375-385](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/pages/Chat.tsx#L375-L385)）：
   - `const { generating, error, elapsed_seconds } = await chatApi.getGeneratingStatus(s.id)`
   - `startProgress(id, elapsed_seconds || 0)`
   - 恢复进度条时同时 `setCardPhase('done')`，避免首次报告生成中刷新后又显示"查看完整解读"按钮导致用户重复点击
3. 正常发送路径（第506、682行）不传 offset，行为不变

### 改动5：前端 `Chat.tsx` — `handleGenerateFirstReading` 处理 409

catch 中识别 409（生成已在进行中）：不弹"生成失败"，改为恢复进度条 + 启动轮询（`startProgress` + `startGeneratingPoll`），避免用户误以为失败。

## 假设与决策

- 复用 `_generating_tasks`/`_generating_start` 字典，不新建首次报告专用字典（首次与追问不会并发）
- 首次报告超时阈值复用 `_GENERATING_TIMEOUT = 900` 秒
- 不改追问报告现有链路，只改首次报告链路和进度恢复逻辑

## 验证步骤

1. 语法检查：`python3 -c "import py_compile; py_compile.compile('app/api/chat.py', doraise=True)"`
2. 前端类型检查：`cd frontend && npx tsc --noEmit`（如项目有配置）
3. 手动验证：
   - 生成首次报告中途刷新 → 进度条恢复且百分比按已耗时显示（不从10%重置）→ 报告最终正常完成
   - 生成追问报告中途刷新 → 同上
   - 首次报告生成中点击"查看完整解读" → 不重复生成
