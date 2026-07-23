# Blinkit Review Discovery Engine

## Executive summary

This project builds an AI-powered research pipeline that turns public Blinkit-related user feedback into validated insights about why users stay within a small set of familiar shopping categories. The system ingests reviews, social conversations, forums, and product-review signals, normalizes them into a common schema, filters for relevance, enriches each item with structured labels, clusters themes, and produces evidence-backed answers to eight research questions.

The work is intentionally an insight-generation exercise, not a product feature build. The final deliverables are a reproducible offline pipeline, a publicly deployed query app, and a scorecard that proves the themes are trustworthy.

You are building **Part 1** of a Product Manager fellowship graduation project.
This file is the source of truth. Read it fully before writing code.

---

## 1. The problem

Blinkit has succeeded at becoming a habit. Millions of urban Indians order from it every week
without thinking about it. That habit is also the ceiling.

Most users buy the same 2–3 categories over and over — groceries, snacks and beverages, household
essentials — and almost never touch the rest of the catalogue. Blinkit already stocks pet supplies,
baby care, beauty and personal care, electronics accessories, toys, home and kitchen, and gifting.
Users simply don't go there.

The company wants to increase the share of Monthly Active Customers who buy from at least one new
category each month. But there is a prior problem blocking that:

> **We don't actually know why users stay inside their familiar categories.**

Everything believed about it today is internal opinion and anecdote. Is it trust? Price? Not
knowing the products exist? Not thinking of Blinkit for those needs? A bad past experience? Each
points to a completely different solution, and we can't currently tell which is true.

The evidence exists — tens of thousands of app reviews, Reddit threads, forum posts, product
reviews and social conversations where users explain their behaviour in their own words. Nobody can
read all of it manually.

---

## 2. What we are building

An **AI-powered discovery engine** that ingests public, unstructured user feedback about
**Blinkit** at scale and outputs a ranked, evidence-linked set of themes explaining why users
stay locked inside 2–3 familiar shopping categories.

The final artefact is:
1. A reproducible offline pipeline (scripts + committed data).
2. A **publicly deployed query app** where a reviewer can ask a question and get a grounded,
   cited answer.
3. An **Insight Quality Scorecard** proving the insights are trustworthy.

**This is a research/insight deliverable, not a product feature.** Do NOT design solutions,
features, or recommendations anywhere in this codebase. Part 1 ends at validated insight. The
themes produced here become the hypotheses tested in user interviews in Part 2 — only after that
does anything get built.

---

## 3. Business context (needed for prompt-writing and theme relevance)

Blinkit is India's quick-commerce leader (~45–50% market share, owned by Eternal Ltd, ex-Zomato).
Quick commerce is now a weekly habit for millions of urban Indians. That habit is also the ceiling:
users converge on a narrow repeated basket — groceries, snacks & beverages, household essentials —
and rarely cross into adjacent categories Blinkit already stocks (pet supplies, baby care, personal
care & beauty, electronics accessories, toys & stationery, home & kitchen, gifting, festival goods).

**Strategic goal being served:** increase the % of Monthly Active Customers who purchase from at
least one *new-to-them* category in a given month.

**North-star metric:**
`Category Exploration Rate (CER) = MACs purchasing ≥1 new-to-user category in month M / total MACs in month M`

