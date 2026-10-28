# 趣算算 V3 MVP 后续开发 ExecPlan

本 ExecPlan 是一份活文档。进度追踪、意外发现、决策日志和成果与复盘章节必须随工作推进持续更新。计划以《趣算算·产品方向与功能框架 V3（收敛版）》为产品事实源，以当前仓库代码为工程事实源。

**创建时代码基线：**
- 分支：`main`
- Commit SHA：`260545494ed97eab9a12d3662a65582272a72ebb`
- 时区：`Asia/Shanghai`（UTC+08:00）
- 工作区状态：`mingli-agent/backend/requirements.txt` 已有未提交的 `aiosqlite==0.20.0`，这是本机 SQLite 启动修复，执行时必须保留并纳入 Milestone 0
- 提交策略：按里程碑提交；每个里程碑验证通过后创建独立 conventional commit，不自动 push

## Summary

本计划把现有“今日 / 对话 / 我的”三 Tab 产品升级为 V3 的“今日 / 解读 / 对话 / 我的”四 Tab MVP。升级后，用户可以基于同一份标准化命盘快照查看基础解读、月运、年报、关系视角和问答解读，也可以为本人档案创建一个命局人格，在独立会话中获得带结构化摘要记忆的第一人称陪伴。商业化从积分单次解锁转为免费、轻享、全享三种权益状态，其中付费档位为轻享 ¥28/月和全享 ¥58/月；MVP 只完成服务端权益闭环和模拟开通，不接真实 IAP 或代扣。

实施采用兼容式演进：保留现有 `Person`、`ChatSession`、`ChatMessage`、`ContentUnlock` 和积分流水；新增标准化命盘快照、报告、订阅、用量、人格会话、人格记忆和安全事件模型。旧报告在用户首次打开报告库时惰性映射，不重跑 AI、不丢历史；旧 `/chat/:personId` 和现有 API 保留一个版本的兼容入口。

## 目标与全局视角

完成后，简中国内版用户能够：

1. 在四 Tab App 壳中明确区分“解读”和“人格对话”。
2. 录入本人档案后免费查看基础解读，并用同一份 `chart_snapshot` 驱动全部报告和命局人格。
3. 在报告库查看五类报告：`base_report`、`monthly_brief`、`annual_brief`、`relation_report`、`qa_reading`。
4. 首次打开月运、年报或关系报告时启动异步生成，离开页面后任务继续，完成后可回看。
5. 为本人档案创建一个命局人格，在独立全屏会话中聊天、切换会话、查看和清空结构化摘要记忆。
6. 查看当前订阅、档案上限、解盘问数和人格会话额度；通过模拟开通验证免费、轻享、全享三种权益。
7. 在危机语句、未成年人和连续使用两小时场景下得到明确、可验证的安全处理。
8. 继续访问历史档案、历史聊天、历史积分流水和已解锁内容；不能再从用户端购买新积分。

**需求对齐记录：**
- 用户原始需求：按照产品文档进行后续开发。
- Agent 理解：以 2026-10-28 的 V3 收敛版取代 V2 商业主线，完成完整 V3 MVP，而不是只做页面原型。
- 面向用户：国内简体中文终端用户；后台运营人员继续使用现有管理端。
- 做：
  - 当前 React/Vite 430px App 壳上的完整 V3 MVP。
  - 四 Tab、标准化命盘快照、五类报告、两套 AI、订阅权益、本人命局人格、结构化摘要记忆、合规门禁。
  - 两档订阅的模拟开通、到期、降级与用量控制。
  - 历史数据兼容、惰性报告迁移和积分停充。
  - 自动化测试、构建、迁移验证、Playwright 截图和独立代码审计。
- 不做：
  - React Native、新原生客户端、繁体中文、英文和海外支付。
  - Apple IAP、安卓渠道 IAP、微信/支付宝周期扣款。
  - 他人档案命局人格、真人咨询、社区、主动私聊、十神分灵、每日唤醒、抽灵纹。
  - 人格语音、逐条可编辑长期记忆、PDF 导出、优惠券、邀请裂变。
  - 积分抵扣订阅首月；MVP 仅保留余额、流水和旧内容兼容。

## Assumptions & Decisions

以下决策已由用户确认，执行时不得重新选择：

1. 交付范围为完整 V3 MVP，按里程碑分批落地。
2. 客户端沿用当前 React/Vite App 壳；不新建 React Native 工程。
3. 订阅先完成权益闭环与模拟开通，真实支付后置。
4. 订阅档位为：
   - 免费：1 份档案、基础解读、每日 3 次解盘问答、每月 3 次人格会话，每次最多 20 个用户回合。
   - 轻享：¥28/月、参考 ¥198/年；3 份档案、完整深度解读、月运、每日解盘问答无限、每月 30 次人格会话，每次最多 20 个用户回合；不含年报。
   - 全享：¥58/月、参考 ¥398/年；档案不限、全部报告含年报、解盘问答无限、人格会话无限。
5. 人格会话计量定义为：创建新会话时消耗 1 次额度；同一会话最多 20 个用户消息，达到上限后必须新建会话。
6. 免费人格额度按自然月重置，不是一次性体验。
7. 首发只允许 `is_self=true` 的本人档案创建命局人格；他人档案只提供关系视角。
8. 人格记忆采用结构化摘要，保存称呼、近况、偏好、重要关系和阶段摘要；MVP 支持查看、关闭使用和全部清空，不支持逐条编辑。
9. 人格头像使用内置命局头像集，按日主/五行稳定映射；不在运行时调用图片生成服务。
10. 旧报告采用惰性迁移：首次打开报告库时扫描本人旧消息并建立映射记录，不批量重跑 AI。
11. 月运、年报、关系报告首次打开时按需异步生成并缓存；基础解读沿用建档生成链路。
12. 积分存量兼容并停充：保留余额、流水、旧内容和管理端查询，隐藏充值入口，用户充值 API 返回明确停用码；MVP 不实现积分抵扣订阅。
13. 首发为简中国内版，不引入 i18n 框架。
14. V3 必须使用功能开关灰度；默认 `OTHER_PERSONA_ENABLED=false`、`POINTS_RECHARGE_ENABLED=false`。

