# Skill: urgency-flag — Application Deadline Urgency

## Purpose
Flag how urgently Lucky should apply based on posting age, competition signals, and job type.

## Urgency Tiers

| Tier | Label | Trigger | Telegram Alert? |
|------|-------|---------|-----------------|
| 1 | 🔴 APPLY NOW | Posted <6h AND score ≥8 | YES — immediate |
| 2 | 🔴 APPLY NOW | Posted <24h AND score ≥8 | YES — immediate |
| 3 | 🟠 <5 HOURS | Deadline in <5h or posted today + closing soon signal | YES |
| 4 | 🟠 <15 HOURS | Posted today, score ≥6 | YES |
| 5 | 🟡 THIS WEEK | Posted 1–3 days ago, score ≥6 | NO — daily digest |
| 6 | 🟡 THIS WEEK | Posted 4–7 days ago, score ≥4 | NO — daily digest |
| 7 | ⚪ LOW PRIORITY | Posted >7 days ago | NO |
| 8 | ⛔ EXPIRED | Posted >14 days ago | NO — discard |

## Telegram Alert Threshold
Alert tiers 1–4 (urgency_tier ≤ 4) immediately.
Tiers 5–6: batch in daily 8am digest.
Tier 7–8: no alert.

## 50-Application Gate
If `applications_this_week >= 50`: pause tier 5–6 alerts. Only send tier 1–4.
Track count in `data/applications.json`.

## Closing Soon Signals (boost urgency +1 tier)
Scan description for:
- "apply by [date]"
- "position closes [date]"
- "rolling basis"
- "until filled"

## Output Fields
```json
{
  "urgency_tier": 2,
  "urgency_label": "APPLY NOW",
  "hours_since_posted": 4.5,
  "closing_signal": "rolling basis",
  "alert_now": true
}
```
