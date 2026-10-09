# 排盘数据持久化优化方案

## 问题诊断

### 当前实现
- `generate_full_analysis()` 是纯算法计算，基础排盘稳定
- 但命格箴言使用 `_select_motto_by_hash()` 从候选列表选择，存在潜在变化风险
- `bazi_data_json` 只存储在 `ChatSession` 中，Person 模型没有该字段
- 每次生成报告都会重新计算排盘数据

### 稳定性风险
1. **算法更新风险**：如果 `generate_full_analysis()` 算法调整，历史人物的排盘数据会变化
2. **重复计算开销**：同一人物多次生成报告，重复计算浪费资源
3. **数据不一致**：如果计算过程中出现异常，可能导致数据不完整

## 优化方案

### 核心改动：Person 模型持久化排盘数据

#### 1. 数据库模型扩展
**文件**：`backend/app/models/person.py`

```python
from sqlalchemy import String, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column

class Person(Base):
    __tablename__ = "persons"

    user_id: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    birth_date: Mapped[str] = mapped_column(String(20), nullable=False)
    birth_time: Mapped[str] = mapped_column(String(20), nullable=False)
    birth_location: Mapped[str] = mapped_column(String(200))
    birth_lat: Mapped[float] = mapped_column(Float)
    birth_lng: Mapped[float] = mapped_column(Float)
    calendar_type: Mapped[str] = mapped_column(String(10), default='solar')
    province: Mapped[str] = mapped_column(String(50), default='')
    city: Mapped[str] = mapped_column(String(50), default='')
    bazi_data_json: Mapped[dict] = mapped_column(JSON, nullable=True)  # 新增：排盘数据
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

#### 2. 数据库迁移脚本
**文件**：`backend/alembic/versions/xxx_add_bazi_data_to_person.py`

```python
def upgrade():
    op.add_column('persons', sa.Column('bazi_data_json', sa.JSON(), nullable=True))

def downgrade():
    op.drop_column('persons', 'bazi_data_json')
```

#### 3. 人物创建时生成并存储排盘数据
**文件**：`backend/app/api/person.py`

```python
@router.post("")
async def create_person(
    request: PersonRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    # 生成完整排盘数据（包括命格箴言）
    bazi_data = generate_full_analysis(
        birth_date=request.birth_date,
        birth_time=request.birth_time,
        longitude=request.birth_lng,
        latitude=request.birth_lat,
        gender=request.gender,
        location=request.birth_location,
    )
    
    # 创建 Person 并存储排盘数据
    person = Person(
        user_id=current_user.id,
        name=request.name,
        gender=request.gender,
        birth_date=request.birth_date,
        birth_time=request.birth_time,
        birth_location=request.birth_location,
        birth_lat=request.birth_lat,
        birth_lng=request.birth_lng,
        calendar_type=request.calendar_type,
        province=request.province,
        city=request.city,
        bazi_data_json=bazi_data,  # 持久化到 Person
    )
    db.add(person)
    await db.commit()
    await db.refresh(person)
    
    # 创建 Session，从 Person 读取排盘数据
    session = ChatSession(
        person_id=person.id,
        bazi_data_json=person.bazi_data_json,  # 从 Person 复制
        astro_data_json=astro_chart.model_dump(),
        title=f"{person.name}的命盘",
    )
    db.add(session)
    await db.commit()
    
    return {
        "person": {...},
        "session_id": session.id,
        "bazi_data": person.bazi_data_json,
        "astro_data": astro_chart.model_dump(),
    }
```

#### 4. 报告生成时优先从 Person 读取
**文件**：`backend/app/api/chat.py`

```python
# 首次报告生成
@router.get("/sessions/{session_id}/first-reading")
async def get_first_reading(...):
    # 优先从 Person 读取排盘数据
    if person.bazi_data_json:
        bazi_data = person.bazi_data_json
    elif session.bazi_data_json:
        bazi_data = session.bazi_data_json
    else:
        # 兜底：生成并存储到 Person
        bazi_data = generate_full_analysis(...)
        person.bazi_data_json = bazi_data
        session.bazi_data_json = bazi_data
        await db.commit()
    
    # 使用 bazi_data 生成报告...

# 追问报告生成
@router.post("/sessions/{session_id}/messages")
async def send_message(...):
    # 同样的逻辑：优先 Person -> Session -> 生成
    if person.bazi_data_json:
        bazi_data = person.bazi_data_json
    elif session.bazi_data_json:
        bazi_data = session.bazi_data_json
    else:
        bazi_data = generate_full_analysis(...)
        person.bazi_data_json = bazi_data
        session.bazi_data_json = bazi_data
        await db.commit()
```

#### 5. ensure_session 从 Person 读取
**文件**：`backend/app/api/person.py`

```python
@router.post("/{person_id}/ensure-session")
async def ensure_session(...):
    # 如果 Person 有排盘数据，直接使用
    if person.bazi_data_json:
        bazi_data = person.bazi_data_json
    else:
        # 生成并存储到 Person
        bazi_data = generate_full_analysis(...)
        person.bazi_data_json = bazi_data
        await db.commit()
    
    session = ChatSession(
        person_id=person.id,
        bazi_data_json=bazi_data,
        ...
    )
```

## 数据迁移策略

### 阶段1：数据库迁移
1. 执行迁移脚本，为 `persons` 表添加 `bazi_data_json` 字段
2. 验证迁移成功

### 阶段2：数据回填（可选）
对于已存在的 Person，可以批量回填排盘数据：
```python
# 脚本：backfill_person_bazi_data.py
persons = await db.execute(select(Person).where(Person.bazi_data_json == None))
for person in persons.scalars():
    bazi_data = generate_full_analysis(...)
    person.bazi_data_json = bazi_data
await db.commit()
```

### 阶段3：代码部署
1. 部署新代码
2. 新创建的人物自动存储排盘数据到 Person
3. 旧人物首次生成报告时自动回填

## 验证步骤

1. **单元测试**：验证 Person 模型可以正确存储和读取 `bazi_data_json`
2. **集成测试**：
   - 创建新人物，验证 Person 和 Session 都有排盘数据
   - 生成首次报告，验证使用 Person 中的排盘数据
   - 生成追问报告，验证使用 Person 中的排盘数据
   - 删除 Session 后重新创建，验证从 Person 恢复排盘数据
3. **数据一致性测试**：
   - 同一人物多次生成报告，验证排盘数据完全一致
   - 对比 Person.bazi_data_json 和 Session.bazi_data_json，确保相同

## 优势总结

1. **数据稳定性**：排盘数据与人物绑定，算法更新不影响历史数据
2. **性能优化**：避免重复计算，直接读取数据库
3. **数据一致性**：Person 是唯一数据源，Session 只是副本
4. **可追溯性**：可以追溯每个人物的排盘数据生成时间
5. **容错能力**：即使 Session 被删除，排盘数据仍保留在 Person 中

## 实施计划

1. 创建数据库迁移脚本（5分钟）
2. 修改 Person 模型（5分钟）
3. 修改 person.py 的 create_person 和 ensure_session（15分钟）
4. 修改 chat.py 的首次报告和追问报告逻辑（20分钟）
5. 编写测试用例（15分钟）
6. 执行迁移并验证（10分钟）

总计：约 70 分钟
