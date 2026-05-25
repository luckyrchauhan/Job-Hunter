#!/usr/bin/env python3
"""
M5 — Outreach & Apply Pipeline
Reads:  data/jobs-scored.json
Writes: data/leads.json, outputs/resumes/, outputs/cover-letters/, outputs/outreach/
        data/jobs-scored.json (updates status → ready_to_apply)

Pipeline per job:
  1. find_leads()       — recruiter + HM via LinkedIn search
  2. draft_outreach()   — referral-ask (warmth>=2) or cold-outreach
  3. tailor_resume()    — Claude rewrites resume for JD keywords
  4. generate_cover()   — Claude generates cover letter
  5. submit_checklist() — QA gate, marks ready_to_apply

Usage:
  python scripts/outreach_apply.py                    # all eligible jobs
  python scripts/outreach_apply.py --job-id <id>      # single job
  python scripts/outreach_apply.py --top N            # top N by score
  python scripts/outreach_apply.py --dry-run          # preview, no writes
"""

import json
import os
import re
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
SCORED_FILE  = BASE_DIR / "data" / "jobs-scored.json"
LEADS_FILE   = BASE_DIR / "data" / "leads.json"
RESUME_FILE  = BASE_DIR / "data" / "my-resume.md"
BLOCKLIST    = BASE_DIR / "config" / "blocklist.json"

OUT_RESUMES  = BASE_DIR / "outputs" / "resumes"
OUT_COVERS   = BASE_DIR / "outputs" / "cover-letters"
OUT_OUTREACH = BASE_DIR / "outputs" / "outreach"

for d in [OUT_RESUMES, OUT_COVERS, OUT_OUTREACH]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Env / API ────────────────────────────────────────────────────────────────

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ─── Helpers ──────────────────────────────────────────────────────────────────

def slug(text: str) -> str:
    """Convert text to URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def load_json(path: Path, default):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  → saved {path.relative_to(BASE_DIR)}")


def load_blocklist() -> set:
    data = load_json(BLOCKLIST, {})
    companies = set()
    for v in data.values():
        if isinstance(v, list):
            companies.update(c.lower() for c in v)
        elif isinstance(v, dict) and "companies" in v:
            companies.update(c.lower() for c in v["companies"])
    return companies


# ─── Step 1: Find Leads ───────────────────────────────────────────────────────

# Alumni / warm-connection hooks — used for warmth scoring
WARM_HOOKS = {
    "boston university": 3, "bu questrom": 3, "questrom": 3,
    "globallogic": 3, "gyansys": 3, "anglo-eastern": 3, "katbotz": 3,
    "avantor": 3, "hitachi": 2,
    "supply chain": 2, "sap": 2, "s/4hana": 2,
    "llm": 2, "ai": 2, "product manager": 1,
}

def find_leads(job: dict, leads_db: dict, dry_run: bool = False) -> dict:
    """
    Find recruiter + hiring manager for a job.
    Real implementation: web search via Claude tool use or manual lookup.
    Returns lead dict (may have placeholders if not found).
    """
    company = job.get("company", "").strip()
    company_key = company.lower()

    # Return existing if already found
    if company_key in leads_db:
        existing = leads_db[company_key]
        if existing.get("recruiter") or existing.get("hiring_manager"):
            print(f"  ↩ Leads already cached for {company}")
            return existing

    lead = {
        "company": company,
        "job_id": job["id"],
        "role_title": job.get("title", ""),
        "recruiter": None,
        "hiring_manager": None,
        "leads_not_found": True,
        "found_at": datetime.now(timezone.utc).isoformat(),
        "search_queries": [
            f'"{company}" recruiter "product manager" site:linkedin.com',
            f'"{company}" "product manager" director OR VP site:linkedin.com',
        ]
    }

    # In dry-run: show queries, don't execute
    if dry_run:
        print(f"  [dry-run] Would search LinkedIn for leads at {company}")
        print(f"    Query 1: {lead['search_queries'][0]}")
        print(f"    Query 2: {lead['search_queries'][1]}")
        return lead

    # NOTE: Real lead finding requires Claude tool use with web search.
    # Run this script via Claude Code for live lead discovery.
    # For now: create placeholder record with search queries for manual lookup.
    print(f"  ⚠ Lead finding requires Claude web search — queries saved to leads.json")
    print(f"    Manual LinkedIn search: {lead['search_queries'][0]}")

    if not dry_run:
        leads_db[company_key] = lead
        save_json(LEADS_FILE, leads_db)

    return lead


# ─── Step 2: Draft Outreach ───────────────────────────────────────────────────

def draft_outreach(job: dict, lead: dict, dry_run: bool = False) -> Path | None:
    """
    Draft referral-ask (warmth>=2) or cold-outreach.
    Uses Claude API if available, else writes template with placeholders.
    """
    company = job.get("company", "Unknown")
    title   = job.get("title", "Product Manager")
    role_slug = slug(f"{company}-{title}")
    outreach_path = OUT_OUTREACH / f"{role_slug}-{TODAY}.md"

    # Check warmth
    recruiter = lead.get("recruiter") or {}
    hm = lead.get("hiring_manager") or {}
    warmth = max(recruiter.get("warmth", 1), hm.get("warmth", 1))
    contact = (recruiter or hm) or {}
    contact_name = contact.get("name", "Hiring Team")
    first_name = contact_name.split()[0] if contact_name != "Hiring Team" else "Hiring Team"
    outreach_type = "referral" if warmth >= 2 else "cold"

    if dry_run:
        print(f"  [dry-run] Would draft {outreach_type} outreach → {outreach_path.name}")
        return outreach_path

    # If Claude API available: use it for personalization
    if ANTHROPIC_KEY:
        content = _claude_draft_outreach(job, lead, outreach_type, first_name)
    else:
        content = _template_outreach(job, lead, outreach_type, first_name, warmth)

    outreach_path.write_text(content)
    print(f"  ✅ Outreach drafted ({outreach_type}) → {outreach_path.relative_to(BASE_DIR)}")
    return outreach_path


def _template_outreach(job, lead, outreach_type, first_name, warmth) -> str:
    company = job.get("company", "the company")
    title   = job.get("title", "Product Manager")
    score   = job.get("score", 0)

    if outreach_type == "referral":
        hook = "[Add shared connection / alumni hook here]"
        body = (
            f"I came across the {title} role at {company} and it's a strong match — "
            "[add 1-2 specifics from JD matching your background].\n\n"
            "Quick background: I'm a PM with 11 years of experience, most recently "
            "building [most relevant recent project — e.g., LLM knowledge platform at GlobalLogic / "
            "$20M enterprise platform at Katbotz].\n\n"
            "Would you be open to a 15-minute chat, or pointing me to the right person on the team?"
        )
    else:
        hook = f"I'm applying for the {title} position and wanted to reach out directly."
        body = (
            "I'm a PM with 11 years of experience — most relevant here: "
            "[add 1 specific credential matching JD, e.g., enterprise platform at scale / AI product from 0→1].\n\n"
            f"{company} is specifically on my list because [add 1 genuine reason — product direction, mission, or team].\n\n"
            "I'd appreciate a 15-minute conversation if you have time, or any guidance on the process."
        )

    return f"""# Outreach Draft — {company} / {title}
