import os
import shutil
import time
from typing import List
from .logger import logger
from .config import global_config

class FileProcessor:
    def __init__(self, monitor_conf: dict):
        self.source_dirs = self._normalize_dirs(monitor_conf["source_dir"])
        self.dest_dir = self._normalize_dir(monitor_conf["dest_dir"])
        self.library_dir = self._normalize_dir(monitor_conf["library_dir"])
        self.video_exts = monitor_conf["video_extensions"]
        self.metadata_exts = monitor_conf["metadata_extensions"]
        self.create_strm = monitor_conf.get("create_strm", True)
        self.enable_copy_metadata = monitor_conf.get("copy_metadata", True)

    def _normalize_dir(self, dir_path: str) -> str: return os.path.abspath(dir_path).rstrip('/') + '/'
    def _normalize_dirs(self, dirs: List[str]) -> List[str]: return [self._normalize_dir(d) for d in dirs]
    def _get_relative_path(self, file_path: str, base_dir: str) -> str: return os.path.relpath(file_path, base_dir)

    # 【关键修正】分离 strm 和 metadata 的判断逻辑
    def _should_process_metadata(self, source_file: str, dest_file: str) -> bool:
        if not os.path.exists(dest_file): return True
        if global_config.overwrite_existing: return True
        # 元数据文件，比较修改时间和文件大小
        return (os.path.getmtime(source_file) > os.path.getmtime(dest_file) or
                os.path.getsize(source_file) != os.path.getsize(dest_file))

    def generate_strm(self, source_video: str, base_dir: str):
        rel_path = self._get_relative_path(source_video, base_dir)
        dest_strm = os.path.splitext(os.path.join(self.dest_dir, rel_path))[0] + ".strm"
        
        # 【关键修正】对于 .strm 文件，逻辑极其简单：不存在就创建
        if os.path.exists(dest_strm) and not global_config.overwrite_existing:
            logger.debug(f"STRM已存在，跳过创建：{dest_strm}")
            return
            
        dest_strm_dir = os.path.dirname(dest_strm)
        os.makedirs(dest_strm_dir, exist_ok=True)
        
        try:
            source_mtime = os.path.getmtime(source_video)
            strm_content = source_video
            
            with open(dest_strm, "w", encoding="utf-8") as f: f.write(strm_content)
            os.utime(dest_strm, (source_mtime, source_mtime))
            logger.info(f"STRM生成成功：{dest_strm} → 指向：{strm_content}")
        except Exception as e:
            logger.error(f"STRM生成失败：{dest_strm} - {str(e)}", exc_info=True)

    def copy_metadata(self, source_metadata: str, base_dir: str):
        rel_path = self._get_relative_path(source_metadata, base_dir)
        dest_metadata = os.path.join(self.dest_dir, rel_path)
        
        # 使用专门为元数据设计的比对方法
        if not self._should_process_metadata(source_metadata, dest_metadata):
            logger.debug(f"元数据已存在且未更新，跳过：{dest_metadata}")
            return
            
        dest_metadata_dir = os.path.dirname(dest_metadata)
        os.makedirs(dest_metadata_dir, exist_ok=True)
        
        try:
            shutil.copy2(source_metadata, dest_metadata)
            logger.info(f"元数据复制/更新成功：{dest_metadata}")
        except Exception as e:
            logger.error(f"元数据复制失败：{dest_metadata} - {str(e)}", exc_info=True)

    def process_single_dir(self, source_dir: str):
        if not os.path.exists(source_dir):
            logger.warning(f"源目录不存在，跳过：{source_dir}")
            return
        
        logger.info(f"开始处理源目录：{source_dir}")
        interval = global_config.file_processing_interval
        
        for root, _, files in os.walk(source_dir):
            for file in files:
                source_file = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()
                
                if self.create_strm and file_ext in self.video_exts:
                    self.generate_strm(source_file, self.library_dir)
                if self.enable_copy_metadata and file_ext in self.metadata_exts:
                    self.copy_metadata(source_file, self.library_dir)
                    
                if interval > 0:
                    time.sleep(interval)
                    
        logger.info(f"源目录处理完成：{source_dir}")

    def process_all_source_dirs(self):
        if not global_config.full_generate:
            logger.info("未启用全量生成，跳过文件处理")
            return
        
        logger.info("="*50 + "\n开始全量文件处理（生成STRM+复制元数据）")
        for source_dir in self.source_dirs:
            self.process_single_dir(source_dir)
        logger.info("全量文件处理完成\n" + "="*50)