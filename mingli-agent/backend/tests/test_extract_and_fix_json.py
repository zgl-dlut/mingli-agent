"""
_extract_and_fix_json 容错函数单元测试

覆盖三层处理：markdown去包裹 → 截取第一个完整JSON → 修复字符串值裸换行
共 17 个 case，覆盖正常/异常/边界/组合场景
"""
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.followup_structured import _extract_and_fix_json


class TestExtractAndFixJson:
    """容错函数测试集"""

    # ============================================================
    # 第一层：markdown 去包裹
    # ============================================================

    def test_normal_json_passthrough(self):
        """① 正常JSON直接通过，三层都不修改"""
        raw = '{"opening":{"lead":"测试"},"subtopics":[]}'
        result = _extract_and_fix_json(raw)
        assert json.loads(result) == json.loads(raw)

    def test_markdown_json_block_wrap(self):
        """② ```json ... ``` 包裹被正确去除"""
        raw = '```json\n{"opening":{"lead":"测试"}}\n```'
        result = _extract_and_fix_json(raw)
        assert json.loads(result)["opening"]["lead"] == "测试"

    def test_markdown_block_wrap_no_lang(self):
        """⑤ 只有开头```没有结尾（截断markdown）"""
        raw = '```\n{"opening":{"lead":"测试"}}'
        result = _extract_and_fix_json(raw)
        # 去掉了开头```，结尾没有```不影响
        assert json.loads(result)["opening"]["lead"] == "测试"

    # ============================================================
    # 第二层：截取第一个完整JSON
    # ============================================================

    def test_long_repeated_output(self):
        """③ 超长重复输出：截取第一个完整JSON，丢弃重复部分"""
        single = '{"opening":{"lead":"测试"},"subtopics":[]}'
        raw = single + '\n' + single + '\n' + single
        result = _extract_and_fix_json(raw)
        data = json.loads(result)
        assert data["opening"]["lead"] == "测试"
        # 确保只保留了一个
        assert result.count('"opening"') == 1

    def test_truncated_brackets(self):
        """⑥ 括号不配平（JSON被max_tokens截断）"""
        raw = '{"opening":{"lead":"测试"},"subtopics":[{"title":"截断'
        result = _extract_and_fix_json(raw)
        # 括号不配平，无法正确解析，但不应该崩溃
        # 返回的内容以 { 开头
        assert result.strip().startswith("{")

    def test_string_braces_not_counted(self):
        """⑧ 字符串值里的 { } 不被计数（in_string状态）"""
        raw = '{"narrative":"说{了}这些","title":"测试"}'
        result = _extract_and_fix_json(raw)
        data = json.loads(result)
        assert data["narrative"] == "说{了}这些"

    def test_escaped_quote_not_string_boundary(self):
        """⑦ 转义引号 \" 不被误判为字符串边界（escape_next状态）"""
        raw = '{"narrative":"他说\\"了这些","title":"测试"}'
        result = _extract_and_fix_json(raw)
        data = json.loads(result)
        assert data["narrative"] == '他说"了这些'

    def test_nested_braces_and_arrays(self):
        """⑨ 嵌套大括号/数组里的对象，深度正确归零"""
        raw = '{"items":[{"a":1},{"b":{"c":2}}],"title":"测试"}'
        result = _extract_and_fix_json(raw)
        data = json.loads(result)
        assert data["items"][1]["b"]["c"] == 2

    def test_backslash_before_brace(self):
        """⑩ \\\\ 反斜杠后跟大括号，escape_next跳过{不误增深度"""
        raw = '{"a":"\\\\{","title":"测试"}'
        result = _extract_and_fix_json(raw)
        data = json.loads(result)
        assert data["a"] == "\\{"

    def test_json_with_prefix_text(self):
        """⑪ JSON前面有非JSON文本，从第一个{开始截取"""
        raw = '这是结果：{"opening":{"lead":"测试"}}'
        result = _extract_and_fix_json(raw)
        data = json.loads(result)
        assert data["opening"]["lead"] == "测试"

    def test_no_brace_found(self):
        """⑫ 完全没有{（非JSON文本），返回原始文本"""
        raw = '这是一段普通文本，没有JSON'
        result = _extract_and_fix_json(raw)
        # 找不到{，返回原始文本
        assert "普通文本" in result

    def test_completely_garbled(self):
        """⑬ 完全乱码（非JSON），不崩溃"""
        raw = '!@#$%^&*()_+{}[]|:;"<>?,./'
        result = _extract_and_fix_json(raw)
        # 不崩溃即可，结果不保证可解析
        assert isinstance(result, str)

    # ============================================================
    # 第三层：修复字符串值裸换行
    # ============================================================

    def test_bare_newline_in_string(self):
        """④ 字符串值裸换行被修复为\\n"""
        raw = '{"narrative":"第一行\n第二行","title":"测试"}'
        result = _extract_and_fix_json(raw)
        data = json.loads(result)
        assert data["narrative"] == "第一行\n第二行"

    def test_escaped_newline_not_double_fixed(self):
        """⑭ 已转义的\\n不被重复修复"""
        raw = '{"narrative":"第一行\\n第二行","title":"测试"}'
        result = _extract_and_fix_json(raw)
        data = json.loads(result)
        # 已转义的\n 解析后是一个换行符，不应变成 \\n
        assert data["narrative"] == "第一行\n第二行"

    def test_structure_newlines_not_fixed(self):
        """⑮ 结构层换行（缩进格式化）不被修复"""
        raw = '{\n  "title": "测试"\n}'
        result = _extract_and_fix_json(raw)
        data = json.loads(result)
        assert data["title"] == "测试"

    def test_bare_newline_in_key(self):
        """⑯ 裸换行在key里（极端情况），不崩溃"""
        raw = '{"na\rrative":"测试","title":"x"}'
        result = _extract_and_fix_json(raw)
        # 不崩溃即可（key里的\r不保证修复，但不应抛异常）
        assert isinstance(result, str)

    # ============================================================
    # 组合场景
    # ============================================================

    def test_triple_combination(self):
        """⑰ 三层问题同时存在：markdown包裹 + 重复 + 裸换行"""
        single = '{"narrative":"第一行\n第二行","title":"测试"}'
        raw = f'```json\n{single}\n{single}\n```'
        result = _extract_and_fix_json(raw)
        data = json.loads(result)
        assert data["narrative"] == "第一行\n第二行"
        assert result.count('"title"') == 1

    # ============================================================
    # 防御性边界
    # ============================================================

    def test_empty_string(self):
        """空字符串输入"""
        result = _extract_and_fix_json("")
        assert result == ""

    def test_whitespace_only(self):
        """纯空白输入"""
        result = _extract_and_fix_json("   \n\t  ")
        assert result.strip() == ""
