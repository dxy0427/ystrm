import logging
from logging.handlers import RotatingFileHandler
import os

def init_logger():
    """初始化日志：控制台+文件输出，按大小切割"""
    log_dir = "/app/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "library_strm.log")

    logger = logging.getLogger("LibrarySTRM")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # 日志格式
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
    )

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出（最大100MB，保留5个备份）
    file_handler = RotatingFileHandler(
        log_file, maxBytes=100 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# 全局日志对象
logger = init_logger()