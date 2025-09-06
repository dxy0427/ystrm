import os
import shutil
from pathlib import Path
from logger import logger
from config import global_config

class FileProcessor:
    def __init__(self, monitor_conf: dict):
        self.source_dirs = self._normalize_dirs(monitor_conf["source_dir"])  # 多源目录
        self.dest_dir = self._normalize_dir(monitor_conf["dest_dir"])       # 目标目录
        self.library_dir = self._normalize_dir(monitor_conf["library_dir"]) # Emby访问路径
        self.video_exts = monitor_conf["video_extensions"]                  # 视频后缀
        self.metadata_exts = monitor_conf["metadata_extensions"]            # 元数据后缀
        self.create_strm = monitor_conf.get("create_strm", True)
        self.copy_metadata = monitor_conf.get("copy_metadata", True)

    def _normalize_dir(self, dir_path: str) -> str:
        """标准化目录路径（确保以/结尾）"""
        return os.path.abspath(dir_path) + "/"

    def _normalize_dirs(self, dirs: list) -> list:
        """标准化多源目录列表"""
        return [self._normalize_dir(d) for d in dirs]

    def _get_relative_path(self, file_path: str, base_dir: str) -> str:
        """计算文件相对于基准目录的路径"""
        return os.path.relpath(file_path, base_dir)

    def _should_process(self, dest_file: str, source_mtime: float) -> bool:
        """判断是否需要处理文件（新增/修改）"""
        if not os.path.exists(dest_file):
            return True  # 文件不存在，需要生成/复制
        if global_config.overwrite_existing:
            return True  # 强制覆盖，需要处理
        # 源文件修改时间晚于目标文件，需要更新
        return source_mtime > os.path.getmtime(dest_file)

    def generate_strm(self, source_video: str, base_source_dir: str):
        """生成STRM文件：根据源视频路径，在目标目录创建对应STRM"""
        # 1. 计算相对路径（保持目录结构一致）
        rel_path = self._get_relative_path(source_video, base_source_dir)
        dest_strm = os.path.join(self.dest_dir, rel_path.replace(os.path.splitext(rel_path)[1], ".strm"))
        dest_strm_dir = os.path.dirname(dest_strm)

        # 2. 判断是否需要生成
        source_mtime = os.path.getmtime(source_video)
        if not self._should_process(dest_strm, source_mtime):
            logger.debug(f"STRM已存在且源文件未改，跳过：{dest_strm}")
            return

        # 3. 创建目标目录
        os.makedirs(dest_strm_dir, exist_ok=True)

        # 4. 写入STRM内容（Emby可访问的真实路径）
        try:
            # STRM内路径 = library_dir + 相对路径（相对于source_dir的路径）
            strm_content = os.path.join(self.library_dir, rel_path)
            with open(dest_strm, "w", encoding="utf-8") as f:
                f.write(strm_content)
            # 同步源文件修改时间（便于后续判断）
            os.utime(dest_strm, (source_mtime, source_mtime))
            logger.info(f"STRM生成成功：{dest_strm} → 指向：{strm_content}")
        except Exception as e:
            logger.error(f"STRM生成失败：{dest_strm} - {str(e)}", exc_info=True)

    def copy_metadata(self, source_metadata: str, base_source_dir: str):
        """复制元数据文件：保持目录结构一致"""
        # 1. 计算相对路径
        rel_path = self._get_relative_path(source_metadata, base_source_dir)
        dest_metadata = os.path.join(self.dest_dir, rel_path)
        dest_metadata_dir = os.path.dirname(dest_metadata)

        # 2. 判断是否需要复制
        source_mtime = os.path.getmtime(source_metadata)
        if not self._should_process(dest_metadata, source_mtime):
            logger.debug(f"元数据已存在且源文件未改，跳过：{dest_metadata}")
            return

        # 3. 创建目标目录
        os.makedirs(dest_metadata_dir, exist_ok=True)

        # 4. 复制文件（保留元数据）
        try:
            shutil.copy2(source_metadata, dest_metadata)  # copy2保留修改时间等元数据
            logger.info(f"元数据复制成功：{dest_metadata}")
        except Exception as e:
            logger.error(f"元数据复制失败：{dest_metadata} - {str(e)}", exc_info=True)

    def process_single_dir(self, source_dir: str):
        """处理单个源目录：遍历所有文件，生成STRM+复制元数据"""
        if not os.path.exists(source_dir):
            logger.warning(f"源目录不存在，跳过：{source_dir}")
            return

        logger.info(f"开始处理源目录：{source_dir}")
        # 遍历源目录下所有文件（递归）
        for root, _, files in os.walk(source_dir):
            for file in files:
                source_file = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()

                # 处理视频文件：生成STRM
                if self.create_strm and file_ext in self.video_exts:
                    self.generate_strm(source_file, source_dir)

                # 处理元数据文件：复制
                if self.copy_metadata and file_ext in self.metadata_exts:
                    self.copy_metadata(source_file, source_dir)

        logger.info(f"源目录处理完成：{source_dir}")

    def process_all_source_dirs(self):
        """处理所有源目录（多源目录批量处理）"""
        if not global_config.full_generate:
            logger.info("未启用全量生成，跳过文件处理")
            return

        logger.info("=" * 50)
        logger.info("开始全量文件处理（生成STRM+复制元数据）")
        for source_dir in self.source_dirs:
            self.process_single_dir(source_dir)
        logger.info("全量文件处理完成")
        logger.info("=" * 50)
