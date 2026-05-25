# Skill: Search LinkedIn Jobs

## Purpose
Scrape LinkedIn job postings for PM roles matching Lucky's search params. Use Apify LinkedIn Jobs Scraper actor.

## Inputs
- Read `config/search-params.json` for roles, locations, keywords
- Read `config/target-companies.json` for priority companies
- Read `.env` for `APIFY_API_TOKEN`

## Steps

### 1. Build Search Queries
Generate search query combinations:
- Roles: "Product Manager", "Senior Product Manager", "AI Product Manager", "Platform PM", "Technical Product Manager"
- Locations: "Remote", "Boston MA", "United States"
- Run each role × location = up to 15 queries

### 2. Call Apify LinkedIn Jobs Scraper
Actor ID: `curious_coder/linkedin-jobs-scraper`

```python
import requests, os, json
from datetime import datetime

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
ACTOR_ID = "curious_coder/linkedin-jobs-scraper"

def scrape_linkedin(role, location, max_results=50):
    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
    params = {"token": APIFY_TOKEN}
    payload = {
        "searchQueries": [{"query": role, "location": location}],
        "maxJobs": max_results,
        "proxy": {"useApifyProxy": True},
        "publishedAt": "past-week"
    }
    resp = requests.post(url, params=params, json=payload, timeout=120)
    return resp.json()
```

### 3. Extract & Normalize Fields
For each job, extract:
```json
{
  "id": "linkedin-<job_id>",
  "source": "linkedin",
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

### 4. Deduplicate
- Hash on (title + company + location)
- Skip if already in `data/jobs-raw/linkedin-YYYY-MM-DD.json`

### 5. Save Output
Write to `data/jobs-raw/linkedin-YYYY-MM-DD.json`
Log count: "LinkedIn: X new jobs scraped"

## Fallback
If Apify fails or quota exceeded:
- Use Playwright direct scrape: `https://www.linkedin.com/jobs/search/?keywords=<role>&location=<loc>&f_TPR=r604800`
- Extract job cards from `.job-search-card` elements
- Rate limit: 2 second delay between pages, max 3 pages per query

## Notes
- LinkedIn blocks aggressive scraping — use Apify proxy
- `publishedAt=past-week` = last 7 days only
- Skip jobs with "intern" or "internship" in title unless role is APM
- Free Apify tier: ~100 actor runs/month — use wisely
