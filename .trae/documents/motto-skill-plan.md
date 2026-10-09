# 命格箴言功能实现方案

## 一、需求概述

每个人物首次测算时，基于**调候标签 + 十神做功标签**生成一句**4字对仗箴言**，采用 skill 方式实现，提供静态库精确匹配 + 多级降级。

## 二、数据流

```
orchestrator.py
  → motto_skill.generate_motto(analysis_data)
    → _extract_climate_tag(月令, 日主, 调候用神, 调候描述)
    → _extract_shishen_action_tag(十神分布, 格局, 旺衰, 四柱)
    → _lookup_motto(调候标签, 十神做功标签)  // 三级查找
  → result["命格箴言"] = "寒木向阳"
  → 前端 AnalyzeResult.命格箴言 → 摘要卡片展示
```

## 三、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/skills/divination/motto_skill.py` | **新建** | 命格箴言 skill |
| `backend/app/skills/orchestrator.py` | **修改** | 集成调用 + 输出字段 |
| `frontend/src/api/bazi.ts` | **修改** | 接口新增字段 |
| `frontend/src/pages/Chat.tsx` | **修改** | 卡片展示箴言 |

## 四、分步实施

### 第1步：新建 `motto_skill.py`

路径：`backend/app/skills/divination/motto_skill.py`

#### 1.1 调候标签提取

从月令地支推断季节（春/夏/秋/冬），从调候描述提取气候特征（寒/热/燥/暖/凉），组合调候用神五行：

标签格式：`{气候特征}{用神五行}`，如 `寒火`、`热水`、`暖水`、`凉火`、`燥水`

枚举约 10 种：`寒火/寒木/寒土`、`热水/热金/热土`、`暖水/暖火`、`凉火/凉水`、`燥水/燥金`

#### 1.2 十神做功标签提取

解析十神分布字符串，识别经典组合（优先级从高到低）：

| 组合 | 条件 |
|------|------|
| 食神生财 | 食神 + 正财/偏财 同时出现 |
| 伤官生财 | 伤官 + 正财/偏财 |
| 杀印相生 | 七杀 + 正印/偏印 |
| 伤官配印 | 伤官 + 正印/偏印 |
| 财官双美 | 正财/偏财 + 正官/七杀 |
| 食神制杀 | 食神 + 七杀 |

无组合时降级为格局十神 + 旺衰：`官星为用`、`印星护身`、`食神泄秀`、`财星为用`、`杀气为权`、`伤官泄秀`、`比劫帮身`、`印比生扶`

共约 15 种做功标签。

#### 1.3 静态库

主库：`Dict[(调候标签, 做功标签), 箴言]`，覆盖常见组合约 60-80 条。

示例：
```
("寒火", "杀印相生") → "寒木向阳"
("寒火", "印星护身") → "寒谷回春"
("热水", "财官双美") → "水火既济"
("暖水", "杀印相生") → "春风化雨"
("凉火", "财官双美") → "金玉满堂"
("燥水", "食神生财") → "旱地甘霖"
```

做功降级库（15条）：`"食神生辉"`、`"杀印相成"`、`"财官双美"` 等

终极降级库（5条，按调候用神五行）：`金→金玉其质`、`木→木秀于林`、`水→上善若水`、`火→光明磊落`、`土→厚德载物`

#### 1.4 主函数

```python
def generate_motto(month_di, day_tian, tiaohou_yongshen, tiaohou_description,
                   shishen_distribution, geju_type, geju_shishen,
                   wangshuai_conclusion, shishen_map, pillars) -> Dict[str, str]:
    # 返回 {"命格箴言": "寒木向阳", "调候标签": "寒火", "十神做功标签": "杀印相生"}
```

### 第2步：修改 `orchestrator.py`

- 新增 import：`from app.skills.divination.motto_skill import generate_motto`
- 在十神分布计算之后（约第 396 行后）调用 `generate_motto()`
- 在 `result` 字典中新增 `"命格箴言"` 和 `"命格箴言标签"` 字段

### 第3步：修改前端 `bazi.ts`

`AnalyzeResult` 接口新增：
```typescript
命格箴言?: string
命格箴言标签?: { 调候标签: string; 十神做功标签: string }
```

### 第4步：修改前端 `Chat.tsx`

摘要卡片（`cardPhase === 'ready'`）中：
- 箴言以大号 serif 字体居中展示（`text-3xl font-bold text-indigo-700 tracking-[0.5em]`）
- 下方小字展示标签：`寒火 · 杀印相生`
- 原有 `buildGejuSummary` 缩小为辅助信息

## 五、验证清单

- [ ] 后端 `/api/bazi/analyze` 返回 JSON 包含 `命格箴言` 和 `命格箴言标签` 字段
- [ ] 不同八字组合返回不同箴言
- [ ] 静态库未命中时降级逻辑正常
- [ ] 前端摘要卡片正确展示箴言
- [ ] 箴言为 4 字对仗短句
