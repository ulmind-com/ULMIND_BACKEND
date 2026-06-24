from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import asyncio
import logging
import re
from playwright.async_api import async_playwright
from app.db.database import get_db
from app.api.deps import get_current_active_admin
from app.core.datetime_utils import get_now

router = APIRouter()
logger = logging.getLogger(__name__)

SCRAPE_TIMEOUT_MS = 90000

@router.get("/scrape")
async def scrape_leads(
    niche: str = Query(..., description="E.g., dentist, plumber, restaurant"),
    location: str = Query(..., description="E.g., Kolkata, New York"),
    limit: int = Query(50, description="Max leads to fetch"),
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """
    Directly scrapes Google Maps for businesses matching the query (niche + location)
    that do NOT have a website listed, returning real-time leads.
    """
    search_query = f"{niche} in {location}"
    url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
    
    logger.info(f"Starting real Google Maps Playwright scrape for: '{search_query}' (limit: {limit})")
    
    leads = []
    
    try:
        async with async_playwright() as p:
            # Launch headless chromium
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--single-process",
                        "--no-zygote",
                        "--no-first-run",
                        "--disable-renderer-backgrounding",
                        "--disable-background-timer-throttling",
                        "--js-flags=--max-old-space-size=128"
                    ]
                )
            except Exception as launch_err:
                logger.error(f"Failed to launch chromium: {launch_err}")
                raise HTTPException(
                    status_code=500,
                    detail="Chromium not installed or failed to launch. Please run 'playwright install chromium' on your host system."
                )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            
            page = await context.new_page()
            
            logger.info(f"Navigating to Google Maps: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=SCRAPE_TIMEOUT_MS)
            await asyncio.sleep(5)
            
            # Handle Google's cookie consent prompts if they appear
            if "consent.google.com" in page.url or await page.locator("form[action*='consent'] button").count() > 0:
                logger.info("Accepting Google consent prompt...")
                try:
                    agree_btn = page.locator("form[action*='consent'] button").last
                    await agree_btn.click(timeout=5000)
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(2)
                except Exception as consent_err:
                    logger.warning(f"Could not click consent button: {consent_err}")
            
            # Select the left sidebar housing the results
            feed_selector = "div[role='feed']"
            try:
                await page.wait_for_selector(feed_selector, timeout=20000)
            except Exception:
                # Fallback to secondary selector if role feed isn't directly on container
                feed_selector = "div.m67rPy"
            
            logger.info(f"Sidebar locator identified: '{feed_selector}'")
            
            # Scroll panel focusing
            try:
                await page.focus(feed_selector)
            except Exception:
                pass

            scrolled_empty_attempts = 0
            max_scroll_attempts = 15
            
            # Loop for deep scrolling
            for attempt in range(max_scroll_attempts):
                # Count the current number of place cards loaded
                card_count = await page.locator('a[href*="/maps/place/"]').count()
                logger.info(f"Scroll iteration {attempt + 1}: Found {card_count} potential place links.")
                
                # Check for "You've reached the end of the list"
                end_locator = page.locator("text='You\'ve reached the end of the list'")
                if await end_locator.count() > 0:
                    logger.info("Found end of list label in DOM. Stopping scroll.")
                    break
                
                # Check page text for end marker
                page_text = await page.evaluate("() => document.body.innerText")
                if "reached the end of the list" in page_text or "You've reached the end" in page_text:
                    logger.info("Detected end of list text. Stopping scroll.")
                    break
                
                # If we have loaded enough place cards to filter, stop early to save memory and time
                if card_count >= min(limit + 5, 55):
                    logger.info("Loaded sufficient business cards. Proceeding to filter.")
                    break
                
                # Execute scroll down
                prev_height = await page.evaluate(f'document.querySelector("{feed_selector}") ? document.querySelector("{feed_selector}").scrollHeight : 0')
                await page.evaluate(f'if(document.querySelector("{feed_selector}")) document.querySelector("{feed_selector}").scrollTop = document.querySelector("{feed_selector}").scrollHeight')
                
                await asyncio.sleep(1.5)
                
                new_height = await page.evaluate(f'document.querySelector("{feed_selector}") ? document.querySelector("{feed_selector}").scrollHeight : 0')
                
                if new_height == prev_height:
                    scrolled_empty_attempts += 1
                    # Press down key to trigger loading
                    try:
                        await page.keyboard.press("PageDown")
                    except:
                        pass
                    if scrolled_empty_attempts >= 3:
                        logger.info("Scroll height unchanged for 3 attempts. Stopping.")
                        break
                else:
                    scrolled_empty_attempts = 0
            
            # Gather all links pointing to individual places
            cards = await page.query_selector_all('a[href*="/maps/place/"]')
            logger.info(f"Scraping detailed information from {len(cards)} listings...")
            
            for index, card in enumerate(cards):
                if len(leads) >= limit:
                    break
                
                try:
                    # Get parent container (a listing is always contained in an article/card container)
                    parent = await card.evaluate_handle("el => el.closest('div[role=\"article\"]') || el.closest('div.Nv2yGc') || el.closest('div.UaQ7dd') || el.parentElement")
                    if not parent:
                        continue
                    
                    # Filter out listings that have a website
                    has_website = False
                    
                    # 1. Check for standard website elements (authority links or website label buttons)
                    website_el = await parent.query_selector('a[data-item-id="authority"], a[aria-label*="Website"], a[aria-label*="website"]')
                    if website_el:
                        has_website = True
                    
                    # 2. Look for any external anchor tags to detect website links
                    if not has_website:
                        anchors = await parent.query_selector_all('a')
                        for anchor in anchors:
                            is_google_or_internal = await anchor.evaluate("""el => {
                                try {
                                    if (!el.href) return true;
                                    const url = new URL(el.href);
                                    return url.hostname.includes('google') || url.hostname.includes('gstatic') || url.protocol === 'javascript:';
                                } catch(e) {
                                    return true;
                                }
                            }""")
                            if not is_google_or_internal:
                                has_website = True
                                break
                            
                    if has_website:
                        continue  # Discard if website exists
                    
                    # 2. Extract Business Name
                    name = ""
                    name_el = await card.query_selector('div.qBF1Pd, div.fontHeadlineSmall')
                    if name_el:
                        name = await name_el.inner_text()
                    else:
                        name = await card.evaluate("el => el.getAttribute('aria-label') || ''")
                    
                    name = name.strip()
                    if not name:
                        continue
                        
                    # Deduplicate name
                    if any(l["companyName"] == name for l in leads):
                        continue
                    
                    # 3. Extract Real maps URL from the specific card anchor
                    maps_url = await card.evaluate("el => el.href")
                    if not maps_url or not maps_url.startswith("http"):
                        continue
                    
                    # 4. Extract Rating
                    rating = 0.0
                    rating_el = await parent.query_selector('span.MW4etd, span[aria-label*="stars"]')
                    if rating_el:
                        rating_text = await rating_el.inner_text()
                        try:
                            rating = float(rating_text.split()[0].replace(',', '.'))
                        except:
                            aria_label = await rating_el.evaluate("el => el.getAttribute('aria-label') || ''")
                            rating_match = re.search(r'(\d+(\.\d+)?)', aria_label)
                            if rating_match:
                                rating = float(rating_match.group(1))
                    
                    # 5. Extract Address & Phone Number
                    address = "Address not listed"
                    phone = None
                    
                    info_divs = await parent.query_selector_all('div.W4Efsd')
                    info_texts = []
                    for div in info_divs:
                        text = await div.inner_text()
                        if text:
                            info_texts.append(text.strip())
                            
                    for text in info_texts:
                        # Extract telephone pattern
                        phone_match = re.search(r'(\+?\d{1,4}[\s-]?\(?\d{1,3}\)?[\s-]?\d{3,5}[\s-]?\d{3,5})', text)
                        if phone_match and not phone:
                            possible_phone = phone_match.group(0).strip()
                            if len(re.sub(r'\D', '', possible_phone)) >= 7:
                                phone = possible_phone
                        
                        # Extract address (usually has commas and doesn't contain stars)
                        if "," in text and len(text) > 10 and "★" not in text and "stars" not in text:
                            address = text.strip()
                            
                    # Fallback address parser from items
                    if address == "Address not listed" and len(info_texts) > 1:
                        for t in info_texts:
                            if any(char.isdigit() for char in t) and len(t) > 8 and "★" not in t:
                                address = t.strip()
                                break
                    
                    leads.append({
                        "companyName": name,
                        "phone": phone,
                        "address": address,
                        "rating": rating,
                        "mapsLink": maps_url,
                        "maps_url": maps_url,
                        "industry": niche.capitalize(),
                        "contactEmail": "info@pending-website.com",
                        "status": "Lead"
                    })
                    
                except Exception as card_err:
                    logger.error(f"Error parsing listing item: {card_err}")
            
            await browser.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Playwright execution error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Real-time Google Maps scraping failed: {str(e)}"
        )
        
    return {"status": "success", "count": len(leads), "leads": leads}
