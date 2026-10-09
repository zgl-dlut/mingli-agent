# 导航栏添加品牌Logo

## 概述
Header 导航栏目前只有"趣算算"文字，缺少品牌 Logo。在品牌名前添加 Logo 组件。

## 当前状态
- 文件：`mingli-agent/frontend/src/components/Header.tsx`
- L40：只有 `<span className="text-lg font-bold text-white">趣算算</span>`，无 Logo
- Header 背景为深色渐变（`from-primary-600 to-primary-800`），Logo 应用 `dark` 属性（浅色背景配色不适用，深色背景应用非 dark 模式的浅棕色系）

## 改动方案

### 文件：`mingli-agent/frontend/src/components/Header.tsx`

1. **导入 Logo**：`import Logo from './Logo'`
2. **在"趣算算"文字前添加 Logo**：`<Logo size={24} />`（深色背景，不传 dark 属性，使用浅棕色系配色）
3. 位置：L40 的 `<span>` 前，与文字之间保持 `gap-2` 间距（外层 div 已有 `gap-2`）

## 验证
- `npm run build` 通过
- 导航栏显示 Logo + "趣算算" 文字
