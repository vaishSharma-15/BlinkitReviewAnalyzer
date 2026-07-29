"""Sidebar 'Fetch new reviews' — a live pull from both app stores, shown as it happens.

Everything else in the app reads files the pipeline already wrote (app/data.py). This is
the one place the dashboard talks to a source itself: it hits the same two endpoints
src/ingest/play_store.py and src/ingest/app_store.py use — Google Play for the Android
app, Apple's public customer-reviews feed for iOS — with the same app ids and storefront
from config.yaml, and streams what comes back into the sidebar request-by-request rather
than after the fact, so the panel shows the scrape running, not just its result. Those
two are the live sources because they are the only ones that answer instantly without a
key; YouTube needs an API key and quota, and the forum/Reddit sources are blocked or
rate-limited (see the raw manifests' blocked_reason), which is fine for a nightly CLI run
and not for a button someone is waiting on.

Sampled one review per star rating rather than straight newest-first. The newest 100 Play
reviews run about 63% five-star and 78% four-or-five, with a median length of 11
characters — so a pure 'newest' pull is a wall of "good", "best", "nice app", which says
nothing about what users are reporting. Walking the rating buckets (Play exposes
filter_score_with; Apple's feed does not, so its page is bucketed client-side) costs one
request each and returns something worth reading at both ends of the scale.

Read-only on purpose. Nothing here appends to data/raw/: the corpus counts on Overview,
the funnel manifests and the vector index are all produced by one pipeline run and have
to agree with each other, and a review injected behind their backs would be counted as
scraped while being absent from every downstream stage. Reviews landing here are labelled
'not yet indexed' for exactly that reason — to index them you re-run the pipeline
(README §01-Ingest onward).

'New' means the id is not already in data/raw/{play,appstore}.jsonl, which is the same
dedup key src/ingest/common.append_records uses, so the count means the same thing in
both places.
"""
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from app import ui

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
RAW_DIR = ROOT / "data" / "raw"

# Small numbers on purpose: this runs inside a page render, blocking the sidebar, so it
# has to finish in a couple of seconds. Enough to show the scrape working, not a re-ingest.
SCORES = [1, 2, 3, 4, 5]  # one Play request per bucket, worst first
PER_BUCKET = 1
PLAY_PAGE = 30
APPSTORE_TAKE = 3
# Below this a review is a rating with a word attached ("good"), not something a reader
# learns anything from. Only a preference: a bucket with nothing longer still shows its
# newest review rather than going empty and hiding that the rating exists.
MIN_TEXT = 25


@st.cache_data(show_spinner=False)
def _stores_config() -> dict:
    import yaml

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"play": cfg["play_store"], "appstore": cfg["app_store"]}


@st.cache_data(show_spinner=False)
def _existing_ids() -> set:
    """Ids already in the raw Play and App Store files. Cached for the session: those
    files only change when the ingest CLI runs, which cannot happen while this app is
    serving a page."""
    import json

    ids = set()
    for name in ("play", "appstore"):
        path = RAW_DIR / f"{name}.jsonl"
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ids.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return ids


def _pick(candidates, take: int):
    """Prefer reviews with something to read, in the order the source returned them
    (newest first), and only fall back to the short ones to fill the quota."""
    substantial = [c for c in candidates if len(c["text"]) >= MIN_TEXT]
    short = [c for c in candidates if len(c["text"]) < MIN_TEXT]
    return (substantial + short)[:take]


def _fetch_play(cfg, known, on_step, on_batch) -> int:
    """One newest-first request per star rating, so the panel spans ★1 to ★5 rather than
    whatever the last minute happened to be. Returns how many reviews were examined."""
    from google_play_scraper import Sort, reviews

    from src.ingest.common import is_probably_spam

    on_step("Reading Google Play reviews")
    seen = 0
    for score in SCORES:
        result, _ = reviews(
            cfg["app_id"], lang=cfg["lang"], country=cfg["country"],
            sort=Sort.NEWEST, count=PLAY_PAGE, filter_score_with=score,
        )
        seen += len(result)
        candidates = []
        for entry in result:
            rid = f"play_{entry['reviewId']}"
            text = (entry.get("content") or "").strip()
            if rid in known or is_probably_spam(text):
                continue
            at = entry.get("at")
            candidates.append({
                "id": rid, "source": "play", "text": text,
                "rating": entry.get("score"),
                "date": at.replace(tzinfo=timezone.utc).isoformat() if at else "",
                "url": f"https://play.google.com/store/apps/details?"
                       f"id={cfg['app_id']}&reviewId={entry['reviewId']}",
            })
        batch = _pick(candidates, PER_BUCKET)
        known.update(c["id"] for c in batch)
        on_step(f"Play Store {score}★ — {len(batch)} new")
        if batch:
            on_batch(batch)
    return seen


