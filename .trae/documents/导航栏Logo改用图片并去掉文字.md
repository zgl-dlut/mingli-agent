# 导航栏Logo改用图片并去掉文字

## 概述
导航栏去掉"趣算算"文字，Logo 组件根据背景深浅切换 ref1.png（深色背景）和 ref2.png（浅色背景）。

## 当前状态
- `Logo.tsx`：固定用 `/ref1.png`，`dark` 参数未使用
- `Header.tsx` L41-42：`<Logo size={24} />` + `<span>趣算算</span>`（深色背景，dark=false）
- `HistoryPanel.tsx` L163-164：`<Logo size={24} dark={true} />` + `<span>趣算算</span>`（浅色背景，dark=true）
- `LoginPage.tsx` L63-64：`<Logo size={44} />` + `<h1>趣算算</h1>`（深色背景，dark=false）
- `Chat.tsx` L954/990：`<Logo size={32} dark />`（浅色背景，对话头像，无文字）

## 改动方案

### 1. 文件：`mingli-agent/frontend/src/components/Logo.tsx`
- `dark=false`（深色背景）→ `src="/ref1.png"`
- `dark=true`（浅色背景）→ `src="/ref2.png"`
- 恢复 `dark` 参数实际使用

### 2. 文件：`mingli-agent/frontend/src/components/Header.tsx`
- 删除 L42 `<span className="text-lg font-bold text-white">趣算算</span>`
- Logo size 从 24 调大到 32（因图片含品牌名，需更大显示）

### 3. 文件：`mingli-agent/frontend/src/components/HistoryPanel.tsx`
- 删除 L164 `<span>趣算算</span>`
- Logo size 从 24 调大到 32

### 4. 文件：`mingli-agent/frontend/src/pages/LoginPage.tsx`
- 删除 L64 `<h1>趣算算</h1>`
- Logo size 保持 44

## 验证
- `npm run build` 通过
- Header 导航栏：仅显示 Logo 图片（ref1.png），无"趣算算"文字
- HistoryPanel 侧边栏：仅显示 Logo 图片（ref2.png），无"趣算算"文字
- LoginPage：仅显示 Logo 图片（ref1.png），无"趣算算"文字
- Chat 对话头像：显示 ref2.png
