# 命理Agent前端UI重构方案

## 一、重构目标

将当前 **6页面 + 3Tab底部导航** 简化为 **2个主视图 + 2个弹层组件** 的极简结构。

### 当前结构
```
LoginPage → AddPerson(首页) → Chat(对话)
         ↘ Recharge(充值)  ↗ Profile(个人中心)  ↗ PersonList(人物列表)
底部导航: [推算] [充值] [我的]
```

### 目标结构
```
LoginPage → MainPage(主页面+表单) → Chat(流式对话)
              ↕ HistoryPanel(侧滑历史面板)
              ↕ RechargeModal(充值弹层)
无底部导航
```

## 二、文件变更清单

### 新建文件（2个）
| 文件 | 说明 |
|------|------|
| `src/components/HistoryPanel.tsx` | 右侧滑出历史面板，合并 PersonList + Profile 功能 |
| `src/components/RechargeModal.tsx` | 充值弹层，从 Recharge.tsx 改造而来 |

### 重写文件（4个）
| 文件 | 说明 |
|------|------|
| `src/App.tsx` | 简化路由：仅保留 `/login`、`/`、`/chat/:personId` |
| `src/pages/AddPerson.tsx` | 改造为主页面，集成历史面板入口+充值弹层+底部积分提示 |
| `src/pages/Chat.tsx` | 移除内嵌人物列表+BottomNav，添加充值弹层+追问引导 |
| `src/pages/Recharge.tsx` | 改造为 RechargeModal 组件（或直接删除，逻辑迁移到新组件） |

### 删除文件（3个）
| 文件 | 说明 |
|------|------|
| `src/components/BottomNav.tsx` | 移除底部导航 |
| `src/pages/PersonList.tsx` | 合并入 HistoryPanel |
| `src/pages/Profile.tsx` | 合并入 HistoryPanel 底部 |

### 修改文件（2个）
| 文件 | 说明 |
|------|------|
| `src/components/Layout.tsx` | 移除 BottomNav 引用（如有） |
| `src/index.css` | 添加侧滑面板+充值弹层动画样式 |

### 保持不变
- `src/store/*` — 所有 Store 无需改动
- `src/api/*` — 所有 API 层保持不变
- `src/components/BaziCard.tsx` — 翻牌动画保持原样
- `src/pages/LoginPage.tsx` — 登录页保持不变
- `src/services/mockAi.ts`、`src/data/chinaAreas.ts`、`src/utils/wechat.ts`

## 三、分步实施

### 第1步：添加动画样式 (`src/index.css`)

追加侧滑面板和充值弹层的 CSS 动画：
- `fadeIn` — 遮罩层淡入
- `slideInRight` / `slideOutRight` — 历史面板右滑入/出
- `slideUp` — 充值弹层从底部滑入
- 面板/弹层的定位和层级样式

### 第2步：新建 `RechargeModal.tsx`

从 `Recharge.tsx` 提取全部充值逻辑，改造为 Modal 组件：

```
Props: { isOpen, onClose, onRechargeSuccess? }
```

UI 结构：
- 半透明遮罩层 (z-60)
- 底部滑入弹层卡片（圆角顶部）
- 标题"积分充值" + 关闭按钮
- 当前积分显示
- 充值档位网格 (40/80/120/160/200)
- 支付方式选择
- 确认充值按钮
- 保留 Mock fallback 和微信支付逻辑

### 第3步：新建 `HistoryPanel.tsx`

合并 PersonList + Profile 功能：

```
Props: { isOpen, onClose, onNavigateToChat, onNavigateToAddPerson }
```

UI 结构：
- 半透明遮罩层 (z-50)
- 右侧滑入面板 (w-80)
- 顶部栏："分析历史" + 关闭按钮
- 人物列表（可滚动）— 每个卡片显示头像首字母+姓名+出生信息
- 底部固定区域：
  - "添加新分析" 按钮
  - 用户信息（头像+用户名+注册时间）
  - 当前积分
  - 退出登录 + 清空数据按钮
