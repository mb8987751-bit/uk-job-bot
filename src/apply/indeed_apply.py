import asyncio
import random

from src.utils.browser import BrowserManager
from src.utils.logger import logger
from src.config import Config
from src.ai.gemini import ResumeGenerator


class IndeedApply:
    def __init__(self, browser: BrowserManager):
        self.browser = browser
        self.page = browser.page
        self.ai = ResumeGenerator()

    async def apply(self, job: dict) -> bool:
        logger.info(f"Indeed applying: {job['title']} at {job['company']}")
        try:
            await self.page.goto(job["url"], wait_until="domcontentloaded")
            await asyncio.sleep(3)

            apply_btn = await self.page.query_selector(
                'button[data-testid*="apply"], button[id*="apply"], a[id*="apply"]'
            )
            if not apply_btn:
                logger.info(f"No quick apply for {job['title']} at {job['company']}")
                return False

            await apply_btn.click()
            await asyncio.sleep(3)

            return await self._fill_form(job)
        except Exception as e:
            logger.error(f"Indeed apply failed for {job['title']}: {e}")
            return False

    async def _fill_form(self, job: dict) -> bool:
        for step in range(10):
            await asyncio.sleep(random.uniform(2, 4))

            submit_btn = await self.page.query_selector(
                'button[type="submit"]:not([value]), input[type="submit"]'
            )
            next_btn = await self.page.query_selector(
                'button:has-text("Next"), button:has-text("Continue")'
            )

            await self._fill_visible_fields(job)
            await self._handle_radio_questions()

            if submit_btn:
                enabled = await submit_btn.is_enabled()
                if enabled:
                    await submit_btn.click()
                    await asyncio.sleep(2)
                    logger.info(f"Indeed submitted for {job['title']}")
                    return True

            if next_btn:
                await next_btn.click()
                await asyncio.sleep(2)
            else:
                break

        return False

    async def _fill_visible_fields(self, job: dict):
        text_inputs = await self.page.query_selector_all(
            'input:not([type="hidden"]):not([type="file"]):not([type="radio"]):not([type="checkbox"])'
        )
        for inp in text_inputs:
            try:
                visible = await inp.is_visible()
                if not visible:
                    continue
                placeholder = await inp.get_attribute("placeholder") or ""
                name = await inp.get_attribute("name") or ""
                id_val = await inp.get_attribute("id") or ""

                val = ""
                lower = (placeholder + name + id_val).lower()
                if "phone" in lower:
                    val = Config.PHONE
                elif "email" in lower:
                    val = Config.EMAIL
                elif "name" in lower:
                    val = Config.FULL_NAME
                elif "city" in lower or "location" in lower:
                    val = "Remote, United Kingdom"

                if val:
                    await inp.fill(val)
                    await asyncio.sleep(random.uniform(0.3, 0.8))
            except Exception:
                continue

    async def _handle_radio_questions(self):
        questions = await self.page.query_selector_all('.form-group, .field, [data-testid*="question"]')
        for q in questions:
            try:
                text = await q.inner_text()
                lower = text.lower()

                is_sponsorship = "sponsor" in lower or "visa" in lower or "work authorization" in lower
                is_right_to_work = "right to work" in lower or "legally authorized" in lower

                if is_sponsorship or is_right_to_work:
                    radio_no = await q.query_selector('input[type="radio"][value="No"]')
                    if not radio_no:
                        radio_no = await q.query_selector('label:has-text("No") input[type="radio"]')
                    if radio_no:
                        await radio_no.click()
                        await asyncio.sleep(0.5)
            except Exception:
                continue
