import asyncio, json, os
from playwright.async_api import async_playwright

async def main():
    os.makedirs("data/linkedin_session", exist_ok=True)
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            "data/linkedin_session",
            headless=False,
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.pages[0]
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        print("Browser opened. Log into LinkedIn in the window.")
        print("This script will wait up to 5 minutes...")
        for i in range(300):
            await asyncio.sleep(1)
            if "feed" in page.url:
                print(f"Logged in! ({i}s)")
                break
            if i % 30 == 0 and i > 0:
                print(f"Waiting... {i}s")
        cookies = await ctx.cookies()
        with open("data/linkedin_cookies.json", "w") as f:
            json.dump(cookies, f, indent=2)
        print(f"Saved {len(cookies)} cookies!")
        await ctx.close()

asyncio.run(main())
