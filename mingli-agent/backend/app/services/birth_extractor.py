"""临时生辰抽取 + 排盘注入。

解决场景：用户在对话里临时提"别人生辰"（非当前求问者档案）来问财运等，
系统原本只对当前 person 档案排盘，临时生辰无排盘入口，LLM 拿不到真实命盘
就自行编造五行/十神/大运（典型表现："满盘是水"这类无依据定性）。

本模块从用户消息抽取生辰(年月日时+地点+性别) → 调 generate_full_analysis 真实排盘
→ 格式化为文本区块，注入 generate_followup_structured 的 system_prompt，
让 LLM 基于真实命盘解读；抽不到时由 prompt 约束兜底（告知无法排盘，禁止自行推导）。
"""
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# 省级行政区经纬度（省会坐标）
# 同省城市经度差通常 <5°（真太阳时差 <20 分钟），不影响时辰判定（2 小时一格），
# 未覆盖的地级市回退省会经纬度，精度足够（与前端 cityCoords.ts 同源同策略）。
PROVINCE_COORDS: Dict[str, Dict[str, float]] = {
    "北京市": {"lng": 116.4074, "lat": 39.9042},
    "天津市": {"lng": 117.2009, "lat": 39.0842},
    "河北省": {"lng": 114.5149, "lat": 38.0428},
    "山西省": {"lng": 112.5489, "lat": 37.8706},
    "内蒙古自治区": {"lng": 111.7491, "lat": 40.8426},
    "辽宁省": {"lng": 123.4315, "lat": 41.8057},
    "吉林省": {"lng": 125.3245, "lat": 43.8868},
    "黑龙江省": {"lng": 126.535, "lat": 45.8038},
    "上海市": {"lng": 121.4737, "lat": 31.2304},
    "江苏省": {"lng": 118.7969, "lat": 32.0603},
    "浙江省": {"lng": 120.1551, "lat": 30.2741},
    "安徽省": {"lng": 117.2272, "lat": 31.8206},
    "福建省": {"lng": 119.2965, "lat": 26.0745},
    "江西省": {"lng": 115.8579, "lat": 28.682},
    "山东省": {"lng": 117.1201, "lat": 36.6512},
    "河南省": {"lng": 113.6253, "lat": 34.7466},
    "湖北省": {"lng": 114.3055, "lat": 30.5928},
    "湖南省": {"lng": 112.9388, "lat": 28.2278},
    "广东省": {"lng": 113.2644, "lat": 23.1291},
    "广西壮族自治区": {"lng": 108.3669, "lat": 22.817},
    "海南省": {"lng": 110.199, "lat": 20.044},
    "重庆市": {"lng": 106.5516, "lat": 29.563},
    "四川省": {"lng": 104.0668, "lat": 30.5728},
    "贵州省": {"lng": 106.6302, "lat": 26.647},
    "云南省": {"lng": 102.8329, "lat": 24.8801},
    "西藏自治区": {"lng": 91.1409, "lat": 29.65},
    "陕西省": {"lng": 108.9398, "lat": 34.3416},
    "甘肃省": {"lng": 103.8343, "lat": 36.0611},
    "青海省": {"lng": 101.7782, "lat": 36.6171},
    "宁夏回族自治区": {"lng": 106.2309, "lat": 38.4872},
    "新疆维吾尔自治区": {"lng": 87.6168, "lat": 43.8256},
    "香港特别行政区": {"lng": 114.1694, "lat": 22.3193},
    "澳门特别行政区": {"lng": 113.5439, "lat": 22.1987},
    "台湾省": {"lng": 121.5654, "lat": 25.033},
}

# 常用地级市经纬度（按城市名索引，补充精度；可按需扩充）
CITY_COORDS: Dict[str, Dict[str, float]] = {
    "日照市": {"lng": 119.5269, "lat": 35.4164},
}

DEFAULT_COORD = {"lng": 116.4074, "lat": 39.9042}  # 北京兜底


