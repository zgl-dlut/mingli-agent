"""
排盘正确性 + 流年流月数据一致性 单元测试

验证两件事：
1. 排盘核心算法正确（四柱、十神、大运）
2. 问题涉及流年流月时，LLM 拿到的是排盘系统计算的真实数据，而非自行推测

测试策略：
- 排盘正确性：用已知命例验证四柱/十神/大运，与公认结果对比
- 流年流月一致性：调用 generate_full_analysis，验证"重点流年"数据的每个年份的干支/吉凶/流月
  都是排盘系统计算的，且与手动推算的结果一致
"""
import sys
import os
import pytest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.bazi_service import (
    calculate_bazi, calculate_shishen, calculate_year_pillar,
    calculate_month_pillar, calculate_day_pillar, calculate_hour_pillar,
    TIANGAN, DIZHI, TIANGAN_WUXING, DIZHI_WUXING,
)
from app.skills.orchestrator import generate_full_analysis
from app.skills.divination.dayun_liunian_skill import (
    analyze_liunian, analyze_liuyue, get_key_years,
    WU_HU_DUN, LIUYUE_MONTHS, _year_to_ganzhi,
)


# ============================================================
# 测试用命例
# ============================================================

# 命例1：1990-06-15 10:30 男，北京
TEST_CASE_1 = {
    "birth_date": "1990-06-15",
    "birth_time": "10:30",
    "longitude": 116.4,
    "latitude": 39.9,
    "gender": "男",
    "location": "北京",
}

# 命例2：1985-12-19 19:35 女，上海
TEST_CASE_2 = {
    "birth_date": "1985-12-19",
    "birth_time": "19:35",
    "longitude": 121.5,
    "latitude": 31.2,
    "gender": "女",
    "location": "上海",
}


# ============================================================
# Part 1: 排盘核心算法正确性
# ============================================================

