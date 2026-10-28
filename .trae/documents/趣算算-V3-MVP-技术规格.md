# 趣算算 V3 MVP 技术规格

> 状态：Frozen for implementation  
> 版本：1.0  
> 日期：2026-10-28  
> 事实源优先级：本规格 > V3 ExecPlan > V3 产品方向文档 > V2/V1 文档

## 1. 目标与边界

本规格定义趣算算 V3 MVP 的对象模型、枚举、API、权益、安全状态、错误码和客户端路由。实现必须将“解盘 AI”和“命局人格 AI”隔离为两套数据域与 Prompt，只共享同一份标准化命盘快照。

首发范围：

- 简体中文国内版，沿用 React/Vite 客户端和 FastAPI 服务端。
- 四 Tab：今日、解读、对话、我的。
- 免费、轻享、全享三种权益状态；仅模拟开通，不接真实支付。
- 仅本人档案可创建命局人格；他人档案仅用于关系视角。
- 积分余额、流水和已解锁内容继续可查；停止用户充值，不抵扣订阅。
- 月运、年报、关系报告按需异步生成；旧报告惰性导入。

明确不做：

- React Native、新原生客户端、海外版和真实 IAP。
- 他人人格、十神分灵、主动私聊、每日唤醒、抽灵纹。
- 真人咨询、社区、PDF 导出、优惠券、邀请裂变。
- 人格语音和逐条编辑记忆。

## 2. 全局约定

### 2.1 传输与命名

- API 前缀：`/api`
- JSON 字段：英文 `snake_case`
- 时间：ISO 8601，服务端保存 UTC，客户端展示 Asia/Shanghai
- ID：数据库自增整数；客户端不得推断连续性
- 金额：人民币分；MVP 价格展示由计划常量提供，不创建支付订单
- 分页：`page >= 1`、`page_size <= 100`
- 空值：无值使用 `null`，不使用空字符串代替

统一成功体不额外包裹 `data`。列表接口返回：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
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

### 2.2 功能开关

| Key | 默认值 | 作用 |
|---|---:|---|
| `V3_ENABLED` | `false` | 开启四 Tab 和 V3 API 入口 |
| `PERSONA_ENABLED` | `false` | 开启命局人格创建与会话 |
| `OTHER_PERSONA_ENABLED` | `false` | 预留，MVP 禁止开启 |
| `POINTS_RECHARGE_ENABLED` | `false` | 用户积分充值；MVP 必须关闭 |

关闭 V3 时保留旧入口与旧 API；关闭 Persona 时返回 `feature_disabled`，不删除数据。

## 3. 核心枚举

```text
plan_code          = free | light | full
subscription_status = active | expired | canceled
relationship_type  = self | partner | spouse | child | parent | friend | colleague | other
report_type         = base_report | monthly_brief | annual_brief | relation_report | qa_reading
report_status       = pending | generating | ready | failed
energy_state        = smooth | steady | contracting
usage_metric        = profile_count | qa_daily | persona_session_monthly
persona_message_role = user | assistant | system
safety_category     = crisis | minor | dependency | output_violation
safety_action       = blocked | role_exited | filtered | reminded | memory_cleared
```

枚举值入库后不可重命名。展示文案由客户端映射。

## 4. 对象模型

```text
User
 ├─ Person 1..n
 │   ├─ chart_snapshot 1..1
 │   ├─ Report 1..n
 │   └─ Persona 0..1
 │       ├─ PersonaConversation 1..n
 │       │   └─ PersonaMessage 1..n
 │       └─ PersonaMemory 0..1
 ├─ Subscription 0..n
 ├─ UsageCounter 0..n
 └─ SafetyEvent 0..n
```

既有 `ChatSession` / `ChatMessage` 只属于解盘 AI。人格消息不得写入这两张表。

### 4.1 Person 扩展

| 字段 | 类型 | 约束 |
|---|---|---|
| `is_self` | bool | 非空，默认 `false` |
| `relationship_type` | enum string | 非空 |
| `relationship_note` | string(200) | 可空 |
| `consent_confirmed_at` | datetime | 他人档案要求非空 |
| `chart_snapshot_json` | JSON/Text | 可空，惰性生成 |
| `chart_snapshot_version` | string(32) | 可空 |
| `chart_snapshot_updated_at` | datetime | 可空 |

