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
        await self.page.goto(self.BASE_URL + "/feed/", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        if "feed" in self.page.url:
            logger.info("Cookies worked - already logged in")
            return True

        logger.info("Cookies expired, trying form login...")
        await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
        await asyncio.sleep(3)

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
        await self.page.goto(self.BASE_URL + "/feed/", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        if "feed" in self.page.url:
            return True
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
        ok = await self.ensure_logged_in()
        if not ok:
            logger.warning("Skipping LinkedIn search - not logged in")
            return []

        url = self._build_search_url(keyword)
        logger.info(f"LinkedIn searching: {keyword}")
        logger.info(f"Navigating to: {url}")
        await self.page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(10)

        jobs = []
        current_url = self.page.url
        page_title = await self.page.title()
        logger.info(f"Current URL: {current_url}")
        logger.info(f"Page title: {page_title}")

        try:
            await self.page.wait_for_selector('[class*="job-card"]', timeout=20000)
        except Exception:
            pass

        card_selectors = [
            ".job-card-container",
            ".job-card-list",
            ".jobs-search-results__list-item",
            "li[data-occludable-job-id]",
            "article",
            ".scaffold-layout__list",
            ".jobs-search-two-panel__list-item",
            ".jobs-search-results-list",
            '[class*="job-card"]',
            '[data-job-id]',
            ".display-flex > li",
            ".jobs-search-results--list",
        ]

        cards = []
        for sel in card_selectors:
            try:
                cards = await self.page.query_selector_all(sel)
                if cards:
                    logger.info(f"Found {len(cards)} cards using: {sel}")
                    break
            except Exception:
                continue

        if not cards:
            logger.warning("No job cards found with any selector")
            main_html = await self.page.evaluate("""() => {
                const main = document.querySelector('#main, .jobs-search-results, [role="main"], .scaffold-layout__list, .jobs-search-results-list');
                return main ? main.innerHTML.substring(0, 8000) : 'NO_MAIN_ELEM';
            }""")
            logger.info(f"Main HTML: {main_html}")
            all_html = await self.page.evaluate("document.body.innerHTML.substring(0, 3000)")
            logger.info(f"Body HTML first 3k: {all_html}")
            await self.page.screenshot(path=f"data/linkedin_debug_{keyword.replace(' ', '_')}.png", full_page=True)
            logger.info("Screenshot saved")
            return jobs

        max_cards = min(len(cards), self.config.get("max_applications_per_run", 25))
        for i in range(max_cards):
            try:
                cards = await self.page.query_selector_all(card_selectors[0])
                if not cards:
                    cards = await self.page.query_selector_all(card_selectors[1])
                if not cards or i >= len(cards):
                    break

                await cards[i].click()
                await asyncio.sleep(2)

                title = keyword
                company = "Unknown"
                location = "Remote UK"
                description = ""

                for sel in [".job-details-jobs-unified-top-card__job-title",
                            ".job-details__title",
                            "h1",
                            ".t-16.t-bold"]:
                    el = await self.page.query_selector(sel)
                    if el:
                        title = (await el.inner_text()).strip()
                        break

                for sel in [".job-details-jobs-unified-top-card__company-name",
                            ".job-details__company",
                            ".job-card-container__company-name",
                            '[data-testid="company-name"]']:
                    el = await self.page.query_selector(sel)
                    if el:
                        company = (await el.inner_text()).strip()
                        break

                for sel in [".job-details-jobs-unified-top-card__workplace-type",
                            ".job-details__location",
                            ".job-card-container__metadata-wrapper"]:
                    el = await self.page.query_selector(sel)
                    if el:
                        location = (await el.inner_text()).strip()
                        break

                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "description": description,
                    "url": self.page.url,
                    "platform": "linkedin",
                })
            except Exception as e:
                logger.debug(f"LinkedIn card {i} error: {e}")
                continue

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
