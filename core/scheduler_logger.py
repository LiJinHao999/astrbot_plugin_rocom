"""
调度器日志记录

单独记录调度事件，便于调试和监控。
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional


class SchedulerLogger:
    """调度器日志记录器"""
    
    def __init__(self, data_dir: str, max_lines: int = 1000):
        self.log_path = os.path.join(data_dir, "scheduler_debug.log")
        self.max_lines = max_lines
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """确保日志文件存在"""
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w", encoding="utf-8") as f:
                f.write(f"# 家园订阅调度日志 - 创建于 {datetime.now().isoformat()}\n")
    
    def _rotate_if_needed(self):
        """日志文件过大时轮转（保留最新的记录）"""
        try:
            if not os.path.exists(self.log_path):
                return
            
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            if len(lines) > self.max_lines:
                with open(self.log_path, "w", encoding="utf-8") as f:
                    f.write(f"# 日志轮转于 {datetime.now().isoformat()}\n")
                    f.writelines(lines[-self.max_lines:])
        except Exception:
            pass
    
    def log(self, event_type: str, sub_key: str = "", data: Optional[Dict[str, Any]] = None):
        """
        记录调度事件
        
        Args:
            event_type: 事件类型（check_scheduled, check_executed, result等）
            sub_key: 订阅key
            data: 附加数据
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                "time": timestamp,
                "type": event_type,
                "sub": sub_key,
                "data": data or {}
            }
            
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
            self._rotate_if_needed()
        except Exception:
            pass
