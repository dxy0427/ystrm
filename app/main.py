import time
import os
from threading import Thread
from crontab import CronTab
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from logger import logger
from config import global_config
from file_processor import FileProcessor
from sync_cleaner import SyncCleaner

# -------------------------- 新增：实时监控事件处理器 --------------------------
class RealTimeHandler(FileSystemEventHandler):
    """实时监控事件处理器：响应文件创建/修改/删除，同步处理"""
    def __init__(self, processor: FileProcessor, cleaner: SyncCleaner):
        self.processor = processor  # 复用文件生成/复制逻辑
        self.cleaner = cleaner      # 复用同步清理逻辑

    def _get_target_file(self, source_file: str) -> str:
        """根据源文件路径，计算目标目录的对应文件路径（保留相对结构）"""
        for source_dir in self.processor.source_dirs:
            if source_file.startswith(source_dir):
                rel_path = os.path.relpath(source_file, source_dir)
                # 视频文件→对应STRM，其他文件→原后缀
                if os.path.splitext(source_file)[1].lower() in self.processor.video_exts:
                    return os.path.join(self.processor.dest_dir, rel_path.replace(os.path.splitext(rel_path)[1], ".strm"))
                else:
                    return os.path.join(self.processor.dest_dir, rel_path)
        return None

    def on_created(self, event):
        """文件/目录创建时触发：生成STRM/复制元数据"""
        if event.is_directory:
            return  # 忽略目录创建（定时/实时清理会处理空目录）
        source_file = event.src_path
        self._process_file(source_file, "创建")

    def on_modified(self, event):
        """文件修改时触发：更新STRM/元数据（增量处理）"""
        if event.is_directory:
            return  # 忽略目录修改
        source_file = event.src_path
        self._process_file(source_file, "修改")

    def on_deleted(self, event):
        """文件/目录删除时触发：同步删除目标目录对应内容"""
        if event.is_directory:
            # 目录删除：触发一次源目标同步（清理无效目录）
            logger.info(f"源目录删除，触发实时同步：{event.src_path}")
            self.cleaner.sync_source_dest()
            self.cleaner.cleanup_empty_dirs()
            return

        # 文件删除：删除目标目录对应文件
        source_file = event.src_path
        dest_file = self._get_target_file(source_file)
        if dest_file and os.path.exists(dest_file):
            try:
                os.remove(dest_file)
                logger.info(f"实时删除无效文件（源文件已删）：{dest_file}")
                # 删完文件后检查是否为空目录，顺便清理
                self.cleaner.cleanup_empty_dirs()
            except Exception as e:
                logger.error(f"实时删除无效文件失败：{dest_file} - {str(e)}", exc_info=True)
        else:
            logger.debug(f"源文件删除，目标文件不存在，跳过：{source_file}")

    def _process_file(self, source_file: str, event_type: str):
        """处理文件创建/修改：生成STRM或复制元数据（复用增量逻辑）"""
        file_ext = os.path.splitext(source_file)[1].lower()
        target_source_dir = None
        # 找到文件所属的源目录（多源目录匹配）
        for source_dir in self.processor.source_dirs:
            if source_file.startswith(source_dir):
                target_source_dir = source_dir
                break
        if not target_source_dir:
            logger.debug(f"文件不在监控源目录内，跳过{event_type}：{source_file}")
            return

        # 处理视频文件→生成STRM
        if self.processor.create_strm and file_ext in self.processor.video_exts:
            self.processor.generate_strm(source_file, target_source_dir)
        # 处理元数据文件→复制
        if self.processor.copy_metadata and file_ext in self.processor.metadata_exts:
            self.processor.copy_metadata(source_file, target_source_dir)

