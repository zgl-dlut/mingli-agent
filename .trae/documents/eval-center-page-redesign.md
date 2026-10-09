# 评测中心页面重构规划 v2

## 一、现状分析

### 1.1 当前页面结构
- **EvalDashboard.tsx**：评测结果列表 + 评测集内容（2个Tab）
- **EvalDetailPage.tsx**：单次评测详情
- **EvalComparePage.tsx**：两次评测对比（独立页面）

### 1.2 当前问题
1. **迭代对比割裂**：独立的对比页面无法在查看具体指标时看到版本变化
2. **缺少全版本趋势**：只支持两两对比，无法看到指标随版本的变化趋势
3. **指标未持久化**：task_completion_rate、accuracy_rate等每次从detail JSON实时计算
4. **评测类型缺失**：没有区分不同评测类型
5. **指标展示不完整**：缺少任务完成率分层、正确率各维度、软性评分、违规分布

### 1.3 评测类型梳理

| 评测类型 | 数据来源 | 评测目标 | 核心指标 |
|---------|---------|---------|---------|
| 报告质量评测 | eval_dataset.json | 报告结构、术语、叙事性 | 检测准确率、违规分布 |
| 排盘正确性评测 | eval_chart_dataset.json | 排盘算法准确性 | 四柱/十神/大运/流年准确率 |
| Badcase动态评测 | badcases表 | 违规修复验证 | 修复率 |
| 生产环境监控 | eval_report_logs表 | 线上报告质量 | L1-L4任务完成率 |

---

## 二、核心设计理念：版本维度贯穿所有页面

### 2.1 标准AI评测逻辑
标准AI评测工具（如MLflow、W&B）的做法：
- **固定数据集** + **版本化快照** + **全版本趋势**
- 在**每个指标视图**内嵌入版本历史和趋势线
- 支持选择任意版本查看delta，而不是跳转到独立对比页面

### 2.2 设计原则
1. **版本选择器**：每个指标卡片旁边都有版本下拉框
2. **Mini趋势图**：每个指标卡片下方显示该指标的历史趋势
3. **深度对比**：作为详情页的一个tab，而不是独立页面
4. **指标持久化**：所有汇总指标写入数据库，避免实时计算

---

## 三、页面结构设计

### 3.1 页面架构

```
评测中心
├── 概览页（Dashboard）
│   ├── 版本选择器（全局）
│   ├── 核心指标卡片（每个带mini趋势图）
│   ├── 评测类型分布饼图
│   └── 最近评测列表
│
├── 评测结果（按类型筛选）
│   ├── 版本选择器
│   ├── 指标卡片（每个带mini趋势图）
│   └── 结果列表
│
├── 评测详情
│   ├── 概览区（带版本选择器）
│   ├── 任务完成率分层（带趋势图）
│   ├── 正确率各维度（带趋势图）
│   ├── 软性评分（带趋势图）
│   ├── 违规分布（带趋势图）
│   ├── 用例详情列表
│   └── 深度对比Tab（选择另一版本进行对比）
│
└── 评测集管理
    ├── 报告质量评测集
    ├── 排盘正确性评测集
    └── Badcase评测集
```

### 3.2 版本选择器组件设计

**VersionSelector组件**：
- 下拉框：选择任意版本
- 对比模式：选择两个版本进行对比
- 趋势视图：显示全版本趋势图

**MetricCard组件**：
- 指标值
- Mini趋势图（最近10个版本）
- 版本选择器（选择查看哪个版本）
- Delta显示（与上一版本或选择版本的差异）

---

## 四、后端API扩展

### 4.1 数据模型扩展
**文件**：`backend/app/models/eval_result.py`

需要增加的字段：
```python
eval_type = Column(String(50), comment="评测类型: report_quality/chart_accuracy/badcase_eval/production_monitor")
task_completion_rate = Column(JSON, comment="任务完成率: {l1, l2, l3, l4, overall}")
accuracy_rate = Column(JSON, comment="正确率: {chart, structure, narrative, logic, consistency, safety, overall}")
soft_score = Column(JSON, comment="软性评分: {叙事性, 通顺性, 故事性, 加粗合理性, 术语通俗化, avg}")
violation_distribution = Column(JSON, comment="违规分布: {违规类型: 计数}")
```

### 4.2 API扩展
**文件**：`backend/app/api/eval.py`

#### 4.2.1 评测结果API增强
```python
GET /api/admin/eval-results
- 增加参数：eval_type（筛选评测类型）
- 返回字段增加：eval_type、task_completion_rate、accuracy_rate、soft_score、violation_distribution

GET /api/admin/eval-results/{id}
- 返回完整评测数据（包含所有持久化指标）

GET /api/admin/eval-trend
- 新增接口：获取指定评测类型的指标趋势
- 参数：eval_type、metric_name、limit
- 返回：[{version_id, version_name, value, created_at}]

GET /api/admin/eval-compare
- 增强：支持多版本对比（不只是两个）
- 参数：ids（多个评测ID）
- 返回：各版本的所有指标
```

### 4.3 评测脚本修改
**文件**：`backend/app/services/eval/run_eval.py`

