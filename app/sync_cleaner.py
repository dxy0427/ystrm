import os, shutil
from typing import List
from .logger import logger
from .config import global_config
class SyncCleaner:
    def __init__(self, m_conf):
        self.source_dirs, self.dest_dir, self.library_dir = self._normalize_dirs(m_conf["source_dir"]), self._normalize_dir(m_conf["dest_dir"]), self._normalize_dir(m_conf["library_dir"])
        self.video_exts, self.metadata_exts = m_conf["video_extensions"], m_conf["metadata_extensions"]
    def _normalize_dir(self, p:str)->str: return os.path.abspath(p).rstrip('/')+'/'
    def _normalize_dirs(self, d:List[str])->List[str]: return [self._normalize_dir(i) for i in d]
    def _is_source_file_exists(self, rel_p:str)->bool:
        f_n, f_e = os.path.splitext(rel_p)
        if f_e.lower() == ".strm":
            for v_e in self.video_exts:
                if os.path.exists(os.path.join(self.library_dir, f"{f_n}{v_e.lower()}")): return True
            return False
        return os.path.exists(os.path.join(self.library_dir, rel_p))
    
    def sync_source_dest(self):
        if not global_config.sync_source_dest or not os.path.exists(self.dest_dir): logger.info("未启用源目标同步，跳过"); return
        logger.info("="*50 + "\n开始源目标目录强同步（删除无效文件/目录）")
        src_subdirs = set()
        for s_d in self.source_dirs:
            for r,ds,_ in os.walk(s_d):
                for d in ds: src_subdirs.add(os.path.relpath(os.path.join(r,d), self.library_dir))
        for r,ds,fs in os.walk(self.dest_dir, topdown=False):
            for f in fs:
                d_f, rel_p = os.path.join(r,f), os.path.relpath(os.path.join(r,f), self.dest_dir)
                
                # 【新功能】如果开启了保留元数据，并且当前文件是元数据，则跳过删除检查
                if global_config.preserve_extra_metadata and os.path.splitext(f)[1].lower() in self.metadata_exts:
                    continue

                if not self._is_source_file_exists(rel_p):
                    try: os.remove(d_f); logger.info(f"删除无效文件（源文件已删）：{d_f}")
                    except Exception as e: logger.error(f"删除无效文件失败：{d_f} - {e}", exc_info=True)
            for d_n in ds:
                d_sub, sub_rel_p = os.path.join(r,d_n), os.path.relpath(os.path.join(r,d_n), self.dest_dir)
                if not os.listdir(d_sub) and sub_rel_p not in src_subdirs:
                    try: os.rmdir(d_sub); logger.info(f"删除无效空目录（源目录已删）：{d_sub}")
                    except Exception as e: logger.error(f"删除无效空目录失败：{d_sub} - {e}", exc_info=True)
        logger.info("源目标目录强同步完成\n" + "="*50)

    # 【新功能】反向同步元数据
    def sync_metadata_back_to_source(self):
        if not global_config.sync_metadata_to_source: logger.info("未启用元数据反向同步，跳过"); return
        logger.info("="*50 + "\n开始反向同步元数据（从目标到源）")
        
        for root, _, files in os.walk(self.dest_dir):
            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext not in self.metadata_exts: continue

                dest_file = os.path.join(root, file)
                rel_path = os.path.relpath(dest_file, self.dest_dir)
                source_file = os.path.join(self.library_dir, rel_path)

                # 如果源文件不存在，或者目标文件比源文件新，则复制
                if not os.path.exists(source_file) or os.path.getmtime(dest_file) > os.path.getmtime(source_file):
                    try:
                        os.makedirs(os.path.dirname(source_file), exist_ok=True)
                        shutil.copy2(dest_file, source_file)
                        logger.info(f"反向同步元数据成功：{dest_file} -> {source_file}")
                    except Exception as e:
                        logger.error(f"反向同步元数据失败：{source_file} - {e}", exc_info=True)
        logger.info("反向同步元数据完成\n" + "="*50)

    def cleanup_empty_dirs(self):
        if not global_config.cleanup_empty_dirs or not os.path.exists(self.dest_dir): logger.info("未启用空目录清理，跳过"); return
        logger.info("="*50 + "\n开始清理目标目录空文件夹")
        changed = True
        while changed:
            changed = False
            for r,ds,_ in os.walk(self.dest_dir, topdown=False):
                for d_n in ds:
                    d_p = os.path.join(r,d_n)
                    if not os.listdir(d_p):
                        try: os.rmdir(d_p); logger.info(f"删除空目录：{d_p}"); changed = True
                        except Exception as e: logger.error(f"删除空目录失败：{d_p} - {e}", exc_info=True)
        logger.info("空目录清理完成\n" + "="*50)
        
    def run_full_cleanup(self):
        # 调整执行顺序，先反向同步，再进行清理
        self.sync_metadata_back_to_source()
        self.sync_source_dest()
        self.cleanup_empty_dirs()