# PC端命理分析页面宽度优化计划

## 问题

PC端命理分析页面（Chat）内容区域没有设置 max-width，在宽屏（如 1920px）上内容撑满剩余宽度（约 1600px），导致文字行长过长、视线移动范围大、操作不便。

## 当前状态分析

### 布局结构（Layout.tsx）

```
<div className="min-h-screen ... flex flex-col">  ← 最外层
  <Header />                                       ← 顶部导航（全宽）
  <div className="flex-1 flex">                    ← 主内容区
    <HistoryPanel />                               ← 左侧历史面板（固定 320px）
    <main className="flex-1 min-h-[calc(100vh-60px)]">  ← 页面内容（撑满剩余宽度，无 max-width）
      <Outlet />                                   ← Chat 页面渲染在这里
    </main>
  </div>
</div>
```

### Chat.tsx 渲染结构

- [Chat.tsx:660-661](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/pages/Chat.tsx#L660-L661)：最外层 `<div>`，无 max-width
- [Chat.tsx:663](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/pages/Chat.tsx#L663)：标题栏 `sticky top-0`（应保持全宽）
- [Chat.tsx:686-690](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/pages/Chat.tsx#L686-L690)：内容区域 `px-4 py-4 pb-36 overflow-y-auto`（无 max-width，撑满 main）

### 根因

`<main>` 和 Chat.tsx 内容区域都没有设置 max-width，导致在宽屏上内容无限撑开。

## 修改方案

只改 Chat.tsx 的内容区域容器，添加 `max-w-5xl mx-auto`，标题栏保持全宽。

### 具体改动

**文件**：[frontend/src/pages/Chat.tsx](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/pages/Chat.tsx)

**位置**：行686-690（内容区域容器）

**改前**：
```jsx
<div 
  ref={scrollContainerRef}
  className="px-4 py-4 pb-36 overflow-y-auto"
  style={{ maxHeight: 'calc(100vh - 200px)' }}
>
```

**改后**：
```jsx
<div 
  ref={scrollContainerRef}
  className="max-w-5xl mx-auto px-4 py-4 pb-36 overflow-y-auto"
  style={{ maxHeight: 'calc(100vh - 200px)' }}
>
```

### 为什么只改内容区域

- **标题栏保持全宽**：标题栏有 `sticky top-0` + 背景色 + 边框，全宽视觉更统一
- **内容区域居中**：报告内容（Markdown 渲染）限制在 1024px 内居中，阅读体验更佳
- **移动端不受影响**：`max-w-5xl`（1024px）在移动端（<768px）不生效，屏幕宽度本身小于 1024px

## 独立性保障

- 只改 Chat.tsx 的内容区域容器 className
- 不影响追问报告和首次报告的 prompt/格式逻辑
- 不影响其他页面（AddPerson 等）
- 不影响 Layout 的 main 容器和其他页面

## 验证

1. PC端（≥1024px）访问命理分析页面，内容区域最大宽度 1024px，居中显示
2. PC端（768px-1024px）访问，内容区域撑满可用宽度（max-w-5xl 不限制）
3. 移动端（<768px）访问，布局不受影响
4. 标题栏保持全宽，视觉统一
5. 报告内容（Markdown 渲染）在 1024px 宽度下阅读舒适