在生成评测结果时，计算并写入：
- task_completion_rate（L1-L4各层级）
- accuracy_rate（7个维度）
- soft_score（5个维度）
- violation_distribution（各违规类型计数）

---

## 五、前端页面重构

### 5.1 概览页（新建）
**文件**：`frontend/src/pages/EvalOverview.tsx`

展示内容：
1. **全局版本选择器**
   - 选择查看哪个版本的评测数据
   - 对比模式：选择两个版本查看delta

2. **核心指标卡片**（4个，每个带mini趋势图）
   - 检测准确率（最新评测）
   - 任务完成率（L1×L2×L3×L4）
   - 正确率（7维度加权）
   - Badcase修复率

3. **评测类型分布**（饼图）
   - 报告质量评测：X次
   - 排盘正确性评测：Y次
   - Badcase动态评测：Z次

4. **最近评测列表**（表格）
   - 显示最近10次评测的摘要信息
   - 每行可点击查看详情

### 5.2 评测结果页（重构）
**文件**：`frontend/src/pages/EvalDashboard.tsx`

改造为：
1. **顶部筛选区**
   - 评测类型下拉框（全部/报告质量/排盘正确性/Badcase/生产监控）
   - 版本选择器（选择查看哪个版本）

2. **指标卡片区域**（根据评测类型动态展示，每个带mini趋势图）
   - 报告质量评测：检测准确率、L2格式完成率、违规分布
   - 排盘正确性评测：四柱准确率、十神准确率、大运准确率
   - Badcase评测：修复率、未修复数量
   - 生产监控：L1-L4各层级完成率

3. **结果列表**（表格）
   - 列：ID、评测类型、评测集ID、总数、通过、失败、核心指标、创建时间、操作
   - 核心指标列根据评测类型显示不同内容

### 5.3 评测详情页（重构）
**文件**：`frontend/src/pages/EvalDetailPage.tsx`

改造为：
1. **概览区**
   - 评测基本信息（类型、时间、评测集ID）
   - 版本选择器（选择查看哪个版本）
   - 核心指标卡片（每个带mini趋势图）

2. **任务完成率分层**（仅报告质量评测显示）
   - L1技术完成率（带趋势图）
   - L2格式完成率（带趋势图）
   - L3质量完成率（带趋势图）
   - L4满意度完成率（带趋势图）

3. **正确率各维度**（仅报告质量评测显示）
   - 排盘正确性（带趋势图）
   - 结构合规性（带趋势图）
   - 术语合规性（带趋势图）
   - 数据真实性（带趋势图）
   - 命理逻辑一致性（带趋势图）
   - 内容一致性（带趋势图）
   - 内容安全性（带趋势图）

4. **软性评分**（仅报告质量评测显示）
   - 叙事性、通顺性、故事性、加粗合理性、术语通俗化（每个带趋势图）

5. **违规分布**（柱状图 + 趋势图）
   - 各违规类型的计数
   - 与上一版本的对比

6. **用例详情列表**
   - 每个用例的预期结果、实际结果、检测状态、违规详情

7. **深度对比Tab**（新增）
   - 选择另一版本进行详细对比
   - 雷达图：任务完成率、正确率维度对比
   - 柱状图：软性评分对比
   - 表格：违规分布变化

### 5.4 评测集管理页（重构）
**文件**：`frontend/src/pages/EvalDataset.tsx`（新建）

改造为：
1. **Tab切换**
   - 报告质量评测集
   - 排盘正确性评测集
   - Badcase评测集

2. **报告质量评测集Tab**
   - 展示eval_dataset.json内容
   - 每个用例显示：ID、描述、用户问题、预期结果、检测内容、最新评测状态

3. **排盘正确性评测集Tab**
   - 展示eval_chart_dataset.json内容
   - 每个用例显示：ID、描述、出生信息、预期排盘结果、最新评测状态

4. **Badcase评测集Tab**
   - 展示badcases表中已审核的案例
   - 每个用例显示：ID、问题、违规类型、审核状态、最新修复状态

### 5.5 路由调整

**文件**：`frontend/src/App.tsx`

新增/修改路由：
```typescript
{ path: 'admin/eval', element: <EvalOverview /> },  // 概览页
{ path: 'admin/eval/results', element: <EvalDashboard /> },  // 评测结果
{ path: 'admin/eval/dataset', element: <EvalDataset /> },  // 评测集管理
{ path: 'admin/eval/detail/:id', element: <EvalDetailPage /> },
// 删除独立的对比页面路由，深度对比作为详情页的tab
```

---

## 六、核心组件设计

### 6.1 VersionSelector组件
**文件**：`frontend/src/components/VersionSelector.tsx`

功能：
- 下拉框：选择任意版本
- 对比模式：选择两个版本进行对比
- 趋势视图：显示全版本趋势图

Props：
```typescript
interface VersionSelectorProps {
  versions: Array<{id: number, name: string, created_at: string}>
  selectedVersion: number
  compareVersion?: number
  onSelect: (versionId: number) => void
  onCompare?: (versionId1: number, versionId2: number) => void
}
```

