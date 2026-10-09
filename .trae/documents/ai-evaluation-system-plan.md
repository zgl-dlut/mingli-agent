# AI测评标准实践方案 - 追问报告评测体系

## 一、目标与范围

**目标**：构建一个基于业务的完美AI测评标准实践案例，用于自动化评估追问报告的质量，并驱动持续迭代。

**范围**：
- 评测对象：仅追问报告（followup_structured.py生成）
- 评测结果：硬性检查Pass/Fail + 软性质量评分（0-100），综合判定
- 测试数据：大规模数据集（50+命盘），覆盖各种边界情况

---

## 二、评测指标体系

### 2.1 核心指标定义

#### 2.1.1 任务完成率（Task Completion Rate）

**定义**：系统成功生成满足用户需求的报告的比例。

**分层理解**：

| 层级 | 指标名称 | 定义 | 计算方式 |
|------|----------|------|----------|
| L1 | 技术完成率 | 系统能否成功生成报告（无技术错误） | 成功生成数 / 总请求数 |
| L2 | 格式完成率 | 生成的报告是否符合JSON Schema | 格式合规数 / 成功生成数 |
| L3 | 质量完成率 | 生成的报告是否通过硬性检查 | 硬性通过数 / 格式合规数 |
| L4 | 满意度完成率 | 生成的报告是否满足用户需求（软性评分>=70） | 软性通过数 / 质量通过数 |

**综合任务完成率**：
```
综合任务完成率 = L1 × L2 × L3 × L4
```

#### 2.1.2 正确率（Accuracy Rate）

**定义**：生成的报告在命盘数据、逻辑推理、内容一致性等方面的正确程度。

| 维度 | 检测内容 | 权重 |
|------|----------|------|
| 排盘正确性 | 四柱、十神、大运、流年、流月 | 30% |
| 命理逻辑一致性 | 用神逻辑、凶年/吉年判断、同义词对立 | 25% |
| 内容一致性 | 开篇-正文-总结一致性、结论矛盾 | 20% |
| 数据真实性 | 不编造大运/流年/用神/忌神 | 15% |
| 术语合规性 | 术语黑名单、术语解释 | 10% |

### 2.2 指标关系

```
任务完成率 = 技术完成率 × 格式完成率 × 质量完成率 × 满意度完成率
           = 系统能力 × 格式规范 × 硬性质量 × 软性质量

正确率 = 排盘正确性×0.3 + 命理逻辑×0.25 + 内容一致性×0.2 + 数据真实性×0.15 + 术语合规性×0.1
```

---

## 三、任务完成率落地实现

### 3.1 数据采集点

#### 3.1.1 L1 技术完成率
- **数据来源**：`ai_usage_logs` 表 `success` 字段（已有）
- **当前状态**：✅ 可直接计算

#### 3.1.2 L2 格式完成率
- **数据来源**：`followup_structured.py` 异常捕获
- **当前状态**：⚠️ 需在 `ai_usage_logs` 表新增 `format_error` 字段

#### 3.1.3 L3 质量完成率
- **数据来源**：新增 `eval_report_logs` 表
- **当前状态**：⚠️ 需新建表

#### 3.1.4 L4 满意度完成率
- **数据来源**：`eval_report_logs` 表 `avg_soft_score` 字段
- **当前状态**：⚠️ 需在生成报告后调用 LLM 评分

### 3.2 数据库迁移脚本

#### 迁移1：`ai_usage_logs` 新增 `format_error` 字段

**文件**：`backend/alembic/versions/004_add_format_error_to_ai_usage_logs.py`

```python
"""add format_error to ai_usage_logs

Revision ID: 004
Revises: 003
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'  # 接续现有迁移003
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        'ai_usage_logs',
        sa.Column('format_error', sa.String(50), nullable=True,
                  comment='格式错误类型: json_decode / validation / None')
    )

def downgrade() -> None:
    op.drop_column('ai_usage_logs', 'format_error')
```

#### 迁移2：新建 `eval_report_logs` 表

**文件**：`backend/alembic/versions/005_create_eval_report_logs.py`

```python
"""create eval_report_logs

Revision ID: 005
Revises: 004
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'eval_report_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('biz_type', sa.String(20), nullable=False,
                  comment='first_reading / followup'),
        sa.Column('question', sa.Text(), nullable=True,
                  comment='用户追问内容'),
        # 任务完成率
        sa.Column('format_error', sa.String(50), nullable=True,
                  comment='格式错误类型'),
        sa.Column('hard_check_passed', sa.Boolean(), default=False,
                  comment='硬性检查是否通过'),
        sa.Column('hard_check_violations', sa.JSON(), nullable=True,
                  comment='违规明细列表'),
        # 软性评分
        sa.Column('soft_score', sa.JSON(), nullable=True,
                  comment='各维度评分 {"叙事性":85,...}'),
        sa.Column('avg_soft_score', sa.Integer(), nullable=True,
                  comment='平均软性评分'),
        # 综合判定
        sa.Column('overall_pass', sa.Boolean(), default=False,
                  comment='综合是否通过'),
        # 评测报告快照（用于迭代对比）
        sa.Column('eval_snapshot_id', sa.Integer(), nullable=True,
                  comment='关联的评测快照ID'),
        # 时间戳
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_eval_report_logs_user_id', 'eval_report_logs', ['user_id'])
    op.create_index('ix_eval_report_logs_created_at', 'eval_report_logs', ['created_at'])
    op.create_index('ix_eval_report_logs_biz_type', 'eval_report_logs', ['biz_type'])
    op.create_index('ix_eval_report_logs_overall_pass', 'eval_report_logs', ['overall_pass'])

def downgrade() -> None:
    op.drop_table('eval_report_logs')
```

#### 迁移3：新建 `eval_snapshots` 表（评测快照，用于迭代对比）

**文件**：`backend/alembic/versions/006_create_eval_snapshots.py`

```python
"""create eval_snapshots

Revision ID: 006
Revises: 005
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'eval_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False,
                  comment='快照名称，如 v1.0-初始版 / v1.1-修复凶年标签'),
        sa.Column('description', sa.Text(), nullable=True,
                  comment='本次迭代说明'),
        sa.Column('git_commit', sa.String(40), nullable=True,
                  comment='关联的git commit hash'),
        # 任务完成率快照
        sa.Column('task_completion_rate', sa.JSON(), nullable=True,
                  comment='{"l1":0.95,"l2":0.90,"l3":0.85,"l4":0.80,"overall":0.58}'),
        # 正确率快照
        sa.Column('accuracy_rate', sa.JSON(), nullable=True,
                  comment='{"chart":0.95,"logic":0.90,...,"overall":0.91}'),
        # 各维度通过率
        sa.Column('dimension_pass_rates', sa.JSON(), nullable=True,
                  comment='{"排盘正确性":0.95,"结构合规性":0.88,...}'),
        # 汇总统计
        sa.Column('total_cases', sa.Integer(), nullable=False,
                  comment='总测试用例数'),
        sa.Column('passed_cases', sa.Integer(), nullable=False,
                  comment='通过用例数'),
        sa.Column('pass_rate', sa.Float(), nullable=False,
                  comment='总通过率'),
        sa.Column('avg_soft_score', sa.Float(), nullable=True,
                  comment='平均软性评分'),
        # 违规分布
        sa.Column('violation_distribution', sa.JSON(), nullable=True,
                  comment='{"凶年启动":12,"术语未解释":5,...}'),
        # 详细结果
        sa.Column('results', sa.JSON(), nullable=True,
                  comment='每个用例的详细评测结果'),
        # 时间戳
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_eval_snapshots_created_at', 'eval_snapshots', ['created_at'])

def downgrade() -> None:
    op.drop_table('eval_snapshots')
```

