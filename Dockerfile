# 基础镜像：Python 3.10 轻量版
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（处理文件权限、时区等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 设置时区（确保Cron时间正确）
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码（只复制app目录，不复制config）
COPY app/ ./app/

# 创建日志目录
RUN mkdir -p /app/logs && chmod 777 /app/logs

# 启动命令（直接运行主程序）
CMD ["python", "/app/main.py"]