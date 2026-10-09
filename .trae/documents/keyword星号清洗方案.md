# keyword 字段 `**` 号清洗

## 根因
LLM 在 JSON 的 keyword 字段值里输出了 `**`（如 `"keyword": "**第一波危险期：...**"`），尽管 prompt 禁止。前端 [FollowupReportView.tsx](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/components/FollowupReportView.tsx) 的 BlockView 直接渲染 `<strong>{data.keyword}</strong>`，keyword 里的 `**` 字面显示为星号。

narrative 用 `renderBold` 能正确解析 `**`，不受影响。问题只在 keyword 字段。

## 修复方案
前端渲染时清洗 keyword 的 `**` 号（数据层兜底，不依赖 prompt）。

### 改动
文件：`frontend/src/components/FollowupReportView.tsx` BlockView（L146-153）

keyword 渲染前清除所有 `**`：
```tsx
const cleanKeyword = (data.keyword || '').replace(/\*\*/g, '').trim()
// 渲染：<strong>{cleanKeyword}</strong>
```

### 不改动
- narrative：已用 renderBold 正确解析 `**`，不动
- prompt：已有禁止 keyword 加 `**` 的规则，保留（减少 LLM 输出 `**` 的概率，但不能 100% 杜绝）
- 后端：追问走 JSON 直渲染，不经过 format_normalizer

## 验证
- `npx tsc --noEmit` 通过
- 硬刷新浏览器，重新生成追问，确认 keyword 前无 `**` 星号