**Type:** {outreach_type}
**To:** {first_name}
**Job Score:** {score}/10
**Date:** {TODAY}

---

Hi {first_name},

{hook}

{body}

Thanks,
Your Name
your.email@example.com | linkedin.com/in/your-profile

---
<!-- Generated by M5 outreach_apply.py — review before sending -->
<!-- skill: skills/connect/{outreach_type.replace("-", "_")}.md -->
"""


def _claude_draft_outreach(job, lead, outreach_type, first_name) -> str:
    """Draft outreach via Claude API."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

        resume = RESUME_FILE.read_text() if RESUME_FILE.exists() else ""
        jd = job.get("description", "No description available")
        company = job.get("company", "the company")
        title = job.get("title", "Product Manager")

        skill_name = "referral-ask" if outreach_type == "referral" else "cold-outreach"
        skill_path = BASE_DIR / "skills" / "connect" / f"{skill_name}.md"
        skill_content = skill_path.read_text() if skill_path.exists() else ""

        prompt = f"""You are drafting a {outreach_type} LinkedIn/email outreach message for Your Name.

SKILL INSTRUCTIONS:
{skill_content}

LUCKY'S RESUME SUMMARY:
{resume[:2000]}

JOB DESCRIPTION:
{jd[:1500]}

CONTACT: {first_name} at {company} (role: {title})

Draft the outreach message following the skill instructions exactly. Max 150 words. Be specific."""

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        drafted = msg.content[0].text
        return f"""# Outreach Draft — {company} / {title}
**Type:** {outreach_type} (Claude-generated)
**To:** {first_name}
**Date:** {TODAY}

---

{drafted}

---
<!-- Generated via Claude claude-sonnet-4-6 — review before sending -->
"""
    except Exception as e:
        print(f"  ⚠ Claude API error: {e} — falling back to template")
        return _template_outreach(job, lead, outreach_type, first_name, 1)


