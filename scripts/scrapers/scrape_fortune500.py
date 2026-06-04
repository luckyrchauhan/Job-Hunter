"""
Fortune 500 PM Job Scraper — Saturday scan
Covers ~400 Fortune 500 companies via:
  - Greenhouse API (free, instant)
  - Lever API (free, instant)
  - Workday API (public JSON endpoint)
  - Playwright fallback (custom/Taleo/iCIMS)

Saves to: data/jobs-raw/fortune500-YYYY-MM-DD.json
Usage:
  python scripts/scrapers/scrape_fortune500.py
"""
import json, re, time, urllib.request, html, asyncio
from datetime import datetime
from pathlib import Path

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = Path(f"data/jobs-raw/fortune500-{DATE}.json")

PM_TITLES = [
    "product manager", "senior product manager", "sr product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "group product manager", "head of product", "director of product",
    "product lead", "product owner",
]
EXCLUDE_TITLES = [
    "marketing", "sales", "recruiter", "data scientist", "software engineer",
    "developer", "designer", "analyst", "data analyst", "business analyst",
    "vp of product", "vice president", "chief product", "svp", "evp",
    "intern", "co-op",
]

# ─── GREENHOUSE ────────────────────────────────────────────────────────────────
# Fortune 500 + large enterprises using Greenhouse ATS
GREENHOUSE_COMPANIES = [
    # Tech / SaaS
    "stripe", "lyft", "pinterest", "dropbox", "twilio", "okta",
    "cloudflare", "datadog", "mongodb", "elastic", "pagerduty",
    "intercom", "asana", "affirm", "adyen", "checkr", "airbnb",
    "doordash", "coinbase", "figma", "notion", "airtable", "databricks",
    "snowflake", "plaid", "brex", "gusto", "rippling", "carta",
    "benchling", "snyk", "harness", "retool", "amplitude", "mixpanel",
    "robinhood", "faire", "lattice", "scale-ai", "zendesk", "hubspot",
    "outreach", "salesloft", "chime", "marqeta", "blend", "opendoor",
    "momentive", "surveymonkey", "qualtrics", "medallia", "sprinklr",
    "zuora", "coupa", "veeva", "procore", "clio", "toast", "mindbody",
    "servicetitan", "samsara", "motive", "axon", "palantir",
    # Fortune 500 enterprises
    "walmart", "target", "kroger", "walgreens", "cvs",
    "unitedhealth", "anthem", "cigna", "humana", "aetna",
    "jpmorgan", "bankofamerica", "wellsfargo", "citigroup", "goldman",
    "americanexpress", "visa", "mastercard", "paypal", "square",
    "apple", "microsoft", "alphabet", "amazon", "meta", "netflix",
    "salesforce", "oracle", "sap", "ibm", "accenture", "deloitte",
    "mckinsey", "bain", "bcg", "pwc", "kpmg", "ey",
    "boeing", "lockheed", "raytheon", "northropgrumman", "generaldynamics",
    "ge", "honeywell", "3m", "caterpillar", "deere",
    "ford", "gm", "stellantis", "tesla",
    "pfizer", "johnson-johnson", "abbvie", "merck", "eli-lilly",
    "unitedparcelservice", "fedex", "xpo", "chlrobinson",
    "att", "verizon", "tmobile", "comcast", "charter",
    "disney", "warnerbrosdiscovery", "nbc", "paramount",
    "nike", "adidas", "underarmour", "pvh", "hanesbrands",
    "marriott", "hilton", "hyatt", "mgm", "caesars",
    "mcdonalds", "yum", "starbucks", "chipotle", "dominos",
    "homedepot", "lowes", "bestbuy", "costco", "dollar-general",
    "exxon", "chevron", "conocophillips", "phillips66", "valero",
    "duke-energy", "nextera", "dominion", "southern", "exelon",
    "pepsico", "coca-cola", "mondelez", "kellogg", "campbells",
    "procter-gamble", "unilever", "colgate", "kimberly-clark",
    "abbott", "baxter", "becton-dickinson", "medtronic", "stryker",
    "dell", "hp", "hpe", "lenovo", "seagate",
    "intel", "amd", "nvidia", "qualcomm", "broadcom", "texas-instruments",
    "cisco", "juniper", "palo-alto-networks", "fortinet", "crowdstrike",
    "servicenow", "workday", "sap-concur", "infor", "epicor",
    "adobe", "autodesk", "ansys", "ptc", "dassault",
    "uber", "lyft", "instacart", "doordash", "grubhub",
    "airbnb", "booking", "expedia", "tripadvisor", "vrbo",
    "linkedin", "twitter", "snap", "pinterest", "reddit",
    "shopify", "bigcommerce", "magento", "woocommerce",
    "twilio", "sendgrid", "mailchimp", "hubspot", "marketo",
    "splunk", "sumo-logic", "datadog", "dynatrace", "new-relic",
    "hashicorp", "chef", "puppet", "ansible", "terraform",
    "atlassian", "github", "gitlab", "jira", "confluence",
    "zoom", "slack", "teams-microsoft", "webex", "ringcentral",
    "docusign", "hellosign", "adobe-sign",
    "box", "dropbox", "onedrive", "google-drive",
    "aws", "azure", "googlecloud", "digitalocean", "linode",
]