### 3.3 模型更新

#### `backend/app/models/usage_log.py` 新增字段

```python
class AiUsageLog(Base):
    # ... 现有字段保持不变 ...
    format_error: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="格式错误类型: json_decode / validation / None"
    )
```

#### 新建 `backend/app/models/eval_report_log.py`

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func
from app.database import Base

class EvalReportLog(Base):
    """每次生成报告的评测日志"""
    __tablename__ = "eval_report_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    session_id = Column(Integer, nullable=True)
    biz_type = Column(String(20), nullable=False)
    question = Column(Text, nullable=True)
    format_error = Column(String(50), nullable=True)
    hard_check_passed = Column(Boolean, default=False)
    hard_check_violations = Column(JSON, nullable=True)
    soft_score = Column(JSON, nullable=True)
    avg_soft_score = Column(Integer, nullable=True)
    overall_pass = Column(Boolean, default=False)
    eval_snapshot_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
```

#### 新建 `backend/app/models/eval_snapshot.py`

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, JSON
from sqlalchemy.sql import func
from app.database import Base

class EvalSnapshot(Base):
    """评测快照 - 每次迭代生成一份，用于前后对比"""
    __tablename__ = "eval_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    git_commit = Column(String(40), nullable=True)
    task_completion_rate = Column(JSON, nullable=True)
    accuracy_rate = Column(JSON, nullable=True)
    dimension_pass_rates = Column(JSON, nullable=True)
    total_cases = Column(Integer, nullable=False)
    passed_cases = Column(Integer, nullable=False)
    pass_rate = Column(Float, nullable=False)
    avg_soft_score = Column(Float, nullable=True)
    violation_distribution = Column(JSON, nullable=True)
    results = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
```

### 3.4 采集逻辑修改

#### `followup_structured.py` 中 L2 格式错误采集

```python
# 在 JSON 解析和 Pydantic 校验的 except 块中记录 format_error
async def _log_ai_usage(..., format_error: str = None):
    """记录 AI 调用日志，包含格式错误信息"""
    db = SessionLocal()
    try:
        log = AiUsageLog(
            user_id=user_id,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            success=success,
            duration_ms=duration_ms,
            biz_type=biz_type,
            format_error=format_error,  # 新增
        )
        db.add(log)
        db.commit()
    finally:
        db.close()

# 在生成报告的 try/except 中：
try:
    raw = await call_llm(...)
    data = json.loads(raw)          # 可能抛 JSONDecodeError
    report = FollowupReport(**data)  # 可能抛 ValidationError
    await _log_ai_usage(..., format_error=None)
except json.JSONDecodeError:
    await _log_ai_usage(..., format_error="json_decode", success=False)
    raise
except ValidationError:
    await _log_ai_usage(..., format_error="validation", success=False)
    raise
```

### 3.5 评测快照生成（独立评测，非累计）

**核心概念**：每次评测是一个独立的快照，对比时是两个快照的对比，不是历史数据的累计。

**文件**：`backend/app/services/eval/snapshot_service.py`

```python
from datetime import datetime
from typing import List, Dict, Optional
import subprocess

def create_eval_snapshot(
    name: str,
    description: str = "",
    eval_results: List[Dict] = None,
) -> Dict:
    """创建评测快照
    
    每次运行评测时调用，生成一个独立的快照。
    快照包含该次评测的完整结果，用于迭代前后对比。
    
    Args:
        name: 快照名称，如 "v1.0-初始版" / "v1.1-修复凶年标签"
        description: 本次迭代说明
        eval_results: 该次评测的详细结果列表，每个元素包含：
            {
                "id": "chart_001",
                "overall_pass": True,
                "hard_check": {...},
                "soft_score": {...},
                "avg_soft_score": 85,
                ...
            }
    
    Returns:
        {"id": snapshot_id, "name": name}
    """
    from app.models.eval_snapshot import EvalSnapshot
    from app.database import SessionLocal

    # 获取当前 git commit
    try:
        git_commit = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd='/Users/zhangguangling/Downloads/命理推算/mingli-agent'
        ).decode().strip()
    except Exception:
        git_commit = None

    # 基于该次评测结果计算指标（不是基于历史数据）
    total_cases = len(eval_results) if eval_results else 0
    passed_cases = sum(1 for r in (eval_results or []) if r.get("overall_pass"))
    pass_rate = passed_cases / total_cases if total_cases > 0 else 0

    # 计算各维度通过率
    dimension_stats = _calculate_dimension_stats(eval_results)
    
    # 统计违规分布
    violation_dist = _calculate_violation_distribution(eval_results)

    # 计算平均软性评分
    soft_scores = [r.get("avg_soft_score", 0) for r in (eval_results or []) if r.get("avg_soft_score")]
    avg_soft = sum(soft_scores) / len(soft_scores) if soft_scores else 0

    # 计算任务完成率（基于该次评测的数据集）
    task_rate = _calculate_task_completion_rate_from_results(eval_results)

    db = SessionLocal()
    try:
        snapshot = EvalSnapshot(
            name=name,
            description=description,
            git_commit=git_commit,
            task_completion_rate=task_rate,
            accuracy_rate=dimension_stats.get("accuracy_rate"),
            dimension_pass_rates=dimension_stats.get("dimension_pass_rates"),
            total_cases=total_cases,
            passed_cases=passed_cases,
            pass_rate=pass_rate,
            avg_soft_score=avg_soft,
            violation_distribution=violation_dist,
            results=eval_results,  # 保存完整结果，用于用例级对比
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return {"id": snapshot.id, "name": name}
    finally:
        db.close()


def _calculate_task_completion_rate_from_results(eval_results: List[Dict]) -> Dict:
    """基于该次评测结果计算任务完成率（L1-L4）
    
    注意：这是基于该次评测的数据集，不是基于 eval_report_logs 的历史数据。
    """
    if not eval_results:
        return {
            "l1_technical": 0,
            "l2_format": 0,
            "l3_quality": 0,
            "l4_satisfaction": 0,
            "overall": 0,
        }

    total = len(eval_results)
    
    # L1: 技术完成率（能生成报告）
    # 在评测数据集中，所有用例都应该是成功生成的（否则不会进入评测）
    # 所以 L1 = 100%（或者根据实际的失败用例调整）
    l1 = 1.0  # 假设评测数据集都是成功生成的
    
    # L2: 格式完成率（JSON符合Schema）
    format_ok = sum(1 for r in eval_results if not r.get("format_error"))
    l2 = format_ok / total if total > 0 else 0
    
    # L3: 质量完成率（通过硬性检查）
    hard_passed = sum(1 for r in eval_results if r.get("hard_check", {}).get("passed", False))
    l3 = hard_passed / format_ok if format_ok > 0 else 0
    
    # L4: 满意度完成率（软性评分>=70）
    soft_passed = sum(1 for r in eval_results 
                     if r.get("hard_check", {}).get("passed", False) 
                     and (r.get("avg_soft_score") or 0) >= 70)
    l4 = soft_passed / hard_passed if hard_passed > 0 else 0
    
    return {
        "l1_technical": round(l1, 4),
        "l2_format": round(l2, 4),
        "l3_quality": round(l3, 4),
        "l4_satisfaction": round(l4, 4),
        "overall": round(l1 * l2 * l3 * l4, 4),
        "sample_size": {
            "total": total,
            "format_ok": format_ok,
            "hard_passed": hard_passed,
            "soft_passed": soft_passed,
        }
    }


def _calculate_dimension_stats(eval_results: List[Dict]) -> Dict:
    """计算各维度通过率和正确率"""
    if not eval_results:
        return {}
    
    dimensions = ["chart", "structure", "narrative", "chart_usage", "logic", "consistency", "safety"]
    dimension_pass = {d: 0 for d in dimensions}
    dimension_total = {d: 0 for d in dimensions}
    
    for r in eval_results:
        hard = r.get("hard_check", {})
        for d in dimensions:
            violations = hard.get(d, [])
            dimension_total[d] += 1
            if len(violations) == 0:
                dimension_pass[d] += 1
    
    dimension_pass_rates = {
        d: round(dimension_pass[d] / dimension_total[d], 4)
        for d in dimensions if dimension_total[d] > 0
    }
    
    # 正确率加权计算
    weights = {"chart": 0.30, "logic": 0.25, "consistency": 0.20, 
               "chart_usage": 0.15, "narrative": 0.10}
    accuracy = sum(
        dimension_pass_rates.get(d, 0) * w
        for d, w in weights.items()
    )
    
    return {
        "dimension_pass_rates": dimension_pass_rates,
        "accuracy_rate": {**dimension_pass_rates, "overall": round(accuracy, 4)}
    }


def _calculate_violation_distribution(eval_results: List[Dict]) -> Dict:
    """统计违规类型分布"""
    dist = {}
    for r in (eval_results or []):
        hard = r.get("hard_check", {})
        for checker_name, violations in hard.items():
            if isinstance(violations, list):
                for v in violations:
                    rule = v.get("rule", "unknown") if isinstance(v, dict) else str(v)
                    dist[rule] = dist.get(rule, 0) + 1
    return dist
```

