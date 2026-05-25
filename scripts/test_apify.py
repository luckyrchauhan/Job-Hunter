"""Quick test: verify Apify token works + scrape 5 LinkedIn PM jobs."""
import os, json, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("APIFY_API_TOKEN")
if not TOKEN:
    print("ERROR: APIFY_API_TOKEN not set in .env"); exit(1)

print(f"Token found: {TOKEN[:8]}...")

# Test with LinkedIn Jobs Scraper — minimal run (5 jobs)
ACTOR_ID = "curious_coder/linkedin-jobs-scraper"
url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"

payload = {
    "searchQueries": [{"query": "Product Manager", "location": "Remote"}],
    "maxJobs": 5,
    "proxy": {"useApifyProxy": True},
    "publishedAt": "past-week"
}

print(f"\nCalling Apify actor: {ACTOR_ID}")
print("Running... (may take 30-60s)")

try:
    resp = requests.post(url, params={"token": TOKEN}, json=payload, timeout=120)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        jobs = resp.json()
        print(f"\n✅ SUCCESS — Got {len(jobs)} jobs\n")
        for j in jobs[:3]:
            print(f"  • {j.get('title','?')} @ {j.get('companyName','?')} — {j.get('location','?')}")
        
        # Save to data/jobs-raw/
        os.makedirs("data/jobs-raw", exist_ok=True)
        date = datetime.now().strftime("%Y-%m-%d")
        out = f"data/jobs-raw/linkedin-test-{date}.json"
        with open(out, "w") as f:
            json.dump(jobs, f, indent=2)
        print(f"\nSaved to {out}")
    else:
        print(f"❌ FAILED: {resp.status_code}")
        print(resp.text[:500])
except Exception as e:
    print(f"❌ ERROR: {e}")
