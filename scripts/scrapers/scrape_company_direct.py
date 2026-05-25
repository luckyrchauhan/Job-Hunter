"""
Company Direct Career Page Scraper
Scrapes career pages of target companies directly.
Runs weekly (Mondays only, enforced in daily-scan.sh).
Saves to: data/jobs-raw/company_direct-YYYY-MM-DD.json

Target companies loaded from config/target-companies.json tier_1 + tier_2.
Each company entry needs a "careers_url" key — add as needed.

Usage:
  python scripts/scrapers/scrape_company_direct.py
  python scripts/scrapers/scrape_company_direct.py --company stripe
  python scripts/scrapers/scrape_company_direct.py --max 5   # top N companies only
"""
import os, json, asyncio, argparse
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/company_direct-{DATE}.json"
BASE_DIR = Path(__file__).parent.parent.parent
COMPANIES_FILE = BASE_DIR / "config" / "target-companies.json"

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "head of product", "director of product",
]

# Hardcoded career URLs for top H1B sponsor companies
# Add more as needed — these are the most reliable PM hiring sources
COMPANY_CAREER_PAGES = [
    {"company": "Stripe", "url": "https://stripe.com/jobs/search?teams[]=Product+Management"},
    {"company": "Airbnb", "url": "https://careers.airbnb.com/positions/?department=Product+Management"},
    {"company": "Databricks", "url": "https://www.databricks.com/company/careers/open-positions?department=Product+Management"},
    {"company": "Snowflake", "url": "https://careers.snowflake.com/jobs?department=Product+Management"},
    {"company": "Figma", "url": "https://www.figma.com/careers/#job-openings"},
    {"company": "Notion", "url": "https://www.notion.so/careers"},
    {"company": "Rippling", "url": "https://www.rippling.com/careers"},
    {"company": "Scale AI", "url": "https://scale.com/careers#openings"},
    {"company": "Cohere", "url": "https://cohere.com/about/careers"},
    {"company": "Anthropic", "url": "https://www.anthropic.com/careers#open-roles"},
    {"company": "OpenAI", "url": "https://openai.com/careers/"},
    {"company": "Palantir", "url": "https://jobs.lever.co/palantir?team=Product"},
    {"company": "HubSpot", "url": "https://www.hubspot.com/careers/jobs?hubs_signup-url=www.hubspot.com/careers&page=1#jobs-list"},
    {"company": "Twilio", "url": "https://www.twilio.com/en-us/company/jobs"},
    {"company": "Datadog", "url": "https://careers.datadoghq.com/all-jobs/?departments=Product"},
    {"company": "Confluent", "url": "https://www.confluent.io/careers/open-roles/?department=Product"},
    {"company": "dbt Labs", "url": "https://www.getdbt.com/dbt-labs/open-roles/"},
    {"company": "Amplitude", "url": "https://amplitude.com/careers"},
    {"company": "Segment", "url": "https://www.twilio.com/en-us/company/jobs"},  # acquired by Twilio
    {"company": "Brex", "url": "https://www.brex.com/careers#open-positions"},
]


def is_pm_title(title: str) -> bool:
    t = title.lower()
    return any(pm in t for pm in PM_TITLES)


async def scrape_company(company: str, url: str, page) -> list:
    """Scrape a single company career page for PM roles."""
    jobs = []
    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)

        import asyncio
        await asyncio.sleep(3)

        # Scroll to trigger lazy loading
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

        # Generic extraction — works for most simple career pages
        job_data = await page.evaluate("""() => {
            const results = [];
            const selectors = [
                'a[href*="product-manager"]',
                'a[href*="product_manager"]',
                '[class*="job"] a, [class*="position"] a, [class*="role"] a, [class*="opening"] a',
                'li a, .careers a, #careers a',
            ];

            const seen = new Set();
            selectors.forEach(sel => {
                try {
                    document.querySelectorAll(sel).forEach(a => {
                        if (!a.href || seen.has(a.href)) return;
                        const text = a.innerText.trim() || a.title || '';
                        if (!text || text.length < 5) return;
                        seen.add(a.href);
                        const parent = a.closest('[class*="job"], [class*="position"], [class*="role"], li') || a.parentElement;
                        const parentText = parent ? parent.innerText.substring(0, 300) : '';
                        results.push({ url: a.href, title: text, context: parentText });
                    });
                } catch(e) {}
            });

            // Also try JSON-LD structured data
            document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
                try {
                    const data = JSON.parse(s.textContent);
                    const jobs = Array.isArray(data) ? data : (data['@graph'] || [data]);
                    jobs.forEach(j => {
                        if (j['@type'] === 'JobPosting' && j.title) {
                            results.push({ url: j.url || '', title: j.title, context: j.description || '' });
                        }
                    });
                } catch(e) {}
            });

            return results;
        }""")

        seen = set()
        for j in job_data:
            title = j.get("title", "").strip()
            if not title or not is_pm_title(title):
                continue
            job_url = j.get("url", url)
            if job_url in seen:
                continue
            seen.add(job_url)

            job_id = job_url.rstrip("/").split("/")[-1] or title.lower().replace(" ", "-")[:40]
            jobs.append({
                "id": f"direct-{company.lower().replace(' ', '_')}-{job_id[:40]}",
                "source": "company_direct",
                "title": title,
                "company": company,
                "location": "See listing",
                "remote": None,  # unknown until we click through
                "salary_text": "",
                "salary_min": None, "salary_max": None,
                "posted_date": DATE,
                "apply_url": job_url,
                "description": j.get("context", "")[:2000],
                "scraped_at": datetime.now().isoformat(),
            })

        print(f"    {company}: {len(jobs)} PM jobs found")

    except Exception as e:
        print(f"    {company} error: {e}")

    return jobs


async def scrape_all(companies: list) -> list:
    from playwright.async_api import async_playwright

    all_jobs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for entry in companies:
            company = entry["company"]
            url = entry["url"]
            print(f"  Scraping {company}...")
            jobs = await scrape_company(company, url, page)
            all_jobs.extend(jobs)

            import asyncio
            await asyncio.sleep(2)  # polite delay

        await browser.close()

    return all_jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", type=str, help="Filter to one company (partial match)")
    parser.add_argument("--max", type=int, default=0, help="Limit to top N companies")
    args = parser.parse_args()

    os.makedirs("data/jobs-raw", exist_ok=True)

    companies = COMPANY_CAREER_PAGES
    if args.company:
        companies = [c for c in companies if args.company.lower() in c["company"].lower()]
        if not companies:
            print(f"No company matched '{args.company}'")
            return
    if args.max:
        companies = companies[:args.max]

    print(f"Scraping {len(companies)} company career pages...")
    jobs = asyncio.run(scrape_all(companies))

    seen = set()
    unique = [j for j in jobs if j["id"] not in seen and not seen.add(j["id"])]

    with open(OUT_FILE, "w") as f:
        json.dump(unique, f, indent=2)
    print(f"\nCompany Direct: {len(unique)} PM jobs saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