---

## 四、L2 格式完成率测试数据

### 4.1 测试目标

验证 `followup_structured.py` 中 JSON 解析失败和 Pydantic 校验失败的捕获逻辑是否正确记录 `format_error`。

### 4.2 测试数据构造

**文件**：`backend/tests/test_format_error_capture.py`

```python
"""L2 格式完成率 - 捕获逻辑验证"""
import json
import pytest
from pydantic import ValidationError

# ============================================================
# 测试数据：模拟 LLM 返回的各种异常 JSON
# ============================================================

FORMAT_ERROR_CASES = [
    # ---- JSON 解析失败（json_decode） ----
    {
        "id": "fmt_001",
        "name": "空响应",
        "raw": "",
        "expected_error": "json_decode",
    },
    {
        "id": "fmt_002",
        "name": "纯文本非JSON",
        "raw": "这是一段分析报告，不是JSON格式",
        "expected_error": "json_decode",
    },
    {
        "id": "fmt_003",
        "name": "截断JSON（LLM输出被截断）",
        "raw": '{"opening":{"lead":"测试","verdict":"测试结论"},"subtopics":[',
        "expected_error": "json_decode",
    },
    {
        "id": "fmt_004",
        "name": "Markdown代码块包裹（需先剥离）",
        "raw": '```json\n{"opening":{"lead":"测试","verdict":"结论"}}\n```',
        "expected_error": None,  # 容错函数应能处理
    },
    {
        "id": "fmt_005",
        "name": "多余逗号",
        "raw": '{"opening":{"lead":"测试",,"verdict":"结论"}}',
        "expected_error": "json_decode",
    },
    {
        "id": "fmt_006",
        "name": "单引号替代双引号",
        "raw": "{'opening': {'lead': '测试'}}",
        "expected_error": "json_decode",
    },
    {
        "id": "fmt_007",
        "name": "未闭合的字符串",
        "raw": '{"opening":{"lead":"测试没有结束',
        "expected_error": "json_decode",
    },
    {
        "id": "fmt_008",
        "name": "非法转义字符",
        "raw": '{"opening":{"lead":"测试\n换行"}}',
        "expected_error": "json_decode",
    },

    # ---- Pydantic 校验失败（validation） ----
    {
        "id": "fmt_009",
        "name": "缺少必填字段opening",
        "raw": json.dumps({"subtopics": [], "summary": {}}),
        "expected_error": "validation",
    },
    {
        "id": "fmt_010",
        "name": "缺少必填字段subtopics",
        "raw": json.dumps({"opening": {"lead": "测试", "verdict": "结论"}, "summary": {}}),
        "expected_error": "validation",
    },
    {
        "id": "fmt_011",
        "name": "subtopics为空数组",
        "raw": json.dumps({
            "opening": {"lead": "测试", "verdict": "结论"},
            "subtopics": [],
            "summary": {"title": "总结", "items": []}
        }),
        "expected_error": "validation",  # subtopics最少1个
    },
    {
        "id": "fmt_012",
        "name": "block缺少keyword",
        "raw": json.dumps({
            "opening": {"lead": "测试", "verdict": "结论"},
            "subtopics": [{
                "title": "子问题1",
                "blocks": [{"type": "keyword", "narrative": "描述内容"}]
                # 缺少 keyword 字段
            }],
            "summary": {"title": "总结", "items": []}
        }),
        "expected_error": "validation",
    },
    {
        "id": "fmt_013",
        "name": "narrative为空字符串",
        "raw": json.dumps({
            "opening": {"lead": "测试", "verdict": "结论"},
            "subtopics": [{
                "title": "子问题1",
                "blocks": [{"type": "keyword", "keyword": "关键词", "narrative": ""}]
            }],
            "summary": {"title": "总结", "items": []}
        }),
        "expected_error": "validation",  # narrative至少30字
    },
    {
        "id": "fmt_014",
        "name": "type字段非法值",
        "raw": json.dumps({
            "opening": {"lead": "测试", "verdict": "结论"},
            "subtopics": [{
                "title": "子问题1",
                "blocks": [{"type": "paragraph", "keyword": "关键词", "narrative": "描述"}]
                # type 只允许 keyword / narrative / group
            }],
            "summary": {"title": "总结", "items": []}
        }),
        "expected_error": "validation",
    },

    # ---- 正常数据（无错误） ----
    {
        "id": "fmt_015",
        "name": "完全合规的JSON",
        "raw": json.dumps({
            "opening": {"lead": "今年整体运势不错", "verdict": "事业有突破，财运平稳"},
            "subtopics": [{
                "title": "事业发展方向",
                "blocks": [
                    {"type": "keyword", "keyword": "上半年蓄力期", "narrative": "1-6月适合积累资源和人脉，不宜急于求成，稳扎稳打为下半年做准备。"},
                    {"type": "keyword", "keyword": "下半年突破期", "narrative": "7-12月迎来事业转机，有贵人相助，适合主动出击争取机会。"}
                ]
            }],
            "summary": {
                "title": "全年运势总结",
                "items": [
                    {"keyword": "上半年蓄力", "text": "1-6月稳扎稳打积累资源"},
                    {"keyword": "下半年突破", "text": "7-12月贵人相助迎来转机"}
                ]
            }
        }),
        "expected_error": None,
    },
]
```

### 4.3 测试执行逻辑

```python
@pytest.mark.parametrize("case", FORMAT_ERROR_CASES, ids=[c["id"] for c in FORMAT_ERROR_CASES])
def test_format_error_capture(case):
    """验证各种异常 JSON 的捕获逻辑"""
    raw = case["raw"]
    expected_error = case["expected_error"]

    format_error = None
    try:
        # 模拟 followup_structured.py 的解析流程
        from app.services.eval.json_fixer import fix_json_string
        fixed = fix_json_string(raw)
        data = json.loads(fixed)
        # 模拟 Pydantic 校验
        from app.models.followup_report import FollowupReport
        FollowupReport(**data)
    except json.JSONDecodeError:
        format_error = "json_decode"
    except ValidationError:
        format_error = "validation"

    assert format_error == expected_error, \
        f"[{case['id']}] {case['name']}: 期望 {expected_error}, 实际 {format_error}"
```

