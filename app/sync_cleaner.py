import os
import shutil
from logger import logger
from config import global_config

class SyncCleaner:
    def __init__(self, monitor_conf: dict):
        self.source_dirs = self._normalize_dirs(monitor_conf["source_dir"])  # 多源目录
        self.dest_dir = self._normalize_dir(monitor_conf["dest_dir"])       # 目标目录

    def _normalize_dir(self, dir_path: str) -> str:
        """标准化目录路径"""
        return os.path.abspath(dir_path) + "/"

    def _normalize_dirs(self, dirs: list) -> list:
        """标准化多源目录列表"""
        return [self._normalize_dir(d) for d in dirs]

    def _is_source_file_exists(self, relative_path: str) -> bool:
        """判断目标文件对应的源文件是否存在（遍历所有源目录）"""
        for source_dir in self.source_dirs:
            source_file = os.path.join(source_dir, relative_path)
            if os.path.exists(source_file):
                return True  # 任意一个源目录存在即视为有效
        return False

    def sync_source_dest(self):
        """强同步源目录与目标目录：删除目标中“源目录不存在”的文件/目录"""
        if not global_config.sync_source_dest or not os.path.exists(self.dest_dir):
            logger.info("未启用源目标同步或目标目录不存在，跳过同步")
            return

        logger.info("=" * 50)
        logger.info("开始源目标目录强同步（删除无效文件/目录）")
        # 遍历目标目录下所有文件（递归）
        for root, dirs, files in os.walk(self.dest_dir, topdown=False):  # topdown=False：先删文件再删目录
            # 处理文件：判断源文件是否存在
            for file in files:
                dest_file = os.path.join(root, file)
                # 计算相对于目标目录的路径（对应源目录的相对路径）
                rel_path = os.path.relpath(dest_file, self.dest_dir)
                # 源文件不存在 → 删除目标文件
                if not self._is_source_file_exists(rel_path):
                    try:
                        os.remove(dest_file)
                        logger.info(f"删除无效文件（源文件已删）：{dest_file}")
                    except Exception as e:
                        logger.error(f"删除无效文件失败：{dest_file} - {str(e)}", exc_info=True)

            # 处理目录：先标记需要删除的空目录（后续统一删）
            for dir_name in dirs:
                dest_subdir = os.path.join(root, dir_name)
                # 目录为空且对应源目录不存在 → 标记删除
                if not os.listdir(dest_subdir) and not self._is_source_file_exists(os.path.relpath(dest_subdir, self.dest_dir)):
                    try:
                        os.rmdir(dest_subdir)
                        logger.info(f"删除无效空目录（源目录已删）：{dest_subdir}")
                    except Exception as e:
                        logger.error(f"删除无效空目录失败：{dest_subdir} - {str(e)}", exc_info=True)
        logger.info("源目标目录强同步完成")
        logger.info("=" * 50)

    def cleanup_empty_dirs(self):
        """清理目标目录中所有空文件夹（即使源目录存在）"""
        if not global_config.cleanup_empty_dirs or not os.path.exists(self.dest_dir):
            logger.info("未启用空目录清理或目标目录不存在，跳过清理")
            return

        logger.info("=" * 50)
        logger.info("开始清理目标目录空文件夹")
        # 多次遍历确保删除嵌套空目录（如a/b/c空，先删c，再删b，最后删a）
        changed = True
        while changed:
            changed = False
            for root, dirs, _ in os.walk(self.dest_dir, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    if not os.listdir(dir_path):  # 目录为空
                        try:
                            os.rmdir(dir_path)
                            logger.info(f"删除空目录：{dir_path}")
                            changed = True
                        except Exception as e:
                            logger.error(f"删除空目录失败：{dir_path} - {str(e)}", exc_info=True)
        logger.info("空目录清理完成")
        logger.info("=" * 50)

    def run_full_cleanup(self):
        """执行完整清理流程：先同步源目标，再清理空目录"""
        self.sync_source_dest()
        self.cleanup_empty_dirs()