- 退场动画：两层状态控制 (isOpen + isExiting)

### 第4步：重写 `AddPerson.tsx` 为主页面

改造要点：
- **顶部栏**：左侧历史按钮(☰) + 中间标题"命理推算" + 右侧积分显示
- **表单区域**：保留现有表单字段（姓名、性别、历法、出生日期时间、出生地）
- **移除**：BottomNav、底部已添加生辰列表、计费规则卡片
- **底部固定区域**：
  - 积分提示："本次分析消耗160积分，当前余额XXX积分"
  - 积分 < 160 → 显示「去充值」按钮（打开 RechargeModal）
  - 积分 >= 160 → 显示「确认分析」按钮（提交表单跳转 Chat）
- **集成**：HistoryPanel + RechargeModal 组件
- **状态**：`isHistoryOpen`、`isRechargeOpen`

### 第5步：简化 `Chat.tsx`

改造要点：
- **移除**：BottomNav 引用、内嵌人物下拉列表 (`showPersonList` 状态及相关 JSX)
- **顶部栏简化**：左侧返回箭头(→ `/`) + 中间人物名 + 右侧积分
- **添加 RechargeModal**：积分不足时弹出充值弹层（替代 `alert`）
- **输入框区域**：
  - placeholder 改为引导提示："追问：我后续的事业运势发展"
  - 输入框上方添加积分提示行："本次分析消耗40积分，当前余额XXX积分"
  - 积分不足时发送按钮变为「去充值」
- **底部定位**：移除 BottomNav 后 `bottom-0`，添加 `safe-area-inset-bottom` 适配
- **保留**：BaziCard 翻牌动画、SSE 流式输出、Mock fallback

### 第6步：简化路由 (`App.tsx`)

新路由结构：
```
/login              → LoginPage
/                   → MainPage (AddPerson 重写)
/chat/:personId     → Chat
```

移除：`persons`、`recharge`、`profile`、`add-person` 路由及相关 import。

### 第7步：清理废弃文件

- 删除 `BottomNav.tsx`
- 删除 `PersonList.tsx`
- 删除 `Profile.tsx`
- 清理 `Recharge.tsx`（如逻辑已完全迁移到 RechargeModal）
- 检查 `Layout.tsx` 是否有 BottomNav 引用

## 四、组件交互流程

### 首次分析
```
主页面(表单) → 填写生辰 → 点击"确认分析"
  → 积分 >= 160? → 是: createPerson() → navigate('/chat/:id')
  → 积分 < 160? → 打开 RechargeModal → 充值成功 → 关闭弹层 → 再次点击
```

### 查看历史
```
主页面 → 点击 ☰ → HistoryPanel 侧滑出
  → 点击人物卡片 → 关闭面板 → navigate('/chat/:id')
  → 点击"添加新分析" → 关闭面板 → 回到表单
```

### 对话中充值
```
Chat → 输入追问 → 积分 < 40? → 打开 RechargeModal → 充值 → 继续追问
```

### 退出登录
```
HistoryPanel → 底部"退出登录" → logout() → navigate('/login')
```

## 五、验证清单

- [ ] 登录后自动跳转主页面表单
- [ ] 表单填写完整 + 积分充足 → "确认分析"正常创建人物并跳转对话
- [ ] 积分不足 → 显示"去充值"按钮，点击弹出充值弹层
- [ ] 充值弹层 Mock 支付正常，成功后积分更新
- [ ] 主页面 ☰ 按钮 → 历史面板右侧滑出
- [ ] 历史面板显示人物列表，点击跳转对话
- [ ] 历史面板底部显示用户信息和积分
- [ ] 历史面板"退出登录"正常
- [ ] Chat 页 BaziCard 翻牌动画正常
- [ ] Chat 页 SSE 流式输出正常
- [ ] Chat 追问积分不足 → 弹出充值弹层
- [ ] Chat 输入框 placeholder 显示引导提示
- [ ] Chat 底部显示追问积分消耗提示
- [ ] 移动端安全区域适配正常
- [ ] 无 BottomNav 残留、无控制台报错
