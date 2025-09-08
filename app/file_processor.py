import os
import shutil
import time
from typing import List
from .logger import logger
from .config import global_config
import errno 

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
        return os.path.abspath(dir_path).rstrip('/') + '/'

    def _normalize_dirs(self, dirs: List[str]) -> List[str]:
        return [self._normalize_dir(d) for d in dirs]

    def _get_relative_path(self, file_path: str, base_dir: str) -> str:
        return os.path.relpath(file_path, base_dir)

    def _should_process_metadata(self, source_file: str, dest_file: str) -> bool:
        if not os.path.exists(dest_file):
            return True
        if global_config.overwrite_existing:
            return True
        # 对元数据文件，同时比较修改时间和文件大小
        return (os.path.getmtime(source_file) > os.path.getmtime(dest_file) or
                os.path.getsize(source_file) != os.path.getsize(dest_file))

    def generate_strm(self, source_video: str, base_dir: str):
        rel_path = self._get_relative_path(source_video, base_dir)
        dest_strm = os.path.splitext(os.path.join(self.dest_dir, rel_path))[0] + ".strm"
        
        # 对 .strm 文件，逻辑简化为：不存在或需要强制覆盖时才创建
        if os.path.exists(dest_strm) and not global_config.overwrite_existing:
            logger.debug(f"STRM已存在，跳过创建：{dest_strm}")
            return
            
        dest_strm_dir = os.path.dirname(dest_strm)
        os.makedirs(dest_strm_dir, exist_ok=True)
        
        try:
            source_mtime = os.path.getmtime(source_video)
            strm_content = source_video
            
            with open(dest_strm, "w", encoding="utf-8") as f:
                f.write(strm_content)
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
        
        # 将 os.walk 转换为列表，以便在出错时可以从断点继续
        try:
            dir_walk_list = list(os.walk(source_dir))
        except OSError as e:
            if e.errno == errno.ENOTCONN: # 错误码 107
                logger.critical(f"开始扫描目录时即发现挂载丢失: {source_dir}。中止对此目录的处理。")
                return
            else:
                # 对于其他未知的OS错误，记录并抛出
                logger.error(f"扫描目录时发生未知操作系统错误: {source_dir} - {str(e)}", exc_info=True)
                raise

        # 遍历目录和文件
        for root, _, files in dir_walk_list:
            for file in files:
                source_file = os.path.join(root, file)
                
                # “暂停与重试”循环，专门处理单个文件的访问错误
                while True:
                    try:
                        # 核心处理逻辑
                        file_ext = os.path.splitext(file)[1].lower()
                        
                        if self.create_strm and file_ext in self.video_exts:
                            self.generate_strm(source_file, self.library_dir)
                        if self.enable_copy_metadata and file_ext in self.metadata_exts:
                            self.copy_metadata(source_file, self.library_dir)
                            
                        # 如果设置了间隔，则等待
                        if interval > 0:
                            time.sleep(interval)

                        # 如果成功处理，就跳出重试循环，继续下一个文件
                        break 
                        
                    except OSError as e:
                        # 只处理 "Transport endpoint is not connected" 这个特定错误
                        if e.errno == errno.ENOTCONN:
                            logger.warning(f"检测到挂载连接丢失，正在暂停处理... 将在30秒后重试。出错文件: {source_file}")
                            time.sleep(30)
                            # 不做任何事，让 while True 循环自动进行下一次尝试
                        else:
                            # 如果是其他操作系统错误，记录下来并放弃这个文件
                            logger.error(f"处理文件时发生未知的操作系统错误，已跳过: {source_file} - {str(e)}")
                            break 
                    except Exception as e:
                        # 如果是其他未知异常，记录下来并放弃这个文件
                        logger.error(f"处理文件时发生未知错误，已跳过: {source_file} - {str(e)}", exc_info=True)
                        break
            
        logger.info(f"源目录处理完成：{source_dir}")

    def process_all_source_dirs(self):
        if not global_config.full_generate:
            logger.info("未启用全量生成，跳过文件处理")
            return
        
        logger.info("="*50 + "\n开始全量文件处理（生成STRM+复制元数据）")
        for source_dir in self.source_dirs:
            self.process_single_dir(source_dir)
        logger.info("全量文件处理完成\n" + "="*50)