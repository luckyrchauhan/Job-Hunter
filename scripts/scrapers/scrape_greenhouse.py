"""
Greenhouse + Lever Job Scraper
Method: Free public APIs — no key needed, returns full JD
Greenhouse: https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true
Lever:      https://api.lever.co/v0/postings/{company}?mode=json

Scrapes 60+ top PM-hiring companies across both ATS platforms.
Saves to: data/jobs-raw/greenhouse-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_greenhouse.py
"""
import json, re, time, urllib.request, html
from datetime import datetime, timedelta
from pathlib import Path

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = Path(f"data/jobs-raw/greenhouse-{DATE}.json")

PM_TITLES = [
    "product manager", "senior product manager", "sr product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "group product manager", "head of product", "director of product",
]
EXCLUDE_TITLES = [
    "marketing", "sales", "recruiter", "data scientist", "software engineer",
    "developer", "designer", "analyst", "data analyst", "business analyst",
    "vp of product", "vice president", "chief product", "svp",
]

# Top companies using Greenhouse ATS (verified active PM jobs)
GREENHOUSE_COMPANIES = [
    # Verified active
    "stripe", "lyft", "pinterest", "dropbox", "twilio", "okta",
    "cloudflare", "datadog", "mongodb", "elastic", "pagerduty",
    "intercom", "salesloft", "asana", "affirm", "sezzle", "adyen",
    "checkr", "airbnb", "doordash", "coinbase",
    # Likely active — big enough
    "figma", "notion", "airtable", "databricks", "snowflake",
    "plaid", "brex", "gusto", "rippling", "carta",
    "benchling", "ironclad", "verkada", "snyk", "harness",
    "retool", "replit", "vanta", "drata", "lacework",
    "amplitude", "mixpanel", "heap", "statsig",
    "robinhood", "faire", "lattice", "scale-ai",
    "zendesk", "hubspot", "outreach",
]

# Top companies using Lever ATS (verified active PM jobs)
LEVER_COMPANIES = [
    # Verified
    "netflix", "pinterest", "yelp",
    # Likely active
    "thumbtack", "calm", "duolingo", "headspace", "nerdwallet",
    "betterment", "wealthfront",
    "shipbob", "flexport", "project44",
    "contentful", "algolia", "sendbird", "loom",
    "miro", "lucidchart", "whimsical",
    "pillar", "gem-com", "ashby",
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_TITLES):
        return False
    return any(pm in t for pm in PM_TITLES)

def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def parse_salary(text: str):
    if not text:
        return None, None
    text = text.replace("K", "000").replace("k", "000")
    nums = re.findall(r"[\d,]+", text)
    nums = [int(n.replace(",", "")) for n in nums if int(n.replace(",", "")) > 10000]
    if len(nums) >= 2:
        return min(nums), max(nums)
    elif len(nums) == 1:
        return nums[0], nums[0]
    return None, None

