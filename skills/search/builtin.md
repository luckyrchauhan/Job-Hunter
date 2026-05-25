# Skill: Search Builtin Jobs

## Purpose
Scrape Builtin (builtin.com) — strong source for PM roles at tech companies in major US cities + remote.

## Target URLs
```
https://builtin.com/jobs/remote/product-management
https://builtin.com/boston/jobs/product-management
https://builtin.com/new-york/jobs/product-management
https://builtin.com/chicago/jobs/product-management
https://builtin.com/austin/jobs/product-management
```

## Steps

### 1. Apify Scraper (Preferred)
Actor ID: Check Apify store for "builtin scraper" — if not available, use Playwright.

### 2. Playwright Scrape
```python
from playwright.async_api import async_playwright
import asyncio

BUILTIN_URLS = [
    "https://builtin.com/jobs/remote/product-management",
    "https://builtin.com/boston/jobs/product-management",
]

async def scrape_builtin():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        jobs = []
        
        for url in BUILTIN_URLS:
            await page.goto(url, wait_until="networkidle")
            await asyncio.sleep(2)
            
            # Scroll to load more jobs
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)
            
            cards = await page.query_selector_all('[data-id="job-card"]')
            for card in cards:
                # extract fields
                pass
            
        await browser.close()
        return jobs
```

### 3. Normalize Fields
```json
{
  "id": "builtin-<job_id>",
  "source": "builtin",
  "title": "",
  "company": "",
  "location": "",
  "remote": true/false,
  "salary_min": null,
  "salary_max": null,
  "posted_date": "",
  "apply_url": "",
  "description": "",
  "scraped_at": "ISO timestamp"
}
```

### 4. Save Output
Write to `data/jobs-raw/builtin-YYYY-MM-DD.json`

## Notes
- Builtin shows remote-friendly companies prominently
- Good coverage of mid-size tech companies (Series B–D)
- Many companies on Builtin are known H1B sponsors
