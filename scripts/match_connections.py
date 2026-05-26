"""
Connection Matcher + Outreach Generator
Reads:  data/connections.csv      — LinkedIn connections export
        data/jobs-scored.json     — scored jobs
Writes: data/jobs-scored.json     — adds connections_to_reach_out, connection_email, outreach_message
        data/connections-index.json — parsed + prioritized connection index

Priority tiers (for same company):
  1. Indian-origin name + US location (or US company)
  2. Previous employer connection
  3. Any other connection

Usage:
  python scripts/match_connections.py
  python scripts/match_connections.py --dry-run   # print matches, don't write
"""
import csv, json, re, argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
CONNECTIONS_FILE = BASE_DIR / "data" / "connections.csv"
SCORED_FILE = BASE_DIR / "data" / "jobs-scored.json"
INDEX_FILE = BASE_DIR / "data" / "connections-index.json"

# ── Previous companies from resume ───────────────────────────────────────────
PREVIOUS_COMPANIES = [
    "accenture", "sap", "tata", "infosys", "wipro", "cognizant", "hcl",
    "deloitte", "pwc", "kpmg", "mckinsey", "bcg", "bain",
    # add more from your resume
]

# ── Indian-origin name heuristics ────────────────────────────────────────────
INDIAN_FIRST_NAMES = {
    "aarav","aditya","akash","amit","amitesh","amol","anand","anil","anish","anjan",
    "ankur","anoop","anuj","anurag","arjun","arpit","aryan","ashish","ashok","ashwin",
    "atharva","ayush","bharat","chirag","deepak","devesh","dhruv","dinesh","divij",
    "gaurav","harsh","hemant","hitesh","ishan","ishaan","jay","jayesh","jignesh",
    "kamal","kapil","kartik","kiran","krishna","kunal","lakshmi","lokesh","madhav",
    "manoj","manish","mehul","milan","mithun","mohit","mukesh","naveen","neeraj",
    "nikhil","nirav","nishant","parag","parth","pavan","piyush","pradeep","pranav",
    "prasad","prashant","pratik","praveen","prem","puneet","rahul","raj","rajesh",
    "rajan","rajiv","rakesh","ram","ramesh","ravi","rishabh","ritesh","rohan",
    "rohit","sachin","sahil","sanjay","sanket","saurabh","shashank","shiv","shivam",
    "shreya","siddharth","soham","sourav","subhash","sudhir","sunil","suresh",
    "sushant","tanmay","tarun","uday","utkarsh","vaibhav","vijay","vikram","vikas",
    "vinay","vineet","vishal","vivek","yash","yogesh",
    # female names
    "aarthi","aditi","akanksha","amrita","ananya","anjali","anushka","aparna",
    "aradhana","archana","arpita","aruna","asha","ashwini","avni","bhavana",
    "deepa","deepika","devika","diya","gayatri","heena","ishita","isha","jyoti",
    "kajal","kavita","kavya","kiran","komal","kritika","lakshmi","lavanya",
    "madhuri","meera","megha","minal","mitali","mohini","namrata","nandita",
    "neha","nidhi","nikita","nisha","nita","pooja","preethi","prerna","priya",
    "priyanka","puja","radha","rashmi","ritu","riya","sangeeta","sarika","seema",
    "shilpa","shweta","simran","smita","sneha","sonal","sonali","sonam","sonu",
    "suchitra","sudha","sunita","supriya","swati","tanvi","usha","vandana",
    "varsha","vidya","vina","yogita",
}

INDIAN_LAST_NAMES = {
    "agarwal","aggarwal","ahuja","arora","bajaj","banerjee","batra","bhatt",
    "bose","chakraborty","chaudhary","chauhan","chawla","chopra","datta","dave",
    "desai","deshpande","dey","dhawan","dubey","dutta","gandhi","garg","ghosh",
    "goswami","grover","gupta","iyer","jain","jaiswal","jha","joshi","kapoor",
    "kaur","khanna","kulkarni","kumar","lal","madan","mahajan","malhotra",
    "mehta","menon","mishra","mistry","mittal","modi","mukherjee","murthy",
    "nair","nanda","narang","narayan","nayyar","pandey","patel","pathak","patil",
    "pillai","prasad","rao","rastogi","reddy","saha","sahni","sen","sethi",
    "shah","sharma","shukla","singh","sinha","soni","srinivasan","talwar",
    "tandon","tiwari","trivedi","varma","verma","yadav",
}


