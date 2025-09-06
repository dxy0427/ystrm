# 基础镜像：Python 3.10 轻量版（用于构建 ystrm 工具）
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制 ystrm 代码（仅app目录）
COPY app/ ./app/

# 创建 ystrm 日志目录
RUN mkdir -p /app/logs && chmod 777 /app/logs

# 启动 ystrm 主程序
CMD ["python", "/app/main.py"]