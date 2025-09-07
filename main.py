import time
import os
import shutil  # 关键新增：用于移动和删除目录树
from threading import Thread
from crontab import CronTab
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 模块引用：从app包导入核心组件
from app.logger import logger
from app.config import global_config
from app.file_processor import FileProcessor
from app.sync_cleaner import SyncCleaner

# -------------------------- 实时监控事件处理器（功能增强） --------------------------
class RealTimeHandler(FileSystemEventHandler):
    def __init__(self, processor: FileProcessor, cleaner: SyncCleaner):
        self.processor = processor
        self.cleaner = cleaner

    def _get_dest_path(self, source_path: str) -> Optional[str]:
        """
        通用方法：根据源路径（文件或目录）计算出目标路径。
        - 对视频文件，会替换后缀为 .strm。
        - 对其他文件和目录，保持相对路径一致。
        """
        for source_dir in self.processor.source_dirs:
            if source_path.startswith(source_dir):
                rel_path = os.path.relpath(source_path, source_dir)
                dest_path = os.path.join(self.processor.dest_dir, rel_path)
                
                # 如果是视频文件，则目标路径后缀应为 .strm
                if not os.path.isdir(source_path) and os.path.splitext(source_path)[1].lower() in self.processor.video_exts:
                    return os.path.splitext(dest_path)[0] + ".strm"
                return dest_path
        return None

    def on_created(self, event):
        """处理文件或目录的创建"""
        if event.is_directory:
            # 修正1：处理目录创建
            dest_dir = self._get_dest_path(event.src_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
                logger.info(f"实时同步创建目录：{dest_dir}")
        else:
            self._process_file(event.src_path, "创建")

    def on_modified(self, event):
        """处理文件的修改"""
        if not event.is_directory:
            self._process_file(event.src_path, "修改")

    def on_deleted(self, event):
        """处理文件或目录的删除"""
        dest_path = self._get_dest_path(event.src_path)
        if not dest_path or not os.path.exists(dest_path):
            return

        try:
            if event.is_directory:
                # 修正2：精准删除目录树
                shutil.rmtree(dest_path)
                logger.info(f"实时同步删除目录：{dest_path}")
            else:
                os.remove(dest_path)
                logger.info(f"实时删除无效文件：{dest_path}")
            # 删除后，清理可能产生的空父目录
            self.cleaner.cleanup_empty_dirs()
        except Exception as e:
            logger.error(f"实时删除失败：{dest_path} - {str(e)}", exc_info=True)

    def on_moved(self, event):
        """修正3：新增对移动/重命名事件的处理"""
        old_dest_path = self._get_dest_path(event.src_path)
        new_dest_path = self._get_dest_path(event.dest_path)

        if not old_dest_path or not new_dest_path:
            return

        try:
            if os.path.exists(old_dest_path):
                # 确保目标父目录存在
                os.makedirs(os.path.dirname(new_dest_path), exist_ok=True)
                shutil.move(old_dest_path, new_dest_path)
                logger.info(f"实时同步移动/重命名：{old_dest_path} -> {new_dest_path}")
                # 移动后，清理可能产生的空父目录
                self.cleaner.cleanup_empty_dirs()
            else:
                # 如果旧目标不存在，说明是新文件移入监控区，当作创建处理
                self._process_file(event.dest_path, "移入")
        except Exception as e:
            logger.error(f"实时移动/重命名失败 - {str(e)}", exc_info=True)

    def _process_file(self, source_file: str, event_type: str):
        """处理文件的核心逻辑（生成STRM/复制元数据）"""
        file_ext = os.path.splitext(source_file)[1].lower()
        target_source_dir = None
        for source_dir in self.processor.source_dirs:
            if source_file.startswith(source_dir):
                target_source_dir = source_dir
                break
        
        if not target_source_dir:
            logger.debug(f"文件不在监控源目录内，跳过 {event_type}：{source_file}")
            return

        logger.info(f"源文件{event_type}，开始处理：{source_file}")
        if self.processor.create_strm and file_ext in self.processor.video_exts:
            self.processor.generate_strm(source_file, target_source_dir)
        if self.processor.enable_copy_metadata and file_ext in self.processor.metadata_exts:
            self.processor.copy_metadata(source_file, target_source_dir)

# -------------------------- 主程序类（修正定时任务逻辑） --------------------------
class YSTRM:
    def __init__(self):
        self.processors = [FileProcessor(conf) for conf in global_config.monitor_confs]
        self.cleaners = [SyncCleaner(conf) for conf in global_config.monitor_confs]
        self.observers = []

    def _run_full_task(self):
        """执行完整定时任务：文件处理 → 同步清理（功能不变）"""
        logger.info("=" * 60)
        logger.info("【定时任务触发】开始全量处理+同步清理")
        logger.info("=" * 60)

        for processor in self.processors:
            processor.process_all_source_dirs()
        for cleaner in self.cleaners:
            cleaner.run_full_cleanup()

        logger.info("=" * 60)
        logger.info("【定时任务结束】全量处理+同步清理完成")
        logger.info("=" * 60)

    def _setup_cron_job(self):
        """将定时任务写入系统Cron表（不再保留循环）"""
        if not global_config.cron_enable:
            logger.warning("定时任务未启用，跳过Cron设置")
            return

        try:
            cron = CronTab(user='root')
            # 先删除旧任务，避免重复
            cron.remove_all(comment="YSTRM Full Task")
            
            # 构造在容器内能独立执行的命令
            cron_command = (
                "/usr/local/bin/python -c 'import sys; "
                "sys.path.append(\"/app\"); "
                "from main import YSTRM; "
                "app = YSTRM(); "
                "app._run_full_task()'"
            )
            
            job = cron.new(command=cron_command, comment="YSTRM Full Task")
            job.setall(global_config.cron_expression)
            cron.write() # 将任务持久化到系统crontab

            logger.info("=" * 50)
            logger.info("定时任务已成功设置到系统Cron表")
            logger.info(f"  - Cron表达式: {global_config.cron_expression}")
            logger.info(f"  - 执行命令: {cron_command}")
            logger.info("=" * 50)

        except Exception as e:
            logger.error(f"设置定时任务失败：{str(e)}", exc_info=True)
            raise

    def _start_real_time_monitor(self):
        """启动实时监控（功能不变）"""
        if not global_config.real_time_monitor:
            logger.info("实时监控已禁用，不启动")
            return

        logger.info("=" * 60)
        logger.info("【实时监控启动】开始监听源目录变化")
        
        for idx, (processor, cleaner) in enumerate(zip(self.processors, self.cleaners)):
            event_handler = RealTimeHandler(processor, cleaner)
            observer = Observer()
            for source_dir in processor.source_dirs:
                if os.path.exists(source_dir):
                    observer.schedule(event_handler, path=source_dir, recursive=True)
                    logger.info(f"  - 监控[{idx}]已添加目录: {source_dir}")
                else:
                    logger.warning(f"  - 监控[{idx}]目录不存在，跳过: {source_dir}")
            
            if observer.emitters:
                observer.start()
                self.observers.append(observer)
                logger.info(f"  - 监控[{idx}]线程已启动")

        logger.info("【实时监控就绪】所有监听线程启动完成")
        logger.info("=" * 60)

    def start(self):
        """启动主程序"""
        logger.info("=" * 60)
        logger.info("YSTRM 服务启动中...")
        logger.info("=" * 60)

        # 1. 设置定时任务（一次性操作）
        self._setup_cron_job()
        
        # 2. 启动实时监控
        self._start_real_time_monitor()

        # 3. 主线程保持运行，以维持容器不退出
        try:
            while True:
                time.sleep(3600) # 主线程每小时唤醒一次，可以用于未来可能的健康检查
        except KeyboardInterrupt:
            logger.info("收到停止信号，服务正在关闭...")
        finally:
            # 停止实时监控线程
            for observer in self.observers:
                observer.stop()
                observer.join()
            logger.info("所有实时监控线程已停止")
            
            # 清理Cron任务（可选，但推荐）
            try:
                cron = CronTab(user='root')
                cron.remove_all(comment="YSTRM Full Task")
                cron.write()
                logger.info("已清理系统Cron表中的定时任务")
            except Exception as e:
                logger.error(f"清理Cron任务失败：{str(e)}", exc_info=True)
            
            logger.info("YSTRM 服务已关闭")

if __name__ == "__main__":
    try:
        app = YSTRM()
        # 首次启动时，先执行一次全量任务，确保初始状态正确
        logger.info("服务首次启动，执行一次全量任务...")
        app._run_full_task()
        # 然后启动长期服务
        app.start()
    except Exception as e:
        logger.critical(f"服务启动失败：{str(e)}", exc_info=True)
        exit(1)