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
            return True
        return False

    async def _save_cookies(self):
        cookies = await self.page.context.cookies()
        os.makedirs(os.path.dirname(self.COOKIE_FILE), exist_ok=True)
        with open(self.COOKIE_FILE, "w") as f:
            json.dump(cookies, f)
        logger.info("Saved cookies")

    async def login(self):
        logger.info("Logging into LinkedIn...")

        await self._load_cookies()
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        if "feed" in self.page.url or "checkpoint" not in self.page.url:
            logger.info("Cookies worked - already logged in")
            return

        logger.info("Cookies expired, trying form login...")
        await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        if "feed" in self.page.url:
            logger.info("Already logged in")
            return

        username_sel = await self.page.wait_for_selector("#username", timeout=10000)
        if not username_sel:
            logger.error("LinkedIn login form not found (CAPTCHA/block)")
            return False

        await username_sel.fill(Config.LINKEDIN_EMAIL)
        await asyncio.sleep(random.uniform(1, 2))
        await self.page.fill("#password", Config.LINKEDIN_PASSWORD)
        await asyncio.sleep(random.uniform(1, 2))
        await self.page.click('button[type="submit"]')
        await asyncio.sleep(5)

        if "feed" in self.page.url:
            logger.info("LinkedIn login successful")
            await self._save_cookies()
            return True

        logger.warning(f"LinkedIn login may have failed. URL: {self.page.url}")
        return False

    def _build_search_url(self, keyword: str) -> str:
        params = {
            "keywords": keyword,
            "location": self.config["location"],
            "f_AL": "true",
            "f_E": "2",
            "f_WT": "2",
            "f_JT": "F",
            "position": "1",
            "pageNum": "0",
        }
        return f"{self.BASE_URL}/jobs/search/?{urlencode(params)}"

    async def search_jobs(self, keyword: str) -> list[dict]:
        url = self._build_search_url(keyword)
        logger.info(f"LinkedIn searching: {keyword}")
        await self.page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(5)

        jobs = []
        try:
            await self.page.wait_for_selector(".job-card-container", timeout=15000)
            cards = await self.page.query_selector_all(".job-card-container")
            max_cards = min(len(cards), self.config.get("max_applications_per_run", 25))

            for i in range(max_cards):
                try:
                    cards = await self.page.query_selector_all(".job-card-container")
                    if i >= len(cards):
                        break
                    await cards[i].click()
                    await asyncio.sleep(2)

                    title_el = await self.page.query_selector(".job-details-jobs-unified-top-card__job-title")
                    company_el = await self.page.query_selector(".job-details-jobs-unified-top-card__company-name")
                    location_el = await self.page.query_selector(".job-details-jobs-unified-top-card__workplace-type")
                    desc_el = await self.page.query_selector(".job-details-jobs-unified-top-card__description")

                    title = await title_el.inner_text() if title_el else keyword
                    company = await company_el.inner_text() if company_el else "Unknown"
                    location = await location_el.inner_text() if location_el else "Remote UK"
                    description = await desc_el.inner_text() if desc_el else ""

                    jobs.append({
                        "title": title.strip(),
                        "company": company.strip(),
                        "location": location.strip(),
                        "description": description.strip(),
                        "url": self.page.url,
                        "platform": "linkedin",
                    })
                except Exception as e:
                    logger.debug(f"LinkedIn card {i} error: {e}")
                    continue
        except Exception as e:
            logger.warning(f"No LinkedIn job cards found: {e}")

        logger.info(f"Found {len(jobs)} LinkedIn jobs for '{keyword}'")
        return jobs

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