# ─── LEVER ─────────────────────────────────────────────────────────────────────
LEVER_COMPANIES = [
    "netflix", "yelp", "thumbtack", "calm", "duolingo", "headspace",
    "nerdwallet", "betterment", "wealthfront", "shipbob", "flexport",
    "project44", "contentful", "algolia", "sendbird", "loom", "miro",
    "lucidchart", "gem-com", "ashby", "greenhouse", "lever",
    "allbirds", "warby-parker", "everlane", "glossier", "away",
    "hims-hers", "ro", "capsule", "life360", "strava",
    "headway", "cerebral", "brightline", "noom",
    "devoted-health", "oscar-health", "alignment-health",
    "devoted", "clover-health", "HealthSun",
    "gusto", "justworks", "rippling", "bamboohr", "lattice",
    "culture-amp", "leapsome", "betterup", "beamery",
    "highspot", "seismic", "showpad", "mindtickle",
    "gong", "chorus", "clari", "outreach-io",
    "zoominfo", "bombora", "clearbit", "6sense",
    "ironclad", "contractbook", "spotdraft",
    "verkada", "brivo", "openpath", "eagle-eye",
    "flexe", "stord", "whiplash", "shipmonk",
    "samsara", "motive", "fleet-complete", "verizon-connect",
    "transfix", "convoy", "uber-freight", "loadsmart",
    "relativity", "disco", "everlaw", "casetext",
    "carta", "pulley", "shareworks", "equity-zen",
    "brex", "ramp", "airbase", "divvy",
    "plaid", "mx", "finicity", "yodlee",
    "marqeta", "lithic", "unit", "synctera",
]

