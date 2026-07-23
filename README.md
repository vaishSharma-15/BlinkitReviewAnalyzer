# Blinkit Review Discovery Engine

## Phase 01 — Ingest

Collects public Blinkit-related feedback into `data/raw/<source>.jsonl`, one file per
source type, per `docs/PhaseWiseArchitecture.md`.

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in REDDIT_*, YOUTUBE_API_KEY as available
```

### Run a stage (always smoke-test with --limit first)

```bash
python -m src.ingest.play_store --config config.yaml --limit 50
python -m src.ingest.app_store --config config.yaml --limit 50
python -m src.ingest.reddit --config config.yaml --limit 50
python -m src.ingest.youtube --config config.yaml --limit 50
python -m src.ingest.forums --config config.yaml --limit 50
python -m src.ingest.product_reviews --config config.yaml --limit 50
python -m src.ingest.qcomm_discussions --config config.yaml --limit 50
```

Each script is idempotent and resumable: it appends only new ids to its output file
and writes a `data/raw/<source>.manifest.json` run manifest with fetch/write counts.

### Source coverage notes

- `app_store`: Blinkit's iOS numeric app id (960335206) was found via the public
  `itunes.apple.com/search` lookup and is set in `config.yaml`. The `app-store-scraper`
  package turned out to be unmaintained (its endpoint returns non-JSON responses), so
  this source instead calls Apple's public customer-reviews RSS/JSON feed directly.
  That feed hard-caps at 10 pages (~500 most-recent reviews) — that is the full volume
  available from this endpoint, not a partial run.
- `youtube`: no `YOUTUBE_API_KEY` was available. With the user's explicit approval,
  this source uses `yt-dlp` (video search) and `youtube-comment-downloader` (comment
  scraping) instead of the official Data API v3. This is a deliberate substitution
  from the tech stack decided in `docs/ProblemStatement.md` §5 — both tools hit
  YouTube's public pages directly rather than a stable API, so they're more fragile to
  markup/behaviour changes than the official API would be.
- `reddit` / `qcomm_comparison`: **blocked, not substitutable.** `reddit.com/robots.txt`
  is a blanket `Disallow: /` for every user agent, and the public `.../search.json`
  endpoints return a 403 anti-bot challenge even without the robots restriction. Reddit
  content can only be collected through the official OAuth API (`praw` +
  `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`), which requires user-supplied credentials
  not available in this environment.
- `forums`: Quora's `robots.txt` disallows scraping outright. MouthShut's `robots.txt`
  allows generic bots but has an explicit `Disallow: /` for `ClaudeBot` — since this
  pipeline is operated by a Claude agent, that directive is honored rather than routed
  around with a different user-agent string. Both forum sources are therefore blocked
  by design, not by scraper failure. Two substitute Indian consumer-forum candidates
  were checked and also ruled out: `consumercomplaints.in` sits behind a Cloudflare
  bot-challenge before robots.txt is even reached; `voxya.com` has a fully permissive
  `robots.txt` but is a JS-rendered SPA with no discoverable Blinkit-specific content
  endpoint. This source remains at 0 records, documented rather than worked around.
- `product_reviews`: Blinkit PDP reviews are not scrapable without an authenticated
  session, so this source falls back to Amazon India / Nykaa reviews for equivalent
  SKUs and labels those records `meta.vendor` + `meta.is_proxy_source: true` honestly.
  The Amazon fallback currently hits a search-results page rather than a product's
  review tab, so extracted text may be listing/navigation copy rather than genuine
  review text — records are tagged `meta.unverified_extraction: true` and need
  spot-checking (or selector refinement against a real review page) before being
  trusted in a full run.
- No PII is stored: ingest strips username-shaped fields at the point of collection.

## Phase 02 — Normalize

`python -m src.normalize --config config.yaml` unifies all `data/raw/*.jsonl` into
`data/normalized/normalized.jsonl`: drops items under 15 chars, filters spam, dedups
exact + near-duplicates (embedding cosine > 0.95, blocked by source+day), and detects
language (en/hi/hinglish/other) via a deterministic keyword/script heuristic in
`src/lang_detect.py` (no ML model — auditable and reproducible). Funnel counts are
logged to `data/normalized/manifest.json`.

## Phase 03 — Relevance gate

`python -m src.relevance --config config.yaml` classifies each normalized record as
relevant/not to the research theme (shopping habits, category choice, product
discovery, assortment, category trial) using the Gemini LLM, prompt versioned at
`prompts/relevance_batch.md`.

**LLM provider note:** the project spec (`docs/ProblemStatement.md` §5) decided
Anthropic/Claude, but the user didn't have an Anthropic key and asked to use their free
Gemini key instead — approved explicitly in conversation. Model is pinned to
`gemini-3.5-flash-lite` (not a `-latest` alias, for reproducibility); the full
`gemini-3.5-flash` intermittently leaked chain-of-thought text into JSON output even
with `responseMimeType=application/json`, so the lite variant was chosen for reliable
strict-JSON output.

**Free-tier quota, measured empirically, not assumed:** 15 requests/minute, and
separately a **500 requests/day** cap (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`)
that does NOT recover within the `retryDelay` the API suggests (confirmed by a sustained
4-minute test that got only 1 success after the cap was hit) — it's a real once-a-day
reset, not a short burst limiter. `src/llm.py` enforces a 13/min safety margin and
raises `DailyQuotaExhausted` distinctly from ordinary 429s so callers stop cleanly
instead of retrying for hours; the disk cache (`sha256(prompt_version + text)`) means
re-running the same command after reset resumes at no extra cost for completed work.

**Batching, to fit the full corpus in one day's quota:** at 1 item per LLM call, the
~10,030 items that survive pre-filtering would need ~65 days at 500 requests/day.
Instead, `src/relevance.py` and `src/enrich.py` batch multiple items into a single
call (numbered list in, JSON array out, matched by index) — default 25/call for
relevance, 15/call for enrich — cutting total requests to a few hundred, comfortably
inside the daily cap. A batch that fails to parse or validate is retried once, then
recursively split in half; only individual items still failing at the smallest split
are quarantined, so one malformed response can't silently drop a whole batch.

**Keyword pre-filter, to conserve quota further:** `src/relevance.py` applies a cheap
keyword pre-filter (`THEME_KEYWORDS` — category names, product exemplars,
discovery/habit/barrier language, authenticity/defect language) to English text only,
and sends 100% of Hindi/Hinglish/other-language text to the LLM unfiltered. This split
exists because the keyword list is Latin-script and under-matches Devanagari almost
completely (measured: Hindi survived at 6.2% vs English at 31.1% before the split — not
a real signal difference, a blind spot). The English keyword list itself was
iteratively spot-checked against random samples of filtered-out items and expanded to
close real misses (e.g. "fake ghee", "hair fall serum" were initially dropped since no
generic category word matched). No keyword list has perfect recall — items
pre-filtered out are logged in `data/relevant/all_classifications.jsonl` with
`reason: "prefiltered..."` so the tradeoff stays auditable, not hidden.

## Phase 04 — Enrich

`python -m src.enrich --config config.yaml` adds closed-vocabulary structured labels
(categories, behaviour signal, barrier type, segment signals, sentiment, quote-worthy)
to each relevant record, per `prompts/enrich.md`. Every LLM response is validated
against the closed vocabularies in `src/schemas.py`; violations are retried once with a
repair instruction, then quarantined to `data/enriched/failed.jsonl`.

## RAG chatbot

A lightweight Streamlit-based RAG chatbot has been added under the app folder.

### Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/rag_chatbot.py
```

### Notes

- The chatbot uses the markdown files in the docs folder as its knowledge base.
- If an Anthropic API key is present in the environment, the app can generate answers grounded in retrieved context.
- Without an API key, it falls back to a simple retrieval-based response.
