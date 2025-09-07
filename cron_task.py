import sys
sys.path.append("/app")

try:
    from main import YSTRM
    from app.logger import logger

    logger.info("Cron task started by system cron daemon.")
    app = YSTRM()
    app._run_full_task()
    logger.info("Cron task finished successfully.")

except Exception as e:
    print(f"Cron task failed with an exception: {e}")
    raise