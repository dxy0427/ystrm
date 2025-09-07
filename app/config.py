import yaml, os
from typing import List, Dict
from .logger import logger
class Config:
    def __init__(self, c_path="/app/config.yaml"): self.config_path, self._load_config, self._validate_config = c_path, self._load_config(), self._validate_config()
    def _load_config(self):
        try:
            with open(self.config_path,"r",encoding="utf-8") as f: self.config=yaml.safe_load(f)["sync"]
            logger.info("配置文件加载成功")
        except Exception as e: logger.error(f"配置文件加载失败：{e}",exc_info=True); raise
    def _validate_config(self):
        req=[("run_full_task_on_startup",bool),("real_time_monitor",bool),("cron_full_process.enable",bool),("cron_full_process.cron_expression",str),("monitor_confs",list)]
        for k,t in req:
            keys,v=k.split("."),self.config
            try:
                for key in keys: v=v[key]
                if not isinstance(v, t): raise TypeError(f"{k} 类型错误，需为{t.__name__}")
            except (KeyError,TypeError) as e: logger.error(f"配置项错误：{k} - {e}",exc_info=True); raise
        for i,c in enumerate(self.config["monitor_confs"]):
            if not all(k in c for k in["source_dir","dest_dir","library_dir"]): logger.error(f"监控配置[{i}]缺失核心路径"); raise KeyError(f"monitor_confs[{i}] 核心路径缺失")
    @property
    def run_full_task_on_startup(self)->bool: return self.config.get("run_full_task_on_startup",True)
    @property
    def real_time_monitor(self)->bool: return self.config.get("real_time_monitor",False)
    @property
    def cron_enable(self)->bool: return self.config["cron_full_process"]["enable"]
    @property
    def cron_expression(self)->str: return self.config["cron_full_process"]["cron_expression"]
    @property
    def file_processing_interval(self)->float:
        try:
            rate=int(self.config["cron_full_process"].get("files_per_second_limit",0))
            return 1.0/rate if rate>0 else 0.0
        except: return 0.0
    @property
    def full_generate(self)->bool: return self.config["cron_full_process"].get("full_generate",True)
    @property
    def overwrite_existing(self)->bool: return self.config["cron_full_process"].get("overwrite_existing",False)
    @property
    def sync_source_dest(self)->bool: return self.config["cron_full_process"].get("sync_source_dest",True)
    @property
    def cleanup_empty_dirs(self)->bool: return self.config["cron_full_process"].get("cleanup_empty_dirs",True)
    # 【新功能】读取新开关
    @property
    def preserve_extra_metadata(self)->bool: return self.config["cron_full_process"].get("preserve_extra_metadata", True)
    @property
    def sync_metadata_to_source(self)->bool: return self.config["cron_full_process"].get("sync_metadata_to_source", False)
    @property
    def monitor_confs(self)->List[Dict]: return self.config["monitor_confs"]
global_config=Config()