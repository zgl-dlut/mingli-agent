# 评测系统修复与 Prompt 自动优化闭环

## 一、现状分析

### 已有基础设施
- **BadCase 模型**：`badcases` 表已有 `reviewed`、`extracted_rule`、`rule_category` 字段
- **规则提取 API**：`GET /api/admin/eval-chart-rules` 可获取已审核提炼的规则
- **评测结果模型**：`eval_results` 表存储评测结果
- **生产监控**：`production_monitor.py` 有采样决策逻辑
- **三大检查器**：structure_checker、narrative_checker、chart_usage_checker

### 缺失环节
1. **人工审核 API**：无提交审核意见的端点
2. **Prompt 注入机制**：提取的规则没有自动注入到 prompt
3. **审核 UI**：前端无审核界面
4. **自动加入评测集**：无机制将审核后的 case 加入 eval_dataset.json
5. **Prompt 版本管理**：无 prompt 变更记录

---

## 二、核心设计：人工审核 → Prompt 自动优化闭环

### 2.1 整体流程

```
─────────────────────────────────────────────────────────────────────┐
│                        完整闭环流程                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. 生产报告生成                                                      │
│     ↓                                                                │
│  2. 自动化检测（三层检测体系）                                          │
│     ↓                                                                │
│  3. 人工抽样审核（前端审核界面）                                        │
│     ↓                                                                │
│  4. 审核结果处理                                                       │
│     ├─ 通过 → 标记为高质量，可用于训练                                  │
│     ├─ 需改进 → 进入优化队列                                           │
│     └─ 不合格 → 自动加入 badcase 集                                    │
│           ↓                                                          │
│  5. 规则提炼（人工 + LLM 辅助）                                        │
│     ├─ 人工填写 extracted_rule（50-150 字精简规则）                     │
│     ├─ rule_category 分类（术语/结构/命盘数据/叙事性/时间因果）          │
│     └─ reviewed 状态更新为 2（已提炼规则）                              │
│           ↓                                                          │
│  6. Prompt 自动注入                                                   │
│     ├─ 读取所有 reviewed=2 的规则                                      │
│     ├─ 按 rule_category 分组                                          │
│     ├─ 注入到 followup_structured.py 的 prompt 模板                    │
│     └─ 生成 prompt 版本记录                                            │
│           ↓                                                          │
│  7. 自动回归验证                                                       │
│     ├─ 将不合格 case 加入 eval_dataset.json                            │
│     ├─ 运行评测集，确认新规则有效                                        │
│     └─ 检测准确率应提升或持平                                          │
│           ↓                                                          │
│  8. 部署上线                                                           │
│     └─ 新 prompt 生效，生产监控继续                                    │
│                                                                      │
─────────────────────────────────────────────────────────────────────
```

### 2.2 关键设计决策

#### 决策 1：规则注入方式

**方案 A：动态注入（推荐）**
- 规则存储在数据库，每次生成报告时从数据库读取并注入
- 优点：无需重启服务，规则可热更新
- 缺点：增加一次数据库查询

**方案 B：静态注入**
- 规则直接写入 `followup_structured.py` 的 prompt 模板
- 优点：无额外查询开销
- 缺点：需要重启服务，规则变更不灵活

**选择方案 A**：动态注入，通过 `get_eval_chart_rules()` API 读取规则，在 `build_structured_prompt()` 时注入。

#### 决策 2：规则提炼方式

**半自动模式（推荐）**：
1. 人工审核标记"不合格"
2. 系统自动调用 LLM 生成初步规则建议（基于 violation_type + raw_output）
3. 人工审核/修改规则建议
4. 确认后注入 prompt

**全自动模式（风险高）**：
- LLM 直接生成规则并注入
- 风险：可能注入错误规则，影响所有报告

**选择半自动模式**：LLM 辅助 + 人工确认。

#### 决策 3：Prompt 版本管理

每次规则注入时：
1. 备份当前 prompt 到 `prompt_versions` 表
2. 记录变更内容（新增/修改/删除的规则）
3. 记录变更原因（关联的 badcase ID）
4. 支持回滚到任意版本

---

## 三、具体实现方案

