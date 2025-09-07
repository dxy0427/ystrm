FROM python:3.10-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY cron_task.py .
COPY app/ ./app/

RUN mkdir -p /app/logs && chmod 777 /app/logs

CMD ["sh", "-c", "cron && python /app/main.py"]