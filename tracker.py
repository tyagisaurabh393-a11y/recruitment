import json, os, re, smtplib, sys, time
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urljoin, urldefrag
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "state.json"
SOURCES_FILE = ROOT / "sources.json"
KEYWORDS_FILE = ROOT / "keywords.json"
USER_AGENT = "IndiaRecruitmentTracker/1.0 (public recruitment page monitor)"
CHECK_INTERVAL_DAYS = 15
TIMEOUT = 25

def now_utc():
    return datetime.now(timezone.utc)

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def fetch_source(source, terms, excludes):
    url = source["url"]
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type and "text" not in content_type:
            return [], f"Skipped non-HTML content ({content_type or 'unknown type'})"
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = norm(soup.get_text(" ", strip=True))
        matches = []
        for a in soup.find_all("a", href=True):
            label = a.get_text(" ", strip=True)
            href = a.get("href", "").strip()
            if not href or href.startswith(("javascript:", "mailto:", "#")):
                continue
            full_url = urldefrag(urljoin(response.url, href))[0]
            combined = norm(label + " " + href)
            if not any(term in combined for term in terms):
                continue
            if any(term in combined for term in excludes):
                continue
            # Keep same-domain links and official documents linked from the official page.
            matches.append({
                "source": source["name"],
                "label": label[:220] or href,
                "url": full_url,
                "priority": any(t in combined for t in PRIORITY_TERMS)
            })
        # If a page contains recruitment terms but links are not clearly labelled, note page itself.
        if not matches and any(term in page_text for term in terms[:8]):
            matches.append({
                "source": source["name"],
                "label": "Recruitment/careers page — review manually",
                "url": response.url,
                "priority": any(t in page_text for t in PRIORITY_TERMS)
            })
        # Deduplicate links
        unique = {}
        for item in matches:
            unique[item["url"]] = item
        return list(unique.values()), None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:180]}"

def send_email(subject, body):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    recipient = os.getenv("ALERT_TO")
    if not all([host, user, password, recipient]):
        print("\nEmail not configured. Report follows:\n")
        print(body)
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = recipient
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
    return True

def main():
    global PRIORITY_TERMS
    cfg = load_json(KEYWORDS_FILE, {})
    terms = [norm(x) for x in cfg.get("recruitment_terms", [])]
    excludes = [norm(x) for x in cfg.get("exclude_terms", [])]
    PRIORITY_TERMS = [norm(x) for x in cfg.get("priority_terms", [])]
    state = load_json(STATE_FILE, {"last_check_utc": None, "known_urls": []})
    now = now_utc()
    force = os.getenv("FORCE_CHECK", "").lower() in ("1", "true", "yes")
    last = None
    if state.get("last_check_utc"):
        try:
            last = datetime.fromisoformat(state["last_check_utc"])
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if not force and last and now - last < timedelta(days=CHECK_INTERVAL_DAYS):
        print(f"Not due yet. Last check: {last.isoformat()}; next check after { (last + timedelta(days=CHECK_INTERVAL_DAYS)).isoformat() }")
        return

    sources = load_json(SOURCES_FILE, [])
    known = set(state.get("known_urls", []))
    current = {}
    errors = []
    for i, source in enumerate(sources, 1):
        found, error = fetch_source(source, terms, excludes)
        if error:
            errors.append(f"- {source['name']}: {error}")
        for item in found:
            current[item["url"]] = item
        print(f"[{i}/{len(sources)}] {source['name']}: {len(found)} matching link(s)")
        time.sleep(0.7)  # be polite to public websites

    new_items = [item for url, item in current.items() if url not in known]
    new_items.sort(key=lambda x: (not x.get("priority", False), x["source"].lower(), x["label"].lower()))

    lines = [
        f"India Recruitment Tracker — {now.strftime('%d %b %Y %H:%M UTC')}",
        "",
        f"Official pages checked: {len(sources)}",
        f"Matching links currently found: {len(current)}",
        f"New matching links since the previous successful scan: {len(new_items)}",
        "",
        "IMPORTANT: These are keyword matches, not confirmed open vacancies. Open each official notice and verify dates, eligibility, post/scale and application status.",
        ""
    ]
    if new_items:
        lines.append("NEWLY DISCOVERED LINKS")
        lines.append("----------------------")
        for item in new_items:
            priority = " [PRIORITY MATCH]" if item.get("priority") else ""
            lines.append(f"- {item['source']}{priority}\n  {item['label']}\n  {item['url']}")
    else:
        lines.append("No newly discovered matching links. Review the official pages if you are expecting a particular notification.")

    if errors:
        lines.extend(["", "PAGES THAT COULD NOT BE CHECKED", "-------------------------------", *errors])

    body = "\n".join(lines)
    print(body)
    # Email on each due scan so the user gets a status report, including no-change reports.
    send_email(f"Recruitment Tracker: {len(new_items)} new link(s)", body)

    # Keep the current set for diffing next time; retain known links even if pages remove them.
    state["last_check_utc"] = now.isoformat()
    state["known_urls"] = sorted(known.union(current.keys()))
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