## Current State Analysis

### 已有可复用能力

- `mingli-agent/backend/app/models/person.py` 已保存生辰和完整 `bazi_data_json`，可作为生成标准化 `chart_snapshot` 的原始数据。
- `mingli-agent/backend/app/api/person.py` 已完成档案创建、去重、排盘、首次会话和首次解读准备。
- `mingli-agent/backend/app/api/chat.py` 已有档案归属校验、问题校验、SSE、后台异步生成、断线后状态恢复和消息落库。
- `mingli-agent/backend/app/api/deep_reading.py` 已有“大纲 → 异步正文 → 持久化”的两段式模式，可复用为 `qa_reading`。
- `mingli-agent/backend/app/schemas/report_schema.py` 与 `followup_structured.py` 已提供结构化问答报告、命盘依据和编造检测。
- `mingli-agent/backend/app/api/daily.py` 与 `daily_fortune_service.py` 已有流日算法和日更内容，但外部契约仍使用 `grade/yi/ji`。
- `mingli-agent/frontend/src/pages/Chat.tsx` 已有成熟的流式消息、后台生成恢复、档案选择、语音和深度解读交互。
- `mingli-agent/frontend/src/pages/Today.tsx`、`Chart.tsx`、`ProfilePage.tsx`、`PersonsPage.tsx` 和现有 V2 设计稿可作为 V3 UI 底盘。

### 主要缺口

- 当前导航仍是三 Tab；“解盘问答”和未来的“命局人格”没有数据域和界面隔离。
- `Person` 没有 `is_self`、`relationship_type`、标准化 `chart_snapshot` 和快照版本。
- 没有 `Report` 聚合模型；首次报告、深度解读正文仍嵌在聊天消息 JSON 中。
- 没有订阅、用量计数和统一 `entitlement` 服务；计费逻辑散落在档案、追问和深读接口。
- 没有人格、人格会话、人格消息、结构化记忆和安全事件模型。
- 日运仍对外暴露 `good/neutral/caution` 与“宜/忌”，不符合 V3 的“顺畅/平稳/收束、适合/留意”。
- 用户端仍显示充值入口，创建人物和问答仍依赖积分扣费。
- 测试工程不完整：前端有 Vitest 文件但无 `test` 脚本；后端 requirements 缺 `pytest`、`pytest-asyncio`、`greenlet`，当前 Alembic 在线历史查询因缺 `greenlet` 失败。
- Alembic 当前唯一 head 为 `010_content_unlocks`。新迁移必须以它为 `down_revision`，禁止重新 autogenerate 旧的 `508b12ccf9f5` 破坏性变更。
- 当前工作区已有 `aiosqlite==0.20.0` 修改，不能覆盖或丢失。

## Proposed Changes

### 数据模型与迁移

新增三组迁移，全部兼容 SQLite 本地开发和 MySQL 8 生产：

1. `mingli-agent/backend/alembic/versions/011_v3_profile_subscription.py`
   - 给 `persons` 增加 `is_self`、`relationship_type`、`relationship_note`、`consent_confirmed_at`、`chart_snapshot_json`、`chart_snapshot_version`、`chart_snapshot_updated_at`。
   - 每个用户最小 `person.id` 回填为本人，其余回填 `other`；应用层强制每个用户最多一个本人档案。
   - 新建 `subscriptions` 和 `usage_counters`。
2. `mingli-agent/backend/alembic/versions/012_v3_reports.py`
   - 新建 `reports`；使用确定性的 `identity_key` 唯一约束规避 MySQL/SQLite 对 NULL 唯一性的差异。
   - 字段包括用户、主档案、关系档案、报告类型、周期、状态、预览、正文、命盘快照、Prompt 版本、旧消息来源、失败原因和时间戳。
3. `mingli-agent/backend/alembic/versions/013_v3_persona.py`
   - 新建 `personas`、`persona_conversations`、`persona_messages`、`persona_memories`、`safety_events`。
   - `personas.person_id` 唯一，确保一份档案一个人格；服务层额外限制仅本人档案。

更新 `mingli-agent/backend/alembic/env.py` 导入全部新增模型，防止后续 autogenerate 漏表。

### 标准化命盘快照

新增 `mingli-agent/backend/app/services/chart_snapshot_service.py` 和 `mingli-agent/backend/app/schemas/chart_snapshot_schema.py`。

`chart_snapshot` 使用英文 snake_case，至少包含：

```text
version
generated_at
birth_profile
pillars
day_master
ten_gods
strength
useful_elements
unfavorable_elements
pattern
luck_cycles
annual_cycles
monthly_cycles
source_hash
```

现有中文键 `bazi_data_json` 保持冻结，不做破坏性改名。服务按“已有标准化快照 → 从现有 `bazi_data_json` 转换 → 缺失时重新排盘”的顺序惰性生成，并以 `source_hash` 判断是否失效。报告和人格只能调用此服务，不允许各自重新拼命盘字段。

### 订阅、权益与存量积分

新增：

- `backend/app/models/subscription.py`
- `backend/app/models/usage_counter.py`
- `backend/app/services/entitlement_service.py`
- `backend/app/schemas/entitlement_schema.py`
- `backend/app/api/subscription.py`

计划目录以代码常量定义 `free/light/full` 权益，价格仅用于 UI 展示；接口为：

```text
GET  /api/subscriptions/plans
GET  /api/subscriptions/current
POST /api/subscriptions/mock-activate
POST /api/subscriptions/mock-expire
GET  /api/entitlements/me
```

`entitlement_service` 提供统一函数：

```python
async def get_entitlement(db, user_id, now=None) -> EntitlementSnapshot
async def require_profile_slot(db, user_id) -> None
async def consume_usage(db, user_id, metric, scope_id=None) -> UsageResult
async def require_report_access(db, user_id, report_type) -> None
```

档案创建、解盘问答、报告生成和人格新会话只能通过这些函数校验，不在 API 内复制额度逻辑。计数更新必须使用事务和唯一键重试，避免并发超额。

