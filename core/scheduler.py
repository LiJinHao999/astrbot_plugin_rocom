"""
家园订阅智能调度器

基于倒计时的按需查询，避免无效轮询。
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple


class HomeScheduler:
    """家园订阅调度计算器"""
    
    # 成熟后再次查询的间隔（秒）
    RECHECK_AFTER_READY = 3 * 3600  # 3小时
    
    # 睡眠时间段（小时）
    SLEEP_START_HOUR = 0
    SLEEP_END_HOUR = 6
    
    # 农场浇水最大加速比例
    GARDEN_MAX_SPEEDUP = 0.2
    
    # 精灵灵感延后查询的缓冲时间（秒）
    INSPIRATION_BUFFER = 300  # 5分钟，确保查到成熟状态
    
    @staticmethod
    def calculate_next_check_time(
        kind: str,
        items: List[Dict[str, Any]],
        current_time: Optional[int] = None
    ) -> Optional[int]:
        """
        计算下次应该查询的时间戳
        
        Args:
            kind: 'garden' 或 'inspiration'
            items: 当前状态的物品列表
            current_time: 当前时间戳（可选，默认为now）
        
        Returns:
            下次查询的时间戳，如果无需查询返回 None
        """
        if current_time is None:
            current_time = int(time.time())
        
        if not items:
            return None
        
        # 收集所有未完成项目的完成时间
        ready_times = []
        has_ready = False
        
        for item in items:
            if kind == "garden":
                if item.get("ready"):
                    has_ready = True
                    continue
                ready_at = item.get("readyAt")
            else:  # inspiration
                if item.get("inspireReady"):
                    has_ready = True
                    continue
                ready_at = item.get("readyAt")
            
            if ready_at:
                ready_times.append(int(ready_at))
        
        # 如果没有未完成项，且有已完成项，3小时后再查
        if not ready_times:
            if has_ready:
                return current_time + HomeScheduler.RECHECK_AFTER_READY
            return None
        
        # 找到最早完成的时间
        earliest_ready = min(ready_times)
        remaining = max(0, earliest_ready - current_time)
        
        if kind == "garden":
            # 农场：根据剩余时间推测作物类型，按比例计算提前时间
            if remaining > 16 * 3600:
                # 24h作物：单次浇水减少2h
                crop_duration = 24 * 3600
                water_reduce = 2 * 3600
            elif remaining > 8 * 3600:
                # 12h作物：单次浇水减少1h
                crop_duration = 12 * 3600
                water_reduce = 3600
            else:
                # 6h作物：单次浇水减少30min
                crop_duration = 6 * 3600
                water_reduce = 1800
            
            if remaining > water_reduce:
                # 时间较长：按比例提前 1.5 × (剩余时间/作物时长) × 单次浇水减少时间
                ratio = remaining / crop_duration
                advance_time = int(1.5 * water_reduce * ratio)
                next_check = earliest_ready - advance_time
            else:
                # 时间较短：延后5分钟，保证查到成熟
                next_check = earliest_ready + 300
        else:
            # 精灵灵感：延后5分钟确保已成熟
            next_check = earliest_ready + HomeScheduler.INSPIRATION_BUFFER
        
        # 不能早于当前时间
        next_check = max(next_check, current_time + 60)
        
        # 处理睡眠时间
        next_check = HomeScheduler.adjust_for_sleep_time(next_check)
        
        return next_check
    
    @staticmethod
    def adjust_for_sleep_time(timestamp: int) -> int:
        """
        调整查询时间以避开睡眠时段（0:00-6:00）
        
        如果查询时间落在睡眠时段，推迟到当天 6:00
        """
        dt = datetime.fromtimestamp(timestamp)
        
        if HomeScheduler.SLEEP_START_HOUR <= dt.hour < HomeScheduler.SLEEP_END_HOUR:
            # 推迟到当天 6:00
            wake_time = dt.replace(hour=HomeScheduler.SLEEP_END_HOUR, minute=0, second=0, microsecond=0)
            return int(wake_time.timestamp())
        
        # 如果是 23:xx，可能跨天进入睡眠时段，也推迟
        if dt.hour == 23:
            remaining_seconds = (24 - dt.hour) * 3600 - dt.minute * 60 - dt.second
            if remaining_seconds < 3600:  # 不到1小时就到0点
                next_day = dt + timedelta(days=1)
                wake_time = next_day.replace(hour=HomeScheduler.SLEEP_END_HOUR, minute=0, second=0, microsecond=0)
                return int(wake_time.timestamp())
        
        return timestamp
    
    @staticmethod
    def should_check_subscription(
        sub: Dict[str, Any],
        current_time: Optional[int] = None
    ) -> bool:
        """
        判断订阅是否应该立即检查
        
        Args:
            sub: 订阅对象，包含 next_check_time 字段
            current_time: 当前时间戳
        
        Returns:
            是否应该检查
        """
        if current_time is None:
            current_time = int(time.time())
        
        next_check = sub.get("next_check_time")
        if next_check is None:
            return True  # 没有记录下次检查时间，立即检查
        
        return current_time >= next_check
    
    @staticmethod
    def get_next_wake_time(subscriptions: Dict[str, Dict[str, Any]]) -> Optional[int]:
        """
        获取所有订阅中最近的检查时间
        
        Args:
            subscriptions: 所有订阅的字典
        
        Returns:
            最近的检查时间戳，如果没有订阅返回 None
        """
        if not subscriptions:
            return None
        
        next_times = []
        current_time = int(time.time())
        
        for sub in subscriptions.values():
            next_check = sub.get("next_check_time")
            if next_check is None:
                # 没有记录，立即检查
                return current_time
            if next_check <= current_time:
                # 已过期（可能因进程重启错过），立即检查
                return current_time
            next_times.append(next_check)
        
        if not next_times:
            return None
        
        return min(next_times)
    
    @staticmethod
    def calculate_sleep_duration(
        subscriptions: Dict[str, Dict[str, Any]],
        default_interval: int = 3600,
        max_sleep: int = 3600
    ) -> int:
        """
        计算应该 sleep 多久
        
        Args:
            subscriptions: 所有订阅
            default_interval: 没有订阅时的默认间隔（秒）
            max_sleep: 最大 sleep 时间（秒）
        
        Returns:
            应该 sleep 的秒数
        """
        if not subscriptions:
            return default_interval
        
        next_wake = HomeScheduler.get_next_wake_time(subscriptions)
        if next_wake is None:
            return default_interval
        
        current_time = int(time.time())
        sleep_duration = max(60, next_wake - current_time)  # 至少sleep 60秒
        
        return min(sleep_duration, max_sleep)
