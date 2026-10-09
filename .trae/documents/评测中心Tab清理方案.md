# 后台管理 Tab 清理方案

## 现状：8 个 Tab + 3 个隐藏路由

| Tab 名 | 路由 | 组件 | 有真实数据 | 评测流程中的角色 |
|--------|------|------|-----------|----------------|
| 反馈看板 | `/feedback` | FeedbackDashboard | ✅ 有API | ❌ 不属于评测流程 |
| 用量记录 | `/admin/usage` | UsageDashboard | ✅ | 运维监控，非评测 |
| 用户积分 | `/admin/users` | AdminUsersPage | ✅ | 用户管理，非评测 |
| 订单记录 | `/admin/orders` | OrdersDashboard | ✅ | 支付管理，非评测 |
| 积分充值 | `/admin/recharge` | AdminRechargePage | ✅ | 管理操作，非评测 |
| 评测中心 | `/admin/eval` | EvalDashboard | ✅ | **评测核心** |
| 人工审核 | `/admin/prompt-review` | PromptReviewPage | ✅ | **人工复审**（与评测中心内联复审重叠） |
| Prompt版本 | `/admin/prompt-versions` | PromptVersionPage | ✅ | **版本管理** |

隐藏路由（无 Tab 入口）：
| 路由 | 组件 | 状态 |
|------|------|------|
| `/admin/eval-test` | EvalDashboardTest | ❌ Mock 数据测试页，生产无意义 |
| `/admin/eval-detail/:id` | EvalDetailPage | ✅ 评测详情子页（从列表点入） |
| `/admin/eval-compare` | EvalComparePage | ✅ 版本对比子页（从列表点入） |

## 问题分析

### 1. 反馈看板 — 路由错位 + 不属于评测流程

- **路由错位**：AdminNav 里列的路径是 `/feedback`，但这个路由在 App.tsx 中挂在**用户路由树**（`/` 的 children）下，不在 `/admin` 下。管理员点"反馈看板"会跳到用户端布局，AdminNav 侧边栏直接消失
- **不属于评测流程**：反馈看板是"用户主动提交反馈 → 管理员人工打分/触发模型打分"，是一个独立的反馈收集通道，与自动评测（L1-L3+LLM）无关联
- **结论**：从评测流程角度无意义，且路由结构有 bug

### 2. 人工审核 — 与评测中心内联复审功能重叠

评测中心（EvalDashboard）已内置**逐层认同/不认同**机制（L1/L2/L3/LLM 四层，每层可标"认同"+"不认同+原因"），这是评测结果级别的人工标注。

人工审核（PromptReviewPage）是**另一套**审核系统：
- 整体评级：通过/需改进/不合格
- 问题标签：跑题/术语堆砌/编造/不通顺/无依据
- LLM 规则提炼：从审核结论提取规则 → 注入 prompt → 自动备份到版本表

**两套系统的关系**：
- 评测中心的内联复审：标注的是"机器评测结果对不对"（元评测）
- 人工审核：标注的是"报告本身好不好"+ 提炼改进规则（产品评测）
- 角色不同但入口分散，用户（你）已经困惑"该在哪标"

**结论**：功能有价值（规则提炼→prompt注入闭环），但作为独立 Tab 与评测中心割裂，导致你不知道该用哪个。建议**合并进评测中心**作为子 Tab，而非删除。

### 3. EvalDashboardTest — 纯测试页

- 文件头注释明确写："使用 Mock 数据验证版本切换和指标趋势显示"
- 无对应后端 API，纯前端 mock
- 路由 `/admin/eval-test` 存在于 App.tsx 但无 Tab 入口
- **结论**：生产环境无意义，应删除路由

### 4. 其余 Tab 均有意义

- **用量记录/用户积分/订单记录/积分充值**：业务运维必需，虽然不是评测流程但管理员日常需要
- **评测中心**：核心，含生产监控、评测结果、badcase、失败模式分析、内联复审
- **Prompt版本**：版本回滚，有后端 API 和真实操作

## 建议方案

### 方案 A：最小清理（推荐）

只清理明确无意义的，不改动有争议的：

1. **删除 `/admin/eval-test` 路由** — 纯 Mock 测试页，生产无用
2. **反馈看板从 AdminNav 移除** — 路由不在 admin 下、不属于评测流程；如果用户反馈功能仍需要，保留 `/feedback` 用户端路由即可，管理员通过直接访问 URL 操作
3. 人工审核和 Prompt 版本**暂时不动** — 等你实际开始用"认同/不认同"后再决定是否合并

### 方案 B：深度整合

在方案 A 基础上：
4. **人工审核合并进评测中心** — 作为 EvalDashboard 的一个子 Tab（如"报告审核"），与"生产监控""评测结果"并列，规则提炼入口统一
5. **Prompt版本保留独立 Tab** — 版本管理是独立操作，不适合嵌进评测中心

### 方案 C：仅分析不改动

只提供分析报告，不做任何代码改动，你自己决定后续

## 具体改动（以方案 A 为例）

### 改动 1：删除 eval-test 路由
- 文件：`frontend/src/App.tsx` 第 114 行
- 删除：`{ path: 'eval-test', element: <EvalDashboardTest /> }`
- 删除：EvalDashboardTest 的 import
- 可选：删除 `frontend/src/pages/EvalDashboardTest.tsx` 整个文件

### 改动 2：反馈看板从 AdminNav 移除
- 文件：`frontend/src/components/AdminNav.tsx` 第 5 行
- 删除：`{ path: '/feedback', label: '反馈看板' }`
- 不动 `/feedback` 路由本身和 FeedbackDashboard 组件（用户端仍可用）

### 验证
- `npm run build` 无报错
- 访问 `/admin/eval` 确认 AdminNav 不再含"反馈看板"
- 访问 `/admin/eval-test` 确认 404
- 其他 Tab 正常可用
