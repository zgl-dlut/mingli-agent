---
name: qusuansuan-ui-design
description: 设计趣算算APP移动端高保真HTML设计稿。当用户要求设计页面、出设计稿、UI稿、mockup、视觉稿、改版面或新增页面视觉方案时使用。输出自包含HTML到 .trae/documents/ui-design/。不用于写RN业务代码。
---

# 趣算算 UI 设计

为趣算算APP（八字命理产品，React Native）产出高保真HTML设计稿。设计稿是给开发看的视觉基准，不是可运行代码。

## 第一步：加载规格

设计任何页面前，先读 [趣算算APP-V1需求文档.md](file:///Users/zhangguangling/Downloads/命理推算/.trae/documents/趣算算APP-V1需求文档.md) 对应章节（五、页面设计的ASCII线框 + 模块说明 + 5.2.1对标发现）。线框图是唯一事实源，设计稿模块顺序和内容必须与之一致，不得自行增删模块。

## 输出规范

- 位置：`.trae/documents/ui-design/<编号>-<页面名>.html`，编号两位（01-今日页、02-对话页、03-对话页-情绪模式、04-我的页、05-会员中心、06-订阅支付、07-建档引导页、00-index画廊）
- 每个文件**完全自包含**：内联CSS、无外部依赖、无JS框架，可直接浏览器打开
- 手机壳：外层深色背景居中，390px宽iPhone框（圆角44px、含状态栏9:41/电量、底部Home indicator）
- 00-index.html 用 iframe 缩略拼廊展示全部页面（transform scale 0.55），供总览

## 设计 Tokens（全页面统一）

```css
:root {
  --bg: #F7F5F0;          /* 宣纸暖白，页面底 */
  --card: #FFFFFF;         /* 卡片 */
  --brand: #4A4E8F;        /* 黛蓝紫，主色/Tab选中/主CTA */
  --brand-soft: #EEEFF9;   /* 主色浅底 */
  --gold: #C9A86A;         /* 金色点缀：会员/吉/高亮边框 */
  --ink: #2B2B33;          /* 主文字 */
  --ink-2: #8A8A93;        /* 次文字 */
  --success: #2E9E6B;      /* 宜/吉 */
  --danger: #D9534F;       /* 忌/凶 */
  --radius-card: 16px; --radius-pill: 999px;
  font-family: -apple-system, "PingFang SC", sans-serif;
}
```

- 吉凶语义色不可换：吉/宜=绿(--success)，凶/忌=红(--danger)，中性强=金
- Tab栏：3个（今日/对话/我的），选中态brand色，白底带顶部细分割线
- AI标识统一样式：`AI回应` pill，brand-soft底+brand字，10px，常驻卡片左上
- 免责声明：`内容由AI生成，仅供自我梳理参考`，ink-2色11px居中，运势/对话/情绪页底部必在场

## 文案规范

直接使用需求文档中的示例文案（如"今日小吉""压力指数45""宜见贵·谈事·学习"），不用占位 lorem。数据用文档示例值（辛金日主/压力45/额度8/10/¥25/58/178）。

## 自检清单（完成后逐项过）

1. 模块顺序与需求文档ASCII线框一致，无缺模块
2. AI标识、免责声明在场（运势/对话/情绪页）
3. 吉凶宜忌语义色正确（绿宜红忌）
4. 单文件无外部依赖可独立打开
5. 与其他页面共用同一套tokens（拷贝同一段:root）
