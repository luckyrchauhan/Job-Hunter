"""
YC Work at a Startup Scraper — visa=true filter
Saves to: data/jobs-raw/yc-YYYY-MM-DD.json
"""
import os, json, asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/yc-{DATE}.json"

async def main():
    os.makedirs("data/jobs-raw", exist_ok=True)
    jobs = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        url = "https://www.workatastartup.com/jobs?role=pm&visa=true"
        print(f"  Fetching: {url}")
        await page.goto(url, wait_until="networkidle", timeout=45000)
        await asyncio.sleep(3)
        
        # Scroll to load more
        for _ in range(4):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)
        
        # Extract job data
        job_data = await page.evaluate("""() => {
            const jobs = [];
            const cards = document.querySelectorAll('.job-name, [class*="JobListing"], [class*="job-item"]');
            
            // Try direct link extraction
            const links = document.querySelectorAll('a[href*="/jobs/"]');
            links.forEach(link => {
                const card = link.closest('[class*="job"], [class*="listing"], li') || link.parentElement;
                if (card) {
                    const text = card.innerText || '';
                    jobs.push({
                        title: link.innerText.trim() || text.split('\\n')[0].trim(),
                        url: link.href,
                        card_text: text.substring(0, 300)
                    });
                }
            });
            return jobs;
        }""")
        
        seen = set()
        for j in job_data:
            if j.get("url") and "/jobs/" in j.get("url","") and j["url"] not in seen:
                seen.add(j["url"])
                title = j.get("title","").strip()
                if not title or len(title) < 3:
                    continue
                jobs.append({
                    "id": f"yc-{j['url'].split('/')[-1]}",
                    "source": "yc_jobs",
                    "title": title,
                    "company": "",
                    "location": "Remote",
                    "remote": True,
                    "visa_sponsored": True,
                    "salary_min": None,
                    "salary_max": None,
                    "posted_date": DATE,
                    "apply_url": j["url"],
                    "description": j.get("card_text",""),
                    "scraped_at": datetime.now().isoformat(),
                })
        
        await browser.close()
    
    with open(OUT_FILE, "w") as f:
        json.dump(jobs, f, indent=2)
    print(f"YC Jobs: {len(jobs)} jobs saved to {OUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