每个用户最多一个 `is_self=true` 档案。旧数据按用户最小 `person.id` 回填为本人，其余回填 `other`。

### 4.2 标准化命盘快照

```json
{
  "version": "1.0",
  "generated_at": "2026-10-28T04:00:00Z",
  "birth_profile": {
    "birth_date": "1992-08-08",
    "birth_time": "10:30",
    "timezone": "Asia/Shanghai",
    "gender": "female",
    "location": "辽宁省大连市"
  },
  "pillars": {
    "year": {"stem": "壬", "branch": "申"},
    "month": {"stem": "戊", "branch": "申"},
    "day": {"stem": "庚", "branch": "申"},
    "hour": {"stem": "辛", "branch": "巳"}
  },
  "day_master": {"stem": "庚", "element": "metal", "yin_yang": "yang"},
  "ten_gods": {},
  "strength": {"level": "strong", "score": 72},
  "useful_elements": ["fire", "wood"],
  "unfavorable_elements": ["metal", "earth"],
  "pattern": {},
  "luck_cycles": [],
  "annual_cycles": [],
  "monthly_cycles": [],
  "source_hash": "sha256:..."
}
```

必填顶层字段：

```text
version, generated_at, birth_profile, pillars, day_master, ten_gods,
strength, useful_elements, unfavorable_elements, pattern, luck_cycles,
annual_cycles, monthly_cycles, source_hash
```

生成顺序：

1. `source_hash` 未变化且已有快照：直接返回。
2. 从冻结的 `bazi_data_json` 转换。
3. 原数据缺失时调用既有排盘服务后转换。

报告和人格只能通过 `chart_snapshot_service` 获取快照。

## 5. 订阅与权益

### 5.1 权益矩阵

| 能力 | 免费 `free` | 轻享 `light` | 全享 `full` |
|---|---:|---:|---:|
| 月价展示 | ¥0 | ¥28 | ¥58 |
| 年价参考 | ¥0 | ¥198 | ¥398 |
| 档案上限 | 1 | 3 | 不限 |
| 基础解读 | 完整 | 完整 | 完整 |
| 完整深度解读 | 试看 1 篇 | 不限 | 不限 |
| 月运简报 | 1 期试看 | 每月 | 每月 |
| 年报 | 无 | 无 | 每年 |
| 关系视角 | 无 | 有 | 有 |
| 解盘 AI | 每日 3 问 | 不限 | 不限 |
| 人格新会话 | 每月 3 次 | 每月 30 次 | 不限 |
| 单人格会话用户回合 | 20 | 20 | 20 |

“人格会话次数”在创建新会话成功时消耗一次。危机输入、被安全规则前置拦截的输入不消耗额度。

### 5.2 Subscription

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int | 主键 |
| `user_id` | int | 索引 |
| `plan_code` | enum | `light` / `full` |
| `status` | enum | 状态 |
| `source` | string | MVP 固定 `mock` |
| `starts_at` | datetime | 生效时间 |
| `expires_at` | datetime | 到期时间 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

同一时刻只认一条有效订阅；多个有效记录取权益更高且 `expires_at` 更晚者。

### 5.3 UsageCounter

唯一键：

```text
(user_id, metric, period_key, scope_id)
```

周期：

- `qa_daily`：`YYYY-MM-DD`，Asia/Shanghai 自然日
- `persona_session_monthly`：`YYYY-MM`，Asia/Shanghai 自然月
- `profile_count`：实时查询 Person，不累计计数

并发消费必须在事务内执行“读取并锁定/唯一键创建重试/递增/校验”。超额时不写入。

### 5.4 EntitlementSnapshot

```json
{
  "plan_code": "light",
  "status": "active",
  "expires_at": "2026-11-28T04:00:00Z",
  "profile": {"limit": 3, "used": 2, "remaining": 1},
  "qa_daily": {"limit": null, "used": 8, "remaining": null},
  "persona_session_monthly": {"limit": 30, "used": 4, "remaining": 26},
  "report_access": {
    "base_report": true,
    "monthly_brief": true,
    "annual_brief": false,
    "relation_report": true,
    "qa_reading": true
  }
}
```

`limit=null` 表示无限。

## 6. 订阅 API

### `GET /api/subscriptions/plans`

返回三档计划、展示价格和权益矩阵。无需登录。

### `GET /api/subscriptions/current`

