# 修复追问 422 错误导致走 mock fallback 的问题

## 任务概述

用户追问时后端返回 422 Unprocessable Entity，前端 catch 后走了 mock fallback，导致用户看到的是 mock 回复而非 skill prompt 生成的真实 AI 回复。

## 根因分析

后端日志显示两次 422 错误：
```
INFO: 127.0.0.1:35410 - "POST /api/chat/analyze-stream HTTP/1.1" 422 Unprocessable Entity
INFO: 127.0.0.1:56474 - "POST /api/chat/analyze-stream HTTP/1.1" 422 Unprocessable Entity
```

前端 `Chat.tsx` 第 227 行 `if (!response.ok) throw new Error(...)` 捕获 422 后进入 catch 分支，调用 `streamMockReply`。

422 是 Pydantic 验证错误。可能原因：
1. `baziResult` 中某些字段（如 `DayunItem` 对象列表）在 JSON 序列化后，后端 `dict` 类型无法正确解析
2. 后端 `--reload` 重载期间的短暂不可用

但 Python 直接测试 `build_skill_prompt` 和 `AnalyzeStreamRequest` 都能正常工作，所以 422 更可能是前端发送的实际数据问题。

## 实施方案

### 修改1：前端增加 422 错误日志

**文件**：`frontend/src/pages/Chat.tsx`

在 catch 分支中，打印 422 响应体中的 `detail` 信息，方便定位具体是哪个字段验证失败：

```typescript
} catch (streamErr) {
  console.warn('后端流式接口失败，使用 mock fallback:', streamErr)
  // 如果是 422，打印详细错误
  if (streamErr instanceof Error && streamErr.message.includes('422')) {
    console.error('422 请求体验证失败，请检查 bazi_data 字段')
  }
  ...
}
```

### 修改2：前端发送前清理 bazi_data

**文件**：`frontend/src/pages/Chat.tsx`

在发送请求前，对 `baziResult` 做一次安全序列化，确保所有字段都是 JSON 兼容的：

```typescript
const safeBaziData = JSON.parse(JSON.stringify(baziResult))
```

### 修改3：后端放宽 bazi_data 验证

**文件**：`backend/app/api/chat_lite.py`

将 `bazi_data: dict = {}` 改为 `bazi_data: Any = {}`，避免 Pydantic 对嵌套结构的严格验证：

```python
from typing import Any
class AnalyzeStreamRequest(BaseModel):
    ...
    bazi_data: Any = {}
```

## 涉及文件

| 文件 | 说明 |
|------|------|
| `backend/app/api/chat_lite.py` | 放宽 bazi_data 类型为 Any |
| `frontend/src/pages/Chat.tsx` | 发送前 JSON 安全序列化 + 错误日志 |
