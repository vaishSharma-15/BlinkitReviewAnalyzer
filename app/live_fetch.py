"""Sidebar 'Fetch new reviews' — a live Play Store pull, shown as it happens.

Everything else in the app reads files the pipeline already wrote (app/data.py). This is
the one place the dashboard talks to a source itself: it hits the same Google Play
endpoint src/ingest/play_store.py uses, with the same app id and locale from config.yaml,
and streams what comes back into the sidebar page-by-page rather than after the fact — so
the panel shows the scrape running, not just its result.

Read-only on purpose. Nothing here appends to data/raw/play.jsonl: the corpus counts on
Overview, the funnel manifests and the vector index are all produced by one pipeline run
and have to agree with each other, and a review injected behind their backs would be
counted as scraped while being absent from every downstream stage. Reviews landing here
are labelled 'not yet indexed' for exactly that reason — to index them you re-run the
pipeline (README §01-Ingest onward).

'New' means the id is not already in data/raw/play.jsonl, which is the same dedup key
src/ingest/common.append_records uses, so the count means the same thing in both places.
"""
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from app import ui

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
PLAY_RAW = ROOT / "data" / "raw" / "play.jsonl"

# Small numbers on purpose: this runs inside a page render, blocking the sidebar, so it
# has to finish in a couple of seconds. Enough to show the scrape working, not a re-ingest.
TARGET_NEW = 6
PAGE_SIZE = 25
MAX_PAGES = 4


@st.cache_data(show_spinner=False)
def _play_config() -> dict:
    import yaml

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["play_store"]
    return {"app_id": cfg["app_id"], "country": cfg["country"], "lang": cfg["lang"]}


