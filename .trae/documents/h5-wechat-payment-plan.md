# H5 适配 + 微信支付接入 实施计划

## 摘要

将当前命理推算应用改造为 H5 移动端形态（微信内置浏览器 + 普通手机浏览器均可使用），并接入微信支付（JSAPI + H5 双模式自动切换）。同时将前端 AI 对话从 Mock 切换到真实 Qwen-3.6-Flash 模型。

## 现状分析

### 前端
- **已有移动端基础**：`index.html` 已设置 `viewport`（禁止缩放），布局使用 `max-w-sm`、`BottomNav` 等移动端组件
- **但非完整 H5**：缺少微信 JS-SDK 引入、微信环境检测、微信 OAuth 登录、微信支付 JSAPI 调起能力
- **AI 对话使用 Mock**：`Chat.tsx` 调用 `streamMockReply`（硬编码文本），未使用已封装好的 `chatApi` SSE 接口
- **充值页面是纯模拟**：`Recharge.tsx` 的 `handleRecharge` 用 `setTimeout` 模拟支付，未调用后端

### 后端
- **AI 服务已完整**：`ai_service.py` 使用 OpenAI SDK，硬编码 `gpt-4o`，只需改 base_url/model/api_key 即可切换 Qwen
- **Chat API 已完整**：`chat.py` 提供 SSE 流式接口（`first-reading` + `messages`），但依赖数据库（Session/Message 模型）
- **支付 API 是空壳**：`payment.py` 的微信回调解析逻辑不完整，`payment_service.py` 缺少实际微信支付下单能力
- **轻量入口**：`lightweight_main.py` 仅注册 bazi 路由，无 DB 无 AI 无支付
- **配置已预留**：`.env` 和 `config.py` 已有 `WECHAT_APP_ID/MCH_ID/API_KEY` 字段

### 核心断连点
1. 前端 AI 对话 → 后端真实 AI（Mock → SSE）
2. 前端充值 → 后端微信支付下单 → 微信回调 → 积分到账
3. 微信环境 → JSAPI 支付；非微信环境 → H5 支付

---

## 实施步骤

### 第一步：后端 - AI 模型切换到 Qwen-3.6-Flash

**目标**：将 `ai_service.py` 从 `gpt-4o` 切换到阿里云 DashScope 的 Qwen-3.6-Flash

**文件与改动**：

1. **`backend/.env`** — 新增配置项
   ```
   DASHSCOPE_API_KEY=sk-xxx
   AI_MODEL=qwen-3.6-flash
   AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
   ```

2. **`backend/app/config.py`** — Settings 新增字段
   ```python
   DASHSCOPE_API_KEY: str = ""
   AI_MODEL: str = "qwen-3.6-flash"
   AI_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
   ```
   将 `OPENAI_API_KEY` 改为可选（`str = ""`），兼容旧配置

3. **`backend/app/services/ai_service.py`** — 改用可配置的 client
   ```python
   client = AsyncOpenAI(
       api_key=settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY,
       base_url=settings.AI_BASE_URL or None,  # None 则用 OpenAI 默认
   )
   # model="gpt-4o" → model=settings.AI_MODEL
   ```

4. **`backend/app/lightweight_main.py`** — 新增无状态的 AI 对话端点
   - 新建 `backend/app/api/chat_lite.py`：不依赖数据库的轻量 chat 路由
   - `POST /api/chat/analyze-stream`：接收 bazi 分析数据 + 用户问题，直接调用 `build_commercial_prompt` + `generate_ai_response`，SSE 流式返回
   - 在 `lightweight_main.py` 中注册该路由
   - 这样无需数据库即可完成 AI 报告生成

---

### 第二步：前端 - AI 对话接入真实后端

**目标**：Chat.tsx 从 Mock 切换到后端 SSE 流式接口

**文件与改动**：

1. **`frontend/src/api/chat.ts`** — 新增轻量版 SSE 调用方法
   ```typescript
   // 无需认证的轻量版，直接传 bazi 数据
   analyzeStream: (data: AnalyzeStreamRequest) => {
     return fetch('/api/chat/analyze-stream', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify(data),
     })
   }
   ```

2. **`frontend/src/pages/Chat.tsx`** — 替换 Mock 为真实 SSE
   - `handleGenerateFirstReading`：调用 `chatApi.analyzeStream`（传 baziResult + isFirstReading=true），解析 SSE 流
   - `handleSend`：调用 `chatApi.analyzeStream`（传 baziResult + question），解析 SSE 流
   - 新增 SSE 解析工具函数：`parseSSEStream(response, onChunk)`
   - 保留 `streamMockReply` 作为 fallback（当后端不可用时）

3. **`frontend/src/api/bazi.ts`** — `AnalyzeRequest` 新增 `user_question` 可选字段

---

### 第三步：后端 - 微信支付服务实现

**目标**：使用 `wechatpayv3` SDK 实现微信支付下单 + 回调

**文件与改动**：

1. **`backend/requirements.txt`** — 新增依赖
   ```
   wechatpayv3
   ```

2. **`backend/.env`** — 补全微信支付配置
   ```
   WECHAT_APP_ID=wx...
   WECHAT_MCH_ID=...
   WECHAT_API_KEY=...
   WECHAT_CERT_PATH=./certs/apiclient_cert.pem
   WECHAT_KEY_PATH=./certs/apiclient_key.pem
   WECHAT_SERIAL_NO=...
   WECHAT_NOTIFY_URL=https://yourdomain.com/api/payment/wechat/callback
   ```

