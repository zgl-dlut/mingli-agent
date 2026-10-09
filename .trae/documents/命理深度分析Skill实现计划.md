# 命理深度分析 Skill 全体系实现计划

## 摘要

当前八字排盘仅实现了基础四柱+十神+五行统计，**缺少调候分析、格局判定、十神做功等核心命理深度分析能力**。本次重构目标：

1. **新增 7 个命理 Skill**，覆盖从排盘到开运的完整链路
2. **重构 Skill 编排层**，让 Skill 真正参与请求处理（当前 Skill 层被架空，API 层直接调 Service）
3. **新增商业化输出模板**：8 字命格概括 + 查看解读按钮 + 完整报告
4. **所有 Skill 结果注入 AI 提示词**，让 AI 基于结构化数据生成高质量解读

---

## 一、现状分析

### 已有能力（基础排盘层）
- ✅ 四柱排盘（年月日时）、天干十神、五行统计、纳音、藏干、大运、流年

### 完全缺失（深度分析层）
- ❌ 调候分析（寒暖燥湿、调候用神）
- ❌ 格局判定（正八格、外格）
- ❌ 十神做功（食神制杀、伤官佩印等）
- ❌ 日主旺衰（得令、得地、得势）
- ❌ 用神/喜神/忌神体系
- ❌ 地支作用关系（六合/三合/六冲/三刑/六害/自刑）
- ❌ 大运流年互动分析（岁运交战）
- ❌ 五行开运映射（行业/色彩/方位/脏腑）

### 当前架构问题

**Skill 层被架空**：API 层（person.py、chat.py）直接 import 并调用 Service 层函数，从不通过 `registry.get().execute()` 调用 Skill。SkillRegistry 仅起到注册展示作用（`GET /api/skills`），未参与实际请求处理。

```
当前实际调用链（Skill 层空转）：
API 层(person.py) → Service 层(bazi_service) → 结果
                     ↗ Skill 层(BaziSkill) → 也调 Service 层，但没人调它
```

---

## 二、完整 Skill 体系设计（共 13 个 Skill）

### 命理计算类（7 个新增 + 2 个已有）

| # | Skill 名称 | name | 输入 | 输出 | 状态 |
|---|-----------|------|------|------|------|
| 1 | 八字排盘 Skill | `bazi_calculation` | 公历生日、性别、经度 | 四柱、月令、日主、藏干、本气余气 | ✅ 已有 |
| 2 | 十神换算 Skill | `shishen_mapping` | 日干 + 其他天干/藏干 | 十神映射（比肩/劫财/食神...） | 🆕 新增 |
| 3 | 地支作用关系 Skill | `dizhi_relations` | 四柱地支 | 六合/三合/六冲/三刑/六害/自刑/半合 | 🆕 新增 |
| 4 | 调候格局判定 Skill | `tiaohou_geju` | 日干 + 月令 + 四柱 | 调候用神、寒暖燥湿、格局断语 | 🆕 新增 |
| 5 | 日主旺衰 Skill | `dayun_flow` | 日干 + 月令 + 四柱 + 藏干 | 身旺/身弱、得令/得地/得势 | 🆕 新增 |
| 6 | 十神做功 Skill | `shishen_zuogong` | 四柱十神 + 藏干十神 | 做功模式（食神制杀/伤官佩印...） | 🆕 新增 |
| 7 | 大运流年推演 Skill | `dayun_flow` | 四柱 + 性别 + 当前年份 | 起运岁数、十年一运、岁运交战 | 🆕 新增 |
| 8 | 五行开运 Skill | `wuxing_kaiyun` | 五行分布 + 用神 | 行业/色彩/方位/脏腑映射 | 🆕 新增 |
| 9 | 占星排盘 Skill | `astrology_calculation` | 公历生日、经纬度 | 星盘数据 | ✅ 已有 |

### 业务能力类（4 个已有）