def extract_salary_from_text(text: str) -> str:
    patterns = [
        r"\$[\d,]+[Kk]?\s*[-–]\s*\$[\d,]+[Kk]?(?:\s*/\s*(?:yr|year|annually))?",
        r"\$[\d,]+[Kk]?\s*(?:per year|\/year|\/yr|annually)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return ""

def fetch_json(url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JobHunter/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None

def scrape_greenhouse(company: str) -> list:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
    data = fetch_json(url)
    if not data:
        return []

    jobs = []
    for job in data.get("jobs", []):
        title = job.get("title", "")
        if not is_pm_title(title):
            continue

        location = job.get("location", {}).get("name", "") or ""
        # Filter: remote or US
        if location and not any(kw in location.lower() for kw in ["remote", "united states", "usa", "us", "new york", "san francisco", "boston", "chicago", "seattle", "austin"]):
            continue

        content_html = job.get("content", "")
        description = strip_html(content_html)[:6000]
        salary_text = extract_salary_from_text(description)
        salary_min, salary_max = parse_salary(salary_text)

        # Parse posted date
        updated = job.get("first_published", job.get("updated_at", ""))
        try:
            posted = datetime.fromisoformat(updated[:10]).strftime("%Y-%m-%d")
        except Exception:
            posted = DATE

        # Only recent jobs (past 14 days)
        try:
            days_old = (datetime.now().date() - datetime.strptime(posted, "%Y-%m-%d").date()).days
            if days_old > 14:
                continue
        except Exception:
            pass

        remote = "remote" in location.lower() or "remote" in description.lower()[:300]

        jobs.append({
            "id": f"greenhouse-{job.get('id', '')}",
            "source": "greenhouse",
            "title": title.strip(),
            "company": job.get("company_name", company).strip(),
            "location": location.strip(),
            "remote": remote,
            "salary_text": salary_text,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "posted_date": posted,
            "apply_url": job.get("absolute_url", ""),
            "description": description,
            "source_query": company,
            "scraped_at": datetime.now().isoformat(),
        })

    return jobs


def scrape_lever(company: str) -> list:
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    data = fetch_json(url)
    if not data or not isinstance(data, list):
        return []

    jobs = []
    for job in data:
        title = job.get("text", "")
        if not is_pm_title(title):
            continue

        location = job.get("categories", {}).get("location", "") or job.get("workplaceType", "")
        commitment = job.get("categories", {}).get("commitment", "") or ""

        # Filter: remote or US
        if location and not any(kw in location.lower() for kw in ["remote", "united states", "usa", "us", ""]):
            continue

        # Build description from lists
        desc_parts = []
        for section in job.get("lists", []):
            desc_parts.append(section.get("text", ""))
            for item in section.get("content", "").split("<li>"):
                clean = strip_html(item).strip()
                if clean:
                    desc_parts.append(f"• {clean}")
        desc_parts.append(strip_html(job.get("description", "")))
        desc_parts.append(strip_html(job.get("additional", "")))
        description = "\n".join(desc_parts)[:6000]

        salary_text = extract_salary_from_text(description)
        salary_min, salary_max = parse_salary(salary_text)

        posted_ts = job.get("createdAt", 0)
        if posted_ts:
            posted = datetime.fromtimestamp(posted_ts / 1000).strftime("%Y-%m-%d")
            days_old = (datetime.now().date() - datetime.strptime(posted, "%Y-%m-%d").date()).days
            if days_old > 14:
                continue
        else:
            posted = DATE

        remote = "remote" in (location or "").lower() or "remote" in commitment.lower()

        jobs.append({
            "id": f"lever-{job.get('id', '')}",
            "source": "lever",
            "title": title.strip(),
            "company": company.replace("-", " ").title().strip(),
            "location": location.strip(),
            "remote": remote,
            "salary_text": salary_text,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "posted_date": posted,
            "apply_url": job.get("hostedUrl", ""),
            "description": description,
            "source_query": company,
            "scraped_at": datetime.now().isoformat(),
        })

    return jobs


def main():
    Path("data/jobs-raw").mkdir(parents=True, exist_ok=True)
    all_jobs = []
    seen_ids = set()

    print(f"Greenhouse scraper — {len(GREENHOUSE_COMPANIES)} companies")
    gh_count = 0
    for i, company in enumerate(GREENHOUSE_COMPANIES):
        jobs = scrape_greenhouse(company)
        for j in jobs:
            if j["id"] not in seen_ids:
                seen_ids.add(j["id"])
                all_jobs.append(j)
                gh_count += 1
        if jobs:
            print(f"  ✓ {company}: {len(jobs)} PM jobs")
        time.sleep(0.3)  # gentle rate limit

    print(f"\nLever scraper — {len(LEVER_COMPANIES)} companies")
    lv_count = 0
    for company in LEVER_COMPANIES:
        jobs = scrape_lever(company)
        for j in jobs:
            if j["id"] not in seen_ids:
                seen_ids.add(j["id"])
                all_jobs.append(j)
                lv_count += 1
        if jobs:
            print(f"  ✓ {company}: {len(jobs)} PM jobs")
        time.sleep(0.3)

    OUT_FILE.write_text(json.dumps(all_jobs, indent=2))
    salary_count = sum(1 for j in all_jobs if j.get("salary_text"))
    print(f"\nGreenhouse+Lever: {len(all_jobs)} PM jobs saved to {OUT_FILE}")
    print(f"  Greenhouse: {gh_count} | Lever: {lv_count} | With salary: {salary_count}")


if __name__ == "__main__":
    main()
