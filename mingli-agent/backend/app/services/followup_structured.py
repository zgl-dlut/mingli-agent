"""
结构化追问报告服务

LLM 输出 JSON（response_format=json_object），后端容错+校验，
直接存 JSON 到数据库，前端用 React 组件直渲染（不走 Markdown 中间层）。

与首次报告解读链路完全隔离，互不影响。
"""
import json
import time
import logging
from typing import AsyncGenerator, Dict, List

from pydantic import ValidationError

from app.schemas.report_schema import FollowupReport
from app.services.skill_prompts import _build_context_vars, _extract_liuyue_data
from app.services.ai_service import model_pool, get_client, build_llm_extra_body

logger = logging.getLogger(__name__)
# 确保 logger.info 能输出到 stdout（uvicorn 默认不配置 app 子 logger 的 handler）
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setLevel(logging.INFO)
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
    logger.addHandler(_h)
    # 检测日志持久化到文件，终端日志会被截断，文件可完整查看
    import os
    os.makedirs("logs", exist_ok=True)
    _fh = logging.FileHandler("logs/followup_check.log", encoding="utf-8")
    _fh.setLevel(logging.INFO)
    _fh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
    logger.addHandler(_fh)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # 避免重复输出


# ============================================================
# Function Calling 工具定义：流月数据按需获取
# ============================================================

LIUYUE_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_liuyue_detail",
        "description": "获取指定年份的流月吉凶数据。当需要给出具体月份建议（如几月适合行动、几月有风险）时调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "要查询的年份，如2026"
                }
            },
            "required": ["year"]
        }
    }
}


def _format_liuyue_result(year: int, liuyue_list: list) -> str:
    """格式化流月数据为工具返回文本"""
    if not liuyue_list:
        return f"{year}年暂无流月数据"
    month_parts = []
    for lm in liuyue_list:
        if isinstance(lm, dict):
            m = lm.get('solar_month', '')
            mg = lm.get('month_ganzhi', '')
            mj = lm.get('judge', '')
            month_parts.append(f"{m}月({mg}){mj}")
    return f"{year}年流月吉凶：{' '.join(month_parts)}"


# ============================================================
# 历史消息压缩：从历史 assistant 消息（JSON）提取关键结论
# ============================================================

def _build_history_summary(history: list, max_rounds: int = 5) -> str:
    """从历史 assistant 消息提取关键结论，构建历史摘要文本。

    只保留最近 max_rounds 轮历史，避免 prompt 过长。

    每份历史报告提取：
    - opening.lead 前12字（开头句式，供本次避开雷同）
    - opening.verdict（核心结论）
    - subtopics[].title（各子问题结论标题）
    - summary 风格标签 + summary.items 或 summary.narrative（行动清单/总结）

    返回摘要文本，约200-400字/份。提取失败的历史消息跳过。
    """
    # 只取最近 max_rounds 轮 assistant 消息
    assistant_msgs = [msg for msg in history if msg.get("role") == "assistant"]
    recent_msgs = assistant_msgs[-max_rounds:] if len(assistant_msgs) > max_rounds else assistant_msgs

    summaries = []
    for i, msg in enumerate(recent_msgs):
        content = msg.get("content") or ""
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue  # 非 JSON（首次报告是 Markdown），跳过

        parts = []
        # 提取核心结论
        opening = data.get("opening") or {}
        lead = (opening.get("lead") or "").strip()
        verdict = opening.get("verdict")
        if lead:
            parts.append(f"上次开头句式：{lead[:12]}（本次开头必须换句式）")
        if verdict:
            parts.append(f"核心结论：{verdict}")

        # 提取各子问题结论标题
        subtopics = data.get("subtopics") or []
        titles = [st.get("title", "") for st in subtopics if st.get("title")]
        if titles:
            parts.append("已回答：" + "；".join(titles))

        # 提取行动清单 + 总结风格标签
        summary = data.get("summary") or {}
        style_hint = (summary.get("style_hint") or "").strip()
        items = summary.get("items") or []
        if items:
            item_texts = [f"{it.get('keyword', '')}({it.get('text', '')[:40]})" for it in items[:5]]
            parts.append("行动建议：" + "；".join(item_texts))
            if not style_hint:
                style_hint = "清单式"
        elif summary.get("narrative"):
            parts.append(f"总结：{summary['narrative'][:80]}")
            if not style_hint:
                style_hint = "段落叙事式"
        if style_hint:
            parts.append(f"上次总结风格：{style_hint}（本次总结必须换风格）")

        if parts:
            summaries.append(f"第{len(summaries) + 1}轮回答：" + " | ".join(parts))

    if not summaries:
        return ""
    return "\n".join(summaries)


# ============================================================
# 精简 prompt（只含命理逻辑 + JSON 结构示例，不含任何格式规则）
# ============================================================

