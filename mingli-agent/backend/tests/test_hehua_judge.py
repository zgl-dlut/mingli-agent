"""合化体系判定测试：覆盖三合/三会/半合/天干合/六冲方向/六合绊/合化条件。

直接测试 _analyze_interactions 与 _compute_overall_judge，验证标准排盘合化逻辑。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.skills.divination.dayun_liunian_skill import (
    _analyze_interactions, _compute_overall_judge,
)


def _pillars(nian, yue, ri, shi):
    """构造四柱 dict，每个参数为 (天干, 地支) 元组。"""
    return {
        "年": {"tian": nian[0], "di": nian[1]},
        "月": {"tian": yue[0], "di": yue[1]},
        "日": {"tian": ri[0], "di": ri[1]},
        "时": {"tian": shi[0], "di": shi[1]},
    }


def _judge(tian, di, pillars, day_tian, yongshen, jishen, label="流年"):
    """跑完整判定，返回 (interactions, judge)。"""
    interactions = _analyze_interactions(tian, di, pillars, day_tian, label, yongshen, jishen)
    tian_wx = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
               "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}[tian]
    di_wx = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土",
             "巳": "火", "午": "火", "未": "土", "申": "金", "酉": "金",
             "戌": "土", "亥": "水"}[di]
    judge = _compute_overall_judge(tian_wx, di_wx, yongshen, jishen, interactions)
    return interactions, judge


# ---------- 完整三合局 ----------

def test_san_he_hua_ji_ke_shen():
    """亥卯未三合木局，木克日主己土（七杀攻身）→ 凶。月支亥水生木得令真化。"""
    # 真实命盘：庚午 丁亥 己卯 戊辰，日主己土，用神火，忌神水
    pillars = _pillars(("庚", "午"), ("丁", "亥"), ("己", "卯"), ("戊", "辰"))
    interactions, judge = _judge("丁", "未", pillars, "己", "火", "水")
    joined = "".join(interactions)
    assert "三合木局克身" in joined, f"应检测到三合木局克身，实际: {interactions}"
    assert "凶" in judge, f"三合木局克身应判凶，实际: {judge}"


def test_san_he_hua_yong_sheng_shen():
    """亥卯未三合木局，木生日主丙火（印星生身）→ 吉。日主丙火用神木。"""
    # 构造日支卯、月支亥，流年未，日主丙火（木生火=印星）
    pillars = _pillars(("庚", "午"), ("壬", "亥"), ("丙", "卯"), ("戊", "辰"))
    interactions, judge = _judge("丁", "未", pillars, "丙", "木", "金")
    joined = "".join(interactions)
    assert "三合木局生身" in joined, f"应检测到三合木局生身，实际: {interactions}"
    assert "吉" in judge, f"三合木局生身应判吉，实际: {judge}"


# ---------- 完整三会局 ----------

def test_san_hui_hua_ji_ke_shen():
    """寅卯辰三会木局，木克日主己土 → 凶（力量强于三合，xiong+3）。"""
    # 原局有寅、卯，流年辰→寅卯辰三会木
    pillars = _pillars(("甲", "寅"), ("丁", "亥"), ("己", "卯"), ("戊", "辰"))
    interactions, judge = _judge("戊", "辰", pillars, "己", "火", "水")
    joined = "".join(interactions)
    assert "三会木局克身" in joined, f"应检测到三会木局克身，实际: {interactions}"
    assert "凶" in judge, f"三会木局克身应判凶，实际: {judge}"


# ---------- 半合分级 ----------

def test_ban_he_with_zhongshen_hua_ji():
    """带中神卯的半合（卯未），化木克己土 → 计凶（xiong+1）。"""
    # 日支卯（中神），流年未，卯未半合带中神
    pillars = _pillars(("庚", "午"), ("丁", "亥"), ("己", "卯"), ("戊", "辰"))
    # 流年亥：亥卯半合带中神卯，化木克己土（但亥不从未来）
    interactions, judge = _judge("辛", "亥", pillars, "己", "火", "水")
    joined = "".join(interactions)
    assert "半合木局（带中神）克身" in joined, f"应检测到带中神半合克身，实际: {interactions}"


def test_ban_he_without_zhongshen_no_score():
    """不带中神的半合（亥未），力量弱，不计吉凶。"""
    # 流年未与月支亥半合（亥未），无中神（中神是卯，不在亥未这对里）
    pillars = _pillars(("庚", "午"), ("丁", "亥"), ("己", "戌"), ("戊", "辰"))
    interactions, judge = _judge("丁", "未", pillars, "己", "火", "水")
    joined = "".join(interactions)
    assert "半合木局" in joined and "带中神" not in joined.split("月柱亥半合木局")[0].split("未与")[-1], (
        f"亥未半合不应带中神标注，实际: {interactions}"
    )


# ---------- 六冲方向 ----------

def test_chong_yongshen_is_xiong():
    """冲用神→凶。子冲午，午=火用神。"""
    pillars = _pillars(("庚", "午"), ("丁", "亥"), ("己", "卯"), ("戊", "辰"))
    interactions, judge = _judge("壬", "子", pillars, "己", "火", "水")
    joined = "".join(interactions)
    assert "冲用神" in joined, f"子冲午应标注冲用神，实际: {interactions}"
    assert "凶" in judge, f"冲用神应判凶，实际: {judge}"


def test_chong_jishen_is_ji():
    """冲忌神→去忌为吉。午冲子，子=水忌神。"""
    # 构造原局有子（忌神水），流年午冲子
    pillars = _pillars(("甲", "子"), ("丁", "亥"), ("己", "卯"), ("戊", "辰"))
    interactions, judge = _judge("壬", "午", pillars, "己", "火", "水")
    joined = "".join(interactions)
    assert "冲忌神" in joined, f"午冲子应标注冲忌神，实际: {interactions}"


def test_chong_neutral_is_bian_dong():
    """中性冲（冲非用非忌）→ 主变动。酉冲卯，卯=木非用非忌。"""
    pillars = _pillars(("庚", "午"), ("丁", "亥"), ("己", "卯"), ("戊", "辰"))
    interactions, judge = _judge("己", "酉", pillars, "己", "火", "水")
    joined = "".join(interactions)
    assert "相冲，主变动" in joined, f"酉冲卯应标注中性冲，实际: {interactions}"


# ---------- 天干五合化气 ----------

def test_tiangan_he_hua_jishen():
    """天干合化忌神→凶。乙庚合化金，金克日主甲木（七杀）。"""
    # 日主甲木，原局月干乙，流年庚→乙庚合化金，金克甲木
    # 需化神得令：月支申酉（金）或辰戌丑未，此处月支申
    pillars = _pillars(("甲", "子"), ("乙", "申"), ("甲", "寅"), ("戊", "辰"))
    interactions, judge = _judge("庚", "午", pillars, "甲", "水", "金")
    joined = "".join(interactions)
    assert "合化金（忌神）" in joined, f"乙庚合化金应标注忌神，实际: {interactions}"


def test_tiangan_he_hua_yongshen():
    """天干合化用神→吉。丙辛合化水，水生木日主（印星）。"""
    # 日主甲木，用神水，原局月干丙，流年辛→丙辛合化水（用神）
    # 化神得令：月支亥子（水），此处月支亥
    pillars = _pillars(("甲", "寅"), ("丙", "亥"), ("甲", "卯"), ("戊", "辰"))
    interactions, judge = _judge("辛", "未", pillars, "甲", "水", "金")
    joined = "".join(interactions)
    assert "合化水（用神）" in joined, f"丙辛合化水应标注用神，实际: {interactions}"


# ---------- 六合绊 ----------

def test_liu_he_ban_yongshen():
    """六合绊用神→减吉。午未六合，午=火用神。"""
    pillars = _pillars(("庚", "午"), ("丁", "亥"), ("己", "卯"), ("戊", "辰"))
    interactions, judge = _judge("丁", "未", pillars, "己", "火", "水")
    joined = "".join(interactions)
    assert "六合绊用神" in joined, f"午未六合绊用神应标注，实际: {interactions}"


def test_liu_he_ban_jishen():
    """六合绊忌神→减凶。子丑六合，子=水忌神。"""
    pillars = _pillars(("甲", "子"), ("丁", "丑"), ("己", "卯"), ("戊", "辰"))
    interactions, judge = _judge("壬", "午", pillars, "己", "火", "水")
    joined = "".join(interactions)
    # 流年午与年支子不六合（子午冲），需构造六合：流年丑与原局子六合
    # 改：流年丑，原局有子
    interactions2, _ = _judge("己", "丑", pillars, "己", "火", "水")
    assert "六合绊忌神" in "".join(interactions2), f"子丑六合绊忌神应标注，实际: {interactions2}"


# ---------- 合化条件 ----------

def test_he_bu_hua_when_not_deling():
    """化神不得令→合而不化，不计克身。亥卯未化木，月支酉（金克木不生木）→合而不化。"""
    # 年支亥+日支卯+流年未=亥卯未齐，但月支酉金不生木，化神不得令
    pillars = _pillars(("甲", "亥"), ("丁", "酉"), ("己", "卯"), ("戊", "辰"))
    interactions, judge = _judge("丁", "未", pillars, "己", "火", "水")
    joined = "".join(interactions)
    assert "三合木局（合而不化）" in joined, f"化神不得令应合而不化，实际: {interactions}"
    assert "克身" not in joined, f"合而不化不应标克身，实际: {interactions}"
