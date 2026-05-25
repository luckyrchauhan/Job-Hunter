# Skill: followup

## Purpose
Draft follow-up messages by timeline and update application status in `data/applications.json`.

## When to Use
`deadline-check.py` flags application with `follow_up_due <= today`.
Or Lucky asks "what needs follow-up?"

## Follow-up Timeline

| Trigger | Action | Template |
|---------|--------|----------|
| 7 days after apply | First follow-up to recruiter | Polite check-in, reaffirm interest |
| 14 days after apply (no response) | Second follow-up | Brief, mention timeline if have one |
| 21 days after apply (no response) | Close-out note | "I'll assume the role is filled — leave door open" |
| Interview scheduled | Pre-interview prep note | Thank you + confirm logistics |
| Post-interview (24–48h) | Thank-you note | Personalized to what was discussed |

## Message Templates

### 7-day Follow-up
```
Subject: Re: [Role Title] — [Your Name]

Hi [First Name],

I wanted to follow up on my application for the [Role Title] position submitted on [date].

I'm still very interested in the opportunity and would welcome a chance to connect.
Happy to share any additional materials if helpful.

Thanks,
Lucky Chauhan
lucky.raajc@gmail.com
```

### 14-day Follow-up (no response)
```
Subject: Following up — [Role Title] at [Company]

Hi [First Name],

Just a brief follow-up on my [Role Title] application. I remain interested and
wanted to check if there's any update on the timeline.

Thanks for your time,
Lucky Chauhan
```

### 21-day Close-out
```
Subject: [Role Title] — Closing the Loop

Hi [First Name],

I'll assume the [Role Title] role has moved forward with other candidates.
I genuinely admire [something specific about company] and would welcome
the chance to connect in the future if the right opportunity comes up.

Thanks,
Lucky Chauhan
lucky.raajc@gmail.com | linkedin.com/in/luckychauhan
```

### Post-Interview Thank You (within 48h)
```
Subject: Thank you — [Role Title] Interview

Hi [First Name],

Thank you for the time today. [One specific thing discussed — a challenge,
a product decision, or something that excited you].

This reinforced my interest in [Company]. Looking forward to next steps.

Lucky Chauhan
```

## Process
1. Load `data/applications.json`
2. Find apps where `follow_up_due <= today` and `status == "applied"`
3. For each: select template by days since apply
4. Draft message, save to `outputs/outreach/[company]-followup-[date].md`
5. Present to Lucky for review — NEVER send automatically
6. After Lucky confirms sent: update `status`, set next `follow_up_due` or mark `stale`

## Status Updates After Follow-up
- 7-day sent → keep `status: applied`, set `follow_up_due` = +7 days
- 14-day sent → keep `status: applied`, set `follow_up_due` = +7 days
- 21-day sent → update `status: stale`
- Post-interview sent → keep `status: interviewing`

## Slack Reminder Format
```
🔔 FOLLOW-UP DUE
Company: Stripe | Role: Senior PM
Applied: 7 days ago | Status: applied
Draft ready: outputs/outreach/stripe-followup-2026-06-01.md
```
