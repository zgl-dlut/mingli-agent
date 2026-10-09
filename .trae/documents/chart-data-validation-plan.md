# 命盘数据严格校验方案

## Summary

在代码层面（不依赖 prompt）保证首次报告和追问报告生成时命盘数据正确输入，并在输出端提供命盘指纹审计便于事后核对。核心是**输入端严格校验 + 异常兜底 + 缺失标注 + 指纹审计**，校验失败时记录告警日志并降级生成（不拒绝用户请求）。

## Current State Analysis

### 当前数据流

**首次报告**（`ai_service.py:241-385` `generate_first_reading_structured`）：
1. 调用 `generate_full_analysis(...)` → `analysis_data`（中文 key dict）
2. `build_first_reading_structured_prompt(analysis_data, ...)` 构建 prompt
3. 调用 LLM → JSON
4. `_normalize_report_data` + `FollowupReport.model_validate` 校验结构

**追问报告**（`followup_structured.py:631-835` `generate_followup_structured`）：
1. 调用 `generate_full_analysis(...)` → `analysis_data`（中文 key dict）
2. `_build_context_vars(analysis_data, ...)` 构建 context（用 `analysis_data.get("日主", "")` 提取）
3. `build_structured_prompt(context, ...)` 构建 prompt
4. 调用 LLM → JSON
5. `_normalize_report_data` + `FollowupReport.model_validate` 校验结构

### 命盘数据来源

`generate_full_analysis`（`orchestrator.py:207-469`）调用 `calculate_bazi` + 多个 skill，组装中文 key dict 返回，包含：四柱、日主、月令、旺衰结论、格局、用神、喜神、忌神、调候描述、地支作用、十神分布、五行分布、当前大运、大运解读、重点流年 等。

### 当前缺口（3 个）

1. **无异常兜底**：`generate_full_analysis` 调用处（ai_service.py:265, followup_structured.py:654）没有 try-catch。排盘失败（节气计算错误、经纬度异常、skill 内部错误）会抛异常冒泡到外层，降级为笼统的"报告生成异常"。

2. **无字段完整性校验**：`generate_full_analysis` 可能返回部分字段为空（某 skill 计算失败）。`_build_context_vars`（skill_prompts.py:1271-1284）用 `analysis_data.get("日主", "")` 静默容错，空字段返回空字符串。命盘数据栏出现"日主："" 用神："等空值，LLM 在残缺命盘上推演并编造缺失数据，**没有任何 check 拦截**。

3. **无输出审计**：LLM 输出后只校验 JSON 结构（FollowupReport schema），不记录命盘指纹，事后无法核对 LLM 输出是否与命盘一致。

## Proposed Changes

### 改动1：新增命盘校验模块 `chart_validator.py`

**文件**：`backend/app/services/chart_validator.py`（新建）

**what**：定义命盘必需字段清单 + 校验函数。

```python
from typing import Dict, Any, Tuple, List

# 命盘必需字段（基于 _build_context_vars 实际使用的字段推导）
# (中文key, 字段类型, 用途说明)
_CHART_REQUIRED_FIELDS = [
    ("日主", "str", "日主天干描述"),
    ("四柱", "str", "四柱干支"),
    ("用神", "str", "调候用神"),
    ("忌神", "str", "忌神五行"),
    ("旺衰结论", "str", "日主旺衰"),
    ("格局", "str", "命局格局"),
    ("当前大运", "str", "当前大运干支"),
    ("重点流年", "list", "重点流年吉凶"),
]

def validate_chart_data(analysis_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """校验命盘数据完整性。返回 (是否通过, 缺失字段列表)。"""
    if not analysis_data or not isinstance(analysis_data, dict):
        return False, ["整个命盘数据为空"]
    
    missing = []
    for key, ftype, _desc in _CHART_REQUIRED_FIELDS:
        val = analysis_data.get(key)
        if val is None:
            missing.append(key)
        elif ftype == "str" and (not isinstance(val, str) or not val.strip()):
            missing.append(key)
        elif ftype == "list" and (not isinstance(val, (list, tuple)) or len(val) == 0):
            missing.append(key)
    return (len(missing) == 0), missing

def get_chart_fingerprint(analysis_data: Dict[str, Any]) -> Dict[str, str]:
    """提取命盘指纹（关键字段摘要），用于日志审计。"""
    return {
        "日主": str(analysis_data.get("日主", ""))[:30],
        "用神": str(analysis_data.get("用神", ""))[:10],
        "忌神": str(analysis_data.get("忌神", ""))[:10],
        "当前大运": str(analysis_data.get("当前大运", ""))[:20],
        "重点流年": str(analysis_data.get("重点流年", ""))[:100],
    }
```