修改 `backend/app/api/payment.py`：用户创建充值订单返回 HTTP 410 和 `points_recharge_disabled`；支付回调、历史订单查询和管理端充值保留兼容。修改前端移除充值入口，但保留积分余额及流水入口，标记为“历史积分”。

### 五类统一报告

新增：

- `backend/app/models/report.py`
- `backend/app/schemas/report_v3_schema.py`
- `backend/app/services/report_service.py`
- `backend/app/services/report_generation_service.py`
- `backend/app/services/legacy_report_adapter.py`
- `backend/app/api/report.py`

统一报告 envelope：

```text
report_id, report_type, status, primary_person_id, secondary_person_id,
period_key, title, preview, content, chart_snapshot, prompt_version,
generated_at, access
```

其中 `content` 复用现有 `FollowupReport` 的 `opening/subtopics/summary/suggested_questions` 外壳；月运、年报、关系视角通过各自 payload 扩展，不新建五套渲染组件。

接口为：

```text
GET  /api/reports?person_id=&report_type=&status=
POST /api/reports
GET  /api/reports/{report_id}
GET  /api/reports/{report_id}/status
POST /api/reports/import-legacy
```

`POST /api/reports` 幂等：相同 `identity_key` 返回已有记录。首次创建返回 `pending/generating`，后台任务写入 `ready/failed`。进程内任务表沿用当前深读模式，但报告状态必须落库，服务重启后 `generating` 超时记录可被重试，不能永久卡住。

旧首次解读与深读消息通过 `legacy_report_adapter.py` 解析；报告库首次加载调用一次导入接口。映射记录保存 `source_message_id`，不复制生成、不改变旧消息。

现有 `deep_reading.py` 改为 entitlement 驱动：存量 `ContentUnlock` 继续有效，新用户由订阅权益决定全文访问；新生成的问答正文同步创建 `qa_reading` 报告。

### 命局人格、记忆与安全

新增：

- `backend/app/models/persona.py`
- `backend/app/models/persona_conversation.py`
- `backend/app/models/persona_message.py`
- `backend/app/models/persona_memory.py`
- `backend/app/models/safety_event.py`
- `backend/app/schemas/persona_schema.py`
- `backend/app/services/persona_profile_service.py`
- `backend/app/services/persona_prompt_service.py`
- `backend/app/services/persona_chat_service.py`
- `backend/app/services/persona_memory_service.py`
- `backend/app/services/safety_service.py`
- `backend/app/api/persona.py`

接口为：

```text
POST   /api/personas
GET    /api/personas
GET    /api/personas/{persona_id}
POST   /api/personas/{persona_id}/conversations
GET    /api/personas/{persona_id}/conversations
GET    /api/persona-conversations/{conversation_id}/messages
POST   /api/persona-conversations/{conversation_id}/messages
GET    /api/personas/{persona_id}/memory
PATCH  /api/personas/{persona_id}/memory-settings
DELETE /api/personas/{persona_id}/memory
```

创建人格时验证：档案归属当前用户、`is_self=true`、档案年龄不小于 18、未超过订阅档案限制。头像根据 `chart_snapshot.day_master` 映射到前端内置十天干头像 key。

人格消息采用 SSE，但使用独立数据表和独立 Prompt，绝不复用 `ChatSession/ChatMessage`。Prompt 输入固定为 `chart_snapshot + persona_profile + memory_summary + recent_messages`；输出为第一人称自然对话，不允许分节解盘、吉凶预测、冒充真人或心理诊断。

安全处理顺序固定为：

1. 输入前置规则检测。
2. 危机命中时退出角色，返回静态求助信息，不消耗额度，写入 `safety_events`。
3. 未成年人不允许创建或进入人格会话。
4. 会话开始两小时后前后端都显示休息提醒；服务端返回 `rest_reminder_required=true`，避免只靠浏览器计时。
5. 输出后置过滤；违规输出替换为安全回复并记录事件。
6. 每屏常驻“AI 生成·命局人格模拟”；未来他人档案启用时再增加“非本人”标识。

每 6 个用户回合或会话结束时更新一次结构化摘要。用户关闭记忆后不再把摘要注入 Prompt；清空执行物理删除并记录审计事件，不保留可恢复正文。

### 今日节律与前端信息架构

新增后端兼容接口 `GET /api/daily/rhythm`，返回：

```text
energy_state: smooth | steady | contracting
suitable: string[]
notice: string[]
action, basis, chart_ref, pressure_level, source
```

旧 `/api/daily/fortune` 暂时保留。新前端只消费 `rhythm`；界面不展示“吉/凶、宜/忌、开运、预测”。

前端新增：

- `src/pages/ReadingHome.tsx`
- `src/pages/ReadingChat.tsx`（从现有 `Chat.tsx` 迁移解盘 AI）
- `src/pages/ReportLibrary.tsx`
- `src/pages/ReportDetail.tsx`
- `src/pages/SubscriptionPage.tsx`
- `src/pages/PersonaHome.tsx`
- `src/pages/PersonaChat.tsx`
- `src/pages/PersonaMemoryPage.tsx`
- `src/api/entitlement.ts`
- `src/api/subscription.ts`
- `src/api/report.ts`
- `src/api/persona.ts`
- `src/api/rhythm.ts`
- `src/store/entitlementStore.ts`
- `src/store/reportStore.ts`
- `src/store/personaStore.ts`
- `src/components/ProfileSwitcher.tsx`
- `src/components/SubscriptionGate.tsx`
- `src/components/UsageSummary.tsx`
- `src/components/AIIdentityBanner.tsx`
- `src/components/ReportCard.tsx`
- `src/components/SafetyNotice.tsx`

修改：

- `src/App.tsx`：加入 `/reading`、`/reading/chat/:personId`、`/reports`、`/reports/:reportId`、`/persona`、`/persona/chat/:conversationId`、`/persona/memory/:personaId`、`/subscription`；旧 `/chat/:personId` 重定向到解读问答。
- `src/components/TabBar.tsx`：改为今日、解读、对话、我的四 Tab。
- `src/components/Layout.tsx`：解读问答和人格对话均使用独立全屏消息布局判断。
- `src/pages/Today.tsx`：改为今日节律、本月入口、解盘 AI 与命局人格双分流。
- `src/pages/ProfilePage.tsx`：显示订阅、用量、历史积分和记忆设置；移除充值入口。
- `src/pages/PersonsPage.tsx`、`AddPerson.tsx`、`api/person.ts`：支持本人/关系属性、授权确认和权益上限；建档不再直接扣首次报告积分。
- `src/pages/DeepReading.tsx`：改为订阅访问，不展示积分解锁。
- `src/pages/RechargePage.tsx`、`RechargeModal.tsx`：从用户路由和可见入口移除，代码保留一个兼容周期。

