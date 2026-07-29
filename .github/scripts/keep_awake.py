"""Open the deployed Streamlit app in a real browser so Community Cloud counts it as a
visitor, and wake it if it has already gone to sleep.

Why a browser and not curl: Streamlit's inactivity timer tracks app *sessions* — a client
opening a websocket to the server — not HTTP hits on the URL. A curl fetches the static
HTML shell and never opens that socket, so it can return a cheerful 200 while the sleep
clock keeps running. Chromium loads the page, the front end connects, and the visit
registers the way a human's would.

A sleeping app serves a placeholder page with a "get this app back up" button rather than
an error, so this clicks it and waits for the rebuild. That is the part a ping cannot do
at all: it can detect sleep but never fix it.

Exit codes: 0 if the app rendered (or was woken and then rendered), 1 otherwise, so a
broken deploy fails the workflow rather than passing quietly.
"""
import os
import sys

from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "").strip()
# Streamlit's own wording on the hibernation page. Matched case-insensitively, and kept as
# two separate strings because the copy has changed before and matching either survives it.
SLEEP_MARKERS = ("gone to sleep", "get this app back up")
WAKE_BUTTON = "get this app back up"
# A cold start rebuilds the environment and can take a while; the app itself is fast.
WAKE_TIMEOUT_MS = 180_000
LOAD_TIMEOUT_MS = 90_000
# Long enough that the session is unambiguously established rather than a connect-and-go.
HOLD_SECONDS = 20


def main() -> int:
    if not URL:
        print("::error::APP_URL is not set. "
              "Set it with: gh variable set APP_URL --body 'https://<your-app>.streamlit.app'")
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        print(f"Opening {URL}")
        page.goto(URL, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT_MS)
        page.wait_for_timeout(5_000)

        body = (page.inner_text("body") or "").lower()
        if any(marker in body for marker in SLEEP_MARKERS):
            print("::warning::App was asleep — waking it.")
            button = page.get_by_role("button", name=WAKE_BUTTON, exact=False)
            if button.count() == 0:
                button = page.get_by_text(WAKE_BUTTON, exact=False)
            button.first.click()
            # The rebuild replaces the placeholder page; wait for the app shell to exist.
            page.wait_for_selector('[data-testid="stApp"]', timeout=WAKE_TIMEOUT_MS)

        # The shell mounts before the script has run, so wait for something this app
        # actually renders — the sidebar nav — not just Streamlit's chrome.
        page.wait_for_selector('[data-testid="stSidebar"]', timeout=LOAD_TIMEOUT_MS)
        page.wait_for_selector("text=Insight Engine", timeout=LOAD_TIMEOUT_MS)

        print(f"App is up. Holding the session for {HOLD_SECONDS}s.")
        page.wait_for_timeout(HOLD_SECONDS * 1_000)
        page.screenshot(path="app.png", full_page=False)
        browser.close()

    print("Done — visit registered.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Named rather than swallowed: a timeout here means the deployed app did not
        # render, which is worth an email.
        print(f"::error::Could not load the app — {type(exc).__name__}: {exc}")
        sys.exit(1)
