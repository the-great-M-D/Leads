#!/usr/bin/env python3
"""
Search the Tree Lead Radar database.

Usage:
  python search_leads.py                          # Show all leads
  python search_leads.py --keyword "tree removal" # Filter by keyword
  python search_leads.py --date 2026-06-01        # Filter by date (YYYY-MM-DD)
  python search_leads.py --last 10                # Show last N leads
  python search_leads.py --stats                  # Summary stats
"""

import argparse
import os
import sqlite3
from datetime import datetime

DB_FILE = os.environ.get("DB_PATH", "leads.db")

def get_con():
    if not os.path.exists(DB_FILE):
        print(f"No database found at: {DB_FILE}")
        exit(1)
    return sqlite3.connect(DB_FILE)

def fmt_row(row):
    id_, url, keyword, found_at = row
    return f"[{id_}] {found_at}  |  {keyword:<20}  |  {url}"

def search_leads(keyword=None, date=None, last=None):
    con = get_con()
    query = "SELECT id, url, keyword, found_at FROM leads WHERE 1=1"
    params = []

    if keyword:
        query += " AND keyword LIKE ?"
        params.append(f"%{keyword}%")

    if date:
        query += " AND DATE(found_at) = ?"
        params.append(date)

    query += " ORDER BY found_at DESC"

    if last:
        query += " LIMIT ?"
        params.append(last)

    rows = con.execute(query, params).fetchall()
    con.close()

    if not rows:
        print("No leads found.")
        return

    print(f"\n{'ID':<5} {'Found At':<22} {'Keyword':<22} URL")
    print("-" * 90)
    for row in rows:
        print(fmt_row(row))
    print(f"\n{len(rows)} lead(s) found.")

def show_stats():
    con = get_con()

    total_leads   = con.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    total_seen    = con.execute("SELECT COUNT(*) FROM seen_posts").fetchone()[0]
    first_lead    = con.execute("SELECT MIN(found_at) FROM leads").fetchone()[0]
    last_lead     = con.execute("SELECT MAX(found_at) FROM leads").fetchone()[0]

    print("\n📊 Tree Lead Radar — Stats")
    print("=" * 40)
    print(f"  Total leads found : {total_leads}")
    print(f"  Total posts seen  : {total_seen}")
    print(f"  First lead        : {first_lead or 'N/A'}")
    print(f"  Last lead         : {last_lead or 'N/A'}")

    print("\n🔑 Leads by keyword:")
    rows = con.execute(
        "SELECT keyword, COUNT(*) as cnt FROM leads GROUP BY keyword ORDER BY cnt DESC"
    ).fetchall()
    for keyword, cnt in rows:
        print(f"  {keyword:<25} {cnt}")

    con.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search Tree Lead Radar database")
    parser.add_argument("--keyword", "-k", help="Filter by keyword (partial match)")
    parser.add_argument("--date",    "-d", help="Filter by date (YYYY-MM-DD)")
    parser.add_argument("--last",    "-n", type=int, help="Show last N leads")
    parser.add_argument("--stats",   "-s", action="store_true", help="Show summary stats")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        search_leads(keyword=args.keyword, date=args.date, last=args.last)