### 4.4 预期结果

| 编号 | 场景 | 期望捕获 | 说明 |
|------|------|----------|------|
| fmt_001 | 空响应 | json_decode | 空字符串无法解析 |
| fmt_002 | 纯文本 | json_decode | 非JSON格式 |
| fmt_003 | 截断JSON | json_decode | LLM输出被截断 |
| fmt_004 | Markdown包裹 | None | 容错函数应能处理 |
| fmt_005 | 多余逗号 | json_decode | 非法JSON语法 |
| fmt_006 | 单引号 | json_decode | Python dict非JSON |
| fmt_007 | 未闭合字符串 | json_decode | 缺少引号 |
| fmt_008 | 非法转义 | json_decode | 裸换行符 |
| fmt_009 | 缺少opening | validation | Pydantic必填字段 |
| fmt_010 | 缺少subtopics | validation | Pydantic必填字段 |
| fmt_011 | subtopics空 | validation | 最少1个子问题 |
| fmt_012 | 缺少keyword | validation | block必填字段 |
| fmt_013 | narrative空 | validation | 最少30字 |
| fmt_014 | type非法值 | validation | 枚举值校验 |
| fmt_015 | 完全合规 | None | 正常通过 |

---

## 五、评测维度设计

### 5.1 硬性检查层（Pass/Fail，一票否决）

| 检测器 | 文件 | 检测维度 | 状态 |
|--------|------|----------|------|
| 排盘正确性 | chart_checker.py | 四柱、十神、大运方向、起运年龄、流年流月 | ✅ 已有 |
| 结构合规性 | structure_checker.py | 子问题拆解、blocks数量、keyword/narrative长度 | ✅ 已有 |
| 术语合规性 | narrative_checker.py | 术语黑名单、术语解释、元标签 | ✅ 已有 |
| 数据真实性 | chart_usage_checker.py | 编造大运/流年/用神/忌神 | ✅ 已有 |
| 命理逻辑一致性 | logic_checker.py | 用神矛盾、同义词对立、凶年/吉年检测、干支纪时 | 🆕 新增 |
| 内容一致性 | consistency_checker.py | 开篇-正文-总结一致性、结论矛盾 | 🆕 新增 |
| 内容安全性 | safety_checker.py | 引导消费、免责声明、模糊词汇 | 🆕 新增 |

### 5.2 软性评分层（0-100分，加权平均）

| 维度 | 权重 | 说明 |
|------|------|------|
| 叙事性 | 20% | 是否像给朋友讲故事 |
| 通顺性 | 20% | 语句是否流畅自然 |
| 故事性 | 20% | 是否有故事感 |
| 加粗合理性 | 20% | 加粗是否用在关键词上 |
| 术语通俗化 | 20% | 术语是否紧跟通俗解释 |

### 5.3 综合判定规则
```
硬性检查通过 AND 软性评分 >= 70 → 整体通过
硬性检查失败 OR 软性评分 < 70 → 整体失败
```

---

## 六、评测驱动的迭代闭环

### 6.1 迭代类型

| 类型 | 触发条件 | 执行方式 | 周期 |
|------|----------|----------|------|
| 自动化迭代 | 硬性检查失败率>5% | 自动修复代码、调整prompt | 实时/每日 |
| 人工迭代 | 软性评分<70或用户反馈差 | 人工分析badcase、调整prompt | 每周/每月 |
| 混合迭代 | 任务完成率下降 | 自动化+人工结合 | 每月/每季度 |

### 6.2 自动化迭代流程

1. **问题定位**：分析违规分布，识别集中出现的问题类型
2. **根因分析**：提取失败case的关键信息，定位根因
3. **自动修复**：调整prompt / 检测规则 / 排盘算法
4. **验证效果**：重新运行评测，检查改进效果

### 6.3 人工迭代流程

1. **Badcase收集**：收集软性评分<70的case
2. **人工分析**：按维度分析（叙事性/通顺性/故事性等）
3. **Prompt优化**：调整prompt措辞和约束
4. **补充测试用例**：为badcase补充expected数据
5. **验证效果**：重新运行评测

---

## 七、测试数据集设计

### 7.1 数据集结构

```json
{
  "id": "chart_001",
  "description": "测试用例描述",
  "birth": {
    "year": 1990, "month": 11, "day": 10,
    "hour": 8, "minute": 0, "gender": "女",
    "longitude": 116.4, "latitude": 39.9, "location": "北京"
  },
  "expected": {
    "四柱": "庚午 丁亥 己卯 戊辰",
    "日主天干": "己",
    "大运方向": "逆",
    "起运年龄": 0.8,
    "大运列表": [...],
    "流年": {...}
  }
}
```

### 7.2 覆盖维度（共78个用例）

| 类别 | 数量 | 说明 |
|------|------|------|
| 基础用例（10日主×2性别） | 20 | 覆盖所有日主和性别组合 |
| 年份覆盖（1980-2000） | 20 | 覆盖不同年份的节气数据 |
| 边界情况 | 13 | 节气边界、起运年龄边界 |
| 流年吉凶 | 25 | 双用神/双忌神/中性/自刑/冲合 |

---

## 八、实施计划

### 8.1 第一阶段：数据库迁移 + 模型更新（0.5天）
- 执行迁移 004/005/006
- 更新 usage_log.py 模型
- 创建 eval_report_log.py 和 eval_snapshot.py

### 8.2 第二阶段：补充检测器（2天）
- 创建 logic_checker.py
- 创建 consistency_checker.py
- 创建 safety_checker.py

### 8.3 第三阶段：L2格式错误采集 + 测试（1天）
- 修改 followup_structured.py 采集 format_error
- 创建 test_format_error_capture.py 并运行验证

### 8.4 第四阶段：扩充测试数据集（3天）
- 生成78个测试用例

### 8.5 第五阶段：评测快照 + 迭代对比（1.5天）
- 实现 eval_snapshot 生成逻辑
- 实现迭代对比 API 和前端页面

### 8.6 第六阶段：集成与验证（1天）
- 更新 run_eval.py 集成所有检测器
- 运行完整评测
- 生成评测报告

---

## 九、评测报告与迭代对比

### 9.1 两个表的用途区分

| 表名 | 用途 | 写入时机 | 数据性质 |
|------|------|----------|----------|
| `eval_report_logs` | 生产环境实时监控 | 每次用户生成报告后自动写入 | 累计的线上数据，用于监控L1-L4趋势 |
| `eval_snapshots` | 迭代前后对比 | 每次运行评测脚本时手动创建 | 独立的评测快照，用于版本对比 |

**关键区别**：
- `eval_report_logs`：记录线上真实用户的报告质量，是**持续积累**的
- `eval_snapshots`：记录某次评测的完整结果，是**独立快照**，用于对比

### 9.2 迭代对比工作流