### 3.1 新增数据模型

**文件**：`backend/app/models/prompt_review.py`

```python
class PromptReview(Base):
    """人工审核记录"""
    __tablename__ = "prompt_reviews"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    eval_result_id = Column(Integer, comment="关联的评测结果ID")
    badcase_id = Column(Integer, comment="关联的 badcase ID")
    report_data = Column(Text, comment="报告 JSON")
    user_question = Column(Text, comment="用户问题")
    reviewer_id = Column(Integer, comment="审核人 ID")
    review_result = Column(String(20), comment="审核结果: pass/improve/fail")
    review_comment = Column(Text, comment="审核意见")
    problem_tags = Column(JSON, comment="问题标签: ['跑题', '术语堆砌', '编造']")
    auto_add_to_dataset = Column(Integer, default=0, comment="是否自动加入评测集")
    created_at = Column(DateTime, default=datetime.utcnow)


class PromptVersion(Base):
    """Prompt 版本记录"""
    __tablename__ = "prompt_versions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), comment="版本号")
    prompt_content = Column(Text, comment="完整 prompt 内容")
    change_summary = Column(Text, comment="变更摘要")
    changed_rules = Column(JSON, comment="变更的规则列表")
    related_badcases = Column(JSON, comment="关联的 badcase ID 列表")
    created_by = Column(String(50), comment="创建人")
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 3.2 新增 API 端点

**文件**：`backend/app/api/eval.py`

#### 端点 1：提交人工审核

```python
@router.post("/prompt-review")
async def submit_prompt_review(
    review: PromptReviewCreate,
    db: AsyncSession,
):
    """提交人工审核意见"""
    # 1. 保存审核记录
    # 2. 如果 review_result == "fail"，自动创建/更新 badcase
    # 3. 如果 auto_add_to_dataset == 1，自动加入 eval_dataset.json
    # 4. 返回审核结果
```

#### 端点 2：LLM 辅助规则提炼

```python
@router.post("/prompt-review/{review_id}/extract-rule")
async def extract_rule_with_llm(
    review_id: int,
    db: AsyncSession,
):
    """使用 LLM 辅助提炼规则"""
    # 1. 读取审核记录和关联的 badcase
    # 2. 调用 LLM 生成规则建议
    # 3. 返回规则建议（人工确认后注入）
```

#### 端点 3：确认注入 Prompt

```python
@router.post("/prompt-review/{review_id}/inject-prompt")
async def inject_rule_to_prompt(
    review_id: int,
    rule: RuleInjectRequest,
    db: AsyncSession,
):
    """确认规则并注入 prompt"""
    # 1. 更新 badcase 的 extracted_rule 和 reviewed=2
    # 2. 备份当前 prompt 到 prompt_versions 表
    # 3. 将规则注入到 followup_structured.py 的 prompt 模板
    # 4. 运行评测集回归验证
    # 5. 返回注入结果
```

#### 端点 4：获取待审核列表

```python
@router.get("/prompt-reviews")
async def list_prompt_reviews(
    db: AsyncSession,
    status: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
):
    """获取待审核列表"""
```

#### 端点 5：获取 Prompt 版本历史

```python
@router.get("/prompt-versions")
async def list_prompt_versions(
    db: AsyncSession,
    offset: int = 0,
    limit: int = 20,
):
    """获取 prompt 版本历史"""
```

#### 端点 6：回滚 Prompt 版本

```python
@router.post("/prompt-versions/{version_id}/rollback")
async def rollback_prompt_version(
    version_id: int,
    db: AsyncSession,
):
    """回滚到指定 prompt 版本"""