### 6.2 MetricCard组件
**文件**：`frontend/src/components/MetricCard.tsx`

功能：
- 显示指标值
- Mini趋势图（最近10个版本）
- Delta显示（与上一版本或选择版本的差异）

Props：
```typescript
interface MetricCardProps {
  title: string
  value: number
  unit?: string
  trend?: Array<{version: string, value: number}>
  delta?: {value: number, type: 'increase' | 'decrease' | 'unchanged'}
  color?: string
}
```

### 6.3 TrendChart组件
**文件**：`frontend/src/components/TrendChart.tsx`

功能：
- 折线图：显示指标随版本的变化趋势
- 支持缩放、悬停查看详情

Props：
```typescript
interface TrendChartProps {
  data: Array<{version: string, value: number}>
  title?: string
  height?: number
}
```

---

## 七、技术细节

### 7.1 图表库选择
- 使用`recharts`实现可视化（React生态友好）
- 折线图：趋势图
- 饼图：评测类型分布
- 雷达图：任务完成率、正确率维度对比
- 柱状图：违规分布、软性评分对比

### 7.2 数据结构设计

#### 评测结果API响应
```typescript
interface EvalResultItem {
  id: number
  eval_type: 'report_quality' | 'chart_accuracy' | 'badcase_eval' | 'production_monitor'
  dataset_id: string
  total: number
  passed: number
  failed: number
  pass_rate: number
  format_pass_rate: number | null
  match_count: number
  match_rate: number
  
  // 持久化指标
  task_completion_rate?: {
    l1_technical: number
    l2_format: number
    l3_quality: number
    l4_satisfaction: number
    overall: number
  }
  
  accuracy_rate?: {
    chart: number
    structure: number
    narrative: number
    logic: number
    consistency: number
    safety: number
    overall: number
  }
  
  soft_score?: {
    narrative: number
    fluency: number
    storytelling: number
    bold_rationality: number
    terminology_popularization: number
    avg: number
  }
  
  violation_distribution?: Record<string, number>
  
  detail?: EvalCaseDetail[]
  created_at: string
}
```

### 7.3 评测类型映射
```typescript
const EVAL_TYPE_MAP = {
  report_quality: {
    label: '报告质量评测',
    color: 'blue',
    metrics: ['检测准确率', 'L2格式完成率', '违规分布'],
  },
  chart_accuracy: {
    label: '排盘正确性评测',
    color: 'green',
    metrics: ['四柱准确率', '十神准确率', '大运准确率'],
  },
  badcase_eval: {
    label: 'Badcase动态评测',
    color: 'orange',
    metrics: ['修复率', '未修复数量'],
  },
  production_monitor: {
    label: '生产环境监控',
    color: 'purple',
    metrics: ['L1技术完成率', 'L2格式完成率', 'L3质量完成率', 'L4满意度'],
  },
}
```

---

## 八、实施步骤

### 阶段1：后端数据模型扩展（0.5天）
1. 扩展EvalResult模型，增加eval_type、task_completion_rate等字段
2. 执行数据库迁移

**数据库迁移脚本**：`backend/alembic/versions/005_add_eval_metrics.py`
```python
def upgrade():
    op.add_column('eval_results', sa.Column('eval_type', sa.String(50), nullable=True))
    op.add_column('eval_results', sa.Column('task_completion_rate', sa.JSON, nullable=True))
    op.add_column('eval_results', sa.Column('accuracy_rate', sa.JSON, nullable=True))
    op.add_column('eval_results', sa.Column('soft_score', sa.JSON, nullable=True))
    op.add_column('eval_results', sa.Column('violation_distribution', sa.JSON, nullable=True))
```

### 阶段2：后端API扩展（1天）
1. 修改eval.py，增加评测类型筛选、趋势API
2. 修改评测脚本，在生成评测结果时写入新字段

**指标计算逻辑**（在run_eval.py中实现）：
```python
# 任务完成率计算
task_completion_rate = {
    "l1_technical": success_count / total_count,  # L1: 技术完成率
    "l2_format": format_pass_count / success_count,  # L2: 格式完成率
    "l3_quality": hard_check_pass_count / format_pass_count,  # L3: 质量完成率
    "l4_satisfaction": soft_score_pass_count / hard_check_pass_count,  # L4: 满意度
    "overall": l1 * l2 * l3 * l4  # 综合任务完成率
}

# 正确率计算（7维度加权）
accuracy_rate = {
    "chart": chart_correct_count / total_count,  # 排盘正确性 30%
    "structure": structure_pass_count / total_count,  # 结构合规性 15%
    "narrative": narrative_pass_count / total_count,  # 术语合规性 10%
    "logic": logic_pass_count / total_count,  # 数据真实性 15%
    "consistency": consistency_pass_count / total_count,  # 命理逻辑一致性 25%
    "safety": safety_pass_count / total_count,  # 内容安全性 5%
    "overall": chart*0.3 + structure*0.15 + narrative*0.1 + logic*0.15 + consistency*0.25 + safety*0.05
}

# 软性评分计算（5维度）
soft_score = {
    "narrative": avg(narrative_scores),  # 叙事性
    "fluency": avg(fluency_scores),  # 通顺性
    "storytelling": avg(storytelling_scores),  # 故事性
    "bold_rationality": avg(bold_scores),  # 加粗合理性
    "terminology_popularization": avg(term_scores),  # 术语通俗化
    "avg": avg(all_scores)
}

# 违规分布统计
violation_distribution = {}
for case in cases:
    for violation in case.violations:
        vtype = violation.type
        violation_distribution[vtype] = violation_distribution.get(vtype, 0) + 1
```

