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

Everything is searched across every frame, not just the top-level page. On a *.streamlit.app
host the app runs inside an iframe below Streamlit's own chrome, so page.inner_text("body")
comes back empty and a selector on the page finds nothing — which reads exactly like a
dead app when it is in fact a healthy one.

Exit codes: 0 if the app rendered (or was woken and then rendered), 1 otherwise, so a
broken deploy fails the workflow rather than passing quietly.
"""
import os
import sys
import time

from playwright.sync_api import Error, sync_playwright

URL = os.environ.get("APP_URL", "").strip()
# Streamlit's own wording on the hibernation page. Matched case-insensitively, and kept as
# two separate strings because the copy has changed before and matching either survives it.
SLEEP_MARKERS = ("gone to sleep", "get this app back up")
WAKE_BUTTON = "get this app back up"
# Something only this app renders. Streamlit's shell mounts before the script has run, so
# waiting on the shell alone would pass for an app that boots and then fails.
APP_MARKER = "Insight Engine"
# A cold start rebuilds the environment and can take a while; a warm app is seconds.
WAKE_TIMEOUT = 240
LOAD_TIMEOUT = 120
# Long enough that the session is unambiguously established rather than a connect-and-go.
HOLD_SECONDS = 20


def _frames_text(page) -> str:
    """Visible text across the page and every frame in it, lowercased."""
    out = []
    for frame in page.frames:
        try:
            out.append(frame.inner_text("body") or "")
        except Error:
            continue  # a frame can detach mid-read; it is not the one we want anyway
    return "\n".join(out).lower()


def _find_app(page, timeout: int):
    """The frame that has actually rendered this app, or None if none does in time."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for frame in page.frames:
            try:
                if frame.get_by_text(APP_MARKER, exact=False).count() > 0:
                    return frame
            except Error:
                continue
        page.wait_for_timeout(2_000)
    return None


def main() -> int:
    if not URL:
        print("::error::APP_URL is not set. "
              "Set it with: gh variable set APP_URL --body 'https://<your-app>.streamlit.app'")
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        print(f"Opening {URL}")
        page.goto(URL, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT * 1_000)
        page.wait_for_timeout(8_000)  # let the iframe attach and the front end connect

        if any(marker in _frames_text(page) for marker in SLEEP_MARKERS):
            print("::warning::App was asleep — waking it.")
            for frame in page.frames:
                try:
                    button = frame.get_by_text(WAKE_BUTTON, exact=False)
                    if button.count() > 0:
                        button.first.click()
                        break
                except Error:
                    continue
            timeout = WAKE_TIMEOUT
        else:
            timeout = LOAD_TIMEOUT

        app = _find_app(page, timeout)
        if app is None:
            page.screenshot(path="app.png")
            print(f"::error::App did not render within {timeout}s "
                  f"(no '{APP_MARKER}' in any frame). Screenshot uploaded as an artifact.")
            return 1

        print(f"App is up. Holding the session for {HOLD_SECONDS}s.")
        page.wait_for_timeout(HOLD_SECONDS * 1_000)
        page.screenshot(path="app.png")
        browser.close()

    print("Done — visit registered.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Named rather than swallowed: a failure here means the deployed app did not
        # render, which is worth an email.
        print(f"::error::Could not load the app — {type(exc).__name__}: {exc}")
        sys.exit(1)