# ─── Step 3: Tailor Resume ────────────────────────────────────────────────────

def tailor_resume(job: dict, dry_run: bool = False) -> Path | None:
    """Tailor resume to job description. Uses Claude if API key set."""
    company   = job.get("company", "Unknown")
    title     = job.get("title", "PM")
    role_slug = slug(f"{company}-{title}")
    out_path  = OUT_RESUMES / f"{role_slug}-{TODAY}.md"

    if dry_run:
        print(f"  [dry-run] Would tailor resume → {out_path.name}")
        return out_path

    if not RESUME_FILE.exists():
        print("  ✗ data/my-resume.md not found — skipping tailor")
        return None

    if ANTHROPIC_KEY:
        content = _claude_tailor_resume(job)
    else:
        # Copy base resume with header noting tailoring needed
        base = RESUME_FILE.read_text()
        content = f"""# Tailored Resume — {company} / {title}
<!-- TODO: Tailor manually or set ANTHROPIC_API_KEY for auto-tailoring -->
<!-- JD Keywords to surface: extract from job description and highlight matching experience -->
<!-- Posted: {job.get('posted_date', 'unknown')} | Score: {job.get('score', 0)}/10 -->

{base}"""

    out_path.write_text(content)
    print(f"  ✅ Resume saved → {out_path.relative_to(BASE_DIR)}")
    return out_path


def _claude_tailor_resume(job: dict) -> str:
    """Use Claude to tailor resume for specific JD."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

        skill_path = BASE_DIR / "skills" / "apply" / "tailor-resume.md"
        skill = skill_path.read_text() if skill_path.exists() else ""
        resume = RESUME_FILE.read_text()
        jd = job.get("description", "")
        company = job.get("company", "")
        title = job.get("title", "")

        prompt = f"""You are tailoring Your Name's resume for a specific job.

SKILL INSTRUCTIONS:
{skill}

ORIGINAL RESUME:
{resume}

JOB DESCRIPTION:
{jd[:2000]}

SCORE BREAKDOWN (what signals matched):
{json.dumps(job.get('score_breakdown', {}), indent=2)}

Rewrite the resume following the skill instructions. Keep same markdown structure. Never invent metrics. Never modify certifications or education. Output the full tailored resume."""

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        print(f"  ⚠ Claude API error for resume: {e} — using base resume")
        return RESUME_FILE.read_text()


# ─── Step 4: Generate Cover Letter ───────────────────────────────────────────

def generate_cover(job: dict, lead: dict, resume_path: Path | None, dry_run: bool = False) -> Path | None:
    """Generate cover letter via Claude or template."""
    company   = job.get("company", "Unknown")
    title     = job.get("title", "PM")
    role_slug = slug(f"{company}-{title}")
    out_path  = OUT_COVERS / f"{role_slug}-{TODAY}.md"

    if dry_run:
        print(f"  [dry-run] Would generate cover letter → {out_path.name}")
        return out_path

    contact = lead.get("hiring_manager") or lead.get("recruiter") or {}
    contact_name = contact.get("name", "Hiring Manager")
    first_name = contact_name.split()[0]

    if ANTHROPIC_KEY:
        content = _claude_cover_letter(job, lead, first_name, resume_path)
    else:
        content = _template_cover(job, first_name, company, title)

    out_path.write_text(content)
    print(f"  ✅ Cover letter saved → {out_path.relative_to(BASE_DIR)}")
    return out_path


def _template_cover(job, first_name, company, title) -> str:
    score = job.get("score", 0)
    return f"""# Cover Letter — {company} / {title}
<!-- TODO: Personalize or set ANTHROPIC_API_KEY for auto-generation -->
**Date:** {TODAY}

---

Dear {first_name},

