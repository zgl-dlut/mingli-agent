# 微信支付接入与 qusuansuan.com 部署计划

## 需求总结

1. **微信支付 AppID 热切换**：AppID 申请好后只需改 `.env` + 重启后端，无需重新发布代码（当前已支持）
2. **固定手机号充值**：后台管理页面新增充值功能，管理员输入手机号直接给对应用户充积分
3. **部署到 qusuansuan.com**：将前后端部署到远程服务器（阿里云ECS），配置 Nginx 和域名解析

---

## 一、微信支付 AppID 热切换（无需改动代码）

### 当前状态
- `_wechat_configured()` 已检查 `WECHAT_APP_ID` 是否为真实值
- `.env` 中 `WECHAT_APP_ID=your-wechat-app-id` 是占位符
- 未配置时自动降级为 mock 模式

### 生效步骤（AppID 申请好后）
1. 编辑 `.env`，将 `WECHAT_APP_ID=your-wechat-app-id` 改为真实 AppID
2. 重启后端服务（`uvicorn --reload` 不监听 `.env`，需手动重启）
3. 真实支付自动生效，前端无需改动

### 验证方式
- 前端点击充值 → 应返回 `mock: false` + 微信支付参数
- 后端日志应显示 `[payment] 微信支付已配置，订单 xxx 走真实支付`

---

## 二、固定手机号充值功能（后台管理）

### 2.1 后端 API

**文件**：`backend/app/api/admin.py`（或新建路由）

新增接口：`POST /api/admin/recharge-by-phone`

```python
class RechargeByPhoneRequest(BaseModel):
    phone: str          # 用户手机号
    points: int         # 充值积分数
    remark: str = ""    # 备注

@router.post("/recharge-by-phone")
async def recharge_by_phone(
    body: RechargeByPhoneRequest,
    db: AsyncSession,
    current_admin: User,  # 需管理员权限
):
    # 1. 根据手机号查找用户
    # 2. 创建订单记录（biz_type='admin_recharge'）
    # 3. 直接给用户加积分
    # 4. 写交易流水
    # 5. 返回结果
```

**文件**：`backend/app/services/payment_service.py`

新增函数 `admin_recharge_points()`：
- 查找用户（按手机号）
- 创建订单（status='paid'，trade_no='ADMIN_时间戳'）
- 增加用户积分
- 写入 transactions 表（biz_type='admin_recharge'）
- 记录 ai_usage_logs（可选）

### 2.2 前端页面

**文件**：`frontend/src/pages/AdminRechargePage.tsx`（新建）

功能：
- 输入手机号（带格式校验）
- 输入充值积分数
- 输入备注（可选）
- 提交按钮
- 显示充值结果/错误信息
- 最近充值记录列表（可选）

**路由**：`/admin/recharge`

**导航**：在 `AdminNav.tsx` 中添加"积分充值"入口

### 2.3 涉及文件清单

| 文件 | 改动 |
|------|------|
| `backend/app/api/admin.py` | 新增 `/recharge-by-phone` 接口 |
| `backend/app/services/payment_service.py` | 新增 `admin_recharge_points()` 函数 |
| `frontend/src/pages/AdminRechargePage.tsx` | 新建充值页面 |
| `frontend/src/api/admin.ts` | 新增 `rechargeByPhone()` API 调用 |
| `frontend/src/App.tsx` | 新增路由 `/admin/recharge` |
| `frontend/src/components/AdminNav.tsx` | 新增导航入口 |

---

## 三、部署到 qusuansuan.com（远程服务器）

### 3.1 服务器环境准备

**需要安装的软件**：
- Python 3.9+
- PostgreSQL 14+
- Nginx
- Node.js 18+（用于前端构建）
- PM2 或 systemd（后端进程管理）

### 3.2 代码部署