| # | Skill 名称 | name | 状态 |
|---|-----------|------|------|
| 10 | 手机验证码认证 Skill | `sms_auth` | ✅ 已有 |
| 11 | 积分支付 Skill | `payment` | ✅ 已有 |
| 12 | AI 内容生成 Skill | `ai_content` | ✅ 已有 |
| 13 | 安全管理 Skill | `security` | ✅ 已有 |

### Skill 编排依赖图

```
用户创建人物 → [1]bazi_calculation → [2]shishen_mapping → [3]dizhi_relations
                                                    ↓
                                              [4]tiaohou_geju
                                                    ↓
                                              [5]wang_shuai
                                                    ↓
                                              [6]shishen_zuogong
                                                    ↓
                                              [7]dayun_liunian
                                                    ↓
                                              [8]wuxing_kaiyun
                                                    ↓
              所有结果 → prompt_builder → [9]ai_content → AI 解读
```

---

## 三、商业化输出模板设计

### 3.1 命格概括（8 个字）

根据调候格局 + 十神做功 + 日主旺衰，生成 8 字概括。例如：
- "身弱杀重用印"
- "食神生财富贵"
- "伤官佩印掌权"
- "寒土喜火调候"
- "身旺财旺有成"

**生成规则**：在 `tiaohou_geju` Skill 中，根据日主旺衰 + 主格局 + 调候状态组合查表。

```python
GEJU_SUMMARY_TABLE = {
    ("身弱", "七杀格", "寒"): "身弱杀重用印",
    ("身旺", "正财格", "平"): "身旺财旺有成",
    ("身弱", "食神格", "寒"): "食神泄秀寒局",
    # ... 覆盖常见组合
}
```

### 3.2 前端展示流程

```
用户点击"开始推算"
    ↓
创建人物 → 依次调用所有命理 Skill → 汇总结果
    ↓
展示「命格概括」卡片（8 个字大字）
    + "查看完整解读" 按钮
    ↓
用户点击"查看完整解读"
    ↓
调用 AI Content Skill → 基于所有 Skill 数据生成完整报告
    ↓
展示完整命理报告（流式输出）
```

### 3.3 完整报告模板（AI 生成的结构 — 商业化心理学融合风格）

AI 角色设定：融合传统子平八字命理 + 现代心理学的专业命理咨询师，输出付费定制式深度人生命理说明书。

**核心写作原则**：
- 禁止生硬算命宿命论，全程用现代心理学词汇转译命理象义（完美主义、精神内耗、逆商、情绪价值、共情力等）
- 多用比喻修辞，将命理比作人生高阶天气预报
- 统一日主核心意象贯穿全文（如己土=初冬田园土）
- 逻辑因果绑定：每一条性格/运势结论前置命理原理，每一条化解建议对应用神规则
- 叙事节奏：先天底层格局 → 共情性格痛点 → 事业婚姻现实 → 时间机遇预期 → 日常可执行改运方法
- 情绪写法：先扬后抑再扬，不制造焦虑
- 语言风格：专业但通俗，商业付费报告质感，流畅长篇段落

