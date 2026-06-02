"""
Manga Update Checker
====================
Scrapes manga sites for recent updates and sends notifications
via Microsoft Teams (webhook) and/or Email.

Add manga URLs to MANGA_URLS below, then configure secrets in GitHub.
"""

import requests
from bs4 import BeautifulSoup
import re
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import time

# ─────────────────────────────────────────────
#  MANGA URLS TO MONITOR — add as many as you like
# ─────────────────────────────────────────────
MANGA_URLS = [
    "https://kaliscan.com/manga/26690-solo-max-level-newbie",
    "https://kaliscan.com/manga/47759-catastrophic-necromancer",
    "https://kaliscan.com/manga/53594-regressing-with-the-kings-power",
    "https://kaliscan.com/manga/5995-the-great-mage-returns-after-4000-years",
    "https://kaliscan.com/manga/19897-return-of-the-frozen-player",
    "https://kaliscan.com/manga/39062-return-of-the-sss-class-ranker",
]

# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────
# Notify if manga was updated within this many minutes
UPDATE_THRESHOLD_MINUTES = 60

# Toggle notification methods
NOTIFY_TEAMS = False  # Microsoft Teams via Incoming Webhook
NOTIFY_EMAIL = True   # Email via SMTP (e.g. Gmail)

# Delay between page requests (seconds) — be polite to servers
REQUEST_DELAY = 3

# ─────────────────────────────────────────────
#  CREDENTIALS — Set these as GitHub Secrets
#  (never hard-code credentials here)
# ─────────────────────────────────────────────
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")
EMAIL_FROM        = os.environ.get("EMAIL_FROM", "")
EMAIL_TO          = os.environ.get("EMAIL_TO", "")
EMAIL_PASSWORD    = os.environ.get("EMAIL_PASSWORD", "")
SMTP_SERVER       = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", "587"))


# ═════════════════════════════════════════════
#  SCRAPING LOGIC
# ═════════════════════════════════════════════

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def parse_minutes_since_update(text: str) -> int | None:
    """
    Parse a relative time string like '26 minutes ago', '3 hours ago', '2 days ago'.
    Returns minutes as an integer, or None if unparseable.
    """
    if not text:
        return None

    t = text.lower().strip()

    if any(k in t for k in ("just now", "second")):
        return 0

    m = re.search(r"(\d+)\s*minute", t)
    if m:
        return int(m.group(1))

    m = re.search(r"(\d+)\s*hour", t)
    if m:
        return int(m.group(1)) * 60

    if "an hour" in t or "1 hour" in t:
        return 60

    # Anything else (days, weeks) counts as not-recent
    return None


def is_recently_updated(update_text: str) -> bool:
    minutes = parse_minutes_since_update(update_text)
    if minutes is None:
        return False
    return minutes <= UPDATE_THRESHOLD_MINUTES


