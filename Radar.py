#!/usr/bin/env python3
import asyncio
import json
import os
import random
import smtplib
import sqlite3
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.async_api import async_playwright, TimeoutError

STATE_FILE = "storage_state.json"
SCREENSHOT_DIR = "debug_screens"
DB_FILE = os.environ.get("DB_PATH", "leads.db")

# Email config — set these in Render environment variables
SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER")      # your Gmail address
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")  # Gmail App Password
NOTIFY_EMAIL  = os.environ.get("NOTIFY_EMAIL")   # where to send lead alerts

GROUP_IDS = [
    "960191220672227",
    "453104559281301",
    "5664138873654225",
    "222392601967984",
    "1838156176874401"
]

KEYWORDS = [
    "tree",
    "tree removal",
    "cut tree",
    "fallen tree",
    "storm damage",
    "dangerous tree",
    "branches falling",
    "stump"
]

# ── Email ─────────────────────────────────────────────────────────────────────

def send_lead_email(url, keyword):
    if not all([SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL]):
        log("Email not configured — skipping notification.")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🌳 New Tree Lead: {keyword}"
        msg["From"]    = SMTP_USER
        msg["To"]      = NOTIFY_EMAIL

        text = f"New lead found!\n\nKeyword: {keyword}\nPost: {url}\nFound at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        html = f"""
        <html><body style="font-family:sans-serif;padding:20px;">
          <h2 style="color:#2d6a4f;">🌳 New Tree Lead Found</h2>
          <table style="border-collapse:collapse;width:100%;max-width:500px;">
            <tr>
              <td style="padding:8px;font-weight:bold;color:#555;">Keyword</td>
              <td style="padding:8px;">{keyword}</td>
            </tr>
            <tr style="background:#f4f4f4;">
              <td style="padding:8px;font-weight:bold;color:#555;">Post</td>
              <td style="padding:8px;"><a href="{url}" style="color:#1a73e8;">{url}</a></td>
            </tr>
            <tr>
              <td style="padding:8px;font-weight:bold;color:#555;">Found at</td>
              <td style="padding:8px;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
          </table>
          <p style="margin-top:20px;color:#888;font-size:12px;">Sent by Tree Lead Radar</p>
        </body></html>
        """

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, NOTIFY_EMAIL, msg.as_string())

        log(f"📧 Email sent to {NOTIFY_EMAIL}")

    except Exception as e:
        log(f"Failed to send email: {e}")

# ── Database ──────────────────────────────────────────────────────────────────

def init_db():
    con = sqlite3.connect(DB_FILE)
    con.execute("""
        CREATE TABLE IF NOT EXISTS seen_posts (
            url TEXT PRIMARY KEY,
            first_seen TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            keyword TEXT NOT NULL,
            found_at TEXT NOT NULL
        )
    """)
    con.commit()
    return con

def is_seen(con, url):
    return con.execute("SELECT 1 FROM seen_posts WHERE url = ?", (url,)).fetchone() is not None

def mark_seen(con, url):
    con.execute(
        "INSERT OR IGNORE INTO seen_posts (url, first_seen) VALUES (?, ?)",
        (url, datetime.now().isoformat())
    )
    con.commit()

def save_lead(con, url, keyword):
    con.execute(
        "INSERT INTO leads (url, keyword, found_at) VALUES (?, ?, ?)",
        (url, keyword, datetime.now().isoformat())
    )
    con.commit()

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

async def safe_goto(page, url):
    try:
        response = await page.goto(url, timeout=30000)
        if response is None:
            raise Exception("No response received.")
        if response.status != 200:
            raise Exception(f"HTTP {response.status}")
    except Exception as e:
        log(f"Navigation failed: {url}")
        log(str(e))
        await save_debug(page)
        return False
    return True

async def save_debug(page):
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)
    filename = f"{SCREENSHOT_DIR}/error_{int(datetime.now().timestamp())}.png"
    await page.screenshot(path=filename)
    log(f"Saved debug screenshot: {filename}")

# ── Auth ──────────────────────────────────────────────────────────────────────

async def login_if_needed(context, page):
    if os.path.exists(STATE_FILE):
        log("Using saved login session.")
        return

    log("Login required.")
    email    = os.environ.get("FB_EMAIL")
    password = os.environ.get("FB_PASSWORD")

    if not email or not password:
        log("Missing FB_EMAIL or FB_PASSWORD environment variables.")
        sys.exit(1)

    ok = await safe_goto(page, "https://www.facebook.com/login")
    if not ok:
        sys.exit(1)

    try:
        await page.fill("input[name='email']", email)
        await page.fill("input[name='pass']", password)
        await page.click("button[name='login']")
        await page.wait_for_timeout(8000)
    except Exception as e:
        log("Login interaction failed.")
        log(str(e))
        await save_debug(page)
        sys.exit(1)

    if "login" in page.url.lower():
        log("Login appears to have failed. Still on login page.")
        await save_debug(page)
        sys.exit(1)

    await context.storage_state(path=STATE_FILE)
    log("Login successful and saved.")

# ── Scanner ───────────────────────────────────────────────────────────────────

async def scan_group(page, group_id, con):
    url = f"https://www.facebook.com/groups/{group_id}"
    log(f"Scanning Group {group_id}")
    ok = await safe_goto(page, url)
    if not ok:
        return

    try:
        await page.wait_for_selector("a[href*='/permalink/']", timeout=10000)
    except TimeoutError:
        log("No post links found. Possible layout change or blocked.")
        await save_debug(page)
        return

    links = await page.eval_on_selector_all(
        "a[href*='/permalink/']",
        "elements => elements.map(e => e.href)"
    )

    if not links:
        log("No permalink links extracted.")
        return

    log(f"Found {len(links)} potential posts.")

    for link in links:
        if is_seen(con, link):
            continue

        mark_seen(con, link)

        post_page = await page.context.new_page()
        ok = await safe_goto(post_page, link)
        if not ok:
            await post_page.close()
            continue

        content = (await post_page.content()).lower()
        for keyword in KEYWORDS:
            if keyword in content:
                log("🚨 LEAD FOUND 🚨")
                log(f"Keyword: {keyword}")
                log(f"Post: {link}")
                log("-" * 40)
                save_lead(con, link, keyword)
                send_lead_email(link, keyword)
                break

        await post_page.close()
        await asyncio.sleep(random.uniform(2, 4))

# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    con = init_db()
    log(f"Database: {DB_FILE}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-zygote",
                "--single-process",
            ]
        )
        context = await browser.new_context(
            storage_state=STATE_FILE if os.path.exists(STATE_FILE) else None
        )
        page = await context.new_page()
        await login_if_needed(context, page)

        log("Tree Lead Radar Running...")
        log("=" * 40)

        for group_id in GROUP_IDS:
            await scan_group(page, group_id, con)
            await asyncio.sleep(random.uniform(5, 8))

        await browser.close()

    con.close()
    log("Scan complete.")

if __name__ == "__main__":
    asyncio.run(main())