[Para 1 — Hook: Something specific about {company}'s product/mission and why this {title} role fits]

[Para 2 — Strongest credential matching the JD: one story, situation → action → measurable result]

[Para 3 — Domain fit + second proof point from your background]

I'd welcome the chance to discuss how my background fits {company}'s team.

Thanks,
Your Name
your.email@example.com | linkedin.com/in/your-profile

---
<!-- Job score: {score}/10 | Generated by M5 — review before sending -->
"""


def _claude_cover_letter(job, lead, first_name, resume_path) -> str:
    """Use Claude to generate cover letter."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

        skill_path = BASE_DIR / "skills" / "apply" / "cover-letter.md"
        skill = skill_path.read_text() if skill_path.exists() else ""

        resume_text = ""
        if resume_path and Path(resume_path).exists():
            resume_text = Path(resume_path).read_text()[:2000]
        elif RESUME_FILE.exists():
            resume_text = RESUME_FILE.read_text()[:2000]

        jd = job.get("description", "")
        company = job.get("company", "")
        title = job.get("title", "")

        prompt = f"""Write a cover letter for Your Name applying to {company} for {title}.

SKILL INSTRUCTIONS:
{skill}

TAILORED RESUME:
{resume_text}

JOB DESCRIPTION:
{jd[:1500]}

ADDRESSING: Dear {first_name},

Follow the skill instructions exactly. Max 350 words. Specific over generic. No clichés."""

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        cover = msg.content[0].text
        return f"""# Cover Letter — {company} / {title}
**Generated:** {TODAY} (Claude claude-sonnet-4-6)

---

{cover}

---
<!-- Review before submitting -->
"""
    except Exception as e:
        print(f"  ⚠ Claude API error for cover letter: {e} — using template")
        return _template_cover(job, first_name, job.get("company",""), job.get("title",""))


# ─── Step 5: Submit Checklist ─────────────────────────────────────────────────

def submit_checklist(
    job: dict,
    lead: dict,
    resume_path: Path | None,
    cover_path: Path | None,
    outreach_path: Path | None,
    blocklist: set,
    dry_run: bool = False
) -> bool:
    """Run QA gate. Returns True if ready to apply."""
    company = job.get("company", "Unknown")
    title   = job.get("title", "PM")
    score   = job.get("score", 0)
    visa    = job.get("visa_status", "unknown")
    days_old = job.get("days_since_posted", 0)
    apply_url = job.get("apply_url", "")
    salary_min = job.get("salary_min")

    hard_pass = True
    warns = []
    checks = []

    def check(label, ok, value, hard=True):
        nonlocal hard_pass
        icon = "✅" if ok else ("❌" if hard else "⚠")
        checks.append(f"  {icon} {label:<22} {value}")
        if not ok and hard:
            hard_pass = False

    check("Score",          score >= 6,         f"{score}/10")
    check("Visa",           visa != "no-sponsorship", visa)
    check("Not blocklisted",company.lower() not in blocklist, company)
    check("Not stale",      days_old <= 7,       f"{days_old} days old")
    check("Apply URL",      bool(apply_url),     apply_url[:60] if apply_url else "MISSING")
    if salary_min:
        check("Salary",     salary_min >= 120000, f"${salary_min:,}")

    check("Resume file",    resume_path and Path(resume_path).exists(),
          str(resume_path.relative_to(BASE_DIR)) if resume_path else "MISSING", hard=False)
    check("Cover letter",   cover_path and Path(cover_path).exists(),
          str(cover_path.relative_to(BASE_DIR)) if cover_path else "MISSING", hard=False)
    check("Outreach draft", outreach_path and Path(outreach_path).exists(),
          str(outreach_path.relative_to(BASE_DIR)) if outreach_path else "MISSING", hard=False)

    contact = lead.get("recruiter") or lead.get("hiring_manager")
    check("Lead found",     bool(contact),
          contact.get("name", "—") if contact else "not found", hard=False)

    verdict = "✅ READY TO APPLY" if hard_pass else "❌ BLOCKED"

    print(f"\n{'═'*50}")
    print(f"SUBMIT CHECKLIST — {company} / {title}")
    print(f"{'═'*50}")
    for c in checks:
        print(c)
    print(f"{'─'*50}")
    print(f"  VERDICT: {verdict}")
    print(f"{'═'*50}\n")

    if dry_run:
        return hard_pass

    if hard_pass:
        # Mark ready_to_apply in scored jobs
        job["status"] = "ready_to_apply"
        job["ready_at"] = datetime.now(timezone.utc).isoformat()
        # Send Slack alert if urgent
        urgency = job.get("urgency_tier", 99)
        if SLACK_WEBHOOK and urgency <= 3:
            _notify_slack(job, resume_path, outreach_path)

    return hard_pass


def _notify_slack(job, resume_path, outreach_path):
    """Send Slack alert: ready to apply."""
    import urllib.request
    company  = job.get("company", "?")
    title    = job.get("title", "PM")
    score    = job.get("score", 0)
    urgency  = job.get("urgency_label", "")
    visa     = job.get("visa_status", "unknown")
    url      = job.get("apply_url", "")
    salary   = job.get("salary_text", "")

    resume_rel = str(resume_path.relative_to(BASE_DIR)) if resume_path else "—"
    outreach_rel = str(outreach_path.relative_to(BASE_DIR)) if outreach_path else "—"

    msg = (
        f"✅ *READY TO APPLY*\n"
        f"*{company}* — {title}\n"
        f"Score: {score}/10 | Urgency: {urgency} | Visa: {visa}\n"
        f"Salary: {salary or 'not listed'}\n"
        f"Resume: `{resume_rel}`\n"
        f"Outreach: `{outreach_rel}`\n"
        f"Apply: {url}"
    )
    payload = json.dumps({"text": msg}).encode()
    req = urllib.request.Request(
        SLACK_WEBHOOK, data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        print("  📣 Slack alert sent")
    except Exception as e:
        print(f"  ⚠ Slack alert failed: {e}")


# ─── Main Pipeline ────────────────────────────────────────────────────────────

def run_pipeline(jobs: list, leads_db: dict, blocklist: set, dry_run: bool = False):
    """Run M5 pipeline for a list of jobs."""
    ready = []
    blocked = []

    for job in jobs:
        company = job.get("company") or "Unknown company"
        title   = job.get("title", "PM")
        score   = job.get("score", 0)
        print(f"\n{'─'*50}")
        print(f"Processing: {company} — {title} (score: {score})")
        print(f"{'─'*50}")

        # 1. Find leads
        lead = find_leads(job, leads_db, dry_run)

        # 2. Draft outreach
        outreach_path = draft_outreach(job, lead, dry_run)

        # 3. Tailor resume
        resume_path = tailor_resume(job, dry_run)

        # 4. Cover letter
        cover_path = generate_cover(job, lead, resume_path, dry_run)

        # 5. Submit checklist
        ok = submit_checklist(job, lead, resume_path, cover_path, outreach_path, blocklist, dry_run)

        if ok:
            ready.append(job)
        else:
            blocked.append(job)

    # Save updated scored jobs
    if not dry_run:
        all_jobs = load_json(SCORED_FILE, [])
        job_map = {j["id"]: j for j in all_jobs}
        for j in ready:
            job_map[j["id"]] = j
        save_json(SCORED_FILE, list(job_map.values()))

    # Summary
    print(f"\n{'═'*50}")
    print(f"M5 PIPELINE COMPLETE")
    print(f"{'═'*50}")
    print(f"  Processed: {len(jobs)}")
    print(f"  ✅ Ready to apply: {len(ready)}")
    print(f"  ❌ Blocked: {len(blocked)}")
    if ready:
        print(f"\nReady jobs:")
        for j in ready:
            print(f"  • {j.get('company')} — {j.get('title')} (score: {j.get('score')})")
    print(f"{'═'*50}")
    return ready


def main():
    parser = argparse.ArgumentParser(description="M5 — Outreach & Apply Pipeline")
    parser.add_argument("--job-id", help="Process single job by ID")
    parser.add_argument("--top", type=int, help="Process top N jobs by score")
    parser.add_argument("--min-score", type=float, default=6.0, help="Minimum score (default: 6)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()

    # Load data
    if not SCORED_FILE.exists():
        print("✗ data/jobs-scored.json not found — run score_jobs.py first")
        sys.exit(1)

    all_jobs = load_json(SCORED_FILE, [])
    leads_db = load_json(LEADS_FILE, {})
    blocklist = load_blocklist()

    if args.dry_run:
        print("⚡ DRY RUN — no files will be written\n")

    # Filter eligible jobs
    if args.job_id:
        jobs = [j for j in all_jobs if j["id"] == args.job_id]
        if not jobs:
            print(f"✗ Job ID not found: {args.job_id}")
            sys.exit(1)
    else:
        eligible = [
            j for j in all_jobs
            if j.get("score", 0) >= args.min_score
            and j.get("visa_status") != "no-sponsorship"
            and j.get("company", "").lower() not in blocklist
            and j.get("days_since_posted", 99) <= 7
            and j.get("status") not in ("ready_to_apply", "applied")
            and not j.get("discard", False)
        ]
        eligible.sort(key=lambda x: x.get("score", 0), reverse=True)

        if args.top:
            jobs = eligible[:args.top]
        else:
            jobs = eligible

    if not jobs:
        print("No eligible jobs found (score>=6, visa OK, not stale, not already processed).")
        sys.exit(0)

    print(f"M5 — Outreach & Apply Pipeline")
    print(f"Jobs to process: {len(jobs)}")
    if not ANTHROPIC_KEY:
        print("⚠ ANTHROPIC_API_KEY not set — using templates (no Claude AI drafting)")
    print()

    run_pipeline(jobs, leads_db, blocklist, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