def extract_update_text(soup: BeautifulSoup) -> str | None:
    """
    Try multiple strategies to find the 'Last update' value in the page.
    Returns just the time string, e.g. '26 minutes ago'.
    """

    # Strategy 1 — find a text node containing "last update" and grab sibling/parent text
    for node in soup.find_all(string=re.compile(r"last\s*update", re.IGNORECASE)):
        parent = node.find_parent()
        if not parent:
            continue
        full = parent.get_text(" ", strip=True)
        m = re.search(r"last\s*update[:\s]+(.+)", full, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    # Strategy 2 — look for standalone relative-time strings anywhere in the page
    for pattern in (
        r"\d+\s*minutes?\s*ago",
        r"\d+\s*hours?\s*ago",
        r"just\s*now",
    ):
        for node in soup.find_all(string=re.compile(pattern, re.IGNORECASE)):
            return node.strip()

    return None


def extract_title(soup: BeautifulSoup, url: str) -> str:
    for tag in ("h1", "h2", "h3"):
        el = soup.find(tag)
        if el:
            return el.get_text(strip=True)
    return url.rstrip("/").split("/")[-1].replace("-", " ").title()


def scrape_manga(url: str) -> dict:
    """Fetch a manga page and return structured info."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        title       = extract_title(soup, url)
        update_text = extract_update_text(soup)
        recent      = is_recently_updated(update_text) if update_text else False

        return {
            "url":              url,
            "title":            title,
            "update_text":      update_text or "Could not detect",
            "recently_updated": recent,
            "checked_at":       datetime.utcnow().isoformat(),
        }

    except requests.RequestException as exc:
        return {
            "url":              url,
            "title":            url.split("/")[-1],
            "update_text":      None,
            "recently_updated": False,
            "error":            str(exc),
            "checked_at":       datetime.utcnow().isoformat(),
        }


# ═════════════════════════════════════════════
#  NOTIFICATIONS
# ═════════════════════════════════════════════

def send_teams_notification(updates: list[dict]) -> bool:
    if not TEAMS_WEBHOOK_URL:
        print("  ⚠️  TEAMS_WEBHOOK_URL secret not set — skipping Teams notification")
        return False

    facts = [
        {
            "name":  item["title"],
            "value": f"Updated {item['update_text']} → [Read Now]({item['url']})",
        }
        for item in updates
    ]

    payload = {
        "@type":    "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "FF6B35",
        "summary":    f"📚 {len(updates)} manga update(s) detected",
        "sections": [{
            "activityTitle":    "📚 Manga Update Alert",
            "activitySubtitle": f"{len(updates)} title(s) updated recently",
            "facts":            facts,
            "markdown":         True,
        }],
    }

    try:
        r = requests.post(TEAMS_WEBHOOK_URL, json=payload, timeout=10)
        r.raise_for_status()
        print(f"  ✅ Teams notification sent ({len(updates)} update(s))")
        return True
    except Exception as exc:
        print(f"  ❌ Teams notification failed: {exc}")
        return False


def send_email_notification(updates: list[dict]) -> bool:
    if not all([EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD]):
        print("  ⚠️  Email secrets not fully configured — skipping email")
        return False

    subject = f"📚 Manga Update Alert: {len(updates)} new update(s)"
    lines = ["The following manga were recently updated:\n"]
    for item in updates:
        lines += [
            f"📖  {item['title']}",
            f"    Last update : {item['update_text']}",
            f"    URL         : {item['url']}\n",
        ]
    lines.append(f"Checked at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    msg = MIMEMultipart()
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText("\n".join(lines), "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"  ✅ Email sent to {EMAIL_TO}")
        return True
    except Exception as exc:
        print(f"  ❌ Email failed: {exc}")
        return False


# ═════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════

def main():
    sep = "─" * 55
    print(f"\n{sep}")
    print(f"  Manga Update Checker  ·  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Threshold: last {UPDATE_THRESHOLD_MINUTES} minutes")
    print(sep)

    recently_updated = []

    for i, url in enumerate(MANGA_URLS):
        if i > 0:
            time.sleep(REQUEST_DELAY)

        print(f"\n🔍  {url}")
        result = scrape_manga(url)
        print(f"    Title      : {result['title']}")
        print(f"    Last update: {result['update_text']}")
        print(f"    Recent     : {'✅ YES — will notify' if result['recently_updated'] else '❌ No'}")

        if "error" in result:
            print(f"    Error      : {result['error']}")

        if result["recently_updated"]:
            recently_updated.append(result)

    print(f"\n{sep}")
    print(f"  Result: {len(recently_updated)} of {len(MANGA_URLS)} manga updated recently")
    print(sep)

    if recently_updated:
        print("\n📣  Sending notifications…")
        if NOTIFY_TEAMS:
            send_teams_notification(recently_updated)
        if NOTIFY_EMAIL:
            send_email_notification(recently_updated)
    else:
        print("\n  No recent updates — no notifications sent.")

    print()


if __name__ == "__main__":
    main()