### 阶段3：前端核心组件（1天）
1. 新建VersionSelector组件
2. 新建MetricCard组件
3. 新建TrendChart组件

### 阶段4：前端概览页（1天）
1. 新建EvalOverview.tsx
2. 实现核心指标卡片、评测类型分布、趋势图
3. 添加路由和导航

### 阶段5：评测结果页重构（1天）
1. 重构EvalDashboard.tsx
2. 增加评测类型筛选、版本选择器
3. 动态展示不同评测类型的指标

### 阶段6：评测详情页重构（1.5天）
1. 重构EvalDetailPage.tsx
2. 实现任务完成率分层、正确率各维度、软性评分展示
3. 实现违规分布可视化
4. 实现深度对比Tab

### 阶段7：评测集管理页（1天）
1. 新建EvalDataset.tsx
2. 实现三种评测集的Tab展示

### 阶段8：集成测试（0.5天）
1. 端到端测试所有页面
2. 验证数据展示正确性
3. 优化性能和用户体验

---

## 九、验证步骤

### 9.1 功能验证
1. 概览页能正确展示所有核心指标和趋势
2. 评测结果页能按类型和版本筛选
3. 评测详情页能展示完整的分层指标和趋势
4. 评测集管理页能展示三种评测集
5. 深度对比Tab能正确对比两个版本

### 9.2 数据验证
1. 评测类型正确标记
2. 任务完成率计算正确
3. 正确率各维度计算正确
4. 违规分布统计正确
5. 趋势数据正确

### 9.3 性能验证
1. 列表页加载时间 < 2s
2. 详情页加载时间 < 3s
3. 图表渲染流畅

---

## 十、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 数据库迁移失败 | 无法写入新字段 | 备份数据，分步迁移 |
| 图表库兼容性问题 | 页面渲染异常 | 充分测试，准备降级方案 |
| 评测脚本修改影响生产 | 评测结果异常 | 灰度发布，回滚机制 |
| 数据量大导致性能问题 | 页面加载慢 | 分页、懒加载、缓存 |

---

## 十一、前端API接口扩展

### 11.1 admin.ts接口更新
**文件**：`frontend/src/api/admin.ts`

需要扩展的接口：

```typescript
// 扩展EvalResultItem接口
export interface EvalResultItem {
  id: number
  dataset_id: string
  eval_type: 'report_quality' | 'chart_accuracy' | 'badcase_eval' | 'production_monitor'
  total: number
  passed: number
  failed: number
  pass_rate: number
  format_pass_rate: number | null
  match_count: number
  match_rate: number
  task_completion_rate?: {
    l1_technical: number
    l2_format: number
    l3_quality: number
    l4_satisfaction: number
    overall: number
  }
  accuracy_rate?: {
    chart: number
    structure: number
    narrative: number
    logic: number
    consistency: number
    safety: number
    overall: number
  }
  soft_score?: {
    narrative: number
    fluency: number
    storytelling: number
    bold_rationality: number
    terminology_popularization: number
    avg: number
  }
  violation_distribution?: Record<string, number>
  detail?: EvalCaseDetail[]
  created_at: string
}

// 新增评测类型接口
export interface EvalType {
  type: string
  label: string
  description: string
  metrics: string[]
  count: number
  latest_time: string | null
}

// 新增趋势数据接口
export interface TrendPoint {
  version_id: number
  version_name: string
  value: number
  created_at: string
}

// 扩展adminApi对象
export const adminApi = {
  // 现有接口...
  
  /** 获取评测类型列表 */
  evalTypes: () =>
    apiClient.get<{ types: EvalType[] }>('/admin/eval-types'),
  
  /** 获取指标趋势数据 */
  evalTrend: (params: {
    eval_type?: string
    metric_name?: string
    limit?: number
  }) =>
    apiClient.get<{ metric_name: string; eval_type?: string; trend: TrendPoint[] }>('/admin/eval-trend', { params }),
  
  /** 扩展evalResults接口，增加eval_type筛选 */
  evalResults: (params?: {
    offset?: number
    limit?: number
    dataset_id?: string
    eval_type?: string
  }) =>
    apiClient.get<{ total: number; items: EvalResultItem[] }>('/admin/eval-results', { params }),
}
```

---

## 十二、页面导航与数据流

### 12.1 页面导航逻辑

#### 概览页导航
```typescript
// 点击评测类型卡片 → 跳转到评测结果页（带筛选）
navigate(`/admin/eval/results?eval_type=${type}`)

// 点击最近评测列表的某一行 → 跳转到详情页
navigate(`/admin/eval/detail/${id}`)

// 点击"查看全部" → 跳转到评测结果页
navigate('/admin/eval/results')
```