def build_structured_prompt(context: dict, history_summary: str = "") -> str:
    """构建结构化追问 prompt：生活化叙事解读 + 固定JSON结构示例"""
    # 历史摘要区块：有摘要时插入，仅供话题承接，结论以命盘为准
    if history_summary:
        history_section = f"""

# 历史对话摘要（话题承接参考，结论以命盘为准）
{history_summary}
- 历史摘要仅供话题承接，不得作为结论依据；历史结论与命盘冲突时，以命盘为准，可在开篇说明"结合命盘重新看"
"""
    else:
        history_section = ""
    return f"""# 角色
职场人生顾问，以命盘当作参考依据，全程像真人给朋友出主意，优先讲故事、讲现实走向、给到落地行动方案。全程面向零基础小白，语言口语通俗、故事感充足；大白话叙事是主干（占90%以上），必要命理术语只作"命理出处标签"以括号形式点缀（如"外部压力较大（七杀）"），括号里只放术语名不解释意思，永远先抛出结论、预判现实遭遇、给到可执行做法，保留精准流年流月时间推演。

# 命盘数据
咨询时间：{context['current_time']}，{context['liunian_ganzhi']}流年{context['liunian_season']}
日主：{context['rizhu']}（{context['gender']}）
四柱：{context['sizu']}
旺衰：{context['wangshuai']}
格局：{context['geju_description']}
用神：{context['yongshen']}，忌神：{context['jishen']}
十神特征：{context['shishen_fenbu']}
五行分布：{context['wuxing_fenbu']}
地支作用：{context['dizhi_zuoyong']}
调候：{context['tiaohou_desc']}
当前大运：{context['current_dayun']}
大运解读：{context['dayun_jiedu']}
重点流年：{context['key_liunian']}
年龄：{context['age']}岁，{context['age_stage']}

# 命盘权威与方向锁定（最高优先级，无论有无历史摘要都生效）
- 命盘数据是最高推演依据，所有结论必须以命盘为准，不得臆造命盘未提供的大运、流月、十神
- 不盲从前轮判断：命盘与历史结论冲突时以命盘为准，可在开篇说明"结合命盘重新看"
- 严禁编造命理依据：narrative/reason 只能引用上文命盘数据栏已给出的信息
- 禁止自相矛盾（硬约束，最大硬伤，高频违规点，务必执行）：
  - **opening.verdict 必须从 subtopic 的实际细节中提炼**。生成顺序：先把每个子问题的细节走向想清楚写进 subtopic，再据此提炼 opening.verdict。禁止开篇另起炉灶给一个与正文细节打架的定论
  - **典型违规（出现即不合格）**：开篇说"不换组"，正文却讲"分到新组、换新领导"；开篇说"拿不到裁员大礼包"，正文却说"苟住能拿赔偿金"。开篇定论与正文细节字面冲突，会让用户彻底失去信任
  - **写完全部 subtopic 后强制回查**：逐条核对 opening.verdict 的每个分句是否与对应 subtopic 的 narrative 细节完全一致。发现冲突时**以正文细节为准修改 opening.verdict**（正文有命盘依据展开，开篇只是提炼），禁止反过来为迁就开篇而改正文
  - subtopic 之间、blocks 之间也必须逻辑自洽；若某年吉凶混合，要分阶段讲清"上半年稳、下半年风险升"而非前后打架
  - **单个 narrative 内部必须逻辑自洽，禁止为安抚而硬凑矛盾**：同一句话里不能一边说"换了新组、换了新领导"，一边又说"汇报线没动、只是物理位置挪了挪"——换领导就意味着汇报线变动，用"挪了挪"粉饰换组换领导是自相矛盾。事件是什么样就如实写，该严重就严重，不要为了降低严重性而塞入与事实冲突的轻描淡写
  - **关键词/标题必须正面回答用户问题，禁止答非所问**：keyword 与 narrative 内容必须是同一件事，禁止标题挂一个问法、正文答另一件事。常见混淆必须分清：
    - 用户问"换组/换岗/调岗"→ narrative **必须出现以下维度中至少2个**：职责（变没变/降没降级）、领导（换没换）、团队（动没动/分到新组）、汇报线（变没变）。这是正向约束——不关心你用什么词，但必须讲到这些组织维度。**禁止只讲物理位置（工位/座位/办公桌/位置挪了挪等任何物理位置描述）而不讲这些维度**；即使没出现"工位"这个词，只要没讲到职责/领导/团队/汇报线，就是答非所问
    - 用户问"工位在不在原地"→ 才答物理位置
    - 用户问"会不会被裁"→ 答裁员名额/被裁资格，不要答成"主动离职赔偿"
- 模糊预判术语必须定义边界（硬约束）：当用户问题含模糊概念（如"裁员大礼包""赔偿金""好结果""能成"），opening.verdict 给出判断时必须明确这个判断的具体所指。
  - **同义词等价识别（高频违规点）**：用户说的"裁员大礼包""赔偿金""补偿金""经济补偿"是同一回事（离开公司拿到的钱，是日常说法 vs 书面说法），**禁止拆成不同概念制造"拿不到裁员大礼包但能谈出补偿金"这种自相矛盾**——这等于说"拿不到赔偿金但能拿到赔偿金"。要么拿得到（讲清是被裁N+1还是协商补偿），要么拿不到，禁止用两个词指同一东西再制造对立
  - **裁员大礼包/赔偿金回答视角（高频违规点，用户视角优先）**：用户问"能不能拿到裁员大礼包/赔偿金"时，关心的是**"离开公司总体能拿到多少钱"**，不是"会不会被裁"。opening.verdict 必须从用户视角先给总体判断，再分路径：
    - 能拿到钱 → 直接说"能拿到"或"总体能拿到一笔钱"，再说明路径（如"通过协商离职谈补偿，不是被裁N+1"）
    - 拿不到钱 → 直接说"拿不到"，再说明原因
    - **禁止用"拿不到A（N+1）但能拿B（协商补偿）"的句式开头**——用户不区分N+1和协商补偿，"拿不到"放在前面会让用户以为"拿不到钱"。正确表述如"27年离开公司能拿到一笔补偿，路径是协商离职（不是被裁N+1）"
    - subtopic 展开时可以解释"为什么拿不到N+1"（不会被裁），但必须紧接着说"但能通过协商拿到补偿"或"所以总体能拿到钱"，不能让用户读完以为"拿不到钱"
  - 若需细分赔偿类型，必须先给总体判断再分路径，**禁止用"拿不到A（N+1）但能拿B（协商补偿）"的句式**。正确写法如："27年离开公司总体能拿到一笔钱，路径是协商离职给的补偿（不是被裁N+1）"——先说"能拿到"，再说路径，不让用户误以为"拿不到钱"
  - **通用高频模糊词二分定义（全场景适用，首次出现必须带定义）**：遇到模糊场景必须做"表层现象 vs 实质结果"二分，禁止笼统对错导致前后打脸：
    - 机会：浅层机会（有人找你聊/有苗头）vs 可落地实质机会（签约/入职/到账）
    - 变动：岗位微调（换组换领导但职责不变）vs 实质变动（降级/转岗/裁撤）
    - 破财：小额花销（日常消费/人情）vs 大额亏损（投资失败/被骗）
    - 和好：争吵内耗后缓和 vs 彻底分手后复合
    - 赚钱：有进账（副业有小钱）vs 实质收益（覆盖主业/可持续）
    - 禁止模糊词双面解读制造"前面说没有、后面又出现"的割裂
- 时间建议必须给因果依据（硬约束，三段闭环）：给出"X月是最佳时机/危险期/窗口期""适合/不适合X月"时，必须配套三段闭环解释：①**为什么这个时间最优/最危险**（基于流月吉凶/命盘喜忌/现实博弈节奏）；②**提前操作会有什么代价**（时机未到强动=踩坑/筹码不够/白费力气）；③**延后会错失什么/加重什么**（机会关闭/难度上升/需等下一窗口）。禁止只抛时间点不给依据，看似直白实则经不起追问；如"11月是谈离职黄金期"要讲清"11月进入吉月、公司年底裁员名额释放、此时谈筹码最大；提前到9月谈则名额未释放筹码不够；延后到次年3月则名额收紧、且错过吉月窗口"。**时间表达用公历月份窗口（如"11月上旬"），禁止用节气当行动节点**（如"立冬后""立秋后"），节气小白无感且无流月数据支撑
- **时间建议必须是未来时间（硬约束，高频违规点）**：所有行动建议的时间点必须**晚于咨询时间**（见命盘数据栏"咨询时间"）。用户8月问"几月拿offer"，说明当前还没拿到，建议必须是9月/10月/11月等未来月份，**禁止建议已过去的月份**（如"6月拿offer""5月准备"）。若流月数据显示过去的月份是吉月，只能作为"复盘参考"（如"6月确实是窗口但已过，现在要抓住下一个窗口"），不能作为行动建议。**命盘结果优先**：修正时必须从剩余月份的流月数据中找到下一个吉月作为建议，禁止随意改成未来月份——必须说清"为什么是这个月"（流月数据显示该月是吉月）。违反此规则=给用户一个无法执行的"穿越式建议"，严重损害可信度
- 结论与建议必须因果衔接，禁止断裂（硬约束，高频违规点）：开篇结论与行动建议之间必须有完整因果链，不能让用户产生"既然A为什么还要B"的困惑。**典型场景——离开公司与赔偿**：当结论是"拿不到裁员大礼包/赔偿金"且建议是"离开/离场"时，必须讲清：
  - ①"拿不到赔偿"具体指哪种情况：是纯主动离职（无赔偿）？还是协商也谈不拢？还是不会被裁所以等不到N+1？必须明确边界，禁止含糊
  - ②"离开"是哪种走法：纯主动走（无赔偿）还是协商走（可谈补偿）？若建议离开且能谈到钱，那是协商离职（公司同意给钱让你走，属赔偿性质），必须讲清"协商离职≠纯主动走"
  - ③既然拿不到赔偿还要走，主动走的理由是什么（避开28凶年/公司环境恶化/早走早占新坑），给出命盘依据
  - **禁止把"拿不到裁员大礼包"和"主动离场"简单并列而不解释为什么拿不到还要走**；更禁止"拿不到裁员大礼包但能谈出补偿金"这种同义词对立（裁员大礼包=补偿金，见上条同义词等价规则）
- 流年吉凶方向锁定（硬约束，禁止违背）：
  - 吉年（吉/大吉）→ 才能说"适合启动/推进/起色/有转机/可行动"
  - 凶年（凶/大凶）→ 只能说"慎入/避开/不宜启动/防守为主/缓一缓"
  - 禁止给凶年安排任何启动类行动（启动副业、跳槽、投资、开业、表白等）
  - 禁止把吉年说成"不宜/慎入"
  - 吉凶标签不可颠倒：凶年（凶/大凶）必须如实标注凶/大凶，禁止贴"小吉/回暖/向好/起色/回升/压力渐松/缓步回暖/逐步回暖"等正向标签；回暖只能从首个吉/平年开始算，禁止把凶年说成回暖起点
  - **段落级正向标签禁止（高频违规点，务必执行）**：当 subtopic 标题或narrative覆盖一段年份范围（如"2031-2036年"），只要范围内含任何一个凶年（凶/大凶），整段就禁止命名为"回暖期/缓步期/复苏期/蓄力期/回升期/回暖升温/缓步回升"等正向段落标签。多年份段落必须如实反映其中凶年状态，标题用"凶+吉"复合表述（如"2031-2033连凶、2035起转吉"），禁止用单一正向标签覆盖整段
  - 回暖/转吉的起点年份必须是吉/平年，禁止从凶年开始算（如2031辛亥是凶年，禁止说"2031起回暖"）
  - 具体月份建议必须基于流月吉凶数据，禁止自行推测月份
- 用神逻辑一致性（硬约束，禁止违背）：
  - 用神五行当令的吉年=帮身（如用神为火，火旺流年帮身利启动），禁止说成"X旺反耗/反激化耗损/太旺耗身/旺而耗身"等与用神冲突的逻辑；用神旺是帮扶不是消耗
  - 忌神五行当令的凶年=耗身，才能说耗损/消耗
  - 用神/忌神以命盘数据栏"用神""忌神"为准，禁止自行判定五行喜忌
- 吉年正向引导（当用户问启动类问题时）：命盘有吉年（吉/大吉）且用户问题含启动类意图（搞副业/跳槽/投资/创业/开业/找工作），吉年应给出"适合启动/可推进/有启动窗口"方向判断，禁止把吉年说成"不适合/不宜/不建议启动"
{history_section}
# 用户问题
{context['user_question']}

# 输出格式
请输出纯JSON（不要用```json代码块包裹，直接输出JSON文本），结构如下：

{{
  "opening": {{
    "lead": "开篇叙事(可选)。1-2句，可内联**加粗**重要词。开头必须先承接用户问题里的现实处境/情绪/核心关切（如'想跳又怕错过赔偿''副业能不能持续''9月返岗会不会换组'），再顺势引出结论，让用户感觉被接住。每次随机选一种开头风格，**严禁**以'直接说结论：''直接回答你：''直接给你结论：''结论是：'等模板化固定句式开头",
    "verdict": "核心结论(可选)。可包含多重总结要点（多个分句），不固定一句话，不强制以'核心结论'开头；若用'核心结论'开头，'核心结论'四字必须用**加粗**（如**核心结论**：...）；后面内容只加粗关键时间节点/结论词，禁止整段全加粗"
  }},
  "subtopics": [
    {{
      "title": "子问题标题，结论感叙事化标题，直接回应用户关切",
      "lead": "可选，1-2句承上启下或总结性引导，引出下面的内容",
      "blocks": [
        {{"type": "keyword", "keyword": "叙事化关键词，不加**号", "narrative": "仅讲单一维度，2-3句、≤120字，可内联**加粗**。大白话主干占90%以上，必要术语以括号标签形式带出（如'外部压力较大（七杀）'），括号里只放术语名作命理出处，不在括号里解释意思；主干大白话已说清现象，小白读主干就懂，括号术语可跳过"}},
        {{"type": "keyword", "keyword": "另一维度关键词", "narrative": "应对策略/时间窗口/心态宽慰各自独立一个block，禁止与剧本预测合并"}}
      ],
      "closing": "默认不输出。仅当能补充上面blocks没说过的新角度（真正有情绪价值的安抚、或一个新的嘱咐方向）时才输出2-3句朋友式话语。两类必须禁止：①把上面已讲过的结论换个说法再重复（如blocks已说'稳住别主动提离职'，closing就不能再写'稳住节奏就是赢'）；②空洞金句/口号式收尾（如'守得住基本盘才能接得住新风口'这类看似有道理但无具体信息、无真实情感的话）。没有真正想对朋友说的话，就留空，宁可没有也不要凑"
    }}
  ],
  "summary": {{
    "title": "总结动态副标题",
    "style_hint": "可选，风格描述",
    "lead": "可选引导语，在items前输出，可内联**加粗**",
    "items": [{{"keyword": "阶段名", "text": "描述"}}],
    "item_format": "可选，items渲染格式：list(列表式,默认)或paragraph(段落式,无前缀)",
    "narrative": "可选整段叙事(与items二选一)",
    "closing": "默认不输出。仅当能补充上面items/narrative没说过的新角度（真正有情绪价值的安抚、或一个新的嘱咐方向）时才输出2-3句朋友式话语。两类必须禁止：①把上面已讲过的结论换个说法再重复；②空洞金句/口号式收尾（如'守得住基本盘才能接得住新风口''稳住就是赢'这类看似有道理但无具体信息、无真实情感的话）。没有真正想对朋友说的话，就留空，宁可没有也不要凑"
  }}
}}

## 硬性JSON渲染约束（一条都不可改动，保障前端稳定渲染）
- **subtopics 必须一一对应用户问题中的子问题（硬约束，高频违规点）**：用户问了几个子问题，就生成几个 subtopic，禁止自行添加用户没问的子问题。例如用户问"几月拿offer、几月入职、新公司发展如何、涨薪如何"，就生成4个 subtopic 分别回答这4个问题，**禁止**额外添加"完整行动路线""从现在到入职"等用户没问的总结性子问题。行动路线/时间线/步骤清单属于 summary 的内容，不属于 subtopic
- opening的lead和verdict都可选，至少填一个
- blocks里每个subtopic放置2-4个block，每个block只讲一个现实维度（现实走向/应对办法/时间窗口/心态宽慰四选一）；严禁把剧本预测和应对策略塞进同一段narrative
- 单个keyword的narrative≤3句、不超过120字，超出立即拆成多个keyword block
- **同一subtopic内所有block必须统一用type=keyword**；禁止group块、禁止type=narrative纯叙事块、禁止空关键词当标题再挂下属段落。每个block必须keyword+narrative齐全，禁止出现"一段有keyword、另一段是光秃秃叙事"的定位不一致
- summary的items和narrative二选一
- keyword字段绝对禁止添加**号或任何Markdown符号（前端组件自动加粗）；keyword必须是叙事化概括（如"被动换组反而是好事""9月返岗坑位变动""签字拿赔偿金时机"），禁止使用"补充提示""补充说明""其他提示""额外建议""现实剧本预测"这类空洞无信息或过于宽泛的词，必须根据本段narrative内容提炼出具体现实结论
- 所有字符串值必须是单行，不能够直接换行；需要分段使用\\n\\n转义
- **禁止使用 term_explain 字段**；命理名词解释只能揉进句子当中，禁止单独段落解释术语
- sub_items使用规则（默认省略）：默认不输出 sub_items 字段。仅当同一关键词下有3个及以上并列的独立要点时才用 sub_items；1-2个短要点直接写进narrative并且**加粗**。绝大多数 keyword block 不需要 sub_items
- subtopic的lead是可选的承上启下引导段落（1-2句），在blocks前输出，引出下面内容。lead和closing都是subtopic独立字段，不是block，不占用blocks的keyword槽位
- **closing 硬约束（subtopic 和 summary 都适用，高频违规点，务必执行）**：
  - closing 默认留空（不输出）。仅当能补充上面 blocks/items 没说过的新角度（真正的情绪安抚、或一个新的嘱咐方向）时才输出 2-3 句朋友式话语
  - 禁止①：复述上面已讲过的结论（换个说法再讲一遍）。如 blocks 已说"稳住别主动提离职"，closing 不得再写"稳住节奏就是赢"
  - 禁止②：空洞金句/口号式收尾。如"守得住基本盘才能接得住新风口""谁先急谁就输"这类看似有道理但无具体信息、无真实情感的话
  - 判断标准：如果没有一句真正想对朋友说的、上面没讲过的话，就留空，宁可没有也不要凑

# 内容撰写硬性规范（本次重点优化板块，用来降低专业术语、强化故事叙事）
0. **具体数字问题处理**
- "具体数字"指金额（多少钱）、倍数（涨2倍）、具体日期（几号入职）——命理算不了
- **禁止在 opening.verdict 提示"命理只能给方向性判断，算不出具体数字"这类开场白**；opening.verdict 必须直接回答用户问题本身，不得用作命理局限性声明
- 改为在回答到那个具体数字问题时，**就地**说明"这个精度命盘算不了，只能看趋势"，再按命盘能答的方向回答（财运趋势/吉凶时段/适合行动的月份窗口），禁止编造具体数字
- "几月会发生"不属于具体数字问题：命盘可基于流月吉凶数据回答，给"有利/不利月份窗口"，但需提示"命理看月份趋势，不保证必然发生"
1. **子问题拆解（必须遵守）**
必须拆分多个 subtopic，拒绝整段长篇叙事。
拆解逻辑（这是逻辑对应，不是数数）：
   - **逐点对应**：用户问题里有几个独立关切点，就必须有对应的几个 subtopic 一一回应。每一个用户提出的独立问题都要有专门一块分析，禁止漏答、禁止把两个独立关切合并成一块带过。例如用户问"是否换组""是否裁员""何时离职""何时入职新公司"四件事，就要有四块分别回应，不能把"入职新公司"塞进"离职"里一笔带过
   - **判断"独立关切点"的方法**：看用户问的是不是两件不同的事（换组 vs 裁员 vs 离职 vs 入职），而不是看句子数量。同一件事的延伸追问（"何时离职"和"怎么离职"）可合并；两件不同的事必须分开
   - 拆完用户关切点后，可额外补充风险提示、时间路线、实操对策作为加餐 subtopic
   - **长跨度时间问题按时间段拆分**：当用户问题涉及较长时间跨度（如"未来10年""未来5年""今后事业"），优先按时间段拆分 subtopic（如2026-2027、2028-2029、2030-2032...），每个 subtopic 聚焦该时间段的事业走向+收入+行动建议，禁止把整个时间跨度塞进一个 subtopic 长篇叙事；标题用时间段+核心结论（如"2026-2027：返岗稳住期"）
   - 标题只讲现实结论，禁止八字、五行类标题；禁止写"长线剧情"字样
>示例：用户询问"26年9月返岗是否换组、27年是否裁员大礼包、最佳离职时间、最快入职新公司" → 用户提了四件不同的事，就有四个 subtopic 一一对应：
>① 9月返岗的岗位变动走向
>② 2027年裁员赔付时机与博弈
>③ 收益最高的主动离职规划
>④ 入职新公司的完整剧本（何时开始找、怎么找、新公司画像、最快入职时间）——这一块就是"未来剧本"，必须独立展开，禁止省略

1.5 **未来剧本（关键，当问题涉及"之后会怎样"时必须独立成块）**
当用户问题涉及未来行动或结果（如"什么时候能入职新公司""能不能找到新工作""开启副业后怎样"），必须把这一未来走向拆成独立 subtopic，并展开完整剧本，禁止只回答一个时间点。剧本必须覆盖四层维度：
   - **何时启动**（when-start）：什么时候开始筹备/投递/行动，依托流年流月吉凶数据给具体公历月份
   - **怎么进行**（how）：路径方式、渠道、关键动作（如"先悄悄更新简历→通过前同事内推→11月集中面试"），禁止只说"会有新机会"
   - **目标画像**（what-like）：新公司/新平台/新机会长什么样——平台大小、行业方向、薪资涨幅、团队氛围等具体画像，依托排盘喜忌给方向
   - **结果时间点**（when-land）：最快什么时候能落地入职/成交，给具体公历月份窗口
氛围要求：像给朋友讲故事一样把这段未来走向讲完整，有起承转合，让用户看到"从现在到入职新公司"的完整路径，而不是一个干巴巴的时间点。依托排盘数据，禁止胡编乱造，不加专业术语。

2. **结论前置**
opening.lead / verdict第一时间给出大白话最终答案，用户三秒之内获取核心判断；verdict里面关键时间、决定、风险点必须**加粗**

3. **开篇话术多样化（强制，违反即不合格）**
- **必须承接用户问题里的内容/情感/现状**：开头先一句话接住用户当下处境或纠结（如'想跳又怕错过赔偿''副业能不能持续''9月返岗后会不会换组'），再顺势引出结论。这是把'干巴巴结论'变成'有温度回应'的关键，禁止脱离用户语境直接抛结论
- **同人物多轮追问必须换开头**：若上方"历史对话摘要"里列出了"上次开头句式"，本次开头**必须换一种完全不同的句式**，禁止与历史开头句式雷同或近似（即使换了话题，句式骨架也不能照搬）。同一人物连续两次用同一种开头风格即不合格
- **每次随机选一种开头风格**，禁止连续两次报告用同一种：
  - 现状承接式（优先选用）：先一句话点出用户当前处境或纠结，再给结论。如'你在产假尾声纠结要不要趁今年布局副业——结论是**今年就该悄悄动手**，但能不能持续要看2028往后那三年。'
  - 痛点直击式：一句话点破核心矛盾。如'你真正纠结的不是今年能不能搞副业，而是这副业能不能撑过2028那波大凶年。结论是**今年可以动，但必须设计成可折叠模式**。'
  - 反常识提醒式：先反转认知再给结论。如'别被2026大吉带偏节奏——吉的是火气和合作运，不是让你辞职all in。**今年该悄悄埋线，5月就能动手试水**。'
  - 情绪共情式：先共情再给结论。如'你这段时间一边带娃一边想副业，确实累。但命盘给的答案是**今年值得动**，关键是别压上全部筹码。'
  - 结论直击式（仅当其他风格都不贴合时使用）：直接抛结论，但**禁止**用'直接说结论：''直接回答你：'等模板，句式必须自然。如'**2026年可以搞副业，5月、6月是黄金启动窗口**，但能不能持续要看2028-2030怎么熬。'
- **绝对禁止的固定开头模板**（出现即不合格）：'直接说结论：''直接回答你：''直接给你结论：''直接给你一个不加任何粉饰的结论：''结论是：''答案很明确：'以及任何以'直接+动词'开头的模板化句式
- **仍禁止时间节点/节气/大运交替式开头**：如'站在X月的节点''距离立秋只有几个小时''命运齿轮咬合'等

4. **术语管控 + 故事叙事（大白话主干 + 括号术语标签点缀）**
> 整体配比：大白话叙事是主干（占90%以上），命理术语只作"命理出处标签"以括号形式点缀（不超过10%）。术语带出形式：大白话现象在前，括号里只放术语名（如"外部压力较大（七杀）"），不在括号里解释术语意思，因为主干大白话已说清现象。小白读主干就懂，括号术语是给懂行的人看的出处，可跳过
- 术语密度约束：**一整段narrative最多1-2个术语标签**，每个以"大白话现象（术语名）"形式带出；禁止连续堆砌多个术语打断叙事
- **术语带出形式规则（务必参照）**：
  - ✅ 正确：大白话现象+括号术语标签——"外部压力较大（七杀）"、"你表达欲强适合做内容（日主丙火）"、"今年合作运旺（流年丙午）"、"适合内容/教育行业（命盘喜火土）"
  - ❌ 错误：术语在前+括号解释意思——"偏官（七杀，代表外部压力）"、"丙火（代表表达传播）"；这种形式术语打断主干，小白要先读括号才懂
  - ❌ 错误：术语裸用不带括号——"七杀旺"、"流年丙午吉"；术语直接出现小白看不懂
  - 判断标准：主干大白话是否能让小白读懂现象？是→括号补术语标签即可；否→纯大白话，不加术语
- **术语使用边界（允许 vs 禁止）**：
  - 允许以括号标签带出：十神名（七杀/正官/偏印等）、日主五行（日主丙火）、流年干支（流年丙午）、命盘喜忌（命盘喜火土）
  - 禁止出现（即使括号也不行）：干支纪时写法（丁酉月/丁未流年→改公历"2026年9月8日-10月8日""2027年"）、排盘术语（月令/宫位/日支/原局/命局/用神/忌神/流月）、玄学话术（火土余温/水气太重/水旺耗身/金气暗动）、作用关系堆砌短语（卯酉相冲/卯辰相害/相害/相刑/杀印相生/伤官见官/寅午半合火局/寅午半合/半合火局/六合绊/三会木局/天干透出/地支联动/X气暗动→改大白话"秋季岗位变动""有外部支持化解压力""暗中有人帮你"）
  - **高频违规术语黑名单（出现即不合格，必须替换成大白话）**：杀印相生、寅午半合火局、寅午半合、半合火局、六合绊用神、三会木局克身、天干透出X、地支X与X联动、X气暗动、X相冲、X相害、X相刑、X相生、X破印、伤官见官、卯酉相冲、卯辰相害；这些作用关系短语小白完全看不懂，必须改成"秋季有岗位变动""有外部资源化解压力""暗中有人帮你"等大白话
- 优先讲故事、剧本化描写：多描写当事人的情绪状态、公司管理层的套路手段、同事关系环境、利弊得失；多用生活化词汇：坑位、苟住、摸鱼、公司施压、拿到补偿、悄悄筹备副业
- **how维度（必须）**：对关键问题除了when（何时）和what（是什么），还要说清楚how（怎么发生、怎么做才稳）。当用户问题明确指向未来结果（如"何时入职新公司""能否找到新工作"），必须按上方第1.5条"未来剧本"独立成 subtopic 并展开四层维度，禁止缩成一句话时间点。依托排盘数据确保不乱推测，术语带出与整体术语管控一致
- 命理原因能省则省，需要提及时以"大白话现象（术语标签）"形式一句话带过立刻转回现实剧情；禁止逐层拆解五行作用、十神联动这类分析
- 术语不单独拿出来讲解，顺势以括号标签形式嵌进句子

5. **subtopic标题必须是现实结论**
只写人事、时机、利弊判断；禁止"财运解析、事业格局、七杀解读"这类抽象标题。
✅合格：9月返岗大概率迎来小组调动、2027秋季最容易下发裁员补偿、年底走人最利于之后副业发展

6. **keyword关键词全部为生活化词语**
绝对不可使用任何八字专业名词；可用关键词示例：现实剧本预判、关键时间节点、自保对策、安心定心提示、风险高发阶段、最佳行动窗口期。关键词必须和本段叙事内容保持一致，不能凭空新增信息。

7. **月份时间参考**
所有月份判断依托给到的排盘参数，不要自行脑补流月信息。
当需要具体月份的吉凶数据时，调用 `get_liuyue_detail` 工具获取（传入年份即可）。

8. **文字加粗规则**
narrative内的年月节点、关键行动、重要收益进行**加粗**；每一段最少一处加粗，不要整段文字加粗。

9. **篇幅控制**
单个keyword对应的narrative保持2-3句话、≤120字，语言紧凑，减少多余命理推演。

10. **总结部分风格轮换（强制，违反即不合格）**
summary分别采用行动清单、时间轴、阶段提醒、避坑清单、剧情演进多种风格，每次必须不同；items关键词全部采用生活化阶段名称。
- **同人物多轮追问必须换总结风格**：若上方"历史对话摘要"里列出了"上次总结风格"（如清单式/段落叙事式/时间轴/避坑清单等），本次总结**必须换一种完全不同的风格**，禁止与历史总结风格雷同。同一人物连续两次用同一种总结风格即不合格
- **items关键词必须是对该条text内容的叙事化总结**：概括这阶段在干什么/发生什么，禁止用"蹲守期""守业期""蛰伏期"这类脱离具体内容的泛泛阶段标签。正确做法是从 text 里提炼出"时间+具体事件/动作"（如 text 讲9月返岗坑位变动，keyword 写"9月返岗适应期"；text 讲27年谈赔偿金，keyword 写"27年赔偿金谈判期"），让用户看 keyword 就知道这阶段在干什么
- **禁止总结重复 subtopic 已讲过的内容（高频违规点）**：如果某个 subtopic 已经用 blocks 详细展开了行动路线/时间节点/步骤清单，summary 就**不得**再用 items 把同样的步骤重复一遍。summary 应该是更高层次的提炼（如"三个关键提醒""两个风险点""一句定心话"），或者换一个 subtopic 没讲过的角度（如心态建议、避坑提醒），而不是把 subtopic 的内容换个格式再列一遍。**判断标准**：summary.items 的 keyword 是否与某个 subtopic 的 blocks keyword 大量重叠（≥3个相同），若重叠则必须重写 summary

11. **block分层与同级格式统一规范**
- 同一个subtopic之下按现实维度拆分多个block：会发生什么/什么时候发生/该怎样处理/心理宽慰，每个维度独立一个keyword block
- **同级block格式必须完全一致**：同一subtopic内所有block统一用type=keyword（keyword+narrative齐全）。严禁出现三类混搭：①"定心丸"是keyword带内容、"精准时间窗口"却是空标题挂下属段落；②一段有keyword、另一段是type=narrative光秃秃叙事无keyword；③混用keyword与group
- **禁止type=narrative块**：subtopic内不允许出现纯叙事块（无keyword的整段文字）。每段内容都必须提炼一个叙事化keyword短语，再写narrative描述。例如整段"2027年底痛快签字拿走赔偿金，挥一挥衣袖..."不能直接当narrative块输出，必须拆成keyword="签字拿赔偿金时机"+narrative="..."
- **多时间节点处理**：每个时间节点（如第一波危险期、最终清算期）各自独立一个keyword block——keyword写节点名、narrative写该节点的现实遭遇+应对。禁止用group块或空关键词当总标题再挂下属段落
- narrative聚焦单一维度、2-3句、≤120字，禁止空洞简短也禁止堆砌；收尾感悟可单独一个keyword block（keyword写"定心提示"之类，narrative写宽慰话）

## 禁止清单（严格规避以下问题）
❌ 禁止术语裸用不带括号（如"七杀旺""流年丙午吉""火土耗身"），术语必须以"大白话现象（术语名）"形式带出
❌ 禁止"术语在前+括号解释意思"的形式（如"偏官（七杀，代表外部压力）""丙火（代表表达传播）"），必须改为"大白话现象（术语名）"
❌ 禁止一整段narrative出现2个以上术语标签，打断大白话主干叙事
❌ 禁止大篇幅解析五行生克、格局原理
❌ 禁止抽象玄学比喻代替现实描述
❌ 禁止关键词采用命理术语
❌ 禁止单独开辟一段解释专业名词
❌ 禁止同一subtopic内block类型混用（如keyword+group并存、keyword+narrative并存）
❌ 禁止用空关键词或group标题当小标题，再在下面挂下属段落
❌ 禁止type=narrative纯叙事块（无keyword的整段文字）；每段必须keyword+narrative齐全
❌ 禁止closing复述上面已讲过的结论（换个说法再讲一遍，如blocks已说"稳住别主动提离职"，closing又写"稳住节奏就是赢"）
❌ 禁止closing输出空洞金句/口号式收尾（如"守得住基本盘才能接得住新风口""谁先急谁就输"这类无具体信息、无真实情感的话）；没有真正想对朋友说的话就留空，宁可不要凑
❌ 禁止在 opening/subtopic/summary 任何位置出现"工位""物理位置""挪了挪"等物理位置描述（用户问换组只关心职责/领导/团队变动，不关心坐哪个工位）；summary 概括换组时必须用"换了领导/换了组/职责变了"等组织变动表述，禁止用"工位换了"

## 全报告统一适用声明（硬约束）
以上所有规则——开篇正文一致性、单段内部逻辑自洽、模糊预判术语定义边界、通用模糊词二分定义、同义词等价识别、时间因果三段闭环、结论与建议因果衔接、术语管控与黑名单、禁止用节气当行动节点、标题答非所问——**全报告统一适用，opening / subtopic / summary 三部分都必须遵守，summary 不设任何豁免域**。summary 的 title/lead/items.keyword/items.text/narrative/closing 都要接受同样的一致性校验、术语管控、同义词对立检测，不得在总结部分出现与 opening/subtopic 矛盾的结论、不得使用黑名单术语、不得出现同义词对立。

## 输出前自检（强制兜底，输出JSON前逐项核对，任何一项不过则改到过为止）
1. **无结论矛盾**：opening.verdict、subtopic narrative、summary 三部分字面一致，无"开篇说不换组、正文讲换新领导、总结又说稳住没动"这类跨部分冲突；单段内无"换领导又配汇报线没动"的自相矛盾；**summary.items 不得与 subtopic 结论打架**
2. **无概念模糊**：裁员大礼包/赔偿金/补偿金等同义词未拆成对立（含 summary）；机会/变动/破财/和好/赚钱等模糊词已做二分定义
3. **无无根判断**：所有时间建议有三段闭环（为什么最优/提前代价/延后错失）；所有结论有命盘数据支撑，未臆造大运流月十神
4. **无因果缺失**：结论与建议之间有完整因果链（如"拿不到赔偿还建议走"已讲清为什么）；结论与建议不割裂
5. **无术语堆砌**：opening/subtopic/summary 全部文本大白话主干占90%以上，术语以括号标签带出；无相冲/相害/相刑/破印等黑名单术语；无干支纪时（丁酉月→改公历）

## 对照示例（务必参照执行）

**❌错误写法1（术语堆砌+剧本策略混在同一段）：**
keyword="现实剧本预测"，narrative="2026年9月8日到10月8日处于丁酉月，地支酉与日支卯发生卯酉相冲（冲代表调岗换组）。但冲的是月令不是岗位宫位，所以你9月回去大概率坑位变了——公司秋季组织架构调整，你被分到新组换新领导。你只需安安静静把手头项目收尾，不主动申请调岗、不站队，就能平稳过渡到年底。"
>问题：术语超标（丁酉月/酉/卯/卯酉相冲/月令/岗位宫位）；剧本预测与应对策略混在一段，过长。

**✅正确写法1（拆成两个独立keyword block，术语清零，换组答职责/领导/团队不答工位）：**
block1: keyword="现实剧本预判", narrative="**9月8日到10月8日**这一个月，公司大概率在搞秋季组织架构调整。你回去后会发现自己**换了新领导、被分到新组**，汇报线跟着变了，但**核心职责没降级**，只是从最耗神的老业务线挪出来，不是贬职。"
block2: keyword="应对策略", narrative="这次被动换组反而帮你脱离最压抑的业务线。**安安静静把手头项目收尾**，不主动调岗、不站队，就能平稳过渡到年底，还能摸鱼搞副业。"
>要点：换组=领导/团队/汇报线变动（如实写，不为安抚硬凑"没动"）；问换组答职责领导，不答"物理位置挪了挪"；事件该怎样就怎样，不为降低严重性塞与事实冲突的轻描淡写。

**❌错误写法6（术语在前+括号解释意思，打断主干）：**
keyword="外部压力来源", narrative="你原局偏官（七杀，代表外部压力）贴身，加上流年丙午（火旺帮身），今年公司对你施压明显。建议苟住别硬刚，等2027年丁未（火土相生）运势平稳再谈跳槽。"
>问题：术语在前+括号解释意思（偏官/七杀/流年丙午/丁未/火土相生堆砌），小白要先读括号才懂，主干被打断；干支纪时（丁未）未转公历。

**✅正确写法6（大白话主干+括号术语标签点缀）：**
keyword="外部压力来源", narrative="你今年**外部压力明显加大（七杀）**，公司大概率用加KPI、边缘化逼你主动走。但今年也有**暗中帮你的资源（火旺帮身）**，别硬刚，苟住把手头活干漂亮就行。等**2027年运势平稳下来**再谈跳槽最划算。"
>要点：大白话主干讲清现象（外部压力加大/暗中帮你/运势平稳），术语只以括号标签点缀（七杀/火旺帮身），括号里不解释意思；干支纪时（丁未）转公历（2027年）。

**❌错误写法2（同级block格式不统一）：**
block1: keyword="定心丸", narrative="公司上半年一定用加KPI、PUA、边缘化逼你主动离职省赔偿金..."（keyword带内容）
block2: {{type:group, title:"精准时间窗口", paragraphs:["第一波危险期：8月7日-9月7日...","最终清算期：10月下旬..."]}}（空标题+下属段落）
>问题：定心丸是keyword有内容，精准时间窗口却是group空标题挂下属段落，同级格式不一致。

**✅正确写法2（同级统一为keyword block，时间节点各自独立）：**
block1: keyword="定心丸", narrative="公司上半年一定用加KPI、PUA、边缘化逼你主动离职省赔偿金，但火护着你（外部压力转成资源支持），**脸皮厚死死苟住，坚决不主动提离职**，坐等大刀落下。"
block2: keyword="第一波危险期", narrative="**2027年8月7日-9月7日**公司大概率启动优化名单筛选。你只需做到三点：不迟到早退、不碰合规红线、所有沟通留痕。"
block3: keyword="最终清算期", narrative="**2027年10月下旬**若遇HR谈话，务必以留任观望姿态应对，**切勿主动签协商解除协议**。你越稳，谈判筹码越大。"

**❌错误写法3（一段有keyword、另一段是narrative光秃秃叙事无keyword）：**
block1: keyword="精准时间窗口锁定", narrative="..."（有keyword）
block2: {{type:narrative, text:"2027年底痛快签字拿走赔偿金，挥一挥衣袖，回家开启副业闭环。新公司入职务必卡在11月中下旬..."}}（无keyword的纯叙事块）
>问题：block1有keyword定位、block2却是一整段光秃秃文字，同级定位不一致。

**✅正确写法3（两段都提炼keyword，定位统一）：**
block1: keyword="精准时间窗口锁定", narrative="离职交接最怕陷入年底拉扯期。**最佳离开时间卡在11月7日立冬之后至11月22日前后**，此时谈判筹码足，能无缝衔接新平台资源。"
block2: keyword="签字拿赔偿金时机", narrative="**2027年底痛快签字拿走赔偿金**，挥一挥衣袖回家开启副业闭环。新公司入职务必卡在11月中下旬，既能拿满年终奖，又能饱满切入新周期。"

**✅正确写法4（未来剧本：入职新公司独立 subtopic，展开四层维度，氛围感足）：**
subtopic title="最快入职新公司的完整路径"
block1: keyword="何时启动找工作", narrative="别等拿到赔偿金再投简历。**10月中旬就开始悄悄更新作品集**，通过前同事内推渠道放出风声。这时候流月对你的口有利，面试聊一个成一个。"
block2: keyword="怎么找最快上岸", narrative="优先走**前同事内推**，别海投。大厂HC冻结的窗口期，独角兽和垂直领域头部反而缺人。把目标锁在B轮以上、业务线能接住你专业壁垒的公司，谈薪时拿原薪资1.3倍起谈。"
block3: keyword="新公司长什么样", narrative="你命盘喜火土，新平台多半是**有内容/教育/文化属性的中小团队**，不是冷冰冰的大厂螺丝钉岗。团队扁平、话语权大，能让你一个人扛一条线，正好接住你想搞副业的野心。"
block4: keyword="最快入职时间窗口", narrative="**11月中下旬集中面试，12月初拿offer**，赶在年底前完成背调和入职。这样既不耽误原公司年终结算，又能新公司开年就上手新项目，无缝衔接。"
>要点：四层维度（启动时机/路径方式/目标画像/结果时间点）各自独立 keyword block，有起承转合的故事氛围，依托流年流月数据给具体月份，零术语。

**❌错误写法5（closing复述结论+空洞金句，高频违规点）：**
subtopic blocks已讲清楚"9月返岗会被动换组、稳住别主动提离职"
closing="稳住节奏，换组不换心。谁先急谁就输，你稳住就是赢。"
>问题：①"稳住节奏"是复述上面blocks已说过的"稳住别主动提离职"结论；②"谁先急谁就输""稳住就是赢"是空洞金句口号，无具体信息无真实情感。
>正确做法：这种情况下 closing 留空（不输出）。只有当能补一句上面没说过的、真正有情绪价值的话（如"你这几年憋屈够了，这次被动换组反而把你从最压抑的业务线里捞出来，往后的日子会松快不少"）才输出。
"""


