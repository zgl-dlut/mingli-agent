# Bug 修复方案：无效问题误判 + yongshen UnboundLocalError + MySQL 断连

## 问题清单

### Bug 1：有效命理问题被误判为无效

**现象**：用户问 "27年4月有没有年终奖入账" 被 AI 回复 "没有发现您有明确的命理咨询需求哦，本次不扣除积分～"

**根因定位**：`skill_prompts.py` 的 `validate_user_question()` 函数有三道关卡，全部未命中：

| 关卡 | 用户问题 | 是否命中 | 原因 |
|---|---|---|---|
| question_words（疑问词列表） | "有没有年终奖入账" | ❌ | 列表有"会不会/什么/怎么"，但**缺"有没有"** |
| _match_skill_type（专项技能关键词） | "年终奖" | ❌ | "年终奖"不在任何 SKILL_PROMPTS 的 keywords 里 |
| _CORE_RELEVANT_KEYWORDS（命理专属名词） | "年终奖" | ❌ | 列表有"财运/赚钱/加薪"但**缺"年终奖/入职/赔偿"等具体词** |

三关全 False → 命中 `if not matched_skill` 分支 → 又因 `not has_question_word and not has_core_relevant` → 返回无效。

**更深层问题**：验证逻辑整体偏保守。命理用户常用**陈述式提问**（"当下正官当令的时候"、"明年本命年"、"走到未运了"），不带疑问词，且涉及具体名词（正官/七杀/偏财/年终奖/入职/赔偿）不在关键词表中。

### Bug 2：UnboundLocalError: cannot access local variable 'yongshen'

**现象**：前端弹错误框 `生成失败(UnboundLocalError: cannot access local variable 'yongshen' where it is not associated with a value)`

**根因定位**：`followup_structured.py` 的 `_build_retry_hint` 内部函数（L3571）存在 **Python 闭包变量名遮蔽**：

- L3470：外层函数 `yongshen = analysis_data.get("用神", "") or ""`（闭包变量）
- L3595：`_build_retry_hint` 内部引用闭包变量 `yongshen` → `f"命理硬逻辑：用神（{yongshen}）当令..."`
- L3756：`_build_retry_hint` 内部条件分支 **同名赋值** `yongshen = analysis_data.get("用神", "")`

Python 编译器发现函数体内有 `yongshen = ...`，把整个 `_build_retry_hint` 作用域内的 `yongshen` 视为**局部变量**。L3756 的赋值仅在 `if v["yongshen_wuxing_mismatch"]:` 成立时执行。如果条件不成立但 L3595 又需要访问 → 局部变量未初始化 → `UnboundLocalError`。

**触发路径**：当 `v["yongshen_wuxing_mismatch"]` 为空但 `v["yongshen"]` 不为空时（用神逻辑矛盾违规存在但五行错误违规不存在），L3595 引用 yongshen 但 L3756 未执行赋值 → crash。

### Bug 3：MySQL Lost connection to MySQL server during query

**现象**：后端日志出现 `sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (2013, 'Lost connection to MySQL server during query')`

**根因**：SQLAlchemy 连接池默认 `pool_recycle=-1`（永不回收），MySQL 默认 `wait_timeout=28800`（8小时），如果连接闲置超过 8 小时被 MySQL 断开，SQLAlchemy 不知情还在用 → 断连。

---

## 修复方案

### 修复 1：validate_user_question 更宽松（skill_prompts.py）

**文件**：`backend/app/services/skill_prompts.py`

**改动 A — question_words 补词**（L1453-1456）

追加：`"有没有"`、`"是不是有"`、`"还"`、`"还能"`、`"会不会被"`、`"到账"`、`"入账"`

**改动 B — _CORE_RELEVANT_KEYWORDS 补具体财运/事业词**（L1391-1403）

追加：
- 财运具体：`"年终奖"`、`"奖金"`、`"分红"`、`"入账"`、`"到账"`、`"赔偿"`、`"裁员"`、`"辞退"`
- 事业具体：`"入职"`、`"离职"`、`"跳槽"`（已存在）、`"转正"`、`"offer"`
- 命理十神具体：`"正官"`、`"七杀"`、`"正财"`、`"偏财"`、`"正印"`、`"偏印"`、`"食神"`、`"伤官"`、`"比肩"`、`"劫财"`
- 时间表达：`"当下"`、`"现在"`、`"这时候"`、`"的时候"`、`"本命年"`、`"走到"`（大运切换）

**改动 C — 默认放行策略**（L1480-1491）

当前逻辑：三关全 False → 拦

改为：如果问题里**有年份/时间模式**（`\d+年`/`明年`/`今年`/`当下`/`什么时候`），或有**命理术语片段**（正官/七杀/偏财等），**即使三关未命中也放行**。让 LLM 自己判断能否回答，而不是关键词硬拦。

### 修复 2：_build_retry_hint 变量名遮蔽（followup_structured.py）

**文件**：`backend/app/services/followup_structured.py`

**改动**：L3756 内部赋值的变量名从 `yongshen` 改为 `ys_local`（或其他不同名），避免遮蔽闭包变量。同时 L3758-3764 内引用也对应改名。

```python
# 修复前（L3756）：
yongshen = analysis_data.get("用神", "")  # ← 遮蔽闭包变量！
jishen = analysis_data.get("忌神", "")
parts.append(f"...用神：{yongshen}，忌神：{jishen}...")

# 修复后：
ys_local = analysis_data.get("用神", "")  # ← 不同名，不遮蔽
js_local = analysis_data.get("忌神", "")
parts.append(f"...用神：{ys_local}，忌神：{js_local}...")
```

### 修复 3：MySQL 连接池配置（数据库配置文件）

**文件**：查 config.py 里的 `DATABASE_URL` 构建，或 db/session.py 里的 engine 创建

**改动**：在 SQLAlchemy `create_engine` 调用里加 `pool_recycle=1800`（30分钟回收，小于 MySQL 默认 8 小时 `wait_timeout`）+ `pool_pre_ping=True`（每次使用前 ping 一下，断了自动重连）。

---

## 验证清单

- [ ] "27年4月有没有年终奖入账" → 能通过 validate_user_question
- [ ] "当下正官当令的时候" → 能通过
- [ ] 模拟 `_build_retry_hint` 中 yongshen_wuxing_mismatch 为空但 yongshen 不为空的场景 → 不 crash
- [ ] MySQL 连接闲置 8 小时后再查询 → 不 Lost connection
- [ ] 跑一遍现有单元测试 pytest → 无回归

---

## 风险

| 风险 | 处理 |
|---|---|
| 关键词补多了，真·无关问题（如"今天吃什么好"）也被放行 | 默认放行策略里保留 `_has_irrelevant_keyword_without_exemption` 的黑名单拦截，无关话题+无命理名词还是会被拦 |
| Python 变量改名可能漏改某个引用 | grep 确认 `_build_retry_hint` 内部所有引用都改对 |
| pool_recycle 加了之后是否有副作用 | pool_recycle 是标准用法，30分钟是常规值，无副作用 |