设计实现前先基于 `.trae/documents/ui-design/14-v2-product.html` 生成 V3 P0 评审稿，补齐四 Tab、解读首页、人格主页、人格创建、人格对话、订阅页和记忆页。实现后的视觉以该稿为准，沿用现有黛蓝紫品牌与克制东方视觉，不引入仙侠、灵纹或游戏化动效。

## 进度追踪

- [x] (2026-10-28 10:55:57+08:00) Phase 0：需求对齐与产品决策完成
- [x] (2026-10-28 11:20:00+08:00) Phase 1：仓库、产品文档、接口、模型、迁移与测试基线探索完成
- [x] (2026-10-28 11:35:00+08:00) Phase 2：ExecPlan 方案撰写完成
- [x] (2026-10-28 12:19:44+08:00) Phase 3：用户 Review 通过
- [x] (2026-10-28 12:20:39+08:00) Milestone 0：本地环境与质量基线修复
- [x] (2026-10-28 12:25:09+08:00) Milestone 1：V3 技术规格与 P0 UI 设计冻结
- [x] (2026-10-28 12:29:22+08:00) Milestone 2：标准化命盘、档案关系与数据库基础
- [x] (2026-10-28 12:37:22+08:00) Milestone 3：订阅权益、用量与积分停充闭环
- [x] (2026-10-28 12:48:00+08:00) Milestone 4：五类报告与解读 Tab
- [x] (2026-10-28 12:55:00+08:00) Milestone 5：命局人格、结构化记忆与安全门禁
- [x] (2026-10-28 13:00:00+08:00) Milestone 6：今日节律、四 Tab 与我的页整合
- [x] (2026-10-28 13:06:00+08:00) Milestone 7：历史兼容、端到端验收与灰度准备
- [x] (2026-10-28 13:44:00+08:00) Milestone 8：独立代码审计与文档更新
- [x] (2026-10-28 13:45:00+08:00) Phase 5：结果汇报材料完成
- [ ] Phase 7：代码提交（按用户约束，等待明确 commit 指令）

## 工作计划

### Milestone 0：本地环境与质量基线修复

**范围**：修复可重复安装、迁移和测试入口。保留已添加的 `aiosqlite`，补充 `greenlet`；新增 `requirements-dev.txt`，包含 `pytest`、`pytest-asyncio`。前端补 `test`、`typecheck` 和 `e2e` 脚本，添加 Playwright；增加 `.nvmrc` 与 `package.json.engines`，固定 Node 24.15+，避开当前 Node 25 与 jsdom 30 的不兼容警告。

**成果**：新机器按锁文件安装后可运行后端、Alembic、前端构建和测试。

**验收**：
- 后端根接口 HTTP 200。
- `alembic heads` 只有 `010_content_unlocks`。
- 前端现有 4 个测试文件全部 PASS，0 skipped。
- TypeScript 检查与生产构建零错误。

### Milestone 1：V3 技术规格与 P0 UI 设计冻结

**范围**：新增 `.trae/documents/趣算算-V3-MVP-技术规格.md`，固化本计划中的对象模型、枚举、API、权益矩阵、安全状态和错误码；新增 `.trae/documents/ui-design/15-v3-mvp.html`，从 V2 资产重构四 Tab 与 P0 页面。

**成果**：代码前拥有唯一、可测试的接口和视觉契约；后续实现不再从方向文档临时推断。

**验收**：
- 技术规格包含本文全部 API 和权益矩阵。
- 设计稿覆盖桌面 430px 容器和 390px 移动视口，无文本溢出或控件重叠。
- 设计稿不出现“分身、算命、吉凶、宜忌、积分购买”等废弃口径。

### Milestone 2：标准化命盘、档案关系与数据库基础

**范围**：完成迁移 011、`chart_snapshot` 服务、档案关系字段和本人唯一性校验；所有新增模型进入 Alembic metadata。补 SQLite 与 MySQL 方言兼容测试。

**成果**：任意现有档案可以无损生成英文 snake_case 命盘快照；每个用户有且仅有一个默认本人档案，用户可修正。

**验收**：
- 旧 SQLite 数据库从 010 升级到 011 后档案、消息、积分数量不变。
- 同一用户创建第二个本人档案返回 HTTP 409。
- 相同原始排盘生成相同 `source_hash`。
- 快照契约测试全部 PASS，0 skipped。

### Milestone 3：订阅权益、用量与积分停充闭环

**范围**：完成订阅、用量表，统一 entitlement 服务，接入档案上限、解盘问数和人格会话计数；完成模拟开通/到期。关闭用户充值入口和新订单 API，保留历史查询与管理端。

**成果**：免费、轻享、全享三种状态的每项能力均由服务端判定，前端仅展示服务端快照。

**验收**：
- 免费第 2 份档案、每日第 4 次解盘问题、当月第 4 次人格会话均返回结构化 403。
- 轻享允许 3 份档案和当月 30 次人格会话，第 4 份档案与第 31 次会话被拒绝。
- 全享不受上述数量限制。
- 模拟到期后立即降级但不删除档案、历史报告和消息。
- 用户充值 API 返回 HTTP 410；历史流水 API 仍返回 HTTP 200。

### Milestone 4：五类报告与解读 Tab

**范围**：完成迁移 012、统一报告模型、异步生成服务、旧报告适配器和报告 API；前端完成解读首页、报告库、报告详情、解盘问答迁移和订阅门禁。

**成果**：用户在解读 Tab 统一查看星盘、基础/月/年/关系/问答报告；按需生成可离页继续并在失败后重试。

