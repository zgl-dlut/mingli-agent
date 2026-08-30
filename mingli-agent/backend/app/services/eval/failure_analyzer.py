"""
失败模式分析脚本
用于分析生产监控数据中的高频违规模式，提供改进建议
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import Counter, defaultdict
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eval_result import EvalResult


async def analyze_failure_patterns(
    db: AsyncSession,
    days: int = 7,
    min_occurrences: int = 2
) -> Dict[str, Any]:
    """
    分析最近 N 天的生产监控数据，识别高频违规模式
    
    Args:
        db: 数据库会话
        days: 分析最近多少天的数据
        min_occurrences: 最少出现次数阈值
    
    Returns:
        分析报告，包含违规分布、高频模式、改进建议
    """
    # 计算时间范围
    start_time = datetime.now() - timedelta(days=days)
    
    # 查询生产监控数据
    stmt = select(EvalResult).where(
        and_(
            EvalResult.eval_type == 'production_monitor',
            EvalResult.created_at >= start_time
        )
    )
    result = await db.execute(stmt)
    monitor_results = result.scalars().all()
    
    if not monitor_results:
        return {
            "total_reports": 0,
            "llm_evaluated": 0,
            "passed": 0,
            "failed": 0,
            "violation_distribution": {},
            "high_frequency_patterns": [],
            "root_cause_distribution": {},
            "improvement_suggestions": [],
        }
    
    # 统计基础数据
    total_reports = len(monitor_results)
    llm_evaluated = 0
    passed = 0
    failed = 0
    
    # 违规统计
    violation_counter = Counter()
    violation_details = defaultdict(list)
    
    # 归因统计
    root_cause_counter = Counter()
    root_cause_examples = defaultdict(list)
    
    # 触发原因统计
    trigger_reason_counter = Counter()
    
    # 分析每条记录
    for monitor in monitor_results:
        detail = json.loads(monitor.detail) if monitor.detail else []
        if not detail or not isinstance(detail, list):
            continue
        
        monitor_detail = detail[0]
        eval_result = monitor_detail.get("eval_result", {})
        trigger_reason = monitor_detail.get("trigger_reason", "unknown")
        trigger_reason_counter[trigger_reason] += 1
        
        # 检查是否有 LLM 评测
        if eval_result.get("passed") is not None:
            llm_evaluated += 1
            if eval_result.get("passed"):
                passed += 1
            else:
                failed += 1
                
                # 提取违规信息
                l2_format = eval_result.get("l2_format", {})
                l3_quality = eval_result.get("l3_quality", {})
                
                if l2_format.get("structure_violations", 0) > 0:
                    violation_counter["structure"] += l2_format["structure_violations"]
                    violation_details["structure"].append({
                        "id": monitor.id,
                        "question": monitor_detail.get("question_preview", ""),
                        "count": l2_format["structure_violations"],
                    })
                
                if l2_format.get("narrative_violations", 0) > 0:
                    violation_counter["narrative"] += l2_format["narrative_violations"]
                    violation_details["narrative"].append({
                        "id": monitor.id,
                        "question": monitor_detail.get("question_preview", ""),
                        "count": l2_format["narrative_violations"],
                    })
                
                if l2_format.get("chart_usage_violations", 0) > 0:
                    violation_counter["chart_usage"] += l2_format["chart_usage_violations"]
                    violation_details["chart_usage"].append({
                        "id": monitor.id,
                        "question": monitor_detail.get("question_preview", ""),
                        "count": l2_format["chart_usage_violations"],
                    })
                
                # 检查 LLM 软性评分
                if eval_result.get("avg_soft_score") is not None and eval_result["avg_soft_score"] < 3.5:
                    violation_counter["low_soft_score"] += 1
                    violation_details["low_soft_score"].append({
                        "id": monitor.id,
                        "question": monitor_detail.get("question_preview", ""),
                        "score": eval_result["avg_soft_score"],
                    })
                
                # 检查编造
                if eval_result.get("fabrication", {}).get("编造"):
                    violation_counter["fabrication"] += 1
                    violation_details["fabrication"].append({
                        "id": monitor.id,
                        "question": monitor_detail.get("question_preview", ""),
                    })
        
        # 提取归因信息
        root_cause = monitor_detail.get("root_cause", {})
        if root_cause and root_cause.get("category"):
            category = root_cause["category"]
            root_cause_counter[category] += 1
            root_cause_examples[category].append({
                "id": monitor.id,
                "note": root_cause.get("note", ""),
                "question": monitor_detail.get("question_preview", ""),
            })
    
    # 识别高频模式
    high_frequency_patterns = []
    for violation_type, count in violation_counter.most_common():
        if count >= min_occurrences:
            examples = violation_details[violation_type][:3]  # 最多显示 3 个示例
            high_frequency_patterns.append({
                "type": violation_type,
                "count": count,
                "percentage": round(count / total_reports * 100, 1),
                "examples": examples,
            })
    
    # 生成改进建议
    improvement_suggestions = []
    
    if violation_counter.get("structure", 0) > total_reports * 0.2:
        improvement_suggestions.append({
            "priority": "high",
            "category": "结构问题",
            "issue": f"结构违规占比过高 ({violation_counter['structure']} 次，{round(violation_counter['structure']/total_reports*100, 1)}%)",
            "suggestion": "检查 prompt 中的结构要求是否清晰，考虑在 prompt 中明确列出必须回答的子问题",
            "action_type": "prompt_issue",
        })
    
    if violation_counter.get("narrative", 0) > total_reports * 0.15:
        improvement_suggestions.append({
            "priority": "high",
            "category": "叙事问题",
            "issue": f"叙事违规占比过高 ({violation_counter['narrative']} 次，{round(violation_counter['narrative']/total_reports*100, 1)}%)",
            "suggestion": "检查术语黑名单是否完整，考虑在 prompt 中增加更明确的术语使用规范",
            "action_type": "prompt_issue",
        })
    
    if violation_counter.get("chart_usage", 0) > total_reports * 0.1:
        improvement_suggestions.append({
            "priority": "medium",
            "category": "命盘使用问题",
            "issue": f"命盘使用违规 ({violation_counter['chart_usage']} 次，{round(violation_counter['chart_usage']/total_reports*100, 1)}%)",
            "suggestion": "检查 chart_data 传递是否正确，考虑在 prompt 中强调必须基于命盘数据进行分析",
            "action_type": "code_bug",
        })
    
    if violation_counter.get("fabrication", 0) > total_reports * 0.05:
        improvement_suggestions.append({
            "priority": "high",
            "category": "编造问题",
            "issue": f"发现编造 ({violation_counter['fabrication']} 次，{round(violation_counter['fabrication']/total_reports*100, 1)}%)",
            "suggestion": "在 prompt 中明确禁止编造命盘未提供的信息，考虑增加编造检测的惩罚机制",
            "action_type": "prompt_issue",
        })
    
    if violation_counter.get("low_soft_score", 0) > total_reports * 0.3:
        improvement_suggestions.append({
            "priority": "medium",
            "category": "软性评分低",
            "issue": f"LLM 软性评分普遍偏低 ({violation_counter['low_soft_score']} 次，{round(violation_counter['low_soft_score']/total_reports*100, 1)}%)",
            "suggestion": "考虑优化 prompt 的叙事性要求，或调整 LLM 评分标准",
            "action_type": "prompt_issue",
        })
    
    # 基于归因的建议
    if root_cause_counter.get("prompt_issue", 0) > 5:
        improvement_suggestions.append({
            "priority": "high",
            "category": "Prompt 问题",
            "issue": f"已标注 {root_cause_counter['prompt_issue']} 个问题为 Prompt 问题",
            "suggestion": "系统性审查和优化 prompt，参考已标注的案例进行改进",
            "action_type": "prompt_issue",
            "examples": root_cause_examples["prompt_issue"][:3],
        })
    
    if root_cause_counter.get("code_bug", 0) > 3:
        improvement_suggestions.append({
            "priority": "high",
            "category": "代码 Bug",
            "issue": f"已标注 {root_cause_counter['code_bug']} 个问题为代码 Bug",
            "suggestion": "优先修复这些代码问题，参考已标注的案例进行排查",
            "action_type": "code_bug",
            "examples": root_cause_examples["code_bug"][:3],
        })
    
    if root_cause_counter.get("rule_too_strict", 0) > 3:
        improvement_suggestions.append({
            "priority": "medium",
            "category": "规则过严",
            "issue": f"已标注 {root_cause_counter['rule_too_strict']} 个问题为评测规则过严",
            "suggestion": "审查评测规则，考虑放宽某些阈值或调整检查逻辑",
            "action_type": "rule_too_strict",
            "examples": root_cause_examples["rule_too_strict"][:3],
        })
    
    return {
        "total_reports": total_reports,
        "llm_evaluated": llm_evaluated,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / llm_evaluated * 100, 1) if llm_evaluated > 0 else 0,
        "violation_distribution": dict(violation_counter.most_common()),
        "high_frequency_patterns": high_frequency_patterns,
        "root_cause_distribution": dict(root_cause_counter.most_common()),
        "trigger_reason_distribution": dict(trigger_reason_counter.most_common()),
        "improvement_suggestions": improvement_suggestions,
        "analysis_period_days": days,
    }


async def get_failure_analysis_report(db: AsyncSession, days: int = 7) -> str:
    """
    生成可读的失败分析报告
    
    Args:
        db: 数据库会话
        days: 分析最近多少天的数据
    
    Returns:
        格式化的报告文本
    """
    analysis = await analyze_failure_patterns(db, days)
    
    if analysis["total_reports"] == 0:
        return f"最近 {days} 天没有生产监控数据"
    
    report_lines = [
        f"📊 生产监控失败模式分析报告（最近 {days} 天）",
        "=" * 60,
        "",
        f"📈 基础统计",
        f"  总报告数: {analysis['total_reports']}",
        f"  LLM 评测数: {analysis['llm_evaluated']}",
        f"  通过数: {analysis['passed']}",
        f"  失败数: {analysis['failed']}",
        f"  通过率: {analysis['pass_rate']}%",
        "",
    ]
    
    if analysis["high_frequency_patterns"]:
        report_lines.extend([
            "🔍 高频违规模式",
            "-" * 60,
        ])
        for pattern in analysis["high_frequency_patterns"]:
            report_lines.extend([
                f"  [{pattern['type']}] 出现 {pattern['count']} 次 ({pattern['percentage']}%)",
            ])
            for i, example in enumerate(pattern["examples"][:2], 1):
                question = example.get("question", "")[:40]
                report_lines.append(f"    示例 {i}: {question}...")
            report_lines.append("")
    
    if analysis["root_cause_distribution"]:
        report_lines.extend([
            "🎯 问题归因分布",
            "-" * 60,
        ])
        category_map = {
            "prompt_issue": "Prompt 问题",
            "code_bug": "代码 Bug",
            "rule_too_strict": "规则过严",
            "edge_case": "边界情况",
        }
        for category, count in analysis["root_cause_distribution"].items():
            category_name = category_map.get(category, category)
            report_lines.append(f"  {category_name}: {count} 次")
        report_lines.append("")
    
    if analysis["improvement_suggestions"]:
        report_lines.extend([
            "💡 改进建议",
            "-" * 60,
        ])
        for i, suggestion in enumerate(analysis["improvement_suggestions"], 1):
            priority_icon = "🔴" if suggestion["priority"] == "high" else "🟡"
            report_lines.extend([
                f"  {priority_icon} {i}. [{suggestion['category']}] {suggestion['issue']}",
                f"     建议: {suggestion['suggestion']}",
                f"     行动类型: {suggestion['action_type']}",
                "",
            ])
    
    return "\n".join(report_lines)