#### 评测结果页导航
```typescript
// 点击某一行 → 跳转到详情页
navigate(`/admin/eval/detail/${id}`)

// 选择对比版本 → 在详情页打开对比Tab
navigate(`/admin/eval/detail/${currentId}?compare=${compareId}`)
```

#### 详情页导航
```typescript
// 点击"返回列表" → 返回上一页
navigate(-1)

// 切换版本 → 重新加载当前页数据
setSelectedVersion(newVersionId)
loadDetail(newVersionId)

// 打开对比Tab → 显示对比视图
setActiveTab('compare')
```

### 12.2 数据流转

#### 概览页数据流
```
1. 页面加载
   ↓
2. 调用 evalTypes() 获取评测类型列表
   ↓
3. 调用 evalResults({ limit: 10 }) 获取最近评测
   ↓
4. 对每个评测类型，调用 evalTrend({ eval_type, metric_name: 'match_rate' })
   ↓
5. 渲染核心指标卡片（带趋势图）和评测类型分布饼图
```

#### 评测结果页数据流
```
1. 页面加载（可能带eval_type参数）
   ↓
2. 调用 evalTypes() 获取评测类型列表（用于下拉框）
   ↓
3. 调用 evalResults({ eval_type, offset, limit }) 获取评测列表
   ↓
4. 对每个评测，调用 evalTrend({ eval_type: item.eval_type }) 获取趋势
   ↓
5. 渲染指标卡片（带趋势图）和结果列表
```

#### 详情页数据流
```
1. 页面加载（可能带compare参数）
   ↓
2. 调用 evalResultDetail(id) 获取当前版本详情
   ↓
3. 调用 evalResults({ limit: 100 }) 获取所有版本（用于版本选择器）
   ↓
4. 对每个指标，调用 evalTrend({ eval_type, metric_name }) 获取趋势
   ↓
5. 如果有compare参数，调用 evalResultDetail(compareId) 获取对比版本
   ↓
6. 渲染概览区、分层指标、违规分布、用例列表
   ↓
7. 如果打开对比Tab，渲染雷达图、柱状图、违规变化表格
```

---

## 十三、UI交互细节

### 13.1 版本选择器交互

#### 基础交互
```
1. 点击版本下拉框 → 展开版本列表
2. 选择某个版本 → 触发onSelect回调
3. 页面重新加载该版本的数据
4. 所有指标卡片和趋势图更新
```

#### 对比模式交互
```
1. 点击"对比模式"开关 → 显示第二个版本选择器
2. 选择对比版本 → 触发onCompare回调
3. 页面加载对比版本数据
4. 在每个指标卡片上显示delta（与对比版本的差异）
5. 在详情页自动打开"深度对比"Tab
```

### 13.2 指标卡片交互

#### 悬停效果
```
1. 鼠标悬停 → 卡片阴影加深，轻微上移
2. 显示tooltip → 展示指标详细说明
3. 趋势图高亮 → 折线变粗，显示数据点
```

#### 点击交互
```
1. 点击指标卡片 → 跳转到对应的详情页面
   - 检测准确率 → 详情页的"用例详情"Tab
   - 任务完成率 → 详情页的"任务完成率"区域
   - 正确率 → 详情页的"正确率维度"区域
   - 违规分布 → 详情页的"违规分布"区域
```

### 13.3 趋势图交互

#### Mini趋势图（指标卡片内）
```
1. 默认显示最近10个版本的趋势
2. 鼠标悬停 → 显示当前数据点的值和版本
3. 点击 → 展开为完整趋势图（在详情页）
```

#### 完整趋势图（详情页内）
```
1. 显示所有版本的趋势
2. 支持缩放和拖拽
3. 鼠标悬停 → 显示详细tooltip
4. 可以点击图例 → 显示/隐藏特定指标
```

### 13.4 深度对比Tab交互

#### 版本选择
```
1. 显示两个版本选择器（当前版本 + 对比版本）
2. 选择对比版本 → 重新加载对比数据
3. 所有对比图表和表格更新
```

#### 雷达图交互
```
1. 显示两个版本的重叠雷达图
2. 鼠标悬停 → 显示该维度的具体数值和差异
3. 可以点击图例 → 显示/隐藏特定版本
```

#### 违规分布变化表格
```
1. 显示每个违规类型的baseline、current、delta
2. delta为正 → 红色背景，表示违规增加
3. delta为负 → 绿色背景，表示违规减少
4. 可以点击某一行 → 跳转到该违规类型的用例列表
```

---

## 十四、错误处理与边界情况

### 14.1 数据为空

#### 概览页
```typescript
if (evalTypes.length === 0) {
  return <EmptyState message="暂无评测数据" />
}

if (latestResults.length === 0) {
  return <EmptyState message="暂无最近评测" />
}
```

