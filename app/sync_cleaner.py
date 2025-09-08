import os
import shutil
from typing import List, Set
from .logger import logger
from .config import global_config

class SyncCleaner:
    def __init__(self, monitor_conf: dict):
        self.source_dirs = self._normalize_dirs(monitor_conf["source_dir"])
        self.dest_dir = self._normalize_dir(monitor_conf["dest_dir"])
        self.library_dir = self._normalize_dir(monitor_conf["library_dir"])
        self.video_exts = monitor_conf["video_extensions"]
        self.metadata_exts = monitor_conf["metadata_extensions"]

    def _normalize_dir(self, dir_path: str) -> str: return os.path.abspath(dir_path).rstrip('/') + '/'
    def _normalize_dirs(self, dirs: List[str]) -> List[str]: return [self._normalize_dir(d) for d in dirs]

    def _is_source_file_exists(self, relative_path: str) -> bool:
        file_name, file_ext = os.path.splitext(relative_path)

        # 【逻辑分离】第一部分：处理 .strm 文件
        if file_ext.lower() == ".strm":
            for video_ext in self.video_exts:
                # 检查时，同时考虑小写和大写后缀，实现大小写不敏感
                source_file_lower = os.path.join(self.library_dir, f"{file_name}{video_ext.lower()}")
                source_file_upper = os.path.join(self.library_dir, f"{file_name}{video_ext.upper()}")
                
                if os.path.exists(source_file_lower) or os.path.exists(source_file_upper):
                    return True
            return False
        
        # 【逻辑分离】第二部分：处理元数据文件
        # 直接使用原始的、大小写敏感的相对路径去检查源文件是否存在
        source_file = os.path.join(self.library_dir, relative_path)
        return os.path.exists(source_file)

    def sync_source_dest(self):
        if not global_config.sync_source_dest or not os.path.exists(self.dest_dir):
            logger.info("未启用源目标同步，跳过")
            return
            
        logger.info("="*50 + "\n开始源目标目录强同步（删除无效文件/目录）")
        
        source_subdirs = set()
        for s_dir in self.source_dirs:
            for root, dirs, _ in os.walk(s_dir):
                for d in dirs:
                    source_subdirs.add(os.path.relpath(os.path.join(root, d), self.library_dir))
                    
        for root, dirs, files in os.walk(self.dest_dir, topdown=False):
            for file in files:
                dest_file = os.path.join(root, file)
                rel_path = os.path.relpath(dest_file, self.dest_dir)
                
                if global_config.preserve_extra_metadata and os.path.splitext(file)[1].lower() in self.metadata_exts:
                    continue
                    
                if not self._is_source_file_exists(rel_path):
                    try:
                        os.remove(dest_file)
                        logger.info(f"删除无效文件（源文件已删）：{dest_file}")
                    except Exception as e:
                        logger.error(f"删除无效文件失败：{dest_file} - {str(e)}", exc_info=True)
                        
            for dir_name in dirs:
                dest_subdir = os.path.join(root, dir_name)
                subdir_rel_path = os.path.relpath(dest_subdir, self.dest_dir)
                
                if not os.listdir(dest_subdir) and subdir_rel_path not in source_subdirs:
                    try:
                        os.rmdir(dest_subdir)
                        logger.info(f"删除无效空目录（源目录已删）：{dest_subdir}")
                    except Exception as e:
                        logger.error(f"删除无效空目录失败：{dest_subdir} - {str(e)}", exc_info=True)
                        
        logger.info("源目标目录强同步完成\n" + "="*50)

    def sync_metadata_back_to_source(self):
        if not global_config.sync_metadata_to_source:
            logger.info("未启用元数据反向同步，跳过")
            return
            
        logger.info("="*50 + "\n开始反向同步元数据（从目标到源）")
        
        for root, _, files in os.walk(self.dest_dir):
            for file in files:
                if os.path.splitext(file)[1].lower() not in self.metadata_exts:
                    continue
                    
                dest_file = os.path.join(root, file)
                rel_path = os.path.relpath(dest_file, self.dest_dir)
                source_file = os.path.join(self.library_dir, rel_path)
                
                should_sync = False
                if not os.path.exists(source_file):
                    should_sync = True
                else:
                    try:
                        if (os.path.getmtime(dest_file) > os.path.getmtime(source_file) or
                            os.path.getsize(dest_file) != os.path.getsize(source_file)):
                            should_sync = True
                    except OSError:
                        should_sync = True

                if should_sync:
                    try:
                        os.makedirs(os.path.dirname(source_file), exist_ok=True)
                        shutil.copy2(dest_file, source_file)
                        logger.info(f"反向同步元数据成功：{dest_file} -> {source_file}")
                    except Exception as e:
                        logger.error(f"反向同步元数据失败：{source_file} - {str(e)}", exc_info=True)
                        
        logger.info("反向同步元数据完成\n" + "="*50)

    def cleanup_empty_dirs(self):
        if not global_config.cleanup_empty_dirs or not os.path.exists(self.dest_dir):
            logger.info("未启用空目录清理，跳过")
            return
            
        logger.info("="*50 + "\n开始清理目标目录空文件夹")
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
                            
        logger.info("空目录清理完成\n" + "="*50)
        
    def run_full_cleanup(self):
        self.sync_metadata_back_to_source()
        self.sync_source_dest()
        self.cleanup_empty_dirs()