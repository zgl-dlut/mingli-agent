"""
错误追问摘要不影响命盘结论的保障测试

分两层：
1. 单元测试（纯函数，不调LLM，快、稳定）：
   - prompt 措辞保障：确认"命盘权威/以命盘为准/不盲从前轮/严禁编造"等修复措辞进了 prompt
   - 历史摘要提取逻辑：确认 verdict/子问题标题提取正确，Markdown 首次报告被跳过
2. 集成测试（调LLM，需API key，自动从 .env 加载）：
   - 注入与命盘矛盾的"错误历史摘要"，验证 LLM 仍以命盘为准，不盲从、不编造

背景：修复"一致性要求"措辞前，错误历史摘要会让 LLM 盲从前轮结论，甚至编造反命盘的
命理依据（如命盘忌火却编造"大运助金水"说适合创业）。本测试固化修复效果，防止回归。
"""
import sys
import os
import json
import urllib.request

import pytest

# 添加 backend 到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.followup_structured import build_structured_prompt, _build_history_summary, _extract_and_fix_json

# 尝试加载 .env（集成测试需要 API key）
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass


# ============================================================
# 固定命盘：壬水弱，2027丁未年火土忌神当道（不利创业）
# 错误历史摘要会说"适合创业"，与命盘矛盾，用于验证 LLM 是否盲从
# ============================================================

FIXED_CONTEXT = {
    "current_time": "2026年8月",
    "liunian_ganzhi": "丙午",
    "liunian_season": "夏季",
    "sizu": "壬申 庚戌 壬子 辛亥",
    "rizhu": "壬水",
    "gender": "男",
    "wangshuai": "偏弱",
    "geju_description": "印格",
    "yongshen": "金水（帮身）",
    "xishen": "金水",
    "jishen": "火土（耗身）",
    "shishen_fenbu": "偏印/正印/比肩/劫财",
    "wuxing_fenbu": "水4 金3 土2 火1 木1",
    "dizhi_zuoyong": "申子半合水局",
    "tiaohou_desc": "调候需金水润局",
    "current_dayun": "丙午",
    "dayun_jiedu": "火土忌神运，耗身破财",
    "key_liunian": "2027丁未年：丁火透干+未土，火土忌神当道，对弱水日主不利，耗身破财",
    "user_question": "2027年我适合创业吗？",
    "age": 35,
    "age_stage": "中年期（31-50岁）",
}

# 与命盘矛盾的"错误历史摘要"
WRONG_HISTORY = "第1轮回答：核心结论：2027丁未年是你事业爆发期，适合创业扩张，大吉"

# 与命盘一致的"正确历史摘要"（对照组）
RIGHT_HISTORY = "第1轮回答：核心结论：2027丁未年火土忌神当道，宜守不宜攻"


# ============================================================
# 单元测试 1：prompt 措辞保障（不调LLM）
# ============================================================

class TestPromptConsistencyRules:
    """验证修复后的"命盘权威"措辞确实进了 system_prompt"""

    def test_prompt_has_panpan_authority(self):
        """命盘数据是最高推演依据"""
        prompt = build_structured_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "命盘数据是最高推演依据" in prompt

    def test_prompt_allows_correction(self):
        """以命盘为准可修正前轮"""
        prompt = build_structured_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "以命盘为准" in prompt

    def test_prompt_forbids_blind_follow(self):
        """不盲从前轮判断"""
        prompt = build_structured_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "不盲从前轮判断" in prompt

    def test_prompt_forbids_fabrication(self):
        """严禁编造命理依据"""
        prompt = build_structured_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "严禁编造命理依据" in prompt

    def test_prompt_no_must_keep_consistent(self):
        """旧措辞'必须保持一致，禁止自相矛盾'已移除（避免强制盲从）"""
        prompt = build_structured_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "必须与历史摘要保持一致，禁止自相矛盾" not in prompt

    def test_prompt_injects_history_when_present(self):
        """有历史摘要时，摘要内容注入 prompt"""
        prompt = build_structured_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "历史对话摘要" in prompt
        assert "事业爆发期" in prompt  # 摘要原文进 prompt

    def test_prompt_no_history_section_when_empty(self):
        """空历史时不应出现历史摘要区块"""
        prompt = build_structured_prompt(FIXED_CONTEXT, "")
        assert "历史对话摘要" not in prompt

    def test_prompt_keeps_bazi_data(self):
        """命盘数据完整注入（以命盘为准的前提）"""
        prompt = build_structured_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "壬水" in prompt
        assert "金水" in prompt  # 用神
        assert "火土" in prompt  # 忌神
        assert "2027丁未年" in prompt  # 重点流年


