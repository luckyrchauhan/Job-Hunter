# Skill: Search Wellfound (AngelList) Jobs

## Purpose
Scrape Wellfound for PM roles at startups. Best source for Series A–C startups that sponsor H1B.

## Inputs
- Read `config/search-params.json`
- Read `config/target-companies.json` tier_3 companies

## Steps

### 1. Direct Playwright Scrape
Wellfound has no official Apify actor — use Playwright.

Target URLs:
```
https://wellfound.com/jobs?role=product-manager&remote=true
https://wellfound.com/jobs?role=product-manager&location=boston
https://wellfound.com/jobs?role=product-manager&location=new-york
```

### 2. Playwright Script
```python
from playwright.async_api import async_playwright
import asyncio, json
from datetime import datetime

async def scrape_wellfound():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        urls = [
            "https://wellfound.com/jobs?role=product-manager&remote=true",
            "https://wellfound.com/jobs?role=product-manager&location=boston"
        ]
        
        jobs = []
        for url in urls:
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_selector('[data-test="JobListing"]', timeout=10000)
            
            cards = await page.query_selector_all('[data-test="JobListing"]')
            for card in cards:
                title = await card.query_selector('h2')
                company = await card.query_selector('[data-test="company-name"]')
                jobs.append({
                    "title": await title.inner_text() if title else "",
                    "company": await company.inner_text() if company else "",
                    # ... extract other fields
                })
            await asyncio.sleep(2)
        
        await browser.close()
        return jobs
```

### 3. Normalize & Save
```json
{
  "id": "wellfound-<slug>",
  "source": "wellfound",
  "title": "",
  "company": "",
  "company_stage": "seed/series-a/series-b/series-c",
  "team_size": "",
  "location": "",
  "remote": true/false,
  "salary_min": null,
  "salary_max": null,
  "equity_min": null,
  "equity_max": null,
  "posted_date": "",
  "apply_url": "",
  "description": "",
  "scraped_at": "ISO timestamp"
}
```

### 4. Save Output
Write to `data/jobs-raw/wellfound-YYYY-MM-DD.json`

## Notes
- Wellfound shows equity ranges — capture this
- `company_stage` helps infer H1B likelihood (Series B+ more likely to sponsor)
- Login not required for basic job listings
- Rate limit: 2s between page loads
