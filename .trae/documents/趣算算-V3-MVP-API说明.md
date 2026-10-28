# 趣算算 V3 MVP API 说明

> 日期：2026-10-28  
> API 前缀：`/api`  
> 认证：除计划列表和功能开关外，均使用 `Authorization: Bearer <token>`

## 功能与权益

```text
GET  /features
GET  /subscriptions/plans
GET  /subscriptions/current
POST /subscriptions/mock-activate
POST /subscriptions/mock-expire
GET  /entitlements/me
```

`/features` 返回 `v3_enabled`、`persona_enabled`、`other_persona_enabled`、`points_recharge_enabled` 和 `subscription_mock_enabled`。

## 档案与命盘

```text
POST /persons
GET  /persons
GET  /persons/{person_id}
PUT  /persons/{person_id}
GET  /persons/{person_id}/chart-snapshot
GET  /chart/{person_id}
```

V3 档案增加 `is_self`、`relationship_type`、`relationship_note` 和授权确认。每个账号最多一份本人档案。

## 今日节律

```text
GET /daily/rhythm?person_id=&date=YYYY-MM-DD
```

响应核心字段：

```json
{
  "energy_state": "smooth",
  "suitable": ["沟通", "推进"],
  "notice": ["拖延"],
  "action": "先完成最重要的一件事。",
  "basis": "今天整体节奏偏顺。",
  "chart_ref": "基于当日节奏与命盘关系",
  "pressure_level": 35
}
```

旧 `/daily/fortune` 保留一个兼容周期。

## 统一报告

```text
GET  /reports
POST /reports
GET  /reports/{report_id}
GET  /reports/{report_id}/status
POST /reports/import-legacy
```

`report_type`：

```text
base_report | monthly_brief | annual_brief | relation_report | qa_reading
```

创建月报要求 `period_key=YYYY-MM`，年报要求 `period_key=YYYY`，关系报告要求两份不同且都属于当前用户的档案。相同 identity 幂等返回原报告。

## 命局人格

```text
POST   /personas
GET    /personas
GET    /personas/{persona_id}
POST   /personas/{persona_id}/conversations
GET    /personas/{persona_id}/conversations
GET    /persona-conversations/{conversation_id}/messages
POST   /persona-conversations/{conversation_id}/messages
GET    /personas/{persona_id}/memory
PATCH  /personas/{persona_id}/memory-settings
DELETE /personas/{persona_id}/memory
```

发送人格消息使用 SSE：

```text
event: meta
data: {"message_id":91,"rest_reminder_required":false}

event: delta
data: {"text":"我会先和你一起把事实理清。"}

event: done
data: {"user_turn_count":4,"remaining_turns":16}
```

危机输入不调用 LLM，不增加用户回合，`done` 事件直接返回静态求助信息。

## 统一错误

```json
{
  "code": "entitlement_required",
  "message": "当前权益不足",
  "required_plan": "full",
  "metric": "annual_brief",
  "remaining": 0
}
```

常用错误码：

```text
feature_disabled
entitlement_required
usage_limit_reached
self_profile_exists
self_profile_required
minor_not_allowed
conversation_turn_limit
conversation_closed
points_recharge_disabled
```
