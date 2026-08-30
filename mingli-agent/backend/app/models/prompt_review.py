"""人工审核记录数据模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from app.db.base import Base
from datetime import datetime


class PromptReview(Base):
    """人工审核记录"""
    __tablename__ = "prompt_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    eval_result_id = Column(Integer, comment="关联的评测结果ID")
    badcase_id = Column(Integer, comment="关联的 badcase ID")
    report_data = Column(Text, comment="报告 JSON")
    user_question = Column(Text, comment="用户问题")
    reviewer_id = Column(Integer, comment="审核人 ID")
    review_result = Column(String(20), comment="审核结果: pass/improve/fail")
    review_comment = Column(Text, comment="审核意见")
    problem_tags = Column(JSON, comment="问题标签: ['跑题', '术语堆砌', '编造']")
    auto_add_to_dataset = Column(Integer, default=0, comment="是否自动加入评测集")
    created_at = Column(DateTime, default=datetime.utcnow)


class PromptVersion(Base):
    """Prompt 版本记录"""
    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), comment="版本号")
    prompt_content = Column(Text, comment="完整 prompt 内容")
    change_summary = Column(Text, comment="变更摘要")
    changed_rules = Column(JSON, comment="变更的规则列表")
    related_badcases = Column(JSON, comment="关联的 badcase ID 列表")
    created_by = Column(String(50), comment="创建人")
    created_at = Column(DateTime, default=datetime.utcnow)
