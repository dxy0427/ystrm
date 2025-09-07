import os
import shutil
from typing import List

from .logger import logger
from .config import global_config

class SyncCleaner:
    def __init__(self, monitor_conf: dict):
        self.source_dirs = self._normalize_dirs(monitor_conf["source_dir"])
        self.dest_dir = self._normalize_dir(monitor_conf["dest_dir"])
        # 【关键新增】获取 library_dir 用于正确的路径判断
        self.library_dir = self._normalize_dir(monitor_conf["library_dir"])
        self.video_exts = monitor_conf["video_extensions"]
        self.metadata_exts = monitor_conf["metadata_extensions"]

    def _normalize_dir(self, dir_path: str) -> str:
        return os.path.abspath(dir_path).rstrip('/') + '/'

    def _normalize_dirs(self, dirs: List[str]) -> List[str]:
        return [self._normalize_dir(d) for d in dirs]

    def _is_source_file_exists(self, relative_path: str) -> bool:
        file_name, file_ext = os.path.splitext(relative_path)

        if file_ext.lower() == ".strm":
            for video_ext in self.video_exts:
                video_relative_path = f"{file_name}{video_ext.lower()}"
                # 【关键修正】使用 library_dir 作为唯一的基准路径来拼接，避免重复
                source_file = os.path.join(self.library_dir, video_relative_path)
                if os.path.exists(source_file):
                    return True
            return False
        else: # 对于元数据文件，逻辑相同
            # 【关键修正】使用 library_dir 作为唯一的基准路径来拼接
            source_file = os.path.join(self.library_dir, relative_path)
            if os.path.exists(source_file):
                return True
            return False

    def sync_source_dest(self):
        if not global_config.sync_source_dest or not os.path.exists(self.dest_dir):
            logger.info("未启用源目标同步或目标目录不存在，跳过同步")
            return

        logger.info("=" * 50)
        logger.info("开始源目标目录强同步（删除无效文件/目录）")
        
        # 建立一个源目录的集合，用于快速判断目录是否存在
        # 【逻辑优化】提前获取所有真实的源目录相对路径
        source_subdirs = set()
        for s_dir in self.source_dirs:
            for root, dirs, _ in os.walk(s_dir):
                for d in dirs:
                    full_path = os.path.join(root, d)
                    rel_path = os.path.relpath(full_path, self.library_dir)
                    source_subdirs.add(rel_path)

        for root, dirs, files in os.walk(self.dest_dir, topdown=False):
            for file in files:
                dest_file = os.path.join(root, file)
                rel_path = os.path.relpath(dest_file, self.dest_dir)

                if not self._is_source_file_exists(rel_path):
                    try:
                        os.remove(dest_file)
                        logger.info(f"删除无效文件（源文件已删）：{dest_file}")
                    except Exception as e:
                        logger.error(f"删除无效文件失败：{dest_file} - {str(e)}", exc_info=True)

            for dir_name in dirs:
                dest_subdir = os.path.join(root, dir_name)
                subdir_rel_path = os.path.relpath(dest_subdir, self.dest_dir)
                
                # 【逻辑优化】判断一个目标目录是否无效：它既是空的，又不在真实的源目录结构中
                if not os.listdir(dest_subdir) and subdir_rel_path not in source_subdirs:
                    try:
                        os.rmdir(dest_subdir)
                        logger.info(f"删除无效空目录（源目录已删）：{dest_subdir}")
                    except Exception as e:
                        logger.error(f"删除无效空目录失败：{dest_subdir} - {str(e)}", exc_info=True)
                        
        logger.info("源目标目录强同步完成")
        logger.info("=" * 50)

    def cleanup_empty_dirs(self):
        if not global_config.cleanup_empty_dirs or not os.path.exists(self.dest_dir):
            logger.info("未启用空目录清理或目标目录不存在，跳过清理")
            return

        logger.info("=" * 50)
        logger.info("开始清理目标目录空文件夹")
        changed = True
        while changed:
            changed = False
            for root, dirs, _ in os.walk(self.dest_dir, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    if not os.listdir(dir_path):
                        try:
                            os.rmdir(dir_path)
                            logger.info(f"删除空目录：{dir_path}")
                            changed = True
                        except Exception as e:
                            logger.error(f"删除空目录失败：{dir_path} - {str(e)}", exc_info=True)
        logger.info("空目录清理完成")
        logger.info("=" * 50)

    def run_full_cleanup(self):
        self.sync_source_dest()
        self.cleanup_empty_dirs()