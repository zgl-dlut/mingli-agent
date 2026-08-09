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
from app.services.skill_prompts import _build_context_vars
from app.services.ai_service import model_pool, get_client

logger = logging.getLogger(__name__)
# 确保 logger.info 能输出到 stdout（uvicorn 默认不配置 app 子 logger 的 handler）
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setLevel(logging.INFO)
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # 避免重复输出


# ============================================================
# 历史消息压缩：从历史 assistant 消息（JSON）提取关键结论
# ============================================================

def _build_history_summary(history: list) -> str:
    """从历史 assistant 消息提取关键结论，构建历史摘要文本。

    每份历史报告提取：
    - opening.verdict（核心结论）
    - subtopics[].title（各子问题结论标题）
    - summary.items 或 summary.narrative（行动清单/总结）

    返回摘要文本，约200-400字/份。提取失败的历史消息跳过。
    """
    summaries = []
    for i, msg in enumerate(history):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content") or ""
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue  # 非 JSON（首次报告是 Markdown），跳过

        parts = []
        # 提取核心结论
        opening = data.get("opening") or {}
        verdict = opening.get("verdict")
        if verdict:
            parts.append(f"核心结论：{verdict}")

        # 提取各子问题结论标题
        subtopics = data.get("subtopics") or []
        titles = [st.get("title", "") for st in subtopics if st.get("title")]
        if titles:
            parts.append("已回答：" + "；".join(titles))

        # 提取行动清单
        summary = data.get("summary") or {}
        items = summary.get("items") or []
        if items:
            item_texts = [f"{it.get('keyword', '')}({it.get('text', '')[:40]})" for it in items[:5]]
            parts.append("行动建议：" + "；".join(item_texts))
        elif summary.get("narrative"):
            parts.append(f"总结：{summary['narrative'][:80]}")

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
    # 历史摘要区块：有摘要时插入，无摘要时空字符串
    if history_summary:
        history_section = f"""

# 历史对话摘要（你之前给出的关键结论）
{history_summary}

## 命盘权威（最高优先级，覆盖历史摘要）
- 命盘数据是最高推演依据，所有结论必须以命盘为准
- 历史摘要仅供话题承接参考，不得作为结论依据；历史结论与命盘冲突时，必须以命盘为准并修正前轮，在开篇说明"结合命盘重新看"
- 反例：若历史摘要说"2027适合创业"，但命盘显示2027火土忌神耗身，必须输出"不宜创业"并说明命盘依据，禁止沿用历史结论
- 长线剧情延伸：承接前轮话题往下讲，但结论以命盘推演为准，不盲从前轮判断
- 严禁编造命理依据：narrative/reason 只能引用上文命盘数据栏已给出的信息，不得臆造未提及的干支、大运、流月
"""
    else:
        history_section = ""
    return f"""# 角色
职场人生顾问，以命盘当作参考依据，全程像真人给朋友出主意，优先讲故事、讲现实走向、给到落地行动方案。全程面向零基础小白，语言口语通俗、故事感充足；命理缘由能省则省、只交代清楚现实走向即可，严控玄学词汇数量，永远先抛出结论、预判现实遭遇、给到可执行做法，保留精准流年流月时间推演。

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
{history_section}
# 用户问题
{context['user_question']}

# 输出格式
请输出纯JSON（不要用```json代码块包裹，直接输出JSON文本），结构如下：

{{
  "opening": {{
    "lead": "开篇叙事(可选)。1-2句，形式多样，可内联**加粗**重要词。不要每次都用'直接回答你'开头",
    "verdict": "核心结论(可选)。可包含多重总结要点（多个分句），不固定一句话，不强制以'核心结论'开头；若用'核心结论'开头，'核心结论'四字必须用**加粗**（如**核心结论**：...）；后面内容只加粗关键时间节点/结论词，禁止整段全加粗"
  }},
  "subtopics": [
    {{
      "title": "子问题标题，结论感叙事化标题，直接回应用户关切",
      "lead": "可选，1-2句承上启下或总结性引导，引出下面的内容",
      "blocks": [
        {{"type": "keyword", "keyword": "叙事化关键词，不加**号", "narrative": "仅讲单一维度，2-3句、≤120字，可内联**加粗**。极少数必要命理名词只用括号附带通俗解释，自然融入语句"}},
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
0. **具体数字问题处理（遇到先执行，优先级最高）**
- "具体数字"指金额（多少钱）、倍数（涨2倍）、具体日期（几号入职）——命理算不了，必须先在 opening.verdict 提示"命理只能给方向性判断，算不出具体数字/日期"，再按命盘能答的方向回答（财运趋势/吉凶时段/适合行动的月份窗口），禁止编造具体数字
- "几月会发生"不属于具体数字问题：命盘可基于流月吉凶数据回答，给"有利/不利月份窗口"，但需提示"命理看月份趋势，不保证必然发生"
- 若用户要的精度命理给不了，明确说"这个精度命盘算不了，只能看趋势"
1. **子问题拆解（必须遵守）**
必须拆分多个 subtopic，拒绝整段长篇叙事。
拆解逻辑（这是逻辑对应，不是数数）：
   - **逐点对应**：用户问题里有几个独立关切点，就必须有对应的几个 subtopic 一一回应。每一个用户提出的独立问题都要有专门一块分析，禁止漏答、禁止把两个独立关切合并成一块带过。例如用户问"是否换组""是否裁员""何时离职""何时入职新公司"四件事，就要有四块分别回应，不能把"入职新公司"塞进"离职"里一笔带过
   - **判断"独立关切点"的方法**：看用户问的是不是两件不同的事（换组 vs 裁员 vs 离职 vs 入职），而不是看句子数量。同一件事的延伸追问（"何时离职"和"怎么离职"）可合并；两件不同的事必须分开
   - 拆完用户关切点后，可额外补充风险提示、时间路线、实操对策作为加餐 subtopic
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

3. **开篇话术多样化**
lead随机选用痛点直击、反常识提醒、直白结论、情绪共情；杜绝固定开场白，不输出节气、流月这类技术式开场白。

4. **术语管控 + 故事叙事（最核心新规）**
> 整体配比：命理原因能省略就省略，只交代清楚现实走向即可。绝大多数 narrative 完全不提命盘，全程像真人给朋友出主意
- 术语密度强制约束：**一整段narrative最多允许出现1个命理词汇**，紧跟着括号大白话释义；绝大多数段落完全不用任何命理名词
- **禁用术语黑名单**（出现即判定不合格，必须替换成大白话）：
  - 十神名直接出现：七杀、正官、偏印、正印、伤官、食神、比肩、劫财、偏财、正财
  - 作用关系短语：天干透出X、地支X与X联动、X气暗动、X相冲、X相生、X破印、杀印相生、伤官见官、卯酉相冲
  - 干支纪时写法：丁酉月、丁未流年、丁未年 → 一律替换为公历"2026年9月8日-10月8日""2027年"
  - 排盘术语：月令、宫位、用神、忌神、日支、流月、地支、天干、原局、命局、流年干支 → 禁止出现在narrative
  - 玄学话术：火土余温、水气太重、水旺耗身、金气暗动 → 替换为"年底公司容易拉扯扯皮"这类人话
- 优先讲故事、剧本化描写：多描写当事人的情绪状态、公司管理层的套路手段、同事关系环境、利弊得失；多用生活化词汇：坑位、苟住、摸鱼、公司施压、拿到补偿、悄悄筹备副业
- **how维度（必须）**：对关键问题除了when（何时）和what（是什么），还要说清楚how（怎么发生、怎么做才稳）。当用户问题明确指向未来结果（如"何时入职新公司""能否找到新工作"），必须按上方第1.5条"未来剧本"独立成 subtopic 并展开四层维度，禁止缩成一句话时间点。依托排盘数据确保不乱推测，不加专业术语，与整体术语管控一致
- 命理原因能省则省，需要提及时一句话带过立刻转回现实剧情；禁止逐层拆解五行作用、十神联动这类分析
- 命理术语不单独拿出来讲解，顺势嵌进句子

5. **subtopic标题必须是现实结论**
只写人事、时机、利弊判断；禁止"财运解析、事业格局、七杀解读"这类抽象标题。
✅合格：9月返岗大概率迎来小组调动、2027秋季最容易下发裁员补偿、年底走人最利于之后副业发展

6. **keyword关键词全部为生活化词语**
绝对不可使用任何八字专业名词；可用关键词示例：现实剧本预判、关键时间节点、自保对策、安心定心提示、风险高发阶段、最佳行动窗口期。关键词必须和本段叙事内容保持一致，不能凭空新增信息。

7. **月份时间参考**
所有月份判断依托给到的排盘参数，不要自行脑补流月信息。

8. **文字加粗规则**
narrative内的年月节点、关键行动、重要收益进行**加粗**；每一段最少一处加粗，不要整段文字加粗。

9. **篇幅控制**
单个keyword对应的narrative保持2-3句话、≤120字，语言紧凑，减少多余命理推演。

10. **总结部分风格轮换**
summary分别采用行动清单、时间轴、阶段提醒、避坑清单多种风格；items关键词全部采用生活化阶段名称。

11. **block分层与同级格式统一规范**
- 同一个subtopic之下按现实维度拆分多个block：会发生什么/什么时候发生/该怎样处理/心理宽慰，每个维度独立一个keyword block
- **同级block格式必须完全一致**：同一subtopic内所有block统一用type=keyword（keyword+narrative齐全）。严禁出现三类混搭：①"定心丸"是keyword带内容、"精准时间窗口"却是空标题挂下属段落；②一段有keyword、另一段是type=narrative光秃秃叙事无keyword；③混用keyword与group
- **禁止type=narrative块**：subtopic内不允许出现纯叙事块（无keyword的整段文字）。每段内容都必须提炼一个叙事化keyword短语，再写narrative描述。例如整段"2027年底痛快签字拿走赔偿金，挥一挥衣袖..."不能直接当narrative块输出，必须拆成keyword="签字拿赔偿金时机"+narrative="..."
- **多时间节点处理**：每个时间节点（如第一波危险期、最终清算期）各自独立一个keyword block——keyword写节点名、narrative写该节点的现实遭遇+应对。禁止用group块或空关键词当总标题再挂下属段落
- narrative聚焦单一维度、2-3句、≤120字，禁止空洞简短也禁止堆砌；收尾感悟可单独一个keyword block（keyword写"定心提示"之类，narrative写宽慰话）

## 禁止清单（严格规避以下问题）
❌ 禁止连续出现多个八字名词、十神名词
❌ 禁止大篇幅解析五行生克、格局原理
❌ 禁止抽象玄学比喻代替现实描述
❌ 禁止关键词采用命理术语
❌ 禁止单独开辟一段解释专业名词
❌ 禁止同一subtopic内block类型混用（如keyword+group并存、keyword+narrative并存）
❌ 禁止用空关键词或group标题当小标题，再在下面挂下属段落
❌ 禁止type=narrative纯叙事块（无keyword的整段文字）；每段必须keyword+narrative齐全
❌ 禁止closing复述上面已讲过的结论（换个说法再讲一遍，如blocks已说"稳住别主动提离职"，closing又写"稳住节奏就是赢"）
❌ 禁止closing输出空洞金句/口号式收尾（如"守得住基本盘才能接得住新风口""谁先急谁就输"这类无具体信息、无真实情感的话）；没有真正想对朋友说的话就留空，宁可没有也不要凑

## 对照示例（务必参照执行）

**❌错误写法1（术语堆砌+剧本策略混在同一段）：**
keyword="现实剧本预测"，narrative="2026年9月8日到10月8日处于丁酉月，地支酉与日支卯发生卯酉相冲（冲代表调岗换组）。但冲的是月令不是岗位宫位，所以你9月回去大概率坑位变了——公司秋季组织架构调整，你被分到新组换新领导。你只需安安静静把手头项目收尾，不主动申请调岗、不站队，就能平稳过渡到年底。"
>问题：术语超标（丁酉月/酉/卯/卯酉相冲/月令/岗位宫位）；剧本预测与应对策略混在一段，过长。

**✅正确写法1（拆成两个独立keyword block，术语清零）：**
block1: keyword="现实剧本预判", narrative="**9月8日到10月8日**这一个月，公司大概率在搞秋季组织架构调整。你回去后会发现自己被分到了新组、换了新领导，但**岗位职责和汇报线基本没动**，只是物理位置挪了挪。"
block2: keyword="应对策略", narrative="这次被动换组反而帮你脱离最压抑的业务线。**安安静静把手头项目收尾**，不主动调岗、不站队，就能平稳过渡到年底，还能摸鱼搞副业。"

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
        for item in summary.get("items") or []:
            if not isinstance(item, dict):
                continue
            if not item.get("text"):
                item["text"] = item.get("desc") or item.get("content") or item.get("description") or ""
            if not item.get("keyword"):
                item["keyword"] = item.get("name") or item.get("title") or ""

    # opening 回退：lead/verdict 都缺时从 conclusion/summary 回退
    opening = data.get("opening")
    if isinstance(opening, dict) and not opening.get("lead") and not opening.get("verdict"):
        opening["lead"] = opening.get("conclusion") or opening.get("summary") or ""

    # closing 金句兜底清理：LLM（qwen-plus）指令遵循能力不足，常输出空洞金句/口号式 closing，
    # 即使 prompt 已三层禁止仍不遵守。此处后端强制检测并清空，不依赖 LLM 自觉。
    _clean_slogan_closings(data)

    return data


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
    # 现场重算命盘（与首次报告一致，保证中文 key 数据完整；修复数据库存BaziChart英文结构导致追问取空的bug）
    from app.skills.orchestrator import generate_full_analysis
    gender_cn = "男" if gender in ("male", "男") else "女"
    analysis_data = generate_full_analysis(
        birth_date=birth_date,
        birth_time=birth_time,
        longitude=longitude,
        latitude=latitude,
        gender=gender_cn,
        location=location,
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

    # 2. 历史消息压缩：从历史 assistant 消息（JSON）提取关键结论作为摘要
    history_summary = _build_history_summary(history)

    # 3. 构建精简 prompt（含历史摘要区块 + 一致性要求）
    # 临时：不参考历史摘要，测试叙事性（history_summary 传空，history_section 不注入）
    system_prompt = build_structured_prompt(context, history_summary="")

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
        logger.info("[StructuredFollowup][排查] 历史摘要为空（首轮追问/历史均为Markdown首次报告被跳过）")

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
    # 打印用户问题原文，便于核对应拆几个子点
    logger.info(f"[StructuredFollowup][排查] 用户问题原文: {user_question}")

    start = time.time()
    try:
        response = await client.chat.completions.create(
            model=model_config.name,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0.3,
            max_tokens=6000,
            response_format={"type": "json_object"},
            timeout=120,
        )
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"[StructuredFollowup] LLM请求失败: 模型={model_config.name}, 状态=异常, 耗时={elapsed:.1f}s, 错误={type(e).__name__}: {str(e)[:200]}")
        raise

    # 防御性检查：某些情况下 choices 可能为 None（如配额耗尽、模型不支持 response_format、内容审核拦截）
    if not response.choices:
        _model = getattr(response, "model", "unknown")
        _id = getattr(response, "id", "unknown")
        logger.error(
            f"[StructuredFollowup] LLM返回空响应: model={_model}, id={_id}, "
            f"config_model={model_config.name}, choices={response.choices}"
        )
        raise RuntimeError(
            f"LLM 返回空响应（choices 为空），可能原因：模型 {model_config.name} 不支持 JSON 模式或 API 配额异常"
        )
    raw_content = response.choices[0].message.content or ""
    finish_reason = response.choices[0].finish_reason
    elapsed = time.time() - start

    # token 用量统计（拆分 prompt/completion）
    usage = getattr(response, "usage", None)
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)
        logger.info(
            f"[StructuredFollowup] LLM响应: 模型={model_config.name}, 状态=成功, "
            f"finish_reason={finish_reason}, 长度={len(raw_content)}, 耗时={elapsed:.1f}s, "
            f"token用量: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
        )
    else:
        logger.info(
            f"[StructuredFollowup] LLM响应: 模型={model_config.name}, 状态=成功, "
            f"finish_reason={finish_reason}, 长度={len(raw_content)}, 耗时={elapsed:.1f}s, "
            f"token用量: 未返回"
        )

    # 排查日志：打印 LLM 原始返回前 1500 字符，看模型实际输出了什么（截断避免日志过长）
    logger.info(f"[StructuredFollowup][排查] LLM原始返回片段(前1500字): {raw_content[:1500]}")

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

    # 排查日志④：Pydantic校验后最终结构
    _log_report_structure(data, stage="校验后-最终")

    # 7. yield JSON 字符串（存库用）
    yield json.dumps(data, ensure_ascii=False)