# ─── WORKDAY ───────────────────────────────────────────────────────────────────
# Format: (company_slug, tenant_id, board_name)
# URL: https://{tenant}.wd5.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs
WORKDAY_COMPANIES = [
    # (display_name, tenant, board)
    ("Amazon",          "amazon",           "Amazon_Jobs"),
    ("Microsoft",       "microsoftcareers", "External"),
    ("Apple",           "apple",            "apple"),
    ("Google",          "google",           "Google"),
    ("Meta",            "meta",             "Meta"),
    ("IBM",             "ibm",              "External"),
    ("Accenture",       "accenture",        "Accenture"),
    ("Oracle",          "oracle",           "oracle"),
    ("AT&T",            "att",              "att"),
    ("Verizon",         "verizon",          "External"),
    ("Comcast",         "comcast",          "External"),
    ("Johnson & Johnson", "jnjcareers",     "JNJ"),
    ("Pfizer",          "pfizer",           "pfizer"),
    ("Merck",           "merck",            "Merck"),
    ("AbbVie",          "abbvie",           "External"),
    ("Eli Lilly",       "lilly",            "ExternalCareers"),
    ("UnitedHealth",    "uhg",              "External"),
    ("Anthem",          "anthem",           "External"),
    ("Cigna",           "cigna",            "Cigna"),
    ("CVS Health",      "cvshealth",        "External"),
    ("Walmart",         "walmart",          "Walmart"),
    ("Target",          "target",           "careerssomething"),
    ("JPMorgan Chase",  "jpmc",             "jpmc"),
    ("Bank of America", "bofa",             "bankofamerica"),
    ("Wells Fargo",     "wellsfargo",       "WellsFargoJobs"),
    ("Goldman Sachs",   "goldmansachs",     "External"),
    ("American Express","aexp",             "External"),
    ("Visa",            "visa",             "Visa"),
    ("Mastercard",      "mastercard",       "mastercard"),
    ("PayPal",          "paypal",           "External"),
    ("Adobe",           "adobe",            "External"),
    ("Salesforce",      "salesforce",       "External"),
    ("ServiceNow",      "servicenow",       "External"),
    ("Workday",         "wd",               "Workday"),
    ("Autodesk",        "autodesk",         "Autodesk"),
    ("Splunk",          "splunk",           "External"),
    ("Palo Alto Networks", "paloaltonetworks", "External"),
    ("CrowdStrike",     "crowdstrike",      "External"),
    ("Fortinet",        "fortinet",         "External"),
    ("Cisco",           "cisco",            "External"),
    ("Dell",            "dell",             "External"),
    ("HP",              "hp",               "External"),
    ("Intel",           "intel",            "External"),
    ("Qualcomm",        "qualcomm",         "External"),
    ("Broadcom",        "broadcom",         "External"),
    ("Nike",            "nike",             "External"),
    ("Starbucks",       "starbucks",        "External"),
    ("McDonald's",      "mcdonalds",        "External"),
    ("Disney",          "disney",           "External"),
    ("Boeing",          "boeing",           "External"),
    ("Lockheed Martin", "lmco",             "External"),
    ("Raytheon",        "rtx",              "External"),
    ("GE",              "ge",               "External"),
    ("Honeywell",       "honeywell",        "External"),
    ("3M",              "3m",               "3M"),
    ("Caterpillar",     "caterpillar",      "CatCareers"),
    ("Deere",           "deere",            "Deere"),
    ("FedEx",           "fedex",            "External"),
    ("UPS",             "upsjobs",          "External"),
    ("Marriott",        "marriott",         "External"),
    ("Hilton",          "hilton",           "External"),
    ("Uber",            "uber",             "External"),
    ("Lyft",            "lyft",             "External"),
    ("Airbnb",          "airbnb",           "External"),
    ("Expedia",         "expedia",          "External"),
    ("Booking Holdings","booking",          "External"),
    ("Shopify",         "shopify",          "External"),
    ("PepsiCo",         "pepsico",          "External"),
    ("Procter & Gamble","pg",               "PGExternalCareerSite"),
    ("Colgate",         "colgate",          "External"),
    ("Medtronic",       "medtronic",        "External"),
    ("Stryker",         "stryker",          "External"),
    ("Abbott",          "abbott",           "External"),
    ("Baxter",          "baxter",           "External"),
    ("Duke Energy",     "duke-energy",      "External"),
    ("NextEra",         "nextera",          "External"),
    ("ExxonMobil",      "exxon",            "External"),
    ("Chevron",         "chevron",          "External"),
    ("Ford",            "ford",             "External"),
    ("General Motors",  "gm",               "External"),
    ("Tesla",           "tesla",            "External"),
    ("Zoom",            "zoom",             "External"),
    ("Slack",           "slack",            "External"),
    ("Atlassian",       "atlassian",        "External"),
    ("GitHub",          "github",           "External"),
    ("GitLab",          "gitlab",           "External"),
    ("Box",             "box",              "External"),
    ("DocuSign",        "docusign",         "External"),
    ("Twilio",          "twilio",           "External"),
    ("Zendesk",         "zendesk",          "External"),
    ("HubSpot",         "hubspot",          "External"),
    ("Sprinklr",        "sprinklr",         "External"),
    ("Veeva",           "veeva",            "External"),
    ("Procore",         "procore",          "External"),
    ("Toast",           "toast",            "External"),
    ("Samsara",         "samsara",          "External"),
    ("Axon",            "axon",             "External"),
    ("Okta",            "okta",             "External"),
    ("CrowdStrike",     "crowdstrike",      "External"),
    ("Datadog",         "datadog",          "External"),
    ("Snowflake",       "snowflake",        "External"),
    ("Databricks",      "databricks",       "External"),
    ("Palantir",        "palantir",         "External"),
    ("Oscar Health",    "oscar",            "External"),
    ("Devoted Health",  "devoted",          "External"),
    ("Clover Health",   "cloverhealth",     "External"),
]

