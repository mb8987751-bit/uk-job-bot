import asyncio
import random
from playwright.async_api import async_playwright, Browser, Page

from src.settings import settings


class BrowserManager:
    def __init__(self):
        self._ctx = None
        self.playwright = None
        self.browser: Browser | None = None
        self.page: Page | None = None

    async def start(self, headless: bool = None):
        if headless is None:
            headless = settings["bot_settings"]["headless"]
        self._ctx = async_playwright()
        self.playwright = await self._ctx.__aenter__()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self.page = await context.new_page()
        return self.page

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self._ctx:
            await self._ctx.__aexit__(None, None, None)

    async def human_delay(self, min_s: float = None, max_s: float = None):
        if min_s is None:
            min_s = settings["bot_settings"]["human_delay_min"]
        if max_s is None:
            max_s = settings["bot_settings"]["human_delay_max"]
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def human_type(self, selector: str, text: str, delay: float = 0.05):
        await self.page.click(selector)
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await self.page.fill(selector, "")
        for char in text:
            await self.page.type(selector, char, delay=delay * random.uniform(0.5, 1.5))
            await asyncio.sleep(random.uniform(0.01, 0.05))

    async def wait_and_click(self, selector: str, timeout: int = 10000):
        await self.page.wait_for_selector(selector, timeout=timeout)
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await self.page.click(selector)
