import os
import shutil
from typing import List

from .logger import logger
from .config import global_config

class SyncCleaner:
    # 1. 关键修改：初始化时接收视频/元数据后缀，用于区分STRM和元数据
    def __init__(self, monitor_conf: dict):
        self.source_dirs = self._normalize_dirs(monitor_conf["source_dir"])
        self.dest_dir = self._normalize_dir(monitor_conf["dest_dir"])
        self.video_exts = monitor_conf["video_extensions"]  # 接收视频后缀列表
        self.metadata_exts = monitor_conf["metadata_extensions"]  # 接收元数据后缀列表

    def _normalize_dir(self, dir_path: str) -> str:
        return os.path.abspath(dir_path) + "/"

    def _normalize_dirs(self, dirs: List[str]) -> List[str]:
        return [self._normalize_dir(d) for d in dirs]

    # 2. 关键修改：判断源文件是否存在（处理STRM文件的后缀映射）
    def _is_source_file_exists(self, relative_path: str) -> bool:
        # 提取文件名和后缀
        file_name, file_ext = os.path.splitext(relative_path)
        
        # 如果是STRM文件：尝试替换为所有视频后缀，检查源目录是否存在对应视频
        if file_ext.lower() == ".strm":
            for video_ext in self.video_exts:
                video_relative_path = f"{file_name}{video_ext.lower()}"  # 拼接视频路径（如1.mp4）
                for source_dir in self.source_dirs:
                    source_file = os.path.join(source_dir, video_relative_path)
                    if os.path.exists(source_file):
                        return True  # 找到对应的视频源文件，返回存在
            return False  # 所有视频后缀都没找到，返回不存在
        
        # 如果是元数据文件：直接用原相对路径检查（元数据后缀和源一致）
        else:
            for source_dir in self.source_dirs:
                source_file = os.path.join(source_dir, relative_path)
                if os.path.exists(source_file):
                    return True
            return False

    def sync_source_dest(self):
        if not global_config.sync_source_dest or not os.path.exists(self.dest_dir):
            logger.info("未启用源目标同步或目标目录不存在，跳过同步")
            return

        logger.info("=" * 50)
        logger.info("开始源目标目录强同步（删除无效文件/目录）")
        for root, dirs, files in os.walk(self.dest_dir, topdown=False):
            for file in files:
                dest_file = os.path.join(root, file)
                # 3. 计算相对路径时，确保从dest_dir根目录开始（避免路径层级错误）
                rel_path = os.path.relpath(dest_file, self.dest_dir)
                
                # 检查源文件是否存在（用修正后的_is_source_file_exists方法）
                if not self._is_source_file_exists(rel_path):
                    try:
                        os.remove(dest_file)
                        logger.info(f"删除无效文件（源文件已删）：{dest_file}")
                    except Exception as e:
                        logger.error(f"删除无效文件失败：{dest_file} - {str(e)}", exc_info=True)

            for dir_name in dirs:
                dest_subdir = os.path.join(root, dir_name)
                subdir_rel_path = os.path.relpath(dest_subdir, self.dest_dir)
                if not os.listdir(dest_subdir) and not self._is_source_file_exists(subdir_rel_path):
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