# -------------------------- 主程序类（原有逻辑+实时监控） --------------------------
class LibrarySTRM:
    def __init__(self):
        self.processors = [FileProcessor(conf) for conf in global_config.monitor_confs]
        self.cleaners = [SyncCleaner(conf) for conf in global_config.monitor_confs]
        self.cron_job = None
        self.observers = []  # 存储实时监控的Observer线程

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
        """启动定时任务调度"""
        if not global_config.cron_enable:
            logger.warning("定时任务未启用，跳过Cron启动")
            return

        try:
            cron = CronTab(tab="", user=False)
            job = cron.new(command=self._run_full_task, comment="LibrarySTRM Full Task")
            job.setall(global_config.cron_expression)
            self.cron_job = job
            logger.info(f"定时任务已加载：Cron表达式 = {global_config.cron_expression}")

            while True:
                cron.run_pending()
                time.sleep(1)
        except Exception as e:
            logger.error(f"定时任务启动失败：{str(e)}", exc_info=True)
            raise

    # -------------------------- 补全：实时监控启动逻辑 --------------------------
    def _start_real_time_monitor(self):
        """启动实时监控（基于watchdog，开关由real_time_monitor控制）"""
        if not global_config.real_time_monitor:
            logger.info("实时监控已禁用（real_time_monitor: False），不启动")
            return

        logger.info("=" * 60)
        logger.info("【实时监控启动】开始监听源目录变化")
        logger.info("=" * 60)

        # 为每个监控配置创建独立的监听线程（Observer）
        for idx, (processor, cleaner, conf) in enumerate(zip(
            self.processors, self.cleaners, global_config.monitor_confs
        )):
            # 创建事件处理器（关联当前配置的生成/清理逻辑）
            event_handler = RealTimeHandler(processor, cleaner)
            # 创建监听线程（Observer）
            observer = Observer()

            # 为当前配置的所有源目录添加监听（递归监听子目录）
            for source_dir in processor.source_dirs:
                if os.path.exists(source_dir):
                    observer.schedule(
                        event_handler,
                        path=source_dir,
                        recursive=True  # 递归监听所有子目录（如“国漫/斗罗大陆/s1”）
                    )
                    logger.info(f"实时监控[{idx}]已添加目录：{source_dir}")
                else:
                    logger.warning(f"实时监控[{idx}]目录不存在，跳过：{source_dir}")

            # 启动监听线程（守护线程，主程序退出时自动停止）
            observer.start()
            self.observers.append(observer)
            logger.info(f"实时监控[{idx}]线程已启动")

        logger.info("=" * 60)
        logger.info("【实时监控就绪】所有监听线程启动完成")
        logger.info("=" * 60)

    def start(self):
        """启动主程序：定时任务+实时监控（按需启动）"""
        logger.info("=" * 60)
        logger.info("LibrarySTRM 服务启动中...")
        logger.info("=" * 60)

        # 1. 启动定时任务（独立线程）
        cron_thread = Thread(target=self._start_cron, daemon=True)
        cron_thread.start()
        logger.info("定时任务线程已启动")

        # 2. 启动实时监控（按需启动，独立线程）
        rt_thread = Thread(target=self._start_real_time_monitor, daemon=True)
        rt_thread.start()

        # 3. 主线程保持运行（防止服务退出）
        try:
            while True:
                # 检查实时监控线程状态（异常退出时重启）
                for observer in self.observers:
                    if not observer.is_alive():
                        logger.error("实时监控线程异常退出，尝试重启...")
                        observer.start()
                time.sleep(3600)  # 每小时检查一次线程状态
        except KeyboardInterrupt:
            logger.info("收到停止信号，服务正在关闭...")
            # 停止所有实时监控线程
            for observer in self.observers:
                observer.stop()
                observer.join()
            logger.info("所有实时监控线程已停止")
        finally:
            logger.info("LibrarySTRM 服务已关闭")

if __name__ == "__main__":
    try:
        app = LibrarySTRM()
        app.start()
    except Exception as e:
        logger.critical(f"服务启动失败：{str(e)}", exc_info=True)
        exit(1)