Why it matters commercially: Blinkit chases premium AOV (~₹709 forecast 2026 vs Instamart's ~₹619).
Cross-category basket expansion is the mechanism behind that AOV strategy, so this work sits on a
stated company priority.

---

## 4. The eight research questions (REQUIRED OUTPUT SLOTS)

Every one of these must be answered by at least one theme with cited evidence. If the corpus
cannot answer one, say so explicitly rather than fabricating a theme.

- **Q1** Why do users repeatedly buy from the same categories?
- **Q2** What prevents users from exploring new categories?
- **Q3** How do users discover products on the platform today?
- **Q4** What role do habits/routines/reorder behaviour play?
- **Q5** What information does a user need before trying a new category for the first time?
- **Q6** What frustrations emerge repeatedly?
- **Q7** Which user segments are more likely to experiment?
- **Q8** What unmet needs emerge consistently across independent sources?

---

## 5. Tech stack (decided — do not substitute without asking)

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Env | `uv` or `venv` + `requirements.txt` | pin versions |
| Play Store ingest | `google-play-scraper` | primary volume source |
| App Store ingest | `app-store-scraper` | lower volume |
| Reddit ingest | `praw` (read-only) | needs free API creds via `.env` |
| YouTube comments | `google-api-python-client` (YouTube Data API v3) | free quota; social + product-review signal |
| Forums / Quora / MouthShut | `httpx` + `selectolax`, polite rate limits | respect robots.txt |
| Product reviews | Blinkit PDP reviews via `httpx`; fall back to Amazon/Nykaa India reviews for the same SKUs if blocked | category-level quality signal |
| LLM | Anthropic Messages API, `claude-sonnet-4-6` | use the **Batches API** for enrichment |
| Embeddings | `sentence-transformers`, `BAAI/bge-small-en-v1.5` | local, free |
| Dim. reduction | `umap-learn` | before clustering only |
| Clustering | `hdbscan` | no fixed k; keep the noise bucket |
| Vector store | `lancedb` | file-based, lives in repo |
| App | `streamlit` | deploy to Streamlit Community Cloud from GitHub |
| Data format | JSONL at every stage | one record per line, never overwrite upstream stages |

**Do NOT use:** LangChain, LlamaIndex, n8n, Zapier, or any managed vector DB. Direct SDK calls only.

---

## 6. Repo structure

```
blinkit-discovery/
├── BlinkitReviewDiscoveryEngine.md   # this spec — source of truth
├── README.md                  # setup + how to reproduce, written last
├── requirements.txt
├── .env.example               # ANTHROPIC_API_KEY, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
├── config.yaml                # sources, date window, model names, thresholds
├── data/
│   ├── raw/                   # 01 output, one JSONL per source
│   ├── normalized/            # 02 output
│   ├── enriched/              # 04 output
│   ├── themes/                # 06 output
│   ├── gold/                  # hand-labelled 100-item eval set
│   └── cache/                 # LLM response cache keyed by content hash
├── src/
│   ├── ingest/
│   │   ├── play_store.py
│   │   ├── app_store.py
│   │   ├── reddit.py
│   │   ├── youtube.py         # social media conversations
│   │   ├── forums.py          # Quora, MouthShut, community forums
│   │   ├── product_reviews.py # PDP-level reviews, category quality signal
│   │   └── qcomm_discussions.py # Blinkit vs Zepto vs Instamart comparison threads
│   ├── normalize.py           # stage 02
│   ├── relevance.py           # stage 03
│   ├── enrich.py              # stage 04
│   ├── cluster.py             # stage 05
│   ├── synthesize.py          # stage 06
│   ├── validate.py            # stage 07
│   ├── index.py               # build LanceDB index for RAG
│   ├── llm.py                 # Anthropic client, batching, caching, retries
│   └── schemas.py             # pydantic models for every record type
├── prompts/                   # every prompt as a versioned .md file, never inline
│   ├── relevance.md
│   ├── enrich.md
│   ├── cluster_name.md
│   ├── synthesize.md
│   └── rag_answer.md
├── app/
│   └── streamlit_app.py
├── tests/
└── reports/
    └── scorecard.md           # generated by validate.py
```

---

## 7. Pipeline stages

Each stage is a standalone CLI script: reads from the previous stage's directory, writes to its
own, and is safely re-runnable. Never mutate an upstream file.

### 01 — Ingest
- Play Store: app id `com.grofers.customerapp`. Pull newest reviews across sorts/scores to
  maximise coverage. Target **≥ 3,000 raw** before filtering.
- App Store: Blinkit iOS reviews, India storefront.
- Reddit: search + subreddit sweeps on `r/india`, `r/bangalore`, `r/mumbai`, `r/delhi`,
  `r/hyderabad`, `r/pune`, `r/IndianFood`, `r/personalfinanceindia`, `r/dogs`/`r/IndianPets`
  (pet-category signal), `r/BeautyBoardIndia` (personal-care signal). Pull post **and comments**
  — the comments carry the reasoning.
- YouTube (social media conversations): comments on Blinkit ads, quick-commerce explainer/review
  videos, "Blinkit vs Zepto" comparison videos, unboxing and haul videos. Use YouTube Data API v3
  (free quota). Comment threads on haul videos are unusually rich on *why someone tried a category*.
- Forums / community (Quora, MouthShut, Indian consumer forums): search for Blinkit + category
  terms. Quora answers and MouthShut reviews are long-form and reason-heavy — high insight density
  per item even though volume is low. Fetch with `httpx`, parse with `selectolax`, respect
  robots.txt, rate-limit to ~1 req/sec.
- Product reviews (category quality signal): PDP-level reviews for a sample of SKUs across the
  *non-core* categories (pet, baby, beauty, electronics accessories). This is the source that tells
  us whether trust barriers are category-specific. If Blinkit PDPs are not scrapable, fall back to
  Amazon India / Nykaa reviews for equivalent SKUs and **label the source honestly** as a proxy.
- Quick-commerce discussions: treat as a targeted slice, not a separate site — comparison and
  "which app do you use for what" threads across Reddit, YouTube and forums. These directly expose
  *category-to-platform mental models* ("Blinkit for groceries, Nykaa for makeup"), which is the
  single most important signal for this project. Tag these items `qcomm_comparison` at ingest.
- Keep: `id, source, url, date, text, rating, subreddit/app_version/video_id, score/upvotes`.
- **Strip usernames at ingest.** No PII in any stored file.
- Window: last 24 months. Public content only. No scraping behind login.
- **Source coverage is a graded requirement.** All seven source types must be represented in
  `data/raw/` with non-zero counts. If a source proves genuinely unscrapable, document the attempt,
  the blocker, and the substitute used in `README.md` — do not silently drop it.

### 02 — Normalize
- Unify to a single schema (see §7).
- Language detect; keep `en`, `hi`, `hinglish`. Flag but don't drop transliterated Hindi.
- Drop items under 15 characters.
- Exact dedup on normalized text; near-dup via embedding cosine > 0.95.
- Basic spam/bot filter (repeated promo strings, referral-code spam, pure emoji).
- Log counts in/out at every filter step — the funnel goes on the scorecard.

### 03 — Relevance gate
- LLM binary classifier: does this item say anything about **shopping behaviour, category choice,
  product discovery, assortment, or trial of something new**?
- Drop pure delivery/refund/app-crash rants **unless** they encode a category-level barrier
  (e.g. "never order fruit from here, always bruised" → quality-trust barrier, keep).
- Target ≥ 1,500 relevant items post-gate. If short, widen ingest, don't loosen the gate.

### 04 — Enrich
- One structured call per item producing the enrichment record in §7.
- Prompt must demand JSON only, no prose, no markdown fences. Parse defensively; on parse
  failure retry once with a repair prompt, then quarantine to `data/enriched/failed.jsonl`.
- Use the Batches API. Cache on `sha256(prompt_version + text)` so prompt tweaks don't force a
  full re-spend.
- Labels must be drawn from the **closed vocabularies** in §8. No free-text label invention.

### 05 — Cluster
- Embed `text` with bge-small-en-v1.5.
- UMAP to ~10 dims, then HDBSCAN (`min_cluster_size` ≈ 15, tune and record the value).
- Keep the noise cluster and report its size — a large noise bucket is a finding, not a failure.
- One LLM call per cluster: produce a name, a one-line description, and the 5 most representative
  verbatim quotes (each **under 15 words**).

### 06 — Synthesize
- Map clusters → the eight research questions. One cluster may serve several.
- Merge near-duplicate clusters into themes.
- Rank by `prevalence × severity × strategic_relevance`. Define and document each factor.
- Every theme carries: prevalence %, n, sources covered, confidence, evidence with resolvable
  URLs, a `so_what` line, and any contradicting evidence found.
- **Hard rule: no claim without a traceable item ID.** If it isn't in the corpus, it isn't a theme.

### 07 — Validate (the differentiator — do not shortcut)
Generate `reports/scorecard.md` with:
1. **Gold set.** 100 randomly sampled items hand-labelled by the user for relevance + barrier
   type. Build `data/gold/` with a CLI labelling helper. Report precision/recall/F1 for the
   relevance gate and the barrier classifier. Target ≥ 0.80 F1 on relevance.
2. **Inter-run stability.** Re-run clustering on a 90% bootstrap sample with a different seed;
   report theme overlap %.
3. **Cross-source triangulation.** A theme is `high` confidence only if it appears in ≥ 2
   independent sources. Single-source themes flagged explicitly.
4. **Citation audit.** Sample 20 evidence quotes; verify each appears verbatim in the stored
   source item and the URL resolves. Report error rate.
5. **Counter-evidence search.** For each theme, actively query the corpus for disconfirming
   items and record what was found. A theme with no counter-search is not validated.
6. **Recency split.** Compare themes from the older 12 months vs the newer 12 months, to catch
   stale complaints Blinkit has already fixed.
7. **Ingest funnel table.** Raw → deduped → relevant → enriched, with counts at each step.
8. **Source coverage table.** Item counts per source type, all seven rows present, plus any
   substitutions and why. Themes should also be checked for source bias — if a theme comes 95%
   from Play Store reviews, flag it, because app-store reviewers skew toward the angry.

### 08 — Index + Serve
- Build LanceDB index over enriched items (text + metadata filters).
- Streamlit app with three tabs:
  - **Ask** — question box, retrieval over the corpus, Claude answers *only* from retrieved
    evidence, every claim rendered with a clickable source link. If evidence is insufficient,
    the app must say so rather than answer from model priors.
  - **Themes** — ranked theme table, filterable by research question, source, confidence.
  - **Scorecard** — the validation numbers, rendered on screen.
- **Landing view is the Scorecard.** A grader opening the link should see measured accuracy first.
- No live scraping in the deployed app. Frozen corpus, with the freeze date shown in the UI.

---

## 8. Schemas (pydantic in `src/schemas.py`)

**Closed vocabularies**

```python
CATEGORIES = ["grocery_staples", "fruits_vegetables", "dairy_bakery", "snacks_beverages",
              "household_essentials", "personal_care_beauty", "baby_care", "pet_supplies",
              "electronics_accessories", "home_kitchen", "toys_stationery", "gifting_festival",
              "pharmacy_wellness", "other"]

BEHAVIOUR_SIGNAL = ["habit_reorder", "discovery", "barrier", "trial", "abandonment",
                    "substitution", "comparison_other_platform", "none"]

BARRIER_TYPE = ["trust_quality", "price_premium", "assortment_doubt", "findability",
                "no_trigger", "returns_risk", "brand_absence", "expiry_freshness",
                "prefer_specialist_store", "none"]
```

**Normalized record**

```json
{"id":"str","source":"play|appstore|reddit|youtube|forum|product_review|qcomm_comparison",
 "url":"str","date":"ISO-8601",
 "text":"str","rating":"int|null","lang":"en|hi|hinglish|other","meta":{}}
```

**Enriched record**

```json
{"id":"str","source":"str","url":"str","date":"ISO-8601","text":"str","lang":"str",
 "rating":"int|null","relevant":true,"relevance_reason":"str",
 "categories_mentioned":["personal_care_beauty"],
 "behaviour_signal":"barrier","barrier_type":"trust_quality",
 "segment_signals":{"family_stage":"parent_young_child|single|couple|unknown",
                    "city_tier":"metro|tier2|unknown",
                    "price_sensitivity":"high|low|unknown",
                    "has_pet":"yes|no|unknown"},
 "sentiment":-0.7,"quote_worthy":true,"prompt_version":"v3"}
```

**Theme record**

```json
{"theme_id":"T-07","title":"str","research_questions":["Q2","Q5"],
 "prevalence_pct":12.4,"n_items":186,"sources_covered":["play","reddit"],
 "severity":"high|medium|low","strategic_relevance":"high|medium|low",
 "rank_score":0.0,"so_what":"str","confidence":"high|medium|low",
 "evidence":[{"id":"str","url":"str","quote":"under 15 words","source":"str"}],
 "contradicting_evidence":[{"id":"str","url":"str","note":"str"}],
 "segments_overrepresented":["parent_young_child"]}
```

---

## 9. Engineering conventions

- Every stage: `python -m src.<stage> --config config.yaml [--limit N]`. `--limit` for cheap
  smoke tests before full runs.
- Idempotent and resumable. Crash on item 1,400 of 1,500 must not cost the first 1,399.
- Log to stdout with counts and timings; write a run manifest (config hash, model, prompt
  versions, item counts) to each output dir.
- Prompts live in `prompts/*.md` with a version string. Never inline a prompt in Python.
- All thresholds in `config.yaml`, never hard-coded.
- Type hints throughout; pydantic validates every record crossing a stage boundary.
- `pytest` for schema validation, dedup logic, and metric computation. Not for LLM output.
- Cost discipline: always run `--limit 50` first and report estimated full-run cost before
  a full enrichment pass.
- Secrets via `.env` only. `.env` in `.gitignore`. Never log a key.

---

## 10. Hard constraints

- **No fabricated data.** Never generate synthetic reviews, never invent a quote, never fill a
  gap with plausible-sounding evidence. An empty result is a valid, reportable result.
- **Every quote under 15 words**, one quote per source item, verbatim, with a resolving URL.
- **No PII** anywhere in `data/`. Usernames stripped at ingest.
- **No solutioning.** No feature ideas, no recommendations, no roadmaps in this repo.
- Public data only. Respect robots/ToS. No login-walled scraping.

---

## 11. Definition of done

1. `python -m src.ingest.play_store` through `python -m src.validate` runs clean end-to-end from
   a fresh clone plus `.env`.
2. ≥ 1,500 relevant enriched items in `data/enriched/`, with **all seven source types present**
   and non-zero.
3. All eight research questions answered with cited themes, or explicitly marked unanswerable.
4. `reports/scorecard.md` populated with real measured numbers — relevance F1 ≥ 0.80, citation
   error rate reported, theme stability reported.
5. Streamlit app live on a public URL, scorecard as the landing view, every answer cited.
6. `README.md` documents setup, reproduction steps, corpus freeze date, and known limitations.

---

## 12. How to work with me

- Work stage by stage. Build 01, show me the output, then move to 02. Don't scaffold all eight
  stages before any of them runs.
- Before any full LLM pass, run `--limit 50`, show me the outputs, and state the projected cost.
- Ask before adding a dependency not listed in §5.
- If the data contradicts an assumption in this file, say so and stop. Don't work around it.
- If a research question has no support in the corpus, report that plainly. That's a finding.
