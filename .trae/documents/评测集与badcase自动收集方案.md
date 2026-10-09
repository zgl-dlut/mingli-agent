# 评测集构建与 Badcase 自动收集方案

## Summary

基于现有的 11 个检测函数和重试机制，构建两层质量保障：1）标准评测集用于上线前回归测试；2）线上 badcase 自动收集到示例库，反哺 prompt 持续优化。

## Current State Analysis

### 现有质量检测机制

**11 个检测函数**（[followup\_structured.py:861-1501](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L861)）：

| 检测函数                                       | 行号   | 检测内容      |
| ------------------------------------------ | ---- | --------- |
| `_detect_favored_year_discouraged_actions` | 861  | 吉年禁止劝退表述  |
| `_detect_unfavored_year_actions`           | 982  | 凶年禁止启动类行动 |
| `_detect_favored_label_on_unfavored_year`  | 1045 | 凶年禁止正向标签  |
| `_detect_yongshen_logic_conflict`          | 1156 | 用神逻辑矛盾    |
| `_detect_forbidden_terms`                  | 1219 | 术语黑名单     |
| `_detect_ganzhi_time_notation`             | 1246 | 干支纪时写法    |
| `_detect_synonym_contradiction`            | 1276 | 同义词对立     |
| `_detect_dimension_coverage`               | 1344 | 维度覆盖      |
| `_detect_summary_duplication`              | 1383 | 总结重复      |
| `_detect_past_month_suggestions`           | 1434 | 过去月份建议    |
| `_detect_llm_contradiction`                | 1501 | LLM 结论矛盾  |

**重试机制**（[followup\_structured.py:2059-2251](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L2059)）：

* 首次生成后跑全量检测

* 违规时动态拼装修正提示（`_build_retry_hint`），最多重试 2 次

* 重试仍违规则降级返回 + 日志告警

* **缺失**：重试仍违规的 badcase 没有持久化存储，无法反哺优化

**反馈系统**（[feedback\_service.py](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/feedback_service.py)）：

* SQLite 存储，支持人工评分（human\_score）、模型自评（model\_score）、标签

* **缺失**：没有自动收集检测失败的 badcase，只有用户主动反馈

**prompt 示例**（[followup\_structured.py:375](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L375)）：

* prompt 中有"对照示例"区域，但目前是硬编码的静态示例

* **缺失**：无法动态注入从 badcase 中提取的典型错误案例

### 历史优化方向（从 project\_memory 提取）

核心优化集中在以下几个方向：

1. **一致性**：开篇与正文一致、三方一致（opening/subtopic/summary）
2. **术语管控**：黑名单术语替换为大白话
3. **方向锁定**：凶年禁启动、吉年禁劝退
4. **模糊词定义**：裁员大礼包/赔偿金等价、机会/破财/变动等定义
5. **时间因果**：时间节点必须配套因果说明
6. **维度覆盖**：未来结果类问题必须展开四层维度

## Proposed Changes

### 第一部分：Badcase 自动收集（线上 → 示例库）

#### 1.1 新建 badcase 存储模型

**文件**：`backend/app/models/badcase.py`（新建）

```python
class BadCase(Base):
    __tablename__ = "bad_cases"
    id = Column(Integer, primary_key=True)
    person_id = Column(Integer)  # 关联人物
    question = Column(Text)  # 用户问题
    chart_fingerprint = Column(String)  # 命盘指纹（脱敏）
    violation_type = Column(String)  # 违规类型（如"凶年启动""术语黑名单"）
    violation_detail = Column(Text)  # 违规详情（JSON）
    raw_output = Column(Text)  # LLM 原始输出（JSON）
    retry_count = Column(Integer)  # 重试次数
    final_status = Column(String)  # "fixed"=重试后修复 / "degraded"=降级返回
    created_at = Column(DateTime)
    reviewed = Column(Boolean, default=False)  # 是否人工审核过
    example_text = Column(Text)  # 审核后提取的示例文本（正确 vs 错误对比）
```

#### 1.2 在重试终止处自动入库

**文件**：`backend/app/services/followup_structured.py`

**改动位置**：[followup\_structured.py:2250](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L2250)（`max_retries` 次重试后仍违规的降级返回处）

**改动内容**：在 `logger.warning` 之后，把违规信息写入 badcase 表：

```python
# 重试仍违规，自动收集 badcase
try:
    await save_badcase(
        person_id=person_id,
        question=user_question,
        chart_fingerprint=get_chart_fingerprint(analysis_data),
        violation_type=','.join(set(v['type'] for v in current_violations['all'])),
        violation_detail=json.dumps(current_violations['all'], ensure_ascii=False),
        raw_output=json.dumps(data, ensure_ascii=False),
        retry_count=max_retries,
        final_status="degraded",
    )
except Exception as e:
    logger.error(f"[BadCase] 入库失败: {e}")
```

