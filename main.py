import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.browser import BrowserManager
from src.utils.logger import logger
from src.db.tracker import ApplicationTracker
from src.scrapers.linkedin import LinkedInScraper
from src.apply.linkedin_apply import LinkedInApply
from src.settings import settings


async def main():
    logger.info("Starting UK Job Auto-Apply Bot")
    tracker = ApplicationTracker()

    user_data_dir = os.environ.get("PLAYWRIGHT_USER_DATA_DIR")
    browser = BrowserManager(user_data_dir=user_data_dir)
    await browser.start()

    resume_text = ""
    resume_path = "data/base_resume.txt"
    if os.path.exists(resume_path):
        with open(resume_path, "r", encoding="utf-8") as f:
            resume_text = f.read().strip()
        if len(resume_text) < 50:
            resume_text = ""

    total_applied = 0
    total_skipped = 0

    try:
        linkedin_cfg = settings["job_search"]["linkedin"]

        if linkedin_cfg.get("enabled", True):
            logger.info("=== LinkedIn Phase ===")
            scraper = LinkedInScraper(browser)
            jobs = await scraper.run()
            logger.info(f"LinkedIn: found {len(jobs)} jobs")

            applier = LinkedInApply(browser, resume_text=resume_text)
            limit = linkedin_cfg.get("max_applications_per_run", 50)
            daily_max = settings["bot_settings"]["max_daily_applications"]
            today_count = tracker.get_today_count()
            remaining = min(limit, daily_max - today_count)

            for job in jobs[:remaining]:
                status = tracker.get_status(job["url"])
                if status in ("submitted", "no_easy_apply"):
                    total_skipped += 1
                    continue

                tracker.record_application(
                    url=job["url"],
                    title=job["title"],
                    company=job["company"],
                    platform="linkedin",
                    location=job.get("location", "Remote UK"),
                    status="pending",
                )

                try:
                    success = await asyncio.wait_for(applier.apply(job), timeout=120)
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout applying: {job['title']}")
                    tracker.update_status(job["url"], "timeout")
                    continue
                except Exception as e:
                    logger.error(f"Apply error for {job['title']}: {e}")
                    tracker.update_status(job["url"], "error")
                    continue

                if success:
                    tracker.update_status(job["url"], "submitted")
                    total_applied += 1
                    logger.info(f"✓ Applied ({total_applied}/{remaining}): {job['title']}")
                else:
                    tracker.update_status(job["url"], "no_easy_apply")

                await browser.human_delay()

            logger.info(f"LinkedIn: {total_applied} applied, {total_skipped} previously skipped")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        await browser.close()
        tracker.export_csv()
        logger.info(f"Session complete. Total applied: {total_applied}")


if __name__ == "__main__":
    asyncio.run(main())