def is_indian_origin(first: str, last: str) -> bool:
    return (
        first.lower() in INDIAN_FIRST_NAMES or
        last.lower() in INDIAN_LAST_NAMES
    )


def normalize_company(name: str) -> str:
    if not name:
        return ""
    name = name.lower()
    # Strip ATS/department suffixes like "company -> dept"
    name = name.split("->")[0].strip()
    for suffix in [" inc.", " inc", " llc", " corp.", " corp", " ltd.", " ltd",
                   " technologies", " technology", " solutions", " software",
                   " group", " holdings", " global", " services", " consulting"]:
        name = name.replace(suffix, "")
    name = re.sub(r"\s+", " ", name).strip()
    return name


def company_match(conn_company: str, job_company: str) -> bool:
    """Fuzzy company match."""
    c1 = normalize_company(conn_company)
    c2 = normalize_company(job_company)
    if not c1 or not c2:
        return False
    return c1 == c2 or c1 in c2 or c2 in c1


def tier_connection(conn: dict) -> int:
    """
    Priority tier (lower = higher priority):
      1 = Indian-origin in USA
      2 = Previous employer
      3 = Any other connection
    """
    first = conn.get("first_name", "")
    last = conn.get("last_name", "")
    company = conn.get("company", "").lower()

    if is_indian_origin(first, last):
        return 1
    if any(prev in company for prev in PREVIOUS_COMPANIES):
        return 2
    return 3


def load_connections() -> list:
    if not CONNECTIONS_FILE.exists():
        print("✗ data/connections.csv not found")
        return []

    connections = []
    with open(CONNECTIONS_FILE, newline="", encoding="utf-8-sig") as f:
        lines = f.readlines()

    # Find header row
    header_idx = 0
    for i, line in enumerate(lines):
        if "First Name" in line or "FirstName" in line:
            header_idx = i
            break

    reader = csv.DictReader(lines[header_idx:])
    for row in reader:
        first = (row.get("First Name") or row.get("FirstName") or "").strip()
        last = (row.get("Last Name") or row.get("LastName") or "").strip()
        email = (row.get("Email Address") or row.get("Email") or "").strip()
        company = (row.get("Company") or "").strip()
        position = (row.get("Position") or "").strip()
        url = (row.get("URL") or "").strip()

        if not first and not last:
            continue

        connections.append({
            "first_name": first,
            "last_name": last,
            "full_name": f"{first} {last}".strip(),
            "email": email,
            "company": company,
            "company_norm": normalize_company(company),
            "position": position,
            "linkedin_url": url,
            "tier": tier_connection({"first_name": first, "last_name": last, "company": company}),
            "indian_origin": is_indian_origin(first, last),
        })

    print(f"✓ Loaded {len(connections)} connections")
    print(f"  Indian-origin: {sum(1 for c in connections if c['indian_origin'])}")
    print(f"  With email: {sum(1 for c in connections if c['email'])}")
    return connections


def find_matches(job: dict, connections: list) -> list:
    """Return top 3 connections at job's company, ranked by tier."""
    job_company = job.get("company", "")
    matches = [c for c in connections if company_match(c["company"], job_company)]
    matches.sort(key=lambda c: c["tier"])
    return matches[:3]


