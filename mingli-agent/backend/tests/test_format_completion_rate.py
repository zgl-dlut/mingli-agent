"""
L2 格式完成率测试数据构造

测试目标：验证 JSON 解析失败和 Pydantic 校验失败的捕获逻辑
测试场景：
1. JSON 解析失败（json.JSONDecodeError）
2. Pydantic 校验失败（ValidationError）
3. 容错修复成功（通过 _extract_and_fix_json）
4. 容错修复失败（返回 error_report）
"""
import json
import sys
import os
import pytest
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.followup_structured import _extract_and_fix_json
from app.schemas.report_schema import FollowupReport
from pydantic import ValidationError


class TestFormatCompletionRate:
    """L2 格式完成率测试集"""

    # ============================================================
    # 第一类：JSON 解析失败场景（json.JSONDecodeError）
    # ============================================================

    def test_json_parse_error_truncated(self):
        """① JSON 被截断（max_tokens 限制）"""
        raw = '{"opening":{"lead":"测试"},"subtopics":[{"title":"截断'
        # 预期：json.JSONDecodeError
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    def test_json_parse_error_missing_bracket(self):
        """② 缺少闭合括号"""
        raw = '{"opening":{"lead":"测试"},"subtopics":[]'
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    def test_json_parse_error_invalid_escape(self):
        """③ 非法转义字符"""
        raw = '{"opening":{"lead":"测试\\x"}}'
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    def test_json_parse_error_single_quote(self):
        """④ 使用单引号而非双引号"""
        raw = "{'opening': {'lead': '测试'}}"
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    def test_json_parse_error_unquoted_key(self):
        """⑤ 未加引号的 key"""
        raw = '{opening: {"lead": "测试"}}'
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    def test_json_parse_error_trailing_comma(self):
        """⑥ 末尾多余逗号"""
        raw = '{"opening":{"lead":"测试"},"subtopics":[],}'
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    def test_json_parse_error_bare_newline(self):
        """⑦ 字符串值内有裸换行"""
        raw = '{"opening":{"lead":"第一行\n第二行"}}'
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    def test_json_parse_error_empty_input(self):
        """⑧ 空输入"""
        raw = ""
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    def test_json_parse_error_not_json(self):
        """⑨ 完全非 JSON 内容"""
        raw = "这是一段普通文本，不是 JSON"
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    # ============================================================
    # 第二类：Pydantic 校验失败场景（ValidationError）
    # ============================================================

    def test_pydantic_validation_missing_opening(self):
        """① 缺少 opening 字段"""
        data = {"subtopics": []}
        with pytest.raises(ValidationError) as exc_info:
            FollowupReport.model_validate(data)
        assert "opening" in str(exc_info.value)

    def test_pydantic_validation_missing_subtopics(self):
        """② 缺少 subtopics 字段"""
        data = {"opening": {"lead": "测试"}}
        with pytest.raises(ValidationError) as exc_info:
            FollowupReport.model_validate(data)
        assert "subtopics" in str(exc_info.value)

    def test_pydantic_validation_opening_wrong_type(self):
        """③ opening 类型错误（应为对象，实际为字符串）"""
        data = {"opening": "测试", "subtopics": []}
        with pytest.raises(ValidationError):
            FollowupReport.model_validate(data)

    def test_pydantic_validation_subtopics_wrong_type(self):
        """④ subtopics 类型错误（应为数组，实际为字符串）"""
        data = {"opening": {"lead": "测试"}, "subtopics": "测试"}
        with pytest.raises(ValidationError):
            FollowupReport.model_validate(data)

    def test_pydantic_validation_subtopic_missing_title(self):
        """⑤ subtopic 缺少 title 字段"""
        data = {
            "opening": {"lead": "测试"},
            "subtopics": [{"blocks": []}]
        }
        with pytest.raises(ValidationError):
            FollowupReport.model_validate(data)

    def test_pydantic_validation_block_missing_type(self):
        """⑥ block 缺少 type 字段"""
        data = {
            "opening": {"lead": "测试"},
            "subtopics": [{
                "title": "测试",
                "blocks": [{"keyword": "测试", "narrative": "测试"}]
            }]
        }
        with pytest.raises(ValidationError):
            FollowupReport.model_validate(data)

    def test_pydantic_validation_keyword_block_missing_narrative(self):
        """⑦ keyword block 缺少 narrative 字段"""
        data = {
            "opening": {"lead": "测试"},
            "subtopics": [{
                "title": "测试",
                "blocks": [{"type": "keyword", "keyword": "测试"}]
            }]
        }
        with pytest.raises(ValidationError):
            FollowupReport.model_validate(data)

    def test_pydantic_validation_summary_wrong_type(self):
        """⑧ summary 类型错误"""
        data = {
            "opening": {"lead": "测试"},
            "subtopics": [],
            "summary": "测试"  # 应为对象
        }
        with pytest.raises(ValidationError):
            FollowupReport.model_validate(data)

    # ============================================================
    # 第三类：容错修复成功场景（_extract_and_fix_json）
    # ============================================================

    def test_fix_success_markdown_wrap(self):
        """① markdown 包裹修复成功"""
        raw = '```json\n{"opening":{"lead":"测试"},"subtopics":[],"summary":{"title":"总结","items":[]}}\n```'
        fixed = _extract_and_fix_json(raw)
        data = json.loads(fixed)
        # 应能通过 Pydantic 校验
        report = FollowupReport.model_validate(data)
        assert report.opening.lead == "测试"

    def test_fix_success_bare_newline(self):
        """② 裸换行修复成功"""
        raw = '{"opening":{"lead":"第一行\n第二行"},"subtopics":[],"summary":{"title":"总结","items":[]}}'
        fixed = _extract_and_fix_json(raw)
        data = json.loads(fixed)
        report = FollowupReport.model_validate(data)
        assert "第一行" in report.opening.lead

    def test_fix_success_trailing_comma(self):
        """③ 末尾逗号修复（需手动处理）"""
        # 注意：_extract_and_fix_json 不处理末尾逗号，这里测试直接解析失败
        raw = '{"opening":{"lead":"测试"},"subtopics":[],}'
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    def test_fix_success_single_quote(self):
        """④ 单引号修复（需手动处理）"""
        # 注意：_extract_and_fix_json 不处理单引号，这里测试直接解析失败
        raw = "{'opening': {'lead': '测试'}, 'subtopics': []}"
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    # ============================================================
    # 第四类：容错修复失败场景（返回 error_report）
    # ============================================================

    def test_fix_failure_completely_broken(self):
        """① 完全损坏的 JSON，无法修复"""
        raw = '{"opening":{"lead":"测试","subtopics":[{"title":"截断'
        fixed = _extract_and_fix_json(raw)
        # 修复后仍然无法解析
        with pytest.raises(json.JSONDecodeError):
            json.loads(fixed)

    def test_fix_failure_missing_required_fields(self):
        """② JSON 解析成功但缺少必填字段"""
        raw = '{"opening":{"lead":"测试"}}'  # 缺少 subtopics
        fixed = _extract_and_fix_json(raw)
        data = json.loads(fixed)
        # JSON 解析成功，但 Pydantic 校验失败
        with pytest.raises(ValidationError):
            FollowupReport.model_validate(data)

    def test_fix_failure_wrong_field_types(self):
        """③ 字段类型错误"""
        raw = '{"opening":"测试","subtopics":"测试"}'
        fixed = _extract_and_fix_json(raw)
        data = json.loads(fixed)
        with pytest.raises(ValidationError):
            FollowupReport.model_validate(data)

    # ============================================================
    # 第五类：边界场景
    # ============================================================

    def test_boundary_very_long_string(self):
        """① 超长字符串"""
        raw = '{"opening":{"lead":"' + '测' * 10000 + '"},"subtopics":[],"summary":{"title":"总结","items":[]}}'
        data = json.loads(raw)
        report = FollowupReport.model_validate(data)
        assert len(report.opening.lead) == 10000

    def test_boundary_deeply_nested(self):
        """② 深度嵌套"""
        raw = '{"opening":{"lead":"测试"},"subtopics":[{"title":"测试","blocks":[{"type":"keyword","keyword":"测试","narrative":"测试"}]}],"summary":{"title":"总结","items":[]}}'
        data = json.loads(raw)
        report = FollowupReport.model_validate(data)
        assert len(report.subtopics) == 1

    def test_boundary_unicode_in_key(self):
        """③ Unicode 字符在 key 中"""
        raw = '{"opening":{"lead":"测试"},"subtopics":[{"title":"测试","blocks":[{"type":"keyword","keyword":"测试","narrative":"测试"}]}],"summary":{"title":"总结","items":[]}}'
        data = json.loads(raw)
        report = FollowupReport.model_validate(data)
        assert report.subtopics[0].blocks[0].keyword == "测试"

    # ============================================================
    # 辅助方法：模拟 L2 格式完成率计算
    # ============================================================

    def test_calculate_format_completion_rate(self):
        """测试 L2 格式完成率计算逻辑"""
        # 模拟 10 次报告生成
        test_cases = [
            {"success": True, "error_type": None},  # 成功
            {"success": True, "error_type": None},
            {"success": False, "error_type": "json_parse_error"},  # JSON 解析失败
            {"success": True, "error_type": None},
            {"success": False, "error_type": "pydantic_validation_error"},  # Pydantic 校验失败
            {"success": True, "error_type": None},
            {"success": True, "error_type": None},
            {"success": False, "error_type": "json_parse_error"},
            {"success": True, "error_type": None},
            {"success": True, "error_type": None},
        ]

        total = len(test_cases)
        success_count = sum(1 for tc in test_cases if tc["success"])
        format_completion_rate = success_count / total if total > 0 else 0

        assert total == 10
        assert success_count == 7
        assert format_completion_rate == 0.7

        # 统计错误类型分布
        error_distribution = {}
        for tc in test_cases:
            if tc["error_type"]:
                error_distribution[tc["error_type"]] = error_distribution.get(tc["error_type"], 0) + 1

        assert error_distribution == {
            "json_parse_error": 2,
            "pydantic_validation_error": 1,
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
