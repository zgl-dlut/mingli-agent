# 去掉对话框内用户头像

## 摘要
聊天消息列表中有两处用户头像（首字母圆圈），占地方且无必要，去掉后气泡更紧凑、阅读体验更好。AI 侧 Logo 保留不动。

## 当前布局
每条消息行结构为 `flex items-start gap-2`，三栏：
1. **左侧 36px**：AI 消息显示 Logo，用户消息空占位
2. **中间 flex-1**：气泡内容
3. **右侧 36px**：用户消息显示首字母圆圈，AI 消息空占位

用户头像出现在两处：
- **正式消息列表**：`Chat.tsx` L1411-L1420（右侧 div，含首字母圆圈）
- **optimistic 临时消息**：`Chat.tsx` L1433-L1437（右侧 div，含首字母圆圈）

## 改动方案

### 文件：`frontend/src/pages/Chat.tsx`

#### 1. 正式消息行（L1380-L1421）
- **删除右侧头像 div**（L1410-L1420）
- **删除左侧空占位 div**（L1382-L1386）——AI 消息仍需 Logo，所以改为：只在 `msg.role === 'assistant'` 时渲染左侧 Logo div，用户消息不渲染左侧占位
- 用户消息气泡 `ml-auto` 保留（靠右对齐），去掉右侧头像后自然贴右

改后结构：
```
<div className="flex items-start gap-2">
  {msg.role === 'assistant' && (
    <Logo dark className="logo-sm" showText={false} />
  )}
  <div className="flex-1"> ...气泡... </div>
</div>
```

#### 2. optimistic 临时消息行（L1426-L1438）
- 删除右侧头像 div（L1433-L1437）
- 删除左侧空占位 div（L1427）

改后结构：
```
<div className="flex items-start gap-2">
  <div className="flex-1">
    <div className="... ml-auto w-fit">...</div>
  </div>
</div>
```

#### 3. 正在生成行（L1447-L1466）
- 左侧 Logo 保留
- 右侧空占位 div（L1465）删除

改后结构：
```
<div className="flex items-start gap-2">
  <Logo dark className="logo-sm" showText={false} />
  <div className="flex-1"> ...进度条... </div>
</div>
```

## 不改动
- AI 侧 Logo（左侧）保留，不影响品牌识别
- 用户消息气泡的 `ml-auto w-fit` 靠右对齐保留
- `gap-2` 间距保留

## 验证
1. `npm run build` 构建成功
2. 部署后手机查看：用户消息无头像、气泡靠右；AI 消息左侧 Logo 保留
3. optimistic 临时消息也无头像
4. 正在生成进度条左侧 Logo 保留
