# 命理Agent开发计划

## 1. 项目概述

构建一个Web版命理Agent，**移动端优先**，用户输入出生年月日时分、出生地（经纬度）、性别后，系统同时进行：
- **中国传统命理（八字）排盘**：计算四柱、十神、五行、大运等
- **西方占星术星盘**：计算行星位置、宫位、相位等
- **AI综合解读**：将两种命理数据输入大模型，生成详细的性格、事业、婚姻、运势等文字解读报告
- **多轮对话追问**：用户首次生成整体运势后，可继续追问流年运势、事业、财运、感情等具体问题，AI基于完整命盘上下文进行深度拆解回复
- **多生辰管理**：用户可添加多个生辰，每个生辰对应一个人，每个人是一个独立对话框

**计费规则**：首次一次性生成为160积分，1元=10积分，后续一次追问为40积分（不限一次追问的问题数量）；支持充值：40、80、120、160、200积分，支持微信、支付宝支付。

## 2. 当前状态分析

- 工作目录为空，从零开始搭建
- 无现有代码、配置或依赖
- 需完整建立前后端分离的Web应用架构

## 3. 技术架构

### 3.1 整体架构
```
┌──────────────────────────────────────────────────────────────────┐
│                          前端 (React SPA)                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  信息录入表单  │  │ 命盘可视化展示  │  │  对话式AI解读区         │  │
│  │ (出生信息输入) │  │(八字表格+SVG   │  │  ·首次: 整体运势报告    │  │
│  │             │  │ 星盘)         │  │  ·追问: 流年/事业/财运   │  │
│  └─────────────┘  └──────────────┘  │  ·多轮对话+Markdown渲染  │  │
│                                     └────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              │ REST API + SSE (流式输出)
┌──────────────────────────────────────────────────────────────────┐
│                       后端 (Python FastAPI)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │   认证模块    │  │  命理计算服务   │  │   对话式AI解读服务      │  │
│  │(JWT登录注册)  │  │(八字+占星排盘)  │  │ ·System Prompt注入命盘  │  │
│  └─────────────┘  └──────────────┘  │ ·多轮对话上下文管理       │  │
│  ┌─────────────┐  ┌──────────────┐  │ ·话题意图识别+追问引导    │  │
│  │  付费/计费模块 │  │   用户管理     │  │ ·流式SSE输出           │  │
│  │(预留接口+计数) │  │(会话历史记录)  │  └────────────────────────┘  │
│  └─────────────┘  └──────────────┘                                 │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────────┐
│                         数据层                                    │
│            PostgreSQL (用户、会话、消息、订单)                      │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 技术栈选型

| 层级 | 技术 | 选型理由 |
|------|------|----------|
| 前端框架 | React 18 + TypeScript | 生态成熟，类型安全，组件化开发，支持移动端响应式 |
| 前端样式 | Tailwind CSS | 原子化CSS，快速构建美观UI，内置移动端响应式支持 |
| 前端路由 | React Router v6 | SPA路由管理，支持移动端导航 |
| 命盘可视化 | SVG (原生) + HTML/CSS | 八字盘用表格/网格，星盘用SVG绘制圆形图，适配移动端 |
| 状态管理 | Zustand | 轻量，适合中小规模状态 |
| 后端框架 | FastAPI (Python) | 高性能异步框架，自动生成OpenAPI文档 |
| 八字计算 | 自研 + 参考 `china-testing/bazi` | 八字规则固定，自研可控且避免额外依赖 |
| 占星计算 | `flatlib` + `pyswisseph` | 活跃维护（2026年更新），基于权威瑞士星历 |
| AI解读 | OpenAI API (GPT-4o) 或兼容接口 | 强大的中文理解和命理知识，支持多轮对话 |
| 对话上下文 | 后端Session + DB存储 | 每个会话关联命盘数据，持久化对话历史 |
| 支付接口 | 微信支付API + 支付宝API | 主流支付方式，支持积分充值 |
| 数据库 | PostgreSQL | 关系型数据，支持JSON字段存储复杂命盘数据 |
| ORM | SQLAlchemy 2.0 | Python标准ORM |
| 迁移工具 | Alembic | 数据库版本管理 |
| 部署 | Docker + Docker Compose | 一键启动，环境一致 |

## 4. 详细实施步骤

### Phase 1: 项目脚手架搭建（第1阶段）

**4.1.1 目录结构初始化**
```
mingli-agent/
├── backend/                 # FastAPI后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # 应用入口
│   │   ├── config.py        # 配置管理
│   │   ├── api/             # API路由
│   │   │   ├── auth.py      # 认证相关
│   │   │   ├── bazi.py      # 八字计算接口
│   │   │   ├── astrology.py # 占星计算接口
│   │   │   ├── chat.py      # 对话式解读接口（多轮对话）
│   │   │   ├── payment.py   # 支付与积分接口
│   │   │   └── user.py      # 用户相关
│   │   ├── services/        # 业务逻辑层
│   │   │   ├── bazi_service.py
│   │   │   ├── astrology_service.py
│   │   │   ├── ai_service.py      # AI解读核心（含对话管理）
│   │   │   ├── prompt_builder.py  # Prompt构建与命盘数据注入
│   │   │   ├── payment_service.py # 支付处理与积分管理
│   │   │   └── wechat_pay.py      # 微信支付对接
│   │   │   └── alipay_pay.py      # 支付宝对接
│   │   ├── models/          # 数据模型
│   │   │   ├── user.py      # 用户模型（含积分字段）
│   │   │   ├── person.py    # 人物模型（一个人物=一个生辰+一个对话框）
│   │   │   ├── session.py   # 会话模型（关联人物和命盘数据）
│   │   │   ├── message.py   # 消息模型（对话历史）
│   │   │   ├── order.py     # 订单模型（充值订单）
│   │   │   └── transaction.py # 积分交易记录
│   │   ├── core/            # 核心工具
│   │   │   ├── security.py  # JWT/密码
│   │   │   └── exceptions.py
│   │   └── db/              # 数据库
│   │       ├── base.py
│   │       └── session.py
│   ├── alembic/             # 数据库迁移
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # React前端（移动端优先）
│   ├── src/
│   │   ├── components/      # 公共组件
│   │   │   ├── ChatWindow.tsx     # 对话窗口组件（移动端优化）
│   │   │   ├── ChatInput.tsx      # 对话输入框（移动端优化）
│   │   │   ├── ChatMessage.tsx    # 单条消息渲染（Markdown）
│   │   │   ├── BaziChart.tsx      # 八字盘组件（移动端适配）
│   │   │   ├── AstrologyChart.tsx # 星盘SVG组件（移动端适配）
│   │   │   ├── PersonList.tsx     # 人物列表组件（底部导航切换）
│   │   │   ├── PersonCard.tsx     # 人物卡片（展示生辰信息）
│   │   │   ├── AddPersonModal.tsx # 添加人物弹窗
│   │   │   └── WalletPanel.tsx    # 钱包/积分面板
│   │   ├── pages/           # 页面
│   │   │   ├── LoginPage.tsx      # 登录页（移动端优先）
│   │   │   ├── ChatPage.tsx       # 对话主页面（核心，移动端优先）
│   │   │   └── WalletPage.tsx     # 充值/钱包页面
│   │   ├── stores/          # Zustand状态
│   │   │   ├── authStore.ts       # 认证状态
│   │   │   ├── chatStore.ts       # 对话状态管理
│   │   │   ├── personStore.ts     # 人物管理状态
│   │   │   └── walletStore.ts     # 积分/钱包状态
│   │   ├── api/             # API客户端
│   │   ├── utils/           # 工具函数
│   │   ├── types/           # TypeScript类型
│   │   └── App.tsx
│   ├── public/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── README.md
```

**4.1.2 Docker环境配置**
- 创建 `docker-compose.yml`：包含后端、前端、PostgreSQL三个服务
- 后端 `Dockerfile`：基于Python 3.11，安装依赖
- 前端 `Dockerfile`：基于Node 20，构建生产包

### Phase 2: 后端核心 - 命理计算引擎（第2阶段）

**4.2.1 八字排盘服务 (`backend/app/services/bazi_service.py`)**
实现功能：
- 公历转农历，节气判定（精确到分钟）
- 年柱、月柱、日柱、时柱计算
- 天干地支、十神、五行属性判定
- 真太阳时校正（根据出生地经度计算时差）
- 大运、流年排列
- 数据结构：`BaziChart` Pydantic模型

核心算法要点：
- 年柱：以立春为界，不是农历正月初一
- 月柱：以节气（节）为界（每月第一个节气）
- 日柱：基于已知基准日推算干支
- 时柱：根据日干和出生时辰确定

**4.2.2 占星排盘服务 (`backend/app/services/astrology_service.py`)**
实现功能：
- 使用 `flatlib` 库计算本命盘
- 提取行星位置（太阳、月亮、水星、金星、火星、木星、土星、天王、海王、冥王）
- 计算12宫位及宫头星座
- 计算主要相位（合相0°、六分60°、四分90°、三分120°、对分180°）
- 上升星座、天顶星座
- 数据结构：`AstrologyChart` Pydantic模型

**4.2.3 AI对话式解读服务 (`backend/app/services/ai_service.py`)**

整体设计：将AI解读从"一次性报告生成"升级为"多轮对话式Agent"，用户首次获得整体运势后可不断追问细分话题。**不提供快捷追问按钮，用户完全自由提问。**

实现功能：
- **会话管理**：每个用户可添加多个人物，每个人物对应一个 `ChatSession`，绑定该人物的八字和占星数据
- **System Prompt构建** (`prompt_builder.py`)：将命盘数据注入System Prompt，AI在所有对话轮次中始终拥有完整命盘上下文
- **多轮对话上下文**：每次调用LLM时携带历史消息（最近N轮，防止token溢出），保持对话连贯性
- **首次消息特殊处理**：创建人物后，自动生成整体运势报告作为AI的首条回复
- **流式输出 (SSE)**：支持前端打字机效果
- **结果缓存**：相同输入直接返回缓存（仅首次整体报告）

**System Prompt设计 (`prompt_builder.py`)**：
```
你是一位精通中国传统八字命理和西方占星术的命理大师，同时也是一位耐心的对话顾问。
你正在为一位求问者进行一对一的命理解读。

