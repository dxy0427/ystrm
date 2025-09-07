import os, shutil, time
from typing import List
from .logger import logger
from .config import global_config
class FileProcessor:
    def __init__(self, m_conf):
        self.source_dirs, self.dest_dir, self.library_dir = self._normalize_dirs(m_conf["source_dir"]), self._normalize_dir(m_conf["dest_dir"]), self._normalize_dir(m_conf["library_dir"])
        self.video_exts, self.metadata_exts = m_conf["video_extensions"], m_conf["metadata_extensions"]
        self.create_strm, self.enable_copy_metadata = m_conf.get("create_strm",True), m_conf.get("copy_metadata",True)
    def _normalize_dir(self, p:str)->str: return os.path.abspath(p).rstrip('/')+'/'
    def _normalize_dirs(self, d:List[str])->List[str]: return [self._normalize_dir(i) for i in d]
    def _get_relative_path(self, f_p:str, b_d:str)->str: return os.path.relpath(f_p, b_d)
    
    # 【升级】比对逻辑现在同时检查修改时间和文件大小
    def _should_process(self, source_file: str, dest_file: str) -> bool:
        if not os.path.exists(dest_file): return True
        if global_config.overwrite_existing: return True
        # 只要修改时间或文件大小任一不匹配，就应该处理
        return (os.path.getmtime(source_file) > os.path.getmtime(dest_file) or
                os.path.getsize(source_file) != os.path.getsize(dest_file))

    def generate_strm(self, s_v:str, b_d:str):
        rel_p = self._get_relative_path(s_v, b_d)
        d_strm = os.path.splitext(os.path.join(self.dest_dir, rel_p))[0] + ".strm"
        # 传递源文件路径给 _should_process
        if not self._should_process(s_v, d_strm): 
            logger.debug(f"STRM已存在且未更新，跳过：{d_strm}"); return
        d_strm_dir = os.path.dirname(d_strm)
        os.makedirs(d_strm_dir, exist_ok=True)
        try:
            s_mt = os.path.getmtime(s_v)
            strm_c = os.path.join(b_d, rel_p)
            with open(d_strm,"w",encoding="utf-8") as f: f.write(strm_c)
            os.utime(d_strm, (s_mt,s_mt)); logger.info(f"STRM生成/更新成功：{d_strm} → 指向：{strm_c}")
        except Exception as e: logger.error(f"STRM生成失败：{d_strm} - {e}", exc_info=True)

    def copy_metadata(self, s_m:str, b_d:str):
        rel_p = self._get_relative_path(s_m, b_d)
        d_meta = os.path.join(self.dest_dir, rel_p)
        # 传递源文件路径给 _should_process
        if not self._should_process(s_m, d_meta): 
            logger.debug(f"元数据已存在且未更新，跳过：{d_meta}"); return
        d_meta_dir = os.path.dirname(d_meta)
        os.makedirs(d_meta_dir, exist_ok=True)
        try: 
            shutil.copy2(s_m, d_meta); logger.info(f"元数据复制/更新成功：{d_meta}")
        except Exception as e: logger.error(f"元数据复制失败：{d_meta} - {e}", exc_info=True)

    def process_single_dir(self, s_d:str):
        if not os.path.exists(s_d): logger.warning(f"源目录不存在，跳过：{s_d}"); return
        logger.info(f"开始处理源目录：{s_d}")
        inter = global_config.file_processing_interval
        for r,_,fs in os.walk(s_d):
            for f in fs:
                s_f, f_ext = os.path.join(r,f), os.path.splitext(f)[1].lower()
                if self.create_strm and f_ext in self.video_exts: self.generate_strm(s_f, self.library_dir)
                if self.enable_copy_metadata and f_ext in self.metadata_exts: self.copy_metadata(s_f, self.library_dir)
                if inter > 0: time.sleep(inter)
        logger.info(f"源目录处理完成：{s_d}")
    def process_all_source_dirs(self):
        if not global_config.full_generate: logger.info("未启用全量生成，跳过文件处理"); return
        logger.info("="*50 + "\n开始全量文件处理（生成STRM+复制元数据）")
        for s_d in self.source_dirs: self.process_single_dir(s_d)
        logger.info("全量文件处理完成\n" + "="*50)