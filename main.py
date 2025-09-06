import time
import os
from threading import Thread
from crontab import CronTab
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.logger import logger
from app.config import global_config
from app.file_processor import FileProcessor
from app.sync_cleaner import SyncCleaner

# -------------------------- 实时监控事件处理器（不变） --------------------------
class RealTimeHandler(FileSystemEventHandler):
    def __init__(self, processor: FileProcessor, cleaner: SyncCleaner):
        self.processor = processor
        self.cleaner = cleaner

    def _get_target_file(self, source_file: str) -> str:
        for source_dir in self.processor.source_dirs:
            if source_file.startswith(source_dir):
                rel_path = os.path.relpath(source_file, source_dir)
                if os.path.splitext(source_file)[1].lower() in self.processor.video_exts:
                    return os.path.join(self.processor.dest_dir, rel_path.replace(os.path.splitext(rel_path)[1], ".strm"))
                else:
                    return os.path.join(self.processor.dest_dir, rel_path)
        return None

    def on_created(self, event):
        if not event.is_directory:
            self._process_file(event.src_path, "创建")

    def on_modified(self, event):
        if not event.is_directory:
            self._process_file(event.src_path, "修改")

    def on_deleted(self, event):
        if event.is_directory:
            logger.info(f"源目录删除，触发实时同步：{event.src_path}")
            self.cleaner.sync_source_dest()
            self.cleaner.cleanup_empty_dirs()
            return
        source_file = event.src_path
        dest_file = self._get_target_file(source_file)
        if dest_file and os.path.exists(dest_file):
            try:
                os.remove(dest_file)
                logger.info(f"实时删除无效文件（源文件已删）：{dest_file}")
                self.cleaner.cleanup_empty_dirs()
            except Exception as e:
                logger.error(f"实时删除无效文件失败：{dest_file} - {str(e)}", exc_info=True)

    def _process_file(self, source_file: str, event_type: str):
        file_ext = os.path.splitext(source_file)[1].lower()
        target_source_dir = None
        for source_dir in self.processor.source_dirs:
            if source_file.startswith(source_dir):
                target_source_dir = source_dir
                break
        if not target_source_dir:
            logger.debug(f"文件不在监控源目录内，跳过{event_type}：{source_file}")
            return
        if self.processor.create_strm and file_ext in self.processor.video_exts:
            self.processor.generate_strm(source_file, target_source_dir)
        if self.processor.copy_metadata and file_ext in self.processor.metadata_exts:
            self.processor.copy_metadata(source_file, target_source_dir)

# -------------------------- 主程序类（不变，仅路径引用已改） --------------------------
class YSTRM:
    def __init__(self):
        self.processors = [FileProcessor(conf) for conf in global_config.monitor_confs]
        self.cleaners = [SyncCleaner(conf) for conf in global_config.monitor_confs]
        self.cron_job = None
        self.observers = []

    def _run_full_task(self):
        """执行完整定时任务：文件处理 → 同步清理"""
        logger.info("=" * 60)
        logger.info("【定时任务启动】开始全量处理+同步清理")
        logger.info("=" * 60)

        for processor in self.processors:
            processor.process_all_source_dirs()
        for cleaner in self.cleaners:
            cleaner.run_full_cleanup()

        logger.info("=" * 60)
        logger.info("【定时任务结束】全量处理+同步清理完成")
        logger.info("=" * 60)

    def _start_cron(self):
        """启动定时任务（已修复：指定root用户）"""
        if not global_config.cron_enable:
            logger.warning("定时任务未启用，跳过Cron启动")
            return

        try:
            # 关键：指定user='root'，解决系统crontab用户缺失错误
            cron = CronTab(tab="", user='root')
            job = cron.new(command=self._run_full_task, comment="YSTRM Full Task")
            job.setall(global_config.cron_expression)
            self.cron_job = job
            logger.info(f"定时任务已加载：Cron表达式 = {global_config.cron_expression}")

            while True:
                cron.run_pending()
                time.sleep(1)
        except Exception as e:
            logger.error(f"定时任务启动失败：{str(e)}", exc_info=True)
            raise

    def _start_real_time_monitor(self):
        """启动实时监控（开关由real_time_monitor控制）"""
        if not global_config.real_time_monitor:
            logger.info("实时监控已禁用（real_time_monitor: False），不启动")
            return

        logger.info("=" * 60)
        logger.info("【实时监控启动】开始监听源目录变化")
        logger.info("=" * 60)

        for idx, (processor, cleaner, conf) in enumerate(zip(
            self.processors, self.cleaners, global_config.monitor_confs
        )):
            event_handler = RealTimeHandler(processor, cleaner)
            observer = Observer()
            for source_dir in processor.source_dirs:
                if os.path.exists(source_dir):
                    observer.schedule(event_handler, path=source_dir, recursive=True)
                    logger.info(f"实时监控[{idx}]已添加目录：{source_dir}")
                else:
                    logger.warning(f"实时监控[{idx}]目录不存在，跳过：{source_dir}")
            observer.start()
            self.observers.append(observer)
            logger.info(f"实时监控[{idx}]线程已启动")

        logger.info("=" * 60)
        logger.info("【实时监控就绪】所有监听线程启动完成")
        logger.info("=" * 60)

    def start(self):
        """启动主程序（定时任务+实时监控）"""
        logger.info("=" * 60)
        logger.info("YSTRM 服务启动中...")
        logger.info("=" * 60)

        # 启动定时任务线程
        cron_thread = Thread(target=self._start_cron, daemon=True)
        cron_thread.start()
        logger.info("定时任务线程已启动")

        # 启动实时监控线程
        rt_thread = Thread(target=self._start_real_time_monitor, daemon=True)
        rt_thread.start()

        # 主线程保持运行
        try:
            while True:
                # 检查实时监控线程状态（异常重启）
                for observer in self.observers:
                    if not observer.is_alive():
                        logger.error("实时监控线程异常退出，尝试重启...")
                        observer.start()
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("收到停止信号，服务正在关闭...")
            # 停止实时监控线程
            for observer in self.observers:
                observer.stop()
                observer.join()
            logger.info("所有实时监控线程已停止")
        finally:
            logger.info("YSTRM 服务已关闭")

if __name__ == "__main__":
    try:
        app = YSTRM()
        app.start()
    except Exception as e:
        logger.critical(f"服务启动失败：{str(e)}", exc_info=True)
        exit(1)