```
═══ 【开篇序言】═══
定调：说明是传统命理+心理学结合，弱化宿命论，核心思路顺势而为。
引出：定制命理画像 + 人生战略规划。
（以日主核心意象开篇，如"你是一方初冬的田园沃土，安静承载、默默滋养..."）

═══ 【模块一：八字基本盘与核心格局】═══
1. 日主五行定性：解读日主先天本质（阴阳区分，如戊土=阳土山川、己土=阴土田园盆栽，赋予人格意象）
2. 分层拆解全局五行能量：
   - 月令本气（第一优先级）
   - 地支合局（半合/三合带来的能量加成）
   - 帮扶五行（比劫/印星的力量来源）
   - 全局唯一救星（调候用神/第一用神）
3. 整体格局定调：身弱/身强 + 格局名 + 调候需求
   - 格局用心理学语言转译（如"七杀格"→"你天生带有危机感雷达，对风险极度敏感"）
4. 用神体系清晰列出：
   - 第一用神：X（原因）
   - 辅助喜神：X、X
   - 忌神：X、X
   - （用通俗语言解释：第一用神就是你人生的"充电器"，忌神就是"耗电器"）

═══ 【模块二：性格特质与潜能画像】═══
1. 先天优势：
   - 日主核心特质（如己土=踏实靠谱、包容力强、情绪稳定）
   - 印星加持（善良、共情力、底线意识、靠谱人设）
   - 正面心理学术语包装（高情绪价值、强共情力、高逆商等）
2. 内在痛点：
   - 七杀贴身带来的焦虑/完美主义/精神内耗/悲观防备
   - 伤官带来的叛逆/不羁/口无遮拦
   - 用心理学词汇深度共情（"你不是不够好，而是对自己要求太高"）
3. 格局潜能：
   - 做功模式解读（如杀印相生→高逆商、危机处理能力、职场救火队长）
   - 用比喻和案例说明潜能如何转化为现实优势

═══ 【模块三：事业与财富发展核心策略】═══
1. 五行行业划分：
   - 首选大吉五行行业（详细列举，如火=教育/传媒/互联网/新能源）
   - 次吉辅助行业
   - 严禁从事忌神行业（如水忌神→远离金融投机）
2. 求财底层逻辑：
   - 解读财星配置（财生杀旺→投机快钱招灾、压力反噬）
   - 正财vs偏财的心理投射（正财=稳定收入安全感，偏财=投资理财冒险欲）
3. 落地求财路径（全部对应用神逻辑）：
   - 考证提升学历（印星化杀）
   - 打造个人IP名气（食伤生财）
   - 依附大平台/贵人（正官正印护身）
   - 每条路径给出具体可执行建议

═══ 【模块四：婚姻与感情分析】═══
1. 夫星/妻星定位：
   - 星座定位（男看财星、女看七杀/官星）
   - 夫妻宫解读（日支），伴侣性格画像
   - 婚姻固有压力羁绊（冲/刑/害夫妻宫→冷战、内耗、聚少离多）
2. 大运合动分析：
   - 哪步大运引动夫妻宫→感情波动期
   - 用神大运→感情稳定上升期
3. 专属婚恋化解方案：
   - 用神五行沟通方式（如用神为火→多表达温暖、主动创造浪漫）
   - 穿搭色彩暗示
   - 共处方位建议

═══ 【模块五：大运流年与人生拐点】═══
1. 当前十年大运完整解读：
   - 大运天干（外在环境/事业面）
   - 大运地支（内在状态/感情健康面）
   - 大运隐患（忌神大运→需提前布局）
   - 暗藏贵人支撑（喜神透出→意外助力）
   - 定性大运阶段（积累期/爆发期/调整期/收获期）
2. 重点用神流年专项拆解：
   - 流年利好机遇（用神流年→事业突破/感情开花/财运提升）
   - 流年暗藏暗礁（忌神流年→需防范的风险领域）
   - 配套应对策略（每条风险都有对应化解方案）

═══ 【模块六：定制风水与健康开运指南】═══
1. 穿搭色彩：
   - 开运色系（用神五行对应颜色，如火=红/紫/橙）
   - 避忌色系（忌神五行对应颜色）
   - 四季穿搭建议
2. 吉利方位与居家办公布局：
   - 有利方位（用神五行方位）
   - 办公桌朝向、座位布局
   - 居家风水摆件宜忌
   - 绿植推荐（五行对应植物）
3. 健康养生：
   - 八字先天五行缺陷→对应脏腑疾病风险
   - 全套养生调理方案（饮食/运动/作息/中医穴位）
   - 情绪管理建议（对应印星/七杀的心理调适）

═══ 【结尾总结升华】═══
1. 复盘全局核心意象（呼应开篇日主比喻）
2. 提炼终身核心行动纲领（3-5条精炼建议）
3. 结合当下大运+重点流年给出正向祝福与心理引导
4. 收尾金句（温暖有力，如"命运给了你一副好牌，怎么打，你说了算"）
```