#### 评测结果页
```typescript
if (items.length === 0) {
  return <EmptyState message="暂无评测结果" />
}

if (trendData.length === 0) {
  // 指标卡片不显示趋势图，只显示当前值
  return <MetricCard value={currentValue} trend={[]} />
}
```

#### 详情页
```typescript
if (!detail) {
  return <Loading />
}

if (detail.task_completion_rate === null) {
  // 不显示任务完成率区域
  return null
}
```

### 14.2 加载失败

#### API调用失败
```typescript
try {
  const { data } = await adminApi.evalResults(params)
  setItems(data.items)
} catch (error: any) {
  setError(error?.response?.data?.detail || '加载失败')
  // 显示错误提示
  toast.error('加载评测数据失败')
}
```

#### 趋势数据加载失败
```typescript
try {
  const { data } = await adminApi.evalTrend(params)
  setTrendData(data.trend)
} catch (error) {
  // 趋势数据加载失败不影响主流程
  console.error('趋势数据加载失败', error)
  setTrendData([])
}
```

### 14.3 数据异常

#### 指标值为null或undefined
```typescript
const displayValue = value ?? 0
const displayRate = rate != null ? (rate * 100).toFixed(1) : '0.0'
```

#### 趋势数据点不足
```typescript
if (trendData.length < 2) {
  // 不显示趋势图，或显示"数据不足"提示
  return <div className="text-gray-400 text-sm">数据不足，无法显示趋势</div>
}
```

#### 对比版本相同
```typescript
if (currentVersionId === compareVersionId) {
  toast.warning('不能选择相同的版本进行对比')
  return
}
```

---

## 十五、样式与布局细节

### 15.1 概览页布局

```typescript
<div className="min-h-screen bg-gray-50">
  <AdminNav />
  <div className="max-w-7xl mx-auto px-4 py-6">
    {/* 标题区 */}
    <div className="mb-6">
      <h1 className="text-2xl font-bold text-gray-900">评测中心概览</h1>
      <p className="text-sm text-gray-500 mt-1">查看评测指标趋势和版本对比</p>
    </div>

    {/* 版本选择器 */}
    <div className="bg-white rounded-lg shadow p-4 mb-6">
      <VersionSelector versions={versions} selectedVersion={selectedVersion} />
    </div>

    {/* 核心指标卡片 - 4列网格 */}
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <MetricCard title="检测准确率" value={matchRate} trend={matchRateTrend} />
      <MetricCard title="任务完成率" value={taskRate} trend={taskRateTrend} />
      <MetricCard title="正确率" value={accuracyRate} trend={accuracyTrend} />
      <MetricCard title="Badcase修复率" value={fixRate} trend={fixRateTrend} />
    </div>

    {/* 评测类型分布 - 饼图 */}
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <h2 className="text-lg font-semibold mb-4">评测类型分布</h2>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie data={typeDistribution} dataKey="value" />
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>

    {/* 最近评测列表 - 表格 */}
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        {/* 表格内容 */}
      </table>
    </div>
  </div>
</div>
```

### 15.2 评测结果页布局

```typescript
<div className="min-h-screen bg-gray-50">
  <AdminNav />
  <div className="max-w-7xl mx-auto px-4 py-6">
    <h1 className="text-2xl font-bold mb-6">评测结果</h1>

    {/* 筛选区 - 评测类型 + 版本选择器 */}
    <div className="bg-white rounded-lg shadow p-4 mb-6">
      <div className="flex gap-4 items-center">
        <select value={filterEvalType} onChange={...}>
          <option value="">全部类型</option>
          {evalTypes.map(t => <option value={t.type}>{t.label}</option>)}
        </select>
        <VersionSelector versions={versions} selectedVersion={selectedVersion} />
      </div>
    </div>

    {/* 指标卡片区域 - 根据评测类型动态展示 */}
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
      {selectedResult && (
        <>
          <MetricCard title="检测准确率" value={selectedResult.match_rate * 100} />
          <MetricCard title="通过率" value={selectedResult.pass_rate * 100} />
          <MetricCard title="L2格式完成率" value={(selectedResult.format_pass_rate || 0) * 100} />
          {selectedResult.eval_type === 'report_quality' && (
            <>
              <MetricCard title="任务完成率" value={selectedResult.task_completion_rate?.overall * 100} />
              <MetricCard title="正确率" value={selectedResult.accuracy_rate?.overall * 100} />
            </>
          )}
        </>
      )}
    </div>

    {/* 结果列表 - 表格 */}
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        {/* 表格内容 */}
      </table>
    </div>
  </div>
</div>
```

### 15.3 详情页布局