def generate_outreach(conn: dict, job: dict) -> str:
    """Generate human-sounding outreach message based on relationship tier."""
    name = conn["first_name"]
    job_title = job.get("title", "")
    job_company = job.get("company", "")
    tier = conn["tier"]
    position = conn.get("position", "")

    if tier == 1:
        # Indian-origin — warm desi-network angle
        msg = (
            f"Hi {name},\n\n"
            f"Hope you're doing well! I came across your profile and noticed we're both part of the Indian tech community navigating the US PM space — always great to connect with fellow desis!\n\n"
            f"I'm currently exploring PM opportunities and saw that {job_company} has an opening for {job_title}. "
            f"Given your experience{f' as {position}' if position else ' there'}, I'd love to get your perspective on the team and culture — even a quick 15-minute chat would mean a lot.\n\n"
            f"Would you be open to connecting? Happy to share my background if helpful.\n\n"
            f"Thanks so much,\n[YOUR_NAME]"
        )
    elif tier == 2:
        # Previous company connection
        shared = normalize_company(conn["company"]).title()
        msg = (
            f"Hi {name},\n\n"
            f"I was looking through my network and realized we both have {shared} in common — small world!\n\n"
            f"I'm currently looking at a {job_title} role at {job_company} and thought you might have some insight into what the team is like there. "
            f"If you have a few minutes for a quick chat, I'd really appreciate it — no pressure at all.\n\n"
            f"Hope things are going well on your end!\n\nBest,\n[YOUR_NAME]"
        )
    else:
        # General connection
        msg = (
            f"Hi {name},\n\n"
            f"I noticed you're at {job_company} and I'm genuinely excited about the {job_title} opportunity there. "
            f"I've been a PM for 11+ years across enterprise platforms and AI products, and this role seems like a great fit.\n\n"
            f"Would you be open to a quick chat about the team culture and what success looks like in this role? "
            f"I'd love to learn more before applying — and happy to share my background too.\n\n"
            f"Thanks for considering it!\n\nBest,\n[YOUR_NAME]"
        )
    return msg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    connections = load_connections()
    if not connections:
        return

    # Save index
    INDEX_FILE.write_text(json.dumps(connections, indent=2))
    print(f"✓ Connection index saved → {INDEX_FILE}")

    # Load scored jobs
    if not SCORED_FILE.exists():
        print("✗ data/jobs-scored.json not found — run score_jobs.py first")
        return

    jobs = json.loads(SCORED_FILE.read_text())
    active_jobs = [j for j in jobs if not j.get("discard") and j.get("score", 0) >= 5]
    print(f"\nMatching connections for {len(active_jobs)} active jobs (score ≥ 5)...")

    matched_count = 0
    for job in active_jobs:
        matches = find_matches(job, connections)
        if not matches:
            continue

        matched_count += 1
        top = matches[0]

        # Connection bonus for priority score
        tier = top["tier"]
        conn_bonus = 3 if tier == 1 else 2 if tier == 2 else 1

        # Update priority score
        old_priority = job.get("priority_score", 0) or 0
        breakdown = job.get("priority_breakdown", {})
        breakdown["connection_bonus"] = conn_bonus
        raw_bonus = sum(v for v in breakdown.values() if isinstance(v, (int, float)))
        MAX_POSSIBLE = 22.5
        new_priority = round(min((raw_bonus / MAX_POSSIBLE) * 10, 10.0), 1)

        if new_priority >= 8.0:
            priority_band = "🔥 Apply Now"
        elif new_priority >= 6.0:
            priority_band = "⚡ Apply Soon"
        elif new_priority >= 4.0:
            priority_band = "👀 Consider"
        else:
            priority_band = "📋 Low Priority"

        # Format connections column
        conn_lines = []
        for c in matches:
            tier_emoji = "🥇" if c["tier"] == 1 else "🥈" if c["tier"] == 2 else "🥉"
            conn_lines.append(f"{tier_emoji} {c['full_name']} — {c['position']}")
        connections_display = "\n".join(conn_lines)

        # Top connection email + outreach
        outreach = generate_outreach(top, job)

        job.update({
            "connections_to_reach_out": connections_display,
            "connection_email": top["email"],
            "connection_linkedin": top["linkedin_url"],
            "outreach_message": outreach,
            "priority_score": new_priority,
            "priority_band": priority_band,
            "priority_breakdown": breakdown,
        })

        if args.dry_run or matched_count <= 5:
            print(f"\n  [{job['score']}] {job.get('company')} — {job.get('title')}")
            print(f"    Priority: {old_priority} → {new_priority} {priority_band}")
            print(f"    Connections: {connections_display.replace(chr(10), ' | ')}")
            print(f"    Email: {top['email'] or 'not available'}")

    print(f"\n✓ Matched {matched_count} jobs with connections")

    if not args.dry_run:
        SCORED_FILE.write_text(json.dumps(jobs, indent=2))
        print(f"✓ Updated jobs-scored.json with connection data")


if __name__ == "__main__":
    main()
