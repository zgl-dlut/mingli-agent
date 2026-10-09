# 评测指标展示补全计划

## 一、现状分析

### 1.1 后端数据模型（已完成）
后端 `EvalResultItem` 接口已定义完整指标：
- `match_rate` - 检测准确率
- `pass_rate` - 通过率
- `format_pass_rate` - L2格式完成率
- `task_completion_rate` - 任务完成率（L1-L4分层）
- `accuracy_rate` - 正确率（7维度）
- `soft_score` - 软性评分（5维度）
- `violation_distribution` - 违规分布

### 1.2 前端展示现状（不完整）

| 指标 | EvalDashboard | EvalOverview | EvalDetailPage |
|------|:---:|:---:|:---:|
| 检测准确率 | ✅ 卡片+表格 | ✅ 卡片 | ✅ 概览区 |
| 通过率 | ✅ 卡片+表格 | ✅ 卡片 | ✅ 概览区 |
| L2格式完成率 | ✅ 卡片+表格 | ❌ | ✅ 概览区 |
| 任务完成率(L1-L4) | ❌ | ✅ 仅overall | ❌ |
| 正确率(7维度) | ❌ | ✅ 仅overall | ❌ |
| 软性评分(5维度) | ❌ | ❌ | ❌ |
| 违规分布 | ❌ | ❌ | ❌ |

---

## 二、补全方案

### 2.1 EvalDetailPage 补全（核心）

**文件**: `frontend/src/pages/EvalDetailPage.tsx`

**补全内容**:

1. **任务完成率分层展示**
   - 使用进度条或分层卡片展示 L1-L4 各层级
   - 显示 overall 综合值
   - 结构示例：
   ```
   任务完成率
   ├── L1 技术完成率: 95%  [████████░░]
   ├── L2 格式完成率: 90%  [█████████░]
   ├── L3 质量完成率: 88%  [████████░░]
   ├── L4 满意度:   82%  [████████░░]
   └── 综合:       85%  [████████░░]
   ```

2. **正确率7维度展示**
   - 使用雷达图（Recharts RadarChart）展示7个维度
   - 维度：chart/structure/narrative/logic/consistency/safety/overall
   - 显示 overall 综合值

3. **软性评分5维度展示**
   - 使用横向柱状图或雷达图展示5个维度
   - 维度：叙事性/通顺性/故事性/加粗合理性/术语通俗化
   - 显示 avg 平均分

4. **违规分布展示**
   - 使用饼图或横向柱状图展示各违规类型计数
   - 按计数降序排列

### 2.2 EvalDashboard 补全

**文件**: `frontend/src/pages/EvalDashboard.tsx`

**补全内容**:

1. **新增 task_completion_rate MetricCard**
   - 显示 overall 值
   - 添加趋势数据（从历史版本构建）
   - 添加 delta 显示

2. **新增 accuracy_rate MetricCard**
   - 显示 overall 值
   - 添加趋势数据
   - 添加 delta 显示

3. **调整布局**
   - 从 3 列改为 5 列（或 2 行：3+2）
   - 保持响应式布局

### 2.3 EvalOverview 补全

**文件**: `frontend/src/pages/EvalOverview.tsx`

**补全内容**:

1. **MetricCard 补上趋势图**
   - 检测准确率卡片：添加 trend 和 delta
   - 任务完成率卡片：添加 trend 和 delta
   - 正确率卡片：添加 trend 和 delta
   - 通过率卡片：添加 trend 和 delta

2. **新增 L2格式完成率卡片**
   - 与其他卡片保持一致

---

## 三、实现步骤

### 步骤1：EvalDetailPage 补全
1. 在概览区下方新增"详细指标"区域
2. 实现任务完成率分层展示组件
3. 实现正确率雷达图组件
4. 实现软性评分展示组件
5. 实现违规分布展示组件

### 步骤2：EvalDashboard 补全
1. 构建 task_completion_rate 和 accuracy_rate 的趋势数据
2. 新增两个 MetricCard
3. 调整网格布局

### 步骤3：EvalOverview 补全
1. 为每个 MetricCard 添加 trend 和 delta 数据
2. 新增 L2格式完成率卡片
3. 调整网格布局

### 步骤4：构建验证
1. 运行 `npm run build` 确保无 TypeScript 错误
2. 本地启动验证页面渲染正常

---

## 四、技术细节

### 4.1 雷达图实现（Recharts）
```tsx
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts'

<RadarChart data={accuracyData}>
  <PolarGrid />
  <PolarAngleAxis dataKey="dimension" />
  <PolarRadiusAxis />
  <Radar dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.6} />
</RadarChart>
```

### 4.2 进度条实现
```tsx
<div className="w-full bg-gray-200 rounded-full h-2">
  <div 
    className="bg-blue-600 h-2 rounded-full" 
    style={{ width: `${value}%` }}
  />
</div>
```

### 4.3 趋势数据构建
从 `evalResults` API 返回的历史版本中提取对应指标，构建趋势数组。

---

## 五、验证清单

- [ ] EvalDetailPage 展示 task_completion_rate 分层
- [ ] EvalDetailPage 展示 accuracy_rate 雷达图
- [ ] EvalDetailPage 展示 soft_score
- [ ] EvalDetailPage 展示 violation_distribution
- [ ] EvalDashboard 展示 5 个 MetricCard
- [ ] EvalOverview 所有 MetricCard 带趋势图
- [ ] `npm run build` 无错误
- [ ] 本地页面渲染正常
