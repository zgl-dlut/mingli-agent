#!/bin/bash
set -e

DOMAIN="qusuansuan.com"
SERVER_IP="39.96.47.33"
PROJECT_DIR="/opt/mingli-agent"
USER="root"

echo "======================================"
echo "  趣算算项目部署脚本"
echo "  Domain: $DOMAIN"
echo "  Server: $SERVER_IP"
echo "======================================"

echo ""
echo "【1/7】检查服务器环境..."
ssh $USER@$SERVER_IP "
  apt update -qq && apt install -y -qq docker.io docker-compose-plugin nginx > /dev/null 2>&1
  systemctl enable docker && systemctl start docker
  echo '  Docker: OK'
"

echo ""
echo "【2/7】创建项目目录..."
ssh $USER@$SERVER_IP "mkdir -p $PROJECT_DIR"

echo ""
echo "【3/7】上传项目文件（排除敏感文件）..."
rsync -avz --exclude='.env' --exclude='node_modules' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' --exclude='venv' ./ $USER@$SERVER_IP:$PROJECT_DIR/

echo ""
echo "【4/7】上传 .env 文件..."
scp backend/.env $USER@$SERVER_IP:$PROJECT_DIR/backend/.env

echo ""
echo "【5/7】Python 语法检查..."
ssh $USER@$SERVER_IP "
  cd $PROJECT_DIR
  python3 -m py_compile backend/app/services/followup_structured.py
  if [ \$? -eq 0 ]; then
    echo '  ✓ followup_structured.py 语法检查通过'
  else
    echo '  ✗ followup_structured.py 语法错误，部署终止'
    exit 1
  fi
"

echo ""
echo "【6/7】构建并启动 Docker 服务..."
ssh $USER@$SERVER_IP "
  cd $PROJECT_DIR

  # 停止旧容器
  docker compose -f docker-compose.prod.yml down 2>/dev/null || true

  # 构建镜像
  docker compose -f docker-compose.prod.yml build

  # 启动服务
  docker compose -f docker-compose.prod.yml up -d

  echo ''
  echo '  容器状态:'
  docker compose -f docker-compose.prod.yml ps
"

echo ""
echo "【6/6】验证部署..."
sleep 5
ssh $USER@$SERVER_IP "
  echo '  Nginx 配置测试:'
  docker exec mingli-nginx nginx -t 2>&1

  echo ''
  echo '  后端健康检查:'
  curl -s -o /dev/null -w '  HTTP %{http_code}' http://localhost:8000/api/health || echo '  (后端未就绪，请稍后检查)'

  echo ''
  echo ''
  echo '  容器日志（最近 10 行）:'
  docker compose -f docker-compose.prod.yml logs --tail=10
"

echo ""
echo "======================================"
echo "  部署完成！"
echo ""
echo "  访问地址:"
echo "  - 用户端: http://$DOMAIN"
echo "  - 管理端: http://admin.$DOMAIN"
echo "  - 直接IP: http://$SERVER_IP"
echo ""
echo "  后台管理账号: admin"
echo "  后台管理密码: admin123"
echo ""
echo "  查看日志: ssh $USER@$SERVER_IP 'cd $PROJECT_DIR && docker compose logs -f'"
echo "  重启服务: ssh $USER@$SERVER_IP 'cd $PROJECT_DIR && docker compose restart'"
echo "======================================"
