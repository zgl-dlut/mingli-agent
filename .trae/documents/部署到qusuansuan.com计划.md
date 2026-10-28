# 部署到 qusuansuan.com 完整计划

## 当前状态

- **服务器**: 39.96.47.33 (root@39.96.47.33)
- **项目目录**: /opt/mingli-agent
- **当前域名**: shisuansuan.com
- **目标域名**: qusuansuan.com
- **部署方式**: Docker Compose + Nginx

---

## 第一步：修改本地配置文件

### 1.1 修改 nginx.conf

**文件**: `mingli-agent/nginx.conf`

将所有 `shisuansuan.com` 改为 `qusuansuan.com`：

```nginx
# 用户前端 - 主域名
server {
    listen 80;
    server_name qusuansuan.com www.qusuansuan.com;
    # ... 其他配置不变
}

# 后台管理 - 独立子域名
server {
    listen 80;
    server_name admin.qusuansuan.com;
    # ... 其他配置不变
}
```

### 1.2 修改 deploy.sh

**文件**: `mingli-agent/deploy.sh`

```bash
DOMAIN="qusuansuan.com"
SERVER_IP="39.96.47.33"
```

### 1.3 修改 .env 文件

**文件**: `mingli-agent/backend/.env`

更新微信支付回调地址：
```bash
WECHAT_NOTIFY_URL=https://qusuansuan.com/api/payment/wechat/callback
```

---

## 第二步：服务器环境准备

### 2.1 SSH 登录服务器

```bash
ssh root@39.96.47.33
```

### 2.2 安装必要软件（如果还没安装）

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Docker
apt install -y docker.io docker-compose-plugin

# 启动 Docker
systemctl enable docker && systemctl start docker

# 安装 Nginx
apt install -y nginx
systemctl enable nginx && systemctl start nginx

# 安装 Certbot（HTTPS 证书）
apt install -y certbot python3-certbot-nginx
```

### 2.3 创建项目目录

```bash
mkdir -p /opt/mingli-agent
```

---

## 第三步：配置 systemd 服务（自动启动）

### 3.1 创建后端服务文件

**文件**: `/etc/systemd/system/mingli-backend.service`

```ini
[Unit]
Description=趣算算后端服务
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mingli-agent/backend
ExecStart=/opt/mingli-agent/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
ExecStop=/bin/kill -SIGTERM $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 3.2 创建前端服务文件

**文件**: `/etc/systemd/system/mingli-frontend.service`

```ini
[Unit]
Description=趣算算前端服务
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mingli-agent/frontend
ExecStart=/usr/bin/npm run start -- --host 0.0.0.0 --port 3000
ExecStop=/bin/kill -SIGTERM $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 3.3 启用服务

```bash
# 重新加载 systemd
systemctl daemon-reload

# 启用并启动服务
systemctl enable mingli-backend
systemctl enable mingli-frontend

systemctl start mingli-backend
systemctl start mingli-frontend

# 查看状态
systemctl status mingli-backend
systemctl status mingli-frontend
```

---

## 第四步：配置 Nginx

### 4.1 上传 nginx.conf

```bash
# 从本地上传
scp mingli-agent/nginx.conf root@39.96.47.33:/opt/mingli-agent/nginx.conf

# 在服务器上创建软链接
ssh root@39.96.47.33 "
  rm -f /etc/nginx/sites-enabled/default
  ln -sf /opt/mingli-agent/nginx.conf /etc/nginx/sites-enabled/mingli-agent
  nginx -t && systemctl reload nginx
"
```

### 4.2 配置 HTTPS（推荐）

```bash
# 申请证书
certbot --nginx -d qusuansuan.com -d www.qusuansuan.com -d admin.qusuansuan.com