# ============================================================
# JSON 容错提取（处理 LLM 输出的格式偏差）
# ============================================================

def _normalize_report_data(data):
    """LLM输出字段规范化：处理常见字段缺失/别名，提升Pydantic校验容错。

    qwen3.7-flash偶发输出keyword block缺narrative（用text/desc/content代替），
    或blocks缺type字段、summary items缺text等，导致Pydantic校验失败降级"报告格式异常"。
    此处做字段回退映射，将常见别名归一到schema字段名。
    """
    if not isinstance(data, dict):
        return data

    # subtopics 规范化
    for sub in data.get("subtopics") or []:
        if not isinstance(sub, dict):
            continue
        if not sub.get("title"):
            sub["title"] = sub.get("name") or sub.get("heading") or ""
        for blk in sub.get("blocks") or []:
            if not isinstance(blk, dict):
                continue
            btype = blk.get("type", "")
            # 缺type时根据字段推断
            if not btype:
                if "keyword" in blk or "narrative" in blk or "sub_items" in blk:
                    btype = blk["type"] = "keyword"
                elif "paragraphs" in blk:
                    btype = blk["type"] = "group"
                else:
                    btype = blk["type"] = "narrative"
            # keyword block: narrative/keyword/sub_items 字段回退
            if btype == "keyword":
                if not blk.get("narrative"):
                    blk["narrative"] = (blk.get("text") or blk.get("desc")
                                        or blk.get("content") or blk.get("description") or "")
                if not blk.get("keyword"):
                    blk["keyword"] = blk.get("title") or blk.get("name") or ""
                if "sub_items" not in blk and "items" in blk:
                    blk["sub_items"] = blk["items"]
            # narrative block: text 字段回退
            elif btype == "narrative":
                if not blk.get("text"):
                    blk["text"] = (blk.get("narrative") or blk.get("content")
                                   or blk.get("desc") or "")
            # group block: paragraphs/title 回退
            elif btype == "group":
                if not blk.get("paragraphs"):
                    blk["paragraphs"] = blk.get("content_list") or []
                if not blk.get("title"):
                    blk["title"] = blk.get("heading") or ""
        # group块展开为多个keyword block + 过滤空narrative的keyword block
        # 解决"精准时间窗口"等空标题挂下属段落的格式不统一：统一转成独立keyword block
        flattened = []
        for blk in sub.get("blocks") or []:
            if not isinstance(blk, dict):
                continue
            if blk.get("type") == "group":
                grp_title = (blk.get("title") or "").strip()
                for para in blk.get("paragraphs") or []:
                    para = (para or "").strip()
                    if not para:
                        continue
                    # 段落形如"第一波危险期：8月7日-9月7日..." → 拆出keyword和narrative
                    if "：" in para:
                        kw, narr = para.split("：", 1)
                    elif ":" in para:
                        kw, narr = para.split(":", 1)
                    else:
                        kw, narr = grp_title, para
                    flattened.append({"type": "keyword",
                                      "keyword": (kw.strip() or grp_title),
                                      "narrative": narr.strip()})
            elif blk.get("type") == "narrative":
                # narrative块转keyword块：保证同级格式统一（避免"一段有keyword、一段光秃秃"）
                txt = (blk.get("text") or blk.get("narrative")
                       or blk.get("content") or blk.get("desc") or "").strip()
                if not txt:
                    continue
                if "：" in txt:
                    kw, narr = txt.split("：", 1)
                elif ":" in txt:
                    kw, narr = txt.split(":", 1)
                else:
                    # 取第一个子句（，。！；前）作keyword，过长/过短则用通用关键词
                    end = len(txt)
                    for sep in ("，", "。", "！", "；"):
                        idx = txt.find(sep)
                        if 0 <= idx < end:
                            end = idx
                    kw = txt[:end].strip()
                    narr = txt[end:].lstrip("，。！；: 、").strip()
                    if len(kw) > 16 or len(kw) < 3 or not narr:
                        kw, narr = "补充提示", txt
                flattened.append({"type": "keyword",
                                  "keyword": kw.strip(),
                                  "narrative": narr.strip()})
            else:
                flattened.append(blk)
        # 过滤掉 keyword 类型但 narrative 为空的 block（避免前端显示孤立空关键词如"定心丸"无内容）
        sub["blocks"] = [blk for blk in flattened
                         if not (blk.get("type") == "keyword"
                                 and not (blk.get("narrative") or "").strip())]

    # summary items 规范化
    summary = data.get("summary")
    if isinstance(summary, dict):
        # title 缺失兜底：LLM偶发只输出 narrative/items 漏掉 title，导致整个报告 Pydantic 校验失败降级
        # 从已有内容动态提取标题，避免写死"总结"
        if not summary.get("title"):
            summary["title"] = _extract_summary_title(summary)
        for item in summary.get("items") or []:
            if not isinstance(item, dict):
                continue
            if not item.get("text"):
                item["text"] = item.get("desc") or item.get("content") or item.get("description") or ""
            if not item.get("keyword"):
                item["keyword"] = item.get("name") or item.get("title") or ""
        # 过滤空 text 的 item：LLM 偶发生成只有 keyword 没有 text 的空 item，前端渲染会出现空白行
        if summary.get("items"):
            summary["items"] = [
                item for item in summary["items"]
                if isinstance(item, dict) and (item.get("text") or "").strip()
            ]

    # opening 回退：lead/verdict 都缺时从 conclusion/summary 回退
    opening = data.get("opening")
    if isinstance(opening, dict) and not opening.get("lead") and not opening.get("verdict"):
        opening["lead"] = opening.get("conclusion") or opening.get("summary") or ""

    # closing 金句兜底清理：LLM（qwen-plus）指令遵循能力不足，常输出空洞金句/口号式 closing，
    # 即使 prompt 已三层禁止仍不遵守。此处后端强制检测并清空，不依赖 LLM 自觉。
    _clean_slogan_closings(data)

    return data