返回当前有效订阅；无订阅时返回免费状态。

### `POST /api/subscriptions/mock-activate`

请求：

```json
{"plan_code": "light", "billing_cycle": "monthly"}
```

仅开发/内部测试环境可用。返回激活后的订阅和权益快照。

### `POST /api/subscriptions/mock-expire`

使当前模拟订阅立即到期。历史档案、报告和消息不删除。

### `GET /api/entitlements/me`

返回 `EntitlementSnapshot`。客户端所有权益展示以此为准。

## 7. 统一报告

### 7.1 Report

| 字段 | 说明 |
|---|---|
| `identity_key` | 确定性唯一键 |
| `user_id` | 所有者 |
| `primary_person_id` | 主档案 |
| `secondary_person_id` | 关系档案，可空 |
| `report_type` | 五类枚举 |
| `period_key` | 月 `YYYY-MM`、年 `YYYY`，其余可空 |
| `status` | 生成状态 |
| `title` / `preview_json` | 列表展示 |
| `content_json` | 统一正文 |
| `chart_snapshot_json` | 生成时快照 |
| `prompt_version` | 可追溯版本 |
| `source_message_id` | 旧消息映射，可空 |
| `failure_code` / `failure_message` | 失败信息 |
| `generated_at` | 完成时间 |

identity 规则：

```text
base_report:      base:{user_id}:{primary_person_id}
monthly_brief:    month:{user_id}:{primary_person_id}:{YYYY-MM}
annual_brief:     year:{user_id}:{primary_person_id}:{YYYY}
relation_report:  relation:{user_id}:{min(person_a,person_b)}:{max(person_a,person_b)}
qa_reading:       qa:{user_id}:{source_message_id}
```

### 7.2 统一内容

```json
{
  "opening": {"lead": "string", "verdict": "string"},
  "subtopics": [
    {
      "title": "string",
      "blocks": [
        {"type": "keyword", "keyword": "string", "narrative": "string"}
      ]
    }
  ],
  "summary": {
    "title": "string",
    "items": [{"keyword": "string", "text": "string"}]
  },
  "suggested_questions": ["string"],
  "payload": {}
}
```

类型差异只进入 `payload`，不创建五套渲染组件。

### 7.3 报告 API

```text
GET  /api/reports?person_id=&report_type=&status=&page=&page_size=
POST /api/reports
GET  /api/reports/{report_id}
GET  /api/reports/{report_id}/status
POST /api/reports/import-legacy
```

创建请求：

```json
{
  "report_type": "monthly_brief",
  "primary_person_id": 12,
  "secondary_person_id": null,
  "period_key": "2026-11"
}
```

首次创建返回 HTTP 202；相同 `identity_key` 已存在时返回 HTTP 200 和原记录。生成状态必须落库。超过超时阈值的 `generating` 记录可重置为 `failed` 后重试。

旧报告导入：

- 只扫描当前用户拥有的旧消息。
- 保存 `source_message_id`，不重跑 AI、不修改旧消息。
- 重复调用幂等。
- 解析前后正文内容哈希必须一致。

## 8. 命局人格

### 8.1 Persona

| 字段 | 说明 |
|---|---|
| `person_id` | 唯一；只允许本人档案 |
| `name` | 默认“{昵称}的命局人格” |
| `avatar_key` | 十天干稳定映射 |
| `profile_json` | 语气、偏好、关键词 |
| `prompt_version` | Prompt 版本 |
| `created_at` / `updated_at` | 时间 |

创建前置条件：

1. `PERSONA_ENABLED=true`
2. 档案属于当前用户
3. `is_self=true`
4. 创建时年龄不小于 18 岁
5. 未触发档案权益限制

相同 `person_id` 重复创建返回原人格。

### 8.2 PersonaConversation

| 字段 | 说明 |
|---|---|
| `persona_id` | 所属人格 |
| `title` | 会话标题 |
| `user_turn_count` | 0..20 |
| `started_at` | 会话开始 |
| `last_message_at` | 最近消息 |
| `closed_at` | 可空 |

创建会话时消耗 `persona_session_monthly` 一次；达到 20 个用户回合后拒绝继续发送。

### 8.3 PersonaMessage

保存 `role`、`content`、`safety_category`、`prompt_version` 和时间。人格消息与解盘消息禁止跨表复制。