```
迭代前：
  1. 运行 run_eval.py（78个用例）
  2. 调用 create_eval_snapshot("v1.0-初始版") → 快照A
  3. 快照A包含：通过率80%、各用例结果、违规分布

修改代码（迭代）

迭代后：
  1. 再次运行 run_eval.py（同样的78个用例）
  2. 调用 create_eval_snapshot("v1.1-修复凶年标签") → 快照B
  3. 快照B包含：通过率90%、各用例结果、违规分布

对比（快照A vs 快照B）：
  - 总览：通过率从80%→90%（+10%）
  - 分层：L2格式完成率从85%→95%（+10%）
  - 违规：凶年启动从12次→2次（-10次）
  - 用例：chart_023、chart_045从失败→通过（改进）
  - 回归：无（没有从通过→失败的用例）
```

### 9.3 评测快照生成

快照生成逻辑已在3.5节完整定义，核心函数：
- `create_eval_snapshot(name, description, eval_results)` - 创建快照
- `_calculate_task_completion_rate_from_results(eval_results)` - 基于该次评测计算L1-L4
- `_calculate_dimension_stats(eval_results)` - 计算各维度通过率
- `_calculate_violation_distribution(eval_results)` - 统计违规分布

### 9.4 迭代对比 API

**文件**：`backend/app/api/eval.py`（追加）

```python
from fastapi import APIRouter, Query
from app.models.eval_snapshot import EvalSnapshot
from app.database import SessionLocal

router = APIRouter()

@router.get("/api/admin/eval/snapshots")
async def list_snapshots(
    limit: int = Query(default=20, description="返回数量"),
):
    """获取评测快照列表"""
    db = SessionLocal()
    try:
        snapshots = db.query(EvalSnapshot).order_by(
            EvalSnapshot.created_at.desc()
        ).limit(limit).all()
        
        return {
            "success": True,
            "data": [{
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "git_commit": s.git_commit,
                "pass_rate": s.pass_rate,
                "avg_soft_score": s.avg_soft_score,
                "total_cases": s.total_cases,
                "passed_cases": s.passed_cases,
                "task_completion_rate": s.task_completion_rate,
                "created_at": s.created_at.isoformat(),
            } for s in snapshots]
        }
    finally:
        db.close()


@router.get("/api/admin/eval/compare")
async def compare_snapshots(
    baseline_id: int = Query(description="基准快照ID（迭代前）"),
    current_id: int = Query(description="对比快照ID（迭代后）"),
):
    """对比两次迭代的评测结果"""
    db = SessionLocal()
    try:
        baseline = db.query(EvalSnapshot).get(baseline_id)
        current = db.query(EvalSnapshot).get(current_id)
        
        if not baseline or not current:
            return {"success": False, "message": "快照不存在"}
        
        # 计算各指标的变化
        comparison = {
            "baseline": {
                "name": baseline.name,
                "git_commit": baseline.git_commit,
                "created_at": baseline.created_at.isoformat(),
            },
            "current": {
                "name": current.name,
                "git_commit": current.git_commit,
                "created_at": current.created_at.isoformat(),
            },
            "metrics": {
                "pass_rate": {
                    "baseline": baseline.pass_rate,
                    "current": current.pass_rate,
                    "delta": round(current.pass_rate - baseline.pass_rate, 4),
                    "trend": "up" if current.pass_rate > baseline.pass_rate 
                             else "down" if current.pass_rate < baseline.pass_rate else "flat",
                },
                "avg_soft_score": {
                    "baseline": baseline.avg_soft_score,
                    "current": current.avg_soft_score,
                    "delta": round((current.avg_soft_score or 0) - (baseline.avg_soft_score or 0), 2),
                    "trend": "up" if (current.avg_soft_score or 0) > (baseline.avg_soft_score or 0)
                             else "down" if (current.avg_soft_score or 0) < (baseline.avg_soft_score or 0) else "flat",
                },
                "task_completion_rate": _compare_task_rates(
                    baseline.task_completion_rate, current.task_completion_rate
                ),
                "dimension_pass_rates": _compare_dimensions(
                    baseline.dimension_pass_rates, current.dimension_pass_rates
                ),
            },
            "violation_changes": _compare_violations(
                baseline.violation_distribution, current.violation_distribution
            ),
            "newly_passing": _find_newly_passing(baseline.results, current.results),
            "newly_failing": _find_newly_failing(baseline.results, current.results),
        }
        
        return {"success": True, "data": comparison}
    finally:
        db.close()


def _compare_task_rates(baseline: dict, current: dict) -> dict:
    """对比任务完成率各层级"""
    if not baseline or not current:
        return {}
    
    result = {}
    for key in ["l1_technical", "l2_format", "l3_quality", "l4_satisfaction", "overall"]:
        b = baseline.get(key, 0)
        c = current.get(key, 0)
        result[key] = {
            "baseline": b,
            "current": c,
            "delta": round(c - b, 4),
            "trend": "up" if c > b else "down" if c < b else "flat",
        }
    return result


def _compare_dimensions(baseline: dict, current: dict) -> dict:
    """对比各维度通过率"""
    if not baseline or not current:
        return {}
    
    all_dims = set(list(baseline.keys()) + list(current.keys()))
    result = {}
    for dim in all_dims:
        b = baseline.get(dim, 0)
        c = current.get(dim, 0)
        result[dim] = {
            "baseline": b,
            "current": c,
            "delta": round(c - b, 4),
            "trend": "up" if c > b else "down" if c < b else "flat",
        }
    return result


def _compare_violations(baseline: dict, current: dict) -> dict:
    """对比违规分布变化"""
    if not baseline:
        baseline = {}
    if not current:
        current = {}
    
    all_rules = set(list(baseline.keys()) + list(current.keys()))
    changes = {}
    for rule in all_rules:
        b = baseline.get(rule, 0)
        c = current.get(rule, 0)
        if b != c:
            changes[rule] = {
                "baseline": b,
                "current": c,
                "delta": c - b,
                "trend": "improved" if c < b else "worsened" if c > b else "unchanged",
            }
    return changes


def _find_newly_passing(baseline_results: list, current_results: list) -> list:
    """找出迭代后新通过的用例"""
    if not baseline_results or not current_results:
        return []
    
    baseline_pass = {r["id"] for r in baseline_results if r.get("overall_pass")}
    current_pass = {r["id"] for r in current_results if r.get("overall_pass")}
    
    newly_passing = current_pass - baseline_pass
    return list(newly_passing)


def _find_newly_failing(baseline_results: list, current_results: list) -> list:
    """找出迭代后新失败的用例（回归）"""
    if not baseline_results or not current_results:
        return []
    
    baseline_pass = {r["id"] for r in baseline_results if r.get("overall_pass")}
    current_pass = {r["id"] for r in current_results if r.get("overall_pass")}
    
    newly_failing = baseline_pass - current_pass
    return list(newly_failing)
```

### 9.5 迭代对比前端页面

**文件**：`frontend/src/pages/admin/EvalCompare.tsx`

