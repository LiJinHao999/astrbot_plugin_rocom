"""
洛克王国数据爬虫模块
用于即时爬取商人信息和活动日历
"""
import asyncio
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


class RocomScraper:
    """洛克王国数据爬虫"""
    
    def __init__(self):
        self.url = "https://huodong2.4399.com/yxhtools/game-store"
        self._browser = None
        self._context = None
    
    async def _ensure_browser(self):
        """确保浏览器已启动"""
        if self._browser is None:
            playwright = await async_playwright().start()
            self._browser = await playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context()
    
    async def close(self):
        """关闭浏览器"""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
    
    async def get_merchant_info(self) -> Optional[Dict]:
        """爬取商人信息"""
        try:
            await self._ensure_browser()
            page = await self._context.new_page()
            
            await page.goto(self.url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            goods_elements = await page.query_selector_all('.goods-row')
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
                except:
                    continue
            
            await page.close()
            return {'goods': goods_list}
            
        except Exception as e:
            return None
    
    async def get_activities_info(self) -> Optional[Dict]:
        """爬取活动日历信息"""
        try:
            await self._ensure_browser()
            page = await self._context.new_page()
            
            await page.goto(self.url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            tab2 = await page.query_selector('.tab-item.tab-2')
            if tab2:
                await tab2.click()
                await page.wait_for_timeout(3000)
            
            activity_cards = await page.query_selector_all('.hd-card')
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
                except:
                    continue
            
            await page.close()
            return {'activities': activities}
            
        except Exception as e:
            return None
