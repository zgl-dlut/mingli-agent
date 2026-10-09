# 彻底修复追问报告"吉年方向锁定颠倒"问题

## 背景与根因

实测命盘（1990-11-10 08:00 女 山西晋中，日主己土用神火）显示：
- **2026丙午是大吉年**（用神火当令，印星帮身）
- 2028-2032 连续大凶年
- 2035/2037 吉到大吉

但系统生成的追问报告（用户对比中的"回答2"）出现三类方向性错误：
1. 把 2026 大吉年说成"不适合启动副业"——**方向锁定颠倒**
2. 编造"火太旺反激化内部耗损"——**用神逻辑反了**（用神火旺是帮身不是耗身）
3. 把 2032 大凶年安排为"启动副业"——凶年启动违规（现有机制本应拦截，但被吉年错误带偏）

### 三层根因

**根因1（代码层，最关键）：方向锁定机制是单向的**
[followup_structured.py](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L651-L901) 现有：
- `_get_unfavored_years` 只提取凶年
- `_detect_unfavored_year_actions` 检测凶年+启动词
- `_detect_favored_label_on_unfavored_year` 检测凶年+正向标签

**完全缺失吉年反向检测**：吉年（大吉）被说成"不适合启动"直接漏网，主流程 L1132-1203 的方向锁定检查不覆盖吉年，不触发重试。虽然 prompt L129 写了"禁止把吉年说成不宜/慎入"，但纯 prompt 约束对 qwen-plus 效果不稳定（项目记忆多次记录 LLM 指令遵循能力不足，需代码层兜底）。

**根因2（prompt层）：缺少用神逻辑一致性约束**
prompt 的"命盘权威与方向锁定"部分（L120-133）只有吉凶方向规则，没有"用神当令吉年=帮身，忌神当令凶年=耗身"的命理逻辑约束。LLM 看到 reason 里"纯火用神年"但没理解用神火旺是帮身，凭"火旺"字面脑补出"火太旺反耗损"——与用神直接冲突。

**根因3（prompt层）：吉年正向引导弱**
L126 "吉年才能说适合启动"是允许性表述，非强制性。用户问启动类问题（搞副业）且命盘有吉年时，LLM 在凶年高压规则下过度保守，把吉年也往保守方向答。

## 修复方案（全部集中在 followup_structured.py 单文件）

### 改动1：代码层补齐吉年反向检测（对称于凶年检测）

**位置**：[followup_structured.py](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L651) 方向锁定检测区块

新增三个函数 + 一个常量：

1. `_FAVORED_YEAR_NEGATE_MARKS`：吉年反向违规的否定词集合，复用现有 `_UNFAVORED_NEGATE_MARKS`（不宜/不适合/不建议/慎/避开/暂缓/不要/不可/切勿 等），再加"不适合启动/不建议搞/不宜做"等启动类否定短语。

2. `_get_favored_years(analysis_data: dict) -> list`：从命盘重点流年提取吉年（judge 含"吉"，包括"大吉""吉""吉（注意）"）。对称于 `_get_unfavored_years`。

3. `_detect_favored_year_discouraged_actions(data: dict, favored_years: list) -> list`：检测吉年+否定启动词组合。
   - 逻辑：遍历 `_collect_report_texts` 收集的文本，对每个启动类关键词（复用 `_UNFAVORED_STARTUP_KEYWORDS`：启动副业/跳槽/投资/创业等），定位年份归属，若归属吉年且启动词前 10 字内出现否定词（不宜/不适合/不建议等）→ 违规。
   - 这是 `_detect_unfavored_year_actions` 的镜像：凶年检测"启动词无否定=违规"，吉年检测"启动词有否定=违规"。
   - 带排查日志（对称现有 `[方向锁定-启动检测]` 日志），打印 `[方向锁定-吉年检测]`。

**不做**吉年+负向标签（阻力大/耗损/不宜）的代码检测——这类模糊词容易误伤合理表述（如"2026大吉适合启动，但某月有阻力"是合理的），用神逻辑约束走 prompt（改动2），不走代码硬检测。

### 改动2：主流程方向锁定检查纳入吉年违规

**位置**：[followup_structured.py](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L1132-L1203) 主流程方向锁定检查块

- L1133 后新增 `favored_years = _get_favored_years(analysis_data)`
- `all_violations` 由原来的 `action_violations + label_violations` 扩展为 `action_violations + label_violations + favored_discouraged_violations`
- 日志 L1138-1142 补充 `吉年={favored_years}` 和 `吉年反向违规={len(favored_discouraged_violations)}项`
- retry_hint（L1148-1155）补充吉年反向违规的修正提示：吉年禁止说"不适合/不宜启动"，用户问启动类问题时吉年应给鼓励方向

