# 追问 Prompt 风格轮换优化计划

## 一、摘要（Summary）

当前追问 prompt 把 5 种开头风格（含示例，约 900 字）+ 5 种总结风格全量硬编码注入，由 LLM 自选，既费 token（风格文本约占 prompt 8%-10%）又只有 5 种风格、重复与否全靠 LLM 自觉。

本方案将**风格选择权从 LLM 收归后端**：

1. 新建代码级风格库（开头 12 种 + 总结 12 种），不占 prompt token；
2. 后端生成前从库中随机选 1 个开头风格 + 1 个总结风格，**排除最近 8 轮已用过的风格**（代码保证短期不重复）；
3. prompt 中只注入选中的那 1 条风格（名称 + 一句描述，约 100-150 字），替换原全量列表（约 1.2k 字）；
4. 生成后把所用风格 key 盖章写入报告 JSON 落库，供下一轮排除使用。

预期收益：每次请求 prompt 减少约 900-1100 字符；风格从 5+5 扩到 12+12；8 轮内绝不重复（确定性保证）。

## 二、现状分析（Current State Analysis）

- **风格定义**：`mingli-agent/backend/app/services/followup_structured.py`
  - L312-L322：开头 5 风格（现状承接式/痛点直击式/反常识提醒式/情绪共情式/结论直击式），每条带示例句，整块约 900 字
  - L358-L362：总结 5 风格（行动清单/时间轴/阶段提醒/避坑清单/剧情演进），一行枚举
  - L238：`opening.lead` 字段描述内嵌"每次随机选一种开头风格"指令
- **选择机制**：无代码级随机/轮换（全库 grep 确认 `random` 仅用于支付 nonce 和短信验证码）；prompt 写"随机选一种/必须不同"，全靠 LLM 自选（temperature=0.3）
- **避重复机制**：`_build_history_summary()`（L79-L141）从最近 5 轮 assistant JSON 提取 `opening.lead` 前 12 字 → "上次开头句式"（L109-L110）；提取 `summary.style_hint` → "上次总结风格"（L122-L134），漏写时粗推断为"清单式/段落叙事式"。均为软约束
- **落库**：报告 JSON 作为 `ChatMessage.content` 存库（`app/api/chat.py` L296-L302），无专门风格字段
- **测试安全性**：`tests/test_followup_consistency.py` 不断言任何风格原文；但 `test_extracts_summary_items` 依赖 `_build_history_summary` L124-L126 的"行动建议："items 提取逻辑，改动该函数时必须保留

## 三、改动方案（Proposed Changes）

### 1. 新建 `mingli-agent/backend/app/services/report_styles.py`

**Why**：风格库数据量较大（24 条），`followup_structured.py` 已 2000+ 行，独立模块便于维护与测试。

**内容**：
- `OPENING_STYLES: dict[str, str]` —— 12 种开头风格，key 为风格名，value 为一句描述（15-25 字）。保留现有 5 种（现状承接式、痛点直击式、反常识提醒式、情绪共情式、结论直击式，描述从现有示例提炼），新增 7 种：场景代入式、悬念设问式、数据锚点式、转折递进式、类比启发式、时间对照式、风险前置式
- `SUMMARY_STYLES: dict[str, str]` —— 12 种总结风格。保留现有 5 种（行动清单、时间轴、阶段提醒、避坑清单、剧情演进），新增 7 种：关键数字提炼式、三句话定心式、风险对策对照式、里程碑节点式、主线分支式、取舍清单式、复盘检查式
- `RECENT_WINDOW = 8`：排除窗口（最近 8 轮已用风格不再选）
- `pick_styles(history_messages: list[dict]) -> tuple[tuple[str,str], tuple[str,str]]`：
  - 从历史 assistant 消息（倒序取最近 `RECENT_WINDOW` 条可解析的 JSON）中收集已用的 `opening.style_key` 和 `summary.style_key`
  - 开头/总结各自从 `全部风格 − 已用风格` 中 `random.choice`；历史无 style_key（旧消息）则跳过不计入排除
  - 返回 `((opening_key, opening_desc), (summary_key, summary_desc))`

### 2. 修改 `mingli-agent/backend/app/services/followup_structured.py`

**Why**：压缩 prompt 风格文本、接入后端选择、盖章落库。

