# Job Hunter — Roadblocks & Pending Fixes

Track items that are broken, partial, or need debugging. Fix before marking milestone fully complete.

---

## M2 — Search (Scrapers)

### 🔴 BROKEN — Needs Fix

| # | Source | Issue | File | Notes |
|---|--------|-------|------|-------|
| 1 | **YC Jobs** | 0 jobs returned — Playwright selector broken. Page loads but JS rendering not exposing job links correctly. | `scripts/scrapers/scrape_yc.py` | Try `waitForSelector` on job card class. Inspect live HTML via non-headless run. |
| 2 | **Himalayas** | API `title=` param doesn't filter by title — returns unrelated jobs (107k results, none PM) | `scripts/scrapers/scrape_himalayas.py` | Try `?q=product+manager` or paginate and filter client-side across all pages. May need Playwright fallback. |
| 3 | **LinkedIn** | Apify `run-sync` times out (3min+). Async run stays `RUNNING` beyond 20 polls (5min). | `scripts/scrapers/scrape_linkedin.py` (not yet written) | Actor `hKByXkMQaC5Qt9UMN` is slow. Try `JkfTWxtpgfvcRQn3p` (Rapid LinkedIn). Or increase poll wait to 30s × 30 iterations. |

### 🟡 PARTIAL — Works But Needs Improvement

| # | Source | Issue | File | Notes |
|---|--------|-------|------|-------|
| 4 | **Indeed** | Company name blank — selector `[data-testid="company-name"]` not matching current HTML. Titles correct. | `scripts/scrapers/scrape_indeed.py` | Indeed renders company via JS after load. Try `waitForSelector` + longer sleep. Or use Apify actor with correct field mapping. |
| 5 | **Indeed** | Bot protection blocks queries 2–5. Only first query (`product manager remote`) succeeds. 11 jobs total vs expected 50+. | `scripts/scrapers/scrape_indeed.py` | Add random delays 3–8s. Rotate user-agent. Or use Apify actor (confirmed working — just need correct input schema). |
| 6 | **RemoteOK** | Tag filter too loose — "product" tag catches Designer, SDR, Dev roles. 8 jobs returned but only ~2 actual PM. | `scripts/scrapers/scrape_remoteok.py` | Tighten filter: require "product manager" in title OR ("product" in tags AND "manager" in title). |
| 7 | **Apify Indeed actor** | `valig/indeed-jobs-scraper` works (100 results) but company field is in `employer.name` — confirmed. Title filter using `is_pm_title()` too strict — only 7/100 pass. | `scripts/scrapers/scrape_indeed.py` | The Apify version works better. Merge Apify + Playwright into one script with Apify as primary, Playwright as fallback. |

### 🟢 NOT YET WRITTEN — Scraper Scripts Missing

| # | Source | Skill File | Script Needed |
|---|--------|-----------|---------------|
| 8 | **LinkedIn** | `skills/search/linkedin.md` ✅ | `scripts/scrapers/scrape_linkedin.py` — not written |
| 9 | **Glassdoor** | `skills/search/glassdoor.md` ✅ | `scripts/scrapers/scrape_glassdoor.py` — not written |
| 10 | **Wellfound** | `skills/search/wellfound.md` ✅ | `scripts/scrapers/scrape_wellfound.py` — not written |
| 11 | **Builtin** | `skills/search/builtin.md` ✅ | `scripts/scrapers/scrape_builtin.py` — not written |
| 12 | **Company Direct** | `skills/search/company-direct.md` ✅ | `scripts/scrapers/scrape_company_direct.py` — not written |

---

## M2 — Infrastructure

| # | Item | Issue | Fix Needed |
|---|------|-------|-----------|
| 13 | **venv not activated in daily-scan.sh** | `daily-scan.sh` calls `python3` directly — won't use venv | Add `source $PROJECT_DIR/venv/bin/activate` before any python calls |
| 14 | **Cron not set up** | No cron entry created yet | After M4 (Telegram) works, run: `crontab -e` and add `0 8 * * * /bin/bash /path/to/daily-scan.sh` |
| 15 | **`scripts/scrapers/` not in daily-scan.sh** | `daily-scan.sh` calls `scripts/scrapers/scrape_linkedin.py` etc but path wasn't `scrapers/` subfolder originally | Update all paths in `daily-scan.sh` to `scripts/scrapers/scrape_*.py` |
| 16 | **No deduplication across sources** | Same job can appear in Indeed + LinkedIn + Glassdoor | Need global dedup in `score_jobs.py` — hash on (title + company + normalized_location) |

---

## M3 — Score & Filter (Not Started)

| # | Item | Status |
|---|------|--------|
| 17 | `scripts/score_jobs.py` | Not written |
| 18 | `skills/score/fit-score.md` | Empty placeholder |
| 19 | `skills/score/visa-check.md` | Empty placeholder |
| 20 | `skills/score/urgency-flag.md` | Empty placeholder |
| 21 | `ANTHROPIC_API_KEY` in `.env` | Not set — needed for scoring |

---

## M4 — Notify (Not Started)

| # | Item | Status |
|---|------|--------|
| 22 | Telegram bot creation | Not done — need to message @BotFather |
| 23 | `TELEGRAM_BOT_TOKEN` in `.env` | Empty |
| 24 | `TELEGRAM_CHAT_ID` in `.env` | Empty |
| 25 | `scripts/notify_telegram.py` | Not written |

---

## M5 — Outreach & Apply (Not Started)

| # | Item | Status |
|---|------|--------|
| 26 | All `skills/connect/*.md` | Empty placeholders |
| 27 | All `skills/apply/*.md` | Empty placeholders |

---

## M6 — Track (Not Started)

| # | Item | Status |
|---|------|--------|
| 28 | `scripts/export-tracker.py` | Empty placeholder |
| 29 | `skills/track/*.md` | Empty placeholders |

---

## How to Use This File

- Fix items top-to-bottom within each milestone before marking milestone ✅ COMPLETE
- When fixed: strike through the row or delete it
- When new blocker found: add row with date discovered
- Check this file at the start of each session

_Last updated: 2026-05-25_