**验收**：
- 五种 `report_type` 都通过 schema 契约测试。
- 相同报告请求并发两次只产生一条 `identity_key` 记录。
- 月运按 `YYYY-MM`、年报按 `YYYY`、关系报告按有序双档案 identity 缓存。
- 轻享访问年报返回 403，全享返回或生成报告。
- 旧大纲/深读消息惰性导入后内容哈希不变，且重复导入不新增记录。

### Milestone 5：命局人格、结构化记忆与安全门禁

**范围**：完成迁移 013、人格 profile、独立对话域、SSE、摘要记忆、内置头像映射、安全检测与用量扣减；前端完成人格主页、创建、全屏聊天、记忆页和常驻 AI 标识。

**成果**：成年用户可为本人档案创建并使用一个命局人格；人格与解盘 AI 的消息、Prompt 和历史完全隔离。

**验收**：
- 他人档案、未满 18 岁档案创建人格均返回结构化 403。
- 同一档案重复创建返回同一人格，不产生重复行。
- 危机输入返回静态安全回复、不调用 LLM、不消耗会话额度，并写入一条安全事件。
- 会话第 20 个用户回合后不可继续发送；新会话按订阅规则扣 1 次额度。
- 关闭记忆后 Prompt 不包含 `memory_summary`；清空后数据库不存在该人格记忆正文。
- 连续两小时会话响应包含休息提醒，前端展示不可忽略的提示条。

### Milestone 6：今日节律、四 Tab 与我的页整合

**范围**：新增 rhythm API；重构 Today、TabBar、Layout、App 路由和 Profile；统一档案切换器、订阅门禁、用量展示和历史积分口径。

**成果**：四 Tab 主链路完整，今日负责日更与分流，解读负责“看”，对话只负责人格“聊”，我的负责资产和设置。

**验收**：
- App 底栏严格显示今日、解读、对话、我的四项。
- 今日页面和 API 不出现禁用词“吉/凶、宜/忌、算命、改运、化解”。
- 无人格时进入对话 Tab 显示创建引导；已有人格时进入最近会话。
- 旧 `/chat/:personId` 自动重定向到 `/reading/chat/:personId`，历史问答仍可见。

### Milestone 7：历史兼容、端到端验收与灰度准备

**范围**：执行旧数据迁移演练、功能开关、失败恢复和端到端关键链路；检查账号注销同步删除新增隐私数据。生产上线前默认只开放内部测试账号。

**成果**：V3 可在不丢旧数据的前提下灰度启用，也可通过关闭开关回退到旧入口。

**验收**：
- 账号注销删除 persona、memory、conversation、report 和 safety 主体关联，并保留依法需保留的匿名财务记录。
- 010 → 013 → downgrade 010 → upgrade 013 的测试数据库流程成功，关键表计数符合预期。
- Playwright 覆盖新用户闭环、免费额度耗尽、轻享开通、全享年报、人格危机退出和历史报告导入。
- 390×844、430×932、1440×900 三个视口截图无空白页面、文字溢出和控件重叠。

### Milestone 8：独立代码审计与文档更新

**范围**：使用独立审查者审计权限绕过、并发额度、隐私删除、Prompt 串味、迁移可逆性和前端路由回归；修复验证属实的问题。更新 V3 产品文档、技术架构文档、部署说明和 API 说明。

**成果**：代码、测试、运行文档和产品口径一致，ExecPlan 填写完成汇报和遗留项。

**验收**：
- 审计中的 P0/P1 真实问题全部修复并有回归测试。
- 文档不存在积分解锁作为 V3 主路径、三 Tab 或他人人格首发等过时描述。
- Git 工作区仅包含计划内文件。

## 具体步骤

所有命令从 `/Users/bytedance/Desktop/mingli-agent` 执行；子目录通过命令参数指定，不使用隐式全局环境。

```bash
# 1. 环境基线
./mingli-agent/backend/.venv/bin/python -m pip install -r mingli-agent/backend/requirements.txt -r mingli-agent/backend/requirements-dev.txt
npm ci --prefix mingli-agent/frontend

# 2. 数据库迁移静态与本地验证
cd mingli-agent/backend
./.venv/bin/python -m alembic heads
DATABASE_URL=sqlite+aiosqlite:///./v3_migration_test.db ./.venv/bin/python -m alembic upgrade head

# 3. 后端测试
./.venv/bin/python -m pytest tests/v3 -q
./.venv/bin/python -m pytest -m "not live_ai" -q

# 4. 前端检查
cd ../frontend
npm run typecheck
npm test
npm run build
npm run e2e
```

预期输出：

- Alembic 仅一个 head，最终为 `013_v3_persona`。
- `tests/v3` 和非 live AI 测试全部 PASS，0 skipped。
- Vitest 全部 PASS，0 skipped。
- TypeScript 与 Vite build 零错误。
- Playwright 全部 PASS，0 skipped，并生成三组视口截图。

## 验证与验收

最终验收按以下顺序执行，任一步失败都不能标记计划完成：

1. 依赖：全新 Python venv 与全新 `node_modules` 安装成功，无缺失运行时依赖。
2. 迁移：SQLite 旧数据副本完成 010→013；生产发布前在 MySQL 8 临时实例执行同一迁移。当前机器没有 Docker，MySQL 验证必须在 CI 或可用测试环境完成。
3. 后端：`tests/v3` 全部 PASS、0 skipped；非 live AI 全量测试全部 PASS、0 skipped。
4. 前端：Vitest、typecheck、build 全部通过。
5. E2E：六条关键业务链路全部通过，0 skipped。
6. 安全：权限越权、额度并发、未成年人、危机退出、记忆清除和账号注销测试全部通过。
7. 视觉：三个视口截图经像素与布局检查，无空白、溢出、遮挡或错误资源。
8. 兼容：旧档案、旧聊天、旧深读、历史积分流水均可查看；充值不可新建。
9. 灰度：关闭 `V3_ENABLED` 时旧入口仍可访问；开启后四 Tab 与新 API 生效。

## 文档更新

执行阶段最后更新：

