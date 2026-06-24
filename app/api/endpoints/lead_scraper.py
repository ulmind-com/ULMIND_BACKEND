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
            max_scroll_attempts = 8
            
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
                if card_count >= min(limit + 5, 45):
                    logger.info("Loaded sufficient business cards. Proceeding to filter.")
                    break
                
                # Execute scroll down
                prev_height = await page.evaluate(f'document.querySelector("{feed_selector}") ? document.querySelector("{feed_selector}").scrollHeight : 0')
                await page.evaluate(f'if(document.querySelector("{feed_selector}")) document.querySelector("{feed_selector}").scrollTop = document.querySelector("{feed_selector}").scrollHeight')
                
                await asyncio.sleep(1.2)
                
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
            
            # Gather and scrape listings in a single high-performance browser evaluation
            logger.info("Executing high-performance JS scraper in browser context...")
            leads = await page.evaluate("""(limit, niche) => {
                const results = [];
                const cards = Array.from(document.querySelectorAll('a[href*="/maps/place/"]'));
                
                for (const card of cards) {
                    if (results.length >= limit) break;
                    
                    try {
                        const parent = card.closest('div[role="article"]') || card.closest('div.Nv2yGc') || card.closest('div.UaQ7dd') || card.parentElement;
                        if (!parent) continue;
                        
                        // Check if it has a website
                        let hasWebsite = false;
                        const websiteEl = parent.querySelector('a[data-item-id="authority"], a[aria-label*="Website"], a[aria-label*="website"]');
                        if (websiteEl) {
                            hasWebsite = true;
                        } else {
                            const anchors = Array.from(parent.querySelectorAll('a'));
                            for (const anchor of anchors) {
                                if (!anchor.href) continue;
                                try {
                                    const url = new URL(anchor.href);
                                    const isGoogle = url.hostname.includes('google') || url.hostname.includes('gstatic') || url.protocol === 'javascript:';
                                    if (!isGoogle) {
                                        hasWebsite = true;
                                        break;
                                    }
                                } catch(e) {}
                            }
                        }
                        
                        if (hasWebsite) continue;
                        
                        // Extract Name
                        let name = "";
                        const nameEl = card.querySelector('div.qBF1Pd, div.fontHeadlineSmall');
                        if (nameEl) {
                            name = nameEl.innerText.trim();
                        } else {
                            name = (card.getAttribute('aria-label') || '').trim();
                        }
                        
                        if (!name) continue;
                        
                        // Deduplicate by name
                        if (results.some(r => r.companyName === name)) continue;
                        
                        // Extract Maps Link
                        const mapsUrl = card.href;
                        if (!mapsUrl || !mapsUrl.startsWith('http')) continue;
                        
                        // Extract Rating
                        let rating = 0.0;
                        const ratingEl = parent.querySelector('span.MW4etd, span[aria-label*="stars"]');
                        if (ratingEl) {
                            const ratingText = ratingEl.innerText;
                            rating = parseFloat(ratingText.split(/\\s+/)[0].replace(',', '.')) || 0.0;
                        }
                        
                        // Extract Info (Address & Phone)
                        const infoDivs = Array.from(parent.querySelectorAll('div.W4Efsd'));
                        const infoTexts = infoDivs.map(div => div.innerText.trim()).filter(Boolean);
                        let address = "Address not listed";
                        let phone = null;
                        
                        const phoneRegex = /(\\+?\\d{1,4}[\\s-]?\\(?\\d{1,3}\\)?[\\s-]?\\d{3,5}[\\s-]?\\d{3,5})/;
                        
                        for (const text of infoTexts) {
                            const phoneMatch = text.match(phoneRegex);
                            if (phoneMatch && !phone) {
                                const possiblePhone = phoneMatch[0].trim();
                                const cleanDigits = possiblePhone.replace(/\\D/g, '');
                                if (cleanDigits.length >= 7) {
                                    phone = possiblePhone;
                                }
                            }
                            if (text.includes(',') && text.length > 10 && !text.includes('★') && !text.includes('stars')) {
                                address = text;
                            }
                        }
                        
                        if (address === "Address not listed" && infoTexts.length > 1) {
                            for (const t of infoTexts) {
                                if (/\\d/.test(t) && t.length > 8 && !t.includes('★')) {
                                    address = t;
                                    break;
                                }
                            }
                        }
                        
                        results.push({
                            "companyName": name,
                            "phone": phone,
                            "address": address,
                            "rating": rating,
                            "mapsLink": mapsUrl,
                            "maps_url": mapsUrl,
                            "industry": niche.charAt(0).toUpperCase() + niche.slice(1),
                            "contactEmail": "info@pending-website.com",
                            "status": "Lead"
                        });
                    } catch(e) {}
                }
                return results;
            }""", limit, niche)
            logger.info(f"Successfully scraped {len(leads)} leads from browser page.")
            
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