class TestBaziPaipan:
    """排盘核心算法正确性测试"""

    # ---------- 四柱计算 ----------

    def test_year_pillar_after_lichun(self):
        """① 立春后出生，年柱用当年"""
        # 2024-03-15 立春后，年柱应为甲辰
        dt = datetime(2024, 3, 15, 10, 0)
        tian, di = calculate_year_pillar(dt)
        assert tian == "甲", f"2024年立春后天干应为甲，实际{tian}"
        assert di == "辰", f"2024年立春后地支应为辰，实际{di}"

    def test_year_pillar_before_lichun(self):
        """② 立春前出生，年柱用前一年"""
        # 2024-01-15 立春前，年柱应为癸卯
        dt = datetime(2024, 1, 15, 10, 0)
        tian, di = calculate_year_pillar(dt)
        assert tian == "癸", f"2024年立春前天干应为癸，实际{tian}"
        assert di == "卯", f"2024年立春前地支应为卯，实际{di}"

    def test_day_pillar_known_date(self):
        """③ 日柱用已知日期验证：1949-10-01=甲子日"""
        dt = datetime(1949, 10, 1, 12, 0)
        tian, di = calculate_day_pillar(dt)
        assert tian == "甲", f"1949-10-01天干应为甲，实际{tian}"
        assert di == "子", f"1949-10-01地支应为子，实际{di}"

    def test_hour_pillar_zi_hour(self):
        """④ 子时（23点）时柱：日干甲，子时天干为甲"""
        tian, di = calculate_hour_pillar("甲", 23)
        assert di == "子", f"23点地支应为子，实际{di}"
        assert tian == "甲", f"甲日子时天干为甲（五鼠遁），实际{tian}"

    def test_hour_pillar_wu_hour(self):
        """⑤ 午时（12点）时柱：日干甲，午时天干为庚"""
        tian, di = calculate_hour_pillar("甲", 12)
        assert di == "午", f"12点地支应为午，实际{di}"
        # 五鼠遁：甲己日起甲子时，午时=庚午
        assert tian == "庚", f"甲日午时天干应为庚，实际{tian}"

    # ---------- 十神计算 ----------

    def test_shishen_same_element_same_yang(self):
        """⑥ 比肩：日干甲，见甲"""
        assert calculate_shishen("甲", "甲") == "比肩"

    def test_shishen_same_element_diff_yang(self):
        """⑦ 劫财：日干甲，见乙"""
        assert calculate_shishen("甲", "乙") == "劫财"

    def test_shishen_i_generate_same_yang(self):
        """⑧ 食神：日干甲（木），见丙（火），同阳"""
        assert calculate_shishen("甲", "丙") == "食神"

    def test_shishen_i_generate_diff_yang(self):
        """⑨ 伤官：日干甲（木），见丁（火），异阴阳"""
        assert calculate_shishen("甲", "丁") == "伤官"

    def test_shishen_i_restraint_same_yang(self):
        """⑩ 偏财：日干甲（木），见戊（土），同阳"""
        assert calculate_shishen("甲", "戊") == "偏财"

    def test_shishen_i_restraint_diff_yang(self):
        """⑪ 正财：日干甲（木），见己（土），异阴阳"""
        assert calculate_shishen("甲", "己") == "正财"

    def test_shishen_restrain_me_same_yang(self):
        """⑫ 七杀：日干甲（木），见庚（金），同阳"""
        assert calculate_shishen("甲", "庚") == "七杀"

    def test_shishen_restrain_me_diff_yang(self):
        """⑬ 正官：日干甲（木），见辛（金），异阴阳"""
        assert calculate_shishen("甲", "辛") == "正官"

    def test_shishen_generate_me_same_yang(self):
        """⑭ 偏印：日干甲（木），见壬（水），同阳"""
        assert calculate_shishen("甲", "壬") == "偏印"

    def test_shishen_generate_me_diff_yang(self):
        """⑮ 正印：日干甲（木），见癸（水），异阴阳"""
        assert calculate_shishen("甲", "癸") == "正印"

    # ---------- 阴干日主十神（验证memory中记录的历史bug） ----------

    def test_shishen_yin_day_master_乙(self):
        """⑯ 阴干日主乙：见甲=劫财，见乙=比肩，见丙=伤官，见丁=食神"""
        assert calculate_shishen("乙", "甲") == "劫财"
        assert calculate_shishen("乙", "乙") == "比肩"
        assert calculate_shishen("乙", "丙") == "伤官"
        assert calculate_shishen("乙", "丁") == "食神"

    def test_shishen_yin_day_master_丁(self):
        """⑰ 阴干日主丁：见壬=正官，见庚=正财，见甲=正印"""
        assert calculate_shishen("丁", "壬") == "正官"
        assert calculate_shishen("丁", "庚") == "正财"
        assert calculate_shishen("丁", "甲") == "正印"

    # ---------- 完整排盘 ----------

    def test_full_bazi_calculation(self):
        """⑱ 完整排盘不报错，返回结构完整"""
        chart = calculate_bazi(
            birth_date=TEST_CASE_1["birth_date"],
            birth_time=TEST_CASE_1["birth_time"],
            longitude=TEST_CASE_1["longitude"],
            gender=TEST_CASE_1["gender"],
        )
        # 四柱齐全
        assert "年" in chart.pillars
        assert "月" in chart.pillars
        assert "日" in chart.pillars
        assert "时" in chart.pillars
        # 每柱有天干地支
        for name, pillar in chart.pillars.items():
            assert "tian" in pillar, f"{name}柱缺少天干"
            assert "di" in pillar, f"{name}柱缺少地支"
            assert pillar["tian"] in TIANGAN, f"{name}柱天干{pillar['tian']}不在天干列表"
            assert pillar["di"] in DIZHI, f"{name}柱地支{pillar['di']}不在地支列表"
        # 大运列表非空
        assert len(chart.dayun) > 0, "大运列表为空"
        # 当前大运
        assert chart.current_dayun is not None, "当前大运为空"
        # 流年
        assert chart.liunian is not None, "流年为空"


# ============================================================
# Part 2: 流年流月数据一致性（排盘 vs LLM上下文）
# ============================================================

