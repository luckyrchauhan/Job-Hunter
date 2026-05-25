# Job Hunter

Automated PM job search — scrapes 13 sources, scores listings, fires Slack alerts, syncs Google Sheets.

## Setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # fill in tokens
```

## .env Keys

| Key | Required for |
|-----|-------------|
| `APIFY_API_TOKEN` | LinkedIn, Indeed, Glassdoor, Wellfound |
| `SLACK_WEBHOOK_URL` | Alerts |
| `GOOGLE_SHEET_ID` + `GOOGLE_SERVICE_ACCOUNT_JSON` | Sheets sync |
| `ANTHROPIC_API_KEY` | AI resume/cover letter drafting |

## Run

```bash
bash scripts/daily-scan.sh      # full scan
python scripts/watcher.py       # one-off hot-job check
```

## Cron

```
0 8,12,15 * * *  /bin/bash /path/to/scripts/daily-scan.sh >> logs/daily-scan.log 2>&1
*/15 8-20 * * *  /path/to/venv/bin/python /path/to/scripts/watcher.py >> logs/watcher.log 2>&1
```

## Rules

- Never auto-apply — Lucky submits manually
- Never commit `.env` or service account JSON
- Always gate on H1B sponsorship