```tsx
import { useState, useEffect } from 'react';
import { Card, Table, Tag, Select, Row, Col, Statistic, Typography } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined } from '@ant-design/icons';

const { Title } = Typography;

function TrendTag({ delta, trend }: { delta: number; trend: string }) {
  if (trend === 'up' || trend === 'improved') {
    return <Tag color="green" icon={<ArrowUpOutlined />}>+{delta}</Tag>;
  }
  if (trend === 'down' || trend === 'worsened') {
    return <Tag color="red" icon={<ArrowDownOutlined />}>{delta}</Tag>;
  }
  return <Tag icon={<MinusOutlined />}>0</Tag>;
}

function EvalCompare() {
  const [snapshots, setSnapshots] = useState([]);
  const [baselineId, setBaselineId] = useState<number | null>(null);
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [comparison, setComparison] = useState<any>(null);

  useEffect(() => {
    fetch('/api/admin/eval/snapshots?limit=50')
      .then(r => r.json())
      .then(d => setSnapshots(d.data));
  }, []);

  useEffect(() => {
    if (baselineId && currentId) {
      fetch(`/api/admin/eval/compare?baseline_id=${baselineId}&current_id=${currentId}`)
        .then(r => r.json())
        .then(d => d.success && setComparison(d.data));
    }
  }, [baselineId, currentId]);

  const snapshotOptions = snapshots.map((s: any) => ({
    label: `${s.name} (${s.created_at?.slice(0, 10)})`,
    value: s.id,
  }));

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>迭代对比报告</Title>
      
      {/* 选择器 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card title="基准版本（迭代前）">
            <Select
              style={{ width: '100%' }}
              placeholder="选择基准快照"
              options={snapshotOptions}
              onChange={setBaselineId}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="对比版本（迭代后）">
            <Select
              style={{ width: '100%' }}
              placeholder="选择对比快照"
              options={snapshotOptions}
              onChange={setCurrentId}
            />
          </Card>
        </Col>
      </Row>

      {comparison && (
        <>
          {/* 总览 */}
          <Card title="总览" style={{ marginBottom: 16 }}>
            <Row gutter={24}>
              <Col span={8}>
                <Statistic
                  title="总通过率"
                  value={comparison.metrics.pass_rate.current * 100}
                  suffix="%"
                  precision={1}
                />
                <TrendTag 
                  delta={Math.round(comparison.metrics.pass_rate.delta * 1000) / 10}
                  trend={comparison.metrics.pass_rate.trend} 
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="平均软性评分"
                  value={comparison.metrics.avg_soft_score.current}
                  precision={1}
                />
                <TrendTag 
                  delta={comparison.metrics.avg_soft_score.delta}
                  trend={comparison.metrics.avg_soft_score.trend} 
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="综合任务完成率"
                  value={(comparison.metrics.task_completion_rate?.overall?.current || 0) * 100}
                  suffix="%"
                  precision={1}
                />
                <TrendTag 
                  delta={Math.round((comparison.metrics.task_completion_rate?.overall?.delta || 0) * 1000) / 10}
                  trend={comparison.metrics.task_completion_rate?.overall?.trend || 'flat'} 
                />
              </Col>
            </Row>
          </Card>

          {/* 任务完成率各层级对比 */}
          <Card title="任务完成率分层对比" style={{ marginBottom: 16 }}>
            <Table
              dataSource={Object.entries(comparison.metrics.task_completion_rate || {}).map(([key, val]: any) => ({
                key,
                level: { l1_technical: 'L1 技术', l2_format: 'L2 格式', l3_quality: 'L3 质量', 
                         l4_satisfaction: 'L4 满意度', overall: '综合' }[key] || key,
                baseline: `${(val.baseline * 100).toFixed(1)}%`,
                current: `${(val.current * 100).toFixed(1)}%`,
                delta: val.delta,
                trend: val.trend,
              }))}
              columns={[
                { title: '层级', dataIndex: 'level' },
                { title: '基准版本', dataIndex: 'baseline' },
                { title: '当前版本', dataIndex: 'current' },
                { title: '变化', dataIndex: 'delta', render: (v: number, row: any) => (
                  <TrendTag delta={Math.round(v * 1000) / 10} trend={row.trend} />
                )},
              ]}
              pagination={false}
              size="small"
            />
          </Card>

          {/* 各维度通过率对比 */}
          <Card title="各维度通过率对比" style={{ marginBottom: 16 }}>
            <Table
              dataSource={Object.entries(comparison.metrics.dimension_pass_rates || {}).map(([key, val]: any) => ({
                key,
                dimension: key,
                baseline: `${(val.baseline * 100).toFixed(1)}%`,
                current: `${(val.current * 100).toFixed(1)}%`,
                delta: val.delta,
                trend: val.trend,
              }))}
              columns={[
                { title: '维度', dataIndex: 'dimension' },
                { title: '基准版本', dataIndex: 'baseline' },
                { title: '当前版本', dataIndex: 'current' },
                { title: '变化', dataIndex: 'delta', render: (v: number, row: any) => (
                  <TrendTag delta={Math.round(v * 1000) / 10} trend={row.trend} />
                )},
              ]}
              pagination={false}
              size="small"
            />
          </Card>

          {/* 违规变化 */}
          <Card title="违规类型变化" style={{ marginBottom: 16 }}>
            <Table
              dataSource={Object.entries(comparison.violation_changes || {}).map(([key, val]: any) => ({
                key,
                rule: key,
                baseline: val.baseline,
                current: val.current,
                delta: val.delta,
                trend: val.trend,
              }))}
              columns={[
                { title: '违规类型', dataIndex: 'rule' },
                { title: '基准版本', dataIndex: 'baseline' },
                { title: '当前版本', dataIndex: 'current' },
                { title: '变化', dataIndex: 'delta', render: (v: number, row: any) => (
                  <TrendTag delta={v} trend={row.trend} />
                )},
              ]}
              pagination={false}
              size="small"
            />
          </Card>

          {/* 用例级别变化 */}
          <Row gutter={16}>
            <Col span={12}>
              <Card title="新通过的用例" style={{ background: '#f6ffed' }}>
                {comparison.newly_passing?.length > 0 ? (
                  <ul>{comparison.newly_passing.map((id: string) => <li key={id}>{id}</li>)}</ul>
                ) : <div style={{ color: '#999' }}>无变化</div>}
              </Card>
            </Col>
            <Col span={12}>
              <Card title="新失败的用例（回归）" style={{ background: '#fff2f0' }}>
                {comparison.newly_failing?.length > 0 ? (
                  <ul>{comparison.newly_failing.map((id: string) => <li key={id}>{id}</li>)}</ul>
                ) : <div style={{ color: '#999' }}>无回归</div>}
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
}

export default EvalCompare;
```

---

## 十、验证步骤

### 10.1 单元测试
- 为每个检测器编写单元测试
- L2格式错误捕获测试（15个case）
- 覆盖正常情况和违规情况

### 10.2 集成测试
- 运行完整评测流程
- 验证快照生成和对比功能
- 验证评测结果正确保存

### 10.3 性能测试
- 测试78个用例的完整评测耗时
- 优化LLM调用频率
- 确保评测时间在可接受范围内

---

## 十一、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| LLM评分不稳定 | 软性评分波动 | temperature=0.1，多次取平均 |
| 检测规则过于严格 | 误判增加 | 合理阈值，允许人工复核 |
| 测试数据集不全 | 覆盖率不足 | 持续补充边界用例 |
| 评测时间过长 | 用户体验差 | 异步评测，批量并行 |

---

## 十二、Badcase 加入评测集

### 12.1 目标

将 badcases 表中的违规案例纳入评测体系，通过**重新生成报告**验证迭代后同类违规是否被修复。

### 12.2 评测流程

```
1. 从 badcases 表读取已审核（reviewed >= 1）的 case
2. 获取命例出生信息（优先级：person_id > chart_fingerprint 反向匹配）
   - 如果 person_id 存在：直接通过 person_id 关联获取出生信息
   - 如果 person_id 不存在但有 chart_fingerprint：通过指纹匹配找到对应命盘
3. 将这些命例加入评测数据集
4. 重新生成报告（调用完整的生成链路）
5. 检测新报告是否还有同类违规
6. 对比迭代前后的修复率
```

### 12.3 chart_fingerprint 反向匹配

`chart_fingerprint` 存储了命盘核心特征，可用于反向定位命例：