# ─── PLAYWRIGHT FALLBACK ───────────────────────────────────────────────────────
# Companies not on Greenhouse/Lever/Workday
PLAYWRIGHT_COMPANIES = [
    {"company": "Walmart",          "url": "https://careers.walmart.com/results?q=product+manager&job_category=Technology"},
    {"company": "Amazon",           "url": "https://www.amazon.jobs/en/search?base_query=product+manager&job_type=Full-Time"},
    {"company": "Apple",            "url": "https://jobs.apple.com/en-us/search?team=product-management-PRODT"},
    {"company": "Microsoft",        "url": "https://jobs.microsoft.com/us/en/search?q=product+manager&l=en_us&pg=1&pgSz=20"},
    {"company": "Google",           "url": "https://careers.google.com/jobs/results/?q=product+manager&employment_type=FULL_TIME"},
    {"company": "Meta",             "url": "https://www.metacareers.com/jobs?q=product+manager&divisions[0]=Product+Management"},
    {"company": "Netflix",          "url": "https://jobs.netflix.com/search?q=product+manager"},
    {"company": "Salesforce",       "url": "https://careers.salesforce.com/en/jobs/?search=product+manager&category=Product+Management"},
    {"company": "Adobe",            "url": "https://careers.adobe.com/us/en/search-results?qkeyword=product+manager"},
    {"company": "Uber",             "url": "https://www.uber.com/us/en/careers/list/?query=product+manager"},
    {"company": "Twitter/X",        "url": "https://careers.x.com/en/jobs?q=product+manager"},
    {"company": "LinkedIn",         "url": "https://careers.linkedin.com/"},
    {"company": "Snap",             "url": "https://careers.snap.com/jobs?searchText=product+manager"},
    {"company": "Spotify",          "url": "https://www.lifeatspotify.com/jobs?l=remote&q=product+manager"},
    {"company": "Stripe",           "url": "https://stripe.com/jobs/search?teams[]=Product+Management"},
    {"company": "Square/Block",     "url": "https://block.xyz/careers/jobs?q=product+manager"},
    {"company": "Shopify",          "url": "https://www.shopify.com/careers/search?q=product+manager&team=Product"},
    {"company": "Intuit",           "url": "https://jobs.intuit.com/search-jobs/product%20manager"},
    {"company": "SAP",              "url": "https://jobs.sap.com/search/?q=product+manager&locationsearch=United+States"},
    {"company": "Workday",          "url": "https://www.workday.com/en-us/company/careers/open-positions.html#q=product+manager"},
    {"company": "ServiceNow",       "url": "https://careers.servicenow.com/careers/jobs?q=product+manager"},
    {"company": "VMware",           "url": "https://careers.vmware.com/main/jobs?q=product+manager"},
    {"company": "Palo Alto Networks","url": "https://jobs.paloaltonetworks.com/en/jobs/?q=product+manager"},
    {"company": "CrowdStrike",      "url": "https://careers.crowdstrike.com/us/en/job-search#/jobs?q=product+manager"},
    {"company": "Cisco",            "url": "https://jobs.cisco.com/jobs/ProjectDetail/Product-Manager"},
    {"company": "IBM",              "url": "https://www.ibm.com/us-en/employment/"},
    {"company": "Dell",             "url": "https://jobs.dell.com/search-jobs/product+manager"},
    {"company": "HP",               "url": "https://jobs.hp.com/jobsearch/SearchJobs/product%20manager"},
    {"company": "Intel",            "url": "https://jobs.intel.com/en/search#q=product%20manager&t=Jobs"},
    {"company": "Qualcomm",         "url": "https://careers.qualcomm.com/careers/search?keyword=product+manager"},
    {"company": "Nvidia",           "url": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/jobs?q=product+manager"},
]

# ─── HELPERS ───────────────────────────────────────────────────────────────────

def is_pm_title(title: str) -> bool:
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_TITLES):
        return False
    return any(pm in t for pm in PM_TITLES)

