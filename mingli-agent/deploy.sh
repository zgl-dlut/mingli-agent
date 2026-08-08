#!/bin/bash
set -e

DOMAIN="shisuansuan.com"
SERVER_IP="39.96.47.33"
PROJECT_DIR="/opt/mingli-agent"
USER="root"

echo "======================================"
echo "  趣算算项目一键部署脚本"
echo "  Domain: $DOMAIN"
echo "  Server: $SERVER_IP"
echo "======================================"

echo ""
echo "【1/5】安装系统依赖..."
ssh $USER@$SERVER_IP "
  apt update && apt upgrade -y
  apt install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx
  systemctl enable docker && systemctl start docker
  systemctl enable nginx && systemctl start nginx
"

echo ""
echo "【2/5】创建项目目录..."
ssh $USER@$SERVER_IP "
  mkdir -p $PROJECT_DIR
  mkdir -p /etc/nginx/sites-available
  mkdir -p /etc/nginx/sites-enabled
"

echo ""
echo "【3/5】上传项目文件..."
scp -r ./* $USER@$SERVER_IP:$PROJECT_DIR/

echo ""
echo "【4/5】配置 Nginx..."
ssh $USER@$SERVER_IP "
  rm -f /etc/nginx/sites-enabled/default
  ln -sf $PROJECT_DIR/nginx.conf /etc/nginx/sites-enabled/mingli-agent
  nginx -t && systemctl reload nginx
"

echo ""
echo "【5/5】启动 Docker 服务..."
ssh $USER@$SERVER_IP "
  cd $PROJECT_DIR
  docker compose -f docker-compose.prod.yml up -d
"

echo ""
echo "======================================"
echo "  部署完成！"
echo ""
echo "  访问地址: http://$SERVER_IP:3000"
echo "  或: http://$DOMAIN (备案完成后)"
echo ""
echo "  查看日志: docker compose -f docker-compose.prod.yml logs -f"
echo "  停止服务: docker compose -f docker-compose.prod.yml down"
echo "======================================"