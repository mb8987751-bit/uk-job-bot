import asyncio
import random
import json
import os
from urllib.parse import urlencode

from src.utils.browser import BrowserManager
from src.utils.logger import logger
from src.settings import settings
from src.config import Config


class LinkedInScraper:
    BASE_URL = "https://www.linkedin.com"
    LOGIN_URL = f"{BASE_URL}/login"
    COOKIE_FILE = "data/linkedin_cookies.json"

    def __init__(self, browser: BrowserManager):
        self.browser = browser
        self.page = browser.page
        self.config = settings["job_search"]["linkedin"]

    async def _load_cookies(self):
        if os.path.exists(self.COOKIE_FILE):
            with open(self.COOKIE_FILE) as f:
                cookies = json.load(f)
            await self.page.context.add_cookies(cookies)
            logger.info("Loaded saved cookies")
            os.remove(self.COOKIE_FILE)
            return True
        return False

    async def _save_cookies(self):
        pass

    async def login(self):
        logger.info("Logging into LinkedIn...")

        await self._load_cookies()
        try:
            await self.page.goto(self.BASE_URL + "/feed/", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.warning(f"Feed page goto timeout: {e}")
        await asyncio.sleep(2)

        if "feed" in self.page.url:
            logger.info("Cookies worked - already logged in")
            return True

        logger.info("Cookies expired, trying form login...")
        try:
            await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.warning(f"Login page goto timeout: {e}")
        await asyncio.sleep(2)

        current_url = self.page.url
        page_title = await self.page.title()
        logger.info(f"Login page URL: {current_url}, Title: {page_title}")

        username_sel = await self.page.wait_for_selector("#username", timeout=10000)
        if not username_sel:
            logger.error("LinkedIn login form not found (CAPTCHA/block)")
            await self.page.screenshot(path="data/login_failed.png", full_page=True)
            body = await self.page.evaluate("document.body.innerText.substring(0, 1000)")
            logger.info(f"Login page body: {body}")
            return False

        await username_sel.fill(Config.LINKEDIN_EMAIL)
        await asyncio.sleep(random.uniform(1, 2))
        await self.page.fill("#password", Config.LINKEDIN_PASSWORD)
        await asyncio.sleep(random.uniform(1, 2))
        await self.page.click('button[type="submit"]')
        await asyncio.sleep(5)

        if "feed" in self.page.url:
            logger.info("LinkedIn login successful")
            return True

        logger.warning(f"LinkedIn login may have failed. URL: {self.page.url}")
        await self.page.screenshot(path="data/login_submit_failed.png", full_page=True)
        return False

    async def ensure_logged_in(self):
        try:
            await self.page.goto(self.BASE_URL + "/feed/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            if "feed" in self.page.url:
                return True
        except Exception:
            logger.warning("Feed page timeout in ensure_logged_in")
        return await self.login()

    def _build_search_url(self, keyword: str) -> str:
        params = {
            "keywords": keyword,
            "location": self.config["location"],
            "f_AL": "true",
            "f_E": "2",
            "f_WT": "2",
            "position": "1",
            "pageNum": "0",
        }
        return f"{self.BASE_URL}/jobs/search/?{urlencode(params)}"

    async def search_jobs(self, keyword: str) -> list[dict]:
        url = self._build_search_url(keyword)
        logger.info(f"LinkedIn searching: {keyword}")
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            logger.warning("Timeout navigating to search URL")
        await asyncio.sleep(3)

        page_url = self.page.url
        page_title = await self.page.title()
        logger.info(f"Page title: {page_title}")

        if "login" in page_url:
            logger.warning("Redirected to login during search")
            return []

        await self._dismiss_modal()
        await asyncio.sleep(1)

        jobs = await self._extract_jobs_via_js(keyword)
        tracked = jobs[:self.config.get("max_applications_per_run", 25)]
        if tracked:
            logger.info(f"Found {len(tracked)} LinkedIn jobs for '{keyword}'")
        else:
            logger.warning(f"No jobs found for '{keyword}'")
        return tracked

    async def _extract_jobs_via_js(self, keyword: str) -> list[dict]:
        data = await self.page.evaluate("""() => {
            const results = [];
            const allText = document.body.innerText;
            const lines = allText.split('\\n').filter(l => l.trim());
            const skipWords = ['Sign in', 'password', 'email', 'username', 'Skip to', 'Dismiss', 'Join now'];
            const isLoginPage = skipWords.some(w => allText.includes(w));
            if (isLoginPage && !allText.includes('jobs')) return results;

            const links = document.querySelectorAll('a[href*="/jobs/view"]');
            for (const link of links) {
                const title = link.innerText || link.title || '';
                if (title.trim() && title.length < 200 && !title.includes('javascript')) {
                    results.push({ title: title.trim(), url: link.href });
                }
            }
            return results;
        }""")
        jobs = []
        seen = set()
        for item in data:
            if item["title"] not in seen:
                seen.add(item["title"])
                jobs.append({
                    "title": item["title"],
                    "company": "Unknown",
                    "location": "Remote UK",
                    "description": "",
                    "url": item["url"],
                    "platform": "linkedin",
                })
        return jobs

    async def _dismiss_modal(self):
        selectors = [
            ".contextual-sign-in-modal__modal-dismiss-icon",
            "button[aria-label='Dismiss']",
            ".artdeco-modal__dismiss",
            '[data-test-modal-close-btn]',
            ".modal__dismiss",
            'button:has(svg use[href*="close"])',
        ]
        for sel in selectors:
            try:
                btn = await self.page.query_selector(sel)
                if btn:
                    await btn.click(force=True)
                    await asyncio.sleep(1)
                    logger.info(f"Dismissed modal with: {sel}")
                    return True
            except Exception:
                continue
        js_result = await self.page.evaluate("""() => {
            const els = document.querySelectorAll('[class*="dismiss"], [class*="close"], [class*="modal"] button, .artdeco-modal__dismiss');
            for (const el of els) {
                if (el.offsetParent !== null) {
                    el.click();
                    return 'Clicked: ' + (el.className || el.tagName);
                }
            }
            return 'No visible dismiss button found';
        }""")
        if "Clicked" in js_result:
            logger.info(f"Modal dismissed via JS: {js_result}")
            await asyncio.sleep(1)
            return True
        return False

    async def run(self) -> list[dict]:
        logged_in = await self.login()
        if not logged_in:
            logger.warning("Skipping LinkedIn - login failed")
            return []
        all_jobs = []
        for keyword in self.config["keywords"]:
            jobs = await self.search_jobs(keyword)
            all_jobs.extend(jobs)
            await self.browser.human_delay()
        return all_jobs
