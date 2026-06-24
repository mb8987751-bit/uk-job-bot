import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.browser import BrowserManager
from src.utils.logger import logger
from src.db.tracker import ApplicationTracker
from src.scrapers.linkedin import LinkedInScraper
from src.scrapers.indeed import IndeedScraper
from src.apply.linkedin_apply import LinkedInApply
from src.apply.indeed_apply import IndeedApply
from src.settings import settings


async def process_jobs(jobs: list[dict], applier, tracker: ApplicationTracker, platform: str):
    applied = 0
    daily_max = settings["bot_settings"]["max_daily_applications"]
    today_count = tracker.get_today_count()

    for job in jobs:
        if today_count + applied >= daily_max:
            logger.info(f"Daily limit ({daily_max}) reached")
            break

        if tracker.is_applied(job["url"]):
            logger.info(f"Already applied: {job['title']} at {job['company']}")
            continue

        try:
            success = await asyncio.wait_for(applier.apply(job), timeout=60)
        except asyncio.TimeoutError:
            logger.info(f"Job timed out: {job['title']}")
            success = False
        except Exception as e:
            logger.debug(f"Job error: {e}")
            success = False

        if success:
            tracker.record_application(
                url=job["url"],
                title=job["title"],
                company=job["company"],
                platform=platform,
                location=job.get("location", "Remote UK"),
            )
            applied += 1

    return applied


async def main():
    logger.info("Starting UK Job Auto-Apply Bot")
    tracker = ApplicationTracker()

    user_data_dir = os.environ.get("PLAYWRIGHT_USER_DATA_DIR")
    browser = BrowserManager(user_data_dir=user_data_dir)
    await browser.start()

    total_applied = 0

    try:
        linkedin_cfg = settings["job_search"]["linkedin"]
        indeed_cfg = settings["job_search"]["indeed"]

        if linkedin_cfg.get("enabled", True):
            logger.info("=== LinkedIn Phase ===")
            linkedin_scraper = LinkedInScraper(browser)
            linkedin_applier = LinkedInApply(browser)
            jobs = await linkedin_scraper.run()
            count = await process_jobs(jobs, linkedin_applier, tracker, "linkedin")
            total_applied += count
            logger.info(f"LinkedIn: {count} applied")

        if indeed_cfg.get("enabled", True):
            logger.info("=== Indeed Phase ===")
            indeed_scraper = IndeedScraper(browser)
            indeed_applier = IndeedApply(browser)
            jobs = await indeed_scraper.run()
            count = await process_jobs(jobs, indeed_applier, tracker, "indeed")
            total_applied += count
            logger.info(f"Indeed: {count} applied")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        await browser.close()
        tracker.export_csv()
        logger.info(f"Session complete. Total applied: {total_applied}")


if __name__ == "__main__":
    asyncio.run(main())