**AI 提示词注入策略**：
- 将所有 Skill 计算结果（排盘/十神/格局/调候/旺衰/做功/地支/大运/开运）以结构化 JSON 注入 system prompt
- 在 system prompt 中嵌入上述完整的写作规则和输出结构
- AI 只需按照模板"填空"，所有命理数据由 Skill 提供确保准确性，AI 负责心理学转译和流畅叙事

---

## 四、文件变更清单

### 新建文件（10 个）

| 文件 | 说明 |
|------|------|
| `services/shishen_service.py` | 十神换算：天干五行生克映射表 + 藏干十神计算 |
| `services/dizhi_relations_service.py` | 地支作用关系：六合/三合/六冲/三刑/六害/自刑规则库 |
| `services/tiaohou_geju_service.py` | 调候格局：120 条月令调候表 + 格局判定 + 命格概括生成 |
| `services/wang_shuai_service.py` | 日主旺衰：得令/得地/得势三维度评分 |
| `services/shishen_zuogong_service.py` | 十神做功：做功模式识别 + 有效性评估 |
| `services/dayun_liunian_service.py` | 大运流年：起运岁数 + 十年一运 + 岁运交战判断 |
| `services/wuxing_kaiyun_service.py` | 五行开运：行业/色彩/方位/脏腑静态对照表 |
| `services/report_builder_service.py` | 报告组装：汇总所有 Skill 结果 + 生成命格概括 + 组装完整数据包 |
| `skills/divination/shishen_skill.py` | 十神换算 Skill 封装 |
| `skills/divination/tiaohou_geju_skill.py` | 调候格局 Skill 封装（合并调候+格局+旺衰+做功） |

> 注：地支作用、大运流年、五行开运逻辑较简单，直接在 `report_builder_service.py` 中实现，不单独创建 Skill 文件。

### 修改文件（6 个）

| 文件 | 改动 |
|------|------|
| `skills/divination/__init__.py` | 新增导出 ShishenSkill, TiaohouGejuSkill |
| `main.py` | 注册新 Skill |
| `services/prompt_builder.py` | 新增所有命理分析数据注入（调候/格局/做功/地支/开运） |
| `services/ai_service.py` | `generate_first_reading` 中调用新 Skill 链 |
| `api/person.py` | 创建人物时调用完整 Skill 链（替代直接调 bazi_service） |
| `api/chat.py` | 首次解读分两步：先返回命格概括，再生成完整报告 |

### 前端修改文件（2 个）

| 文件 | 改动 |
|------|------|
| `pages/Chat.tsx` | 新增「命格概括」卡片展示 + "查看完整解读"按钮 |
| `pages/AddPerson.tsx` | 创建人物后先展示命格概括，不直接跳转对话 |

---

## 五、实现步骤

### Step 1: 创建命理基础数据服务

#### 1.1 `services/shishen_service.py` — 十神换算
- 固定天干五行生克映射表（甲木克己土 = 七杀、水生木 = 财生杀等），纯查表逻辑
- 计算所有藏干（本气/余气/杂气）的十神
- 输出：四柱天干十神 + 地支藏干十神完整映射

#### 1.2 `services/dizhi_relations_service.py` — 地支作用关系
- 内置规则库：六合（6组）、三合（4组）、半合（8组）、六冲（6组）、三刑（4组）、六害（6组）、自刑（4组）
- 地支五行属性：辰为湿土、戌为燥土等
- 输入四柱地支，输出所有作用关系列表

### Step 2: 创建命理深度分析服务