```python
{
    "日主": "己土",
    "用神": "火",
    "忌神": "木",
    "当前大运": "癸未",
    "重点流年": "2024甲辰年(平)、2025乙巳年(吉)..."
}
```

通过"日主+用神+忌神"可以唯一确定命盘核心特征，遍历 persons 表重算命盘后对比指纹匹配。

### 12.4 与静态数据集的区别

| 维度 | 静态数据集（eval_chart_dataset.json） | Badcase 动态评测 |
|------|--------------------------------------|------------------|
| 数据来源 | 人工构造的标准测试用例 | 真实用户产生的违规案例 |
| 出生信息 | 直接包含在 JSON 中 | 通过 person_id 或 chart_fingerprint 获取 |
| 评测目标 | 验证排盘算法正确性 | 验证违规是否被修复 |
| 是否需要 expected | 需要完整的 expected 数据 | 不需要，只需检测同类违规 |
| 动态性 | 静态，手动维护 | 动态，随 badcases 表增长 |

### 12.5 violation_type 与检测器映射

| violation_type | 对应检测器 | 评测方式 |
|----------------|------------|----------|
| `术语黑名单` | narrative_checker.py | 重新生成报告后，检测是否仍包含黑名单术语 |
| `凶年启动` | logic_checker.py | 重新生成报告后，检测是否在凶年安排启动类行动 |
| `同义词对立` | logic_checker.py | 重新生成报告后，检测是否存在同义词对立 |
| `干支纪时` | logic_checker.py | 重新生成报告后，检测是否使用干支纪时写法 |
| `用神矛盾` | logic_checker.py | 重新生成报告后，检测是否存在用神逻辑矛盾 |
| `开篇一致性` | consistency_checker.py | 重新生成报告后，检测开篇-正文-总结一致性 |
| `结构违规` | structure_checker.py | 重新生成报告后，检测结构合规性 |

### 12.6 实现代码

**文件**：`backend/app/services/eval/badcase_evaluator.py`

```python
"""Badcase 评测器：通过重新生成报告验证违规是否被修复"""
import json
from typing import List, Dict, Optional
from datetime import datetime

from app.models.badcase import BadCase
from app.models.person import Person
from app.database import SessionLocal


# violation_type 与检测函数的映射
VIOLATION_CHECKERS = {
    "术语黑名单": "check_terminology_blacklist",
    "凶年启动": "check_fengnian_startup",
    "同义词对立": "check_synonym_contradiction",
    "干支纪时": "check_ganzhi_time_format",
    "用神矛盾": "check_yongshen_logic",
    "开篇一致性": "check_opening_consistency",
    "结构违规": "check_structure_compliance",
}


def get_reviewed_badcases(limit: int = 100) -> List[BadCase]:
    """获取已审核的 badcase 列表"""
    db = SessionLocal()
    try:
        return db.query(BadCase).filter(
            BadCase.reviewed >= 1,
        ).order_by(
            BadCase.created_at.desc()
        ).limit(limit).all()
    finally:
        db.close()


def get_person_birth_info(person_id: int) -> Optional[Dict]:
    """通过 person_id 获取出生信息"""
    db = SessionLocal()
    try:
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            return None
        
        return {
            "birth_date": person.birth_date,
            "birth_time": person.birth_time,
            "gender": person.gender,
            "longitude": person.longitude,
            "latitude": person.latitude,
            "location": person.location,
        }
    finally:
        db.close()


def find_person_by_fingerprint(chart_fingerprint: str) -> Optional[Dict]:
    """通过 chart_fingerprint 反向匹配命例
    
    通过"日主+用神+忌神"匹配 persons 表中对应的命盘，
    返回出生信息用于重新生成报告。
    """
    try:
        fp = json.loads(chart_fingerprint) if isinstance(chart_fingerprint, str) else chart_fingerprint
    except json.JSONDecodeError:
        return None
    
    target_日主 = fp.get("日主", "")
    target_用神 = fp.get("用神", "")
    target_忌神 = fp.get("忌神", "")
    
    if not target_日主:
        return None
    
    db = SessionLocal()
    try:
        persons = db.query(Person).filter(
            Person.birth_date.isnot(None),
            Person.birth_time.isnot(None),
        ).all()
        
        for person in persons:
            try:
                from app.skills.orchestrator import generate_full_analysis
                chart = generate_full_analysis(
                    birth_date=person.birth_date.strftime("%Y-%m-%d"),
                    birth_time=person.birth_time.strftime("%H:%M"),
                    longitude=person.longitude,
                    latitude=person.latitude,
                    gender=person.gender,
                    location=person.location or "",
                )
                
                from app.services.chart_validator import get_chart_fingerprint
                person_fp = get_chart_fingerprint(chart)
                
                if (person_fp.get("日主") == target_日主 and
                    person_fp.get("用神") == target_用神 and
                    person_fp.get("忌神") == target_忌神):
                    
                    return {
                        "birth_date": person.birth_date.strftime("%Y-%m-%d"),
                        "birth_time": person.birth_time.strftime("%H:%M"),
                        "gender": person.gender,
                        "longitude": person.longitude,
                        "latitude": person.latitude,
                        "location": person.location or "",
                    }
            except Exception:
                continue
        
        return None
    finally:
        db.close()


async def evaluate_badcase(badcase: BadCase) -> Dict:
    """评测单个 badcase
    
    流程：
    1. 获取出生信息（优先 person_id，其次 chart_fingerprint 反向匹配）
    2. 重新生成报告
    3. 检测新报告是否还有同类违规
    """
    # 1. 获取出生信息
    birth_info = None
    match_method = None
    
    if badcase.person_id:
        birth_info = get_person_birth_info(badcase.person_id)
        match_method = "person_id"
    
    if not birth_info and badcase.chart_fingerprint:
        birth_info = find_person_by_fingerprint(badcase.chart_fingerprint)
        match_method = "chart_fingerprint"
    
    if not birth_info:
        return {
            "badcase_id": badcase.id,
            "person_id": badcase.person_id,
            "violation_type": badcase.violation_type or "unknown",
            "still_violated": True,
            "fixed": False,
            "details": {"error": f"无法获取出生信息"},
        }
    
    # 2. 重新生成报告
    try:
        from app.skills.orchestrator import generate_full_analysis
        
        new_report = generate_full_analysis(
            birth_date=birth_info["birth_date"],
            birth_time=birth_info["birth_time"],
            longitude=birth_info["longitude"],
            latitude=birth_info["latitude"],
            gender=birth_info["gender"],
            location=birth_info.get("location", ""),
        )
    except Exception as e:
        return {
            "badcase_id": badcase.id,
            "person_id": badcase.person_id,
            "violation_type": badcase.violation_type or "unknown",
            "still_violated": True,
            "fixed": False,
            "details": {"error": f"报告生成失败: {str(e)}"},
        }
    
    # 3. 检测新报告是否还有同类违规
    violation_types = (badcase.violation_type or "").split(",")
    results = []
    
    for vtype in violation_types:
        vtype = vtype.strip()
        if not vtype:
            continue
        
        checker_name = VIOLATION_CHECKERS.get(vtype)
        if not checker_name:
            results.append({
                "violation_type": vtype,
                "still_violated": True,
                "fixed": False,
                "reason": f"未找到对应的检测器: {vtype}",
            })
            continue
        
        checker_func = globals().get(checker_name)
        if checker_func:
            violations = checker_func(new_report)
            results.append({
                "violation_type": vtype,
                "still_violated": len(violations) > 0,
                "fixed": len(violations) == 0,
                "violations": violations,
            })
        else:
            results.append({
                "violation_type": vtype,
                "still_violated": True,
                "fixed": False,
                "reason": f"检测函数未实现: {checker_name}",
            })
    
    all_fixed = all(r.get("fixed", False) for r in results)
    
    return {
        "badcase_id": badcase.id,
        "person_id": badcase.person_id,
        "question": badcase.question,
        "violation_type": badcase.violation_type,
        "still_violated": not all_fixed,
        "fixed": all_fixed,
        "new_report": new_report,
        "details": results,
    }


async def evaluate_all_badcases(limit: int = 100) -> Dict:
    """评测所有已审核的 badcase"""
    badcases = get_reviewed_badcases(limit)
    
    results = []
    for badcase in badcases:
        result = await evaluate_badcase(badcase)
        results.append(result)
    
    total = len(results)
    fixed = sum(1 for r in results if r.get("fixed"))
    still_violated = total - fixed
    fix_rate = fixed / total if total > 0 else 0
    
    return {
        "total": total,
        "fixed": fixed,
        "still_violated": still_violated,
        "fix_rate": round(fix_rate, 4),
        "results": results,
    }


# ============ 检测函数实现 ============

def check_terminology_blacklist(data: dict) -> List[Dict]:
    from app.services.eval.narrative_checker import check_terminology
    return check_terminology(data)

def check_fengnian_startup(data: dict) -> List[Dict]:
    from app.services.eval.logic_checker import check_fengnian_startup
    return check_fengnian_startup(data)

def check_synonym_contradiction(data: dict) -> List[Dict]:
    from app.services.eval.logic_checker import check_synonym_contradiction
    return check_synonym_contradiction(data)

def check_ganzhi_time_format(data: dict) -> List[Dict]:
    from app.services.eval.logic_checker import check_ganzhi_time_format
    return check_ganzhi_time_format(data)

def check_yongshen_logic(data: dict) -> List[Dict]:
    from app.services.eval.logic_checker import check_yongshen_logic
    return check_yongshen_logic(data)

def check_opening_consistency(data: dict) -> List[Dict]:
    from app.services.eval.consistency_checker import check_opening_consistency
    return check_opening_consistency(data)

def check_structure_compliance(data: dict) -> List[Dict]:
    from app.services.eval.structure_checker import check_structure
    return check_structure(data)
```