def _extract_summary_title(summary: dict) -> str:
    """LLM 漏 summary.title 时，从已有内容动态提取标题，避免写死"总结"。

    提取优先级：
    1. items 非空：取首个 item 的 keyword 作为标题基础
    2. narrative 非空：取首句（第一个句号/感叹号/问号/换行前），去加粗标记，截断到16字
    3. 都没有：降级"总结"
    """
    items = summary.get("items") or []
    if items and isinstance(items[0], dict):
        kw = (items[0].get("keyword") or "").strip()
        if kw:
            return kw

    narrative = (summary.get("narrative") or "").strip()
    if narrative:
        # 取首句
        first_sent = narrative
        for sep in ("。", "！", "？", "\n"):
            idx = first_sent.find(sep)
            if 0 <= idx < len(first_sent):
                first_sent = first_sent[:idx]
        # 去加粗标记和首尾空白
        first_sent = first_sent.replace("**", "").strip()
        # 截断到 16 字，过长加省略号
        if len(first_sent) > 16:
            first_sent = first_sent[:16] + "…"
        if first_sent:
            return first_sent

    return "总结"


# closing 金句检测：匹配口号词或过短无信息 closing，返回 True 表示应清空
_SLOGAN_WORDS = (
    "才是", "就是赢", "守得住", "稳住就是", "风口", "基本盘", "谁先急",
    "抢得先机", "输不起", "赢得", "不换心",
)


def _is_slogan_closing(text: str) -> bool:
    """判断 closing 是否为空洞金句/口号式收尾，是则应清空。"""
    text = (text or "").strip()
    if not text:
        return False  # 已经是空，不需要清
    # 含口号词 → 金句
    if any(w in text for w in _SLOGAN_WORDS):
        return True
    # 过短（<12字）且不含具体月份/数字/行动词 → 多半是金句
    if len(text) < 12:
        _info_words = ("月", "日", "年", "offer", "离职", "入职", "面试", "投", "签", "谈", "苟", "收尾", "筹备")
        if not any(w in text for w in _info_words):
            return True
    return False


def _clean_slogan_closings(data: dict) -> None:
    """清空所有 subtopic 和 summary 的金句 closing（数据层兜底）。"""
    if not isinstance(data, dict):
        return
    for sub in data.get("subtopics") or []:
        if isinstance(sub, dict) and _is_slogan_closing(sub.get("closing", "")):
            sub["closing"] = ""
    summary = data.get("summary")
    if isinstance(summary, dict) and _is_slogan_closing(summary.get("closing", "")):
        summary["closing"] = ""


def _extract_and_fix_json(raw: str) -> str:
    """容错提取 JSON：截取第一个完整JSON对象 + 去掉markdown包裹 + 修复字符串值裸换行"""
    text = raw.strip()

    # 第一层：去掉 ```json ... ``` 包裹
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # 第二层：截取第一个完整的 JSON 对象（处理超长重复输出）
    start_idx = text.find("{")
    if start_idx < 0:
        return text

    depth = 0
    in_string = False
    escape_next = False
    end_idx = -1
    for i, ch in enumerate(text[start_idx:], start_idx):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break

    if end_idx > start_idx:
        text = text[start_idx:end_idx]
    else:
        text = text[start_idx:]

    # 第三层：修复 JSON 字符串值里的裸换行
    result = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == "\\":
            result.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if ch == "\n" and in_string:
            result.append("\\n")
            continue
        result.append(ch)

    return "".join(result)


# ============================================================
# 排查日志辅助：打印报告结构详情（subtopics 数量/标题/closing）
# ============================================================

def _log_report_structure(data: dict, stage: str) -> None:
    """打印报告结构关键信息，便于排查拆解数量、closing空洞金句等问题。

    打印内容：
    - subtopics 数量 + 每个 subtopic 的 title / closing 字段值
    - summary 的 title / closing 字段值
    - 检测 closing 是否为空（理想状态）/ 是否疑似空洞金句（含"才是""就是赢""守得住"等口号词）
    """
    if not isinstance(data, dict):
        logger.info(f"[StructuredFollowup][排查][{stage}] data非dict, 类型={type(data).__name__}")
        return

    # 打印 opening 的 lead/verdict，便于对照开篇结论与各 subtopic 细节是否矛盾
    opening = data.get("opening") or {}
    if isinstance(opening, dict):
        o_lead = opening.get("lead", "")
        o_verdict = opening.get("verdict", "")
        logger.info(
            f"[StructuredFollowup][排查][{stage}] opening: lead={o_lead!r}, verdict={o_verdict!r}"
        )

    subtopics = data.get("subtopics") or []
    logger.info(f"[StructuredFollowup][排查][{stage}] subtopics数量={len(subtopics)}")

    _slogan_words = ("才是", "就是赢", "守得住", "稳住就是", "输不起", "赢得", "风口", "基本盘")

    for i, sub in enumerate(subtopics):
        if not isinstance(sub, dict):
            continue
        title = sub.get("title", "")
        closing = sub.get("closing", "")
        closing_status = "空(理想)" if not closing else "有内容"
        if closing:
            closing_status += f", 疑似金句={any(w in closing for w in _slogan_words)}"
        blocks = sub.get("blocks") or []
        block_keywords = [b.get("keyword", "") for b in blocks if isinstance(b, dict)]
        logger.info(
            f"[StructuredFollowup][排查][{stage}] subtopic[{i}] title={title!r}, "
            f"blocks={len(blocks)} keywords={block_keywords}, "
            f"closing={closing!r} ({closing_status})"
        )

    summary = data.get("summary") or {}
    if isinstance(summary, dict):
        s_title = summary.get("title", "")
        s_closing = summary.get("closing", "")
        s_closing_status = "空(理想)" if not s_closing else "有内容"
        if s_closing:
            s_closing_status += f", 疑似金句={any(w in s_closing for w in _slogan_words)}"
        logger.info(
            f"[StructuredFollowup][排查][{stage}] summary title={s_title!r}, "
            f"closing={s_closing!r} ({s_closing_status})"
        )


# ===== 方向锁定事后兜底：凶年启动类行动检测 =====
# 启动类关键词（凶年出现这些词且无否定修饰=违规）
_UNFAVORED_STARTUP_KEYWORDS = [
    # 副业类（口语变体全覆盖：搞/做/干/开/启动/开始）
    "启动副业", "开始副业", "副业起盘", "做副业", "搞副业", "干副业", "开副业",
    # 创业类
    "启动创业", "开始创业", "创业启动", "创业开干", "搞创业", "做创业",
    # 跳槽/换工作类
    "跳槽", "换工作", "辞职创业", "辞职跳槽",
    # 投资/开业类
    "投资", "开业", "开新店", "启动新业务", "开始新项目", "launch",
]
# 否定语境标记（启动词前10字内出现这些词则不算违规，如"不宜启动副业""严禁跳槽"）
_UNFAVORED_NEGATE_MARKS = [
    "不宜", "不适合", "慎", "避开", "暂缓", "推迟", "压后", "别", "勿",
    "禁止", "严禁", "不建议", "缓一缓", "不要", "不可", "不是好时机",
    "不靠", "不能", "无法", "切勿", "切忌", "杜绝", "严防", "拒绝",
]
import re as _re
_YEAR_PATTERN = _re.compile(r"(\d{4})年?")


def _get_unfavored_years(analysis_data: dict) -> list:
    """从命盘重点流年提取凶年（judge 含'凶'的年份）"""
    years = []
    for y in analysis_data.get("重点流年", []) or []:
        if not isinstance(y, dict):
            continue
        judge = y.get("judge", "") or ""
        if "凶" in judge:
            yr = y.get("year")
            if yr:
                try:
                    years.append(int(yr))
                except (ValueError, TypeError):
                    pass
    return years


def _get_favored_years(analysis_data: dict) -> list:
    """从命盘重点流年提取吉年（judge 含'吉'，包括大吉/吉/吉（注意））。

    对称于 _get_unfavored_years。"吉（注意）"本质是吉年带提醒，按吉年处理。
    """
    years = []
    for y in analysis_data.get("重点流年", []) or []:
        if not isinstance(y, dict):
            continue
        judge = y.get("judge", "") or ""
        if "吉" in judge:
            yr = y.get("year")
            if yr:
                try:
                    years.append(int(yr))
                except (ValueError, TypeError):
                    pass
    return years


def _detect_favored_year_discouraged_actions(data: dict, favored_years: list) -> list:
    """检测吉年+否定启动词组合（吉年方向锁定颠倒）。

    对称于 _detect_unfavored_year_actions 的镜像：
    - 凶年检测：启动词前无否定词 → 违规（凶年不该启动）
    - 吉年检测：启动词前有否定词 → 违规（吉年不该劝退启动）

    判定：启动词归属年份（文本内无年份用 subtopic title 上下文）是吉年，
    且启动词前10字内出现否定词（不宜/不适合/不建议等）→ 违规。
    例如 "2026不适合启动副业" "2026年不建议搞副业" 均违规。

    不检测吉年+模糊负向词（阻力/耗损/不宜单字），避免误伤"吉年但某月有阻力"这类合理表述。
    """
    if not favored_years:
        return []
    favored_set = set(favored_years)
    violations = []
    skip_non_negate = []  # 吉年+启动词但无否定词（正确表述，日志用）
    skip_non_favored = []  # 启动词归属非吉年（日志用）
    texts = _collect_report_texts(data)
    for path, text, ctx_year in texts:
        year_matches = list(_YEAR_PATTERN.finditer(text))
        for kw in _UNFAVORED_STARTUP_KEYWORDS:
            idx = text.find(kw)
            while idx != -1:
                # 定位启动词归属年份：取启动词前最近的年份，无则用上下文年份
                nearest_year = None
                for m in year_matches:
                    if m.start() < idx:
                        try:
                            nearest_year = int(m.group(1))
                        except ValueError:
                            pass
                    else:
                        break
                if nearest_year is None:
                    nearest_year = ctx_year
                if nearest_year is not None and nearest_year in favored_set:
                    # 吉年+启动词：检查前10字是否有否定词
                    before = text[max(0, idx - 10):idx]
                    matched_neg = [n for n in _UNFAVORED_NEGATE_MARKS if n in before]
                    if matched_neg:
                        snippet = text[max(0, idx - 12):idx + len(kw) + 12]
                        violations.append(f"{path}: 吉年{nearest_year}+否定词{matched_neg}+'{kw}' (原文:...{snippet}...)")
                        break
                    else:
                        skip_non_negate.append(f"{path}: 吉年{nearest_year}+'{kw}' 无否定词(正确表述)")
                elif nearest_year is not None:
                    skip_non_favored.append(f"{path}: 年{nearest_year}(非吉)+'{kw}'")
                idx = text.find(kw, idx + 1)
    if skip_non_negate or skip_non_favored:
        logger.info(
            f"[StructuredFollowup][方向锁定-吉年检测] 命中启动词但跳过: "
            f"吉年无否定(正确)={len(skip_non_negate)}项, 非吉年跳过={len(skip_non_favored)}项"
        )
        for s in skip_non_negate[:5]:
            logger.info(f"  [吉年正确] {s}")
        for s in skip_non_favored[:5]:
            logger.info(f"  [非吉年跳过] {s}")
    return violations