#### 2.1 `services/tiaohou_geju_service.py` — 调候格局判定
- 120 条月令调候表（日干×月令），自动输出「身弱杀重用印、寒土喜火」类格局断语
- 正八格判定（月令藏干透出关系）
- 外格判定（从格/化格/建禄格）
- 命格概括生成（8 字概括查表）

#### 2.2 `services/wang_shuai_service.py` — 日主旺衰
- 得令：月支主气五行与日干五行的生克关系
- 得地：日支/年支/时支藏干是否有日干同类五行
- 得势：天干是否有比肩/劫财
- 输出：身旺/身弱 + 三维度明细 + 综合评分

#### 2.3 `services/shishen_zuogong_service.py` — 十神做功
- 做功模式库：食神制杀、伤官佩印、财星生杀、杀印相生、食伤生财、官印相生
- 检查所需十神是否同时存在于八字中
- 评估有效性（力量对比）
- 输出：匹配的做功模式列表 + 有效性

### Step 3: 创建扩展分析服务

#### 3.1 `services/dayun_liunian_service.py` — 大运流年推演
- 基于现有 `bazi_service.calculate_dayun()` 扩展
- 固定起运岁数计算
- 十年一运，区分天干运 / 地支运
- 岁运交战判断（大运与流年的冲合刑害）

#### 3.2 `services/wuxing_kaiyun_service.py` — 五行开运映射
- 内置静态对照表：
  - 五行→行业：火=教育传媒互联网，木=园林生鲜，水=金融水产，金=机械法律，土=房地产农业
  - 五行→色彩方位：火=红/正南，水=黑/正北，木=绿/正东，金=白/正西，土=黄/中宫
  - 五行→脏腑：火主心脏眼睛，木主肝胆，水主肾耳骨髓，金主肺大肠，土主脾胃
- 输入：用神五行 + 八字五行分布
- 输出：推荐行业/色彩/方位/健康提示

### Step 4: 创建报告组装服务

#### 4.1 `services/report_builder_service.py` — 报告组装器
- **核心编排函数** `build_full_report(bazi_data, astro_data, gender)`：
  1. 调用 shishen_service → 十神完整映射
  2. 调用 dizhi_relations_service → 地支作用关系
  3. 调用 tiaohou_geju_service → 调候格局 + 命格概括
  4. 调用 wang_shuai_service → 日主旺衰
  5. 调用 shishen_zuogong_service → 做功模式
  6. 调用 dayun_liunian_service → 大运流年
  7. 调用 wuxing_kaiyun_service → 开运指南
  8. 汇总为 `FullReport` Pydantic 模型
- 输出模型 `FullReport`：
  ```python
  class FullReport(BaseModel):
      geju_summary: str              # 8 字命格概括
      bazi_chart: dict               # 四柱数据
      shishen_full: dict             # 完整十神映射
      dizhi_relations: dict          # 地支作用关系
      tiaohou: dict                  # 调候分析
      geju: dict                     # 格局判定
      wang_shuai: dict               # 日主旺衰
      zuogong: list                  # 做功模式
      dayun_liunian: dict            # 大运流年
      kaiyun: dict                   # 开运指南
      ai_prompt_data: str            # 预格式化的 AI 提示词数据块
  ```

### Step 5: 创建 Skill 封装

#### 5.1 `skills/divination/shishen_skill.py`
- name: `shishen_mapping`

#### 5.2 `skills/divination/tiaohou_geju_skill.py`
- name: `tiaohou_geju_analysis`
- 内部调用 tiaohou_geju_service + wang_shuai_service + shishen_zuogong_service

### Step 6: 集成到系统

#### 6.1 `main.py`
- 注册 ShishenSkill + TiaohouGejuSkill

#### 6.2 `api/person.py` 修改
- 创建人物时调用 `report_builder_service.build_full_report()`
- 将完整报告存入 `ChatSession.report_json`（新增字段）
- 返回命格概括给前端

