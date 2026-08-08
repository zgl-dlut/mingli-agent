#!/bin/bash
# 生成 Nginx Basic Auth 密码文件
# 在服务器上执行此脚本，按照提示输入用户名和密码

if [ $# -lt 2 ]; then
    echo "用法: $0 <用户名> <密码>"
    echo "示例: $0 admin 'your_secure_password'"
    exit 1
fi

USERNAME=$1
PASSWORD=$2

# 使用 openssl 生成 htpasswd 格式的密码哈希
# 这比依赖 htpasswd 命令更通用
HASH=$(openssl passwd -apr1 "$PASSWORD")

# 输出结果
echo "${USERNAME}:${HASH}"