def _collect_report_texts(data: dict) -> list:
    """收集报告所有文本字段，返回 [(路径, 文本, 上下文年份), ...]。
    上下文年份：subtopic title 解析出的年份，用于该 subtopic 内 block 文本无年份时兜底。
    """
    texts = []
    opening = data.get("opening") or {}
    if isinstance(opening, dict):
        for k in ("lead", "verdict"):
            t = opening.get(k, "") or ""
            if t:
                texts.append((f"opening.{k}", t, None))
    for i, sub in enumerate(data.get("subtopics") or []):
        if not isinstance(sub, dict):
            continue
        title = sub.get("title", "") or ""
        ctx_year = None
        m = _YEAR_PATTERN.search(title)
        if m:
            try:
                ctx_year = int(m.group(1))
            except ValueError:
                pass
        if title:
            texts.append((f"subtopic[{i}].title", title, None))
        for j, b in enumerate(sub.get("blocks") or []):
            if not isinstance(b, dict):
                continue
            kw = b.get("keyword", "") or ""
            nar = b.get("narrative", "") or ""
            if kw:
                texts.append((f"subtopic[{i}].block[{j}].keyword", kw, ctx_year))
            if nar:
                texts.append((f"subtopic[{i}].block[{j}].narrative", nar, ctx_year))
            for it in b.get("items") or []:
                if isinstance(it, dict):
                    for ik in ("keyword", "narrative"):
                        it_t = it.get(ik, "") or ""
                        if it_t:
                            texts.append((f"subtopic[{i}].block[{j}].item.{ik}", it_t, ctx_year))
                elif isinstance(it, str) and it:
                    texts.append((f"subtopic[{i}].block[{j}].item", it, ctx_year))
        closing = sub.get("closing", "") or ""
        if closing:
            texts.append((f"subtopic[{i}].closing", closing, ctx_year))
    summary = data.get("summary") or {}
    if isinstance(summary, dict):
        for k in ("title", "closing", "narrative", "lead"):
            t = summary.get(k, "") or ""
            if t:
                texts.append((f"summary.{k}", t, None))
        for idx, it in enumerate(summary.get("items") or []):
            if isinstance(it, dict):
                for ik in ("keyword", "text"):
                    it_t = it.get(ik, "") or ""
                    if it_t:
                        texts.append((f"summary.items[{idx}].{ik}", it_t, None))
    return texts


def _detect_unfavored_year_actions(data: dict, unfavored_years: list) -> list:
    """检测报告里凶年+启动类关键词组合（排除否定语境）。
    判定：启动词前面最近的年份（文本内无年份则用 subtopic title 上下文年份）是凶年，
    且启动词前10字内无否定词 → 违规。
    """
    if not unfavored_years:
        return []
    unfavored_set = set(unfavored_years)
    violations = []
    skip_negate = []  # 因否定语境跳过的命中（日志用）
    skip_non_unfavored = []  # 因年份非凶年跳过的命中（日志用）
    texts = _collect_report_texts(data)
    for path, text, ctx_year in texts:
        year_matches = list(_YEAR_PATTERN.finditer(text))
        for kw in _UNFAVORED_STARTUP_KEYWORDS:
            idx = text.find(kw)
            while idx != -1:
                nearest_year = None
                for m in year_matches:
                    if m.start() < idx:
                        try:
                            nearest_year = int(m.group(1))
                        except ValueError:
                            pass
                    else:
                        break
                if nearest_year is None:
                    nearest_year = ctx_year
                if nearest_year is not None and nearest_year in unfavored_set:
                    before = text[max(0, idx - 10):idx]
                    matched_neg = [n for n in _UNFAVORED_NEGATE_MARKS if n in before]
                    if matched_neg:
                        skip_negate.append(f"{path}: 凶年{nearest_year}+'{kw}' 否定词={matched_neg} 前置文='{before}'")
                    else:
                        snippet = text[max(0, idx - 12):idx + len(kw) + 12]
                        violations.append(f"{path}: 凶年{nearest_year}+'{kw}' (原文:...{snippet}...)")
                        break
                elif nearest_year is not None:
                    skip_non_unfavored.append(f"{path}: 年{nearest_year}(非凶)+'{kw}'")
                idx = text.find(kw, idx + 1)
    if skip_negate or skip_non_unfavored:
        logger.info(
            f"[StructuredFollowup][方向锁定-启动检测] 命中关键词但跳过: "
            f"否定语境跳过={len(skip_negate)}项, 非凶年跳过={len(skip_non_unfavored)}项"
        )
        for s in skip_negate[:5]:
            logger.info(f"  [否定跳过] {s}")
        for s in skip_non_unfavored[:5]:
            logger.info(f"  [非凶年跳过] {s}")
    return violations


# 吉凶标签颠倒检测：凶年被贴正向标签（小吉/回暖/向好等）
_FAVORED_LABEL_KEYWORDS = [
    "小吉", "回暖", "向好", "起色", "回升", "压力渐松",
    "缓步回暖", "逐步回暖", "转吉", "起吉", "吉年",
]


# 正向标签后跟年份的指示词（如"回暖要等到2037年"→ 主体年份是后面的2037，不是前面的）
_LABEL_AFTER_YEAR_MARKS = ["等到", "要等", "从", "在", "至", "到", "始于", "起于"]


def _detect_favored_label_on_unfavored_year(data: dict, unfavored_years: list) -> list:
    """检测凶年是否被贴正向标签（小吉/回暖/向好等），吉凶标签颠倒。
    判定逻辑：
    0. 范围表达检测：标签前后30字内有"start-end"年份范围（如"2031-2036年：缓步回暖期"），
       只要范围内含任何一个凶年 → 违规（段落级正向标签）
    1. 优先看正向标签词后面15字内是否有年份，且中间含"等到/从/在/至"等指示词
       → 用后面的年份作为主体（处理"回暖要等到2037年"这种句式）
    2. 否则用正向标签词前面最近的年份（文本内无年份用subtopic title上下文）
    主体年份是凶年 → 违规。
    """
    if not unfavored_years:
        return []
    unfavored_set = set(unfavored_years)
    violations = []
    skip_after_year = []  # 因后置年份非凶年跳过（日志用）
    skip_non_unfavored = []  # 因前置年份非凶年跳过（日志用）
    # 范围表达正则：2031-2036 / 2031—2036 / 2031至2036 / 2031到2036 / 2031~2036
    _RANGE_PATTERN = _re.compile(r'(\d{4})\s*[-—~至到]\s*(\d{4})')
    texts = _collect_report_texts(data)
    for path, text, ctx_year in texts:
        year_matches = list(_YEAR_PATTERN.finditer(text))
        for kw in _FAVORED_LABEL_KEYWORDS:
            idx = text.find(kw)
            while idx != -1:
                kw_end = idx + len(kw)
                # 0. 范围表达检测：标签前15字内有年份范围，范围紧邻标签（中间无"凶"字），
                # 且范围内含凶年 → 违规（段落级正向标签，如"2031-2036年：缓步回暖期"）
                # 排除"2026-2030年大凶，2031起回暖"这种范围是描述凶年的正确表述
                before_window = text[max(0, idx - 15):idx]
                range_matches_before = list(_RANGE_PATTERN.finditer(before_window))
                range_hit_years = []
                if range_matches_before:
                    last_range = range_matches_before[-1]
                    between_text = before_window[last_range.end():]
                    # 范围和标签之间有"凶"字 → 范围是描述凶年的，不是标签的修饰对象，跳过范围检测
                    if "凶" not in between_text:
                        try:
                            ry1 = int(last_range.group(1))
                            ry2 = int(last_range.group(2))
                            lo, hi = (ry1, ry2) if ry1 <= ry2 else (ry2, ry1)
                            for y in range(lo, hi + 1):
                                if y in unfavored_set and y not in range_hit_years:
                                    range_hit_years.append(y)
                        except ValueError:
                            pass
                if range_hit_years:
                    snippet = text[max(0, idx - 12):idx + len(kw) + 15]
                    violations.append(f"{path}: 凶年范围{range_hit_years}+'{kw}' (原文:...{snippet}...)")
                    break
                # 1. 先看标签后面15字内是否有年份+指示词（如"回暖要等到2037年"）
                after_window = text[kw_end:kw_end + 15]
                subject_year = None
                year_source = None  # 记录年份来源（日志用）
                after_year_m = _YEAR_PATTERN.search(after_window)
                if after_year_m:
                    between = after_window[:after_year_m.start()]
                    matched_marks = [m for m in _LABEL_AFTER_YEAR_MARKS if m in between]
                    if matched_marks:
                        try:
                            subject_year = int(after_year_m.group(1))
                            year_source = f"后置年份(指示词={matched_marks}, 间隔文='{between}')"
                        except ValueError:
                            pass
                # 2. 没有后置年份指示，用前面最近的年份
                if subject_year is None:
                    for m in year_matches:
                        if m.start() < idx:
                            try:
                                subject_year = int(m.group(1))
                            except ValueError:
                                pass
                        else:
                            break
                    if subject_year is not None:
                        year_source = "前置年份"
                if subject_year is None:
                    subject_year = ctx_year
                    if subject_year is not None:
                        year_source = "上下文年份(subtopic title)"
                if subject_year is not None and subject_year in unfavored_set:
                    snippet = text[max(0, idx - 12):idx + len(kw) + 15]
                    violations.append(f"{path}: 凶年{subject_year}+'{kw}' (原文:...{snippet}...)")
                    break
                elif subject_year is not None:
                    if year_source and "后置" in year_source:
                        skip_after_year.append(f"{path}: '{kw}' 主体=年{subject_year}({year_source}) → 非凶年,正确跳过")
                    else:
                        skip_non_unfavored.append(f"{path}: '{kw}' 主体=年{subject_year}({year_source or '未知'}) → 非凶年")
                idx = text.find(kw, idx + 1)
    if skip_after_year or skip_non_unfavored:
        logger.info(
            f"[StructuredFollowup][方向锁定-标签检测] 命中标签词但跳过: "
            f"后置年份跳过={len(skip_after_year)}项, 非凶年跳过={len(skip_non_unfavored)}项"
        )
        for s in skip_after_year[:5]:
            logger.info(f"  [后置年份跳过] {s}")
        for s in skip_non_unfavored[:5]:
            logger.info(f"  [非凶年跳过] {s}")
    return violations


# ===== 命理逻辑兜底检测：用神矛盾 / 术语黑名单 / 干支纪时 =====

# 用神五行字 → 别名映射（命盘"用神"字段可能是单字或带描述）
_YONGSHEN_WUXING_CHARS = ("火", "水", "木", "金", "土")
# 旺类词（用神+旺本是帮身，配合耗类词才违规）
_WANG_WORDS = ("旺", "太旺", "过旺", "旺盛", "旺相")
# 耗类词（与用神旺搭配即逻辑矛盾：用神旺不可能耗身）
_HAO_WORDS = ("耗", "损", "激化", "消耗", "泄", "泄气", "耗身", "耗损")


def _detect_yongshen_logic_conflict(data: dict, yongshen: str) -> list:
    """检测用神逻辑矛盾：用神五行+旺+耗损 共现 = 违规。

    命理硬逻辑：用神当令=帮身，用神旺是帮扶不是消耗。
    LLM 常脑补"火太旺反激化耗损""水旺耗身"等与用神冲突的逻辑（prompt 约束失效时）。

    判定：文本里出现用神五行字，且其前后8字窗口内同时出现旺类词和耗类词 → 违规。
    例如用神火时，"火太旺反激化内部耗损" → 火+太旺+激化+耗损 共现 → 违规。
    误伤控制：单纯"火旺帮身利启动"（火+旺但无耗类词）不违规。
    """
    if not yongshen:
        return []
    # 从用神字段提取五行字（可能是"火"或"火、土"或"火土"）
    ys_chars = [c for c in yongshen if c in _YONGSHEN_WUXING_CHARS]
    if not ys_chars:
        return []
    violations = []
    texts = _collect_report_texts(data)
    for path, text, _ctx in texts:
        for ys_char in ys_chars:
            # 找用神五行字的所有出现位置
            idx = text.find(ys_char)
            while idx != -1:
                # 取前后8字窗口
                window_start = max(0, idx - 8)
                window_end = min(len(text), idx + 9)
                window = text[window_start:window_end]
                has_wang = any(w in window for w in _WANG_WORDS)
                has_hao = any(h in window for h in _HAO_WORDS)
                if has_wang and has_hao:
                    snippet = text[max(0, idx - 6):idx + 12]
                    violations.append(f"{path}: 用神'{ys_char}'+旺+耗损 共现 (原文:...{snippet}...)")
                    break  # 同一文本同一用神字只记一次
                idx = text.find(ys_char, idx + 1)
    if violations:
        logger.info(
            f"[StructuredFollowup][用神逻辑检测] 用神={yongshen}({ys_chars}), "
            f"逻辑矛盾违规={len(violations)}项"
        )
        for v in violations[:5]:
            logger.info(f"  [用神矛盾] {v}")
    return violations


# 术语黑名单：出现即违规（小白完全看不懂，必须替换成大白话）
# 固定短语（零误伤）+ 子串词（低误伤）
_FORBIDDEN_TERMS = [
    # 完整短语（prompt L229 高频违规黑名单）
    "杀印相生", "寅午半合火局", "寅午半合", "半合火局", "六合绊用神",
    "三会木局克身", "伤官见官", "卯酉相冲",
    # 常见地支相冲组合（带地支的完整短语，零误伤）
    "子午相冲", "辰戌相冲", "丑未相冲", "寅申相冲", "巳亥相冲",
    # 常见地支相害组合（带地支的完整短语，零误伤）
    "子未相害", "丑午相害", "寅巳相害", "卯辰相害", "申亥相害", "酉戌相害",
    # 子串词（narrative 里不该裸用，出现即该转大白话）
    "破印", "气暗动", "天干透出", "地支联动", "相害", "相刑",
    # 玄学话术（完整短语，零误伤）
    "正印护体", "火土余温", "水气太重", "水旺耗身", "金气暗动",
    # 物理位置描述（用户问换组不关心工位，全报告禁止出现）
    "工位", "物理位置", "挪了挪",
]


def _detect_forbidden_terms(data: dict) -> list:
    """检测术语黑名单：narrative 出现杀印相生/寅午半合火局/伤官见官等 = 违规。

    这些作用关系短语小白完全看不懂，prompt 已禁但 LLM 常违规。
    零误伤设计：只检测明确的作用关系短语和排盘术语，不检测单字（如"冲""生"）。
    """
    violations = []
    texts = _collect_report_texts(data)
    for path, text, _ctx in texts:
        for term in _FORBIDDEN_TERMS:
            if term in text:
                idx = text.find(term)
                snippet = text[max(0, idx - 8):idx + len(term) + 8]
                violations.append(f"{path}: 出现禁用术语'{term}' (原文:...{snippet}...)")
    if violations:
        logger.info(f"[StructuredFollowup][术语黑名单检测] 违规={len(violations)}项")
        for v in violations[:8]:
            logger.info(f"  [禁用术语] {v}")
    return violations


# 干支纪时正则：天干+地支+(月|流年)，如 丁酉月、丁未流年
_GANZHI_TIME_PATTERN = _re.compile(
    r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥](月|流年)"
)


def _detect_ganzhi_time_notation(data: dict) -> list:
    """检测干支纪时写法：narrative 出现 丁酉月/丁未流年 = 违规。

    prompt 要求干支纪时改公历（丁酉月→2026年9月8日-10月8日，丁未流年→2027年），
    LLM 常直接搬用命盘数据栏的干支记法。零误伤：天干+地支+月/流年 的组合只用于纪时。
    """
    violations = []
    texts = _collect_report_texts(data)
    for path, text, _ctx in texts:
        for m in _GANZHI_TIME_PATTERN.finditer(text):
            matched = m.group(0)
            idx = m.start()
            snippet = text[max(0, idx - 8):idx + len(matched) + 8]
            violations.append(f"{path}: 干支纪时'{matched}' (原文:...{snippet}...)")
    if violations:
        logger.info(f"[StructuredFollowup][干支纪时检测] 违规={len(violations)}项")
        for v in violations[:8]:
            logger.info(f"  [干支纪时] {v}")
    return violations