def get_coord_by_name(province: str = "", city: str = "") -> Dict[str, float]:
    """按省/市名查经纬度，市级优先 → 省级 → 北京兜底。"""
    if city:
        if city in CITY_COORDS:
            return CITY_COORDS[city]
        # 去"市"后缀模糊匹配
        for k, v in CITY_COORDS.items():
            if province and province[:2] in k:
                return v
    if province:
        if province in PROVINCE_COORDS:
            return PROVINCE_COORDS[province]
        # 模糊匹配：去掉"省/市/自治区"等后缀后包含判断
        for k, v in PROVINCE_COORDS.items():
            if province in k or k.startswith(province[:2]):
                return v
    return DEFAULT_COORD


# ---- 生辰抽取正则 ----
# 日期：1994-09-22 / 1994/9/22 / 1994年9月22日
_RE_DATE = re.compile(r'(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})\s*日?')
# 时间：20:30 / 08:00
_RE_TIME_COLON = re.compile(r'(\d{1,2}):(\d{2})')
# 时间中文：晚上8点半 / 下午3点 / 凌晨0点30分
_RE_TIME_CN = re.compile(r'(凌晨|早上|上午|中午|下午|傍晚|晚上|夜间)?\s*(\d{1,2})\s*[点时]\s*(\d{1,2})?\s*分?')
# 性别：性别：女 / 性别:男
_RE_GENDER = re.compile(r'性别\s*[：:]\s*(男|女)')
# 省/自治区/直辖市
_RE_PROVINCE = re.compile(r'([\u4e00-\u9fa5]{2,}(?:省|自治区|壮族自治区|回族自治区|维吾尔自治区|特别行政区))')
# 市
_RE_CITY = re.compile(r'([\u4e00-\u9fa5]{2,}市)')


def _parse_time_to_hhmm(text: str) -> Optional[str]:
    """从文本片段解析时间到 HH:MM。"""
    m = _RE_TIME_COLON.search(text)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    m = _RE_TIME_CN.search(text)
    if m:
        period = m.group(1) or ""
        h = int(m.group(2))
        minute = int(m.group(3)) if m.group(3) else 0
        if period in ("晚上", "夜间", "傍晚") and h < 12:
            h += 12
        elif period in ("下午", "中午") and h < 12:
            h += 12
        # 早上/上午/凌晨保持原值
        return f"{h:02d}:{minute:02d}"
    return None


def extract_births(text: str) -> List[Dict[str, Any]]:
    """从用户消息抽取生辰信息。

    保守策略：必须匹配到日期才算一个生辰；时间/地点/性别缺省时分别处理。
    性别未明确抽取到时置 None（调用方据此决定是否排盘——gender 影响大运顺逆，
    缺失则不排盘，交由 prompt 兜底）。

    Returns:
        [{birth_date, birth_time, province, city, gender}, ...]
        gender: "male"/"female"/None
    """
    results: List[Dict[str, Any]] = []
    for m in _RE_DATE.finditer(text):
        year = m.group(1)
        month = int(m.group(2))
        day = int(m.group(3))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            continue
        birth_date = f"{year}-{month:02d}-{day:02d}"

        # 在该日期附近找时间（前后 30 字符窗口）
        win_start = max(0, m.start() - 30)
        win_end = min(len(text), m.end() + 30)
        nearby = text[win_start:win_end]
        birth_time = _parse_time_to_hhmm(nearby)

        # 省市：取全文第一个匹配（生辰表述通常集中）
        province = ""
        city = ""
        pm = _RE_PROVINCE.search(text)
        cm = _RE_CITY.search(text)
        if pm:
            province = pm.group(1)
        if cm:
            city = cm.group(1)

        # 性别
        gender: Optional[str] = None
        gm = _RE_GENDER.search(text)
        if gm:
            gender = "female" if gm.group(1) == "女" else "male"

        results.append({
            "birth_date": birth_date,
            "birth_time": birth_time,  # 可能为 None
            "province": province,
            "city": city,
            "gender": gender,
        })
    return results


