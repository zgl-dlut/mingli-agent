# 流年流月准确度代码检测兜底可行性评估

## 评估结论

**流年准确度**：现有六类代码检测已基本覆盖，**无需新增**。
**流月准确度**：技术上可行，但用户决定**不做代码检测**（表达太多样、误伤风险高，保持现状靠 prompt 约束）。

本评估为决策记录，不涉及代码实施。

## 现有代码检测盘点（已完成，六类）

[followup_structured.py](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py) 已实现六类命理逻辑代码兜底，prompt 失效时代码层拦截重试：

| 检测 | 函数 | 覆盖范围 |
|------|------|------|
| 凶年启动类行动 | `_detect_unfavored_year_actions` | 凶年+启动词无否定=违规 |
| 凶年贴正向标签 | `_detect_favored_label_on_unfavored_year` | 凶年+小吉/回暖/向好等=违规（含段落级+回暖起点） |
| 吉年反向劝退 | `_detect_favored_year_discouraged_actions` | 吉年+否定启动词=违规 |
| 用神逻辑矛盾 | `_detect_yongshen_logic_conflict` | 用神五行+旺+耗损共现=违规 |
| 术语黑名单 | `_detect_forbidden_terms` | 杀印相生/寅午半合火局/伤官见官等=违规 |
| 干支纪时写法 | `_detect_ganzhi_time_notation` | 丁酉月/丁未流年格式=违规 |

## 流年准确度分析

**已覆盖的维度**：
- 凶年不能启动（`_detect_unfavored_year_actions`）
- 吉年不能劝退（`_detect_favored_year_discouraged_actions`）
- 凶年不能贴正向标签（`_detect_favored_label_on_unfavored_year`，含"回暖起点必须是吉/平年"）
- 用神当令吉年=帮身，不能说成耗损（`_detect_yongshen_logic_conflict`）

**剩余缺口（不建议代码化）**：
- 吉年被"降级标签"（如大吉年说成"平年/普通年份"）：边界模糊，"2026是不错的一年"vs"2026大吉"难界定违规
- 流年整体叙事基调与吉凶的弱冲突：主观判断，无法确定性检测

结论：流年方向锁定已充分，剩余缺口属于表述弱化而非方向错误，代码硬检测误伤高于收益。

## 流月准确度分析

**数据可行性**：技术上可行。[analysis_data["重点流年"]](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/skills/orchestrator.py#L514) 每条流年都带完整 `liuyue`（12个月，每月有 judge：大吉/吉/凶/大凶/平），由 [analyze_liuyue](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/skills/divination/dayun_liunian_skill.py#L993) 生成。代码检测可取完整数据（不限 prompt 里的前5条）。

**可检测的违规**：
- 凶流月（凶/大凶）+ 明确正向行动断言（"9月适合启动/可推进"）= 违规
- 吉流月（大吉/吉）+ 明确负向行动断言（"9月不宜/慎入/避开"）= 违规

**用户决策：不做**。理由：
1. 月份表达太多样（公历数字/节气/区间），节气表达（立秋/白露/霜降）跨月边界难精确归属
2. 吉凶词多样，合理中性描述（"9月有阻力需注意"）易误判为负向断言
3. 误伤风险高于前三类（用神/术语/干支），收益不确定

保持现状：流月准确度靠 prompt 约束（"具体月份建议必须基于流月吉凶数据，禁止自行推测月份"），不做代码硬检测。

## 假设与决策

1. **流年检测不新增**：现有六类已覆盖方向性错误，剩余缺口边界模糊。
2. **流月检测不做**：用户基于误伤风险决定保持现状。
3. **本评估无代码实施**：结论为"维持现有六类检测"，无需改动文件。

## 验证步骤

无需验证（无代码变更）。现有六类检测已在前序变更中验证并通过构造数据测试。