**why**：集中定义命盘必需字段，首次报告和追问报告共用，避免校验逻辑散落两处。字段清单基于 `_build_context_vars` 实际使用的 8 个关键字段（非全部返回字段，避免过度校验）。

**how**：被 ai_service.py 和 followup_structured.py 调用。

### 改动2：首次报告接入校验 + 异常兜底

**文件**：`backend/app/services/ai_service.py`（L264-278）

**what**：`generate_full_analysis` 调用加 try-catch，返回后调用 `validate_chart_data`，缺失时记录告警并降级生成。

**当前代码**（L264-272）：
```python
analysis_data = generate_full_analysis(
    birth_date=birth_date, birth_time=birth_time,
    longitude=longitude, latitude=latitude,
    gender=gender_cn, location=location,
)
```

**改为**：
```python
from app.services.chart_validator import validate_chart_data, get_chart_fingerprint

# 1. 现场重算命盘（加异常兜底，排盘失败不崩溃）
try:
    analysis_data = generate_full_analysis(
        birth_date=birth_date, birth_time=birth_time,
        longitude=longitude, latitude=latitude,
        gender=gender_cn, location=location,
    )
except Exception as e:
    logger.error(f"[StructuredFirstReading] generate_full_analysis 异常: {type(e).__name__}: {e}")
    analysis_data = {}  # 降级为空，后续校验会记录所有字段缺失

# 2. 命盘数据完整性校验
chart_ok, missing = validate_chart_data(analysis_data)
if not chart_ok:
    logger.warning(f"[StructuredFirstReading] 命盘数据缺失: {missing}，降级生成（缺失字段在prompt标注）")
else:
    logger.info(f"[StructuredFirstReading] 命盘校验通过, 指纹: {get_chart_fingerprint(analysis_data)}")
```

**why**：排盘异常不再崩溃；字段缺失有告警日志便于排查；降级生成避免用户看到错误。

### 改动3：追问报告接入校验 + 异常兜底

**文件**：`backend/app/services/followup_structured.py`（L651-674）

**what**：与改动2对称，`generate_full_analysis` 调用加 try-catch + 校验。

**当前代码**（L654-661）：
```python
analysis_data = generate_full_analysis(...)
```

**改为**：同样加 try-catch + `validate_chart_data` + 告警日志。

### 改动4：`_build_context_vars` 缺失字段标注

**文件**：`backend/app/services/skill_prompts.py`（L1266-1288）

**what**：命盘字段缺失时，context 里标注"（命盘数据缺失）"而非空字符串，让 LLM 知道该字段无数据、不要编造。

**当前代码**（L1271）：
```python
"rizhu": analysis_data.get("日主", ""),
```

**改为**：
```python
"rizhu": analysis_data.get("日主") or "（命盘数据缺失）",
```

对 8 个必需字段（rizhu/sizu/yongshen/jishen/wangshuai/geju_description/current_dayun/key_liunian）统一应用此模式。

