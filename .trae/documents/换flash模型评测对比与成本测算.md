# 换 flash 模型评测对比与成本测算

## Summary
生产 AI 模型用的是 qwen3-max 系列（.env `AI_MODELS=qwen3.8-max`），成本高（用户已花100元不含免费额度，今天又充135元）。目标：本地切 qwen-flash 跑同一评测用例，对比 max 基准的生成质量（硬性检查/编造/软性分）+ 实测 token 消耗算真实价差，给出"flash 能否替代 max"的结论。本次只本地测，不动生产。

## Current State Analysis

### 模型配置机制（[config.py#L11-L27](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/config.py#L11)）
- `AI_MODELS`（多模型池）优先，生产 [.env#L14](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/.env#L14) 设 `AI_MODELS=qwen3.8-max` → 只跑 max
- 代码默认 `AI_MODEL=qwen-3.6-flash` / `AI_MODELS=qwen-3.6-flash,qwen-2.5-7b,qwen2-7b-chat`
- ⚠️ **代码默认的 `qwen-3.6-flash` 非官方名，可能调不通**。官方可用 flash 名：`qwen-flash`（Qwen3 Flash，最便宜）或 `qwen3.5-flash`。代码内部已用 `qwen-flash`（[followup_structured.py#L2489](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L2489) 矛盾检测、[llm_scorer.py#L243](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/eval/llm_scorer.py#L243) 评测打分），证明 `qwen-flash` 可调通
- 切换只需改 .env `AI_MODELS` 重启，[ai_service.py#L94-L123](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/ai_service.py#L94) `parse_models` 按配置构造模型池，`generate_ai_response` 按 model_order 优先级调用
- [followup_structured.py#L3505](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L3505) 主生成用 `model_pool[0]`

### max 基准评测结果（1994财运追问，已有）
- 硬性检查：结构0 叙事0 命盘使用0 总0 ✅通过
- 编造检测：编造=None 严重程度=None（无编造）
- 软性评分：avg 86.6
- overall_pass: False（非编造问题）

### 价格对比（阿里云百炼，0-128K区间，非缓存）

| 模型 | 输入(元/百万tok) | 输出(元/百万tok) | 相对 max |
|---|---|---|---|
| qwen3-max | 2.5 | 10 | 1× |
| qwen-flash | 0.15 | 1.5 | 输入1/17，输出1/6.7 |
| qwen3.5-flash | 0.2 | 2 | 输入1/12.5，输出1/5 |

**理论速算**（典型生成：输入10K + 输出3K tokens）：
- max：0.025 + 0.03 = 0.055元/次
- flash：0.0015 + 0.0045 = 0.006元/次
- **flash 约便宜 9 倍**
- 用户已花100元 max ≈ 1800次生成 → 同量 flash 约 11元，省约 89元

> 实际价差需按实测 token 数算（system prompt 大，可能走 32K-128K 档，max 更贵）。执行阶段用真实 token 计数复算。

## Proposed Changes

### 步骤1：本地临时改 .env 切 flash（不动生产）
- 改本地 [backend/.env](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/.env#L14) L14：`AI_MODELS=qwen3.8-max` → `AI_MODELS=qwen-flash`
- ⚠️ 用官方名 `qwen-flash`，不用代码默认的 `qwen-3.6-flash`（非官方名可能调不通）
- 改完重启本地后端（或直接跑脚本，脚本会重新 import config）

### 步骤2：跑同一评测用例（1994财运追问，对比 max 基准）
- 复用之前的临时脚本模式（`generate_full_analysis` + `generate_followup_structured` + `check_structure`/`check_narrative`/`check_chart_usage`/`evaluate_report`）
- 用例：1994-09-22 20:30 山东日照 女，问题"我未来的财务压力和财运"（与 max 基准完全一致）
- **记录 token 消耗**：在 [ai_service.py](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/ai_service.py) `generate_ai_response` 的 chunk 流里抓 `usage`（dashscope 兼容模式返回 prompt_tokens/completion_tokens），累计输入/输出 token

### 步骤3：对比 max 基准 4 维度

| 维度 | max 基准 | flash 结果 | 判定 |
|---|---|---|---|
| 硬性检查（结构/叙事/命盘使用） | 0/0/0 | 实测 | flash 应=0 |
| 编造检测 | None（无编造） | 实测 | flash 应无 high 编造 |
| 软性评分 avg | 86.6 | 实测 | flash ≥80 可接受 |
| 报告质量主观 | （对比参考） | 开篇/子话题/命理逻辑 | 人工看 |

### 步骤4：实测价差计算
- 用步骤2记录的实测 token 数 × 单价
- max：(输入tok/1M × 2.5) + (输出tok/1M × 10)
- flash：(输入tok/1M × 0.15) + (输出tok/1M × 1.5)
- 输出"单次生成省多少元"+"按用户已花100元反推同量 flash 成本"

### 步骤5：给结论与建议
- 若 flash 质量可接受（硬性0 + 无high编造 + 软性≥80）→ 建议生产切 flash，估算月成本降幅
- 若 flash 质量明显下降 → 备选方案：生成用 flash + 质检/编造检测用 max（分级），或用 qwen3.5-flash（稍贵更强）
- 不擅自改生产，给用户决策依据

## Assumptions & Decisions

1. **flash 模型用 `qwen-flash`**（官方名，最便宜 0.15/1.5元，代码内部已用证明可调通），不用代码默认的 `qwen-3.6-flash`（非官方名）
2. **评测用例用1994财运追问**（有 max 基准 avg86.6/编造None/硬性0，苹果对苹果对比）。如用户想加更多用例（首次报告/其他问题），执行后可补
3. **只本地测，不动生产**。生产切换需用户确认后再做（scp .env + 重建容器）
4. **token 记录**：dashscope 兼容模式在流式最后一个 chunk 返回 usage，需在 ai_service 抓取（若抓不到，用 tiktoken 估算输入 + 数输出字符估算输出）
5. **价格用 0-32K 档算 max**（命理 system prompt 约 8-10K，输出 2-4K，单次请求多在 32K 内）。若实测超 32K，按实际档位复算

## Verification

1. **flash 可调通**：本地跑脚本，generate_followup_structured 正常流式输出报告，无 model not found 错误
2. **评测对比表**：4 维度（硬性/编造/软性/主观）flash vs max 并排
3. **价差数据**：实测 token 数 + 单次生成 max vs flash 成本 + "100元 max 同量 flash 多少钱"
4. **结论**：flash 能否替代 max / 是否需分级方案 / 生产切换建议
