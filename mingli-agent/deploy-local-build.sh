#!/bin/bash

# 本地构建并部署到服务器脚本
# 使用方法: ./deploy-local-build.sh

set -e  # 遇到错误立即退出

# 配置变量
SERVER_IP="39.96.47.33"
SERVER_USER="root"
REMOTE_DIR="/opt/mingli-agent"
IMAGE_NAME="mingli-backend"
IMAGE_TAG="latest"
LOCAL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
EXPORT_FILE="backend-image.tar.gz"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的信息
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# 检查必要工具
check_requirements() {
    info "检查必要工具..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker 未安装，请先安装 Docker Desktop"
    fi
    
    if ! command -v ssh &> /dev/null; then
        error "SSH 未安装"
    fi
    
    if ! command -v scp &> /dev/null; then
        error "SCP 未安装"
    fi
    
    info "✓ 所有必要工具已安装"
}

# 测试服务器连接
test_connection() {
    info "测试服务器连接..."
    
    if ! ssh -o ConnectTimeout=10 -o BatchMode=yes ${SERVER_USER}@${SERVER_IP} "echo 'connected'" &> /dev/null; then
        error "无法连接到服务器 ${SERVER_IP}，请检查网络和 SSH 配置"
    fi
    
    info "✓ 服务器连接正常"
}

# 本地构建镜像
build_image() {
    info "开始在本地构建 Docker 镜像..."
    
    cd "$(dirname "$0")"
    
    # 构建镜像
    if ! docker build -t ${LOCAL_IMAGE} ./backend; then
        error "镜像构建失败"
    fi
    
    info "✓ 镜像构建成功: ${LOCAL_IMAGE}"
    
    # 显示镜像信息
    docker images ${LOCAL_IMAGE}
}

# 导出镜像
export_image() {
    info "导出镜像到文件..."
    
    if [ -f "${EXPORT_FILE}" ]; then
        warn "发现旧的导出文件，正在删除..."
        rm -f "${EXPORT_FILE}"
    fi
    
    # 导出并压缩镜像
    if ! docker save ${LOCAL_IMAGE} | gzip > "${EXPORT_FILE}"; then
        error "镜像导出失败"
    fi
    
    # 显示文件大小
    FILE_SIZE=$(du -h "${EXPORT_FILE}" | cut -f1)
    info "✓ 镜像导出成功: ${EXPORT_FILE} (${FILE_SIZE})"
}

# 上传镜像到服务器
upload_image() {
    info "上传镜像到服务器..."
    
    # 使用 scp 上传
    if ! scp -o ConnectTimeout=30 "${EXPORT_FILE}" ${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/; then
        error "镜像上传失败"
    fi
    
    info "✓ 镜像上传成功"
}

# 在服务器上导入镜像
import_image() {
    info "在服务器上导入镜像..."
    
    ssh -o ConnectTimeout=30 ${SERVER_USER}@${SERVER_IP} << EOF
        cd ${REMOTE_DIR}
        
        # 导入镜像
        if ! docker load < ${EXPORT_FILE}; then
            echo "镜像导入失败"
            exit 1
        fi
        
        # 删除导出文件
        rm -f ${EXPORT_FILE}
        
        # 显示导入的镜像
        docker images ${LOCAL_IMAGE}
EOF
    
    if [ $? -ne 0 ]; then
        error "镜像导入失败"
    fi
    
    info "✓ 镜像导入成功"
}

# 重启服务
restart_services() {
    info "重启服务..."
    
    ssh -o ConnectTimeout=30 ${SERVER_USER}@${SERVER_IP} << EOF
        cd ${REMOTE_DIR}
        
        # 停止旧服务
        docker compose -f docker-compose.prod.yml down
        
        # 启动新服务
        docker compose -f docker-compose.prod.yml up -d
        
        # 等待服务启动
        sleep 5
        
        # 显示服务状态
        docker compose -f docker-compose.prod.yml ps
EOF
    
    if [ $? -ne 0 ]; then
        error "服务重启失败"
    fi
    
    info "✓ 服务重启成功"
}

# 检查服务状态
check_services() {
    info "检查服务状态..."
    
    ssh -o ConnectTimeout=30 ${SERVER_USER}@${SERVER_IP} << EOF
        cd ${REMOTE_DIR}
        
        # 检查容器状态
        echo "=== 容器状态 ==="
        docker compose -f docker-compose.prod.yml ps
        
        # 检查后端日志
        echo ""
        echo "=== 后端日志（最后20行）==="
        docker compose -f docker-compose.prod.yml logs --tail=20 backend
        
        # 测试网站访问
        echo ""
        echo "=== 测试网站访问 ==="
        if curl -s -o /dev/null -w "%{http_code}" http://localhost | grep -q "200"; then
            echo "✓ 网站访问正常 (HTTP 200)"
        else
            echo "✗ 网站访问异常"
        fi
EOF
    
    info "✓ 服务检查完成"
}

# 清理本地临时文件
cleanup() {
    info "清理本地临时文件..."
    
    if [ -f "${EXPORT_FILE}" ]; then
        rm -f "${EXPORT_FILE}"
        info "✓ 已删除导出文件: ${EXPORT_FILE}"
    fi
}

# 主流程
main() {
    echo "=========================================="
    echo "  本地构建并部署到服务器"
    echo "=========================================="
    echo ""
    
    # 执行各个步骤
    check_requirements
    test_connection
    build_image
    export_image
    upload_image
    import_image
    restart_services
    check_services
    cleanup
    
    echo ""
    echo "=========================================="
    info "部署完成！"
    echo "=========================================="
    echo ""
    echo "访问地址: http://www.qusuansuan.com"
    echo ""
}

# 捕获中断信号
trap 'error "部署被中断"' INT TERM

# 执行主流程
main
