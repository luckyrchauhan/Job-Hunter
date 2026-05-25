"""
Himalayas.app Job Scraper
Method: SSR HTML scraping (BeautifulSoup) — page is server-rendered, no Playwright needed.
URL: https://himalayas.app/jobs/product-management?page=N
Saves to: data/jobs-raw/himalayas-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_himalayas.py
  python scripts/scrapers/scrape_himalayas.py --max-pages 5
"""
import os, json, time, argparse, re
from datetime import datetime
from pathlib import Path
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    print("✗ beautifulsoup4 not installed — run: pip install beautifulsoup4")
    import sys; sys.exit(1)
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/himalayas-{DATE}.json"

BASE_URL = "https://himalayas.app/jobs/product-management"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

PM_TITLES = [
    "product manager", "senior product manager", "sr product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "group product manager", "director of product", "head of product",
    "vp of product", "vp product",
]

def is_pm_title(title: str) -> bool:
    return any(p in title.lower() for p in PM_TITLES)


def parse_page(html: str) -> list:
    """Extract job listings from Himalayas SSR HTML."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    seen_hrefs = set()

    # Job links pattern: /companies/{company-slug}/jobs/{job-slug}
    for link in soup.find_all("a", href=re.compile(r"/companies/.+/jobs/")):
        href = link.get("href", "")
        text = link.get_text(strip=True)

        if not text or text == "View job" or href in seen_hrefs:
            continue
        if not is_pm_title(text):
            continue
        seen_hrefs.add(href)

        # Extract company slug from href: /companies/{company-slug}/jobs/{job-slug}
        parts = href.split("/")
        company_slug = parts[2] if len(parts) > 2 else ""
        job_slug = parts[4].split("?")[0] if len(parts) > 4 else ""

        # Try to find company name in surrounding HTML
        card = link.find_parent("div") or link.find_parent("li") or link.find_parent("article")
        company_name = ""
        if card:
            # Look for company name element
            for el in card.find_all(["span", "p", "div"]):
                el_text = el.get_text(strip=True)
                if el_text and el_text != text and len(el_text) < 60 and "view job" not in el_text.lower():
                    # Likely company name
                    company_name = el_text
                    break

        # Fallback: prettify company slug
        if not company_name:
            company_name = company_slug.replace("-", " ").title()

        apply_url = f"https://himalayas.app{href.split('?')[0]}"

        jobs.append({
            "id": f"himalayas-{company_slug}-{job_slug}",
            "source": "himalayas",
            "title": text,
            "company": company_name,
            "location": "Remote",
            "remote": True,
            "salary_min": None,
            "salary_max": None,
            "visa_sponsored": False,  # Himalayas doesn't surface visa info in listing
            "posted_date": DATE,
            "apply_url": apply_url,
            "description": "",
            "scraped_at": datetime.now().isoformat(),
        })

    return jobs


def has_next_page(html: str, current_page: int) -> bool:
    """Check if there's a next page link."""
    soup = BeautifulSoup(html, "html.parser")
    next_link = soup.find("a", href=re.compile(rf"product-management\?page={current_page + 1}"))
    if next_link:
        return True
    # Also check for generic next/> pagination
    next_btn = soup.find("a", string=re.compile(r"next|›|»", re.IGNORECASE))
    return bool(next_btn)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=10)
    args = parser.parse_args()

    os.makedirs("data/jobs-raw", exist_ok=True)

    all_jobs = []
    seen_ids = set()

    for page_num in range(1, args.max_pages + 1):
        url = BASE_URL if page_num == 1 else f"{BASE_URL}?page={page_num}"
        print(f"  Page {page_num}: {url}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                print(f"    HTTP {resp.status_code} — stopping")
                break

            jobs = parse_page(resp.text)
            new = [j for j in jobs if j["id"] not in seen_ids]
            for j in new:
                seen_ids.add(j["id"])
                all_jobs.append(j)

            print(f"    {len(jobs)} PM jobs on page ({len(new)} new) | total: {len(all_jobs)}")

            if not new or not has_next_page(resp.text, page_num):
                break

            time.sleep(1.5)

        except Exception as e:
            print(f"    Error: {e}")
            break

    with open(OUT_FILE, "w") as f:
        json.dump(all_jobs, f, indent=2)
    print(f"Himalayas: {len(all_jobs)} PM jobs saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