### 8.4 PersonaMemory

```json
{
  "enabled": true,
  "preferred_name": "小玲",
  "current_context": ["正在准备转岗"],
  "preferences": ["偏好直接表达"],
  "important_relationships": [
    {"label": "伴侣", "summary": "近期沟通减少"}
  ],
  "stage_summary": "最近在处理职业选择与关系边界。",
  "updated_at": "2026-10-28T04:00:00Z"
}
```

每 6 个用户回合或会话结束更新一次。关闭记忆后不更新、不注入 Prompt。清空记忆执行物理删除，并写一条不含正文的 `safety_event` 审计记录。

### 8.5 人格 API

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

发送消息使用 SSE：

```text
event: meta
data: {"message_id": 91, "rest_reminder_required": false}

event: delta
data: {"text": "我会先把这件事拆开看。"}

event: done
data: {"user_turn_count": 4, "remaining_turns": 16}
```

危机命中时返回静态 `done` 事件，不产生 `delta`，不调用 LLM。

## 9. 人格 Prompt 契约

输入顺序固定：

```text
system safety rules
chart_snapshot
persona_profile
memory_summary（仅 enabled=true）
recent_messages
current_user_message
```

人格输出要求：

- 第一人称自然对话，不分节讲盘。
- 可以体现命局形成的思考方式和偏好，不作宿命断言。
- 不冒充真人、不声称有现实感官或线下关系。
- 不作心理诊断，不给医疗、法律和高风险财务结论。
- 不输出吉凶预测、改运、化解等内容。

## 10. 安全状态机

处理顺序不可调整：

1. 输入前置规则检测。
2. 危机命中：退出角色、返回静态求助信息、不消耗额度、写 `safety_event`。
3. 未成年人：禁止创建或进入人格会话。
4. 会话开始满两小时：响应 `rest_reminder_required=true`。
5. LLM 输出后置过滤：违规时替换安全回复并记录。
6. 每屏常驻“AI 生成 · 命局人格模拟”。

危机静态回复必须包含：

- 立即危险时联系 `110` / `120`
- 建议联系可信任的人并避免独处
- 明确 AI 不能替代专业帮助
- 不出现付费、订阅或继续角色扮演引导

`SafetyEvent` 最少字段：

```text
user_id, persona_id, conversation_id, category, action,
rule_version, content_hash, created_at
```

不得保存危机原文到安全事件表。

## 11. 今日节律

### `GET /api/daily/rhythm?person_id=`

响应：

```json
{
  "date": "2026-10-28",
  "energy_state": "steady",
  "title": "收束杂音，先把一件事做实",
  "suitable": ["整理重点", "完成收尾", "坦诚沟通"],
  "notice": ["避免同时推进过多事项", "重要决定留出复核时间"],
  "action": "给今天最重要的一件事留出完整的一小时。",
  "basis": "金气偏强，适合收拢边界。",
  "chart_ref": {"day_master": "庚金", "daily_pillar": "丁卯"},
  "pressure_level": 45,
  "source": "calculated"
}
```

客户端禁用文案：`吉`、`凶`、`宜`、`忌`、`算命`、`改运`、`化解`。旧 `/api/daily/fortune` 保留兼容，但 V3 页面不得调用。

## 12. 档案 API 变更

新增快照接口：

```text
GET /api/persons/{person_id}/chart-snapshot
```

接口仅返回当前用户档案的标准化快照；快照不存在或 `source_hash` 失效时惰性生成并持久化。

创建/更新档案新增：

```json
{
  "is_self": false,
  "relationship_type": "partner",
  "relationship_note": "伴侣",
  "consent_confirmed": true
}
```

规则：

- 创建本人档案前校验本人唯一性，冲突返回 HTTP 409 `self_profile_exists`。
- 创建任何档案前调用 `require_profile_slot`。
- 他人档案要求 `consent_confirmed=true`，否则返回 HTTP 422。
- 首次报告不再扣积分。

## 13. 积分兼容

- `POST /api/payment/orders` 在 `POINTS_RECHARGE_ENABLED=false` 时返回 HTTP 410。
- 错误码：`points_recharge_disabled`。
- 支付回调、历史订单、积分余额、积分流水、管理端人工调整继续可用。
- 客户端统一称“历史积分”，不显示充值按钮。
- 既有 `ContentUnlock` 继续授权旧内容；新内容由 entitlement 判定。

