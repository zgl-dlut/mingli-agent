"""评测模块：结构检查、叙事性检查、排盘正确性、命盘数据使用检查、LLM 评分器"""

from app.services.eval.structure_checker import check_structure
from app.services.eval.narrative_checker import check_narrative
from app.services.eval.chart_checker import check_chart_correctness
from app.services.eval.chart_usage_checker import check_chart_usage
from app.services.eval.llm_scorer import evaluate_report

__all__ = [
    "check_structure",
    "check_narrative",
    "check_chart_correctness",
    "check_chart_usage",
    "evaluate_report",
]
