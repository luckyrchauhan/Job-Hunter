# Job Hunter — Roadblocks & Pending Fixes

Track items that are broken, partial, or need debugging.

_Last updated: 2026-05-25_

---

## M2 — Search (Scrapers)

### ✅ FIXED in this session

| # | Source | Fix Applied | File |
|---|--------|-------------|------|
| 1 | **YC Jobs** | Rewritten — JSON API primary + Playwright fallback with fixed selectors + PM title filter | `scripts/scrapers/scrape_yc.py` |
| 2 | **Himalayas** | Already uses `?q=product+manager` + client-side `is_pm()` filter. Added `remoteOnly=true` param. | `scripts/scrapers/scrape_himalayas.py` |
| 4 | **Indeed** | Rewritten — Apify `valig/indeed-jobs-scraper` primary (company in `employer.name`), Playwright fallback | `scripts/scrapers/scrape_indeed.py` |
| 5 | **Indeed bot** | Apify-primary bypasses bot protection. Playwright fallback uses random delays 3–8s. | `scripts/scrapers/scrape_indeed.py` |
| 6 | **RemoteOK** | Tightened filter — `is_pm_title()` requires "product manager" variant in title (not loose tag match) | `scripts/scrapers/scrape_remoteok.py` |
| 7 | **LinkedIn** | ✅ Written — Apify actor `JkfTWxtpgfvcRQn3p` primary + fallback actor `hKByXkMQaC5Qt9UMN` | `scripts/scrapers/scrape_linkedin.py` |
| 8 | **Glassdoor** | ✅ Written — Apify `crawlector/glassdoor-jobs-scraper` + fallback actor | `scripts/scrapers/scrape_glassdoor.py` |
| 9 | **Wellfound** | ✅ Written — Apify primary + Playwright fallback | `scripts/scrapers/scrape_wellfound.py` |
| 10 | **Builtin** | ✅ Written — API primary + Playwright fallback | `scripts/scrapers/scrape_builtin.py` |
| 11 | **Company Direct** | ✅ Written — Playwright, 20 companies, runs Mondays only | `scripts/scrapers/scrape_company_direct.py` |
| 12 | **Niche Boards** | ✅ Written — Pallet API + ProductHunt Playwright | `scripts/scrapers/scrape_niche.py` |
| 15 | **Cross-source dedup** | ✅ Added — hash(title+company+location) in `load_all_raw_jobs()` | `scripts/score_jobs.py` |
| 3 | **LinkedIn timeout** | Apify `run-sync-get-dataset-items` with 180s timeout + fallback actor | `scripts/scrapers/scrape_linkedin.py` |

---

## M2 — Infrastructure

| # | Item | Status | Fix |
|---|------|--------|-----|
| 12 | ~~`daily-scan.sh` uses `python3` not venv~~ | ✅ FIXED | Now uses `$PROJECT_DIR/venv/bin/python` |
| 13 | ~~Cron not set up~~ | ✅ FIXED | 11pm daily digest cron installed |
| 14 | ~~`scripts/scrapers/` paths missing in daily-scan.sh~~ | ✅ FIXED | All paths correct, graceful skip if missing |
| 16 | ~~daily-scan.sh calls Telegram~~ | ✅ FIXED | Updated to use `notify_slack.py` |
| 20 | **8am daily scan cron not installed** | 🟡 Open | Install after `APIFY_API_TOKEN` set: `0 8 * * * /bin/bash .../daily-scan.sh >> .../logs/daily-scan.log 2>&1` |

---

## ✅ RESOLVED — M3/M4/M5/M6

| Milestone | Status |
|-----------|--------|
| M3 Score & Filter | ✅ COMPLETE — `score_jobs.py`, skill files done |
| M4 Notify | ✅ COMPLETE — `notify_slack.py` alert + digest modes |
| M5 Outreach & Apply | ✅ COMPLETE — all skill files + `outreach_apply.py` |
| M6 Track & Follow-up | ✅ COMPLETE — `log_application.py`, `export-tracker.py` (daily tabs) |

---

## Open — Cross-Cutting

| # | Item | Priority | Notes |
|---|------|----------|-------|
| 17 | `ANTHROPIC_API_KEY` not set | 🟡 Medium | Needed for Claude AI drafting in M5. Templates work without it. |
| 18 | `APIFY_API_TOKEN` not set | 🔴 High | Needed for LinkedIn/Indeed/Glassdoor/Wellfound scrapers |
| 19 | 8am daily scan cron not installed | 🟡 Medium | Set `APIFY_API_TOKEN` first, then: `crontab -e` → `0 8 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1` |

### What to test once APIFY_API_TOKEN is set

```bash
# Test one scraper at a time
cd ~/Documents/Projects/Antigravity/Job-Hunter
source venv/bin/activate

python scripts/scrapers/scrape_linkedin.py
python scripts/scrapers/scrape_indeed.py
python scripts/scrapers/scrape_glassdoor.py
python scripts/scrapers/scrape_wellfound.py

# Test non-Apify scrapers (work now)
python scripts/scrapers/scrape_remoteok.py
python scripts/scrapers/scrape_yc.py
python scripts/scrapers/scrape_himalayas.py
python scripts/scrapers/scrape_hiring_cafe.py
python scripts/scrapers/scrape_builtin.py
python scripts/scrapers/scrape_niche.py

# Full pipeline
bash scripts/daily-scan.sh
```
