# 排盘数据流程优化计划

## 背景

当前系统在生成首次报告和追问报告时，依赖 `session.bazi_data_json` 中的排盘数据。如果排盘数据缺失，会导致报告生成失败。需要优化流程，确保：

1. 新加人物时，生成命格箴言并完成排盘
2. 追问/首次报告时，如果没有排盘数据，后端先生成排盘数据再生成报告
3. 测试验证数据传递是否正确

## 当前状态分析

### 已实现的部分

1. **人物创建时的排盘**（`/api/persons` POST）
   - ✅ 调用 `calculate_bazi()` 生成八字排盘
   - ✅ 调用 `calculate_astrology()` 生成占星数据
   - ✅ 将结果存入 `person.bazi_data_json` 和 `person.astro_data_json`
   - ✅ 创建 session 时复制排盘数据到 `session.bazi_data_json`

2. **命格箴言生成**
   - ✅ 在 `orchestrator.py` 的 `generate_full_analysis()` 中调用 `generate_motto()`
   - ✅ 结果存入排盘数据的 `命格箴言` 和 `命格箴言标签` 字段

3. **报告生成时的数据使用**
   - ✅ 首次报告（`/api/chat/sessions/{session_id}/first-reading`）：从 `session.bazi_data_json` 获取排盘数据
   - ✅ 追问报告（`/api/chat/sessions/{session_id}/messages` POST）：从 `session.bazi_data_json` 获取排盘数据

### 需要优化的部分

1. **排盘数据缺失的兜底逻辑**
   - ❌ 当前如果 `session.bazi_data_json` 为空，报告会生成失败
   - ❌ 需要在报告生成前检查排盘数据，如果缺失则先生成排盘

2. **命格箴言在人物创建时的生成**
   - ❌ 当前命格箴言只在 `generate_full_analysis()` 中生成
   - ❌ 需要在 `create_person` 时也生成命格箴言

## 实施方案

### 阶段1：人物创建时生成命格箴言

**文件**：`backend/app/api/person.py`

**改动**：
1. 在 `create_person` 函数中，调用 `generate_full_analysis()` 代替单独的 `calculate_bazi()`
2. 这样会同时生成完整的排盘数据（包括命格箴言）
3. 将完整结果存入 `person.bazi_data_json` 和 `session.bazi_data_json`

**代码位置**：
- 第 61-66 行：替换 `calculate_bazi()` 调用
- 第 98 行：确保 `bazi_data_json` 包含命格箴言

### 阶段2：报告生成前检查排盘数据

**文件**：`backend/app/api/chat.py`

**改动**：
1. 在 `get_first_reading` 函数（第 408 行）中：
   - 检查 `session.bazi_data_json` 是否为空
   - 如果为空，调用 `generate_full_analysis()` 生成排盘数据
   - 更新 `session.bazi_data_json` 后再继续生成报告

2. 在 `send_message` 函数（第 113 行）中：
   - 检查 `session.bazi_data_json` 是否为空
   - 如果为空，调用 `generate_full_analysis()` 生成排盘数据
   - 更新 `session.bazi_data_json` 后再继续生成报告

**代码位置**：
- 第 420-425 行：在获取 person 后检查排盘数据
- 第 241 行：在获取 bazi_data 后检查是否为空

### 阶段3：测试数据传递

**测试文件**：`backend/tests/test_bazi_data_flow.py`（新建）

**测试场景**：
1. 创建人物时验证排盘数据包含命格箴言
2. 首次报告生成时验证排盘数据正确传递
3. 追问报告生成时验证排盘数据正确传递
4. 排盘数据缺失时验证自动生成功能

**测试方法**：
- 使用 pytest 编写单元测试
- Mock AI 服务调用
- 验证数据库中的 `bazi_data_json` 字段
- 验证传递给报告生成函数的参数

## 详细实现步骤

### 步骤1：修改 person.py

