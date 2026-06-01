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
            
            goods_elements = await page.query_selector_all('.goods-row')
            logger.info(f"[Rocom Scraper] 找到 {len(goods_elements)} 个商品元素")
            
            goods_list = []
            for goods in goods_elements:
                try:
                    name_elem = await goods.query_selector('.goods-row__name')
                    if not name_elem:
                        continue
                    name = (await name_elem.text_content() or "").strip()
                    if not name:
                        continue
                    
                    item = {'name': name}
                    
                    price_elem = await goods.query_selector('.goods-row__price span')
                    item['price'] = (await price_elem.text_content()).strip() if price_elem else None
                    
                    limit_elem = await goods.query_selector('.goods-row__limit')
                    item['limit'] = (await limit_elem.text_content()).strip() if limit_elem else None
                    
                    countdown_elem = await goods.query_selector('.goods-countdown')
                    item['countdown'] = (await countdown_elem.text_content()).strip() if countdown_elem else None
                    
                    tag_elements = await goods.query_selector_all('.goods-row__tags .span-item i')
                    tags = []
                    for tag in tag_elements:
                        tag_text = (await tag.text_content() or "").strip()
                        if tag_text:
                            tags.append(tag_text)
                    item['tags'] = tags
                    
                    rare_elem = await goods.query_selector('.goods-row__rare')
                    item['is_rare'] = rare_elem is not None
                    
                    goods_list.append(item)
                except Exception as e:
                    logger.warning(f"[Rocom Scraper] 提取单个商品失败: {e}")
                    continue
            
            logger.info(f"[Rocom Scraper] 成功提取 {len(goods_list)} 个商品")
            return {'goods': goods_list}
            
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
                    
                    activity = {'name': name}
                    
                    time_elem = await card.query_selector('.hd-card__time')
                    activity['time_remaining'] = (await time_elem.text_content()).strip() if time_elem else None
                    
                    date_elem = await card.query_selector('.hd-card__date')
                    activity['date_range'] = (await date_elem.text_content()).strip() if date_elem else None
                    
                    item_elements = await card.query_selector_all('.hd-card__related-item')
                    related_items = []
                    for item in item_elements:
                        item_text = (await item.text_content() or "").strip()
                        if item_text:
                            related_items.append(item_text)
                    activity['related_items'] = related_items
                    
                    activities.append(activity)
                except Exception as e:
                    logger.warning(f"[Rocom Scraper] 提取单个活动失败: {e}")
                    continue
            
            logger.info(f"[Rocom Scraper] 成功提取 {len(activities)} 个活动")
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