def _fetch_appstore(cfg, known, on_step, on_batch) -> int:
    """Apple's public customer-reviews feed, newest page. It has no per-rating filter, so
    the page is bucketed here: one review from the lowest rating present, one from the
    highest, then whatever else fills APPSTORE_TAKE."""
    import httpx

    from src.ingest.common import is_probably_spam

    country, app_id = cfg["country"], cfg["app_id"]
    on_step("Reading App Store reviews")
    url = (f"https://itunes.apple.com/{country}/rss/customerreviews/"
           f"id={app_id}/sortBy=mostRecent/page=1/json")
    with httpx.Client(timeout=15.0) as client:
        response = client.get(url)
        response.raise_for_status()
        entries = [e for e in response.json()["feed"].get("entry", []) if "im:rating" in e]

    candidates = []
    for entry in entries:
        rid = f"appstore_{entry['id']['label']}"
        text = (entry.get("content", {}).get("label") or "").strip()
        if rid in known or is_probably_spam(text):
            continue
        published = datetime.fromisoformat(entry["updated"]["label"])
        candidates.append({
            "id": rid, "source": "appstore", "text": text,
            "rating": int(entry["im:rating"]["label"]),
            "date": published.isoformat(),
            "url": f"https://apps.apple.com/{country}/app/blinkit/id{app_id}",
        })

    batch = []
    if candidates:
        ratings = [c["rating"] for c in candidates]
        # Lowest and highest rating on the page first, then newest-first for the rest, so
        # a page that is mostly five-star still yields its complaint.
        preferred = (_pick([c for c in candidates if c["rating"] == min(ratings)], 1)
                     + _pick([c for c in candidates if c["rating"] == max(ratings)], 1)
                     + _pick(candidates, APPSTORE_TAKE))
        for row in preferred:
            if row["id"] not in known and len(batch) < APPSTORE_TAKE:
                known.add(row["id"])
                batch.append(row)
    on_step(f"App Store — {len(batch)} new")
    if batch:
        on_batch(batch)
    return len(entries)


def _fetch(on_step, on_batch) -> dict:
    """Walk both stores, handing each source's finds to the sidebar as they land.

    on_step(text) marks progress; on_batch(rows) hands over reviews as soon as they exist,
    so the panel fills in while the remaining requests are still in flight. Returns the
    run summary that gets parked in session state.

    A failure in one store is reported as a step and does not abort the other — losing
    Apple's feed to a timeout is not a reason to show nothing from Google.
    """
    cfg = _stores_config()
    known = _existing_ids()
    on_step(f"You already have {ui.fmt_full(len(known))} reviews")

    found, seen = [], 0

    def collect(batch):
        found.extend(batch)
        on_batch(batch)

    for name, fn, store_cfg in (("Play Store", _fetch_play, cfg["play"]),
                                ("App Store", _fetch_appstore, cfg["appstore"])):
        try:
            seen += fn(store_cfg, known, on_step, collect)
        except Exception as exc:
            on_step(f"{name} did not respond")

    # Newest first across both stores, so the panel reads as one feed rather than two
    # concatenated blocks.
    found.sort(key=lambda r: r["date"], reverse=True)
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
        # Same source names the rest of the app uses, so a card here and an evidence
        # card in the chat name the same source the same way.
        name = ui.SOURCE_META.get(r.get("source", ""), ("", ""))[0]
        cards.append(
            f'<a class="lf-card" href="{ui.esc(r["url"])}" target="_blank" rel="noopener">'
            f'<div class="lf-card-head"><span class="lf-stars">{stars}</span>'
            f'<span class="lf-date">{ui.esc(name)} · {ui.esc(date)}</span></div>'
            f'<div class="lf-card-text">{ui.esc(text)}</div></a>'
        )
    return f'<div class="lf-feed">{"".join(cards)}</div>'


def _result_html(state) -> str:
    """The settled panel: the done chip, the reviews, and the step trace folded away
    underneath.

    The trace is kept rather than dropped — the whole fetch takes under two seconds, so a
    log that only existed during the run would be a flash — but it is the record of a
    finished job, not the point of the panel, so it collapses into a one-line disclosure
    and the reviews get the space.
    """
    log = (f'<details class="lf-details"><summary>What it did</summary>'
           f'{_steps_html(state.get("steps", []), running=False)}'
           f'<div class="lf-scanned">{state["scanned"]} reviews checked</div></details>')
    if state.get("error"):
        return f'<div class="lf-chip err">Couldn\'t fetch · {ui.esc(state["error"])}</div>' + log
    n = len(state["new"])
    label = f"{n} new review{'' if n == 1 else 's'}" if n else "no new reviews"
    chip = (f'<div class="lf-chip">Done · {label}'
            f'<span class="lf-chip-sub">{ui.esc(state["at"])}</span></div>')
    if not n:
        return chip + log
    note = '<div class="lf-note">One per star rating · not saved to the corpus</div>'
    return chip + note + _cards_html(state["new"]) + log


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
