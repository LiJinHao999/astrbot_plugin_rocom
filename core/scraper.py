"""
洛克王国数据查询模块
通过 4399 活动工具平台 API 获取商人信息和活动日历
"""
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from astrbot.api import logger

_CN_TZ = timezone(timedelta(hours=8))
_BASE_URL = "https://huodong2.4399.com/n/comm/tool/api.php"
_TOOL_ID = "11"
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_TIMEOUT = 15.0

# batch 编号 → 时间段
_BATCH_SLOTS = {
    1: ("08:00", "12:00"),
    2: ("12:00", "16:00"),
    3: ("16:00", "20:00"),
    4: ("20:00", "24:00"),
}


class RocomScraper:
    """洛克王国数据查询（httpx 直连 API）"""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT)

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ── 远行商人 ─────────────────────────────────────────────

    async def get_merchant_info(self) -> Optional[Dict]:
        """查询远行商人商品列表"""
        try:
            logger.info("[Rocom Scraper] 请求远行商人 API")
            await self._ensure_client()
            resp = await self._client.post(
                _BASE_URL, params={"path": "lkyxGood/index", "tool_id": _TOOL_ID}
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("success"):
                logger.warning(f"[Rocom Scraper] 商人 API 返回失败: {data.get('msg')}")
                return None

            all_goods = self._parse_merchant_list(data.get("list") or [])
            logger.info(f"[Rocom Scraper] 成功获取 {len(all_goods)} 个商品")
            return {
                "merchantActivities": [{
                    "name": "远行商人",
                    "get_props": all_goods,
                    "get_extra_props": [],
                    "get_pets": [],
                }],
                "random_goods": [],
            }
        except Exception as e:
            logger.error(f"[Rocom Scraper] 获取商人信息失败: {e}")
            return None

    def _parse_merchant_list(self, batch_list: List[Dict]) -> List[Dict]:
        """解析 API 返回的商品批次列表"""
        all_goods: List[Dict] = []
        for batch_obj in batch_list:
            items = batch_obj.get("items") or []
            for item in items:
                parsed = self._parse_merchant_item(item)
                if parsed:
                    all_goods.append(parsed)
        return all_goods

    def _parse_merchant_item(self, item: Dict) -> Optional[Dict]:
        """将单个 API 商品条目转换为插件内部格式"""
        name = (item.get("name") or "").strip()
        if not name:
            return None

        start_ms = self._datetime_str_to_ms(item.get("stime"))
        end_ms = self._datetime_str_to_ms(item.get("etime"))

        # 判断当前是否在有效期内
        now_ms = int(datetime.now(_CN_TZ).timestamp() * 1000)
        is_active = True
        if start_ms is not None and end_ms is not None:
            is_active = start_ms <= now_ms < end_ms

        price_raw = item.get("price") or "0"
        try:
            price = int(price_raw)
        except (ValueError, TypeError):
            price = 0

        limit_raw = item.get("buy_limit") or "0"
        try:
            limit = int(limit_raw)
        except (ValueError, TypeError):
            limit = 0

        return {
            "name": name,
            "price": price,
            "limit": limit,
            "buy_limit_num": limit,
            "is_active": is_active,
            "is_rare": str(item.get("is_worth")) == "1",
            "icon_url": item.get("image") or "",
            "start_time": start_ms,
            "end_time": end_ms,
        }

    # ── 活动日历 ─────────────────────────────────────────────

    async def get_activities_info(self) -> Optional[Dict]:
        """查询活动日历列表"""
        try:
            logger.info("[Rocom Scraper] 请求活动日历 API")
            await self._ensure_client()
            resp = await self._client.post(
                _BASE_URL, params={"path": "lkyxAct/index", "tool_id": _TOOL_ID}
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("success"):
                logger.warning(f"[Rocom Scraper] 活动 API 返回失败: {data.get('msg')}")
                return None

            activities = self._parse_activity_list(data.get("list") or [])
            logger.info(f"[Rocom Scraper] 成功获取 {len(activities)} 个活动")
            return {"activities": activities}
        except Exception as e:
            logger.error(f"[Rocom Scraper] 获取活动信息失败: {e}")
            return None

    def _parse_activity_list(self, raw_list: List[Dict]) -> List[Dict]:
        """解析活动列表"""
        activities: List[Dict] = []
        for item in raw_list:
            parsed = self._parse_activity_item(item)
            if parsed:
                activities.append(parsed)
        return activities

    def _parse_activity_item(self, item: Dict) -> Optional[Dict]:
        """将单个 API 活动条目转换为插件内部格式"""
        name = (item.get("name") or "").strip()
        if not name:
            return None

        start_ts = self._datetime_str_to_ts(item.get("stime"))
        end_ts = self._datetime_str_to_ts(item.get("etime"))
        if not start_ts and not end_ts:
            return None

        # 构建日期显示文本
        start_date = self._format_date_text(item.get("stime"))
        end_date = self._format_date_text(item.get("etime"))

        # 提取奖励文本
        prizes = item.get("prizes") or []
        reward_names = [p.get("name") for p in prizes if isinstance(p, dict) and p.get("name")]
        rewards = "、".join(reward_names[:6]) if reward_names else ""

        return {
            "name": name,
            "start_time": start_ts,
            "end_time": end_ts,
            "start_date": start_date,
            "end_date": end_date,
            "rewards": rewards,
        }

    # ── 工具方法 ─────────────────────────────────────────────

    @staticmethod
    def _datetime_str_to_ms(value: Optional[str]) -> Optional[int]:
        """将 '2026-07-05 08:00:00' 格式的时间字符串转换为毫秒时间戳"""
        if not value:
            return None
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_CN_TZ)
            return int(dt.timestamp() * 1000)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _datetime_str_to_ts(value: Optional[str]) -> Optional[int]:
        """将时间字符串转换为秒级时间戳"""
        if not value:
            return None
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_CN_TZ)
            return int(dt.timestamp())
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _format_date_text(value: Optional[str]) -> str:
        """将 '2026-07-05 08:00:00' 转为 '7月5日' 格式"""
        if not value:
            return ""
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return f"{dt.month}月{dt.day}日"
        except (ValueError, TypeError):
            return ""
