# 测试报告：追问报告结构化改造

**日期**：2026-08-08
**测试范围**：追问报告从 Markdown 渲染改为 JSON 直渲染的完整改造
**测试文件**：4 个测试文件，84 个测试用例（后端 62 + 前端 22）

---

## 一、测试文件清单

| 文件 | 框架 | 用例数 | 测试目标 |
|---|---|---|---|
| `backend/tests/test_extract_and_fix_json.py` | pytest | 19 | JSON 容错函数三层处理 |
| `backend/tests/test_report_schema.py` | pytest | 13 | Pydantic 模型校验 |
| `backend/tests/test_bazi_paipan.py` | pytest | 30 | 排盘正确性 + 流年流月一致性 |
| `frontend/src/__tests__/FollowupReportView.test.tsx` | vitest | 22 | renderBold 加粗解析 + isStructuredReport JSON 判断 |

---

## 二、后端测试详情

### 2.1 JSON 容错函数（19 个）

**文件**：`test_extract_and_fix_json.py`
**目标函数**：`_extract_and_fix_json`（三层处理：markdown 去包裹 → 截取完整 JSON → 修复裸换行）

| # | 测试名 | 验证内容 |
|---|---|---|
| ① | normal_json_passthrough | 正常 JSON 直接通过 |
| ② | markdown_json_block_wrap | ` ```json ` 包裹被去除 |
| ③ | markdown_block_wrap_no_lang | 只有开头 ` ``` ` 没有结尾 |
| ④ | long_repeated_output | 超长重复输出截取第一个完整 JSON |
| ⑤ | truncated_brackets | 括号不配平（max_tokens 截断） |
| ⑥ | string_braces_not_counted | 字符串值里 `{}` 不被计数 |
| ⑦ | escaped_quote_not_string_boundary | 转义引号 `\"` 不误判为字符串边界 |
| ⑧ | nested_braces_and_arrays | 嵌套大括号/数组深度归零 |
| ⑨ | backslash_before_brace | `\\{` 反斜杠跳过不增深度 |
| ⑩ | json_with_prefix_text | JSON 前有非 JSON 文本 |
| ⑪ | no_brace_found | 完全没有 `{` 不崩溃 |
| ⑫ | completely_garbled | 完全乱码不崩溃 |
| ⑬ | bare_newline_in_string | 字符串裸换行修复为 `\n` |
| ⑭ | escaped_newline_not_double_fixed | 已转义 `\n` 不重复修复 |
| ⑮ | structure_newlines_not_fixed | 结构层换行不修复 |
| ⑯ | bare_newline_in_key | key 里裸换行不崩溃 |
| ⑰ | triple_combination | 三层问题同时存在 |
| ⑱ | empty_string | 空字符串 |
| ⑲ | whitespace_only | 纯空白 |

### 2.2 Pydantic 模型校验（13 个）

**文件**：`test_report_schema.py`
**目标模型**：`FollowupReport`（opening / subtopics / summary）

| # | 测试名 | 验证内容 |
|---|---|---|
| ① | valid_full_report | 合法 JSON 全字段通过 |
| ② | opening_only_lead | opening 只有 lead |
| ③ | opening_only_verdict | opening 只有 verdict |
| ④ | missing_opening | 缺 opening 报错 |
| ⑤ | missing_subtopics | 缺 subtopics 报错 |
| ⑥ | missing_summary | 缺 summary 报错 |
| ⑦ | empty_subtopics_array | 空数组合法 |
| ⑧ | keyword_block | type=keyword 解析 |
| ⑨ | narrative_block | type=narrative 解析 |
| ⑩ | group_block | type=group 解析 |
| ⑪ | unknown_block_type | 未知 type 报错 |
| ⑫ | unknown_item_format | 未知 item_format 报错 |
| ⑬ | item_format_defaults_to_list | 默认 list |

### 2.3 排盘正确性 + 流年流月一致性（30 个）

**文件**：`test_bazi_paipan.py`

**Part 1: 排盘核心算法（18 个）**

| # | 测试名 | 验证内容 |
|---|---|---|
| ① | year_pillar_after_lichun | 立春后年柱用当年 |
| ② | year_pillar_before_lichun | 立春前年柱用前一年 |
| ③ | day_pillar_known_date | 日柱 1949-10-01=甲子 |
| ④ | hour_pillar_zi_hour | 子时五鼠遁 |
| ⑤ | hour_pillar_wu_hour | 午时五鼠遁 |
| ⑥~⑮ | 十神 10 种关系 | 比肩/劫财/食神/伤官/偏财/正财/七杀/正官/偏印/正印 |
| ⑯ | shishen_yin_day_master_乙 | 阴干日主乙（历史 bug 验证） |
| ⑰ | shishen_yin_day_master_丁 | 阴干日主丁（历史 bug 验证） |
| ⑱ | full_bazi_calculation | 完整排盘结构 |

**Part 2: 流年流月数据一致性（12 个）**

