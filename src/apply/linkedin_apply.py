import asyncio
import json
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
        self.last_debug = ""

    def _load_resume(self) -> str:
        if self.resume_text:
            return self.resume_text
        if os.path.exists(RESUME_FILE):
            with open(RESUME_FILE, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    async def apply_jobs(self, jobs: list[dict]) -> list[tuple[str, str, str]]:
        results = []
        for idx, job in enumerate(jobs):
            self.last_debug = ""
            try:
                status = await self._process_job_at_index(job, idx)
                results.append((job["url"], status, self.last_debug))
                if status == "submitted":
                    logger.info(f"✓ Applied: {job['title']}")
            except Exception as e:
                logger.debug(f"Apply error: {job['title']}: {e}")
                results.append((job["url"], "error", ""))
        return results

    async def _process_job_at_index(self, job: dict, idx: int) -> str:
        logger.info(f"Processing job {idx}: {job['title']}")
        clicked = await self.page.evaluate(f"""
            (() => {{
                const links = document.querySelectorAll('a[href*="/jobs/view"]');
                if (links[{idx}]) {{
                    links[{idx}].click();
                    return true;
                }}
                return false;
            }})()
        """)
        if not clicked:
            return "error"
        await asyncio.sleep(3)
        await self._extract_job_details(job)
        btn_found = await self._click_easy_apply()
        if not btn_found:
            await self._debug_page_buttons()
            return "no_easy_apply"
        await asyncio.sleep(2)
        filled = await self._fill_form(job)
        if filled:
            await self._dismiss_success_modal()
            return "submitted"
        return "no_easy_apply"

    async def _debug_page_buttons(self):
        data = await self.page.evaluate("""() => {
            const all = document.querySelectorAll('button, a, span, div[role="button"]');
            const items = [];
            for (const el of all) {
                const t = el.innerText.trim();
                if (t && t.length < 100 && el.offsetParent !== null) {
                    items.push({ tag: el.tagName, text: t, class: (el.className || '').substring(0, 80) });
                }
            }
            const job_btns = items.filter(x =>
                x.text.includes('Apply') || x.text.includes('Easy') ||
                x.text.includes('applied') || x.text.includes('submit')
            );
            return JSON.stringify(job_btns.length ? job_btns : items.slice(0, 20));
        }""")
        self.last_debug = f"buttons: {data[:200]}"
        logger.info(f"Page debug for '{await self.page.title()}': {self.last_debug}")

    async def _click_easy_apply(self) -> bool:
        selectors = [
            'button:has-text("Easy Apply")',
            'button:has-text("easy apply")',
            'button:has-text("Easy apply")',
            '[data-control-name*="apply"]',
            '[class*="jobs-apply"] button',
            'a:has-text("Easy Apply")',
            'span:has-text("Easy Apply")',
            'div[role="button"]:has-text("Easy Apply")',
        ]
        for sel in selectors:
            try:
                el = await self.page.wait_for_selector(sel, timeout=2000)
                if el and await el.is_visible():
                    await el.click()
                    return True
            except Exception:
                continue
        clicked = await self.page.evaluate("""() => {
            const all = document.querySelectorAll('button, a, span, div[role="button"]');
            for (const el of all) {
                const t = el.innerText.trim();
                if (t === 'Easy Apply' && el.offsetParent !== null) {
                    el.click(); return true;
                }
            }
            for (const el of all) {
                const t = el.innerText.trim();
                if (t.includes('Easy') && t.includes('Apply') && el.offsetParent !== null) {
                    el.click(); return true;
                }
            }
            const cls = document.querySelectorAll('[class*="easy" i]');
            for (const el of cls) {
                if (el.offsetParent !== null && el.innerText.trim().includes('Apply')) {
                    el.click(); return true;
                }
            }
            return false;
        }""")
        return clicked

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

    async def _dismiss_success_modal(self):
        selectors = [
            'button[aria-label="Dismiss"]',
            'button[aria-label="Close"]',
            '.artdeco-modal__dismiss',
            'button:has-text("Done")',
            'button:has-text("Close")',
        ]
        for sel in selectors:
            try:
                btn = await self.page.wait_for_selector(sel, timeout=5000)
                if btn and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(1)
                    return
            except Exception:
                continue