**步骤**：
1. 将项目代码推送到 Git 仓库（GitHub/Gitee）
2. 在服务器上 `git clone` 拉取代码
3. 配置 `.env` 文件（数据库连接、域名等）
4. 安装后端依赖：`pip install -r requirements.txt`
5. 构建前端：`cd frontend && npm install && npm run build`
6. 运行数据库迁移：`alembic upgrade head`

### 3.3 Nginx 配置

**文件**：`nginx.conf`（需修改域名）

将 `shisuansuan.com` 和 `admin.shisuansuan.com` 改为 `qusuansuan.com` 和 `admin.qusuansuan.com`：

```nginx
# 用户前端
server {
    listen 80;
    server_name qusuansuan.com www.qusuansuan.com;
    # ... 其他配置不变
}

# 后台管理
server {
    listen 80;
    server_name admin.qusuansuan.com;
    # ... 其他配置不变
}
```

**静态资源路径**：
- 前端构建产物：`/opt/qusuansuan/frontend/dist`
- 后端代码：`/opt/qusuansuan/backend`

### 3.4 域名解析

在域名服务商（如阿里云）添加 DNS 记录：

| 主机记录 | 记录类型 | 记录值 |
|---------|---------|--------|
| @ | A | 服务器公网IP |
| www | A | 服务器公网IP |
| admin | A | 服务器公网IP |

### 3.5 HTTPS 配置（推荐）

使用 Let's Encrypt 免费证书：
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d qusuansuan.com -d www.qusuansuan.com -d admin.qusuansuan.com
```

### 3.6 后端进程管理

使用 PM2：
```bash
cd /opt/qusuansuan/backend
source venv/bin/activate
pm2 start "uvicorn app.main:app --host 0.0.0.0 --port 8000" --name mingli-backend
pm2 save
pm2 startup
```

或使用 systemd 服务（更稳定）。

### 3.7 微信支付回调地址

`.env` 中需要更新：
```
WECHAT_NOTIFY_URL=https://qusuansuan.com/api/payment/wechat/callback
```

### 3.8 涉及文件清单

| 文件 | 改动 |
|------|------|
| `nginx.conf` | 域名从 shisuansuan.com 改为 qusuansuan.com |
| `backend/.env` | 更新 WECHAT_NOTIFY_URL 域名 |
| 服务器部署脚本 | 新建（可选） |

---

## 四、实施顺序

### 第一阶段：固定手机号充值功能
1. 后端新增 `admin_recharge_points()` 函数
2. 后端新增 `/api/admin/recharge-by-phone` 接口
3. 前端新建 `AdminRechargePage.tsx`
4. 前端 API 客户端新增方法
5. 前端路由和导航配置
6. 测试验证

### 第二阶段：qusuansuan.com 部署
1. 修改 `nginx.conf` 域名
2. 修改 `.env` 回调地址
3. 准备服务器环境
4. 代码部署到服务器
5. 配置域名解析
6. 配置 HTTPS
7. 启动服务并验证

### 第三阶段：微信支付 AppID 生效
1. 在服务器上编辑 `.env` 填入真实 AppID
2. 重启后端服务
3. 测试真实支付流程

---

## 五、验证步骤

### 固定手机号充值
1. 访问 `http://qusuansuan.com/admin/recharge`
2. 输入已注册手机号和积分数
3. 提交后检查用户积分是否增加
4. 检查交易流水记录

### 部署验证
1. 访问 `http://qusuansuan.com` 前端正常
2. 访问 `http://admin.qusuansuan.com` 后台正常（需 Basic Auth）
3. API 接口正常响应
4. 微信支付回调正常

### 微信支付验证
1. 前端点击充值 → 返回 `mock: false`
2. 完成支付 → 积分到账
3. 检查订单记录

---

## 六、风险点

1. **服务器安全**：需配置防火墙、SSH 密钥登录、定期更新
2. **数据库备份**：需配置定时备份策略
3. **微信支付证书安全**：证书文件权限设为 600，避免泄露
4. **域名备案**：国内服务器需要 ICP 备案
5. **HTTPS 证书续期**：Let's Encrypt 证书 90 天过期，需配置自动续期