**why**：空字符串在 prompt 里显示为"日主："，LLM 看到空位可能自行脑补；标注"（命盘数据缺失）"明确告知 LLM 该字段无数据，符合 prompt 已有的"严禁编造命理依据"规则。仅追问报告走 `_build_context_vars`，首次报告走 `build_first_reading_structured_prompt`（改动5同步处理）。

### 改动5：首次报告 prompt 构建同步标注

**文件**：`backend/app/services/prompt_builder.py`（`build_first_reading_structured_prompt`）

**what**：首次报告构建 prompt 时，命盘字段缺失同样标注"（命盘数据缺失）"。检查该函数内 `analysis_data.get(...)` 调用，对 8 个必需字段统一应用 `or "（命盘数据缺失）"` 模式。

**why**：与改动4对称，保证首次报告和追问报告的缺失标注行为一致。

### 改动6：LLM 输出后记录命盘指纹审计

**文件**：`ai_service.py`（L384 yield 前） + `followup_structured.py`（yield 前）

**what**：LLM 输出校验通过后，记录命盘指纹 + LLM 输出摘要到日志，便于事后核对。

```python
logger.info(
    f"[StructuredFirstReading] 命盘指纹: {get_chart_fingerprint(analysis_data)}, "
    f"LLM输出摘要: {raw_content[:200]}"
)
```

**why**：诉求2（输出依据命盘）在代码层面100%保证不可能（LLM 是黑盒，且 prompt 要求叙事化大白话转述，正则匹配命理特征会误杀合法的"你这把火"这类转述）。采用命盘指纹审计方案：记录命盘关键数据 + LLM 输出摘要，事后可人工核对，不做强制拦截避免误杀。

## Assumptions & Decisions

1. **必需字段清单**：只校验 8 个 `_build_context_vars` 实际使用的关键字段（日主/四柱/用神/忌神/旺衰结论/格局/当前大运/重点流年），不校验全部返回字段（纳音/占星/命格箴言等非报告必需），避免过度校验导致正常命例被误判缺失。

2. **校验失败处理**：采用用户选择的"记录告警+降级生成"。不拒绝用户请求、不返回错误提示、不阻断生成流程。缺失字段在 prompt 里标注"（命盘数据缺失）"，让 LLM 知道不要编造。

3. **输出校验深度**：采用轻量审计方案（命盘指纹日志），不做输出内容强制校验。理由：(a) LLM 是黑盒无法100%保证；(b) prompt 要求叙事化大白话、零术语，LLM 会把"丙火"转述成"你这把火"，命理特征正则匹配会误杀合法转述；(c) 输入端保证命盘正确注入 prompt 后，LLM 自然有依据，输出端强制校验收益低、误杀风险高。

4. **异常兜底**：`generate_full_analysis` 抛异常时降级为空 dict `{}`，让后续校验统一记录"所有字段缺失"，而非崩溃。排盘失败的根本原因应通过告警日志暴露，由开发者修复排盘算法，而非在报告生成层反复兜底。

5. **不修改 generate_full_analysis 本身**：校验在调用侧做，不侵入排盘核心逻辑。排盘返回什么由排盘算法负责，校验层只负责检测和告警。

## Verification Steps

1. **单元测试**：对 `validate_chart_data` 编写测试，覆盖：完整数据通过、单字段缺失、全空 dict、异常类型（None/非dict）。

2. **正常命例验证**：用1992人物（birth_date=1992-12-19, birth_time=19:35, lng=126.55, lat=43.8378）生成首份报告，确认日志输出"命盘校验通过, 指纹: {...}"。

3. **异常命例验证**：构造一个会触发 generate_full_analysis 异常的输入（如经纬度为0），确认日志输出"generate_full_analysis 异常"+"命盘数据缺失"+"降级生成"，且报告仍生成（prompt 里标注"命盘数据缺失"）。

4. **追问报告验证**：在1990人物下追问，确认 followup_structured.py 的校验日志正常输出。

5. **指纹审计验证**：生成报告后，grep 后端日志确认命盘指纹 + LLM 输出摘要被记录。
