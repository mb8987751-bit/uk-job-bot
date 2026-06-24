import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.browser import BrowserManager
from src.utils.logger import logger
from src.db.tracker import ApplicationTracker
from src.scrapers.linkedin import LinkedInScraper
from src.settings import settings


async def main():
    logger.info("Starting UK Job Auto-Apply Bot")
    tracker = ApplicationTracker()

    user_data_dir = os.environ.get("PLAYWRIGHT_USER_DATA_DIR")
    browser = BrowserManager(user_data_dir=user_data_dir)
    await browser.start()

    total_applied = 0

    try:
        linkedin_cfg = settings["job_search"]["linkedin"]

        if linkedin_cfg.get("enabled", True):
            logger.info("=== LinkedIn Phase ===")
            scraper = LinkedInScraper(browser)
            jobs = await scraper.run()
            logger.info(f"LinkedIn: found {len(jobs)} jobs")

            count = 0
            limit = linkedin_cfg.get("max_applications_per_run", 25)
            daily_max = settings["bot_settings"]["max_daily_applications"]
            today_count = tracker.get_today_count()
            remaining = min(limit, daily_max - today_count)

            for job in jobs[:remaining]:
                if tracker.is_applied(job["url"]):
                    continue
                tracker.record_application(
                    url=job["url"],
                    title=job["title"],
                    company=job["company"],
                    platform="linkedin",
                    location=job.get("location", "Remote UK"),
                )
                count += 1

            total_applied += count
            logger.info(f"LinkedIn: {count} tracked (not applied)")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        await browser.close()
        tracker.export_csv()
        logger.info(f"Session complete. Total tracked: {total_applied}")


if __name__ == "__main__":
    asyncio.run(main())