3. **`backend/app/config.py`** — Settings 新增字段
   ```python
   WECHAT_CERT_PATH: str | None = None
   WECHAT_KEY_PATH: str | None = None
   WECHAT_SERIAL_NO: str | None = None
   WECHAT_NOTIFY_URL: str | None = None
   ```

4. **新建 `backend/app/services/wechat_pay_service.py`** — 微信支付核心服务
   - `create_jsapi_order(user_id, points, openid)` → 返回 `prepay_id`
   - `create_h5_order(user_id, points, client_ip, user_agent)` → 返回 `h5_url`
   - `verify_and_parse_callback(body, headers)` → 验签 + 解析回调
   - 使用 `wechatpayv3` SDK 的 `WeChatPay` 类，支持异步

5. **`backend/app/api/payment.py`** — 重写支付端点
   - `POST /api/payment/create-wechat-order`：根据请求中的 `pay_type`（jsapi/h5）调用对应方法
     - JSAPI：返回 `{ prepay_id, pay_params }`（前端用 wx.requestPayment 调起）
     - H5：返回 `{ h5_url }`（前端跳转）
   - `POST /api/payment/wechat/callback`：使用 V3 验签，解析回调，更新订单状态，增加积分
   - 新增环境检测工具：前端传 `pay_type`，不由后端判断

---

### 第四步：前端 - H5 适配与微信支付对接

**目标**：页面完整 H5 化，充值页面接入微信支付

**文件与改动**：

1. **`frontend/index.html`** — 引入微信 JS-SDK
   ```html
   <script src="https://res.wx.qq.com/open/js/jweixin-1.6.0.js"></script>
   ```

2. **新建 `frontend/src/utils/wechat.ts`** — 微信环境工具
   ```typescript
   export const isWechatBrowser = /MicroMessenger/i.test(navigator.userAgent)
   export function wxConfig(jsapiTicket: string) { ... }
   export function wxChooseWXPay(payParams: any): Promise<void> { ... }
   ```

3. **`frontend/src/api/payment.ts`** — 新增微信支付 API
   ```typescript
   createWechatOrder: (data: { points: number; pay_type: 'jsapi' | 'h5' }) =>
     apiClient.post('/payment/create-wechat-order', data)
   ```

4. **`frontend/src/pages/Recharge.tsx`** — 对接真实支付
   - `handleRecharge` 改为：
     1. 调用 `createWechatOrder` 获取支付参数
     2. 微信环境：调用 `wxChooseWXPay` 调起支付
     3. 非微信环境：`window.location.href = h5_url` 跳转微信 H5 支付
   - 支付结果轮询：跳转回来后查询订单状态，成功则刷新积分
   - 保留 Mock 模式作为开发环境 fallback

5. **H5 适配细节**（各页面微调）：
   - `AddPerson.tsx`：确保表单在手机键盘弹出时不被遮挡（`scrollIntoView`）
   - `Chat.tsx`：输入框 `fixed bottom` 在 iOS Safari 上的兼容（使用 `visualViewport` API 或 `position: absolute` + `scrollIntoView`）
   - `LoginPage.tsx`：微信环境可增加"微信一键登录"按钮（OAuth2.0 静默授权，获取 openid）
   - 全局：添加 `safe-area-inset-bottom` 适配 iPhone 底部安全区

---

### 第五步：微信 OAuth 登录（可选增强）

**目标**：微信内置浏览器中支持微信一键登录

**文件与改动**：

1. **`backend/app/api/auth.py`** — 新增微信 OAuth 端点
   - `GET /api/auth/wechat-login-url`：生成微信 OAuth2.0 授权 URL
   - `GET /api/auth/wechat-callback`：接收 code，换取 openid/session_key，创建/查找用户，返回 JWT

2. **`frontend/src/pages/LoginPage.tsx`** — 微信环境显示"微信一键登录"按钮
   - 检测 `isWechatBrowser`，是则显示微信登录按钮
   - 点击跳转微信授权 → 回调到当前页面 → 自动登录

---

## 假设与决策

1. **支付模式**：采用 JSAPI + H5 双模式。前端检测环境，传 `pay_type` 给后端
2. **微信支付 SDK**：使用 `wechatpayv3`（Python 异步兼容，FastAPI 友好）
3. **AI 模型**：Qwen-3.6-Flash 通过 DashScope OpenAI 兼容接口调用，无需改 SDK
4. **轻量模式优先**：先在 `lightweight_main.py` 中实现无 DB 的 AI + 支付，降低部署门槛
5. **微信商户资质**：先实现代码框架，`.env` 中配置占位值，后续填入真实商户信息
6. **数据库**：支付订单暂用内存/文件存储，后续再接入 PostgreSQL

## 验证步骤

1. **AI 模型**：`curl -X POST /api/chat/analyze-stream` 验证 Qwen 流式返回
2. **前端 AI 对话**：在浏览器中点击"开始解读"，确认流式输出真实 AI 内容
3. **微信支付下单**：`curl -X POST /api/payment/create-wechat-order` 验证返回 prepay_id/h5_url
4. **H5 适配**：手机浏览器打开页面，验证布局、键盘、底部安全区
5. **微信环境**：微信内置浏览器打开，验证 JSAPI 支付调起
6. **端到端**：充值 → 积分到账 → 生成报告 → 追问，完整流程