【求问者基本信息】
性别：{gender}
出生时间：{birth_time}（已做真太阳时校正）
出生地：{location}（经度{lng}，纬度{lat}）

【八字排盘数据】
四柱：{bazi_pillars}
十神关系：{shishen}
五行分布：{wuxing_distribution}（金{jin} 木{mu} 水{shui} 火{huo} 土{tu}）
纳音：{nayin}
藏干：{canggan}
大运排列：{dayun_list}
当前大运：{current_dayun}
流年：{current_liunian}

【占星排盘数据】
太阳星座：{sun_sign}（{sun_degree}°）
月亮星座：{moon_sign}（{moon_degree}°）
上升星座：{ascendant}
天顶星座：{mc_sign}
行星位置：{planet_positions}
宫位分布：{house_cusps}
主要相位：{major_aspects}
元素分布：火{fire} 土{earth} 风{air} 水{water}
模式分布：开创{cardinal} 固定{fixed} 变动{mutable}

【对话规则】
1. 回答必须基于上述命盘数据，结合八字和占星两套体系进行交叉分析
2. 当两套体系的结论一致时，强调该结论的可信度；不一致时，分别说明并给出综合判断
3. 对用户的具体问题要深入拆解，不要泛泛而谈：
   - 谈事业：结合官星/10宫/6宫/土星相位等具体分析
   - 谈财运：结合财星/2宫/8宫/木星相位等具体分析
   - 谈感情：结合日支/7宫/金星火星/月亮相位等具体分析
   - 谈流年：结合大运流年/土星回归/木星过宫/日月食等具体分析