def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def parse_salary(text: str):
    if not text:
        return None, None
    text = text.replace("K", "000").replace("k", "000")
    nums = re.findall(r"[\d,]+", text)
    nums = [int(n.replace(",", "")) for n in nums if int(n.replace(",", "")) > 10000]
    if len(nums) >= 2:
        return min(nums), max(nums)
    elif len(nums) == 1:
        return nums[0], nums[0]
    return None, None

def extract_salary(text: str) -> str:
    patterns = [
        r"\$[\d,]+[Kk]?\s*[-–]\s*\$[\d,]+[Kk]?(?:\s*/\s*(?:yr|year|annually))?",
        r"\$[\d,]+[Kk]?\s*(?:per year|\/year|\/yr|annually)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return ""

def fetch_json(url: str, timeout: int = 15, post_data: bytes = None, headers: dict = None):
    try:
        h = {"User-Agent": "Mozilla/5.0 (compatible; JobHunter/1.0)", "Accept": "application/json"}
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, data=post_data, headers=h, method="POST" if post_data else "GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return None

def is_us_location(loc: str) -> bool:
    if not loc:
        return True  # unknown → include
    loc = loc.lower()
    us_keywords = ["remote", "united states", "usa", "u.s.", "new york", "san francisco",
                   "boston", "chicago", "seattle", "austin", "los angeles", "denver",
                   "atlanta", "dallas", "houston", "miami", "portland", "washington dc",
                   "minneapolis", "philadelphia", "phoenix", "san diego", "raleigh"]
    return any(kw in loc for kw in us_keywords)

def days_old(date_str: str) -> int:
    try:
        return (datetime.now().date() - datetime.strptime(date_str[:10], "%Y-%m-%d").date()).days
    except Exception:
        return 0

# ─── GREENHOUSE ────────────────────────────────────────────────────────────────

def scrape_greenhouse(company: str) -> list:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
    data = fetch_json(url)
    if not data:
        return []

    jobs = []
    for job in data.get("jobs", []):
        title = job.get("title", "")
        if not is_pm_title(title):
            continue

        location = job.get("location", {}).get("name", "") or ""
        if not is_us_location(location):
            continue

        description = strip_html(job.get("content", ""))[:6000]
        salary_text = extract_salary(description)
        salary_min, salary_max = parse_salary(salary_text)

        updated = job.get("first_published", job.get("updated_at", ""))
        try:
            posted = datetime.fromisoformat(updated[:10]).strftime("%Y-%m-%d")
        except Exception:
            posted = DATE

        if days_old(posted) > 30:
            continue

        jobs.append({
            "id": f"greenhouse-{job.get('id', '')}",
            "source": "greenhouse",
            "title": title.strip(),
            "company": job.get("company_name", company).strip(),
            "location": location.strip(),
            "remote": "remote" in location.lower() or "remote" in description.lower()[:300],
            "salary_text": salary_text,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "posted_date": posted,
            "apply_url": job.get("absolute_url", ""),
            "description": description,
            "source_query": company,
            "scraped_at": datetime.now().isoformat(),
        })
    return jobs

# ─── LEVER ─────────────────────────────────────────────────────────────────────

def scrape_lever(company: str) -> list:
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    data = fetch_json(url)
    if not data or not isinstance(data, list):
        return []

    jobs = []
    for job in data:
        title = job.get("text", "")
        if not is_pm_title(title):
            continue

        location = job.get("categories", {}).get("location", "") or ""
        commitment = job.get("categories", {}).get("commitment", "") or ""
        if not is_us_location(location):
            continue

        desc_parts = [strip_html(job.get("description", "")), strip_html(job.get("additional", ""))]
        for section in job.get("lists", []):
            desc_parts.append(strip_html(section.get("content", "")))
        description = "\n".join(desc_parts)[:6000]

        salary_text = extract_salary(description)
        salary_min, salary_max = parse_salary(salary_text)

        posted_ts = job.get("createdAt", 0)
        if posted_ts:
            posted = datetime.fromtimestamp(posted_ts / 1000).strftime("%Y-%m-%d")
            if days_old(posted) > 30:
                continue
        else:
            posted = DATE

        jobs.append({
            "id": f"lever-{job.get('id', '')}",
            "source": "lever",
            "title": title.strip(),
            "company": company.replace("-", " ").title(),
            "location": location.strip(),
            "remote": "remote" in (location + commitment).lower(),
            "salary_text": salary_text,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "posted_date": posted,
            "apply_url": job.get("hostedUrl", ""),
            "description": description,
            "source_query": company,
            "scraped_at": datetime.now().isoformat(),
        })
    return jobs

# ─── WORKDAY ───────────────────────────────────────────────────────────────────

def scrape_workday(display_name: str, tenant: str, board: str) -> list:
    """
    Workday public JSON API.
    POST https://{tenant}.wd5.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs
    Body: {"appliedFacets":{},"limit":20,"offset":0,"searchText":"product manager"}
    """
    base_url = f"https://{tenant}.wd5.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs"

    jobs = []
    offset = 0
    limit = 20
    max_pages = 5  # cap at 100 jobs per company

    for _ in range(max_pages):
        payload = json.dumps({
            "appliedFacets": {},
            "limit": limit,
            "offset": offset,
            "searchText": "product manager"
        }).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        data = fetch_json(base_url, post_data=payload, headers=headers)

        if not data:
            break

        postings = data.get("jobPostings", [])
        if not postings:
            break

        for job in postings:
            title = job.get("title", "")
            if not is_pm_title(title):
                continue

            location = job.get("locationsText", "") or ""
            if not is_us_location(location):
                continue

            external_path = job.get("externalPath", "")
            apply_url = f"https://{tenant}.wd5.myworkdayjobs.com/en-US/{board}{external_path}" if external_path else ""

            posted = job.get("postedOn", DATE)
            # Workday format: "Posted 3 Days Ago" or ISO date
            if "ago" in posted.lower():
                try:
                    n = int(re.search(r"\d+", posted).group())
                    from datetime import timedelta
                    posted = (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
                except Exception:
                    posted = DATE
            elif len(posted) >= 10:
                posted = posted[:10]

            if days_old(posted) > 30:
                continue

            remote = "remote" in location.lower()

            jobs.append({
                "id": f"workday-{tenant}-{re.sub(r'[^a-z0-9]', '-', title.lower())[:40]}",
                "source": "workday",
                "title": title.strip(),
                "company": display_name,
                "location": location.strip(),
                "remote": remote,
                "salary_text": "",
                "salary_min": None,
                "salary_max": None,
                "posted_date": posted,
                "apply_url": apply_url,
                "description": "",
                "source_query": tenant,
                "scraped_at": datetime.now().isoformat(),
            })

        total = data.get("total", 0)
        offset += limit
        if offset >= total:
            break

    return jobs

# ─── PLAYWRIGHT FALLBACK ───────────────────────────────────────────────────────

async def scrape_playwright_company(company: str, url: str, page) -> list:
    jobs = []
    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)
        await asyncio.sleep(3)
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

        job_data = await page.evaluate("""() => {
            const results = [];
            const selectors = [
                'a[href*="product-manager"]', 'a[href*="product_manager"]',
                '[class*="job"] a, [class*="position"] a, [class*="role"] a',
            ];
            const seen = new Set();
            selectors.forEach(sel => {
                try {
                    document.querySelectorAll(sel).forEach(a => {
                        if (!a.href || seen.has(a.href)) return;
                        const text = a.innerText.trim() || '';
                        if (!text || text.length < 5) return;
                        seen.add(a.href);
                        results.push({ url: a.href, title: text });
                    });
                } catch(e) {}
            });
            return results;
        }""")

        seen = set()
        for j in job_data:
            title = j.get("title", "").strip()
            if not title or not is_pm_title(title):
                continue
            job_url = j.get("url", url)
            if job_url in seen:
                continue
            seen.add(job_url)
            job_id = re.sub(r"[^a-z0-9]", "-", title.lower())[:40]
            jobs.append({
                "id": f"direct-{company.lower().replace(' ', '_')[:20]}-{job_id}",
                "source": "company_direct",
                "title": title,
                "company": company,
                "location": "See listing",
                "remote": None,
                "salary_text": "",
                "salary_min": None,
                "salary_max": None,
                "posted_date": DATE,
                "apply_url": job_url,
                "description": "",
                "source_query": company,
                "scraped_at": datetime.now().isoformat(),
            })
    except Exception as e:
        print(f"    {company} Playwright error: {e}")
    return jobs

async def scrape_playwright_batch(companies: list) -> list:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("  ⚠ Playwright not installed — skipping custom career pages")
        return []

    all_jobs = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        page = await context.new_page()

        for entry in companies:
            print(f"    {entry['company']}...")
            jobs = await scrape_playwright_company(entry["company"], entry["url"], page)
            print(f"      → {len(jobs)} PM jobs")
            all_jobs.extend(jobs)
            await asyncio.sleep(2)

        await browser.close()
    return all_jobs

# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    Path("data/jobs-raw").mkdir(parents=True, exist_ok=True)
    all_jobs = []
    seen_ids = set()

    def add_jobs(jobs):
        for j in jobs:
            if j["id"] not in seen_ids:
                seen_ids.add(j["id"])
                all_jobs.append(j)

    # ── Tier 1: Greenhouse ──
    print(f"\nGreenhouse — {len(GREENHOUSE_COMPANIES)} Fortune 500 companies")
    gh_count = 0
    for company in GREENHOUSE_COMPANIES:
        jobs = scrape_greenhouse(company)
        if jobs:
            print(f"  ✓ {company}: {len(jobs)} PM jobs")
            gh_count += len(jobs)
        add_jobs(jobs)
        time.sleep(0.3)

    # ── Tier 1: Lever ──
    print(f"\nLever — {len(LEVER_COMPANIES)} Fortune 500 companies")
    lv_count = 0
    for company in LEVER_COMPANIES:
        jobs = scrape_lever(company)
        if jobs:
            print(f"  ✓ {company}: {len(jobs)} PM jobs")
            lv_count += len(jobs)
        add_jobs(jobs)
        time.sleep(0.3)

    # ── Tier 2: Workday ──
    print(f"\nWorkday — {len(WORKDAY_COMPANIES)} Fortune 500 companies")
    wd_count = 0
    for display_name, tenant, board in WORKDAY_COMPANIES:
        jobs = scrape_workday(display_name, tenant, board)
        if jobs:
            print(f"  ✓ {display_name}: {len(jobs)} PM jobs")
            wd_count += len(jobs)
        add_jobs(jobs)
        time.sleep(0.5)

    # ── Tier 3: Playwright fallback ──
    print(f"\nPlaywright fallback — {len(PLAYWRIGHT_COMPANIES)} companies")
    pw_jobs = asyncio.run(scrape_playwright_batch(PLAYWRIGHT_COMPANIES))
    pw_count = 0
    for j in pw_jobs:
        if j["id"] not in seen_ids:
            seen_ids.add(j["id"])
            all_jobs.append(j)
            pw_count += 1

    OUT_FILE.write_text(json.dumps(all_jobs, indent=2))
    salary_count = sum(1 for j in all_jobs if j.get("salary_text"))
    print(f"\nFortune 500 scraper complete:")
    print(f"  Greenhouse: {gh_count} | Lever: {lv_count} | Workday: {wd_count} | Playwright: {pw_count}")
    print(f"  Total: {len(all_jobs)} PM jobs | With salary: {salary_count}")
    print(f"  Saved → {OUT_FILE}")


if __name__ == "__main__":
    main()
