import yaml
import os
from typing import List, Dict
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
            keys, value = key.split("."), self.config
            try:
                for k in keys: value = value[k]
                if not isinstance(value, typ): raise TypeError(f"{key} 类型错误，需为{typ.__name__}")
            except (KeyError, TypeError) as e:
                logger.error(f"配置项错误：{key} - {str(e)}", exc_info=True)
                raise
        for idx, conf in enumerate(self.config["monitor_confs"]):
            if not all(k in conf for k in ["source_dir", "dest_dir", "library_dir"]):
                logger.error(f"监控配置[{idx}]缺失核心路径")
                raise KeyError(f"monitor_confs[{idx}] 核心路径缺失")

    @property
    def run_full_task_on_startup(self) -> bool: return self.config.get("run_full_task_on_startup", True)
    @property
    def real_time_monitor(self) -> bool: return self.config.get("real_time_monitor", False)
    @property
    def cron_enable(self) -> bool: return self.config["cron_full_process"]["enable"]
    @property
    def cron_expression(self) -> str: return self.config["cron_full_process"]["cron_expression"]
    @property
    def file_processing_interval(self) -> float:
        try:
            rate = int(self.config["cron_full_process"].get("files_per_second_limit", 0))
            return 1.0 / rate if rate > 0 else 0.0
        except (ValueError, TypeError): return 0.0
    @property
    def full_generate(self) -> bool: return self.config["cron_full_process"].get("full_generate", True)
    @property
    def overwrite_existing(self) -> bool: return self.config["cron_full_process"].get("overwrite_existing", False)
    @property
    def sync_source_dest(self) -> bool: return self.config["cron_full_process"].get("sync_source_dest", True)
    @property
    def cleanup_empty_dirs(self) -> bool: return self.config["cron_full_process"].get("cleanup_empty_dirs", True)
    @property
    def preserve_extra_metadata(self) -> bool: return self.config["cron_full_process"].get("preserve_extra_metadata", True)
    @property
    def sync_metadata_to_source(self) -> bool: return self.config["cron_full_process"].get("sync_metadata_to_source", False)
    
    # 【新增】读取安全锁开关
    @property
    def stop_on_mount_loss(self) -> bool: return self.config["cron_full_process"].get("stop_on_mount_loss", True)
    
    @property
    def monitor_confs(self) -> List[Dict]: return self.config["monitor_confs"]

global_config = Config()