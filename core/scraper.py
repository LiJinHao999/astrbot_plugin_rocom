"""
洛克王国数据爬虫模块
用于即时爬取商人信息和活动日历
"""
import asyncio
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from astrbot.api import logger


class RocomScraper:
    """洛克王国数据爬虫"""
    
    def __init__(self):
        self.url = "https://huodong2.4399.com/yxhtools/game-store"
        self._playwright = None
        self._browser = None
        self._context = None
    
    async def _ensure_browser(self):
        """确保浏览器已启动"""
        if self._browser is None:
            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
                self._context = await self._browser.new_context()
                logger.info("[Rocom Scraper] 浏览器已启动")
            except Exception as e:
                logger.error(f"[Rocom Scraper] 启动浏览器失败: {e}")
                raise
    
    async def close(self):
        """关闭浏览器"""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            self._browser = None
            self._context = None
            self._playwright = None
            logger.info("[Rocom Scraper] 浏览器已关闭")
        except Exception as e:
            logger.error(f"[Rocom Scraper] 关闭浏览器失败: {e}")
    
    async def get_merchant_info(self) -> Optional[Dict]:
        """爬取商人信息"""
        page = None
        try:
            logger.info("[Rocom Scraper] 开始爬取商人信息")
            await self._ensure_browser()
            page = await self._context.new_page()
            
            logger.info(f"[Rocom Scraper] 正在访问: {self.url}")
            await page.goto(self.url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            logger.info("[Rocom Scraper] 页面加载完成")
            
            time_slot_buttons = await page.query_selector_all('.time-slot-btn')
            logger.info(f"[Rocom Scraper] 找到 {len(time_slot_buttons)} 个时间段按钮")
            
            all_goods = []
            for i, button in enumerate(time_slot_buttons):
                try:
                    button_text = (await button.text_content() or "").strip()
                    logger.info(f"[Rocom Scraper] 点击时间段按钮: {button_text}")
                    await button.click()
                    await page.wait_for_timeout(1000)
                    
                    from datetime import datetime, time as dt_time, timezone, timedelta
                    import re
                    time_match = re.match(r'(\d+):(\d+)-(\d+):(\d+)', button_text)
                    start_ts, end_ts = None, None
                    if time_match:
                        start_hour, start_min = int(time_match.group(1)), int(time_match.group(2))
                        end_hour, end_min = int(time_match.group(3)), int(time_match.group(4))
                        cn_tz = timezone(timedelta(hours=8))
                        now = datetime.now(cn_tz)
                        start_dt = datetime.combine(now.date(), dt_time(start_hour, start_min), tzinfo=cn_tz)
                        end_dt = datetime.combine(now.date(), dt_time(end_hour, end_min), tzinfo=cn_tz)
                        if end_hour == 0:
                            end_dt += timedelta(days=1)
                        start_ts = int(start_dt.timestamp() * 1000)
                        end_ts = int(end_dt.timestamp() * 1000)
                    
                    visible_goods = await page.query_selector_all('.goods-list-box:not([style*="display: none"]) .goods-row')
                    logger.info(f"[Rocom Scraper] 时间段 {button_text} 找到 {len(visible_goods)} 个可见商品")
                    
                    for goods in visible_goods:
                        try:
                            name_elem = await goods.query_selector('.goods-row__name')
                            if not name_elem:
                                continue
                            name = (await name_elem.text_content() or "").strip()
                            if not name:
                                continue
                            
                            icon_url = ""
                            try:
                                pic_elem = await goods.query_selector('.goods-row__pic img')
                                if pic_elem:
                                    icon_url = await pic_elem.get_attribute('src') or ""
                            except:
                                pass
                            
                            price_elem = await goods.query_selector('.goods-row__price span')
                            price_text = (await price_elem.text_content()).strip() if price_elem else "0"
                            price = int(price_text.replace(',', '').replace('W', '0000')) if price_text else 0
                            
                            limit_elem = await goods.query_selector('.goods-row__limit')
                            limit_text = (await limit_elem.text_content()).strip() if limit_elem else ""
                            limit = int(''.join(filter(str.isdigit, limit_text))) if limit_text else 0
                            
                            countdown_elem = await goods.query_selector('.goods-countdown')
                            countdown = (await countdown_elem.text_content()).strip() if countdown_elem else ""
                            is_active = countdown and "已结束" not in countdown
                            
                            rare_elem = await goods.query_selector('.goods-row__rare')
                            is_rare = rare_elem is not None
                            
                            item = {
                                "name": name,
                                "price": price,
                                "limit": limit,
                                "is_active": is_active,
                                "is_rare": is_rare,
                                "icon_url": icon_url,
                                "start_time": start_ts,
                                "end_time": end_ts
                            }
                            all_goods.append(item)
                            
                        except Exception as e:
                            logger.warning(f"[Rocom Scraper] 提取单个商品失败: {e}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"[Rocom Scraper] 处理时间段 {i+1} 失败: {e}")
                    continue
            
            logger.info(f"[Rocom Scraper] 成功提取 {len(all_goods)} 个有效商品")
            
            return {
                "merchantActivities": [{
                    "name": "远行商人",
                    "get_props": all_goods,
                    "get_extra_props": [],
                    "get_pets": []
                }],
                "random_goods": []
            }
            
        except PlaywrightTimeout as e:
            logger.error(f"[Rocom Scraper] 页面加载超时: {e}")
            return None
        except Exception as e:
            logger.error(f"[Rocom Scraper] 爬取商人信息失败: {e}")
            return None
        finally:
            if page:
                await page.close()
    
    async def get_activities_info(self) -> Optional[Dict]:
        """爬取活动日历信息"""
        page = None
        try:
            logger.info("[Rocom Scraper] 开始爬取活动日历")
            await self._ensure_browser()
            page = await self._context.new_page()
            
            logger.info(f"[Rocom Scraper] 正在访问: {self.url}")
            await page.goto(self.url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            logger.info("[Rocom Scraper] 页面加载完成")
            
            tab2 = await page.query_selector('.tab-item.tab-2')
            if tab2:
                logger.info("[Rocom Scraper] 切换到活动标签页")
                await tab2.click()
                await page.wait_for_timeout(3000)
            else:
                logger.warning("[Rocom Scraper] 未找到活动标签页")
            
            activity_cards = await page.query_selector_all('.hd-card')
            logger.info(f"[Rocom Scraper] 找到 {len(activity_cards)} 个活动卡片")
            
            activities = []
            for card in activity_cards:
                try:
                    title_elem = await card.query_selector('.hd-card__title-text')
                    if not title_elem:
                        continue
                    name = (await title_elem.text_content() or "").strip()
                    if not name:
                        continue
                    
                    full_text = (await card.text_content() or "").strip()
                    
                    import re
                    date_match = re.search(r'活动时间[：:]\s*(\d+月\d+日.*?~.*?\d+月\d+日.*?)(?:\n|活动相关|$)', full_text)
                    date_range = date_match.group(1).strip() if date_match else ""
                    
                    start_date, end_date = None, None
                    if date_range:
                        from datetime import datetime
                        parts = date_range.split('~')
                        if len(parts) == 2:
                            start_str = parts[0].strip()
                            end_str = parts[1].strip()
                            
                            year = datetime.now().year
                            try:
                                start_match = re.match(r'(\d+)月(\d+)日(?:\s+(\d+):(\d+))?', start_str)
                                if start_match:
                                    month, day = int(start_match.group(1)), int(start_match.group(2))
                                    hour = int(start_match.group(3)) if start_match.group(3) else 0
                                    minute = int(start_match.group(4)) if start_match.group(4) else 0
                                    start_date = datetime(year, month, day, hour, minute)
                                    start_date = int(start_date.timestamp())
                                
                                end_match = re.match(r'(\d+)月(\d+)日(?:\s+(\d+):(\d+))?', end_str)
                                if end_match:
                                    month, day = int(end_match.group(1)), int(end_match.group(2))
                                    hour = int(end_match.group(3)) if end_match.group(3) else 23
                                    minute = int(end_match.group(4)) if end_match.group(4) else 59
                                    end_date = datetime(year, month, day, hour, minute)
                                    end_date = int(end_date.timestamp())
                            except:
                                pass
                    
                    if not start_date or not end_date:
                        continue
                    
                    rewards = ""
                    reward_match = re.search(r'活动相关[：:]\s*(.+?)(?:\n|$)', full_text)
                    if reward_match:
                        rewards = reward_match.group(1).strip()
                    
                    activity = {
                        'name': name,
                        'start_time': start_date,
                        'end_time': end_date,
                        'start_date': date_range.split('~')[0].strip() if '~' in date_range else '',
                        'end_date': date_range.split('~')[1].strip() if '~' in date_range else '',
                        'rewards': rewards
                    }
                    
                    activities.append(activity)
                except Exception as e:
                    logger.warning(f"[Rocom Scraper] 提取单个活动失败: {e}")
                    continue
            
            logger.info(f"[Rocom Scraper] 成功提取 {len(activities)} 个有效活动")
            return {'activities': activities}
            
        except PlaywrightTimeout as e:
            logger.error(f"[Rocom Scraper] 页面加载超时: {e}")
            return None
        except Exception as e:
            logger.error(f"[Rocom Scraper] 爬取活动信息失败: {e}")
            return None
        finally:
            if page:
                await page.close()