- `.trae/documents/趣算算-产品方向与功能框架-V3-融合版.md`：回填最终权益矩阵、轻享 30 次人格会话、首发仅本人和已实现状态。
- `.trae/documents/命理Agent技术架构文档.md`：新增 chart snapshot、report、entitlement、persona、memory 与 safety 架构。
- `.trae/documents/趣算算-V3-MVP-技术规格.md`：作为 API、schema、错误码和枚举事实源。
- `.trae/documents/ui-design/15-v3-mvp.html`：保存最终 P0 视觉稿。
- `README.md` 与 `mingli-agent/README.md`（若后者不存在则创建）：补本地启动、Node/Python 版本、迁移、测试与功能开关说明。

## 幂等性与恢复

- 数据迁移只新增列/表并做确定性回填；上线前必须先备份数据库。
- `chart_snapshot`、报告创建、旧报告导入、人格创建和用量周期创建均使用唯一键和幂等返回。
- 报告与人格异步任务状态落库。进程重启后，超过超时阈值的 `generating` 记录转为 `failed`，用户可重试。
- 功能通过 `V3_ENABLED`、`PERSONA_ENABLED`、`OTHER_PERSONA_ENABLED`、`POINTS_RECHARGE_ENABLED` 控制；回退优先关闭开关，不删除新表。
- 旧 API 和旧路由保留一个版本，不在本计划中物理删除。
- 降级迁移只允许在测试环境演练；生产回退使用应用开关和数据库备份，不自动 downgrade 含用户新数据的表。
- 当前未提交的 `aiosqlite` 修改属于计划内环境修复，不得在执行中还原。

## 意外发现

- 观察：当前后端本地 SQLite 启动依赖 `aiosqlite`，但原 requirements 未声明；已经产生一处未提交修复。
  证据：`app/db/session.py` 使用异步数据库 URL，本机启动曾报 `ModuleNotFoundError: aiosqlite`。
- 观察：Alembic 唯一 head 是 `010_content_unlocks`，但在线 history 因缺 `greenlet` 失败。
  证据：`alembic heads` 输出 `010_content_unlocks (head)`；连接阶段报 `No module named 'greenlet'`。
- 观察：仓库已有一个历史 autogenerated migration `508b12ccf9f5`，其中包含大量删表语句；新迁移不能仿照该文件生成。
  证据：该迁移 `upgrade()` 含 `drop_table('eval_results')`、`drop_table('prompt_versions')` 等操作。
- 观察：产品文档原权益表将轻享和全享都写成人格无限，与“轻享=解读向、全享=解读+人格”冲突。
  证据：用户已拍板轻享每月 30 次人格会话，全享无限。
- 观察：当前 Node 25.8.0 不满足 jsdom 30 声明的引擎范围。
  证据：`npm ci` 输出 `EBADENGINE`，`jsdom@30.0.1` 要求 `^22.22.2 || ^24.15.0 || >=26.0.0`；计划固定 Node 24.15。
- 观察：从 revision 001 离线编译完整 SQLite 迁移链会在历史 `508b12ccf9f5` 的 column comment DDL 处失败；011 本身不受影响。
  证据：SQLite DDL compiler 无法渲染该历史迁移的 `ColumnComment`；改用已存在的 010 数据库副本和 `010:011 --sql` 范围后，实际升级、降级、SQLite SQL 与 MySQL SQL 均通过。
- 观察：本机已安装 Playwright npm 包但未安装 Chromium browser binary，无法用 CLI 生成真实应用截图。
  证据：`browserType.launch` 报 `Executable doesn't exist ... chromium_headless_shell-1248`；本里程碑改用已连接浏览器完成 DOM、交互和溢出验收，截图资产留到 Milestone 7 安装浏览器后统一补齐。
- 观察：`tests/v3` 扩展到 36 条后，Playwright `*.spec.ts` 会被 Vitest 默认规则误收集。
  证据：合并质量命令中 Vitest 报 `Playwright Test did not expect test.beforeEach()`；新增独立 `vitest.config.ts`，将单测范围固定为 `src/**/*.{test,spec}.{ts,tsx}`。
- 观察：独立审计发现人格第 20 回合、报告失败重试和首次记忆创建存在并发抢占窗口。
  证据：原实现先读后写；现已改为数据库条件更新或唯一键 savepoint，并新增文件型 SQLite 并发测试。

## 决策日志

- 决策：完整 V3 MVP，而非只做原型或单一闭环。
  理由：用户明确选择完整 V3 MVP。
  日期/作者：2026-10-28，用户。
- 决策：沿用 React/Vite App 壳，首发简中国内版。
  理由：最大化复用当前页面和 API，避免并行维护 RN 与 Web。
  日期/作者：2026-10-28，用户。
- 决策：权益闭环和模拟开通先行，真实支付后置。
  理由：先验证产品与权限模型，避免被商店资质和支付外部依赖阻塞。
  日期/作者：2026-10-28，用户。
- 决策：本人档案人格首发，他人人格不开放。
  理由：降低冒充、隐私和拟人化互动合规风险。
  日期/作者：2026-10-28，用户。
- 决策：人格记忆采用结构化摘要，支持查看、关闭和清空。
  理由：满足连续陪伴，同时控制隐私和实现复杂度。
  日期/作者：2026-10-28，用户。
- 决策：积分存量兼容并停充，MVP 不做订阅抵扣。
  理由：避免在真实支付缺席时提前固化兑换和退款规则。
  日期/作者：2026-10-28，用户。
- 决策：轻享每月 30 次人格会话，全享无限。
  理由：修复产品文档档位定位与权益表冲突，保留升级动机。
  日期/作者：2026-10-28，用户。
- 决策：模拟订阅接口增加独立 `SUBSCRIPTION_MOCK_ENABLED` 开关，默认关闭。
  理由：模拟开通只用于本地和内部测试，不能因 V3 主开关开启而暴露到生产用户。
  日期/作者：2026-10-28，Agent。

## 接口与依赖

新增或固定的主要依赖：

- Python 3.9 现状兼容；后续单独评估升级，不在本计划内。
- `aiosqlite==0.20.0`：本地异步 SQLite。
- `greenlet`：SQLAlchemy async/Alembic 在线迁移。
- `pytest`、`pytest-asyncio`：后端确定性测试。
- Node 24.15+：前端开发和 CI 运行时。
- `vitest`：前端单元与契约测试。
- `@playwright/test`：关键链路与多视口截图。

