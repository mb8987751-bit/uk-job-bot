import asyncio
import json
import os
from playwright.async_api import async_playwright

async def main():
    print("=== LinkedIn Cookie Saver ===")
    print("This will open a browser. Log into LinkedIn manually.")
    print("Cookies will be saved after login.\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        input("Press Enter AFTER you have logged into LinkedIn in the browser...")

        cookies = await context.cookies()
        os.makedirs("data", exist_ok=True)
        with open("data/linkedin_cookies.json", "w") as f:
            json.dump(cookies, f, indent=2)
        print(f"Saved {len(cookies)} cookies to data/linkedin_cookies.json")
        await browser.close()

asyncio.run(main())