```python
# 第 61-66 行：替换为 generate_full_analysis
from app.skills.orchestrator import generate_full_analysis

bazi_data = generate_full_analysis(
    birth_date=request.birth_date,
    birth_time=request.birth_time,
    longitude=request.birth_lng,
    latitude=request.birth_lat,
    gender=request.gender,
)

# 第 98 行：bazi_data 已经包含命格箴言，直接使用
session = ChatSession(
    person_id=person.id,
    bazi_data_json=bazi_data,  # 包含命格箴言
    astro_data_json=astro_chart.model_dump(),
    title=f"{person.name}的命盘",
)
```

### 步骤2：修改 chat.py

```python
# 第 420-425 行：检查并生成排盘数据
if not session.bazi_data_json:
    from app.skills.orchestrator import generate_full_analysis
    bazi_data = generate_full_analysis(
        birth_date=person.birth_date,
        birth_time=person.birth_time,
        longitude=person.birth_lng,
        latitude=person.birth_lat,
        gender=person.gender,
    )
    session.bazi_data_json = bazi_data
    await db.commit()

# 第 241 行：同样检查
if not bazi_data:
    from app.skills.orchestrator import generate_full_analysis
    bazi_data = generate_full_analysis(
        birth_date=person.birth_date,
        birth_time=person.birth_time,
        longitude=person.birth_lng,
        latitude=person.birth_lat,
        gender=person.gender,
    )
    session.bazi_data_json = bazi_data
    await db.commit()
```

### 步骤3：编写测试

```python
# test_bazi_data_flow.py
import pytest
from app.skills.orchestrator import generate_full_analysis

def test_person_creation_includes_motto():
    """测试人物创建时排盘数据包含命格箴言"""
    bazi_data = generate_full_analysis(
        birth_date="1990-01-01",
        birth_time="12:00",
        longitude=116.4,
        latitude=39.9,
        gender="male",
    )
    assert "命格箴言" in bazi_data
    assert "命格箴言标签" in bazi_data
    assert bazi_data["命格箴言"] != ""

def test_first_reading_with_bazi_data():
    """测试首次报告生成时排盘数据正确传递"""
    # Mock session 和 person
    # 验证 generate_first_reading_structured 接收到正确的 analysis_data
    
def test_followup_with_bazi_data():
    """测试追问报告生成时排盘数据正确传递"""
    # Mock session 和 person
    # 验证 generate_followup_structured 接收到正确的 analysis_data

def test_auto_generate_bazi_when_missing():
    """测试排盘数据缺失时自动生成"""
    # 创建 session 时 bazi_data_json 为空
    # 调用首次报告接口
    # 验证 session.bazi_data_json 被自动填充
```

## 验证方法

1. **单元测试**：运行 `pytest backend/tests/test_bazi_data_flow.py`
2. **集成测试**：
   - 创建新人物，检查数据库 `bazi_data_json` 是否包含命格箴言
   - 生成首次报告，检查日志确认排盘数据正确传递
   - 生成追问报告，检查日志确认排盘数据正确传递
3. **日志检查**：
   - 在 `generate_first_reading_structured` 和 `generate_followup_structured` 中添加日志
   - 打印接收到的 `analysis_data` 的关键字段（四柱、日主、命格箴言）

## 风险点

1. **性能影响**：
   - 人物创建时调用 `generate_full_analysis()` 会增加耗时（约 1-2 秒）
   - 但这是一次性操作，用户可接受

2. **向后兼容**：
   - 旧人物的 `bazi_data_json` 可能不包含命格箴言
   - 报告生成前的检查会自动补充，不影响功能

3. **错误处理**：
   - 如果 `generate_full_analysis()` 失败，需要优雅降级
   - 可以在报告中提示"排盘数据生成失败，请稍后重试"

## 时间估算

- 阶段1（人物创建优化）：30 分钟
- 阶段2（报告生成兜底）：45 分钟
- 阶段3（测试验证）：45 分钟
- 总计：2 小时

## 下一步

1. 确认计划是否完整
2. 开始实施阶段1
3. 实施阶段2
4. 编写并运行测试
5. 验证数据传递正确性