```

### 3.3 Prompt 动态注入机制

**文件**：`backend/app/services/followup_structured.py`

修改 `build_structured_prompt()` 函数：

```python
async def build_structured_prompt(context: Dict) -> str:
    """构建追问报告 prompt（含动态注入的规则）"""
    
    # 1. 读取基础 prompt 模板
    base_prompt = FOLLOWUP_PROMPT_TEMPLATE
    
    # 2. 从数据库读取已审核的规则
    rules = await get_injected_rules()
    
    # 3. 按 category 分组注入
    if rules:
        rules_section = "\n\n## 动态注入规则（来自人工审核）\n\n"
        for category, category_rules in groupby(rules, key=lambda r: r["category"]):
            rules_section += f"### {category}\n"
            for rule in category_rules:
                rules_section += f"- {rule['rule']}\n"
            rules_section += "\n"
        
        # 注入到 prompt 的"输出前自检"部分之前
        base_prompt = base_prompt.replace(
            "## 输出前自检",
            rules_section + "## 输出前自检"
        )
    
    # 4. 填充 context 变量
    prompt = base_prompt.format(**context)
    
    return prompt


async def get_injected_rules() -> List[Dict]:
    """从数据库读取已审核注入的规则"""
    from app.db.session import async_session
    from app.models.badcase import BadCase
    from sqlalchemy import select
    
    async with async_session() as db:
        rows = await db.execute(
            select(BadCase.extracted_rule, BadCase.rule_category)
            .where(BadCase.reviewed == 2, BadCase.extracted_rule.isnot(None))
        )
        return [
            {"category": r.rule_category, "rule": r.extracted_rule}
            for r in rows
        ]
