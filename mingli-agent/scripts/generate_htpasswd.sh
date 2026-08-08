#!/bin/bash
# 在服务器上执行此脚本，生成 .htpasswd 文件
# 用法: ./generate_htpasswd.sh [用户名] [密码]

if [ $# -lt 2 ]; then
    echo "用法: $0 <用户名> <密码>"
    echo "示例: $0 admin 'your_secure_password'"
    exit 1
fi

USERNAME=$1
PASSWORD=$2
OUTPUT_FILE=".htpasswd"

# 使用 openssl 生成 Apache 格式的密码哈希
if command -v openssl &> /dev/null; then
    HASH=$(openssl passwd -apr1 "$PASSWORD")
    echo "${USERNAME}:${HASH}" > "$OUTPUT_FILE"
    echo "✅ 成功生成密码文件: $OUTPUT_FILE"
    echo "   用户名: $USERNAME"
    echo "   请务必妥善保管此文件。"
else
    echo "❌ 错误: 未找到 openssl 命令。"
    echo "请先安装 openssl 或手动使用 htpasswd 命令。"
    exit 1
fi
