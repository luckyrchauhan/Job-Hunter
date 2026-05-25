# Skill: Search YC Jobs (Work at a Startup)

## Purpose
Scrape YC's job board — https://www.workatastartup.com. High-quality startups, many sponsor H1B.

## Target URL
```
https://www.workatastartup.com/jobs?role=pm&remote=true&visa=true
https://www.workatastartup.com/jobs?role=pm&visa=true
```

## Steps

### 1. Playwright Scrape with Visa Filter
YC board has a `visa=true` filter — use it to pre-filter H1B sponsors.

```python
from playwright.async_api import async_playwright
import asyncio

async def scrape_yc_jobs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(
            "https://www.workatastartup.com/jobs?role=pm&visa=true&remote=true",
            wait_until="networkidle"
        )
        
        # Scroll to load all jobs (lazy loading)
        for _ in range(5):
            await page.keyboard.press("End")
            await asyncio.sleep(1.5)
        
        jobs = await page.evaluate('''() => {
            const cards = document.querySelectorAll(".job-card");
            return Array.from(cards).map(card => ({
                title: card.querySelector(".role-name")?.innerText,
                company: card.querySelector(".company-name")?.innerText,
                location: card.querySelector(".job-location")?.innerText,
                salary: card.querySelector(".job-compensation")?.innerText,
                url: card.querySelector("a")?.href
            }));
        }''')
        
        await browser.close()
        return jobs
```

### 2. Normalize Fields
```json
{
  "id": "yc-<company_slug>-<role_slug>",
  "source": "yc_jobs",
  "title": "",
  "company": "",
  "yc_batch": "W24/S24 etc",
  "location": "",
  "remote": true,
  "salary_min": null,
  "salary_max": null,
  "visa_sponsored": true,
  "posted_date": "",
  "apply_url": "",
  "description": "",
  "scraped_at": "ISO timestamp"
}
```

### 3. Save Output
Write to `data/jobs-raw/yc-YYYY-MM-DD.json`

## Notes
- `visa=true` filter = company explicitly accepts visa candidates — high confidence H1B
- Set `visa_sponsored: true` for all YC jobs with this filter — skip H1B re-check
- YC companies are generally PM-friendly; score them +0.5 bonus in fit scoring
- No Apify needed — YC board scrapes cleanly with Playwright