```typescript
<div className="min-h-screen bg-gray-50">
  <AdminNav />
  <div className="max-w-7xl mx-auto px-4 py-6">
    {/* 返回按钮 + 标题 */}
    <div className="mb-6">
      <button onClick={() => navigate(-1)} className="text-blue-600 mb-2">
        ← 返回
      </button>
      <h1 className="text-2xl font-bold">评测详情 #{detail.id}</h1>
    </div>

    {/* 版本选择器 */}
    <div className="bg-white rounded-lg shadow p-4 mb-6">
      <VersionSelector versions={versions} selectedVersion={selectedVersion} />
    </div>

    {/* Tab切换 */}
    <div className="mb-6 border-b border-gray-200">
      <nav className="-mb-px flex space-x-8">
        <button onClick={() => setActiveTab('overview')}>概览</button>
        <button onClick={() => setActiveTab('cases')}>用例详情</button>
        <button onClick={() => setActiveTab('compare')}>深度对比</button>
      </nav>
    </div>

    {/* Tab内容 */}
    {activeTab === 'overview' && (
      <>
        {/* 核心指标卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {/* MetricCards */}
        </div>

        {/* 任务完成率分层 */}
        {detail.task_completion_rate && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">任务完成率分层</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* L1-L4指标卡片 */}
            </div>
          </div>
        )}

        {/* 正确率各维度 */}
        {detail.accuracy_rate && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">正确率各维度</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* 7个维度指标卡片 */}
            </div>
          </div>
        )}

        {/* 软性评分 */}
        {detail.soft_score && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">软性评分</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* 5个维度指标卡片 */}
            </div>
          </div>
        )}

        {/* 违规分布 */}
        {detail.violation_distribution && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">违规分布</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={violationData}>
                <Bar dataKey="count" />
                <Tooltip />
                <XAxis dataKey="type" />
                <YAxis />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </>
    )}

    {activeTab === 'cases' && (
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {/* 用例详情列表 */}
      </div>
    )}

    {activeTab === 'compare' && (
      <div className="bg-white rounded-lg shadow p-6">
        {/* 对比版本选择器 */}
        <div className="mb-6">
          <VersionSelector versions={versions} selectedVersion={compareVersion} />
        </div>

        {/* 雷达图 - 任务完成率对比 */}
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-4">任务完成率对比</h2>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={taskCompletionRadarData}>
              <Radar dataKey="baseline" />
              <Radar dataKey="current" />
              <Tooltip />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* 雷达图 - 正确率维度对比 */}
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-4">正确率维度对比</h2>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={accuracyRadarData}>
              <Radar dataKey="baseline" />
              <Radar dataKey="current" />
              <Tooltip />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* 柱状图 - 软性评分对比 */}
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-4">软性评分对比</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={softScoreCompareData}>
              <Bar dataKey="baseline" />
              <Bar dataKey="current" />
              <Tooltip />
              <Legend />
              <XAxis dataKey="dimension" />
              <YAxis />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* 表格 - 违规分布变化 */}
        <div>
          <h2 className="text-lg font-semibold mb-4">违规分布变化</h2>
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th>违规类型</th>
                <th>基准版本</th>
                <th>当前版本</th>
                <th>变化</th>
              </tr>
            </thead>
            <tbody>
              {/* 表格内容 */}
            </tbody>
          </table>
        </div>
      </div>
    )}
  </div>
</div>
```

---

## 十六、测试策略

### 16.1 单元测试

#### 后端单元测试
```python
# test_eval_api.py
def test_eval_results_with_eval_type_filter():
    """测试评测类型筛选"""
    response = client.get("/api/admin/eval-results?eval_type=report_quality")
    assert response.status_code == 200
    data = response.json()
    assert all(item["eval_type"] == "report_quality" for item in data["items"])

def test_eval_trend_api():
    """测试趋势数据API"""
    response = client.get("/api/admin/eval-trend?metric_name=match_rate&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "trend" in data
    assert len(data["trend"]) <= 10

# test_eval_metrics.py
def test_task_completion_rate_calculation():
    """测试任务完成率计算"""
    result = calculate_task_completion_rate(cases)
    assert "l1_technical" in result
    assert "overall" in result
    assert 0 <= result["overall"] <= 1

def test_accuracy_rate_calculation():
    """测试正确率计算"""
    result = calculate_accuracy_rate(cases)
    assert "chart" in result
    assert "overall" in result
    assert 0 <= result["overall"] <= 1
```

#### 前端单元测试
```typescript
// MetricCard.test.tsx
test('renders metric card with trend', () => {
  const trend = [{ version: 'v1', value: 80 }, { version: 'v2', value: 85 }]
  render(<MetricCard title="检测准确率" value={85} trend={trend} />)
  expect(screen.getByText('检测准确率')).toBeInTheDocument()
  expect(screen.getByText('85.0')).toBeInTheDocument()
})

// VersionSelector.test.tsx
test('calls onSelect when version changes', () => {
  const onSelect = vi.fn()
  const versions = [{ id: 1, name: 'v1', created_at: '2026-01-01' }]
  render(<VersionSelector versions={versions} selectedVersion={1} onSelect={onSelect} />)
  fireEvent.change(screen.getByRole('combobox'), { target: { value: '1' } })
  expect(onSelect).toHaveBeenCalledWith(1)
})
```

### 16.2 集成测试

