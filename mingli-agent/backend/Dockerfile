FROM python:3.11-slim

WORKDIR /app

# 清除基础镜像默认源，全部替换为阿里云镜像
RUN rm -f /etc/apt/sources.list.d/* && \
    echo "deb http://mirrors.aliyun.com/debian trixie main" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian trixie-updates main" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security trixie-security main" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY sxwnl/ ./sxwnl/

# 使用阿里云 PyPI 镜像加速 Python 包下载
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
