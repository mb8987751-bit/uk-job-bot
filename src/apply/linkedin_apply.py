import asyncio
import random

from src.utils.browser import BrowserManager
from src.utils.logger import logger
from src.config import Config
from src.ai.gemini import ResumeGenerator


class LinkedInApply:
    def __init__(self, browser: BrowserManager):
        self.browser = browser
        self.page = browser.page
        self.ai = ResumeGenerator()

    async def apply(self, job: dict) -> bool:
        logger.info(f"LinkedIn applying: {job['title']} at {job['company']}")
        try:
            await self.page.goto(job["url"], wait_until="domcontentloaded")
            await asyncio.sleep(3)

            easy_apply_btn = await self.page.query_selector(
                'button[aria-label*="Easy Apply"], .jobs-apply-button'
            )
            if not easy_apply_btn:
                logger.info(f"No Easy Apply for {job['title']} at {job['company']}")
                return False

            await easy_apply_btn.click()
            await asyncio.sleep(3)

            submitted = await self._fill_form(job)
            if submitted:
                logger.info(f"Applied: {job['title']} at {job['company']}")
                return True
            return False
        except Exception as e:
            logger.error(f"LinkedIn apply failed for {job['title']}: {e}")
            return False

    async def _fill_form(self, job: dict) -> bool:
        max_steps = 15
        for step in range(max_steps):
            await asyncio.sleep(random.uniform(2, 4))

            submit_btn = await self.page.query_selector(
                'button[aria-label*="Submit"], button[data-control-name*="submit"]'
            )
            next_btn = await self.page.query_selector(
                'button[aria-label*="Next"], button[data-control-name*="continue"]'
            )
            review_btn = await self.page.query_selector(
                'button[aria-label*="Review"]'
            )

            await self._fill_visible_fields(job)
            await self._handle_radio_questions()

            if submit_btn:
                await submit_btn.click()
                await asyncio.sleep(2)
                return True
            elif review_btn:
                await review_btn.click()
                await asyncio.sleep(2)
            elif next_btn:
                await next_btn.click()
                await asyncio.sleep(2)
            else:
                break

        return False

    async def _fill_visible_fields(self, job: dict):
        text_inputs = await self.page.query_selector_all(
            'input:not([type="hidden"]):not([type="file"])'
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
                elif "linkedin" in lower:
                    continue

                if val:
                    await inp.fill(val)
                    await asyncio.sleep(random.uniform(0.3, 0.8))
            except Exception:
                continue

    async def _handle_radio_questions(self):
        questions = await self.page.query_selector_all(".fb-form-element, .jobs-easy-apply-form-element")
        for q in questions:
            try:
                text = await q.inner_text()
                lower = text.lower()

                is_sponsorship = "sponsor" in lower or "visa" in lower or "work authorization" in lower
                is_right_to_work = "right to work" in lower or "legally authorized" in lower
                is_disability = "disability" in lower
                is_gender = "gender" in lower or "race" in lower or "ethnicity" in lower
                is_start_now = "start" in lower and "immediate" in lower

                if is_sponsorship or is_right_to_work:
                    radio_no = await q.query_selector('input[type="radio"][value="No"], label:has-text("No") input[type="radio"]')
                    if radio_no:
                        await radio_no.click()
                        await asyncio.sleep(0.5)
                    continue

                if is_disability or is_gender:
                    radio_no = await q.query_selector('input[type="radio"][value="No"], label:has-text("No") input[type="radio"]')
                    if radio_no:
                        await radio_no.click()
                        await asyncio.sleep(0.5)
                    continue

                if is_start_now:
                    radio_yes = await q.query_selector('input[type="radio"][value="Yes"], label:has-text("Yes") input[type="radio"]')
                    if radio_yes:
                        await radio_yes.click()
                        await asyncio.sleep(0.5)
                    continue

            except Exception:
                continue
