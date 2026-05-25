# Skill: log-application

## Purpose
Write submitted application to `data/applications.json` and trigger `export-tracker.py`
to regenerate `outputs/tracker.xlsx`.

## When to Use
Immediately after Lucky confirms "I submitted this application."

## Inputs
- `job` — job object from `jobs-scored.json`
- `applied_date` — ISO date string (default: today)
- `outreach_contact` — name from `data/leads.json` (recruiter or HM)
- `outreach_sent` — bool: did Lucky send the outreach message?
- `notes` — optional free-text

## Application Record Schema
```json
{
  "id": "stripe-senior-pm-2026-05-25",
  "company": "Stripe",
  "role": "Senior PM — Payments",
  "apply_url": "https://stripe.com/jobs/...",
  "score": 9,
  "urgency": "apply-now",
  "visa": "confirmed",
  "salary_text": "$180k–$220k",
  "status": "applied",
  "applied_date": "2026-05-25",
  "outreach_contact": "Jane Doe (Recruiter)",
  "outreach_sent": true,
  "follow_up_due": "2026-06-01",
  "resume_path": "outputs/resumes/stripe-senior-pm-2026-05-25.md",
  "cover_letter_path": "outputs/cover-letters/stripe-senior-pm-2026-05-25.md",
  "outreach_path": "outputs/outreach/stripe-senior-pm-referral-2026-05-25.md",
  "notes": "",
  "outcome": null,
  "outcome_date": null,
  "logged_at": "2026-05-25T10:30:00Z"
}
```

## Status Values
| Status | Meaning |
|--------|---------|
| `ready_to_apply` | Materials ready, not yet submitted |
| `applied` | Submitted by Lucky |
| `outreach_sent` | Outreach sent, not yet applied |
| `interviewing` | Active interview process |
| `offer` | Offer received |
| `rejected` | Rejected / no response after follow-up |
| `withdrawn` | Lucky withdrew |
| `stale` | No response, follow-up exhausted |

## Follow-up Date Rule
`follow_up_due` = `applied_date` + 7 days

## Process
1. Load `data/applications.json` (create if missing)
2. Check if `id` already exists — update if so, append if not
3. Set `status: "applied"`, `applied_date`, `follow_up_due`
4. Save `data/applications.json`
5. Run `python scripts/export-tracker.py` to regenerate Excel
6. Print confirmation: "✅ Logged: [Company] — [Role] | Follow-up due: [date]"

## Notes
- NEVER auto-submit — Lucky submits, then calls this skill
- `id` = `slug(company) + "-" + slug(role) + "-" + applied_date`
- Duplicate IDs: update existing record, don't create duplicate