```typescript
// EvalOverview.integration.test.tsx
test('loads and displays overview data', async () => {
  render(<EvalOverview />)
  
  // 等待数据加载
  await waitFor(() => {
    expect(screen.getByText('检测准确率')).toBeInTheDocument()
  })
  
  // 验证指标卡片显示
  expect(screen.getByText('任务完成率')).toBeInTheDocument()
  expect(screen.getByText('正确率')).toBeInTheDocument()
  
  // 验证趋势图渲染
  expect(screen.getAllByRole('img', { name: /line chart/i }).length).toBeGreaterThan(0)
})

test('navigates to detail page on click', async () => {
  render(<EvalOverview />)
  
  await waitFor(() => {
    expect(screen.getByText('最近评测')).toBeInTheDocument()
  })
  
  fireEvent.click(screen.getByText('查看详情'))
  
  expect(window.location.pathname).toMatch(/\/admin\/eval\/detail\/\d+/)
})
```

### 16.3 端到端测试

```typescript
// eval-center.e2e.test.ts
test('complete eval center workflow', async () => {
  // 1. 访问概览页
  await page.goto('/admin/eval')
  await expect(page.locator('h1')).toHaveText('评测中心概览')
  
  // 2. 选择版本
  await page.selectOption('select[aria-label="版本选择"]', 'v2')
  await expect(page.locator('.metric-card')).toHaveCount(4)
  
  // 3. 点击评测类型
  await page.click('text=报告质量评测')
  await expect(page).toHaveURL(/eval_type=report_quality/)
  
  // 4. 查看评测结果
  await expect(page.locator('table')).toBeVisible()
  
  // 5. 进入详情页
  await page.click('text=查看详情')
  await expect(page.locator('h1')).toContainText('评测详情')
  
  // 6. 打开对比Tab
  await page.click('text=深度对比')
  await expect(page.locator('.radar-chart')).toBeVisible()
})
```

---

## 十七、部署与回滚策略

### 17.1 部署步骤

#### 阶段1：数据库迁移
```bash
# 备份数据库
pg_dump mingli_db > backup_$(date +%Y%m%d).sql

# 执行迁移
cd mingli-agent/backend
alembic upgrade head

# 验证迁移成功
psql mingli_db -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'eval_results';"
```

#### 阶段2：后端部署
```bash
# 构建后端
cd mingli-agent/backend
python -m build

# 重启服务
systemctl restart mingli-backend

# 验证API
curl http://localhost:8000/api/admin/eval-types
```

#### 阶段3：前端部署
```bash
# 构建前端
cd mingli-agent/frontend
npm run build

# 部署到Nginx
cp -r dist/* /var/www/mingli/

# 重启Nginx
systemctl restart nginx
```

#### 阶段4：验证
```bash
# 访问概览页
curl -I http://shisuansuan.com/admin/eval

# 访问评测结果页
curl -I http://shisuansuan.com/admin/eval/results

# 访问详情页
curl -I http://shisuansuan.com/admin/eval/detail/1
```

### 17.2 回滚策略

#### 数据库回滚
```bash
# 回滚迁移
alembic downgrade -1

# 恢复备份（如果需要）
psql mingli_db < backup_20260113.sql
```

#### 后端回滚
```bash
# 回滚代码
git checkout HEAD~1

# 重启服务
systemctl restart mingli-backend
```

#### 前端回滚
```bash
# 回滚代码
git checkout HEAD~1

# 重新构建
npm run build

# 部署
cp -r dist/* /var/www/mingli/

# 重启Nginx
systemctl restart nginx
```

### 17.3 监控与告警

#### 后端监控
```python
# 添加日志
logger.info(f"Eval result created: id={result.id}, eval_type={result.eval_type}")

# 添加指标监控
from prometheus_client import Counter
eval_result_counter = Counter('eval_results_total', 'Total eval results', ['eval_type'])
eval_result_counter.labels(eval_type='report_quality').inc()
```

#### 前端监控
```typescript
// 错误监控
window.addEventListener('error', (event) => {
  console.error('Frontend error:', event.error)
  // 发送到监控平台
  fetch('/api/monitor/error', {
    method: 'POST',
    body: JSON.stringify({
      message: event.message,
      stack: event.error?.stack,
      url: window.location.href,
    }),
  })
})

// 性能监控
window.addEventListener('load', () => {
  const timing = performance.timing
  const loadTime = timing.loadEventEnd - timing.navigationStart
  console.log(`Page load time: ${loadTime}ms`)
})
```

---

## 十八、总结

本次重构的核心变化：
1. **取消独立的对比页面**，将版本对比融入各页面
2. **每个指标卡片带mini趋势图**，随时看到版本变化
3. **指标持久化到数据库**，避免实时计算
4. **深度对比作为详情页的tab**，而不是独立页面

覆盖内容：
- 4种评测类型
- 7个检测维度
- 4层任务完成率
- 5维度软性评分
- Badcase动态评测
- 全版本趋势视图

实施计划：
- 阶段1：后端数据模型扩展（0.5天）
- 阶段2：后端API扩展（1天）
- 阶段3：前端核心组件（1天）
- 阶段4：前端概览页（1天）
- 阶段5：评测结果页重构（1天）
- 阶段6：评测详情页重构（1.5天）
- 阶段7：评测集管理页（1天）
- 阶段8：集成测试（0.5天）

总计：7.5天