```

### 3.4 自动加入评测集逻辑

**文件**：`backend/app/api/eval.py`

```python
async def auto_add_to_eval_dataset(
    report_data: Dict,
    user_question: str,
    violation_types: List[str],
    review_comment: str,
) -> str:
    """自动将审核不合格的 case 加入评测集"""
    
    # 1. 读取现有评测集
    dataset = load_eval_dataset()
    
    # 2. 生成新 case ID
    new_id = f"review_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    
    # 3. 构建新 case
    new_case = {
        "id": new_id,
        "description": f"人工审核-{violation_types[0] if violation_types else '未知'}",
        "user_question": user_question,
        "report": report_data,
        "expected_pass": False,
        "expected_violations": violation_types,
        "review_comment": review_comment,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # 4. 追加到评测集
    dataset.append(new_case)
    
    # 5. 写回文件
    with open(EVAL_DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    
    return new_id
```

### 3.5 前端审核界面

**文件**：`frontend/src/pages/PromptReviewPage.tsx`（新建）

```tsx
// 审核界面布局
// 左侧：报告详情（与用户看到的格式一致）
// 右侧：审核表单
//   - 审核结果：通过 / 需改进 / 不合格
//   - 审核意见文本框
//   - 问题标签多选：跑题、术语堆砌、编造、不通顺、无依据、其他
//   - LLM 辅助提炼规则按钮
//   - 提交审核按钮
//   - 加入评测集复选框
```

**文件**：`frontend/src/pages/PromptVersionPage.tsx`（新建）

```tsx
// Prompt 版本历史页面
// - 版本列表（版本号、变更摘要、关联 badcase、创建时间）
// - 版本对比（diff 展示）
// - 回滚按钮
```

### 3.6 审核数据流

```
人工提交审核
    ↓
POST /api/admin/prompt-review
    ↓
┌─ review_result == "pass"
│   → 标记为高质量报告
│   → 可用于训练数据
│
├─ review_result == "improve"
│   → 标记为待优化
│   → 进入优化队列
│   → 可选：调用 LLM 辅助提炼规则
│
└─ review_result == "fail"
    → 自动创建/更新 badcase（reviewed=1）
    → 如果 auto_add_to_dataset=1：
       → 调用 auto_add_to_eval_dataset()
       → 加入 eval_dataset.json
    → 人工提炼规则（或 LLM 辅助）
    → 更新 badcase（reviewed=2, extracted_rule=...）
    → 调用 inject_rule_to_prompt()
       → 备份当前 prompt
       → 注入规则到 prompt 模板
       → 运行评测集回归验证
       → 返回验证结果
```

---

## 四、实施步骤

### 第一阶段：基础人工审核（1-2 周）

**目标**：建立人工审核流程

**任务**：
1. 创建 `PromptReview` 数据模型
2. 实现 `POST /api/admin/prompt-review` 端点
3. 实现 `GET /api/admin/prompt-reviews` 端点
4. 创建前端审核界面 `PromptReviewPage.tsx`
5. 集成到评测中心（新增 Tab 或入口）

**验证**：
- 可以提交审核意见
- 审核记录可查询
- 不合格的 case 自动创建 badcase

### 第二阶段：规则提炼与注入（2-3 周）

**目标**：实现规则提炼和 prompt 注入

**任务**：
1. 实现 `POST /api/admin/prompt-review/{id}/extract-rule` 端点（LLM 辅助）
2. 实现 `POST /api/admin/prompt-review/{id}/inject-prompt` 端点
3. 创建 `PromptVersion` 数据模型
4. 修改 `followup_structured.py` 支持动态注入
5. 实现 `auto_add_to_eval_dataset()` 函数
6. 创建前端版本历史页面 `PromptVersionPage.tsx`

**验证**：
- LLM 可生成规则建议
- 规则可注入到 prompt
- prompt 版本可记录
- 评测集自动更新

### 第三阶段：闭环验证（1 周）

**目标**：验证完整闭环

**任务**：
1. 手动触发一次完整流程：
   - 审核一条不合格报告
   - 提炼规则
   - 注入 prompt
   - 运行评测集
   - 确认检测准确率提升
2. 验证 prompt 回滚功能
3. 编写使用文档

**验证**：
- 完整流程可运行
- 检测准确率提升或持平
- 可随时回滚 prompt

---

## 五、关键代码示例

### 5.1 LLM 辅助规则提炼

```python
async def extract_rule_with_llm(
    violation_type: str,
    raw_output: str,
    user_question: str,
) -> str:
    """使用 LLM 辅助提炼规则"""
    
    prompt = f"""
你是一个命理 AI 产品的评测专家。

用户问题：{user_question}

违规类型：{violation_type}

LLM 输出（节选）：
{raw_output[:500]}

请提炼一条精简规则（50-150 字），用于防止此类违规再次发生。
规则应该：
1. 明确指出什么是不允许的
2. 给出正确的做法示例
3. 简洁明了，可直接注入 prompt

规则：
"""
    
    # 调用 LLM
    response = await call_llm(prompt)
    
    return response.strip()
```

### 5.2 Prompt 注入示例

**注入前**：
```
## 输出前自检
1. 无编造命理数据（最高优先级）
2. 术语融合式（术语 + 大白话自然过渡）
...
```

**注入后**：
```
## 动态注入规则（来自人工审核）

### 叙事性
- 禁止在 subtopic 标题中使用"关键前置动作"等用户未提及的扩展话题，标题必须直接回应用户问题的核心关键词
- 每个 subtopic 最多 2-3 个术语标签，分散在不同 block 中，避免术语堆砌

### 命盘数据
- 禁止编造流年干支，必须调用 get_liuyue_detail 工具获取流月信息

## 输出前自检
1. 无编造命理数据（最高优先级）
2. 术语融合式（术语 + 大白话自然过渡）
...
```

---

## 六、风险与应对

### 风险 1：规则冲突

**问题**：新注入的规则可能与现有规则冲突

**应对**：
- 注入前运行评测集回归验证
- 如果检测准确率下降，拒绝注入
- 提供规则冲突检测（检查新规则是否与现有规则矛盾）

### 风险 2：规则过多导致 prompt 过长

**问题**：规则累积导致 prompt 超过 LLM 上下文限制

**应对**：
- 设置规则数量上限（如最多 20 条）
- 定期合并相似规则
- 按优先级排序，优先保留高频违规的规则

### 风险 3：错误规则影响所有报告

**问题**：注入的错误规则导致大量报告不合格

**应对**：
- 注入前必须人工确认
- 提供一键回滚功能
- 注入后自动运行评测集，异常时自动回滚

---

## 七、验证清单

- [ ] 可以提交人工审核意见
- [ ] 审核记录可查询和筛选
- [ ] 不合格的 case 自动创建 badcase
- [ ] LLM 可生成规则建议
- [ ] 规则可注入到 prompt
- [ ] prompt 版本可记录和回滚
- [ ] 评测集自动更新
- [ ] 注入后检测准确率提升或持平
- [ ] 前端审核界面可用
- [ ] 前端版本历史界面可用
