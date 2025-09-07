# 基础镜像：Python 3.10 轻量版
FROM python:3.10-slim

# 设置工作目录（容器内根路径：/app）
WORKDIR /app

# 安装系统依赖（cron用于定时任务，tzdata用于时区）
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 设置时区（确保定时任务时间正确）
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 复制依赖文件（先复制requirements.txt，利用Docker缓存）
COPY requirements.txt .
# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY main.py .
COPY cron_task.py .
COPY app/ ./app/

# 创建日志目录（权限777，避免写入失败）
RUN mkdir -p /app/logs && chmod 777 /app/logs

# 启动命令
CMD ["sh", "-c", "cron && python /app/main.py"]