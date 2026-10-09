# 追问时使用专项 Skill Prompt 生成结构化报告

## 任务概述

当用户在对话中提出具体问题时，不再使用通用的 `build_commercial_prompt` + 末尾追加【用户当前问题】的方式，而是根据问题类型匹配对应的专项 skill prompt，生成结构化、有针对性的深度报告。

用户提供了一个职场专项 prompt 范例作为参考模板。

## 当前状态分析

### 现有追问流程

```
前端 handleSend() → chatApi.analyzeStream({is_first_reading: false, question, history, bazi_data})
  → 后端 chat_lite.py → build_commercial_prompt(..., user_question=question)
    → system prompt 末尾追加通用的【用户当前问题】段
    → generate_ai_response(system_prompt, messages)
```

**问题**：
- 追问时使用的是完整的命理报告模板（约 2200 字的 system prompt），包含开场白、八字基本盘、性格、事业、婚姻、大运等全部章节
- `user_question` 仅在末尾追加一个通用指引（"先概括→分层次→给建议"），没有针对问题类型的专项结构
- 所有类型的问题（事业、感情、财运、健康）共用同一个 prompt，输出格式不统一、不够深入

### 用户期望

- 追问时根据问题类型使用专门的 skill prompt
- 每个 skill prompt 有固定的输出结构和格式
- 报告绑定具体流年流月时间，给出精准时间窗口
- 给出可落地的行动方案

## 实施方案

### 修改1：创建专项 skill prompt 模块

**文件**：`backend/app/services/skill_prompts.py`（新建）

创建一个专项 prompt 模块，包含多个问题类型的 skill prompt 模板：

```python
SKILL_PROMPTS = {
    "career": {
        "keywords": ["事业", "工作", "职场", "跳槽", "涨薪", "升职", "公司", "部门", "职业", "创业", "副业", "老板", "领导", "同事", "转行", "找工"],
        "prompt": "..."  # 职场专项 prompt（基于用户提供的范例）
    },
    "wealth": {
        "keywords": ["财运", "赚钱", "投资", "理财", "收入", "财富", "偏财", "正财", "股票", "基金", "房产"],
        "prompt": "..."  # 财运专项 prompt
    },
    "marriage": {
        "keywords": ["感情", "婚姻", "恋爱", "对象", "配偶", "结婚", "离婚", "桃花", "姻缘", "另一半", "相亲"],
        "prompt": "..."  # 婚姻感情专项 prompt
    },
    "health": {
        "keywords": ["健康", "身体", "疾病", "养生", "医疗", "手术", "体检", "睡眠", "压力", "情绪"],
        "prompt": "..."  # 健康专项 prompt
    },
}
```

每个 skill prompt 模板的结构：
- **角色设定**：专业八字命理咨询师 + 对应领域专家
- **已知条件注入**：从 `analysis_data` 动态填充（四柱、日主、格局、大运、流年等）
- **输出强制结构**：固定章节格式（开篇承接→核心总纲→分模块解答→综合决策指南）
- **硬性要求**：绑定流年流月、区分路径、给出实操建议

### 修改2：新增 `build_skill_prompt()` 函数

**文件**：`backend/app/services/skill_prompts.py`

```python
def build_skill_prompt(
    analysis_data: Dict,
    gender: str,
    birth_date: str,
    birth_time: str,
    location: str,
    user_question: str,
    history: list,
) -> str:
```

逻辑：
1. 从 `user_question` 中匹配关键词，确定问题类型（career/wealth/marriage/health）
2. 如果匹配到专项类型，使用对应的 skill prompt 模板
3. 将 `analysis_data` 中的命盘数据注入模板的占位符
4. 如果未匹配到任何专项类型，降级使用通用追问 prompt（保持向后兼容）

### 修改3：修改 `chat_lite.py` 调用逻辑

**文件**：`backend/app/api/chat_lite.py`

在追问分支（`is_first_reading=False`）中：

```python
# 原来：
system_prompt = build_commercial_prompt(..., user_question=request.question)

# 改为：
from app.services.skill_prompts import build_skill_prompt
system_prompt = build_skill_prompt(
    analysis_data=request.bazi_data,
    gender=request.gender,
    birth_date=request.birth_date,
    birth_time=request.birth_time,
    location=request.location,
    user_question=request.question,
    history=request.history,
)
```

### 修改4：编写各专项 prompt 模板内容

基于用户提供的职场专项 prompt 范例，编写 4 个专项 prompt：

1. **职场专项**（用户提供范例，直接适配）
2. **财运专项**（参照范例结构，调整领域内容）
3. **婚姻感情专项**（参照范例结构，调整领域内容）
4. **健康专项**（参照范例结构，调整领域内容）

每个 prompt 的通用骨架：
```
# 角色设定
你是专业八字命理咨询师，擅长{领域}专项推演...

# 已知条件（动态注入）
1. 咨询时间：{当前年月}，{流年干支}
2. 命局格局：{格局}，当前行{大运}
3. 客户问题：{user_question}

# 输出强制结构
1. 开篇承接
2. 全局核心总纲
3. 分模块逐一解答
4. 文末综合决策指南

# 硬性要求
- 绑定流年流月精确时间
- 给出可落地动作
- 分段清晰，逻辑严谨
```

## 涉及文件

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/app/services/skill_prompts.py` | 新建 | 专项 skill prompt 模块 |
| `backend/app/api/chat_lite.py` | 修改 | 追问分支调用 `build_skill_prompt` |

## 验证步骤

1. 输入职场相关问题（如"适合跳槽还是留任"），确认使用职场专项 prompt，输出包含固定结构和流月时间
2. 输入感情相关问题，确认使用婚姻感情专项 prompt
3. 输入不匹配任何专项的通用问题，确认降级为通用追问 prompt
4. 验证首次解读不受影响（`is_first_reading=True` 时仍使用 `build_commercial_prompt`）