### 12.7 集成到评测快照

在 `snapshot_service.py` 的 `create_eval_snapshot` 中增加 badcase 评测：

```python
async def create_eval_snapshot(
    name: str,
    description: str = "",
    eval_results: List[Dict] = None,
    include_badcases: bool = True,  # 新增参数
) -> Dict:
    # ... 原有逻辑 ...
    
    badcase_results = None
    if include_badcases:
        from app.services.eval.badcase_evaluator import evaluate_all_badcases
        badcase_results = await evaluate_all_badcases()
    
    # 保存 badcase_results 到 EvalSnapshot
```

### 12.8 数据库迁移

**文件**：`backend/alembic/versions/007_add_badcase_results_to_snapshots.py`

```python
def upgrade() -> None:
    op.add_column(
        'eval_snapshots',
        sa.Column('badcase_results', sa.JSON(), nullable=True,
                  comment='badcase评测结果: {"total":50,"fixed":30,"fix_rate":0.6,...}')
    )
```

### 12.9 迭代对比 API 扩展

在 `compare_snapshots` 接口中增加 badcase 修复率对比：

```python
def _compare_badcase_fix_rate(baseline: dict, current: dict) -> dict:
    """对比 badcase 修复率"""
    if not baseline and not current:
        return None
    
    b_rate = (baseline or {}).get("fix_rate", 0)
    c_rate = (current or {}).get("fix_rate", 0)
    
    return {
        "baseline": {
            "total": (baseline or {}).get("total", 0),
            "fixed": (baseline or {}).get("fixed", 0),
            "fix_rate": b_rate,
        },
        "current": {
            "total": (current or {}).get("total", 0),
            "fixed": (current or {}).get("fixed", 0),
            "fix_rate": c_rate,
        },
        "delta": round(c_rate - b_rate, 4),
        "trend": "up" if c_rate > b_rate else "down" if c_rate < b_rate else "flat",
    }
```

### 12.10 前端展示扩展

在对比页面增加 badcase 修复率展示：

```tsx
{/* Badcase 修复率对比 */}
{comparison.badcase_fix_rate && (
  <Card title="Badcase 修复率" style={{ marginBottom: 16 }}>
    <Row gutter={24}>
      <Col span={8}>
        <Statistic
          title="基准版本修复率"
          value={(comparison.badcase_fix_rate.baseline.fix_rate * 100).toFixed(1)}
          suffix="%"
          precision={1}
        />
        <div style={{ color: '#666', fontSize: 12 }}>
          共 {comparison.badcase_fix_rate.baseline.total} 个，已修复 {comparison.badcase_fix_rate.baseline.fixed} 个
        </div>
      </Col>
      <Col span={8}>
        <Statistic
          title="当前版本修复率"
          value={(comparison.badcase_fix_rate.current.fix_rate * 100).toFixed(1)}
          suffix="%"
          precision={1}
        />
        <div style={{ color: '#666', fontSize: 12 }}>
          共 {comparison.badcase_fix_rate.current.total} 个，已修复 {comparison.badcase_fix_rate.current.fixed} 个
        </div>
      </Col>
      <Col span={8}>
        <Statistic
          title="修复率变化"
          value={(comparison.badcase_fix_rate.delta * 100).toFixed(1)}
          suffix="%"
          precision={1}
          valueStyle={{ 
            color: comparison.badcase_fix_rate.delta > 0 ? '#3f8600' : 
                   comparison.badcase_fix_rate.delta < 0 ? '#cf1322' : '#000' 
          }}
        />
      </Col>
    </Row>
  </Card>
)}
```

### 12.11 Badcase 评测流程

```
1. 用户生成报告 → 检测违规 → 重试仍违规 → 写入 badcases 表
                                              ↓
2. 人工审核 badcases → 标记 reviewed=1（已审核）
                                              ↓
3. 迭代前：运行评测 → 重新生成报告 → 生成快照A（包含 badcase 评测结果）
                                              ↓
4. 修改代码（修复违规问题）
                                              ↓
5. 迭代后：运行评测 → 重新生成报告 → 生成快照B（包含 badcase 评测结果）
                                              ↓
6. 对比快照A vs 快照B → 查看 badcase 修复率变化
```

---

## 十三、总结

本方案构建了一个完整的AI测评标准实践案例：

1. **双指标体系**：任务完成率（L1-L4分层）+ 正确率（5维度加权）
2. **7个检测维度**：排盘正确性、结构合规性、术语合规性、数据真实性、命理逻辑一致性、内容一致性、内容安全性
3. **两层评分**：硬性检查Pass/Fail + 软性质量评分0-100
4. **78个测试用例**：覆盖10日主、2性别、20年份、13边界、25流年吉凶
5. **15个格式错误测试**：覆盖JSON解析失败和Pydantic校验失败的各种场景
6. **3张新表**：eval_report_logs（评测日志）、eval_snapshots（评测快照）、ai_usage_logs新增format_error字段
7. **迭代对比报告**：快照机制 + 对比API + 前端可视化，支持迭代前后的全维度对比
8. **迭代闭环**：自动化迭代 + 人工迭代 + 混合迭代
9. **Badcase 评测**：通过 person_id 或 chart_fingerprint 反向匹配命例，重新生成报告验证违规是否被修复
