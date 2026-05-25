# Skill: Search Company Career Pages Directly

## Purpose
Scrape careers pages of Tier 1 + Tier 2 target companies directly. Catches jobs not posted to aggregators.

## When to Run
- After LinkedIn/Indeed scan
- Focus on Tier 1 + Tier 2 companies from `config/target-companies.json`
- Run weekly (not daily) — career pages change slowly

## Company Career Page URLs
```json
{
  "Anthropic": "https://www.anthropic.com/careers",
  "OpenAI": "https://openai.com/careers",
  "Google": "https://careers.google.com/jobs/results/?q=product+manager",
  "Microsoft": "https://jobs.careers.microsoft.com/global/en/search?q=product+manager",
  "Meta": "https://www.metacareers.com/jobs?q=product+manager",
  "Stripe": "https://stripe.com/jobs/search?name=product+manager",
  "Salesforce": "https://careers.salesforce.com/en/jobs/?search=product+manager",
  "Snowflake": "https://careers.snowflake.com/us/en/search-results?keywords=product+manager",
  "Databricks": "https://www.databricks.com/company/careers/open-positions?department=Product",
  "HubSpot": "https://www.hubspot.com/careers/jobs?hubs_signup-cta=careers-nav&q=product+manager",
  "Glean": "https://www.glean.com/careers",
  "Moveworks": "https://www.moveworks.com/careers",
  "ServiceNow": "https://jobs.smartrecruiters.com/ServiceNow?search=product+manager",
  "Workday": "https://www.workday.com/en-us/company/careers/open-positions.html?q=product+manager"
}
```

## Steps

### 1. Playwright Scrape per Company
```python
from playwright.async_api import async_playwright
import asyncio

async def scrape_company_careers(company_name, url, selectors):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        jobs = []
        cards = await page.query_selector_all(selectors["card"])
        for card in cards:
            title_el = await card.query_selector(selectors["title"])
            title = await title_el.inner_text() if title_el else ""
            
            if "product manager" in title.lower():
                link_el = await card.query_selector("a")
                href = await link_el.get_attribute("href") if link_el else ""
                jobs.append({"title": title, "url": href, "company": company_name})
        
        await browser.close()
        return jobs
```

### 2. Filter for PM Titles
Only keep if title contains (case-insensitive):
- "product manager"
- "product management"
- "PM"
- "APM"
- "associate product"

### 3. Normalize Fields
```json
{
  "id": "direct-<company_slug>-<title_slug>",
  "source": "company_direct",
  "title": "",
  "company": "",
  "location": "",
  "remote": true/false,
  "apply_url": "",
  "description": "",
  "scraped_at": "ISO timestamp"
}
```

### 4. Save Output
Write to `data/jobs-raw/company-direct-YYYY-MM-DD.json`

## Notes
- Company direct = highest quality signal (they posted it themselves)
- No salary data usually — that's OK, Tier 1/2 companies pay well
- Run this weekly, not daily — career pages don't change hourly
- If page uses heavy JS framework: use `wait_until="networkidle"` + extra sleep
