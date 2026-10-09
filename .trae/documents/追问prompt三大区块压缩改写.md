# 追问 Prompt 零影响省 Token 方案（V2：上下文缓存优先，压缩降级为备选）

## 一、摘要（Summary）

用户要求"不希望有任何（生成效果）影响"。V1 的三大区块压缩方案存在 2-3 处真实风险（对照示例削减、赔偿视角规则压缩、文案变密），**V2 改为不压缩任何规则文本**，转而利用 DashScope 上下文缓存机制降低计费 token：

**核心思路**：当前 prompt 的动态内容（命盘数据/历史摘要/用户问题/本轮风格）散落在前中部，导致跨请求公共前缀只有"# 角色"约 180 字，官方隐式缓存完全吃不到。**将 prompt 重排为"静态规则在前 + 动态信息收尾"，使约 15.5k 字（≈9k token）静态部分成为可缓存前缀**。官方文档明确缓存"不影响响应质量"，命中部分按标准输入价 **20%** 计费（隐式缓存，自动生效）。

预期收益：命中时输入成本约降 60-70%（9k token 按 20% 计），TTFT 缩短；规则文本零删改，生成效果零影响。

V1 压缩方案保留为备选（第四节），仅在缓存收益不达标时再评估启动。

## 二、现状分析（Current State Analysis）

### 2.1 缓存可行性（已核实）

- **模型支持**：`qwen3.7-flash` 在 DashScope 上下文缓存官方支持列表中（Qwen Flash 类目，含显式/隐式缓存）
- **隐式缓存**：自动生效、无法关闭、无需配置；命中部分按标准输入价 20% 计费；要求公共前缀 ≥256 token；命中率不保证（取决于请求前缀重复度——本应用所有用户共享同一份静态规则文本，前缀重复度天然高）
- **显式缓存**：需 `cache_control` 标记，命中按 10% 计费，但创建按 125% 计费且缓存仅 5 分钟有效——追问场景用户两轮间隔常超 5 分钟，显式缓存可能反而更贵，本期不做
- **质量影响**：官方表格明确"对响应质量的影响：无"（缓存是服务端计算复用，不改变模型输入）

### 2.2 当前 prompt 结构问题（followup_structured.py build_structured_prompt）

| 位置 | 内容 | 动静态 |
|---|---|---|
| L159 起 | # 角色 | 静态 |
| L164-L182 | # 命盘数据（排盘字段注入） | **动态**（每人不同） |
| L184-L233 | # 命盘权威与方向锁定 | 静态（除 L234 占位符） |
| L234 | {history_section}（历史对话摘要） | **动态** |
| L235-L236 | # 用户问题 | **动态** |
| L238-L280 | # 输出格式 / ## 硬性JSON渲染约束 | 静态 |
| L281-L392 | # 内容撰写硬性规范 / ## 禁止清单 / 声明 / 自检 | 静态（除规则3/10 的风格注入行） |
| L394-L444 | ## 对照示例 | 静态 |

动态内容插在 L164 和 L234，把静态规则切成三段 → 公共前缀仅约 180 字 < 256 token 门槛，缓存完全失效。

### 2.3 代码配套现状

- usage 已在采集：followup_structured.py L1872-L1876（prompt_tokens/completion_tokens/total_tokens），可直接扩展记录 cached_tokens
- 风格注入现状：`本次开头风格：**X**（desc）`/`本次总结风格：**Y**（desc）` 两行在规则 3/10 内（上一轮改动引入），属于动态内容，必须移到尾部
- 仅 1 处方向性措辞依赖位置：L187 "引用**上文**命盘数据栏"（重排后命盘数据在下方，需改措辞）；L336 "上方第1.5条"指向的 1.5 条仍在静态区内且顺序不变，无需改

## 三、改动方案（Proposed Changes）

### 改动 1：重排 `build_structured_prompt`（followup_structured.py L148-L445）

新结构（**所有原文案逐字保留，仅移动位置**）：

```
【静态前缀 —— 跨请求完全一致，构成缓存前缀】
# 角色
# 命盘权威与方向锁定（删除尾部 {history_section} 占位符；L187 "上文命盘数据栏" → "末尾命盘数据栏"）
# 输出格式（JSON结构示例）
## 硬性JSON渲染约束
# 内容撰写硬性规范（规则3/10 的风格注入行改为静态引用措辞，见改动2）
## 禁止清单
## 全报告统一适用声明
## 输出前自检
## 对照示例

【动态尾部 —— 新增 "# 本次会话信息" 区块，按序包含】
# 本次会话信息
## 命盘数据（原 # 命盘数据 全文照搬）
## 历史对话摘要（原 history_section 内容，无历史时此小节省略）
## 本轮风格要求（改动2 新增）
## 用户问题（原 # 用户问题 内容）
```

