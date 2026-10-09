# 品牌Logo恢复螺旋线条与圆点

## 概述
上次改动将 Logo 从螺旋图案改为"趣字+圆形"时，丢失了原有的螺旋线条和中心圆点。需要恢复这些元素，与"趣"字和圆形外框组合呈现。

## 当前状态
- 文件：`mingli-agent/frontend/src/components/Logo.tsx`
- 当前状态：只有圆形外框 + "趣"字，螺旋线条和中心圆点被删除
- 原始设计（需恢复）：螺旋 polyline + 中心 circle r=5 + 渐变色 + 阴影滤镜，支持 dark/light 主题

## 改动方案

### 文件：`mingli-agent/frontend/src/components/Logo.tsx`

恢复完整的 Logo 设计，在圆形外框 + "趣"字基础上，加回：

1. **螺旋渐变定义**：恢复 `linearGradient` + `filter`（dropShadow），dark/light 两套配色
2. **螺旋 polyline**：恢复 `generateSpiralPoints()` 函数和 `<polyline>` 元素，绘制在"趣"字下方作为背景纹理
3. **中心圆点**：恢复 `<circle cx="50" cy="50" r="5">` 
4. **渲染层级**（从下到上）：
   - 圆形外框（最底层）
   - 螺旋线条（中间层，降低不透明度避免遮挡趣字）
   - 中心圆点
   - "趣"字（最顶层）
5. **保留**：dark/light 主题切换逻辑、圆形外框、"趣"字

### 文件：`mingli-agent/frontend/public/favicon.svg`
- 同步恢复螺旋线条 + 中心圆点，与 Logo 组件保持一致

## 验证
- `npm run build` 通过
- Logo 展示：圆形外框 + 螺旋线条 + 中心圆点 + "趣"字，四层叠加
- dark 模式（浅色背景）：深棕色系
- 非 dark 模式（深色背景）：浅棕色系