### 改动3：prompt 层加用神逻辑一致性约束

**位置**：[followup_structured.py](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L125-L134) "流年吉凶方向锁定"规则块

在现有规则后追加：
```
- 用神逻辑一致性（硬约束）：
  - 用神五行当令的吉年=帮身（如用神为火，火旺流年帮身利启动），禁止说成"X旺反耗/反激化耗损/太旺耗身/旺而耗身"等与用神冲突的逻辑
  - 忌神五行当令的凶年=耗身，才能说耗损/消耗
  - 用神/忌神以命盘数据栏"用神""忌神"为准，禁止自行判定五行喜忌
```

### 改动4：prompt 层强化吉年正向引导

**位置**：同上 L125-L134 规则块

在吉年规则后追加：
```
- 吉年正向引导（当用户问启动类问题时）：命盘有吉年（吉/大吉）且用户问题含启动类意图（搞副业/跳槽/投资/创业/开业），吉年应给出"适合启动/可推进/有启动窗口"方向判断，禁止把吉年说成"不适合/不宜/不建议启动"
```

## 涉及文件

仅 [followup_structured.py](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py) 一个文件：
- 新增 `_get_favored_years` 函数
- 新增 `_detect_favored_year_discouraged_actions` 函数
- 新增 `_FAVORED_YEAR_NEGATE_MARKS` 常量
- 修改主流程方向锁定检查块（L1132-1203）：纳入吉年违规 + 扩展 retry_hint
- 修改 prompt 的方向锁定规则块（L125-134）：加用神逻辑约束 + 吉年正向引导

## 假设与决策

1. **吉年定义**：judge 含"吉"即算吉年（大吉/吉/吉（注意））。"吉（注意）"本质是吉年带提醒，按吉年处理。
2. **不做吉年+负向标签代码检测**：阻力/耗损/不宜等模糊词易误伤合理表述，用神逻辑约束走 prompt 软约束，不硬检测。只做"吉年+否定启动词"的硬检测（确定性高）。
3. **复用现有启动词表**：`_UNFAVORED_STARTUP_KEYWORDS` 和否定词表 `_UNFAVORED_NEGATE_MARKS` 直接复用，不另建表，保持单一数据源。
4. **重试机制沿用现有**：吉年违规触发同一套重试流程（temperature=0.2，重试仍违规则告警返回），不新增重试通道。
5. **不修改首次报告链路**：改动只影响追问报告（followup_structured.py），首次报告（build_first_reading_structured_prompt）如需同步可后续评估，本次不动。

## 验证步骤

1. **命盘实测**：用 1990-11-10 08:00 女山西晋中命盘，发送问题"26年适合搞副业吗？搞得话这个副业可否持续"。
2. **报告检查**：
   - 2026 大吉年应给出"适合启动"方向，不能出现"不适合/不宜启动副业"
   - 不能出现"火太旺反耗损/反激化耗损"等与用神冲突的逻辑
   - 2028-2032 凶年不能安排启动类行动（原有机制应继续生效）
3. **日志检查**（搜索 `[方向锁定`）：
   - `[方向锁定检查]` 应打印 `吉年=[2026, 2035, 2036, 2037, ...]`
   - `[方向锁定-吉年检测]` 若 LLM 首次答错应打印命中跳过/违规详情
   - 重试机制触发后，最终报告应无吉年反向违规
4. **回归检查**：确认原有凶年检测（`_detect_unfavored_year_actions`、`_detect_favored_label_on_unfavored_year`）不受影响，日志格式与原有一致。

## 风险点

- **吉年检测误伤**：已通过"只检测否定启动词、不检测模糊负向词"控制粒度。若仍有误伤，可通过排查日志 `[方向锁定-吉年检测]` 的"跳过"项定位调整。
- **重试增加 LLM 调用开销**：吉年反向错误发生时多一次 LLM 调用。但 prompt 层用神逻辑约束（改动3）+ 吉年正向引导（改动4）会从源头减少首次错误率，重试是兜底。
- **用神逻辑约束的 prompt 遵循度**：qwen-plus 对 prompt 规则遵循不稳定，用神逻辑约束可能被忽略。但有代码层吉年检测兜底，prompt 失效时代码层仍能拦截重试。