| # | 测试名 | 验证内容 |
|---|---|---|
| ① | key_liunian_exists | 重点流年字段存在且非空 |
| ② | key_liunian_structure | 数据结构完整（year/ganzhi/judge/reason/detail/liuyue） |
| ③ | liunian_ganzhi_correct | 流年干支与 `_year_to_ganzhi` 一致 |
| ④ | liunian_ganzhi_in_tiangan_dizhi | 干支字符在天干地支列表内 |
| ⑤ | liunian_wuxing_correct | detail 五行与干支对应 |
| ⑥ | liuyue_has_12_months | 每个流年 12 个月流月 |
| ⑦ | liuyue_month_ganzhi_correct | 流月干支五虎遁推算正确 |
| ⑧ | liunian_judge_consistent_with_yongshen | 吉凶与用神/忌神一致 |
| ⑨ | analysis_data_2_complete | 命例2交叉验证 |
| ⑩ | liunian_ganzhi_correct_case2 | 命例2流年干支正确 |
| ⑪ | context_contains_liunian_data | LLM 上下文包含排盘数据 |
| ⑫ | context_liunian_matches_analysis | 上下文流年数据与排盘一致（未被篡改） |

---

## 三、前端测试详情

### 3.1 renderBold 加粗解析（12 个）

**文件**：`FollowupReportView.test.tsx`

| # | 测试名 | 验证内容 |
|---|---|---|
| ① | 无加粗标记 | 普通文本正常渲染 |
| ② | 单个加粗 | `**加粗**` → `<strong>` |
| ③ | 多个加粗 | 全部渲染 |
| ④ | 加粗在开头 | 边界位置 |
| ⑤ | 加粗在结尾 | 边界位置 |
| ⑥ | 未闭合加粗 | `**加粗` 不渲染 |
| ⑦ | 空加粗 | `****` 不渲染 |
| ⑧ | 连续加粗 | `**a****b**` |
| ⑨ | 含特殊字符 | `**2026-2027年**` |
| ⑩ | 换行渲染 | `\n` → `<br/>` |
| ⑪ | 跨行加粗 | `**第一行\n第二行**` |
| ⑫ | 空字符串 | 不崩溃 |

### 3.2 isStructuredReport JSON 判断（10 个）

| # | 测试名 | 验证内容 |
|---|---|---|
| ① | JSON 格式 | 返回 true |
| ② | Markdown 格式 | 返回 false |
| ③ | 空字符串 | 返回 false |
| ④ | 无效 JSON | 返回 false |
| ⑤ | 缺 opening | 返回 false |
| ⑥ | 缺 subtopics | 返回 false |
| ⑦ | 缺 summary | 返回 false |
| ⑧ | JSON 前有空白 | 仍能识别 |
| ⑨ | JSON 数组 | 返回 false |
| ⑩ | JSON 字符串值 | 返回 false |

---

## 四、测试过程中发现并修复的 Bug

| Bug | 文件 | 修复 |
|---|---|---|
| `renderBold` 正则 `.` 不匹配 `\n`，跨行加粗失效 | FollowupReportView.tsx | 改用 `[\s\S]` |

---

## 五、边界条件覆盖分析

### 5.1 已覆盖

- 立春前后年柱分界
- 阴干日主十神（历史 bug）
- JSON 各种异常输出（乱码/截断/重复/裸换行）
- 加粗各种边界（未闭合/空/连续/跨行）

### 5.2 未覆盖（建议后续补充）

| 边界场景 | 风险 | 建议优先级 |
|---|---|---|
| **节气交接日出生**（立春当天） | 年柱/月柱判定可能 ±1 天误差 | 高 |
| **预计算表外年份**（<2023 或 >2045） | 回退寿星公式，≤1 天误差 | 中 |
| **大运列表为空时 get_key_years** | 所有流年被 `continue` 跳过 | 高 |
| **子时跨日**（23:00-01:00） | 日柱可能用次日或当日 | 中 |
| **极端经纬度**（非中国地区） | 节气时间不适用 | 低 |

### 5.3 闰月说明

排盘系统**不处理闰月**——这是正确的。八字排盘用节气定月柱，不用农历闰月。测试无需覆盖闰月场景。

### 5.4 流年数据处理分支

`get_key_years` 的唯一跳过分支是 `_find_dayun_for_year` 返回空 `ganzhi` 时 `continue`。如果大运列表为空，所有流年都会被跳过，导致 `analysis_data["重点流年"]` 为空列表。现有测试用例的大运列表非空，未覆盖此分支。

---

## 六、运行方式

```bash
# 后端
cd mingli-agent/backend
python3 -m pytest tests/test_extract_and_fix_json.py tests/test_report_schema.py tests/test_bazi_paipan.py -v

# 前端
cd mingli-agent/frontend
npx vitest run src/__tests__/FollowupReportView.test.tsx
```

端到端测试（依赖真实 LLM）：
```bash
cd mingli-agent/backend
python3 tests/test_structured_followup_e2e.py
```
