#!/usr/bin/env python3

import asyncio
import json
import os
import random
import sys
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError

SEEN_FILE = "seen_posts.json"
STATE_FILE = "storage_state.json"
SCREENSHOT_DIR = "debug_screens"

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


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r") as f:
        return set(json.load(f))


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


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


async def login_if_needed(context, page):
    if os.path.exists(STATE_FILE):
        log("Using saved login session.")
        return

    log("Login required.")

    email = os.environ.get("FB_EMAIL")
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


async def scan_group(page, group_id, seen):
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
        if link in seen:
            continue

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
                seen.add(link)
                save_seen(seen)
                break

        await post_page.close()
        await asyncio.sleep(random.uniform(2, 4))


async def main():
    seen = load_seen()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=STATE_FILE if os.path.exists(STATE_FILE) else None
        )
        page = await context.new_page()

        await login_if_needed(context, page)

        log("Tree Lead Radar Running...")
        log("=" * 40)

        for group_id in GROUP_IDS:
            await scan_group(page, group_id, seen)
            await asyncio.sleep(random.uniform(5, 8))

        await browser.close()

    log("Scan complete.")


if __name__ == "__main__":
    asyncio.run(main())