核心枚举：

```text
plan_code       = free | light | full
report_type     = base_report | monthly_brief | annual_brief | relation_report | qa_reading
report_status   = pending | generating | ready | failed
relationship    = self | partner | spouse | child | parent | friend | colleague | other
energy_state    = smooth | steady | contracting
usage_metric    = profile_count | qa_daily | persona_session_monthly
safety_category = crisis | minor | dependency | output_violation
```

统一错误体：

```json
{
  "code": "entitlement_required",
  "message": "当前权益不足",
  "required_plan": "full",
  "metric": "annual_brief",
  "remaining": 0
}
```

## 产物与备注

前端执行必须保存以下实操截图到 `.trae/documents/artifacts/v3-mvp/`：

1. 新用户建档与基础解读。
2. 四 Tab 首页。
3. 月运生成中与完成态。
4. 报告库及历史报告导入。
5. 命局人格创建与主页。
6. 人格对话、AI 标识和休息提醒。
7. 危机语句退出角色。
8. 免费额度耗尽后的订阅墙。
9. 轻享和全享权益页。
10. 记忆查看、关闭与清空。

每张截图同时记录 URL、视口和对应测试用例。不得用仅静态 HTML 的截图替代真实运行应用截图。

## 成果与复盘

**Milestone 0（2026-10-28）**：

- 新增 `requirements-dev.txt`，固定 `pytest==8.3.5`、`pytest-asyncio==0.24.0`；运行依赖补齐 `greenlet==3.0.3`，并保留 `aiosqlite==0.20.0`。
- 前端新增 `test`、`typecheck`、`e2e` 脚本、Playwright 依赖、`.nvmrc` 和 Node engines 约束。
- 验收结果：后端根接口 HTTP 200；Alembic 唯一 head 为 `010_content_unlocks`，在线连接成功；`pip check` 无缺失依赖；前端 4 个测试文件、34 条测试全部 PASS，0 skipped；TypeScript 与生产构建零错误；`npm ci` 冷安装成功且 0 vulnerabilities。
- 已知提示：当前终端仍运行 Node 25.8.0，因此 npm 按预期提示 `EBADENGINE`；切换到仓库声明的 Node 24.15.0 后该提示消失。Vite 仍提示主 bundle 超过 500 kB，后续页面拆分阶段处理。

**Milestone 1（2026-10-28）**：

- 新增 `.trae/documents/趣算算-V3-MVP-技术规格.md`，冻结对象模型、命盘快照、权益矩阵、全部 V3 API、SSE、安全状态机、错误码、迁移、隐私删除和客户端路由。
- 新增 `.trae/documents/ui-design/15-v3-mvp.html`，覆盖今日、解读、报告库、人格创建、人格主页、人格对话、订阅、记忆和我的 9 屏。
- 验收结果：设计稿为无外部依赖的单文件；禁用口径扫描无命中；Playwright 在 390×844、430×932、1440×900 三个视口检查到 0 个横向溢出元素，截图视觉检查无文本遮挡或控件重叠。

**Milestone 2（2026-10-28）**：

- 完成 `011_v3_profile_subscription`，为档案增加本人/关系、授权和标准化快照字段，并创建订阅、用量基础表；所有模型已进入 Alembic metadata。
- 新增 `chart_snapshot_service`，以 `source_hash` 驱动惰性生成与失效，统一输出英文 snake_case 顶层契约；新增本人唯一性和他人授权校验。
- 验收结果：V3 单测 8 条和既有排盘回归 8 条共 16 条全部 PASS，0 skipped；旧 SQLite 副本从 010 升至 011 后档案 2、消息 21、流水 16、解锁 6 均不变，每个用户恰好回填 1 个本人档案；011 完成 downgrade/upgrade 往返；SQLite 与 MySQL 8 SQL 编译通过；后端应用导入成功。

**Milestone 3（2026-10-28）**：

- 新增免费/轻享/全享计划常量、统一 entitlement 快照、原子用量消费、档案槽位锁和报告访问控制；新增订阅计划、当前权益、模拟开通与模拟到期 API。
- 档案创建、主问答、旧版流式问答和深度解读均改为服务端权益判定；用户充值订单返回 HTTP 410，管理端充值、回调、历史订单和积分流水保留。
- 前端移除用户充值路由、建档积分门槛、聊天充值门槛和深读充值弹窗；新增 entitlement/subscription API 与 Zustand store。
- 验收结果：V3 服务与 ASGI API 测试 13 条全部 PASS，0 skipped；覆盖免费第 4 问、轻享第 31 次人格会话、全享无限、年报门禁、到期降级、充值 410 和历史流水 200；前端 34 条测试、typecheck、build 全通过；运行中的订阅计划 API 与前端首页均返回 HTTP 200。本地数据库已备份至 `/tmp/mingli_dev_before_v3_20261028.db` 并升级到 011。

**Milestone 4（2026-10-28）**：

- 完成 `012_v3_reports`、统一 `Report` 模型、五类内容 envelope、确定性 `identity_key`、异步生成状态机、失败/超时重试、报告 API 和旧消息惰性适配器；深度解读完成后同步建立 `qa_reading` 映射。
- 前端新增解读首页、解盘 AI 新路由、报告库、统一报告详情、订阅页、report API/store，并在底栏加入解读入口；旧 `/chat/:personId` 和深读入口继续兼容。
- 验收结果：V3 单测 19 条、排盘回归 45 条、前端单测 34 条全部 PASS；typecheck 与 build 通过。012 在旧库副本完成 `011→012→011→012` 往返，档案/消息/流水计数保持 `2/21/16`，SQLite 与 MySQL DDL 编译通过。
- 真实旧库首次导入扫描 10 条 assistant 消息，映射 1 份基础解读和 6 份问答解读；第二次导入 `imported=0, existing=7`。浏览器验证解读首页、免费订阅墙、报告库和 390px 报告详情无横向溢出。本地库备份至 `/tmp/mingli_dev_before_m4_20261028.db` 并升级到 012。

