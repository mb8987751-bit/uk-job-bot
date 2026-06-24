import asyncio
import random
from urllib.parse import quote

from src.utils.browser import BrowserManager
from src.utils.logger import logger
from src.settings import settings
from src.config import Config


class IndeedScraper:
    BASE_URL = "https://uk.indeed.com"

    def __init__(self, browser: BrowserManager):
        self.browser = browser
        self.page = browser.page
        self.config = settings["job_search"]["indeed"]

    async def login(self):
        logger.info("Logging into Indeed...")
        await self.page.goto(f"{self.BASE_URL}/account/login", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        email_input = await self.page.query_selector('input[type="email"]')
        if email_input:
            await email_input.fill(Config.INDEED_EMAIL)
            await asyncio.sleep(random.uniform(1, 2))
            await self.page.click('button[type="submit"]')
            await asyncio.sleep(2)

            pwd_input = await self.page.query_selector('input[type="password"]')
            if pwd_input:
                await pwd_input.fill(Config.INDEED_PASSWORD)
                await asyncio.sleep(random.uniform(1, 2))
                await self.page.click('button[type="submit"]')
                await asyncio.sleep(4)

        logger.info(f"Indeed login result: {self.page.url}")

    def _build_search_url(self, keyword: str) -> str:
        q = quote(keyword)
        params = f"?q={q}&l=&fromage=7&remotejob=1&sort=date"
        return f"{self.BASE_URL}/jobs{params}"

    async def search_jobs(self, keyword: str) -> list[dict]:
        url = self._build_search_url(keyword)
        logger.info(f"Indeed searching: {keyword}")
        await self.page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        jobs = []
        try:
            await self.page.wait_for_selector(".job_seen_beacon, .job-card, .result", timeout=15000)
            cards = await self.page.query_selector_all(".job_seen_beacon, .job-card, .result")
            max_cards = min(len(cards), self.config.get("max_applications_per_run", 25))

            for i in range(max_cards):
                try:
                    cards = await self.page.query_selector_all(".job_seen_beacon, .job-card, .result")
                    if i >= len(cards):
                        break

                    link = await cards[i].query_selector("a[data-jk]")
                    if not link:
                        link = await cards[i].query_selector("h2 a")
                    if not link:
                        continue

                    title_el = await cards[i].query_selector("h2 span, .jobTitle")
                    company_el = await cards[i].query_selector('[data-testid="companyName"], .companyName')
                    location_el = await cards[i].query_selector('[data-testid="location"], .companyLocation')

                    title = await title_el.inner_text() if title_el else keyword
                    company = await company_el.inner_text() if company_el else "Unknown"
                    location = await location_el.inner_text() if location_el else "Remote UK"

                    href = await link.get_attribute("href") or ""
                    job_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                    jobs.append({
                        "title": title.strip(),
                        "company": company.strip(),
                        "location": location.strip(),
                        "description": "",
                        "url": job_url,
                        "platform": "indeed",
                    })
                except Exception as e:
                    logger.debug(f"Indeed card {i} error: {e}")
                    continue
        except Exception as e:
            logger.warning(f"No Indeed job cards found: {e}")

        logger.info(f"Found {len(jobs)} Indeed jobs for '{keyword}'")
        return jobs

    async def run(self) -> list[dict]:
        await self.login()
        all_jobs = []
        for keyword in self.config["keywords"]:
            jobs = await self.search_jobs(keyword)
            all_jobs.extend(jobs)
            await self.browser.human_delay()
        return all_jobs