- `build_structured_prompt()` 新增参数 `opening_style: tuple[str, str]`、`summary_style: tuple[str, str]`
- **L312-L322（第 3 条规则）重写**：删除 5 风格全量枚举与示例，替换为：
  - 保留通用硬约束：开头必须承接用户问题内容/情感/现状（1 句）、绝对禁止的固定开头模板清单（"直接说结论："等）、禁止时间节点/节气/大运交替式开头（约 300 字）
  - 新增一行注入选中风格：`本次开头风格：**{name}**（{desc}），必须用该风格开篇，禁止套用其他风格`
- **L358-L362（第 10 条规则）重写**：删除枚举行，替换为 `本次总结风格：**{name}**（{desc}），summary 必须按该风格组织`；**保留** items 关键词叙事化规则、禁止总结重复 subtopic 内容规则（这两条与风格枚举无关）
- **L238**：lead 字段描述中删除"每次随机选一种开头风格"字样，仅保留禁止模板化句式提醒
- **`_build_history_summary()`（L79-L141）**：删除"上次开头句式"提取（L109-L110）与"上次总结风格"提取及兜底推断（L120-L134）——轮换已由后端保证，无需再告知 LLM；**必须保留 L124-L126 的 summary.items "行动建议："提取逻辑**（测试依赖）
- **`generate_followup_structured()`（约 L1724 调用处）**：
  - 构建 prompt 前调用 `pick_styles(history_list)` 选定风格，传入 `build_structured_prompt`
  - Pydantic 校验通过后（约 L981 附近），在最终返回的 data 上盖章：`data["opening"]["style_key"] = opening_key`、`data["summary"]["style_key"] = summary_key`，使落库 JSON 携带风格标记（盖章在校验后进行，不影响 Pydantic 校验）
  - 日志追加所选风格，便于排查：`logger.info(f"本轮风格 opening={opening_key} summary={summary_key}")`

### 3. 修改 `mingli-agent/backend/app/schemas/report_schema.py`

**Why**：让盖章字段能通过后续（如有）反序列化，且语义明确。

- Opening 模型新增可选字段 `style_key: Optional[str] = None`（注释：后端盖章，非 LLM 输出）
- Summary 模型新增可选字段 `style_key: Optional[str] = None`；`style_hint` 保持现状（可选、不强制）

### 4. 修改 `mingli-agent/backend/tests/test_followup_consistency.py`

**Why**：为轮换机制补测试，回归现有断言。

新增 `TestStyleRotation`：
- 空历史：`pick_styles` 返回库内合法风格
- 排除逻辑：构造最近 3 轮带 style_key 的历史，断言返回风格不在已用集合内
- 旧消息兼容：历史 JSON 无 style_key 时不报错、不纳入排除
- prompt 注入：调用 `build_structured_prompt` 传入指定风格，断言 prompt 含 `本次开头风格：**{name}**`、`本次总结风格：**{name}**`，且**不含**未选中风格的示例文本（如"痛点直击式"未选中时不出现其示例句）
- 回归：现有 prompt 措辞保障 8 项 + 历史摘要提取测试全部通过（重点确认 `test_extracts_summary_items` 不受 `_build_history_summary` 改动影响）

## 四、假设与决策（Assumptions & Decisions）

1. **风格库规模 12+12**：较现有 5+5 翻倍以上；排除窗口 8 < 12，保证任意连续 8 轮不重复且始终有候选
2. **后端确定性轮换，非 LLM 自选**：LLM 只执行被选中的风格；比 prompt 软约束可靠
3. **旧消息兼容**：无 style_key 的历史轮不参与排除，不做回填
4. **不改旧 Markdown 链路**（`skill_prompts.py`，服务 chat_lite/job_store）：本次仅针对结构化追问链路
5. **"上次开头句式（lead 前 12 字）"提示一并移除**：风格已由后端切换，句式相似度风险大幅降低，省 token优先；若上线后观察到跨风格句式雷同再补回

## 五、验证步骤（Verification）

1. 单元测试：`cd mingli-agent/backend && ./venv/bin/python -m pytest tests/test_followup_consistency.py -v` 全过（含新增 TestStyleRotation）
2. 全量回归：`./venv/bin/python -m pytest tests/ -v`（排盘容错/正确性/校验等既有测试不受影响）
3. Token 对比：`build_structured_prompt` L1795 已有 prompt 长度打印，对比重构前后同一命盘 prompt 长度，预期减少约 900-1100 字符
4. 轮换验证：临时脚本连续调用 `pick_styles` 模拟 12 轮历史，断言每轮风格不与前 8 轮重复
5. `git grep "现状承接式"` 等确认旧风格全量枚举文本已从 prompt 移除（仅保留在 report_styles.py 库中）