def _format_chart_brief(analysis_data: Dict[str, Any], birth_info: Dict[str, Any]) -> str:
    """把排盘结果格式化为紧凑文本区块，供注入 system_prompt。"""
    if not analysis_data:
        return ""
    g_cn = "女" if birth_info.get("gender") == "female" else "男"
    place = f"{birth_info.get('province', '')} {birth_info.get('city', '')}".strip()
    lines = [
        "【用户提及的他人命盘（系统已排盘，可基于此解读；与当前求问者命盘不同，勿混淆主语）】",
        f"性别：{g_cn}",
        f"公历生辰：{birth_info['birth_date']} {birth_info.get('birth_time', '未知')}",
        f"出生地：{place or '未知'}",
        f"四柱：{analysis_data.get('四柱', '')}",
        f"日主：{analysis_data.get('日主', '')}",
        f"旺衰：{analysis_data.get('旺衰结论', '')}",
        f"格局：{analysis_data.get('格局', '')}",
        f"用神/忌神：{analysis_data.get('用神', '')} / {analysis_data.get('忌神', '')}",
    ]
    wx = analysis_data.get("五行分布", {})
    if isinstance(wx, dict):
        lines.append(
            f"五行分布：金{wx.get('金', 0)} 木{wx.get('木', 0)} 水{wx.get('水', 0)} 火{wx.get('火', 0)} 土{wx.get('土', 0)}"
        )
    lines.append(f"十神分布：{analysis_data.get('十神分布', '')}")
    lines.append(f"当前大运：{analysis_data.get('当前大运', '')}")
    dy = analysis_data.get("大运列表", [])
    if dy:
        lines.append(f"大运列表：{dy}")
    return "\n".join(lines)


def build_extra_chart_block(
    question: str,
    exclude_birth_date: Optional[str] = None,
    exclude_birth_time: Optional[str] = None,
) -> str:
    """主入口：从用户消息抽取临时生辰 → 排盘 → 格式化为注入区块。

    Args:
        question: 用户原始问题
        exclude_birth_date: 当前求问者档案的出生日期，抽到相同生辰则跳过（避免重复排盘）
        exclude_birth_time: 当前求问者档案的出生时间

    Returns:
        格式化文本区块（多个生辰用空行拼接）；无可用生辰或排盘失败返回空串。
    """
    births = extract_births(question)
    if not births:
        return ""

    blocks: List[str] = []
    for b in births:
        # gender 缺失不排盘（大运顺逆依赖性别，错了全盘错；交 prompt 兜底）
        if not b["gender"]:
            logger.info(f"[BirthExtractor] 生辰 {b['birth_date']} 缺性别，跳过排盘")
            continue
        # 缺时间用午时(12:00)兜底——时辰未知时用午时是命理常规处理
        if not b["birth_time"]:
            b["birth_time"] = "12:00"
        # 跳过与当前档案相同的生辰
        if exclude_birth_date and b["birth_date"] == exclude_birth_date:
            if not exclude_birth_time or b["birth_time"] == exclude_birth_time:
                continue

        coord = get_coord_by_name(b["province"], b["city"])
        try:
            from app.skills.orchestrator import generate_full_analysis
            analysis = generate_full_analysis(
                birth_date=b["birth_date"],
                birth_time=b["birth_time"],
                longitude=coord["lng"],
                latitude=coord["lat"],
                gender=b["gender"],
                location=f"{b['province']} {b['city']}".strip(),
            )
            block = _format_chart_brief(analysis, b)
            if block:
                blocks.append(block)
            logger.info(
                f"[BirthExtractor] 临时生辰排盘成功: {b['birth_date']} {b['birth_time']} {b['gender']}"
            )
        except Exception as e:
            logger.warning(
                f"[BirthExtractor] 临时生辰排盘失败 {b['birth_date']} {b['birth_time']}: "
                f"{type(e).__name__}: {e}"
            )

    if not blocks:
        return ""
    return "\n\n".join(blocks)
