# Gender 归一化层实现计划（修订版）

## Context（为什么做这个改动）

大运顺逆排 bug 根因：gender 字段中英文数字三格式并存（前端表单 value 英文 `male/female`、排盘算法历史期望中文 `男/女`、微信天生返回数字 `1/2/0`），而**所有 API 入口原样透传、无归一化层**，算法靠 `("男","male","m","1")` 兜底全收。后果：单元测试用中文 `"男"/"女"` 假阳性通过，生产 DB 存英文时旧代码 `gender=="男"` 失效，29 个 person（56%）顺逆排算反。

探索阶段发现**原计划严重低估改动范围**：不止追问链路 [followup_structured.py:3056](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py#L3056) 有 `gender_cn` 转中文喂算法，**首次报告链路 [ai_service.py:305](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/ai_service.py#L305)（商业报告）和 [ai_service.py:351](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/ai_service.py#L351)（首次结构化报告）也有同样的 `gender_cn` 转中文喂 `generate_full_analysis`**。三处转换点每处都有两个用途：①喂算法（要英文）②喂 prompt builder 展示（要中文）。若算法层只认英文且外部不调，首次报告和追问都会崩。

**前端展示层已规范**：[HistoryPanel.tsx:233-240](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/components/HistoryPanel.tsx#L233-L240) 已做 `person.gender==='male'?'男':'女'` 映射，[types/index.ts](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/types/index.ts#L11-L28) 类型限定 `'male'|'female'`，前端统一是"英文值+中文展示映射"模式，DB 存英文对前端展示基本无影响。

目标：**入口归一化英文 + 算法层 fail-fast + generate_full_analysis 内部防御归一化 + 算法用英文/展示用中文彻底分离**。存量已是英文无需迁移。

## 核心设计：两层归一化 + 用途分离

- **入口归一化（包容）**：`normalize_gender(gender) -> "male" | "female"`，识别 `男/女/male/female/m/f/1/2/0` 全变体。3 个 Pydantic Request 的 `field_validator` 调用，保证 DB 存英文。
- **编排层防御归一化**：`generate_full_analysis` 第一行 `gender = normalize_gender(gender)`，喂 `calculate_bazi` 用英文。防御外部任何调用方传中文/数字，单点兜底。
- **算法消费层（严格）**：`calculate_dayun` 删兜底，只认 `male/female`，其他 `raise ValueError`（fail-fast）。
- **用途分离原则**：三处 `gender_cn` 转换点保留变量用于"喂 prompt builder 展示"（中文），但"喂 `generate_full_analysis`"的传参改成传英文 `gender`。

## 改动清单

### 1. 归一化函数 + 算法层 fail-fast
**文件**：`backend/app/services/bazi_service.py`
- 顶部新增 `normalize_gender(gender: str) -> str`：`lower().strip()` 后，`男/male/m/1 → "male"`，`女/female/f/2/0 → "female"`，其他 `raise ValueError(f"无法识别的性别值: {gender}")`。
- `calculate_dayun`（约 1094-1097 行）：删 `_g in ("男","male","m","1")` 兜底，改为只认 `male`/`female`，其他 `raise ValueError`。

### 2. 编排层防御归一化（关键兜底）
**文件**：`backend/app/skills/orchestrator.py`
- `generate_full_analysis`（205 行）函数体第一行加 `gender = normalize_gender(gender)`（从 bazi_service import），喂 `calculate_bazi` 用英文。这样三处外部调用即使传中文 `gender_cn` 也不会崩（内部转回英文），单点防御。

### 3. 三处 gender_cn 转换点：算法传英文 / 展示保留中文
**文件**：`backend/app/services/ai_service.py`
- 商业报告（305-315 行）：`generate_full_analysis(gender=gender_cn)` → 改传 `gender=gender`（英文原值）；`build_commercial_prompt(analysis_data, gender_cn, ...)`（318 行）保留中文不变。
- 首次结构化报告（351-362 行）：`generate_full_analysis(gender=gender_cn)` → 改传 `gender=gender`；`build_first_reading_structured_prompt(analysis_data, gender_cn, ...)`（392 行）保留中文不变。

**文件**：`backend/app/services/followup_structured.py`
- 追问（3056-3065 行）：`generate_full_analysis(gender=gender_cn)` → 改传 `gender=gender`（英文原值）；`_build_context_vars(gender=gender)`（3095 行）→ 改传 `gender=gender_cn`（中文展示，因模板 `日主：...（{gender}）` 给用户看要中文）。

### 4. 三个 API 入口加 Pydantic validator
**文件**：`backend/app/api/person.py`
- `PersonRequest.gender`（27 行）加 `@field_validator("gender")` 调 `normalize_gender`。写库（98 行）自然拿英文。

**文件**：`backend/app/api/bazi.py`
- `BaziRequest.gender`（14 行）和 `AnalyzeRequest.gender`（33 行）各加 `@field_validator("gender")` 调 `normalize_gender`。

### 5. 前端 normalizeGender 改转英文
**文件**：`frontend/src/api/bazi.ts`（62-65 行）
- 改为 `female/女 → "female"`，其他（`male/男/m/1`）→ `"male"`，返回类型 `'male' | 'female'`。与后端 validator 同向，前后端双保险。

### 6. 测试改英文（与生产同源，消除假阳性）
**文件**：`backend/tests/test_dayun_direction_branches.py`（59-119 行 6 个用例）
- `"gender": "男"/"女"` → `"male"/"female"`。

**文件**：`backend/tests/test_extreme_cases.py`（29-53 行 4 个用例）
- `"gender": "男"/"女"` → `"male"/"female"`。

### 7. 前端展示排查与确认
**文件**：`frontend/src/components/HistoryPanel.tsx`、`frontend/src/pages/AddPerson.tsx` 等
- 已确认 [HistoryPanel.tsx:233-240](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/components/HistoryPanel.tsx#L233-L240) 有 `male→男` 映射，[types/index.ts](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/types/index.ts#L11-L28) 类型为英文 `male|female`。
- 实现阶段 grep 前端所有直接渲染 `{person.gender}` / `{gender}` 的点，确保都有 `male→男` 映射；AddPerson 编辑回显时 state 用英文 `male/female`（后端返回已是英文，按钮高亮正确）。
- 若发现详情页/编辑页直接显示 gender 字段未转中文，补一个前端展示工具 `genderToText(g: 'male'|'female') => '男'|'女'`。

### 8. 不动的部分
- **存量数据**：DB 已是英文 male/female，无需迁移。
- **recalc_dayun.py / scan_dayun_dir.py**：一次性脚本，兼容判断不动。
- **PROMPT_VERSION**：不涉及 prompt 内容变更（gender 仅改传递格式），无需递增。
- **orchestrator.py docstring**（223 行）：顺手把 `"男" 或 "女"` 注释改为 `"male" 或 "female"`。

## 各环节影响评估（修订）

| 环节 | 影响 | 处理 |
|---|---|---|
| 已存历史 person/bazi_data_json | 无 | gender 已英文；排盘结果不含 gender 字段 |
| 单元测试 | 会全挂 | 改英文（第 6 步），改后真通过 |
| 首次报告 | 原计划会崩 | 第 2+3 步：编排层 normalize 兜底 + ai_service 改传英文 |
| 追问 | 原计划会崩 | 第 2+3 步：编排层 normalize 兜底 + followup 改传英文，展示用 gender_cn |
| 前端展示/回显 | 基本无影响 | 已有 male→男 映射，第 7 步排查补漏 |
| 商业报告 prompt | 无 | gender_cn 保留喂 build_commercial_prompt |

## 验证方法

本地 venv 是 Python 3.9 跑不了含 `str|None` 语法的库内代码（memory 教训），整链路测试在生产容器跑：

1. **算法层 fail-fast 验证**：
   ```bash
   docker exec -w /app -e PYTHONPATH=/app mingli-backend python -c "
   from app.services.bazi_service import calculate_dayun, normalize_gender
   from datetime import datetime
   print(normalize_gender('male'), normalize_gender('女'), normalize_gender('1'))  # male female male
   try:
       calculate_dayun(datetime(1984,2,10,8,0),'甲','男','丙','寅','甲')
       print('BUG: 中文没抛异常')
   except ValueError as e:
       print('OK fail-fast:', e)
   "
   ```

2. **编排层防御验证**：传中文给 generate_full_analysis 不崩（内部 normalize）：
   ```bash
   docker exec -w /app -e PYTHONPATH=/app mingli-backend python -c "
   from app.skills.orchestrator import generate_full_analysis
   d = generate_full_analysis('1990-11-10','08:00',116.4,39.9,'男','北京')
   print('OK 中文兜底, 日主=', d.get('日主'))
   "
   ```

3. **测试同源验证**：
   ```bash
   docker exec -w /app -e PYTHONPATH=/app mingli-backend python tests/test_dayun_direction_branches.py
   docker exec -w /app -e PYTHONPATH=/app mingli-backend python tests/test_extreme_cases.py
   ```
   预期：gender 改英文后四分支全部 PASS（真通过）。

4. **端到端链路验证**：起容器后手动触发首次报告 + 追问，确认不崩、报告里性别显示中文"男/女"；前端人物列表/详情性别回显中文。

5. **前端展示排查**：grep `{person.gender}`/`{gender}` 确认无裸英文显示。

## 风险与回退

- **风险**：编排层 normalize 是单点兜底，若漏改则外部传中文会崩——但第 2 步在 generate_full_analysis 内部归一化已覆盖所有调用方，是最可靠的单点。
- **fail-fast 风险**：漏网入口传非英文会让该请求 500，但 3 个 API 入口已加 validator，且编排层兜底，正常不崩；漏网会立即暴露（优于静默算反）。
- **回退**：改动集中在 normalize_gender + generate_full_analysis 一行 + 3 处传参 + validator + 测试，git revert 单提交即可。