## 14. 错误码

| HTTP | code | 场景 |
|---:|---|---|
| 403 | `feature_disabled` | V3 或 Persona 开关关闭 |
| 403 | `entitlement_required` | 计划不含该能力 |
| 403 | `usage_limit_reached` | 日/月额度耗尽 |
| 403 | `persona_self_only` | 他人档案创建人格 |
| 403 | `persona_minor_blocked` | 未成年人使用人格 |
| 403 | `conversation_turn_limit` | 单会话已达 20 回合 |
| 404 | `person_not_found` | 档案不存在或不属于用户 |
| 404 | `report_not_found` | 报告不存在或不属于用户 |
| 409 | `self_profile_exists` | 第二份本人档案 |
| 409 | `report_generation_in_progress` | 不允许的重复重试 |
| 410 | `points_recharge_disabled` | 用户充值已停用 |
| 422 | `consent_required` | 他人档案未确认授权 |
| 422 | `invalid_period_key` | 报告周期格式错误 |
| 503 | `generation_unavailable` | 生成服务暂不可用 |

权限失败不得泄露资源是否真实存在；跨用户访问统一返回 404。

## 15. 客户端路由

```text
/today
/reading
/reading/chat/:personId
/reports
/reports/:reportId
/persona
/persona/create/:personId
/persona/chat/:conversationId
/persona/memory/:personaId
/subscription
/profile
```

兼容路由：

```text
/chat/:personId -> /reading/chat/:personId
```

全屏路由不显示底部 Tab：

- `/reading/chat/:personId`
- `/reports/:reportId`
- `/persona/create/:personId`
- `/persona/chat/:conversationId`
- `/persona/memory/:personaId`
- `/subscription`

四 Tab 归属：

- 今日：`/today`
- 解读：`/reading`、`/reports`
- 对话：`/persona`
- 我的：`/profile`

## 16. 客户端状态

每个异步页面至少覆盖：

```text
idle | loading | ready | empty | error | forbidden
```

报告额外状态：

```text
pending | generating | ready | failed
```

人格首页：

- 无本人档案：引导建档
- 本人未成年：显示不可用说明
- 有本人档案、无人格：显示创建引导
- 已有人格、无会话：显示开始对话
- 已有会话：显示最近会话与新建会话
- 月额度耗尽：显示订阅墙，不隐藏历史

## 17. 数据迁移

迁移链：

```text
010_content_unlocks
  -> 011_v3_profile_subscription
  -> 012_v3_reports
  -> 013_v3_persona
```

要求：

- SQLite 与 MySQL 8 均可执行。
- 不复用历史破坏性迁移 `508b12ccf9f5`。
- 011 确定性回填本人档案。
- 新表降级只用于测试；生产回退使用功能开关和备份。
- 升降级演练必须核对旧档案、消息、积分和解锁记录计数。

## 18. 隐私与删除

账号注销必须删除：

- Person 的 V3 快照字段及关联报告
- Persona、PersonaConversation、PersonaMessage、PersonaMemory
- SafetyEvent 中可关联用户主体的数据
- Subscription 和 UsageCounter

依法保留的财务记录必须匿名化用户标识。记忆清空物理删除正文，不进入软删除或恢复队列。

## 19. 可观测字段

报告、解盘问答和人格调用日志至少包含：

```text
request_id, user_id_hash, person_id, report_type/persona_id,
prompt_version, model, latency_ms, input_tokens, output_tokens,
cache_hit, safety_category, result_status
```

禁止记录生辰明文、人格记忆正文和危机原文。

## 20. 验收契约

- 权益矩阵逐格有服务端测试。
- 免费第 2 份档案、每日第 4 问、每月第 4 次人格会话返回结构化 403。
- 轻享第 4 份档案、第 31 次人格会话和年报访问被拒绝。
- 全享上述能力均允许。
- 相同报告 identity 并发创建只有一条记录。
- 他人和未成年人无法创建人格。
- 危机输入不调用 LLM、不消耗额度并写一条安全事件。
- 20 个用户回合后会话拒绝继续发送。
- 关闭记忆后 Prompt 不包含记忆；清空后数据库无记忆正文。
- 今日页面和 API 不出现禁用词。
- 旧聊天、报告、积分流水与解锁内容仍可访问。
