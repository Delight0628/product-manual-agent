"""亚马逊产品页面抓取器"""

import asyncio
import random
import re
from typing import Optional
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from src.models import ProductData


# Mock 数据用于 Demo 演示
MOCK_PRODUCTS = {
    "B0DEFAULT": ProductData(
        title="Solid Wood Dining Table - Modern Minimalist Kitchen Table",
        bullet_points=[
            "Material: 100% Natural Oak Wood, environmentally friendly",
            "Size: 120cm x 80cm x 75cm (L x W x H), seats 4-6 people",
            "Design: Modern minimalist style with clean lines",
            "Assembly: Easy assembly with included hardware and instructions",
            "Durability: Scratch-resistant surface, easy to clean with damp cloth",
        ],
        images=[
            "https://via.placeholder.com/800x600?text=Dining+Table+Front",
            "https://via.placeholder.com/800x600?text=Dining+Table+Side",
        ],
        price="$299.99",
        asin="B0DEFAULT",
        brand="WoodCraft",
    ),
    "B0COUCH01": ProductData(
        title="Modern L-Shaped sectional Sofa with Chaise Lounge",
        bullet_points=[
            "Material: Premium linen fabric, solid wood frame",
            "Dimensions: 270cm x 180cm x 85cm, fits large living rooms",
            "Comfort: High-density foam cushions with spring support",
            "Features: Reversible chaise, removable and washable covers",
            "Style: Contemporary design, available in multiple colors",
        ],
        images=[
            "https://via.placeholder.com/800x600?text=Sofa+Front",
            "https://via.placeholder.com/800x600?text=Sofa+Angle",
        ],
        price="$899.99",
        asin="B0COUCH01",
        brand="ComfortHome",
    ),
    "B0SHELF01": ProductData(
        title="Industrial Style Bookshelf - 5 Tier Open Shelving Unit",
        bullet_points=[
            "Material: Metal frame with rustic engineered wood shelves",
            "Dimensions: 80cm x 30cm x 180cm (L x W x H)",
            "Capacity: Each shelf holds up to 20kg, total load 100kg",
            "Assembly: Easy 15-minute assembly with included tools",
            "Versatile: Perfect for books, plants, decorations, or storage",
        ],
        images=[
            "https://via.placeholder.com/800x600?text=Bookshelf+Front",
            "https://via.placeholder.com/800x600?text=Bookshelf+Detail",
        ],
        price="$159.99",
        asin="B0SHELF01",
        brand="IndustrialHome",
    ),
}


class AmazonScraper:
    """亚马逊产品页面抓取器"""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock

    async def scrape(self, url: str) -> ProductData:
        """抓取亚马逊产品数据"""
        if self.use_mock or not PLAYWRIGHT_AVAILABLE:
            return self._get_mock_data(url)

        return await self._scrape_amazon(url)

    def _extract_asin(self, url: str) -> Optional[str]:
        """从 URL 中提取 ASIN"""
        patterns = [
            r'/dp/([A-Z0-9]{10})',
            r'/product/([A-Z0-9]{10})',
            r'asin=([A-Z0-9]{10})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return None

    def _get_mock_data(self, url: str) -> ProductData:
        """获取 Mock 数据"""
        asin = self._extract_asin(url)
        if asin and asin in MOCK_PRODUCTS:
            return MOCK_PRODUCTS[asin]
        return MOCK_PRODUCTS["B0DEFAULT"]

    async def _scrape_amazon(self, url: str) -> ProductData:
        """真实抓取亚马逊页面"""
        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=random.choice(self.USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
            )
            page: Page = await context.new_page()

            try:
                # 随机延迟，模拟人类行为
                await asyncio.sleep(random.uniform(1, 3))

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # 等待页面加载
                await page.wait_for_selector("#productTitle", timeout=10000)

                # 提取标题
                title = await page.text_content("#productTitle")
                title = title.strip() if title else "Unknown Product"

                # 提取五点描述
                bullet_points = []
                bullet_elements = await page.query_selector_all(
                    "#feature-bullets li span.a-list-item"
                )
                for elem in bullet_elements[:5]:
                    text = await elem.text_content()
                    if text and text.strip():
                        bullet_points.append(text.strip())

                # 提取图片
                images = []
                img_elements = await page.query_selector_all(
                    "#altImages img"
                )
                for img in img_elements:
                    src = await img.get_attribute("src")
                    if src and "media-amazon.com" in src:
                        # 获取高清版本
                        hd_src = src.replace("._SS", "._AC").replace("_SL", "_AC")
                        images.append(hd_src)

                # 提取价格
                price = None
                price_elem = await page.query_selector(
                    ".a-price .a-offscreen"
                )
                if price_elem:
                    price = await price_elem.text_content()

                # 提取 ASIN
                asin = self._extract_asin(url)

                return ProductData(
                    title=title,
                    bullet_points=bullet_points,
                    images=images[:5],  # 最多5张图
                    price=price,
                    asin=asin,
                    url=url,
                )

            except Exception as e:
                print(f"抓取失败: {e}")
                return self._get_mock_data(url)
            finally:
                await browser.close()
