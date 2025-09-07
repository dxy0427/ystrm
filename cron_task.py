import sys

# 确保能找到 app 模块
sys.path.append("/app")

try:
    # 这里的导入会触发 config.py 和 logger.py 的初始化
    from app.main import YSTRM
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