# ===== 同义词对立矛盾检测 =====
# 用户语境里"裁员大礼包""赔偿金""补偿金""经济补偿"是同一回事（离开公司拿到的钱）
# LLM 常拆成两个概念制造"拿不到裁员大礼包但能谈出补偿金"的自相矛盾，prompt 约束失效，需代码兜底
# 否定词（配"裁员大礼包"出现=拿不到）
_SYNONYM_NEG_WORDS = ("拿不到", "没有", "得不到", "无", "没戏", "拿不了", "拿不着", "拿不到手")
# 肯定词（配"补偿金/赔偿金"出现=能拿到）
_SYNONYM_POS_WORDS = ("谈出", "能谈", "能拿", "拿到", "有", "可谈", "可以谈", "能争取", "谈下来", "协商", "可协商", "能协商", "可争取", "能要到", "要得到")


def _detect_synonym_contradiction(data: dict) -> list:
    """检测同义词对立矛盾：裁员大礼包=赔偿金=补偿金，禁止"拿不到A但能拿B"。

    用户语境里这些词指同一回事（离开公司拿到的钱），LLM 常拆成两个概念制造对立。
    prompt 约束失效（已验证多轮仍违规），需代码兜底拦截并触发重试。

    判定：同一文本里同时出现"裁员大礼包"和（补偿/赔偿 子串，覆盖补偿金/赔偿金/经济补偿/谈出一笔补偿等所有变体），
    且"裁员大礼包"附近8字窗口有否定词（拿不到/没有），
    同时"补偿/赔偿"附近8字窗口有肯定词（谈出/能拿/协商）→ 违规。
    误伤控制：要求否定和肯定分别绑定不同同义词，不误伤"裁员大礼包就是赔偿金"这种解释性表述。
    子串检测设计：LLM 常在重试时换说法绕过完整词检测（如"补偿金"→"补偿"），
    用子串"补偿""赔偿"能覆盖所有变体，不再靠枚举完整词打地鼠。
    """
    violations = []
    texts = _collect_report_texts(data)
    for path, text, _ctx in texts:
        if not text or "裁员大礼包" not in text:
            continue
        # 检测同义词共现：裁员大礼包 + 补偿/赔偿（子串，覆盖所有变体）
        other_syns = [w for w in ("补偿", "赔偿") if w in text]
        if not other_syns:
            continue
        # 检测"裁员大礼包"附近是否有否定词
        idx_dali = text.find("裁员大礼包")
        window_dali = text[max(0, idx_dali - 8):idx_dali + 12]
        has_neg = any(neg in window_dali for neg in _SYNONYM_NEG_WORDS)
        if not has_neg:
            continue
        # 检测"补偿金/赔偿金"附近是否有肯定词
        pos_word = ""
        for syn in other_syns:
            idx_syn = text.find(syn)
            window_syn = text[max(0, idx_syn - 8):idx_syn + 12]
            for pos in _SYNONYM_POS_WORDS:
                if pos in window_syn:
                    pos_word = syn
                    break
            if pos_word:
                break
        if pos_word:
            snippet = text[max(0, idx_dali - 6):idx_dali + 30]
            violations.append(
                f"{path}: 同义词对立矛盾——'裁员大礼包'带否定 + '{pos_word}'带肯定 "
                f"(原文:...{snippet}...)。裁员大礼包=赔偿金=补偿金，是同一回事，"
                f"禁止'拿不到A但能拿B'的对立"
            )
    if violations:
        logger.info(f"[StructuredFollowup][同义词对立检测] 违规={len(violations)}项")
        for v in violations[:5]:
            logger.info(f"  [同义词对立] {v}")
    return violations


# ===== 维度覆盖检测（通用答非所问检测） =====
# 不靠黑名单枚举禁止词（黑名单是打地鼠，LLM 换说法就绕过），
# 而是检测"应该说的维度说了没有"——当 subtopic 涉及组织变动时，
# narrative 必须包含职责/领导/团队/汇报线维度，否则可能是只讲了物理位置
# 组织变动关键词（subtopic title 含这些词时触发维度覆盖检测）
_ORG_CHANGE_KEYWORDS = ("换组", "换岗", "调岗", "返岗", "小组调动", "组织架构", "架构调整", "小组调动")
# 组织维度词（narrative 必须包含至少一个，否则可能是答非所问）
_ORG_DIMENSION_WORDS = (
    "职责", "岗位", "工作内容", "工作范围", "KPI", "降级", "贬职", "核心职责", "职责没变", "职责变",
    "领导", "上司", "主管", "经理", "老板", "新领导", "换了领导",
    "团队", "部门", "小组", "新组", "业务线", "分到新组", "换了组",
    "汇报线", "汇报",
)


def _detect_dimension_coverage(data: dict) -> list:
    """维度覆盖检测：subtopic 涉及组织变动时，narrative 必须包含职责/领导/团队/汇报线维度。

    通用答非所问检测——不靠黑名单枚举禁止词（LLM 换说法如"座位换了""办公桌挪了"就绕过），
    而是检测"应该说的维度说了没有"。当 subtopic title 含"换组/换岗/调岗"时，
    narrative 必须包含组织维度词（职责/领导/团队/汇报线），
    否则可能是只讲了物理位置而没讲组织维度，属于答非所问。

    误伤控制：只在 title 明确含组织变动关键词时触发，且 narrative 完全不含任何维度词才标记违规。
    """
    violations = []
    for i, sub in enumerate(data.get("subtopics") or []):
        if not isinstance(sub, dict):
            continue
        title = sub.get("title", "") or ""
        if not any(kw in title for kw in _ORG_CHANGE_KEYWORDS):
            continue
        all_text = title
        for b in sub.get("blocks") or []:
            if isinstance(b, dict):
                all_text += " " + (b.get("keyword", "") or "") + " " + (b.get("narrative", "") or "")
                for it in b.get("items") or []:
                    if isinstance(it, dict):
                        all_text += " " + (it.get("keyword", "") or "") + " " + (it.get("text", "") or "")
        has_dimension = any(dim in all_text for dim in _ORG_DIMENSION_WORDS)
        if not has_dimension:
            snippet = all_text[:60]
            violations.append(
                f"subtopic[{i}] title='{title}': 维度覆盖不足——narrative 未出现职责/领导/团队/汇报线"
                f"任何组织维度词，可能只讲了物理位置（工位/座位等）而答非所问 "
                f"(文本片段:{snippet}...)"
            )
    if violations:
        logger.info(f"[StructuredFollowup][维度覆盖检测] 违规={len(violations)}项")
        for v in violations[:5]:
            logger.info(f"  [维度覆盖] {v}")
    return violations


def _detect_summary_duplication(data: dict) -> list:
    """总结重复检测：summary.items 的 keyword 不得与 subtopic blocks keyword 大量重叠。

    高频违规场景：subtopic 已用 blocks 展开行动路线（5月准备期/6月面试期/...），
    summary 又用 items 把同样的步骤重复一遍，用户看到两块几乎一样的内容。

    判断标准：summary.items 的 keyword 与任一 subtopic 的 blocks keyword 重叠≥3个即违规。
    """
    violations = []
    summary = data.get("summary") or {}
    summary_items = summary.get("items") or []
    if not summary_items or not isinstance(summary_items, list):
        return violations

    # 提取 summary items 的 keyword 集合
    summary_keywords = set()
    for item in summary_items:
        if isinstance(item, dict):
            kw = (item.get("keyword") or "").strip()
            if kw:
                summary_keywords.add(kw)

    if len(summary_keywords) < 3:
        return violations  # summary items 太少，不检测

    # 检查每个 subtopic 的 blocks keyword
    for i, sub in enumerate(data.get("subtopics") or []):
        if not isinstance(sub, dict):
            continue
        block_keywords = set()
        for b in sub.get("blocks") or []:
            if isinstance(b, dict):
                kw = (b.get("keyword") or "").strip()
                if kw:
                    block_keywords.add(kw)

        # 计算重叠
        overlap = summary_keywords & block_keywords
        if len(overlap) >= 3:
            violations.append(
                f"summary 与 subtopic[{i}] title='{sub.get('title', '')}' 内容重复："
                f"重叠keyword={list(overlap)[:5]}，summary 不得重复 subtopic 已展开的步骤"
            )

    if violations:
        logger.info(f"[StructuredFollowup][总结重复检测] 违规={len(violations)}项")
        for v in violations[:3]:
            logger.info(f"  [总结重复] {v}")
    return violations


def _detect_past_month_suggestions(data: dict, current_month: int) -> list:
    """过去月份建议检测：行动建议的时间点不得早于咨询月份。

    高频违规场景：用户8月问"几月拿offer"，报告建议"6月拿offer"（已过去的月份）。
    用户还没拿到offer，建议必须是未来月份，不能是已过去的月份。

    检测逻辑：
    1. 提取 subtopic blocks 和 summary items 的 keyword 中的月份
    2. 若月份 < 当前咨询月份，且 keyword 含行动类词（准备/拿/入职/面试/谈/签），则违规
    """
    violations = []
    if not current_month or current_month < 1 or current_month > 12:
        return violations

    # 行动类关键词（表示"建议做某事"而非"复盘"）
    ACTION_WORDS = ["准备", "拿", "入职", "面试", "谈", "签", "投", "启动", "开始", "行动", "offer", "跳槽", "离职"]

    def check_keyword(kw: str, location: str) -> bool:
        """检查 keyword 是否含过去月份+行动词"""
        if not kw:
            return False
        # 提取月份（如 "6月准备期" -> 6）
        import re
        month_match = re.search(r'(\d{1,2})月', kw)
        if not month_match:
            return False
        month = int(month_match.group(1))
        if month >= current_month:
            return False  # 未来月份，OK
        # 检查是否含行动词
        has_action = any(w in kw for w in ACTION_WORDS)
        if has_action:
            violations.append(
                f"{location}: keyword='{kw}' 建议{month}月行动，但当前已是{current_month}月，"
                f"该月份已过去，用户无法执行'穿越式建议'"
            )
            return True
        return False

    # 检查 subtopic blocks
    for i, sub in enumerate(data.get("subtopics") or []):
        if not isinstance(sub, dict):
            continue
        for j, b in enumerate(sub.get("blocks") or []):
            if isinstance(b, dict):
                check_keyword(b.get("keyword", ""), f"subtopic[{i}].block[{j}]")

    # 检查 summary items
    summary = data.get("summary") or {}
    for j, item in enumerate(summary.get("items") or []):
        if isinstance(item, dict):
            check_keyword(item.get("keyword", ""), f"summary.items[{j}]")

    if violations:
        logger.info(f"[StructuredFollowup][过去月份检测] 违规={len(violations)}项")
        for v in violations[:5]:
            logger.info(f"  [过去月份] {v}")
    return violations


# ===== LLM 矛盾检测（语义层矛盾，枚举检测覆盖不了的场景） =====
# 用 qwen-flash 做矛盾检测，覆盖：
# 1. 开篇与正文矛盾（"不换组" vs "换了新领导"——相似度高但语义相反）
# 2. 同义词对立（"拿不到A但能拿B"——需要领域知识理解A=B）
_LLM_CHECK_MODEL = "qwen-flash"  # 轻量快模型，延迟约2-5秒


def _detect_llm_contradiction(data: dict) -> list:
    """LLM 矛盾检测：用 qwen-flash 判断 opening 与各 subtopic narrative 是否语义矛盾。

    覆盖枚举检测无法覆盖的语义层矛盾：
    1. 开篇与正文矛盾：opening说"不换组"，subtopic说"换了新领导"——相似度高但语义相反
    2. 同义词对立：opening说"拿不到裁员大礼包"，subtopic说"能谈出补偿金"——需理解裁员大礼包=补偿金

    用 openai 同步客户端调用 qwen-flash，延迟约2-5秒。
    如果调用失败（模型不可用/超时），降级返回空列表（不阻塞主流程）。
    """
    try:
        from openai import OpenAI
        from app.services.ai_service import model_pool

        if not model_pool:
            return []

        model_config = model_pool[0]
        client = OpenAI(api_key=model_config.api_key, base_url=model_config.base_url, max_retries=0)

        # 收集 opening 所有文本
        opening = data.get("opening") or {}
        opening_verdict = " ".join([v for v in opening.values() if isinstance(v, str) and v])
        if not opening_verdict:
            return []

        # 收集各 subtopic 的 narrative
        pairs = []
        for i, sub in enumerate(data.get("subtopics") or []):
            if not isinstance(sub, dict):
                continue
            narratives = []
            for b in sub.get("blocks") or []:
                if isinstance(b, dict):
                    kw = b.get("keyword", "") or ""
                    nar = b.get("narrative", "") or ""
                    if kw or nar:
                        narratives.append(f"{kw}：{nar}")
            narrative_text = " ".join(narratives)
            if narrative_text:
                pairs.append((i, sub.get("title", ""), narrative_text))

        if not pairs:
            return []

        # 构造矛盾检测 prompt（一次调用检测所有文本对）
        pairs_text = ""
        for idx, (i, title, narrative) in enumerate(pairs):
            pairs_text += (
                f"文本对{idx + 1}：\n"
                f"A（开篇结论）：{opening_verdict[:200]}\n"
                f"B（正文细节-{title}）：{narrative[:300]}\n\n"
            )

        check_prompt = (
            "你是矛盾检测专家。请判断以下文本对是否存在语义矛盾（前后说法相反/对立）。\n\n"
            f"{pairs_text}\n"
            "判断标准（严格区分'矛盾'和'一致'）：\n"
            "- A说\"不换组\" B说\"换了新领导/被分到新组\" → 矛盾（A说不换，B说换了，前后相反）\n"
            "- A说\"不换组\" B说\"职责没变/汇报线没变/继续做原来的事\" → 不矛盾（两者都在说'没变化'，B是在补充说明为什么没换）\n"
            "- A说\"不换组\" B说\"公司架构微调但你的岗没动\" → 不矛盾（结论一致，都在说'你没换'）\n"
            "- A说\"拿不到裁员大礼包\" B说\"能谈出补偿金\" → 矛盾（裁员大礼包=补偿金=赔偿金，同一回事，不能说'拿不到A但能拿B'）\n"
            "- A说\"总体能拿到钱\" B说\"通过协商谈补偿\" → 不矛盾（两者一致）\n\n"
            "关键规则：\n"
            "- 只有当A和B的说法直接相反（A说不、B说是；或A说有、B说没有）才算矛盾\n"
            "- 如果A说'不换组'，B说'职责没变/没动/继续做原来的事'，这是在补充说明'为什么没换'，不是矛盾\n"
            "- 如果A说'拿不到X'，B说'能拿到Y'，且X和Y是同一回事（如裁员大礼包=补偿金），才算矛盾\n\n"
            "请返回JSON：\n"
            '{"results": [{"pair": 1, "contradiction": true, "reason": "A说不换组，B说换了新领导，前后矛盾"}]}\n\n'
            "只返回有矛盾的文本对，无矛盾的不需要列出。"
        )

        start = time.time()
        response = client.chat.completions.create(
            model=_LLM_CHECK_MODEL,
            messages=[{"role": "user", "content": check_prompt}],
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"},
            timeout=30,
            extra_body=build_llm_extra_body(_LLM_CHECK_MODEL),
        )
        elapsed = time.time() - start

        # 兼容不同 endpoint 的响应格式：标准格式用 choices，部分自定义 endpoint 用 text 字段
        if response.choices:
            raw = response.choices[0].message.content or ""
        else:
            raw = getattr(response, "text", None) or ""
        logger.info(
            f"[StructuredFollowup][LLM矛盾检测] 模型={_LLM_CHECK_MODEL}, "
            f"耗时={elapsed:.1f}s, 文本对={len(pairs)}, 返回={raw[:300]}"
        )

        result = json.loads(raw)
        contradictions = result.get("results", [])

        # 代码层修正：检查 reason 是否真的表示"不矛盾"
        # 注意：不能用简单的 "一致" 子串匹配，因为 "不一致" 也包含 "一致"
        # 需要检查关键词前是否有否定前缀（不/非/未/没）
        _NO_CONTRADICTION_KEYWORDS = ["不矛盾", "无矛盾", "没有矛盾", "一致", "相同", "相符", "吻合"]
        _NEGATION_PREFIXES = ("不", "非", "未", "没")

        def _reason_says_no_contradiction(reason: str) -> bool:
            """检查 reason 是否表示'不矛盾'，避免'不一致'被误匹配为'一致'"""
            for kw in _NO_CONTRADICTION_KEYWORDS:
                idx = reason.find(kw)
                if idx == -1:
                    continue
                # 检查关键词前是否有否定前缀（如"不一致"中的"一致"）
                if idx > 0 and reason[idx - 1] in _NEGATION_PREFIXES:
                    continue  # 被否定了（如"不一致"），不算"不矛盾"
                return True
            return False

        violations = []
        for c in contradictions:
            if c.get("contradiction"):
                pair_idx = c.get("pair", 0) - 1
                if 0 <= pair_idx < len(pairs):
                    i, title, _ = pairs[pair_idx]
                    reason = c.get("reason", "")
                    # 代码层修正：如果 reason 真的表示"不矛盾"，覆盖为 false
                    if _reason_says_no_contradiction(reason):
                        logger.info(
                            f"[StructuredFollowup][LLM矛盾检测] 代码层修正: "
                            f"contradiction=true 但 reason 表示不矛盾，覆盖为false "
                            f"(pair={pair_idx+1}, reason={reason[:100]})"
                        )
                        continue
                    violations.append(
                        f"LLM矛盾检测: opening vs subtopic[{i}]'{title}' → {reason}"
                    )

        if violations:
            logger.info(f"[StructuredFollowup][LLM矛盾检测] 违规={len(violations)}项")
            for v in violations[:5]:
                logger.info(f"  [LLM矛盾] {v}")
        else:
            logger.info(f"[StructuredFollowup][LLM矛盾检测] 违规=0项（无矛盾）")

        return violations

    except Exception as e:
        logger.warning(
            f"[StructuredFollowup][LLM矛盾检测] 调用失败，降级跳过: "
            f"{type(e).__name__}: {str(e)[:200]}"
        )
        return []