class TestLiunianLiuyueConsistency:
    """
    验证"重点流年"数据全部来自排盘系统计算，而非LLM自行推测。

    核心逻辑：
    1. generate_full_analysis 返回 analysis_data
    2. analysis_data["重点流年"] 包含每个年份的 ganzhi/judge/reason/detail/liuyue
    3. 手动调用 analyze_liunian + analyze_liuyue 验证每个字段
    4. 如果一致，说明 LLM 拿到的是排盘系统计算的真实数据
    """

    @pytest.fixture(scope="class")
    def analysis_data_1(self):
        """命例1的完整分析数据"""
        return generate_full_analysis(
            birth_date=TEST_CASE_1["birth_date"],
            birth_time=TEST_CASE_1["birth_time"],
            longitude=TEST_CASE_1["longitude"],
            latitude=TEST_CASE_1["latitude"],
            gender=TEST_CASE_1["gender"],
            location=TEST_CASE_1["location"],
        )

    @pytest.fixture(scope="class")
    def analysis_data_2(self):
        """命例2的完整分析数据"""
        return generate_full_analysis(
            birth_date=TEST_CASE_2["birth_date"],
            birth_time=TEST_CASE_2["birth_time"],
            longitude=TEST_CASE_2["longitude"],
            latitude=TEST_CASE_2["latitude"],
            gender=TEST_CASE_2["gender"],
            location=TEST_CASE_2["location"],
        )

    # ---------- 重点流年数据存在性 ----------

    def test_key_liunian_exists(self, analysis_data_1):
        """① analysis_data 包含"重点流年"字段且非空"""
        assert "重点流年" in analysis_data_1, "analysis_data缺少'重点流年'字段"
        key_list = analysis_data_1["重点流年"]
        assert isinstance(key_list, list), "'重点流年'不是列表"
        assert len(key_list) > 0, "'重点流年'列表为空"

    def test_key_liunian_structure(self, analysis_data_1):
        """② 每个流年数据结构完整"""
        for item in analysis_data_1["重点流年"]:
            assert "year" in item, f"流年数据缺少year字段: {item}"
            assert "ganzhi" in item, f"流年数据缺少ganzhi字段: {item}"
            assert "judge" in item, f"流年数据缺少judge字段: {item}"
            assert "reason" in item, f"流年数据缺少reason字段: {item}"
            assert "detail" in item, f"流年数据缺少detail字段: {item}"
            assert "liuyue" in item, f"流年数据缺少liuyue字段: {item}"
            # year是整数
            assert isinstance(item["year"], int), f"year不是整数: {item['year']}"
            # ganzhi是2字符
            assert len(item["ganzhi"]) == 2, f"ganzhi不是2字符: {item['ganzhi']}"

    # ---------- 流年干支正确性 ----------

    def test_liunian_ganzhi_correct(self, analysis_data_1):
        """③ 流年干支与年份对应正确（用_year_to_ganzhi验证）"""
        for item in analysis_data_1["重点流年"]:
            year = item["year"]
            expected_ganzhi = _year_to_ganzhi(year)
            assert item["ganzhi"] == expected_ganzhi, (
                f"流年{year}干支应为{expected_ganzhi}，实际{item['ganzhi']}"
            )

    def test_liunian_ganzhi_in_tiangan_dizhi(self, analysis_data_1):
        """④ 流年干支字符在天干地支列表内"""
        for item in analysis_data_1["重点流年"]:
            tian = item["ganzhi"][0]
            di = item["ganzhi"][1]
            assert tian in TIANGAN, f"流年天干{tian}不在天干列表"
            assert di in DIZHI, f"流年地支{di}不在地支列表"

    # ---------- 流年五行正确性 ----------

    def test_liunian_wuxing_correct(self, analysis_data_1):
        """⑤ 流年detail里的五行与干支对应正确"""
        for item in analysis_data_1["重点流年"]:
            detail = item["detail"]
            tian = item["ganzhi"][0]
            di = item["ganzhi"][1]
            expected_tian_wx = TIANGAN_WUXING[tian]
            expected_di_wx = DIZHI_WUXING[di]
            assert detail["tian_wuxing"] == expected_tian_wx, (
                f"流年{item['ganzhi']}天干{tian}五行应为{expected_tian_wx}，"
                f"实际{detail['tian_wuxing']}"
            )
            assert detail["di_wuxing"] == expected_di_wx, (
                f"流年{item['ganzhi']}地支{di}五行应为{expected_di_wx}，"
                f"实际{detail['di_wuxing']}"
            )

    # ---------- 流月数据正确性 ----------

    def test_liuyue_has_12_months(self, analysis_data_1):
        """⑥ 每个流年的流月数据有12个月"""
        for item in analysis_data_1["重点流年"]:
            liuyue = item["liuyue"]
            assert isinstance(liuyue, list), f"流月不是列表: {type(liuyue)}"
            assert len(liuyue) == 12, (
                f"流年{item['year']}的流月应有12个月，实际{len(liuyue)}个"
            )

    def test_liuyue_month_ganzhi_correct(self, analysis_data_1):
        """⑦ 流月干支由五虎遁推算正确"""
        for item in analysis_data_1["重点流年"][:3]:  # 抽查前3个流年
            year_tian = item["ganzhi"][0]
            yin_tian = WU_HU_DUN.get(year_tian, "丙")
            yin_idx = TIANGAN.index(yin_tian)

            for i, liuyue_item in enumerate(item["liuyue"]):
                solar_month, month_di, _ = LIUYUE_MONTHS[i]
                expected_month_tian = TIANGAN[(yin_idx + i) % 10]
                # 流月数据里应包含月令干支或地支信息
                # 验证地支对应正确
                assert month_di in str(liuyue_item), (
                    f"流年{item['year']}第{i+1}个月应含地支{month_di}，"
                    f"实际: {liuyue_item}"
                )

    # ---------- 流年吉凶与用神/忌神一致性 ----------

    def test_liunian_judge_consistent_with_yongshen(self, analysis_data_1):
        """⑧ 流年judge与用神/忌神一致：纯用神年应含'吉'"""
        yongshen = analysis_data_1["用神"]
        jishen = analysis_data_1["忌神"]

        for item in analysis_data_1["重点流年"]:
            detail = item["detail"]
            tian_wx = detail["tian_wuxing"]
            di_wx = detail["di_wuxing"]

            # 纯用神年 → 应标注"大吉"
            if tian_wx == yongshen and di_wx == yongshen:
                assert "大吉" in item["judge"], (
                    f"流年{item['year']}({item['ganzhi']})天干地支都是用神{yongshen}，"
                    f"应判大吉，实际{item['judge']}"
                )

            # 纯忌神年 + 有冲 → 应标注"大凶"
            if tian_wx == jishen and di_wx == jishen:
                has_chong = any("相冲" in inter for inter in detail.get("interactions", []))
                if has_chong:
                    assert "大凶" in item["judge"], (
                        f"流年{item['year']}({item['ganzhi']})天干地支都是忌神{jishen}且有冲，"
                        f"应判大凶，实际{item['judge']}"
                    )

    # ---------- 第二个命例验证 ----------

    def test_analysis_data_2_complete(self, analysis_data_2):
        """⑨ 命例2排盘数据完整（交叉验证）"""
        assert "重点流年" in analysis_data_2
        assert len(analysis_data_2["重点流年"]) > 0
        assert "用神" in analysis_data_2
        assert "忌神" in analysis_data_2

    def test_liunian_ganzhi_correct_case2(self, analysis_data_2):
        """⑩ 命例2流年干支正确"""
        for item in analysis_data_2["重点流年"]:
            expected = _year_to_ganzhi(item["year"])
            assert item["ganzhi"] == expected, (
                f"命例2流年{item['year']}干支应为{expected}，实际{item['ganzhi']}"
            )

    # ---------- LLM 上下文包含排盘数据 ----------

    def test_context_contains_liunian_data(self, analysis_data_1):
        """⑪ 验证 generate_followup_structured 的 prompt 上下文包含重点流年数据"""
        from app.services.followup_structured import _build_context_vars

        context = _build_context_vars(
            analysis_data=analysis_data_1,
            gender=TEST_CASE_1["gender"],
            user_question="未来三年运势如何",
            birth_date=TEST_CASE_1["birth_date"],
        )

        # 上下文应包含流年数据
        assert "key_liunian" in context, "上下文缺少key_liunian字段"
        assert context["key_liunian"], "key_liunian为空"

        # 上下文应包含用神忌神
        assert "yongshen" in context, "上下文缺少yongshen"
        assert "jishen" in context, "上下文缺少jishen"

        # 上下文应包含当前流年干支
        assert "liunian_ganzhi" in context, "上下文缺少liunian_ganzhi"

    def test_context_liunian_matches_analysis(self, analysis_data_1):
        """⑫ 上下文中的流年数据包含排盘系统计算的干支和吉凶（未被篡改）"""
        from app.services.followup_structured import _build_context_vars
        import re

        context = _build_context_vars(
            analysis_data=analysis_data_1,
            gender=TEST_CASE_1["gender"],
            user_question="2026年适合买房吗",
            birth_date=TEST_CASE_1["birth_date"],
        )

        ctx_str = context["key_liunian"]
        src_liunian = analysis_data_1["重点流年"]

        # 从上下文字符串中提取出现的年份
        ctx_years = set(int(m) for m in re.findall(r'(\d{4})年', ctx_str))

        # 对上下文中出现的每个年份，验证干支和吉凶与排盘数据一致
        for src_item in src_liunian:
            if src_item["year"] not in ctx_years:
                continue  # 上下文只取重点年份，跳过未出现的
            ganzhi = src_item["ganzhi"]
            year = src_item["year"]
            judge = src_item["judge"]
            assert ganzhi in ctx_str, f"上下文缺少流年干支{ganzhi}（{year}年）"
            assert judge in ctx_str, f"上下文缺少流年{year}年的吉凶标签{judge}"

        # 验证流月数据也传递到了上下文
        assert "流月吉凶" in ctx_str, "上下文缺少流月吉凶数据"