4. 语言风格：专业但亲切，避免过度恐吓，给出建设性建议
5. 如果用户问题超出命理范畴，礼貌说明并引导回命理话题
```

**对话流程设计**：
```
用户登录/注册
    │
    ▼
用户添加人物（输入姓名、性别、出生时间、出生地）
    │
    ▼
扣除160积分（余额不足提示充值）
    │
    ▼
后端排盘计算（八字+占星）
    │
    ▼
创建Person（人物）→ 创建ChatSession（绑定命盘数据）
    │
    ▼
自动触发首次对话：System Prompt注入命盘 + User Message="请为我进行整体命理解读"
    │
    ▼
AI生成整体运势报告（流式SSE输出）
    │
    ▼
前端展示报告
    │
    ▼
用户自由追问（输入框输入任意问题）
    │
    ▼
扣除40积分（余额不足提示充值）
    │
    ▼
后端加载该Session历史消息 + 新问题 → 调用LLM（流式）
    │
    ▼
AI基于完整上下文回复（始终拥有命盘数据）
    │
    ▼
循环追问...（用户可随时切换人物）
```

**多人物管理设计**：
- 用户可添加多个人物（如：自己、家人、朋友）
- 每个人物是一个独立的对话框，拥有独立的命盘数据和对话历史
- 底部导航栏切换不同人物
- 支持编辑人物信息、删除人物（需确认）

### Phase 3: 后端基础设施（第3阶段）

**4.3.1 数据库设计与建模**

表结构：
- `users`：用户表（id, email, hashed_password, name, avatar, points, created_at, updated_at）— points字段存储用户积分余额
- `persons`：人物表（id, user_id, name, gender, birth_date, birth_time, birth_location, birth_lat, birth_lng, created_at）— 一个人物=一个生辰+一个对话框
- `chat_sessions`：会话表（id, person_id, bazi_data_json, astro_data_json, title, created_at, updated_at）— 每次排盘创建一个会话，绑定命盘数据
- `chat_messages`：消息表（id, session_id, role ENUM['system','user','assistant'], content, created_at）— 存储完整对话历史
- `orders`：订单表（id, user_id, points, amount, pay_method ENUM['wechat','alipay'], status ENUM['pending','paid','failed'], trade_no, created_at, paid_at）— 充值订单
- `transactions`：积分交易记录（id, user_id, type ENUM['recharge','consume','refund'], points, order_id, description, created_at）— 积分收支流水

**4.3.2 认证与授权**
- JWT Token认证（access token + refresh token）
- 注册/登录/找回密码API
- 中间件保护需要登录的接口

**4.3.3 API路由实现**
- `POST /api/auth/register` - 注册（赠送初始积分：0）
- `POST /api/auth/login` - 登录
- `POST /api/auth/refresh` - 刷新Token
- `POST /api/bazi/calculate` - 八字排盘（无需登录）
- `POST /api/astrology/calculate` - 占星排盘（无需登录）
- `POST /api/persons` - 添加人物（扣160积分，需登录）
- `GET /api/persons` - 获取人物列表（需登录）
- `GET /api/persons/{id}` - 获取人物详情（需登录）
- `PUT /api/persons/{id}` - 更新人物信息（需登录）
- `DELETE /api/persons/{id}` - 删除人物（需登录）
- `POST /api/chat/sessions` - 创建对话会话（添加人物时自动创建）
- `GET /api/chat/sessions` - 获取用户的会话列表（需登录）
- `POST /api/chat/sessions/{id}/messages` - 发送消息/追问（扣40积分，SSE流式返回，需登录）
- `GET /api/chat/sessions/{id}/messages` - 获取会话历史消息（需登录）
- `GET /api/user/profile` - 用户信息（含积分余额，需登录）
- `POST /api/payment/orders` - 创建充值订单（需登录）
- `GET /api/payment/orders/{id}` - 查询订单状态（需登录）
- `POST /api/payment/wechat/callback` - 微信支付回调
- `POST /api/payment/alipay/callback` - 支付宝支付回调
- `GET /api/transactions` - 获取积分交易记录（需登录）

**4.3.4 付费模块设计（积分系统）**

**积分规则**：
- 1元 = 10积分
- 首次生成整体运势：扣除 **160积分**（约16元）
- 每次追问：扣除 **40积分**（约4元），不限一次追问的问题数量

**充值档位**：
| 积分数量 | 金额（元） |
|----------|-----------|
| 40积分 | 4元 |
| 80积分 | 8元 |
| 120积分 | 12元 |
| 160积分 | 16元 |
| 200积分 | 20元 |

**支付方式**：
- 微信支付（JSAPI/小程序支付）
- 支付宝（电脑网站支付/手机网站支付）

**支付流程**：
```
用户选择充值档位 → 创建订单 → 选择支付方式 → 跳转支付页面 → 支付回调 → 积分到账 → 记录交易
```

**积分管理**：
- `payment_service.py`：积分增减逻辑，保证事务一致性
- `transactions`表：记录每笔积分变动（充值+、消费-、退款+）
- 用户余额不足时，前端提示充值，跳转钱包页面

**接口实现**：
- `POST /api/payment/orders`：创建充值订单，返回支付链接
- `POST /api/payment/wechat/callback`：微信支付异步回调
- `POST /api/payment/alipay/callback`：支付宝异步回调
- `GET /api/transactions`：查询积分交易记录

### Phase 4: 前端开发（第4阶段）— 移动端优先

**4.4.1 页面实现**

1. **登录页 (`LoginPage.tsx`)** — 移动端优先设计
   - 全屏登录/注册表单，适配手机竖屏
   - 邮箱+密码登录
   - 注册表单（邮箱、密码、昵称）
   - 底部显示积分规则说明

2. **对话主页面 (`ChatPage.tsx`)** — 核心页面，移动端优先三栏布局
   - **顶部栏**：当前人物信息（姓名、八字简览）、返回按钮、积分余额显示
   - **左侧面板**（可折叠抽屉）：人物列表
     - `PersonList`组件：展示所有人物卡片
     - 点击切换人物
     - "添加人物"按钮（弹出`AddPersonModal`）
   - **右侧主区域**：对话式AI解读
     - `ChatWindow`组件：滚动式消息列表（移动端优化，滑动流畅）
     - AI首条消息：整体运势报告（Markdown渲染，支持折叠展开）
     - 用户追问消息：自由输入（`ChatInput`组件）
     - AI追问回复：基于上下文的深度拆解（Markdown渲染+流式打字效果）
   - **底部导航**：切换人物按钮（移动端）、积分按钮（跳转钱包）

3. **钱包页面 (`WalletPage.tsx`)** — 移动端优先
   - 当前积分余额大字体展示
   - 充值档位选择（40/80/120/160/200积分）
   - 支付方式选择（微信/支付宝）
   - 积分交易记录列表
   - 返回按钮

4. **添加人物弹窗 (`AddPersonModal.tsx`)**
   - 姓名输入
   - 性别选择
   - 出生日期时间选择器（精确到分钟，移动端友好）
   - 出生地输入（带地理编码）
   - 确认按钮（显示扣除160积分提示）

**4.4.2 命盘可视化细节**

- 八字盘：使用CSS Grid布局，清晰展示四柱+藏干+十神
- 星盘SVG：
  - 外圈：12宫位刻度
  - 中圈：黄道十二宫符号
  - 内圈：行星位置（使用天文符号）
  - 相位线：用不同颜色虚线连接有相位的行星
  - 响应式设计，适配移动端

**4.4.3 API客户端**
- 封装 `fetch` 或 `axios`
- 自动携带JWT Token
- 统一错误处理

### Phase 5: 集成与优化（第5阶段）

**4.5.1 联调测试**
- 端到端测试：输入 → 排盘 → 可视化 → AI解读
- 边界测试：闰年、节气交界时刻、不同经纬度
- 性能测试：AI解读接口响应时间

**4.5.2 安全性**
- 后端CORS配置
- 前端敏感信息（API Key）不暴露，所有AI调用走后端
- SQL注入防护（ORM参数化查询）
- Rate Limiting（API限流）

**4.5.3 部署配置**
- `docker-compose.yml` 一键启动
- 环境变量管理（`.env`）
- Nginx反向代理配置（预留）

## 5. 核心依赖清单

### 后端 (`requirements.txt`)
```
fastapi==0.111.*
uvicorn[standard]==0.30.*
sqlalchemy==2.0.*
alembic==1.13.*
psycopg2-binary==2.9.*
pydantic==2.7.*
pydantic-settings==2.3.*
python-jose[cryptography]==3.3.*
passlib[bcrypt]==1.7.*
python-multipart==0.0.*
httpx==0.27.*
openai==1.35.*
flatlib==0.2.*
pyswisseph==2.10.*
python-dateutil==2.9.*
ephem==4.1.*
```

### 前端 (`package.json` 核心依赖)
```json
{
  "react": "^18.3.0",
  "react-dom": "^18.3.0",
  "react-router-dom": "^6.24.0",
  "typescript": "^5.5.0",
  "tailwindcss": "^3.4.0",
  "zustand": "^4.5.0",
  "react-markdown": "^9.0.0",
  "remark-gfm": "^4.0.0",
  "axios": "^1.7.0",
  "date-fns": "^3.6.0"
}
```

## 6. 验证步骤

1. **八字计算验证**：
   - 输入已知八字的出生时间，验证四柱是否与万年历一致
   - 测试节气交界日（如立春前后）的年柱切换
   - 测试真太阳时（新疆 vs 北京）

2. **占星计算验证**：
   - 与专业占星软件（如Astro.com）对比同一出生数据的星盘
   - 验证行星位置误差 < 1角分
   - 验证宫位系统（Placidus）

3. **AI对话验证**：
   - 检查首次回复是否同时引用了八字和占星数据
   - 验证追问时AI是否保持命盘上下文（追问"我的事业"应引用具体星盘数据）
   - 验证流式输出正常
   - 测试长对话（10轮+）上下文不丢失
   - 测试AI对不同话题（流年/事业/财运/感情）的深度拆解质量
   - 验证无快捷追问按钮，用户完全自由提问

4. **多人物管理验证**：
   - 添加多个人物（自己、家人）
   - 每个人物有独立的命盘和对话历史
   - 切换人物后对话正确切换
   - 编辑/删除人物功能正常

5. **积分系统验证**：
   - 添加人物扣除160积分
   - 每次追问扣除40积分
   - 积分不足时提示充值
   - 充值订单创建正确
   - 支付回调后积分到账正确
   - 积分交易记录完整

6. **支付接口验证**：
   - 微信支付流程完整
   - 支付宝支付流程完整
   - 支付成功后积分自动到账
   - 支付失败订单状态正确

7. **移动端验证**：
   - 所有页面适配手机竖屏
   - 触摸交互流畅
   - 输入框键盘弹出正常
   - 消息列表滑动流畅

8. **端到端验证**：
   - 登录 → 添加人物（扣积分）→ 排盘 → AI解读 → 追问（扣积分）→ 充值 → 继续追问 完整流程
   - 历史人物可从列表恢复继续对话
