# Skill: Search Indeed Jobs

## Purpose
Scrape Indeed job postings for PM roles. Indeed is highest volume source — expect 50–150 jobs/day.

## Inputs
- Read `config/search-params.json`
- Read `.env` for `APIFY_API_TOKEN`

## Steps

### 1. Build Search Queries
Roles × Locations matrix:
- Roles: "product manager", "senior product manager", "ai product manager", "platform product manager"
- Locations: "remote", "Boston MA", "New York NY", "San Francisco CA", "Seattle WA"

### 2. Call Apify Indeed Scraper
Actor ID: `misceres/indeed-scraper`

```python
import requests, os, json
from datetime import datetime

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
ACTOR_ID = "misceres/indeed-scraper"

def scrape_indeed(role, location, max_results=50):
    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
    params = {"token": APIFY_TOKEN}
    payload = {
        "position": role,
        "country": "US",
        "location": location,
        "maxItems": max_results,
        "parseCompanyDetails": True,
        "saveOnlyUniqueItems": True,
        "followApplyRedirects": True
    }
    resp = requests.post(url, params=params, json=payload, timeout=120)
    return resp.json()
```

### 3. Extract & Normalize Fields
```json
{
  "id": "indeed-<job_key>",
  "source": "indeed",
  "title": "",
  "company": "",
  "location": "",
  "remote": true/false,
  "salary_min": null,
  "salary_max": null,
  "salary_type": "year/hour",
  "posted_date": "",
  "apply_url": "https://www.indeed.com/viewjob?jk=<job_key>",
  "description": "",
  "company_rating": null,
  "scraped_at": "ISO timestamp"
}
```

### 4. Filter Before Saving
Skip if:
- Title contains: "intern", "director", "VP", "head of", "chief" (too senior)
- Posted > 7 days ago
- Location not in USA (unless remote)

### 5. Save Output
Write to `data/jobs-raw/indeed-YYYY-MM-DD.json`
Log count: "Indeed: X new jobs scraped"

## Fallback (Direct Scrape)
If Apify unavailable:
```
URL: https://www.indeed.com/jobs?q=<role>&l=<location>&fromage=7&sort=date
Selector: .job_seen_beacon
Rate limit: 3s between requests, rotate user-agent
```

## Notes
- Indeed has good salary data — capture when available
- `fromage=7` = last 7 days
- Many Indeed jobs are aggregated from other boards — check for duplicates across sources
