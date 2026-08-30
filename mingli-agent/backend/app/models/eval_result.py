"""评测结果数据模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, JSON
from app.db.base import Base
from datetime import datetime


class EvalResult(Base):
    __tablename__ = "eval_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(100), comment="评测集批次ID")
    eval_type = Column(String(50), comment="评测类型: report_quality/chart_accuracy/badcase_eval/production_monitor")
    total = Column(Integer, comment="总测试数")
    passed = Column(Integer, comment="通过数")
    failed = Column(Integer, comment="失败数")
    pass_rate = Column(Float, comment="通过率")
    detail = Column(Text, comment="详细结果JSON")
    format_error = Column(Text, comment="L2格式完成率错误信息JSON: {'json_parse_failed':bool,'pydantic_validation_failed':bool,'error_detail':str}")
    format_pass_rate = Column(Float, comment="L2格式完成率（通过Pydantic校验的比例）")
    match_count = Column(Integer, comment="检测匹配数（预期结果与实际结果一致的数量）")
    match_rate = Column(Float, comment="检测准确率（检测匹配数/总数）")
    task_completion_rate = Column(JSON, comment="任务完成率: {l1_technical, l2_format, l3_quality, l4_satisfaction, overall}")
    accuracy_rate = Column(JSON, comment="正确率: {chart, structure, narrative, logic, consistency, safety, overall}")
    soft_score = Column(JSON, comment="软性评分: {narrative, fluency, storytelling, bold_rationality, terminology_popularization, avg}")
    violation_distribution = Column(JSON, comment="违规分布: {违规类型: 计数}")
    created_at = Column(DateTime, default=datetime.utcnow)
