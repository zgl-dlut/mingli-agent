"""
FollowupReport Pydantic 模型校验单元测试

覆盖合法输入、缺少必填字段、discriminator分发、枚举校验、空数组等
共 13 个 case
"""
import sys
import os
import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.schemas.report_schema import FollowupReport


class TestFollowupReportValidation:
    """Pydantic 模型校验测试集"""

    # ============================================================
    # 合法输入
    # ============================================================

    def test_valid_full_report(self):
        """① 合法JSON，所有字段齐全，通过校验"""
        data = {
            "opening": {"lead": "测试lead", "verdict": "测试verdict"},
            "subtopics": [
                {"title": "子问题1", "blocks": [
                    {"type": "keyword", "keyword": "关键词", "narrative": "描述"}
                ]}
            ],
            "summary": {"title": "总结", "items": [{"keyword": "阶段", "text": "描述"}]},
        }
        report = FollowupReport.model_validate(data)
        assert report.opening.lead == "测试lead"
        assert len(report.subtopics) == 1

    def test_opening_only_lead(self):
        """② opening只有lead没有verdict（两字段都可选）"""
        data = {
            "opening": {"lead": "只有lead"},
            "subtopics": [],
            "summary": {"title": "总结"},
        }
        report = FollowupReport.model_validate(data)
        assert report.opening.lead == "只有lead"
        assert report.opening.verdict is None

    def test_opening_only_verdict(self):
        """③ opening只有verdict没有lead"""
        data = {
            "opening": {"verdict": "只有verdict"},
            "subtopics": [],
            "summary": {"title": "总结"},
        }
        report = FollowupReport.model_validate(data)
        assert report.opening.verdict == "只有verdict"
        assert report.opening.lead is None

    # ============================================================
    # 缺少必填字段
    # ============================================================

    def test_missing_opening(self):
        """④ 缺少opening"""
        with pytest.raises(ValidationError):
            FollowupReport.model_validate({"subtopics": [], "summary": {"title": "x"}})

    def test_missing_subtopics(self):
        """⑤ 缺少subtopics"""
        with pytest.raises(ValidationError):
            FollowupReport.model_validate({"opening": {}, "summary": {"title": "x"}})

    def test_missing_summary(self):
        """⑥ 缺少summary"""
        with pytest.raises(ValidationError):
            FollowupReport.model_validate({"opening": {}, "subtopics": []})

    def test_empty_subtopics_array(self):
        """⑦ subtopics为空数组（合法但业务上无意义）"""
        data = {"opening": {}, "subtopics": [], "summary": {"title": "x"}}
        report = FollowupReport.model_validate(data)
        assert len(report.subtopics) == 0

    # ============================================================
    # blocks discriminator 分发
    # ============================================================

    def test_keyword_block(self):
        """⑧ type=keyword正确解析"""
        data = {
            "opening": {},
            "subtopics": [{"title": "t", "blocks": [
                {"type": "keyword", "keyword": "kw", "narrative": "desc",
                 "term_explain": "解释", "sub_items": ["点1", "点2"]}
            ]}],
            "summary": {"title": "s"},
        }
        report = FollowupReport.model_validate(data)
        block = report.subtopics[0].blocks[0]
        assert block.type == "keyword"
        assert block.keyword == "kw"
        assert block.term_explain == "解释"
        assert len(block.sub_items) == 2

    def test_narrative_block(self):
        """⑨ type=narrative正确解析"""
        data = {
            "opening": {},
            "subtopics": [{"title": "t", "blocks": [
                {"type": "narrative", "text": "纯叙事"}
            ]}],
            "summary": {"title": "s"},
        }
        report = FollowupReport.model_validate(data)
        assert report.subtopics[0].blocks[0].text == "纯叙事"

    def test_group_block(self):
        """⑩ type=group正确解析"""
        data = {
            "opening": {},
            "subtopics": [{"title": "t", "blocks": [
                {"type": "group", "title": "组标题", "paragraphs": ["段1", "段2"]}
            ]}],
            "summary": {"title": "s"},
        }
        report = FollowupReport.model_validate(data)
        block = report.subtopics[0].blocks[0]
        assert block.title == "组标题"
        assert len(block.paragraphs) == 2

    def test_unknown_block_type(self):
        """⑪ type为未知值，discriminator报错"""
        data = {
            "opening": {},
            "subtopics": [{"title": "t", "blocks": [
                {"type": "unknown", "text": "未知类型"}
            ]}],
            "summary": {"title": "s"},
        }
        with pytest.raises(ValidationError):
            FollowupReport.model_validate(data)

    # ============================================================
    # 枚举与边界
    # ============================================================

    def test_unknown_item_format(self):
        """⑫ item_format为未知值，Literal枚举校验报错"""
        data = {
            "opening": {},
            "subtopics": [],
            "summary": {"title": "s", "items": [{"keyword": "k", "text": "t"}], "item_format": "table"},
        }
        with pytest.raises(ValidationError):
            FollowupReport.model_validate(data)

    def test_item_format_defaults_to_list(self):
        """⑬ item_format省略时默认为list"""
        data = {
            "opening": {},
            "subtopics": [],
            "summary": {"title": "s", "items": [{"keyword": "k", "text": "t"}]},
        }
        report = FollowupReport.model_validate(data)
        assert report.summary.item_format == "list"
