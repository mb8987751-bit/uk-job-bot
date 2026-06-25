import asyncio
import random
import os

from src.utils.browser import BrowserManager
from src.utils.logger import logger
from src.config import Config
from src.ai.gemini import ResumeGenerator


RESUME_FILE = "data/base_resume.txt"


class LinkedInApply:
    def __init__(self, browser: BrowserManager, resume_text: str = ""):
        self.browser = browser
        self.page = browser.page
        self.page.set_default_timeout(25000)
        self.resume_text = resume_text
        self.resume_gen = ResumeGenerator()

    def _load_resume(self) -> str:
        if self.resume_text:
            return self.resume_text
        if os.path.exists(RESUME_FILE):
            with open(RESUME_FILE, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    async def apply(self, job: dict) -> bool:
        try:
            return await self._apply_with_timeout(job)
        except Exception as e:
            logger.debug(f"Apply error: {job['title']}: {e}")
            return False

    async def _apply_with_timeout(self, job: dict) -> bool:
        logger.info(f"LinkedIn applying: {job['title']}")

        await self.page.evaluate(f"window.location.href = '{job['url']}'")
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        await asyncio.sleep(3)

        current = self.page.url
        if "login" in current:
            logger.info(f"Redirected to login - skip: {job['title']}")
            return False

        await self._extract_job_details(job)

        easy_btn = await self._find_apply_button()
        if not easy_btn:
            logger.info(f"No Easy Apply: {job['title']}")
            return False

        try:
            await easy_btn.click()
        except Exception:
            clicked = await self.page.evaluate("""() => {
                const texts = ['Easy Apply', 'Apply now', 'Apply'];
                for (const t of texts) {
                    const els = document.querySelectorAll('button, a, span');
                    for (const el of els) {
                        if (el.innerText.trim() === t && el.offsetParent !== null) {
                            el.click(); return true;
                        }
                    }
                }
                return false;
            }""")
            if not clicked:
                return False
        await asyncio.sleep(2)

        return await self._fill_form(job)

    async def _extract_job_details(self, job: dict):
        data = await self.page.evaluate("""() => {
            const descEl = document.querySelector('.show-more-less-html__markup, [class*="description"], [class*="job-details"], article');
            const companyEl = document.querySelector('[class*="company"] a, a[class*="company"], [class*="org-name"], [class*="employer"]');
            const titleEl = document.querySelector('h1, [class*="job-title"], [class*="top-card"]');
            return {
                description: descEl ? descEl.innerText.trim().substring(0, 3000) : '',
                company: companyEl ? companyEl.innerText.trim() : '',
                title: titleEl ? titleEl.innerText.trim() : ''
            };
        }""")
        if data.get("company"):
            job["company"] = data["company"]
        if data.get("description"):
            job["description"] = data["description"]
        if data.get("title"):
            job["title"] = data["title"]

    async def _generate_cover_letter(self, job: dict) -> str:
        resume = self._load_resume()
        if not Config.GEMINI_API_KEY:
            return f"I am excited to apply for the {job['title']} position at {job.get('company', 'your company')} and would love to contribute to your team."

        desc = job.get('description', '')[:2000]
        prompt = f"""Write a professional cover letter (3-4 paragraphs) for a {job['title']} position at {job.get('company', 'the company')}.
Job Description: {desc}
The applicant is based in Pakistan and authorized to work remotely for UK companies.
Keep it concise, professional, and tailored to the job description."""
        if resume:
            prompt += f"\n\nThe applicant's background:\n{resume[:2000]}"

        try:
            response = self.resume_gen.client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            return response.text
        except Exception as e:
            logger.warning(f"Gemini cover letter failed: {e}")
        return f"I am excited to apply for the {job['title']} position and bring my skills to your team."

    async def _find_apply_button(self):
        selectors = [
            'button[aria-label*="Easy Apply"]',
            'button[aria-label*="Apply"]',
            '.jobs-apply-button',
            'button:has-text("Easy Apply")',
            'button:has-text("Apply")',
            'a:has-text("Easy Apply")',
        ]
        for sel in selectors:
            try:
                btn = await self.page.wait_for_selector(sel, timeout=2000)
                if btn and await btn.is_visible():
                    return btn
            except Exception:
                continue
        return None

    async def _fill_form(self, job: dict) -> bool:
        cover_letter = None

        for step in range(10):
            await asyncio.sleep(random.uniform(1, 2))

            submit_btn = await self.page.query_selector('button[aria-label*="Submit application"], button[aria-label*="Submit"]')
            next_btn = await self.page.query_selector('button[aria-label*="Next"]')
            review_btn = await self.page.query_selector('button[aria-label*="Review"]')

            if not (submit_btn or next_btn or review_btn):
                break

            await self._fill_visible_fields(job)
            await self._handle_radio_questions()

            if cover_letter is None:
                cover_letter = await self._generate_cover_letter(job)
            await self._fill_textarea(cover_letter)

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

    async def _fill_textarea(self, text: str):
        textareas = await self.page.query_selector_all("textarea")
        for ta in textareas:
            try:
                if await ta.is_visible():
                    current = await ta.input_value()
                    if not current.strip():
                        await ta.fill(text[:2000])
                        await asyncio.sleep(0.5)
            except Exception:
                continue

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
