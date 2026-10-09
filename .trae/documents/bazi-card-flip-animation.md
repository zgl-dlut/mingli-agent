# 命格概括抽牌效果 + 开始解读 实施计划

## 摘要

用户首次点击人物或点击"开始推算"时，先展示一张命格概括"卡片"（带翻牌/抽牌动画效果），卡片上显示八字核心信息。用户看完卡片后点击"开始解读"按钮，才进入 AI 对话生成完整报告。

## 现状分析

### 当前流程
1. `PersonList.tsx`：人物列表页，点击人物 → `navigate(/chat/${id})`
2. `Chat.tsx`：进入后立即调用 `analyzeBazi` 获取命理数据，同时展示：
   - 命格概括卡片（静态，无动画）
   - "开始解读"按钮（在卡片下方）
3. 点击"开始解读" → 调用 AI 流式生成报告 → 进入对话模式

### 问题
- 命格概括卡片直接展示，没有"抽牌"的仪式感
- 卡片和"开始解读"按钮同时出现，缺少层次感
- 从 PersonList 点击人物后直接进入对话页，没有过渡

## 设计方案

### 交互流程
1. 用户在 PersonList 点击人物 → 进入 Chat 页面
2. Chat 页面显示**加载动画**（排盘分析中...）
3. bazi 数据返回后，展示**命格概括卡片**，带**翻牌动画**（从背面翻到正面）
4. 卡片正面展示：四柱、日主、旺衰、格局、用神/喜神/忌神
5. 卡片下方出现**"开始解读"按钮**（带渐入动画）
6. 点击"开始解读" → 卡片上滑收起/淡出 → AI 流式生成开始 → 进入对话模式

### 动画设计
- **翻牌效果**：CSS 3D transform，卡片从 Y 轴旋转 180°，背面是神秘图案（太极/星空），正面是命格数据
- **卡片入场**：从底部上滑 + 缩放弹入
- **开始解读按钮**：延迟 0.5s 后渐入
- **卡片收起**：点击后卡片向上滑出 + 淡出，对话区域渐入

## 实施步骤

### 1. 新建卡片翻牌组件

**新建文件**: `frontend/src/components/BaziCard.tsx`

- Props: `baziResult: AnalyzeResult`, `onStartReading: () => void`, `visible: boolean`
- 三阶段动画：`entering`（翻牌入场）→ `visible`（静态展示）→ `exiting`（收起退出）
- 卡片背面：渐变背景 + 太极/八卦图案（CSS 绘制或 emoji）+ "命运之牌"文字
- 卡片正面：命格核心数据（四柱、日主、旺衰、格局、用神喜神忌神）
- 底部"开始解读"按钮，延迟渐入
- 使用 CSS `transform: rotateY(180deg)` + `backface-visibility: hidden` 实现翻牌
- 使用 `@keyframes` 实现入场/退场动画

### 2. 修改 Chat.tsx

**文件**: `frontend/src/pages/Chat.tsx`

改动点：
- 新增状态：`cardPhase: 'loading' | 'flipping' | 'ready' | 'exiting' | 'done'`
- `loadingBazi` 阶段：显示排盘加载动画（旋转的八卦/星空）
- `baziResult` 返回后：`cardPhase = 'flipping'`，渲染 `<BaziCard>` 组件
- `<BaziCard>` 的 `onStartReading` 回调：
  1. `cardPhase = 'exiting'`（卡片开始退出动画）
  2. 动画结束后 `cardPhase = 'done'`（显示对话区域）
  3. 触发 `handleGenerateFirstReading`（AI 流式生成）
- 移除原有的静态命格概括卡片（第 344-418 行的 `{baziResult && !hasGenerated && (...)}` ）
- 移除原有的"开始解读"按钮区域（第 427-440 行）
- `cardPhase === 'done'` 或 `hasGenerated` 时才显示对话消息和输入框

### 3. 新增 CSS 动画

**文件**: `frontend/src/index.css`（或内联在组件中）

新增动画：
- `@keyframes cardFlip`：Y 轴旋转 0 → 180°
- `@keyframes cardEnter`：从底部 translateY(100px) + scale(0.8) → 原位
- `@keyframes cardExit`：向上 translateY(-100%) + opacity 0
- `@keyframes buttonFadeIn`：opacity 0 → 1，延迟 0.6s
- `@keyframes loadingSpin`：排盘加载旋转动画

## 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/components/BaziCard.tsx` | 新建 | 翻牌卡片组件 |
| `src/pages/Chat.tsx` | 修改 | 替换静态卡片为翻牌组件，调整状态流程 |
| `src/index.css` | 修改 | 新增翻牌/入场/退场动画 keyframes |

## 验证步骤

1. 点击人物进入 Chat 页，观察加载动画 → 翻牌动画 → 卡片展示
2. 卡片正面数据正确（四柱、日主、用神等）
3. 点击"开始解读"，卡片退出，AI 流式生成开始
4. 已生成过报告的人物再次进入，直接显示对话（跳过翻牌）
5. 手机端动画流畅，无卡顿
