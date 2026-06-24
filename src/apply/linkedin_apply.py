import asyncio
import json
import random

from src.utils.browser import BrowserManager
from src.utils.logger import logger
from src.config import Config


class LinkedInApply:
    def __init__(self, browser: BrowserManager):
        self.browser = browser
        self.page = browser.page
        self.page.set_default_timeout(25000)

    async def apply(self, job: dict) -> bool:
        try:
            return await self._apply_with_timeout(job)
        except Exception as e:
            logger.debug(f"Apply error: {job['title']}: {e}")
            return False

    async def _apply_with_timeout(self, job: dict) -> bool:
        logger.info(f"LinkedIn applying: {job['title']} at {job['company']}")

        navigated = await self.page.evaluate(f"""
            async () => {{
                try {{
                    await new Promise(r => {{ window.location.href = '{job["url"]}'; setTimeout(r, 3000); }});
                    return 'navigated';
                }} catch(e) {{ return 'error: ' + e.message; }}
            }}
        """)
        await asyncio.sleep(3)

        current = self.page.url
        if "login" in current:
            logger.info(f"Redirected to login - skip: {job['title']}")
            return False

        easy_btn = await self._find_easy_apply()
        if not easy_btn:
            logger.info(f"No Easy Apply: {job['title']} at {job['company']}")
            return False

        try:
            await easy_btn.click()
        except Exception:
            clicked = await self.page.evaluate("""() => {
                const btn = document.querySelector('button[aria-label*="Easy Apply"], .jobs-apply-button');
                if (btn) { btn.click(); return true; }
                return false;
            }""")
            if not clicked:
                return False
        await asyncio.sleep(2)

        return await self._fill_form(job)

    async def _find_easy_apply(self):
        for _ in range(10):
            btn = await self.page.query_selector('button[aria-label*="Easy Apply"], .jobs-apply-button')
            if btn:
                return btn
            await asyncio.sleep(0.5)
        return None

    async def _fill_form(self, job: dict) -> bool:
        for step in range(10):
            await asyncio.sleep(random.uniform(1, 2))

            submit_btn = await self.page.query_selector('button[aria-label*="Submit application"], button[aria-label*="Submit"]')
            next_btn = await self.page.query_selector('button[aria-label*="Next"]')
            review_btn = await self.page.query_selector('button[aria-label*="Review"]')

            if not (submit_btn or next_btn or review_btn):
                break

            await self._fill_visible_fields(job)
            await self._handle_radio_questions()

            if submit_btn:
                try:
                    await submit_btn.click()
                except Exception:
                    await self.page.evaluate("document.querySelector('button[aria-label*=\"Submit\"]')?.click()")
                await asyncio.sleep(1)
                return True
            elif review_btn:
                try:
                    await review_btn.click()
                except Exception:
                    await self.page.evaluate("document.querySelector('button[aria-label*=\"Review\"]')?.click()")
                await asyncio.sleep(1)
            elif next_btn:
                try:
                    await next_btn.click()
                except Exception:
                    await self.page.evaluate("document.querySelector('button[aria-label*=\"Next\"]')?.click()")
                await asyncio.sleep(1)

        return False

    async def _fill_visible_fields(self, job: dict):
        inputs = await self.page.query_selector_all('input:not([type="hidden"]):not([type="file"])')
        for inp in inputs:
            try:
                if not await inp.is_visible():
                    continue
                placeholder = (await inp.get_attribute("placeholder") or "") + (await inp.get_attribute("name") or "") + (await inp.get_attribute("id") or "")
                lower = placeholder.lower()
                val = ""
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
                sponsorship = "sponsor" in lower or "visa" in lower or "work authorization" in lower
                disability = "disability" in lower
                gender = "gender" in lower or "race" in lower or "ethnicity" in lower
                start_now = "start" in lower and "immediate" in lower

                if sponsorship or "right to work" in lower:
                    radio = await q.query_selector('input[type="radio"][value="No"], label:has-text("No") input[type="radio"]')
                    if radio:
                        await radio.click()
                        await asyncio.sleep(0.5)
                    continue
                if disability or gender:
                    radio = await q.query_selector('input[type="radio"][value="No"], label:has-text("No") input[type="radio"]')
                    if radio:
                        await radio.click()
                        await asyncio.sleep(0.5)
                    continue
                if start_now:
                    radio = await q.query_selector('input[type="radio"][value="Yes"], label:has-text("Yes") input[type="radio"]')
                    if radio:
                        await radio.click()
                        await asyncio.sleep(0.5)
                    continue
            except Exception:
                continue