**Milestone 5（2026-10-28）**：

- 完成 `013_v3_persona`，新增人格、独立会话、独立消息、结构化记忆和安全事件五张表；人格只允许成年本人档案且按日主稳定映射头像。
- 新增独立 Persona Prompt、SSE 对话、每会话 20 用户回合、每 6 回合摘要、记忆查看/关闭/物理清空、两小时休息提醒、输入危机退出角色和输出违规替换；人格消息不写入旧 `ChatMessage`。
- 前端新增对话 Tab 人格主页、创建引导、最近会话、全屏聊天、常驻“AI 生成·命局人格模拟”、记忆设置和清空界面；会话额度完全由 entitlement 快照展示。
- 验收结果：V3 测试 25 条、排盘回归 45 条、前端单测 34 条全部 PASS；typecheck 与 build 通过。013 完成 `012→013→012→013` 往返，SQLite/MySQL DDL 编译通过；真实浏览器完成本人创建、新会话、危机静态回复、0/20 回合不递增、记忆页和无横向溢出验收。危机事件落库 `llm_called=false`，当月会话计数保持 1。
- 本地数据库已备份至 `/tmp/mingli_dev_before_m5_20261028.db` 并升级到 013；开发后端当前以 `PERSONA_ENABLED=true` 运行用于后续联调。

**Milestone 6（2026-10-28）**：

- 新增 `/api/daily/rhythm`，将旧内部等级映射为 `smooth/steady/contracting`，输出 `suitable/notice` 与行动建议；接口边界统一净化旧口径，避免旧生成链路的术语泄漏。
- 今日页改为“顺畅/平稳/收束”节律、压力、今日安排、留意事项和解读/人格双分流；底栏稳定为今日、解读、对话、我的四项。
- 我的页新增当前计划、档案余量、今日问答和本月人格会话用量；旧 `/chat/:personId` 兼容重定向到 `/reading/chat/:personId`，历史消息继续由原 Chat 数据域展示。
- 验收结果：V3 测试 26 条、前端单测 34 条、typecheck 和 build 全通过；今日页源代码禁用词扫描 0 命中。真实 `/daily/rhythm` 响应与页面均不含废弃口径，四 Tab、我的页用量和旧聊天重定向浏览器验收通过，页面无横向溢出。

**Milestone 7（2026-10-28）**：

- 新增服务端 `/api/features` 与 V3 主开关门禁，客户端在开关关闭或旧后端缺少接口时降级为三 Tab 和旧问答入口；模拟订阅继续由独立开关控制。
- 账号注销扩展到报告、人格、人格消息、记忆、安全事件、订阅、用量和旧解锁记录；财务流水与匿名账号墓碑保留。
- 完成 `010→013→010→013` 旧库往返，旧档案/消息/流水始终保持 `2/21/16`，降级到 010 后全部 V3 表移除。
- 安装 Playwright Chromium，新增三视口 E2E；390×844、430×932、1440×900 共生成 24 张真实运行截图，覆盖今日、解读、报告库、免费墙、全享、人设主页、危机退出和记忆页，全部无横向溢出。

**Milestone 8（2026-10-28）**：

- 使用 `bits-code-guard` 按 6 组审计 88 个文件、约 7277 行变更/新增代码，覆盖权限、并发、隐私、Prompt 隔离、迁移和路由。
- 已修复：人格第 20 回合并发越界、记忆唯一键竞态、报告重试重复抢占、关系报告缺第二命盘、报告周期非法值、失败异常外泄、旧聊天重复请求用量回滚、两小时提醒需再次发言、V3 关闭仍展示新入口。
- 复审未发现剩余 P0-P2 缺陷；审计报告输出至 `.trae/documents/artifacts/v3-mvp-review/`。
- 更新 V3 产品落地状态、技术架构、部署说明和 API 说明。
- 最终验收：后端 V3 36 条、排盘回归 45 条、前端单测 34 条、Playwright 3 条全部 PASS；TypeScript、生产构建、SQLite/MySQL DDL 和 Alembic 单 head 验证通过。

在每个里程碑完成时追加结果。最终 Phase 5 必须填写：

**目标达成**：完整 V3 MVP 已按 M0–M8 落地并通过验收。

**变更概览**：四 Tab、标准化命盘、统一报告、订阅权益、命局人格、结构化记忆、安全门禁、今日节律、历史兼容和灰度开关均已实现。

**验收结果**：后端 V3 36 条、排盘回归 45 条、前端单测 34 条、E2E 3 条全部通过；010↔013 可逆，三视口截图无溢出。

**已知风险/遗留**：

- 真实 IAP/代扣、他人人格、海外版和逐条编辑记忆明确后置。
- 本机无 Docker，MySQL 8 迁移验证需要 CI 或独立测试环境。
- Vite 主 bundle 约 1.09 MB，仍有 chunk size 警告；不阻断 MVP，后续按页面动态加载拆包。

**建议后续**：待执行。

## 后续修复记录

如出现 Review、CI 或回归问题，按 Fix 编号追加触发原因、修复内容和验证结果，不覆盖原决策。

---

[2026-10-28 11:35:00+08:00] 修改说明：创建完整 V3 MVP ExecPlan，纳入用户确认的范围、权益、人格、记忆、积分、历史迁移和客户端决策。
[2026-10-28 12:19:44+08:00] 修改说明：用户批准 ExecPlan，进入 Phase 4，并开始 Milestone 0 环境与质量基线修复。
[2026-10-28 12:20:39+08:00] 修改说明：完成 Milestone 0，依赖安装、Alembic、后端根接口、Vitest、TypeScript 与生产构建验收通过。
[2026-10-28 12:25:09+08:00] 修改说明：完成 Milestone 1，冻结 V3 技术规格与 9 屏 P0 视觉稿，并通过多视口溢出检查。
[2026-10-28 12:29:22+08:00] 修改说明：完成 Milestone 2，落地 011、命盘快照与档案关系约束，并通过旧库迁移和双方言验证。
[2026-10-28 12:37:22+08:00] 修改说明：完成 Milestone 3，统一订阅权益与用量、停止用户积分充值，并通过 API 和前端回归验收。