重排依据："指令在前、任务材料在后"是标准 prompt 实践（recency 效应对尾部任务材料反而更有利）；规则对"命盘数据栏"的引用改为按标签名引用，与位置无关。

### 改动 2：风格注入移出静态区

- 规则 3 中 `本次开头风格：**{opening_style[0]}**（{opening_style[1]}）` 一行改为静态措辞：
  `- **开头风格以后方"本次会话信息 > 本轮风格要求"为准**，必须严格按指定风格开篇，禁止套用其他开头风格`
- 规则 10 总结风格行同理改为静态引用措辞
- 动态尾部"本轮风格要求"小节内容：`开头风格：**X**（desc）；总结风格：**Y**（desc）。必须分别按指定风格执行开篇与总结。`
- `generate_followup_structured` 中 `pick_styles`/盖章逻辑不变

### 改动 3：缓存命中观测（followup_structured.py L1872-L1876 usage 日志处）

```python
cached_tokens = 0
details = getattr(usage, "prompt_tokens_details", None)
if details is not None:
    cached_tokens = getattr(details, "cached_tokens", 0) or 0
if not cached_tokens:
    cached_tokens = getattr(usage, "cached_tokens", 0) or 0
logger.info(f"[StructuredFollowup] prompt={prompt_tokens} cached={cached_tokens} ...")
```

（兼容 OpenAI 格式的 prompt_tokens_details.cached_tokens 与 DashScope 原生 cached_tokens 两种返回。）

### 改动 4：测试补充（tests/test_followup_consistency.py）

新增 `TestPromptCachingLayout`：
- `test_static_prefix_stable`：用两个不同 FIXED_CONTEXT（改 user_question/命盘字段）各构建一次 prompt，断言两者**公共前缀长度 ≥ 5000 字**（证明静态区在前、动态区在尾）
- `test_dynamic_section_order`：prompt 含 "# 本次会话信息"，且其位置晚于 "## 对照示例"；"本轮风格要求" 含选中的风格名
- `test_anchor_phrases_intact`：复用 TestPromptConsistencyRules 的 15 个锚点短语断言（重排不得丢字）
- 现有测试回归：TestPromptConsistencyRules / TestHistorySummaryExtraction / TestStyleRotation 全过（注意：`test_prompt_injects_only_selected_styles` 的断言串 `本次开头风格：**痛点直击式**` 需同步改为新措辞下的断言）

## 四、备选方案（V1 压缩，本期不执行）

若上线观测后缓存收益不达预期（如区域不支持隐式缓存、命中率过低），再启动 V1 内容压缩方案（详见 git 历史与本文件旧版讨论）：对照示例 6组→3+1组、命盘权威去例压缩、closing/block 规则去重，预期再省约 6700 字（−38%），但需配合灰度对比验证生成质量。

## 五、假设与决策（Assumptions & Decisions）

1. **零文案删改**：除 2 处必要措辞调整（L187 "上文"→"末尾"、规则3/10 风格行改静态引用）外，所有规则/示例逐字保留
2. **只用隐式缓存**：免配置、命中 20% 计费、无 5 分钟过期问题；显式缓存（10%）留作后续按用户提问节奏评估
3. **重排顺序**：静态规则全部前置，动态四件套（命盘数据/历史摘要/本轮风格/用户问题）统一收进"# 本次会话信息"，用户问题放最末尾（recency）
4. **不依赖缓存必中**：即使缓存未命中，功能与现状完全一致，仅成本收益打折；命中率通过改动 3 日志观测
5. **探针/日志检查字典**：全部锚点短语在静态区原样保留，`_rule_checks`/`_consistency_checks`/`_verdict_consistency_checks` 无需改动

## 六、验证步骤（Verification）

1. 单测：`cd mingli-agent/backend && ./venv/bin/python -m pytest tests/test_followup_consistency.py -v` 单元测试全过（含新增 TestPromptCachingLayout）
2. 全量回归：`./venv/bin/python -m pytest tests/ -q`（存量失败 test_bazi_paipan 流月断言除外）
3. 总长不变验证：重排后 prompt 总长与重排前差值 < 200 字（仅措辞微调），证明无内容丢失
4. 公共前缀验证：两个不同命盘/问题的 prompt 公共前缀 ≥ 15000 字（脚本对比）
5. 缓存命中观测（尽力而为，API 可用时）：真实调用一次追问，查日志 `cached=` 字段；同一静态前缀第二次请求应出现 cached_tokens > 0
6. 生成效果对比（尽力而为）：重排前后同一命盘同一问题各跑一次 e2e，人工抽查报告无异常（预期无差异）
