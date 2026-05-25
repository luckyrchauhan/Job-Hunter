# Skill: cover-letter

## Purpose
Generate a targeted cover letter from tailored resume + job description.

## When to Use
After `tailor-resume` completes. Run before `submit-checklist`.

## Inputs
- `job` — job object from `jobs-scored.json`
- `tailored_resume_path` — from tailor-resume output
- `lead` — from `data/leads.json` (use hiring manager name if available)

## Structure (4 paragraphs, max 350 words)

### Para 1 — Hook + Role
```
Opening: Why this specific role at this specific company.
NOT: "I am writing to express my interest in..."
YES: Start with something specific about their product, team, or challenge.
Example: "Stripe's push into AI-powered financial infrastructure is exactly the space where I've been building..."
```

### Para 2 — Most Relevant Credential
```
Your single strongest proof point for THIS role.
One story: situation → action → measurable result.
Map to JD's biggest ask.
Example for AI PM role: "At GlobalLogic, I owned the LLM knowledge platform from 0→1 — defined hallucination rate targets (<5%), ran A/B tests that improved search success 40%, reached 78% adoption in Q1."
```

### Para 3 — Domain Fit + Second Proof Point
```
Show you understand their domain.
One more data point from background that addresses JD's secondary requirement.
Keep to 3-4 sentences.
```

### Para 4 — Close
```
"I'd welcome the chance to discuss how my [specific background] fits [Company]'s [specific goal/team/product]."
NO: "Thank you for your consideration" × 3 filler sentences.
YES: One sentence close, offer specific value.
```

## Tone Rules
- Confident, direct — not humble-braggy
- Specific over general always
- First-person but not "I, I, I" every sentence
- No clichés: "passionate", "team player", "quick learner", "highly motivated"

## Addressing
- If hiring manager found: "Dear [First Name],"
- If recruiter only: "Dear [First Name],"
- If no lead: "Dear Hiring Manager,"

## Output
- Save as `outputs/cover-letters/[company]-[role-slug]-[date].md`
- Return path for submit-checklist