@st.cache_data(show_spinner=False)
def _existing_ids() -> set:
    """Ids already in the raw Play file. Cached for the session: the file only changes
    when the ingest CLI runs, which cannot happen while this app is serving a page."""
    import json

    ids = set()
    if not PLAY_RAW.exists():
        return ids
    with open(PLAY_RAW, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids


def _fetch(on_step, on_batch) -> dict:
    """Page through newest-first Play reviews until TARGET_NEW unseen ones are found.

    on_step(text) marks progress; on_batch(rows) hands over each page's new reviews as
    soon as they exist, so the sidebar fills in while later pages are still in flight.
    Returns the run summary that gets parked in session state.
    """
    from google_play_scraper import Sort, reviews

    from src.ingest.common import is_probably_spam

    cfg = _play_config()
    on_step(f"Connecting to Google Play · {cfg['app_id']}")
    known = _existing_ids()
    on_step(f"Loaded {ui.fmt_full(len(known))} known review ids")

    found, seen, token = [], 0, None
    for page in range(1, MAX_PAGES + 1):
        on_step(f"Fetching page {page} — newest first")
        result, token = reviews(
            cfg["app_id"], lang=cfg["lang"], country=cfg["country"],
            sort=Sort.NEWEST, count=PAGE_SIZE, continuation_token=token,
        )
        if not result:
            break

        # Counted per entry actually examined, not per entry returned: the loop breaks the
        # moment TARGET_NEW is reached, and claiming the rest of the page was scanned
        # would overstate what the run looked at.
        batch, examined = [], 0
        for entry in result:
            examined += 1
            rid = f"play_{entry['reviewId']}"
            text = (entry.get("content") or "").strip()
            if rid in known or is_probably_spam(text):
                continue
            known.add(rid)
            at = entry.get("at")
            batch.append({
                "id": rid,
                "text": text,
                "rating": entry.get("score"),
                "date": at.replace(tzinfo=timezone.utc).isoformat() if at else "",
                "url": f"https://play.google.com/store/apps/details?"
                       f"id={cfg['app_id']}&reviewId={entry['reviewId']}",
            })
            if len(found) + len(batch) >= TARGET_NEW:
                break

        found.extend(batch)
        seen += examined
        on_step(f"Page {page}: {len(batch)} new of {examined} scanned")
        if batch:
            on_batch(batch)
        if len(found) >= TARGET_NEW or token is None or not getattr(token, "token", None):
            break

    return {"new": found, "scanned": seen, "at": datetime.now().strftime("%H:%M"), "error": None}


# --- rendering -------------------------------------------------------------

def _steps_html(steps, running: bool = True) -> str:
    """The step trace. Only the last step of a run still in flight is left undimmed —
    that is the one the scrape is actually on."""
    last = len(steps) - 1 if running else -1
    rows = "".join(
        f'<div class="lf-step{"" if i == last else " done"}">'
        f'<i></i><span>{ui.esc(text)}</span></div>'
        for i, text in enumerate(steps)
    )
    return f'<div class="lf-log">{rows}</div>'


def _cards_html(rows) -> str:
    if not rows:
        return ""
    cards = []
    for r in rows:
        stars = "★" * int(r["rating"] or 0) + "☆" * (5 - int(r["rating"] or 0))
        date = (r.get("date") or "")[:10]
        text = r["text"][:180] + ("…" if len(r["text"]) > 180 else "")
        cards.append(
            f'<a class="lf-card" href="{ui.esc(r["url"])}" target="_blank" rel="noopener">'
            f'<div class="lf-card-head"><span class="lf-stars">{stars}</span>'
            f'<span class="lf-date">{ui.esc(date)}</span></div>'
            f'<div class="lf-card-text">{ui.esc(text)}</div></a>'
        )
    return f'<div class="lf-feed">{"".join(cards)}</div>'


def _result_html(state) -> str:
    """The settled panel: the run's step trace, the 'done' chip that reports it, then the
    reviews. The trace is kept rather than cleared — a page of newest-first reviews comes
    back in about a second, so a log that only existed during the run would be a flash;
    left on screen it is the record of what the scrape did."""
    log = _steps_html(state.get("steps", []), running=False)
    if state.get("error"):
        return log + f'<div class="lf-chip err">Failed · {ui.esc(state["error"])}</div>'
    n = len(state["new"])
    label = f"{n} new review{'' if n == 1 else 's'}" if n else "no new reviews"
    chip = (f'<div class="lf-chip">Done · {label} · {ui.esc(state["at"])}'
            f'<span class="lf-chip-sub">{state["scanned"]} scanned</span></div>')
    if not n:
        return log + chip
    note = '<div class="lf-note">Live from Play Store · not yet indexed</div>'
    return log + chip + note + _cards_html(state["new"])


def render_panel():
    """Draws under the sidebar's Fetch button: the live log while a run is in flight,
    the run's result on every render after that."""
    if st.session_state.pop("live_fetch_run", False):
        log_slot, feed_slot = st.empty(), st.empty()
        steps, rows = [], []

        def on_step(text):
            steps.append(text)
            log_slot.markdown(_steps_html(steps), unsafe_allow_html=True)

        def on_batch(batch):
            rows.extend(batch)
            feed_slot.markdown(_cards_html(rows), unsafe_allow_html=True)

        try:
            state = _fetch(on_step, on_batch)
        except Exception as exc:  # network, rate limit, scraper API change
            state = {"new": rows, "scanned": 0, "at": datetime.now().strftime("%H:%M"),
                     "error": f"{type(exc).__name__}"}
        state["steps"] = steps
        st.session_state.live_fetch = state
        # Redraw the whole panel from the settled state in this same pass: the log stops
        # animating, the done chip appears, and the cards are re-rendered from one place
        # rather than left as the progressive copy — so what is on screen at the end of a
        # run is identical to what a later rerun will draw from session state.
        log_slot.empty()
        feed_slot.markdown(_result_html(state), unsafe_allow_html=True)
        return

    state = st.session_state.get("live_fetch")
    if state:
        st.markdown(_result_html(state), unsafe_allow_html=True)
