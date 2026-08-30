"""BadCase 数据模型：记录重试终止后仍违规的案例，供后续提炼规则注入 prompt"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db.base import Base
from datetime import datetime


class BadCase(Base):
    __tablename__ = "badcases"
    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, nullable=True, comment="关联人物ID")
    question = Column(Text, nullable=False, comment="用户问题")
    chart_fingerprint = Column(Text, comment="命盘指纹JSON")
    violation_type = Column(String(200), comment="违规类型逗号分隔")
    violation_detail = Column(Text, comment="违规详情JSON")
    raw_output = Column(Text, comment="LLM原始输出JSON（仅供审核查阅，不注入prompt）")
    retry_count = Column(Integer, default=0, comment="重试次数")
    final_status = Column(String(20), default="degraded", comment="最终状态: degraded/blocked")
    reviewed = Column(Integer, default=0, comment="审核状态: 0未审核 1已审核 2已提炼规则 3已注入")
    extracted_rule = Column(Text, comment="从该case提炼的精简规则(50-150字)，审核后填入，注入prompt规则区")
    rule_category = Column(String(50), comment="规则分类: 术语/结构/命盘数据/叙事性/时间因果")
    created_at = Column(DateTime, default=datetime.utcnow)