# 自动续期（已默认配置）
certbot renew --dry-run
```

---

## 第五步：域名解析

在阿里云域名控制台添加 DNS 记录：

| 主机记录 | 记录类型 | 记录值 |
|---------|---------|--------|
| @ | A | 39.96.47.33 |
| www | A | 39.96.47.33 |
| admin | A | 39.96.47.33 |

---

## 第六步：部署代码

### 6.1 方式一：使用 deploy.sh（推荐）

```bash
# 在本地执行
cd mingli-agent
chmod +x deploy.sh
./deploy.sh
```

### 6.2 方式二：手动部署

```bash
# 上传代码
scp -r ./* root@39.96.47.33:/opt/mingli-agent/

# 在服务器上构建前端
ssh root@39.96.47.33 "
  cd /opt/mingli-agent/frontend
  npm install
  npm run build
"

# 在服务器上安装后端依赖
ssh root@39.96.47.33 "
  cd /opt/mingli-agent/backend
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
"

# 运行数据库迁移
ssh root@39.96.47.33 "
  cd /opt/mingli-agent/backend
  source venv/bin/activate
  alembic upgrade head
"
```

---

## 第七步：配置微信支付证书

```bash
# 上传证书文件
scp backend/certs/apiclient_cert.pem root@39.96.47.33:/opt/mingli-agent/backend/certs/
scp backend/certs/apiclient_key.pem root@39.96.47.33:/opt/mingli-agent/backend/certs/

# 设置权限
ssh root@39.96.47.33 "
  chmod 600 /opt/mingli-agent/backend/certs/*.pem
  chown root:root /opt/mingli-agent/backend/certs/*.pem
"
```

---

## 第八步：验证部署

### 8.1 检查服务状态

```bash
# 后端服务
ssh root@39.96.47.33 "systemctl status mingli-backend"

# 前端服务
ssh root@39.96.47.33 "systemctl status mingli-frontend"

# Nginx
ssh root@39.96.47.33 "systemctl status nginx"
```

### 8.2 访问测试

- 用户端: http://qusuansuan.com
- 管理端: http://admin.qusuansuan.com
- API 测试: http://qusuansuan.com/api/health

### 8.3 查看日志

```bash
# 后端日志
ssh root@39.96.47.33 "journalctl -u mingli-backend -f"

# 前端日志
ssh root@39.96.47.33 "journalctl -u mingli-frontend -f"

# Nginx 日志
ssh root@39.96.47.33 "tail -f /var/log/nginx/access.log"
```

---

## 第九步：配置自动备份（可选但推荐）

### 9.1 创建备份脚本

**文件**: `/opt/mingli-agent/backup.sh`

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/mingli-agent"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 备份数据库
pg_dump -U postgres mingli > $BACKUP_DIR/db_$DATE.sql

# 备份代码
tar -czf $BACKUP_DIR/code_$DATE.tar.gz /opt/mingli-agent

# 删除 7 天前的备份
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

### 9.2 设置定时任务

```bash
# 编辑 crontab
crontab -e

# 添加每天凌晨 3 点备份
0 3 * * * /opt/mingli-agent/backup.sh >> /var/log/mingli-backup.log 2>&1
```

---

## 快速操作命令

### 重启服务

```bash
ssh root@39.96.47.33 "
  systemctl restart mingli-backend
  systemctl restart mingli-frontend
  systemctl reload nginx
"
```

### 查看实时日志

```bash
# 后端
ssh root@39.96.47.33 "journalctl -u mingli-backend -f --since '10 minutes ago'"

# Nginx 访问日志
ssh root@39.96.47.33 "tail -f /var/log/nginx/access.log"

# Nginx 错误日志
ssh root@39.96.47.33 "tail -f /var/log/nginx/error.log"
```

### 更新代码

```bash
# 方式一：使用 deploy.sh
./deploy.sh

# 方式二：手动更新
scp -r ./* root@39.96.47.33:/opt/mingli-agent/
ssh root@39.96.47.33 "
  cd /opt/mingli-agent/frontend
  npm install && npm run build
  systemctl restart mingli-frontend
"
```

---

## 故障排查

### 问题 1：服务无法启动

```bash
# 查看详细错误
journalctl -u mingli-backend -n 100 --no-pager

# 检查端口占用
netstat -tlnp | grep 8000
netstat -tlnp | grep 3000
```

### 问题 2：Nginx 502 错误

```bash
# 检查后端是否运行
curl http://localhost:8000/api/health

# 检查 Nginx 配置
nginx -t

# 查看 Nginx 错误日志
tail -f /var/log/nginx/error.log
```

### 问题 3：域名无法访问

```bash
# 检查 DNS 解析
nslookup qusuansuan.com

# 检查防火墙
ufw status

# 开放端口
ufw allow 80
ufw allow 443
```

---

## 验证清单

- [ ] nginx.conf 域名已改为 qusuansuan.com
- [ ] deploy.sh 域名已更新
- [ ] .env 中 WECHAT_NOTIFY_URL 已更新
- [ ] 服务器软件已安装（Docker、Nginx、Certbot）
- [ ] systemd 服务已创建并启用
- [ ] Nginx 配置已上传并生效
- [ ] 域名 DNS 解析已配置
- [ ] HTTPS 证书已申请
- [ ] 微信支付证书已上传
- [ ] 服务正常运行
- [ ] 用户端可访问
- [ ] 管理端可访问
- [ ] API 接口正常
- [ ] 自动备份已配置

---

## V3 MVP 发布增量（2026-10-28）

### 发布前备份与迁移

```bash
# 1. 备份生产数据库
mysqldump --single-transaction --routines --triggers \
  -u "$DB_USER" -p "$DB_NAME" > "backup_before_v3_$(date +%Y%m%d_%H%M%S).sql"

# 2. 确认唯一 head
PYTHONPATH=. alembic heads
# 预期：013_v3_persona (head)

# 3. 执行迁移
PYTHONPATH=. alembic upgrade 013_v3_persona
```

不要从 revision 001 重跑历史迁移，也不要在生产自动执行 downgrade。需要回退时关闭开关并恢复应用版本；只有确认无新增 V3 用户数据时才考虑数据库恢复。

### 首次灰度环境变量

```dotenv
V3_ENABLED=false
PERSONA_ENABLED=false
OTHER_PERSONA_ENABLED=false
POINTS_RECHARGE_ENABLED=false
SUBSCRIPTION_MOCK_ENABLED=false
```

内部测试阶段只对独立测试环境启用：

```dotenv
V3_ENABLED=true
PERSONA_ENABLED=true
SUBSCRIPTION_MOCK_ENABLED=true
```

生产灰度顺序：

1. 部署代码和 011–013 迁移，保持 `V3_ENABLED=false`。
2. 验证 `/api/features`、旧聊天、旧报告和历史积分。
3. 内部账号环境开启 `V3_ENABLED=true`。
4. 观察报告失败率、用量计数、安全事件和数据库连接。
5. 再开启 `PERSONA_ENABLED=true`；`OTHER_PERSONA_ENABLED` 保持关闭。
6. 模拟订阅验收结束后关闭 `SUBSCRIPTION_MOCK_ENABLED`。

### V3 验证命令

```bash
curl -s https://qusuansuan.com/api/features
curl -s https://qusuansuan.com/

cd frontend
npm run typecheck
npm test -- --run
npm run build
npm run e2e

cd ../backend
python -m pytest tests/v3 -q
```

### V3 发布检查

- [ ] 数据库已备份，Alembic 为 `013_v3_persona`
- [ ] `V3_ENABLED` 与 `PERSONA_ENABLED` 按灰度阶段配置
- [ ] 生产环境 `SUBSCRIPTION_MOCK_ENABLED=false`
- [ ] 生产环境 `POINTS_RECHARGE_ENABLED=false`
- [ ] 旧 `/chat/:personId` 可重定向且历史消息可见
- [ ] 账号注销会删除报告、人格、记忆、会话和安全事件
- [ ] 390、430、1440 三视口 E2E 截图无溢出
