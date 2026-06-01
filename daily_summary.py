#!/usr/bin/env python3
"""
Daily summary email — run as a separate Render cron job.
Sends a summary of all leads found in the last 24 hours.
"""

import os
import smtplib
import sqlite3
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

DB_FILE       = os.environ.get("DB_PATH", "leads.db")
SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
NOTIFY_EMAIL  = os.environ.get("NOTIFY_EMAIL")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def get_stats():
    if not os.path.exists(DB_FILE):
        return None, []

    con = sqlite3.connect(DB_FILE)
    since = (datetime.now() - timedelta(hours=24)).isoformat()

    total_all     = con.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    total_seen    = con.execute("SELECT COUNT(*) FROM seen_posts").fetchone()[0]
    last_24h      = con.execute("SELECT COUNT(*) FROM leads WHERE found_at >= ?", (since,)).fetchone()[0]
    by_keyword    = con.execute(
        "SELECT keyword, COUNT(*) FROM leads GROUP BY keyword ORDER BY COUNT(*) DESC"
    ).fetchall()
    recent_leads  = con.execute(
        "SELECT url, keyword, found_at FROM leads WHERE found_at >= ? ORDER BY found_at DESC",
        (since,)
    ).fetchall()
    con.close()

    stats = {
        "total_all":   total_all,
        "total_seen":  total_seen,
        "last_24h":    last_24h,
        "by_keyword":  by_keyword,
    }
    return stats, recent_leads

def send_summary():
    if not all([SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL]):
        log("Email not configured — skipping.")
        return

    stats, recent = get_stats()
    if stats is None:
        log("No database found.")
        return

    today = datetime.now().strftime("%B %d, %Y")

    keyword_rows_html = "".join(
        f"<tr><td style='padding:6px 12px;'>{kw}</td><td style='padding:6px 12px;font-weight:bold;'>{cnt}</td></tr>"
        for kw, cnt in stats["by_keyword"]
    )
    keyword_rows_text = "\n".join(f"  {kw}: {cnt}" for kw, cnt in stats["by_keyword"])

    recent_rows_html = "".join(
        f"<tr style='background:{'#f9f9f9' if i%2==0 else '#fff'};'>"
        f"<td style='padding:6px 10px;font-size:12px;'>{found_at}</td>"
        f"<td style='padding:6px 10px;font-size:12px;'>{kw}</td>"
        f"<td style='padding:6px 10px;font-size:12px;'><a href='{url}' style='color:#1a73e8;'>View Post</a></td>"
        f"</tr>"
        for i, (url, kw, found_at) in enumerate(recent)
    ) or "<tr><td colspan='3' style='padding:10px;color:#888;'>No new leads in the last 24 hours.</td></tr>"

    recent_text = "\n".join(f"  [{found_at}] {kw} — {url}" for url, kw, found_at in recent) \
                  or "  No new leads in the last 24 hours."

    html = f"""
    <html><body style="font-family:sans-serif;padding:20px;max-width:600px;">
      <h2 style="color:#2d6a4f;">🌳 Tree Lead Radar — Daily Summary</h2>
      <p style="color:#555;">{today}</p>

      <table style="border-collapse:collapse;width:100%;margin-bottom:24px;background:#f0f7f4;border-radius:8px;">
        <tr>
          <td style="padding:12px 16px;font-size:24px;font-weight:bold;color:#2d6a4f;">{stats['last_24h']}</td>
          <td style="padding:12px 16px;font-size:24px;font-weight:bold;color:#555;">{stats['total_all']}</td>
          <td style="padding:12px 16px;font-size:24px;font-weight:bold;color:#888;">{stats['total_seen']}</td>
        </tr>
        <tr>
          <td style="padding:0 16px 12px;font-size:12px;color:#888;">New (24h)</td>
          <td style="padding:0 16px 12px;font-size:12px;color:#888;">Total Leads</td>
          <td style="padding:0 16px 12px;font-size:12px;color:#888;">Posts Scanned</td>
        </tr>
      </table>

      <h3 style="color:#2d6a4f;">New Leads (Last 24h)</h3>
      <table style="border-collapse:collapse;width:100%;font-size:13px;">
        <tr style="background:#2d6a4f;color:#fff;">
          <th style="padding:8px 10px;text-align:left;">Time</th>
          <th style="padding:8px 10px;text-align:left;">Keyword</th>
          <th style="padding:8px 10px;text-align:left;">Post</th>
        </tr>
        {recent_rows_html}
      </table>

      <h3 style="color:#2d6a4f;margin-top:24px;">All-Time by Keyword</h3>
      <table style="border-collapse:collapse;font-size:13px;">
        <tr style="background:#eee;">
          <th style="padding:6px 12px;text-align:left;">Keyword</th>
          <th style="padding:6px 12px;text-align:left;">Count</th>
        </tr>
        {keyword_rows_html}
      </table>

      <p style="margin-top:24px;color:#aaa;font-size:11px;">Sent by Tree Lead Radar · {today}</p>
    </body></html>
    """

    text = f"""Tree Lead Radar — Daily Summary ({today})

New leads (24h): {stats['last_24h']}
Total leads:     {stats['total_all']}
Posts scanned:   {stats['total_seen']}

--- New Leads ---
{recent_text}

--- All-Time by Keyword ---
{keyword_rows_text}
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌳 Lead Radar Daily Summary — {today}"
    msg["From"]    = SMTP_USER
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, NOTIFY_EMAIL, msg.as_string())
        log(f"✅ Daily summary sent to {NOTIFY_EMAIL}")
    except Exception as e:
        log(f"Failed to send summary email: {e}")

if __name__ == "__main__":
    send_summary()
