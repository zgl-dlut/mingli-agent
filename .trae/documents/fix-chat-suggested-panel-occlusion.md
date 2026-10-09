# 修复：追问回答完成后「试试追问」面板遮挡最新回复

## Summary

追问回答完成后，底部「试试追问」推荐面板出现，滚动位置没把面板高度算进去，最新一轮"问题→回答"被压在折叠线以下（截图1）。**期望（按用户澄清）：滚动定位到"最后一条追问问题贴住可视区顶部"，回答从问题下方自然展开，用户自上而下阅读；面板不出现在问题上方、不遮挡问题；回答较短时一屏完整可见（= 截图2）。**

## Current State Analysis（根因，已核实代码）

**布局**（[Chat.tsx L909-941]）：垂直 flex 列 = 标题栏 + 滚动容器(flex:1) + 底部输入栏(flex-shrink-0)。推荐面板在底部栏内部、输入行上方（L1155-1198，普通流）。**面板出现使滚动容器可视高度被压矮约 100-110px。**

**时序缺陷**（追问完成 L852-859）：`fetchMessages` 后消息 effect（L397-399，依赖 `[messages, currentMessage, pendingUserMsg]`）按"面板未出现"的全高容器滚到底；随后 `setShowSuggested(true)` 面板渲染压矮容器，**`showSuggested` 不在任何滚动 effect 依赖里，无人重新滚动** → 最新回复被压到折叠线下方；叠加微信 webview smooth 滚动与布局变化竞争，实际偏差可达一屏。

**`setShowSuggested(true)` 三个调用点**：L385 后台生成轮询完成、L634 首次报告完成、L858 追问回答完成——一个 effect 全覆盖。

**现有滚动设施**（L260-288）：`isNearBottom()` 150px 守卫 + 100ms 防抖 + `container.scrollTo`（刻意不用 scrollIntoView 防影响外层布局）。消息 JSX：每条消息外层 `<div key={msg.id} className="flex items-start gap-2">`（L1038），无定位属性。

## Proposed Changes

**仅改 1 个文件**：[Chat.tsx](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/pages/Chat.tsx)

### 改动 1：给消息外层加定位属性（L1038）

```tsx
<div key={msg.id} data-role={msg.role} className="flex items-start gap-2">
```

### 改动 2：新增 `showSuggested` 监听 effect（放在 L399 现有消息滚动 effect 之后）

```tsx
// 推荐Chip出现后底部栏增高、滚动容器被压矮，需重新定位：
// 锚定"最后一条追问问题"贴可视区顶部，回答在下方展开（短回答时浏览器自动钳制为整屏可见）
useEffect(() => {
  if (!showSuggested) return
  const timer = window.setTimeout(() => {
    const container = scrollContainerRef.current
    if (!container) return
    const bubbles = container.querySelectorAll('[data-role="user"]')
    const lastQuestion = bubbles[bubbles.length - 1] as HTMLElement | undefined
    if (!lastQuestion) {
      scrollToBottom({ force: false })  // 首次报告等无追问场景：回退滚到底
      return
    }
    if (!isNearBottom()) return  // 用户上翻阅读时不拽回，与现有守卫口径一致
    const containerRect = container.getBoundingClientRect()
    const elRect = lastQuestion.getBoundingClientRect()
    const targetTop = container.scrollTop + (elRect.top - containerRect.top) - 8
    container.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' })
  }, 200)  // 盖过消息effect的100ms防抖竞态，确保面板已参与布局
  return () => window.clearTimeout(timer)
}, [showSuggested])
```

**设计要点**：
- **锚定问题而非滚到底**：`getBoundingClientRect` 相对计算（不依赖 offsetTop 定位上下文），问题顶部贴容器顶留 8px 呼吸空隙；回答长→问题固定在顶、向下阅读；回答短→scrollTop 被浏览器钳制在最大值，等效"整屏完整可见"（自动兼容截图2 两种形态）
- 只在 `showSuggested` false→true 跳变触发；面板常驻/隐藏期间不触发
- `isNearBottom()` 守卫：面板出现场景距底 ~105px < 150px 阈值会执行定位；生成期间刻意上翻的用户不被拽回
- 兜底链：找不到用户消息（首次报告）→ 滚到底；`targetTop<0` → 钳 0
- 若真机（微信 iOS）验证 smooth 滚动仍偶发不准，此处 behavior 改 `'auto'` 兜底（备用，不预做）

**不改的**：滚动公式/isNearBottom 阈值/面板 JSX 样式/后端；PROMPT_VERSION 不动（纯前端）。

## Assumptions & Decisions

- "贴顶部"取问题气泡外层（含头像行）顶部对齐，视觉即"问题在最上"
- 首次报告完成路径无追问气泡，回退滚到底（报告卡片场景本就需要看完整卡片底部）

## Verification

1. `npm run build` 通过 → `git commit`（回滚点）→ tar/scp 替换 dist（保留目录）→ `docker restart mingli-nginx` → 外网 200 + 新 JS hash
2. 微信真机验证：
   - 长回答：追问→回答完成，**最后一条问题贴可视区顶部**，回答向下展开，面板不挡问题；下滑可读完全文，到底时回答结尾紧贴面板顶边
   - 短回答：问题+回答一屏完整可见（=截图2）
   - 首次报告完成：滚动到底，不被遮挡
   - 面板出现后上翻看历史不被拽回；打字隐藏面板无跳动；点 chip 正常发送
