import yaml
import os
from logger import logger
from typing import List, Dict, Optional

class Config:
    def __init__(self, config_path: str = "/app/config.yaml"):
        self.config_path = config_path
        self._load_config()
        self._validate_config()

    def _load_config(self):
        """加载yaml配置文件"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)["sync"]
            logger.info("配置文件加载成功")
        except Exception as e:
            logger.error(f"配置文件加载失败：{str(e)}", exc_info=True)
            raise

    def _validate_config(self):
        """验证核心配置项是否存在"""
        # 必选配置项检查
        required = [
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

        # 监控目录配置检查
        for idx, conf in enumerate(self.config["monitor_confs"]):
            if not all(k in conf for k in ["source_dir", "dest_dir", "library_dir"]):
                logger.error(f"监控配置[{idx}]缺失核心路径（source_dir/dest_dir/library_dir）")
                raise KeyError(f"monitor_confs[{idx}] 核心路径缺失")

    # -------------------------- 配置项快捷访问 --------------------------
    @property
    def real_time_monitor(self) -> bool:
        """是否启用实时监控（当前需求：False）"""
        return self.config.get("real_time_monitor", False)

    @property
    def cron_enable(self) -> bool:
        """是否启用定时任务"""
        return self.config["cron_full_process"]["enable"]

    @property
    def cron_expression(self) -> str:
        """定时任务Cron表达式（如：0 3 * * *）"""
        return self.config["cron_full_process"]["cron_expression"]

    @property
    def full_generate(self) -> bool:
        """是否全量扫描生成缺失文件"""
        return self.config["cron_full_process"].get("full_generate", True)

    @property
    def overwrite_existing(self) -> bool:
        """是否覆盖已存在的文件"""
        return self.config["cron_full_process"].get("overwrite_existing", False)

    @property
    def sync_source_dest(self) -> bool:
        """是否强同步源目录与目标目录（源删则目标删）"""
        return self.config["cron_full_process"].get("sync_source_dest", True)

    @property
    def cleanup_empty_dirs(self) -> bool:
        """是否清理空文件夹"""
        return self.config["cron_full_process"].get("cleanup_empty_dirs", True)

    @property
    def monitor_confs(self) -> List[Dict]:
        """监控目录配置列表"""
        return self.config["monitor_confs"]

# 全局配置对象
global_config = Config()