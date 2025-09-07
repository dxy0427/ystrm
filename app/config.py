import yaml
import os
from typing import List, Dict, Optional

from .logger import logger

class Config:
    def __init__(self, config_path: str = "/app/config.yaml"):
        self.config_path = config_path
        self._load_config()
        self._validate_config()

    def _load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)["sync"]
            logger.info("配置文件加载成功")
        except Exception as e:
            logger.error(f"配置文件加载失败：{str(e)}", exc_info=True)
            raise

    def _validate_config(self):
        required = [
            ("run_full_task_on_startup", bool),
            ("real_time_monitor", bool),
            ("cron_full_process.enable", bool),
            ("cron_full_process.cron_expression", str),
            ("monitor_confs", list)
        ]

        for key, typ in required:
            keys = key.split(".")
            value = self.config
            try:
                for k in keys:
                    value = value[k]
                if not isinstance(value, typ):
                    raise TypeError(f"{key} 类型错误，需为{typ.__name__}")
            except (KeyError, TypeError) as e:
                logger.error(f"配置项错误：{key} - {str(e)}", exc_info=True)
                raise

        for idx, conf in enumerate(self.config["monitor_confs"]):
            if not all(k in conf for k in ["source_dir", "dest_dir", "library_dir"]):
                logger.error(f"监控配置[{idx}]缺失核心路径（source_dir/dest_dir/library_dir）")
                raise KeyError(f"monitor_confs[{idx}] 核心路径缺失")

    @property
    def run_full_task_on_startup(self) -> bool:
        return self.config.get("run_full_task_on_startup", True)

    @property
    def real_time_monitor(self) -> bool:
        return self.config.get("real_time_monitor", False)

    @property
    def cron_enable(self) -> bool:
        return self.config["cron_full_process"]["enable"]

    @property
    def cron_expression(self) -> str:
        return self.config["cron_full_process"]["cron_expression"]

    # 【关键修改】实现速率转换逻辑
    @property
    def file_processing_interval(self) -> float:
        try:
            # 读取新的配置项，默认为 0
            rate_limit = self.config["cron_full_process"].get("files_per_second_limit", 0)
            rate_limit = int(rate_limit)

            # 如果限制为 0 或负数，则不等待
            if rate_limit <= 0:
                return 0.0
            
            # 否则，计算每个文件处理后需要等待的秒数
            # 例如：rate_limit=2 (每秒2个)，则返回 1.0 / 2 = 0.5 秒
            return 1.0 / rate_limit

        except (ValueError, TypeError):
            # 如果配置值不是数字，则默认为不等待
            return 0.0

    @property
    def full_generate(self) -> bool:
        return self.config["cron_full_process"].get("full_generate", True)

    @property
    def overwrite_existing(self) -> bool:
        return self.config["cron_full_process"].get("overwrite_existing", False)

    @property
    def sync_source_dest(self) -> bool:
        return self.config["cron_full_process"].get("sync_source_dest", True)

    @property
    def cleanup_empty_dirs(self) -> bool:
        return self.config["cron_full_process"].get("cleanup_empty_dirs", True)

    @property
    def monitor_confs(self) -> List[Dict]:
        return self.config["monitor_confs"]

global_config = Config()