import sys

# 确保能找到 /app 目录下的模块
sys.path.append("/app")

try:
    # 关键修正：直接从 'main' 模块导入，因为它和本文件在同一目录下
    from main import YSTRM
    from app.logger import logger

    logger.info("Cron task started by system cron daemon.")
    
    # 创建 YSTRM 实例并执行核心任务
    app = YSTRM()
    app._run_full_task()
    
    logger.info("Cron task finished successfully.")

except Exception as e:
    # 如果在执行过程中出现任何错误，将其打印出来。
    # 这个输出会被重定向到 /app/logs/cron.log 文件中。
    print(f"Cron task failed with an exception: {e}")
    # 抛出异常，以便在 cron.log 中看到完整的错误堆栈信息
    raise