#### 6.3 `api/chat.py` 修改
- 新增 `GET /api/chat/sessions/{session_id}/report` — 返回已生成的命格概括
- 新增 `POST /api/chat/sessions/{session_id}/full-reading` — 触发 AI 生成完整报告
- `first-reading` 改为返回命格概括（不调 AI）

#### 6.4 `services/prompt_builder.py` 修改
- `build_system_prompt()` 新增参数 `report_data: FullReport`
- 将所有命理分析数据以紧凑格式注入提示词（控制新增 token 在 500 以内）

#### 6.5 `services/ai_service.py` 修改
- `generate_first_reading()` → 改为 `generate_full_reading()`
- 接收 `report_data` 参数，传给 `prompt_builder`

### Step 7: 前端适配

#### 7.1 `pages/Chat.tsx`
- 新增「命格概括」卡片组件：
  - 大字显示 8 字概括
  - 下方显示简要信息（格局/旺衰/调候评分）
  - "查看完整解读" 按钮（扣 160 积分）
- 点击按钮后调用 `POST /api/chat/sessions/{id}/full-reading`
- 流式展示完整报告

#### 7.2 `pages/AddPerson.tsx`
- 创建人物后不直接跳转 Chat
- 先展示命格概括卡片
- "查看完整解读" 按钮跳转到 Chat 页

---

## 六、Skill 编排重构方案

### 当前问题
API 层直接调 Service，Skill 层空转。

### 重构方案：引入 SkillOrchestrator

在 `services/report_builder_service.py` 中实现编排器，作为所有命理 Skill 的统一调度入口：

```python
class SkillOrchestrator:
    """命理 Skill 编排器 — 统一调度所有命理计算 Skill"""
    
    def __init__(self, registry: SkillRegistry):
        self.registry = registry
    
    async def build_full_report(self, birth_date, birth_time, longitude, gender):
        # Step 1: 八字排盘
        bazi_result = await self.registry.get("bazi_calculation").execute(...)
        
        # Step 2: 十神换算（依赖排盘结果）
        shishen_result = await self.registry.get("shishen_mapping").execute(...)
        
        # Step 3: 地支作用关系
        dizhi_result = await self.registry.get("dizhi_relations").execute(...)
        
        # Step 4-8: 并行调用深度分析 Skill
        tiaohou, wang_shuai, zuogong, dayun, kaiyun = await asyncio.gather(
            self.registry.get("tiaohou_geju").execute(...),
            self.registry.get("wang_shuai").execute(...),
            ...
        )
        
        # Step 9: 汇总
        return FullReport(...)
```

API 层只需调用 `orchestrator.build_full_report()`，不再直接调 Service。

---

## 七、假设与决策

1. **120 条调候数据**：基于《穷通宝鉴》原文编码，每条包含用神/喜神/忌神/温度/摘要
2. **格局优先级**：从格 > 化格 > 正八格 > 建禄格 > 暗格
3. **做功模式**：作为参考信号输出，标注有效性（有效/部分有效/无效）
4. **旺衰判定**：采用"得令+得地+得势"三维度评分法
5. **命格概括**：通过查表生成（旺衰×格局×调候 组合），不依赖 AI
6. **完整报告**：由 AI 基于结构化数据生成，按固定模板输出
7. **前端两步展示**：先展示命格概括（免费），再查看完整解读（扣积分）
8. **Skill 编排**：通过 SkillOrchestrator 统一调度，API 层不再直接调 Service
9. **prompt 长度控制**：所有命理数据新增 token 控制在 500 以内

## 八、验证步骤

1. 用经典命例验证调候结果（"冬生甲木需丙火"）
2. 用已知格局验证格局判定（"月令正官透干→正官格"）
3. 验证命格概括生成正确（8 字概括与实际命局匹配）
4. 验证 SkillOrchestrator 编排链路完整
5. 验证 prompt_builder 注入后提示词格式正确
6. 验证前端两步展示流程（概括 → 完整解读）
7. 验证 main.py 启动后所有 Skill 注册成功
