# Job Hunter — Roadblocks & Pending Fixes

_Last updated: 2026-05-25_

---

## ✅ ALL CODE COMPLETE — No open blockers

All milestones M1–M6 are code-complete. Remaining items are **config-only** — no code needed.

---

## Open Config Items

| # | Item | Priority | Action |
|---|------|----------|--------|
| 1 | `APIFY_API_TOKEN` not set | 🔴 High | Add to `.env`. Enables LinkedIn, Indeed (Apify), Glassdoor, Wellfound scrapers. Get token: https://console.apify.com/account/integrations |
| 2 | `ANTHROPIC_API_KEY` not set | 🟡 Medium | Add to `.env`. Enables AI resume/cover letter drafting in M5. Templates work without it. |
| 3 | 8am daily scan cron not installed | 🟡 Medium | Run: `crontab -e` and add: `0 8 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1` |

---

## How to Test Once APIFY_API_TOKEN is Set

```bash
cd ~/Documents/Projects/Antigravity/Job-Hunter
source venv/bin/activate

# Test Apify scrapers
python scripts/scrapers/scrape_linkedin.py
python scripts/scrapers/scrape_indeed.py
python scripts/scrapers/scrape_glassdoor.py
python scripts/scrapers/scrape_wellfound.py

# Test non-Apify scrapers (work now, no token needed)
python scripts/scrapers/scrape_remoteok.py
python scripts/scrapers/scrape_yc.py
python scripts/scrapers/scrape_himalayas.py
python scripts/scrapers/scrape_hiring_cafe.py
python scripts/scrapers/scrape_builtin.py
python scripts/scrapers/scrape_niche.py

# Full pipeline
bash scripts/daily-scan.sh
```

---

## ✅ Resolved — M2 Scraper Fixes (2026-05-25)

| # | Source | Fix |
|---|--------|-----|
| 1 | YC Jobs | JSON API primary + Playwright fallback with working selectors + PM title filter |
| 2 | Himalayas | Added `remoteOnly=true`; `q=product+manager` was already correct |
| 3 | LinkedIn | Written — Apify `JkfTWxtpgfvcRQn3p` + fallback actor |
| 4 | Indeed blank company | Apify `valig/indeed-jobs-scraper` — company from `employer.name` |
| 5 | Indeed bot protection | Apify-primary bypasses scraping blocks |
| 6 | RemoteOK loose filter | `is_pm_title()` — title must contain PM variant, not just tags |
| 7 | Glassdoor | Written — Apify `crawlector/glassdoor-jobs-scraper` + fallback |
| 8 | Wellfound | Written — Apify + Playwright fallback |
| 9 | Builtin | Written — API primary + Playwright fallback |
| 10 | Company Direct | Written — Playwright, 20 H1B sponsor companies, Mondays only |
| 11 | Niche Boards | Written — Pallet board API + ProductHunt Playwright |
| 12 | Cross-source dedup | `score_jobs.py` — `hash(title+company+location)` removes duplicates across boards |

## ✅ Resolved — Infrastructure

| # | Fix |
|---|-----|
| daily-scan.sh venv path | Uses `$PROJECT_DIR/venv/bin/python` |
| Cron 11pm digest | Installed |
| Slack integration | Uses `notify_slack.py` (not Telegram) |
| All scraper paths in daily-scan.sh | Correct + graceful skip if missing |

## ✅ Resolved — M3/M4/M5/M6

| Milestone | Commit |
|-----------|--------|
| M3 Score & Filter | `score_jobs.py` + skill files |
| M4 Notify | `notify_slack.py` alert + digest |
| M5 Outreach & Apply | `outreach_apply.py` + all skill files |
| M6 Track & Follow-up | `log_application.py` + `export-tracker.py` (daily Excel tabs) |