# ============================================================
# 单元测试 2：历史摘要提取逻辑（不调LLM）
# ============================================================

class TestHistorySummaryExtraction:
    """验证 _build_history_summary 的提取行为"""

    def test_extracts_verdict_from_json_history(self):
        """从 JSON 历史 assistant 消息提取 opening.verdict"""
        history = [{"role": "assistant", "content": json.dumps({
            "opening": {"verdict": "2027年不宜创业"},
            "subtopics": [],
            "summary": {"title": "总结"},
        }, ensure_ascii=False)}]
        summary = _build_history_summary(history)
        assert "2027年不宜创业" in summary

    def test_skips_markdown_first_reading(self):
        """Markdown 首次报告被跳过（不进摘要）—— 这是已知设计，防止首次报告错误传染"""
        history = [{"role": "assistant", "content": "# 你的命理全局解读\n\n壬水日主偏弱，2027年适合创业扩张..."}]
        summary = _build_history_summary(history)
        assert summary == ""
        assert "适合创业扩张" not in summary  # 关键：Markdown 结论不进摘要

    def test_extracts_subtopic_titles(self):
        """提取子问题标题"""
        history = [{"role": "assistant", "content": json.dumps({
            "opening": {},
            "subtopics": [{"title": "财务时间线"}, {"title": "离职时机"}],
            "summary": {"title": "总结"},
        }, ensure_ascii=False)}]
        summary = _build_history_summary(history)
        assert "财务时间线" in summary
        assert "离职时机" in summary

    def test_extracts_summary_items(self):
        """提取 summary.items 行动建议"""
        history = [{"role": "assistant", "content": json.dumps({
            "opening": {},
            "subtopics": [],
            "summary": {"title": "总结", "items": [
                {"keyword": "9月", "text": "打磨作品集"},
                {"keyword": "10月", "text": "入职新公司"},
            ]},
        }, ensure_ascii=False)}]
        summary = _build_history_summary(history)
        assert "打磨作品集" in summary
        assert "入职新公司" in summary

    def test_skips_user_messages(self):
        """只处理 assistant 消息，跳过 user"""
        history = [
            {"role": "user", "content": "用户原始问题"},
            {"role": "assistant", "content": json.dumps({
                "opening": {"verdict": "结论"},
                "subtopics": [], "summary": {"title": "s"},
            }, ensure_ascii=False)},
        ]
        summary = _build_history_summary(history)
        assert "结论" in summary
        assert "用户原始问题" not in summary

    def test_empty_history_returns_empty(self):
        """空历史返回空字符串"""
        assert _build_history_summary([]) == ""

    def test_invalid_json_skipped(self):
        """无效 JSON 的 assistant 消息被跳过（不抛异常）"""
        history = [{"role": "assistant", "content": "这不是JSON"}]
        assert _build_history_summary(history) == ""


# ============================================================
# 集成测试：LLM 不被错误历史摘要带偏（调真实 API）
# ============================================================

_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
_API_URL = os.getenv("AI_BASE_URL", "https://ws-ekdxihtd67l14sw6.cn-beijing.maas.aliyuncs.com/compatible-mode/v1") + "/chat/completions"
_LLM_MODEL = os.getenv("AI_MODEL", "qwen-plus-latest")

