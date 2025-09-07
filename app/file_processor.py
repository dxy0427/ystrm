import os
import shutil
import time
from pathlib import Path
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

    def _normalize_dir(self, dir_path: str) -> str:
        # 确保路径以斜杠结尾，以便进行路径操作
        return os.path.abspath(dir_path).rstrip('/') + '/'

    def _normalize_dirs(self, dirs: List[str]) -> List[str]:
        return [self._normalize_dir(d) for d in dirs]

    def _get_relative_path(self, file_path: str, base_dir: str) -> str:
        # 确保 base_dir 是 file_path 的前缀
        if file_path.startswith(base_dir):
            return file_path[len(base_dir):]
        return os.path.relpath(file_path, base_dir)

    def _should_process(self, dest_file: str, source_mtime: float) -> bool:
        if not os.path.exists(dest_file):
            return True
        if global_config.overwrite_existing:
            return True
        return source_mtime > os.path.getmtime(dest_file)

    def generate_strm(self, source_video: str, base_source_dir: str):
        # 【关键修正】使用 library_dir 作为计算相对路径的基准
        rel_path = self._get_relative_path(source_video, self.library_dir)
        dest_strm = os.path.join(self.dest_dir, rel_path).replace(os.path.splitext(rel_path)[1], ".strm")
        dest_strm_dir = os.path.dirname(dest_strm)

        source_mtime = os.path.getmtime(source_video)
        if not self._should_process(dest_strm, source_mtime):
            logger.debug(f"STRM已存在且源文件未改，跳过：{dest_strm}")
            return

        os.makedirs(dest_strm_dir, exist_ok=True)
        try:
            strm_content = os.path.join(self.library_dir, rel_path)
            with open(dest_strm, "w", encoding="utf-8") as f:
                f.write(strm_content)
            os.utime(dest_strm, (source_mtime, source_mtime))
            logger.info(f"STRM生成成功：{dest_strm} → 指向：{strm_content}")
        except Exception as e:
            logger.error(f"STRM生成失败：{dest_strm} - {str(e)}", exc_info=True)

    def copy_metadata(self, source_metadata: str, base_source_dir: str):
        # 【关键修正】使用 library_dir 作为计算相对路径的基准
        rel_path = self._get_relative_path(source_metadata, self.library_dir)
        dest_metadata = os.path.join(self.dest_dir, rel_path)
        dest_metadata_dir = os.path.dirname(dest_metadata)

        source_mtime = os.path.getmtime(source_metadata)
        if not self._should_process(dest_metadata, source_mtime):
            logger.debug(f"元数据已存在且源文件未改，跳过：{dest_metadata}")
            return

        os.makedirs(dest_metadata_dir, exist_ok=True)
        try:
            shutil.copy2(source_metadata, dest_metadata)
            logger.info(f"元数据复制成功：{dest_metadata}")
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

                # 这里的 base_source_dir 参数虽然还在，但已在内部方法中被 self.library_dir 替代
                if self.create_strm and file_ext in self.video_exts:
                    self.generate_strm(source_file, source_dir)
                if self.enable_copy_metadata and file_ext in self.metadata_exts:
                    self.copy_metadata(source_file, source_dir)

                if interval > 0:
                    time.sleep(interval)

        logger.info(f"源目录处理完成：{source_dir}")

    def process_all_source_dirs(self):
        if not global_config.full_generate:
            logger.info("未启用全量生成，跳过文件处理")
            return

        logger.info("=" * 50)
        logger.info("开始全量文件处理（生成STRM+复制元数据）")
        for source_dir in self.source_dirs:
            self.process_single_dir(source_dir)
        logger.info("全量文件处理完成")
        logger.info("=" * 50)