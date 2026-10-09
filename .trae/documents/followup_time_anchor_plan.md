# 追问时间锚点继承：解决上下文语义断档

## 问题复现

1. 用户问"如果**9月**有换组机会的话，新组的领导画像…"（无显式年份）→ AI 正确回答了 2026 年 9 月（靠 current_time 蒙对）
2. 用户点推荐追问"新组业务适合我吗"（无年份无月份）→ AI **漂移到 2027 年**，语义断档

## 根因

追问链路时间数据注入的逻辑（[followup_structured.py:3177](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L3177)）：

- `_format_question_year_block` 只从**本轮**用户问题提取年份（`_extract_question_years`）
- 本轮问题没有年份/相对时间词 → 不注入任何流年流月数据 → LLM 失去时间锚点，自行漂移
- 历史摘要 `_build_history_summary` 只含用户问题原文（这是防"编造代代传染"的正确设计，**不能回退**），但 LLM 没有被明确告知"上轮的时间焦点是什么"

关键细节：用户第一轮说的是"**9月**"而非"今年9月"——`_extract_question_years` 只认年份词（2026/26年/今年/当下/丁未年），**不认裸月份**，所以"9月"这个锚点从未被代码提取过。

## 修复方案：时间锚点继承（只从用户问题提取，不碰 AI 结论）

保持"历史摘要去断语化"的防编造设计不变——锚点只从**用户问题原文**提取（用户自己的话天然不含编造结论，和 history_summary 同源同安全等级）。

### 三层时间焦点解析（按优先级）

| 优先级 | 来源 | 例子 | 处理 |
|---|---|---|---|
| 1 | 本轮问题显式年份 | "27年4月…""明年…" | 现有逻辑不变，最优先 |
| 2 | 本轮问题裸月份 | "9月换组…" | 月份解析年份：月份≥当前月→今年，否则→明年 |
| 3 | **上一轮用户问题**继承 | 上轮"9月换组"→本轮"新组业务适合我吗" | 继承上轮的年份（含裸月份解析） |

命中第 3 层时，注入的流月区块带明确标记和硬约束：

```
⚠ 本轮问题未明确说年份。按对话上下文，时间焦点承接上轮：2026年9月
  （上轮问题：「如果9月有换组机会的话，新组的领导画像…」）
  本轮回答必须围绕该年份展开，禁止自行跳到其他年份；
  若用户本轮明确提到新年份/月份，以用户原话为准。
```

裸月份解析的防护：
- 正则只认 `X月`，天然排除"3个月"（X 和 月之间隔了"个"）
- 问题含"出生/生于/生日/生辰/阳历/阴历/农历"时跳过月份锚点（防止"1995年10月出生"被误锚）

## 改动清单

### 1. `backend/app/services/skill_prompts.py`

**新增两个纯函数**（放在 `_extract_question_years` 附近）：

- `_extract_month_focus(question) -> Optional[int]`：提取裸月份（1-12），排除出生语境
- `_resolve_month_year(month, now) -> int`：`month >= now.month → now.year`，否则 `now.year+1`
- `_resolve_time_focus(current_q, history_user_qs, start_year, end_year, now) -> dict`：
  返回 `{"years": [...], "inherited": bool, "source_q": str, "month": int|None}`
  - 先试本轮显式年份；再试本轮裸月份；最后找上一轮用户问题（只看最近1轮，避免跨话题误继承）

**修改 `_format_question_year_block`**：加两个可选参数
- `override_years: list = None`：外部已解析好的年份直接用（继承场景）
- `anchor_note: str = ""`：继承时在区块顶部插入的时间锚点说明；流年后的标记从"★用户问题涉及年份"变为"★上下文时间锚点（承接上轮对话）"

### 2. `backend/app/services/followup_structured.py`（L3171-3195 注入段）

- 调用 `_resolve_time_focus` 解析时间焦点
- 显式年份：行为完全不变
- 继承/裸月份命中：用 override_years + anchor_note 构建区块，追加硬约束文案
- 加日志：`[时间锚点] 本轮无显式年份，继承上轮焦点=2026年9月（来源：「如果9月有换组机会…」）`，便于生产排查

### 3. 推荐问题 prompt 规则（双保险，两处）

- [prompt_builder.py:627](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/prompt_builder.py#L627)（首次报告）
- [followup_structured.py:392](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L392)（追问）

suggested_questions 规则加一条：
> 若本轮回答围绕具体时间焦点（如"2026年9月换组"），推荐问题应自然带上时间限定（如"9月换组后新业务适合我吗"），不要生成脱离时间语境的短句。

### 4. `backend/app/config.py`

PROMPT_VERSION 递增 → `v2026.09.07-2`

## 验证

容器内跑脚本验证解析逻辑：

| 场景 | 期望 |
|---|---|
| Q1="如果9月有换组机会的话…"（无历史） | 裸月份锚点 → 2026年 |
| Q2="新组业务适合我吗"（历史=Q1） | 继承 → 2026年，anchor_note 含上轮问题原文 |
| "27年4月有没有年终奖"→"谈赔偿怎么开口" | 继承 → 2027年 |
| "我是1995年10月出生的，今年事业怎么样" | 显式"今年"=2026 优先，不被出生月份干扰 |
| "我是95年10月生的"（无其他时间） | 出生语境跳过，无锚点不注入 |
| "正常是3个月，是否符合" | "3个月"不被识别为月份 |

部署后生产日志确认 `[时间锚点]` 命中情况。

## 风险与处理

| 风险 | 处理 |
|---|---|
| 回看过去月份（9月说"3月那次面试"）被解析成明年 | 罕见且 anchor_note 已声明"用户原话为准"；注入的是数据不是禁令 |
| 用户跨话题切换（"对了，财运怎么样"）误继承上轮年份 | 只继承最近1轮；注入的流月数据对该年回答无副作用，LLM 可泛答 |
| 与防编造设计冲突 | 锚点只取用户问题原文，不引入任何 AI 历史结论，不违反"摘要去断语化" |
| 评测端数据源 | 注入的是指令文本，命盘数据本身不变，生成/评测同源同构不受影响；PROMPT_VERSION 递增 |
