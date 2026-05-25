# Skill: Search Glassdoor Jobs

## Purpose
Scrape Glassdoor for PM jobs. Glassdoor valuable for salary data + company ratings.

## Inputs
- Read `config/search-params.json`
- Read `.env` for `APIFY_API_TOKEN`

## Steps

### 1. Call Apify Glassdoor Scraper
Actor ID: `bebity/glassdoor-jobs-scraper`

```python
ACTOR_ID = "bebity/glassdoor-jobs-scraper"

def scrape_glassdoor(role, location, max_results=30):
    payload = {
        "keyword": role,
        "locationName": location,
        "maxItems": max_results,
        "proxy": {"useApifyProxy": True}
    }
    # POST to Apify run endpoint
```

### 2. Normalize Fields
```json
{
  "id": "glassdoor-<job_listing_id>",
  "source": "glassdoor",
  "title": "",
  "company": "",
  "company_rating": null,
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

### 3. Bonus Data Points (Glassdoor-specific)
Capture if available:
- `company_rating` (out of 5)
- `ceo_approval` (%)
- `recommend_to_friend` (%)
- `salary_estimate` from Glassdoor model

### 4. Save Output
Write to `data/jobs-raw/glassdoor-YYYY-MM-DD.json`

## Notes
- Glassdoor aggressively blocks scraping — always use Apify proxy
- Max 30 results per query on free tier
- Company ratings are high-value signal for scoring later
