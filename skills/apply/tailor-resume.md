# Skill: tailor-resume

## Purpose
Rewrite `data/my-resume.md` to match a specific job description — surface right keywords, reorder bullets, sharpen relevance. Save tailored version to `outputs/resumes/`.

## When to Use
Job score >= 6, visa passed, ready to apply.

## Inputs
- `job` — job object from `jobs-scored.json` (needs `description` field)
- `my_resume` — `data/my-resume.md` (source of truth, NEVER modify this)
- `score_breakdown` — from scored job (tells which signals matched)

## Process

### Step 1 — Extract JD signals
From job description, identify:
- **Must-have keywords** — role-specific terms the ATS will scan (e.g., "roadmap", "stakeholder", "agile", "B2B", "platform")
- **Domain signals** — industry focus (AI/ML, fintech, enterprise, supply chain, etc.)
- **Seniority signals** — "lead", "own", "drive", "partner with engineering" etc.
- **Differentiators** — what makes this JD unique vs generic PM role

### Step 2 — Map to my experience
For each must-have keyword/signal:
- Find the best matching bullet from my resume
- If keyword missing: find where it's implied and make it explicit (don't fabricate)

### Step 3 — Rewrite summary
Rewrite the Summary section to:
- Open with the specific domain/context of this role
- Name the most relevant credential (AI, enterprise platform, supply chain, etc.)
- 3-4 sentences max

### Step 4 — Reorder experience bullets
For the 2 most relevant roles:
- Move strongest matching bullets to top
- Remove weak-signal bullets if > 5 bullets in a role
- Keep all facts accurate — no invented metrics

### Step 5 — Keyword pass
Final scan: ensure these appear naturally if in JD:
- Product-led growth, roadmap, KPIs, OKRs, cross-functional, stakeholders, agile/scrum
- Domain-specific: AI/ML, LLM, enterprise, platform, SaaS, API, data, analytics

## Output
- Save as `outputs/resumes/[company]-[role-slug]-[date].md`
- Format: same markdown structure as `data/my-resume.md`
- Return path for use in submit-checklist

## Rules
- NEVER modify `data/my-resume.md`
- NEVER invent metrics or credentials
- If JD asks for skill I don't have: don't add it — just don't highlight its absence
- Keep total resume under 2 pages when rendered
