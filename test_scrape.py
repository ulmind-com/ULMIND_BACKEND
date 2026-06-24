import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        # Navigate
        url = "https://www.google.com/maps/search/Cafe+in+Durgapur"
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        # Take a screenshot to verify what it sees
        screenshot_path = "maps_debug.png"
        await page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")
        
        # Find place links
        cards = await page.query_selector_all('a[href*="/maps/place/"]')
        print(f"Found {len(cards)} place links.")
        
        for i, card in enumerate(cards[:5]):
            href = await card.evaluate("el => el.href")
            aria_label = await card.evaluate("el => el.getAttribute('aria-label') || ''")
            
            # Find parent card
            parent = await card.evaluate_handle("el => el.closest('div.Nv2yGc') || el.closest('div.UaQ7dd') || el.closest('div[role=\"article\"]') || el.parentElement")
            parent_html = await parent.evaluate("el => el.outerHTML")
            
            print(f"\n--- Card {i+1} ---")
            print(f"Name: {aria_label}")
            print(f"Href: {href[:100]}...")
            print(f"Parent Outer HTML snippet (first 300 chars): {parent_html[:300]}")
            
            # Check website indicators
            website_el = await parent.query_selector('a[data-item-id="authority"], a[aria-label*="Website"], a[aria-label*="website"]')
            website_text = await parent.query_selector('text="Website", text="website"')
            print(f"website_el found: {website_el is not None}")
            print(f"website_text found: {website_text is not None}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