pytestmark_integration = pytest.mark.skipif(
    not _API_KEY,
    reason="未配置 DASHSCOPE_API_KEY，跳过 LLM 集成测试",
)


@pytest.mark.skipif(not _API_KEY, reason="未配置 DASHSCOPE_API_KEY，跳过 LLM 集成测试")
class TestLLMNotContaminated:
    """集成测试：注入错误历史摘要，验证 LLM 仍以命盘为准

    命盘事实：壬水弱 + 2027丁未火土忌神 = 不利创业
    错误历史：2027适合创业扩张
    期望：LLM 不盲从错误历史，输出"不宜/守/慎"等以命盘为准的结论
    """

    def _call_llm(self, history_summary: str) -> dict:
        """用 build_structured_prompt 构造 prompt 并调用 LLM，返回解析后的 dict"""
        prompt = build_structured_prompt(FIXED_CONTEXT, history_summary)
        body = json.dumps({
            "model": _LLM_MODEL,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": FIXED_CONTEXT["user_question"]},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 4000,
        }).encode()
        req = urllib.request.Request(
            _API_URL, data=body,
            headers={"Authorization": f"Bearer {_API_KEY}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
        content = resp["choices"][0]["message"]["content"]
        # 复用生产容错：先直接解析，失败则用 _extract_and_fix_json 修复（处理裸换行/markdown包裹等）
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            fixed = _extract_and_fix_json(content)
            result = json.loads(fixed)
        # 打印 verdict 便于人工核对（pytest -s 可见）
        _v = result.get("opening", {}).get("verdict", "")
        print(f"\n[verdict] {_v[:300]}")
        return result

    def test_wrong_history_not_followed(self):
        """错误历史(适合创业)下，LLM 应以命盘为准(不宜)，不盲从"""
        data = self._call_llm(WRONG_HISTORY)
        verdict = data.get("opening", {}).get("verdict", "")

        # 反向信号：明确盲从错误历史，禁止出现（用正向推荐短语，避免"不适合创业"否定句误匹配）
        blind_signals = ["建议创业", "该创业", "可以创业", "创业扩张", "创业最稳", "创业好时机", "创业吉", "创业旺", "创业爆", "事业爆发期"]
        for w in blind_signals:
            assert w not in verdict, f"被错误历史带偏(含'{w}'): verdict={verdict}"

        # 正向信号：以命盘为准，至少一个（覆盖 LLM 多样化表述）
        bazi_signals = ["不宜", "不适合", "避开", "慎", "暂缓", "推迟", "压后", "得等", "2028",
                        "守住", "稳住", "火土旺", "水气弱", "架在火上", "耗身", "破财", "忌神"]
        assert any(w in verdict for w in bazi_signals), f"未以命盘为准(无命盘信号): verdict={verdict}"

    def test_right_history_kept(self):
        """正确历史(不宜)下，LLM 结论与命盘一致"""
        data = self._call_llm(RIGHT_HISTORY)
        verdict = data.get("opening", {}).get("verdict", "")
        bazi_signals = ["不宜", "不适合", "避开", "慎", "暂缓", "推迟", "压后", "得等", "2028",
                        "守住", "稳住", "火土旺", "水气弱", "架在火上", "耗身", "破财", "忌神"]
        assert any(w in verdict for w in bazi_signals), f"正确历史下结论偏离命盘: verdict={verdict}"

    def test_no_fabricated_bazi_basis(self):
        """narrative 不编造 prompt 未提供的命理依据

        prompt 只给了 current_dayun=丙午(火土忌神)，若 LLM 说"大运助金水"
        就是编造反命盘依据来迎合错误历史，必须禁止。
        """
        data = self._call_llm(WRONG_HISTORY)
        all_text = json.dumps(data, ensure_ascii=False)
        # 典型编造模式：大运助金水/大运生身（实际丙午是忌神运，不可能助身）
        assert "大运助金水" not in all_text, f"编造'大运助金水': {all_text[:300]}"
        assert "大运生身" not in all_text, f"编造'大运生身': {all_text[:300]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