同时在**重试成功**处也记录（`final_status="fixed"`），用于统计修复率。

#### 1.3 后台审核界面

**文件**：`backend/app/api/admin.py` 新增 `/api/admin/badcases` 接口

* 列表页：展示未审核的 badcase，按违规类型筛选

* 审核操作：人工查看错误输出 → 提取"错误写法 vs 正确写法"对比 → 填入 `example_text` → 标记 `reviewed=True`

### 第二部分：示例库动态注入

#### 2.1 示例库存储

**文件**：`backend/app/models/badcase.py` 同表，`example_text` 字段存储审核后的示例

格式：

```json
{
  "violation_type": "凶年启动",
  "error": "2034年适合启动副业（错误：凶年安排启动类行动）",
  "correct": "2034年大凶，不宜启动副业，建议防守为主",
  "rule": "凶年（命盘judge含'凶'）禁止安排启动类行动"
}
```

#### 2.2 prompt 动态注入

**文件**：`backend/app/services/followup_structured.py` - `build_structured_prompt`

**改动位置**：[followup\_structured.py:375](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L375)（"对照示例"区域）

**改动内容**：从 badcase 表查询最近 5 条已审核的典型示例，动态注入 prompt：

```python
# 查询已审核的典型 badcase 示例
examples = await get_reviewed_badcases(limit=5)
example_section = ""
for ex in examples:
    example_section += f"\n❌ 错误：{ex['error']}\n✅ 正确：{ex['correct']}\n规则：{ex['rule']}\n"
```

### 第三部分：标准评测集

#### 3.1 评测集结构

**文件**：`backend/tests/eval_dataset.json`（新建）

```json
[
  {
    "id": "eval_001",
    "category": "凶年启动",
    "person": {"birth": "1996-05-15", "gender": "male", "name": "测试用户A"},
    "question": "2027年适合创业吗？",
    "expected_rules": ["2027为凶年，禁止鼓励创业", "必须标注凶/大凶"],
    "assertions": [
      {"type": "no_forbidden_terms", "params": {}},
      {"type": "no_unfavored_year_actions", "params": {"year": 2027}},
      {"type": "no_favored_label_on_unfavored", "params": {"year": 2027}}
    ]
  }
]
```

#### 3.2 评测脚本

**文件**：`backend/tests/run_eval.py`（新建）

```python
"""运行评测集，输出通过率报告"""
# 1. 加载 eval_dataset.json
# 2. 对每个 case 调用 generate_followup_structured
# 3. 用 11 个检测函数跑检测
# 4. 输出报告：通过率、违规类型分布、具体失败 case
```

#### 3.3 评测集内容（基于历史优化方向）

按历史优化方向分类，每类 3-5 个 case：

| 类别      | case 数 | 覆盖场景             |
| ------- | ------ | ---------------- |
| 凶年启动/标签 | 5      | 凶年安排副业、凶年贴吉标签    |
| 吉年劝退    | 3      | 吉年说"不适合跳槽"       |
| 术语黑名单   | 5      | 七杀/正官/卯酉相冲等      |
| 同义词对立   | 3      | "拿不到裁员大礼包但能谈出补偿" |
| 一致性     | 5      | 开篇与正文矛盾          |
| 维度覆盖    | 3      | "之后会怎样"未展开四层     |
| 时间因果    | 3      | 给时间点无因果          |
| 模糊词定义   | 3      | 机会/破财/变动未定义      |

## Assumptions & Decisions

1. **badcase 表用 PostgreSQL**（与现有 AiUsageLog 同库），不用 SQLite（feedback.db 是独立轻量存储，badcase 需要关联 person\_id 用主库更合适）

2. **评测集用 JSON 文件**（不入库），方便版本管理和 diff

3. **示例注入上限 5 条**，避免 prompt 过长影响缓存命中率（固定部分不变，示例注入到动态部分）

4. **badcase 自动入库是异步的**，不阻塞主流程（try/except 包裹，失败只记日志）

5. **示例注入位置在动态部分**（"# 本次会话信息"之后），不影响固定部分缓存

6. **评测集需要真实命盘数据**，使用 divination skill 排盘后构造，不编造命盘

## Verification Steps

1. 创建 badcase 模型和迁移
2. 在重试终止处接入 badcase 自动入库
3. 新增后台 badcase 审核接口
4. 构建评测集 JSON（30+ case）
5. 编写评测脚本
6. 运行评测集验证检测函数覆盖率
7. 触发一次追问，故意构造违规场景，确认 badcase 自动入库
8. 后台审核 badcase，填入示例文本
9. 下次追问时确认示例被注入 prompt