# ============================================================
# 结构化追问生成（主入口）
# ============================================================

async def generate_followup_structured(
    analysis_data: Dict,
    gender: str,
    birth_date: str,
    birth_time: str,
    location: str,
    user_question: str,
    history: List[dict],
    longitude: float,
    latitude: float,
) -> AsyncGenerator[str, None]:
    """
    结构化追问报告生成：
    1. 构建命盘上下文 + 精简 prompt
    2. 调用 LLM（response_format=json_object，非流式）
    3. 容错提取 + Pydantic 校验
    4. yield JSON 字符串（一次性，非流式）

    返回的 JSON 字符串可直接存库，前端解析后用 React 组件渲染。
    """
    # 现场重算命盘（加异常兜底，排盘失败不崩溃）
    from app.skills.orchestrator import generate_full_analysis
    from app.services.chart_validator import validate_chart_data, get_chart_fingerprint
    gender_cn = "男" if gender in ("male", "男") else "女"
    try:
        analysis_data = generate_full_analysis(
            birth_date=birth_date,
            birth_time=birth_time,
            longitude=longitude,
            latitude=latitude,
            gender=gender_cn,
            location=location,
        )
    except Exception as e:
        logger.error(
            f"[StructuredFollowup] generate_full_analysis 异常: {type(e).__name__}: {e}"
        )
        analysis_data = {}  # 降级为空，后续校验会记录所有字段缺失

    # 命盘数据完整性校验（代码层 check，不依赖 prompt）
    chart_ok, missing = validate_chart_data(analysis_data)
    if not chart_ok:
        # 关键字段（日主/四柱/用神/当前大运）缺失升 error，便于重点排查；其余 warning
        _CRITICAL_FIELDS = {"日主", "四柱", "用神", "当前大运"}
        _log_fn = logger.error if any(m in _CRITICAL_FIELDS for m in missing) else logger.warning
        _log_fn(
            f"[StructuredFollowup] 命盘数据缺失: {missing}，降级生成（缺失字段在prompt标注），"
            f"指纹: {get_chart_fingerprint(analysis_data)}"
        )
    else:
        logger.info(
            f"[StructuredFollowup] 命盘校验通过, 指纹: {get_chart_fingerprint(analysis_data)}"
        )

    # 1. 构建命盘上下文
    context = _build_context_vars(
        analysis_data=analysis_data,
        gender=gender,
        user_question=user_question,
        birth_date=birth_date,
    )
    logger.info(
        f"[StructuredFollowup][排查] 命盘上下文构建: 日主={context.get('rizhu')}, "
        f"用神={context.get('yongshen')}, 忌神={context.get('jishen')}, "
        f"当前大运={context.get('current_dayun')}, "
        f"重点流年={str(context.get('key_liunian', ''))[:120]}"
    )

    # 1.5 提取流月数据供 function calling 使用（不再写入 prompt）
    key_liunian_raw = analysis_data.get("重点流年", [])
    liuyue_data = _extract_liuyue_data(key_liunian_raw)
    logger.info(f"[StructuredFollowup][排查] 流月数据提取: 年份={list(liuyue_data.keys())}")

    # 1.6 解析当前咨询月份（用于"过去月份建议"检测）
    import re as _re
    current_month = 0
    current_time_str = context.get("current_time", "")
    month_match = _re.search(r'(\d{1,2})月', current_time_str)
    if month_match:
        current_month = int(month_match.group(1))
    logger.info(f"[StructuredFollowup][排查] 当前咨询月份: {current_month}月")

    # 2. 历史消息压缩：从历史 assistant 消息（JSON）提取关键结论作为摘要
    history_summary = _build_history_summary(history)

    # 3. 构建精简 prompt（含历史摘要区块 + 命盘权威与方向锁定）
    system_prompt = build_structured_prompt(context, history_summary=history_summary)

    # 4. 构建 messages：history 已压缩为摘要注入 system_prompt，messages 只传当前问题
    # 不再传完整 history 到 messages 数组，避免上下文超限 + 输出雷同
    _orig_chars = sum(len((m.get("content") or "")) for m in history)
    logger.info(
        f"[StructuredFollowup][排查] history压缩: 原始{len(history)}条/{_orig_chars}字 → "
        f"摘要{len(history_summary)}字"
    )
    if history_summary:
        logger.info(f"[StructuredFollowup][排查] 历史摘要内容(前500字): {history_summary[:500]}")
    else:
        logger.info("[StructuredFollowup][排查] 历史摘要为空（首轮追问无历史）")

    messages = [{"role": "user", "content": user_question}]
    logger.info(
        f"[StructuredFollowup][排查] messages构造: roles={[m['role'] for m in messages]}, "
        f"用户问题长度={len(user_question)}, system_prompt长度={len(system_prompt)}"
    )

    # 5. 调用 LLM（复用 ai_service 的 model_pool，取第一个可用模型）
    if not model_pool:
        logger.error("[StructuredFollowup] model_pool为空: AI模型未配置，返回错误JSON")
        yield json.dumps({"opening": {"lead": "AI模型未配置"}, "subtopics": [], "summary": {"title": "错误"}}, ensure_ascii=False)
        return
    model_config = model_pool[0]
    client = await get_client(model_config)

    logger.info(f"[StructuredFollowup] 开始生成, 模型={model_config.name}, 问题: {user_question[:50]}..., prompt长度: {len(system_prompt)}")

    # 排查日志①：确认 prompt 是否包含新规则关键词（避免缓存/旧代码未生效）
    _rule_checks = {
        "未来剧本": "未来剧本" in system_prompt,
        "closing硬约束": "closing 硬约束" in system_prompt,
        "逐点对应": "逐点对应" in system_prompt,
        "守得住基本盘反例": "守得住基本盘" in system_prompt,
        "禁止清单closing项": "禁止closing复述" in system_prompt,
        "错误写法5反例": "错误写法5" in system_prompt,
        "历史摘要区块": "历史对话摘要" in system_prompt,
        "一致性要求": "一致性要求" in system_prompt,
    }
    logger.info(f"[StructuredFollowup][排查] prompt规则关键词存在性: {_rule_checks}")
    # 新增：确认"命盘权威"新一致性措辞是否进 prompt（修复错误传染后必须为 True）
    _consistency_checks = {
        "命盘权威": "命盘数据是最高推演依据" in system_prompt,
        "以命盘为准可修正": "以命盘为准" in system_prompt,
        "不盲从前轮": "不盲从前轮判断" in system_prompt,
        "严禁编造命理依据": "严禁编造命理依据" in system_prompt,
    }
    logger.info(f"[StructuredFollowup][排查] 新一致性措辞存在性(修复错误传染): {_consistency_checks}")
    # 确认开篇与正文一致性、模糊术语定义、时间因果依据三条新规则是否进 prompt
    _verdict_consistency_checks = {
        "开篇正文一致性": "opening.verdict 必须从 subtopic 的实际细节中提炼" in system_prompt,
        "写完回查": "写完全部 subtopic 后强制回查" in system_prompt,
        "模糊术语定义边界": "模糊预判术语必须定义边界" in system_prompt,
        "通用模糊词二分定义": "通用高频模糊词二分定义" in system_prompt,
        "时间因果三段闭环": "三段闭环" in system_prompt,
        "禁用节气当行动节点": "禁止用节气当行动节点" in system_prompt,
        "单段内部逻辑自洽": "单个 narrative 内部必须逻辑自洽" in system_prompt,
        "标题答非所问": "关键词/标题必须正面回答用户问题" in system_prompt,
        "结论建议因果衔接": "结论与建议必须因果衔接" in system_prompt,
        "输出前自检": "输出前自检" in system_prompt,
        "全报告统一适用": "全报告统一适用" in system_prompt,
    }
    logger.info(f"[StructuredFollowup][排查] 开篇一致性新规则存在性: {_verdict_consistency_checks}")
    # 打印用户问题原文，便于核对应拆几个子点
    logger.info(f"[StructuredFollowup][排查] 用户问题原文: {user_question}")
    # 排查日志：打印完整 system_prompt（LLM 实际收到的 prompt），便于核对规则措辞是否正确注入
    logger.info(f"[StructuredFollowup][排查] 完整system_prompt(长度={len(system_prompt)}字):\n{system_prompt}")

    start = time.time()
    tool_call_count = 0
    max_tool_rounds = 3  # 最多3轮工具调用，防止无限循环

    # Function Calling 循环：LLM 可调用 get_liuyue_detail 获取流月数据
    all_messages = [{"role": "system", "content": system_prompt}] + messages
    tools = [LIUYUE_TOOL_DEFINITION] if liuyue_data else None

    for round_num in range(max_tool_rounds + 1):
        try:
            response = await client.chat.completions.create(
                model=model_config.name,
                messages=all_messages,
                tools=tools,
                temperature=0.3,
                max_tokens=6000,
                response_format={"type": "json_object"},
                timeout=600,
                extra_body=build_llm_extra_body(model_config.name),
            )
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"[StructuredFollowup] LLM请求失败: 模型={model_config.name}, 状态=异常, 耗时={elapsed:.1f}s, 错误={type(e).__name__}: {str(e)[:200]}")
            raise

        # 防御性检查：某些情况下 choices 可能为 None
        if not response.choices:
            raw_content = getattr(response, "text", None) or ""
            if not raw_content:
                raise RuntimeError("LLM 返回空响应（choices 为空）")
            finish_reason = getattr(response, "finish_reason", "stop")
            break

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # 处理工具调用
        if msg.tool_calls:
            tool_call_count += len(msg.tool_calls)
            logger.info(f"[StructuredFollowup] 第{round_num + 1}轮工具调用: {[tc.function.name for tc in msg.tool_calls]}")
            all_messages.append(msg)  # 添加 assistant 消息（含 tool_calls）
            for tool_call in msg.tool_calls:
                if tool_call.function.name == "get_liuyue_detail":
                    try:
                        args = json.loads(tool_call.function.arguments)
                        year = args.get("year")
                        liuyue = liuyue_data.get(year, [])
                        result = _format_liuyue_result(year, liuyue)
                        logger.info(f"[StructuredFollowup] 工具返回: {year}年流月数据，长度={len(result)}")
                    except Exception as e:
                        result = f"工具调用失败: {e}"
                        logger.error(f"[StructuredFollowup] 工具调用异常: {e}")
                    all_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
            continue  # 继续下一轮 LLM 调用

        # 无工具调用，获取最终响应
        raw_content = msg.content or ""
        break

    elapsed = time.time() - start

    # token 用量统计
    usage = getattr(response, "usage", None)
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)
        logger.info(
            f"[StructuredFollowup] LLM响应: 模型={model_config.name}, 状态=成功, "
            f"finish_reason={finish_reason}, 长度={len(raw_content)}, 耗时={elapsed:.1f}s, "
            f"工具调用={tool_call_count}次, token用量: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
        )
    else:
        logger.info(
            f"[StructuredFollowup] LLM响应: 模型={model_config.name}, 状态=成功, "
            f"finish_reason={finish_reason}, 长度={len(raw_content)}, 耗时={elapsed:.1f}s, "
            f"工具调用={tool_call_count}次, token用量: 未返回"
        )

    # 排查日志：打印 LLM 完整原始返回，对照 prompt 规则逐条核对是否遵守（换组定义/术语黑名单/开篇一致性等）
    logger.info(f"[StructuredFollowup][排查] LLM完整原始返回(长度={len(raw_content)}字):\n{raw_content}")

    # 5. 解析 + 容错 + 校验
    try:
        data = json.loads(raw_content)
        logger.info("[StructuredFollowup] JSON直接解析成功")
    except json.JSONDecodeError:
        logger.info("[StructuredFollowup] JSON直接解析失败，启动容错修复...")
        fixed = _extract_and_fix_json(raw_content)
        try:
            data = json.loads(fixed)
            logger.info("[StructuredFollowup] 容错修复后解析成功")
        except json.JSONDecodeError as e:
            logger.error(f"[StructuredFollowup] JSON解析彻底失败: {e}")
            # 降级：返回错误JSON，前端显示兜底提示
            error_report = {
                "opening": {"lead": "报告生成异常，请稍后重试。"},
                "subtopics": [],
                "summary": {"title": "生成失败"},
            }
            yield json.dumps(error_report, ensure_ascii=False)
            return

    # 排查日志②：打印 LLM 原始返回结构详情（解析后、规范化前）
    _log_report_structure(data, stage="解析后-规范化前")

    # 6. 字段规范化（处理LLM偶发字段缺失/别名，如keyword block缺narrative）
    _normalize_report_data(data)
    logger.info("[StructuredFollowup] 字段规范化完成")

    # 排查日志③：规范化后结构（对比是否被改坏）
    _log_report_structure(data, stage="规范化后")

    # 7. Pydantic 校验
    try:
        report = FollowupReport.model_validate(data)
        logger.info(f"[StructuredFollowup] Pydantic校验通过, subtopics={len(report.subtopics)}")
    except ValidationError as e:
        logger.error(f"[StructuredFollowup] Pydantic校验失败: {e}")
        logger.error(f"[StructuredFollowup] 规范化后data片段: {json.dumps(data, ensure_ascii=False)[:800]}")
        error_report = {
            "opening": {"lead": "报告格式异常，请稍后重试。"},
            "subtopics": [],
            "summary": {"title": "校验失败"},
        }
        yield json.dumps(error_report, ensure_ascii=False)
        return

    # 7.1 空内容检测：LLM 返回空 JSON（subtopics 为空且 opening 为空）时重试
    opening_empty = not (data.get("opening", {}).get("lead") or data.get("opening", {}).get("verdict"))
    subtopics_empty = not data.get("subtopics")
    if opening_empty and subtopics_empty:
        logger.warning(f"[StructuredFollowup] LLM返回空内容（opening和subtopics都为空），触发重试")
        # 重试一次，不带 tools（避免 thinking 模式干扰）
        try:
            retry_response = await client.chat.completions.create(
                model=model_config.name,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                temperature=0.3,
                max_tokens=6000,
                response_format={"type": "json_object"},
                timeout=600,
                extra_body=build_llm_extra_body(model_config.name),
            )
            retry_content = retry_response.choices[0].message.content or ""
            if retry_content and len(retry_content) > 100:
                logger.info(f"[StructuredFollowup] 空内容重试成功，长度={len(retry_content)}")
                raw_content = retry_content
                # 重新解析
                data = _extract_json_from_response(raw_content)
                if data:
                    data = _normalize_report_data(data)
                    report = FollowupReport.model_validate(data)
                    logger.info(f"[StructuredFollowup] 重试后Pydantic校验通过, subtopics={len(report.subtopics)}")
            else:
                logger.error(f"[StructuredFollowup] 空内容重试仍失败，长度={len(retry_content)}")
        except Exception as e:
            logger.error(f"[StructuredFollowup] 空内容重试异常: {e}")

    # 排查日志④：Pydantic校验后最终结构
    _log_report_structure(data, stage="校验后-最终")

    # 7.5 命理逻辑兜底检查：方向锁定（凶年启动/吉年劝退/标签颠倒）+ 用神逻辑矛盾 + 术语黑名单 + 干支纪时
    # 六类检测共用同一套重试机制；术语/干支/用神检测不依赖吉凶年，即使重点流年为空也执行
    unfavored_years = _get_unfavored_years(analysis_data)
    favored_years = _get_favored_years(analysis_data)
    yongshen = analysis_data.get("用神", "") or ""
    action_violations = _detect_unfavored_year_actions(data, unfavored_years) if unfavored_years else []
    label_violations = _detect_favored_label_on_unfavored_year(data, unfavored_years) if unfavored_years else []
    favored_discouraged_violations = _detect_favored_year_discouraged_actions(data, favored_years) if favored_years else []
    yongshen_conflict_violations = _detect_yongshen_logic_conflict(data, yongshen)
    forbidden_term_violations = _detect_forbidden_terms(data)
    ganzhi_time_violations = _detect_ganzhi_time_notation(data)
    synonym_violations = _detect_synonym_contradiction(data)
    dimension_violations = _detect_dimension_coverage(data)
    summary_dup_violations = _detect_summary_duplication(data)
    past_month_violations = _detect_past_month_suggestions(data, current_month) if current_month else []
    llm_violations = _detect_llm_contradiction(data)
    all_violations = (action_violations + label_violations + favored_discouraged_violations
                      + yongshen_conflict_violations + forbidden_term_violations + ganzhi_time_violations
                      + synonym_violations + dimension_violations + summary_dup_violations
                      + past_month_violations + llm_violations)
    logger.info(
        f"[StructuredFollowup][命理逻辑检查] 凶年={unfavored_years}, 吉年={favored_years}, 用神={yongshen}, "
        f"启动类违规={len(action_violations)}项, 标签颠倒违规={len(label_violations)}项, "
        f"吉年反向违规={len(favored_discouraged_violations)}项, 用神矛盾违规={len(yongshen_conflict_violations)}项, "
        f"禁用术语违规={len(forbidden_term_violations)}项, 干支纪时违规={len(ganzhi_time_violations)}项, "
        f"同义词对立违规={len(synonym_violations)}项, 维度覆盖违规={len(dimension_violations)}项, "
        f"总结重复违规={len(summary_dup_violations)}项, 过去月份违规={len(past_month_violations)}项, "
        f"LLM矛盾违规={len(llm_violations)}项, "
        f"合计={len(all_violations)}项"
    )
    if all_violations:
        logger.warning(
            f"[StructuredFollowup] 命理逻辑违规(首次): 凶年={unfavored_years}, 吉年={favored_years}, "
            f"违规={all_violations}, 命盘指纹={get_chart_fingerprint(analysis_data)}"
        )

        # 把检测抽成内部函数，重试时基于最新 data 重新跑全量检测
        def _run_all_checks(d):
            v_action = _detect_unfavored_year_actions(d, unfavored_years) if unfavored_years else []
            v_label = _detect_favored_label_on_unfavored_year(d, unfavored_years) if unfavored_years else []
            v_favored = _detect_favored_year_discouraged_actions(d, favored_years) if favored_years else []
            v_yongshen = _detect_yongshen_logic_conflict(d, yongshen)
            v_terms = _detect_forbidden_terms(d)
            v_ganzhi = _detect_ganzhi_time_notation(d)
            v_synonym = _detect_synonym_contradiction(d)
            v_dimension = _detect_dimension_coverage(d)
            v_summary_dup = _detect_summary_duplication(d)
            v_past_month = _detect_past_month_suggestions(d, current_month) if current_month else []
            v_llm = _detect_llm_contradiction(d)
            return {
                "action": v_action, "label": v_label, "favored": v_favored,
                "yongshen": v_yongshen, "terms": v_terms, "ganzhi": v_ganzhi,
                "synonym": v_synonym, "dimension": v_dimension, "summary_dup": v_summary_dup,
                "past_month": v_past_month, "llm": v_llm,
                "all": v_action + v_label + v_favored + v_yongshen + v_terms + v_ganzhi + v_synonym + v_dimension + v_summary_dup + v_past_month + v_llm,
            }

        # 基于当前违规字典动态拼装修正提示（每次重试按最新违规类型给提示，更精准）
        def _build_retry_hint(v):
            parts = []
            if v["action"] or v["label"]:
                parts.append(
                    f"在凶年({', '.join(map(str, unfavored_years))})存在两类问题——"
                    f"①安排了启动类行动（搞副业/做副业/启动副业/跳槽/投资/创业/开业），②给凶年贴了正向标签（小吉/回暖/向好/起色等）。"
                    f"命盘显示这些年份是大凶年（有冲、主变动），必须如实标注凶/大凶，"
                    f"严禁安排启动类行动（只能说慎入/避开/不宜启动/缓一缓/防守为主），"
                    f"严禁贴小吉/回暖/向好等正向标签（回暖只能从首个吉/平年开始算）。"
                )
            if v["favored"]:
                parts.append(
                    f"在吉年({', '.join(map(str, favored_years))})存在方向锁定颠倒问题——"
                    f"把吉年说成了'不适合/不宜/不建议 搞副业/做副业/启动副业/跳槽/投资'。"
                    f"命盘显示这些年份是大吉年（用神当令、帮身利启动），用户问启动类问题时，"
                    f"吉年必须给出'适合启动/可推进/有启动窗口/今年可以动手'的鼓励方向，"
                    f"严禁出现'不适合/不宜/不建议/千万别/不要 搞副业/做副业/启动副业/跳槽/投资'等劝退表述。"
                    f"特别注意：命盘reason里'需注意/有自刑/有合'等提示，是指吉年里有小波折需要留心，"
                    f"绝不等于'不适合启动'——吉年整体方向是利启动的，'需注意'只是在鼓励启动时附带提醒'留意XX细节'，"
                    f"不能把'需注意'放大成'不适合/不宜/不建议'的劝退结论。"
                )
            if v["yongshen"]:
                parts.append(
                    f"存在用神逻辑矛盾——把用神五行当令说成了'X旺反耗/反激化耗损/太旺耗身'。"
                    f"命理硬逻辑：用神（{yongshen}）当令=帮身，用神旺是帮扶不是消耗；"
                    f"忌神当令的凶年=耗身，才能说耗损。必须删除所有'用神旺反耗'类表述。"
                )
            if v["terms"]:
                parts.append(
                    f"出现了禁用词（杀印相生/寅午半合火局/伤官见官/卯酉相冲/卯辰相害/相害/相刑/破印等命理术语，"
                    f"或正印护体/火土余温/水旺耗身等玄学话术，或工位/物理位置/挪了挪等物理位置描述）。"
                    f"命理术语必须替换成大白话（如'有外部资源化解压力''秋季岗位变动''暗中有人帮你'）；"
                    f"玄学话术必须换成现实说法（如'正印护体'→'你在公司不可替代性增强'）；"
                    f"物理位置描述必须删除或换成组织变动表述（如'工位换了'→'换了领导/换了组/职责变了'）。"
                )
            if v["ganzhi"]:
                parts.append(
                    f"出现了干支纪时写法（如丁酉月/丁未流年）。"
                    f"必须改成公历：干支+月→公历月份区间（如'2026年9月8日-10月8日'），干支+流年→公历年（如'2027年'）。"
                )
            if v["synonym"]:
                parts.append(
                    f"出现了同义词对立矛盾——'裁员大礼包'和'补偿金/赔偿金'是同一回事（离开公司拿到的钱，"
                    f"裁员大礼包是日常说法，赔偿金/补偿金是书面说法），禁止说成'拿不到裁员大礼包但能谈出补偿金'，"
                    f"这等于'拿不到赔偿金但能拿到赔偿金'，自相矛盾。必须统一口径：要么拿得到（讲清是被裁N+1还是协商补偿），"
                    f"要么拿不到，禁止用两个词指同一东西再制造对立。"
                )
            if v["dimension"]:
                parts.append(
                    f"出现了维度覆盖不足——subtopic 涉及'换组/换岗/调岗'但 narrative 没有出现职责/领导/团队/汇报线"
                    f"任何组织维度词，可能只讲了物理位置（工位/座位/办公桌/位置挪了挪等）而答非所问。"
                    f"用户问换组关心的是职责/领导/团队/汇报线是否变动，不关心坐哪个工位。"
                    f"必须在 narrative 里讲清这些组织维度（至少2个），禁止只讲物理位置。"
                )
            if v["summary_dup"]:
                parts.append(
                    f"出现了总结重复——summary.items 的 keyword 与某个 subtopic 的 blocks keyword 大量重叠（≥3个相同），"
                    f"summary 把 subtopic 已展开的行动步骤/时间节点又重复列了一遍，用户看到两块几乎一样的内容。"
                    f"summary 应该是更高层次的提炼（如'三个关键提醒''两个风险点'），或换一个 subtopic 没讲过的角度"
                    f"（如心态建议、避坑提醒），禁止把 subtopic 的内容换个格式再列一遍。"
                )
            if v["past_month"]:
                # 从 liuyue_data 提取当前年份剩余月份的流月数据，注入 retry_hint（命盘结果优先）
                remaining_liuyue = ""
                current_year = datetime.now().year
                if current_year in liuyue_data:
                    future_months = [
                        lm for lm in liuyue_data[current_year]
                        if isinstance(lm, dict) and lm.get('solar_month', 0) > current_month
                    ]
                    if future_months:
                        month_parts = [f"{lm.get('solar_month')}月({lm.get('month_ganzhi','')}){lm.get('judge','')}" for lm in future_months]
                        remaining_liuyue = f"当前{current_month}月之后剩余月份的流月数据：{' '.join(month_parts)}。"
                parts.append(
                    f"出现了过去月份建议——行动建议的时间点早于当前咨询月份（{current_month}月），用户无法执行'穿越式建议'。"
                    f"【命盘结果优先】修正时必须基于流月吉凶数据找下一个吉月，禁止随意改成未来月份。"
                    f"{remaining_liuyue}"
                    f"若流月数据显示过去月份是吉月，先承认'X月确实是窗口但已过'（复盘参考），"
                    f"再从上述剩余月份中找到下一个吉/平月作为行动建议，给出命盘依据。"
                    f"禁止毫无根据地把'6月拿offer'改成'9月拿offer'——必须说清为什么是9月（流月数据显示9月是吉月）。"
                )
            if v["llm"]:
                parts.append(
                    f"LLM矛盾检测发现开篇结论与正文细节存在语义矛盾——"
                    f"opening.verdict 与 subtopic narrative 说了相反/对立的话（如开篇说'不换组'正文说'换了新领导'，"
                    f"或开篇说'拿不到裁员大礼包'正文说'能谈出补偿金'）。"
                    f"必须确保开篇结论与正文细节语义完全一致：如果正文说'换了领导'，开篇就不能说'不换组'；"
                    f"如果能谈到补偿，开篇就说'能拿到钱'而不是'拿不到'。"
                )
            return "上次生成违背了命理逻辑约束：" + "".join(parts) + "请修正这些违规点后重新输出完整JSON。"

        # 当前违规字典（首次用上面已算好的检测结果，后续重试基于最新 data 重算）
        current_violations = {
            "action": action_violations, "label": label_violations,
            "favored": favored_discouraged_violations, "yongshen": yongshen_conflict_violations,
            "terms": forbidden_term_violations, "ganzhi": ganzhi_time_violations,
            "synonym": synonym_violations, "dimension": dimension_violations,
            "summary_dup": summary_dup_violations, "past_month": past_month_violations,
            "llm": llm_violations,
            "all": all_violations,
        }
        max_retries = 2  # 重试次数从1次提升到2次，给LLM更多修正机会
        for attempt in range(1, max_retries + 1):
            retry_hint = _build_retry_hint(current_violations)
            try:
                retry_response = await client.chat.completions.create(
                    model=model_config.name,
                    messages=[{"role": "system", "content": system_prompt}] + messages + [{"role": "user", "content": retry_hint}],
                    temperature=0.2,
                    max_tokens=6000,
                    response_format={"type": "json_object"},
                    timeout=600,
                    extra_body=build_llm_extra_body(model_config.name),
                )
                # 兼容不同 endpoint 的响应格式
                if retry_response.choices:
                    retry_raw = retry_response.choices[0].message.content or ""
                else:
                    retry_raw = getattr(retry_response, "text", None) or ""
                if not retry_raw:
                    logger.error(f"[StructuredFollowup] 第{attempt}次重试返回空响应，终止重试")
                    break
                retry_data = None
                try:
                    retry_data = json.loads(retry_raw)
                except json.JSONDecodeError:
                    fixed_retry = _extract_and_fix_json(retry_raw)
                    try:
                        retry_data = json.loads(fixed_retry)
                    except json.JSONDecodeError:
                        logger.error(f"[StructuredFollowup] 第{attempt}次重试JSON解析失败，继续下次重试")
                        continue
                if retry_data is None:
                    continue
                _normalize_report_data(retry_data)
                # 基于最新 retry_data 重新跑全量检测，更新 current_violations 供下次 hint 拼装
                current_violations = _run_all_checks(retry_data)
                logger.info(
                    f"[StructuredFollowup][命理逻辑检查] 第{attempt}次重试: "
                    f"启动类={len(current_violations['action'])}, 标签颠倒={len(current_violations['label'])}, "
                    f"吉年反向={len(current_violations['favored'])}, 用神矛盾={len(current_violations['yongshen'])}, "
                    f"禁用术语={len(current_violations['terms'])}, 干支纪时={len(current_violations['ganzhi'])}, "
                    f"同义词对立={len(current_violations['synonym'])}, 维度覆盖={len(current_violations['dimension'])}, "
                    f"LLM矛盾={len(current_violations['llm'])}, "
                    f"合计={len(current_violations['all'])}"
                )
                if not current_violations["all"]:
                    logger.info(f"[StructuredFollowup] 命理逻辑重试第{attempt}次成功, 原违规数={len(all_violations)}")
                    try:
                        FollowupReport.model_validate(retry_data)
                        data = retry_data
                    except ValidationError:
                        logger.error(f"[StructuredFollowup] 第{attempt}次重试Pydantic校验失败，返回原结果")
                    break
                else:
                    logger.error(
                        f"[StructuredFollowup] 第{attempt}次重试仍违规: {current_violations['all']}"
                    )
                    # 降级采用最新重试结果（比首次违规结果更接近正确），继续下一次重试
                    try:
                        FollowupReport.model_validate(retry_data)
                        data = retry_data
                    except ValidationError:
                        logger.error(f"[StructuredFollowup] 第{attempt}次重试Pydantic校验失败")
            except Exception as e:
                logger.error(f"[StructuredFollowup] 第{attempt}次重试异常: {type(e).__name__}: {str(e)[:200]}，终止重试")
                break
        if current_violations["all"]:
            logger.error(
                f"[StructuredFollowup] {max_retries}次重试后仍违规({len(current_violations['all'])}项)，"
                f"降级返回最新重试结果(已告警)"
            )
    else:
        logger.info(f"[StructuredFollowup] 命理逻辑检查通过, 凶年={unfavored_years} 吉年={favored_years} 用神={yongshen} 无违规")

    # 7. 命盘指纹审计（事后核对 LLM 输出是否与命盘一致，不强制拦截）
    logger.info(
        f"[StructuredFollowup] 命盘指纹审计: {get_chart_fingerprint(analysis_data)}, "
        f"LLM输出摘要: {raw_content[:200]}"
    )

    # 8. yield JSON 字符串（存库用）
    yield json.dumps(data, ensure_ascii=False)
