# Methodology

How the Blinkit Review Discovery Engine gathers data, identifies themes, generates
insights, and checks whether those insights are trustworthy.

Every number in this document is read from the pipeline's own manifests and outputs, not
estimated. Where a figure is stale or a check is incomplete, that is stated rather than
smoothed over.

---

## 1. How the workflow gathers and analyzes data

The pipeline is seven numbered phases, each writing to disk so any stage can be rerun,
audited, or resumed independently.

```
ingest → normalize → relevance gate → enrich → cluster (check) → synthesize → validate
                                                                                  ↓
                                                                     index → RAG chatbot
```

### 1.1 Ingest (Phase 01)

Seven source types are configured in `config.yaml`, each with its own collector under
`src/ingest/`:

| Source | What it covers | Status |
|---|---|---|
| Play Store | `com.grofers.customerapp`, IN/en | Primary volume |
| App Store | app id 960335206, IN | Hard-capped by Apple's public RSS at ~500 most recent |
| YouTube | 10 search terms (hauls, comparisons, reviews) | Collected via `yt-dlp` + comment downloader |
| Q-comm comparison | Targeted Blinkit-vs-Zepto/Instamart slice | Tagged at ingest |
| Product reviews | Category SKUs (pet, baby care, …) | Amazon/Nykaa proxy SKUs |
| Reddit | 11 subreddits, 2 search terms | **Blocked** |
| Forums | Quora, MouthShut | **Blocked** |

Two sources yielded zero records, and this is a real limitation rather than a
configuration bug:

- **Reddit** — `robots.txt` disallows all agents, and `search.json` returns 403 without
  OAuth credentials unavailable in this environment.
- **Forums** — Quora disallows scraping; MouthShut explicitly disallows the crawler. Two
  substitute forums were checked and also ruled out.

Two substitutions were made and are labelled in the data rather than hidden: YouTube uses
`yt-dlp` instead of the official Data API (no API key available — more fragile, so
flagged), and Blinkit product-detail reviews require an authenticated session, so
Amazon/Nykaa SKUs stand in, marked `meta.is_proxy_source = true`.

### 1.2 Normalize (Phase 02)

`src/normalize.py` unifies every raw file into one record shape and applies, in order:

1. **Length filter** — drops anything under 15 characters.
2. **Spam filter.**
3. **Exact dedup**, then **near-dedup** — embedding cosine similarity > 0.95, blocked by
   source + day to keep the comparison tractable.
4. **Language detection** — en / hi / hinglish / other, using a deterministic
   keyword-and-script heuristic in `src/lang_detect.py`. No ML model, deliberately: this
   keeps the step auditable and reproducible.

### 1.3 Relevance gate (Phase 03)

Each normalized record is classified relevant / not relevant to the research subject
(shopping habits, category choice, discovery, assortment, category trial) by an LLM, using
the versioned prompt at `prompts/relevance_batch.md`.

Two engineering constraints shaped this stage:

**Quota.** The free Gemini tier allows 15 requests/minute and 500 requests/day, measured
empirically rather than assumed — the daily cap is a genuine once-a-day reset, confirmed
by a sustained four-minute test that produced one success after the cap was hit. At one
item per call, the surviving corpus would take roughly 65 days. So calls are **batched**
(numbered list in, JSON array out, matched by index): 40 items per relevance call, 15 per
enrich call. A batch that fails to parse is retried once, then split recursively in half,
so a single malformed response can't drop a whole batch — only individual items that still
fail at the smallest split are quarantined. Results are cached on disk under
`sha256(prompt_version + text)`, so reruns resume free of charge.

**A keyword pre-filter** conserves quota further, but is applied to **English text only**.
Hindi and Hinglish go to the LLM unfiltered, because the Latin-script keyword list
under-matched Devanagari almost completely — measured at 6.2% survival for Hindi versus
31.1% for English, which was a blind spot, not a real signal difference. Pre-filtered items
are logged to `data/relevant/all_classifications.jsonl` with a `prefiltered...` reason, so
the tradeoff stays inspectable.

### 1.4 The funnel, as it currently stands

| Stage | Count | Share of raw |
|---|---|---|
| Raw collected | 41,176 | 100% |
| After length + spam + dedup | 26,569 | 65% |
| Sent to the relevance LLM | 11,172 | 27% |
| Judged relevant | **4,110** | 10% |
| Enriched (0 failed) | **4,110** | 10% |
| Assigned a theme | **3,548** | 9% |

The analyzed corpus spans **2024-09-05 to 2026-07-23** and breaks down as: Play Store
3,662 · YouTube 252 · Q-comm threads 121 · App Store 57 · product reviews 18. A barrier
type was identified in 2,912 of the 4,110 records.

**This 10% survival rate is the point, not a loss.** The corpus is deliberately narrowed to
reviews that speak to category discovery and barriers. It is therefore *not* a
representative sample of Blinkit sentiment, and figures drawn from it (such as the 60%
negative / 29% positive split) describe this research-relevant subset only — not customer
satisfaction overall.

### 1.5 Enrich (Phase 04)

Each relevant record receives closed-vocabulary structured labels in a single LLM call:
category, behaviour signal, barrier type, segment signals (family stage, city tier, price
sensitivity, pet ownership), sentiment (−1 to +1), quote-worthiness, and a primary
`theme_id`. Every response is validated against the vocabularies in `src/schemas.py`;
violations are retried once with a repair instruction, then quarantined to
`data/enriched/failed.jsonl`. On the current run, **0 records failed**.

---

## 2. How themes are identified

**Themes are assigned by supervised classification against a fixed taxonomy — not
discovered by clustering.** This is the most consequential methodological decision in the
project, and it was made after the alternative was tried and measured.

### 2.1 Why not clustering

An unsupervised approach was built first: embeddings → PCA → HDBSCAN, no fixed categories.
On this corpus it produced **only 3 clusters, with 66% of records falling into the noise
bucket** — far too coarse to answer the eight research questions. Supervised classification
against a hand-designed taxonomy leaves only ~14% unclassified.

### 2.2 The taxonomy

Nine themes, hand-designed against the research questions in `docs/ProblemStatement.md` §4.
Each record gets exactly one, or `unclassified` if none fit — assigned in the same LLM call
as the other enrichment labels, at no extra quota cost.

| Theme | Records | Share of themed |
|---|---|---|
| Category-Specific Distrust | 1,463 | 41.2% |
| Habit & Reorder | 469 | 13.2% |
| Assortment Gaps | 440 | 12.4% |
| Price & Value | 419 | 11.8% |
| Cross-Platform Comparison | 382 | 10.8% |
| First-Trial Stories | 148 | 4.2% |
| Discovery Mechanics | 104 | 2.9% |
| Platform Mental Model | 87 | 2.5% |
| Life-Event Triggers | 36 | 1.0% |
| *(unclassified)* | *562* | — |

### 2.3 Clustering still runs — as a check, not a source of themes

`src/cluster.py` runs the original embedding + PCA + HDBSCAN pipeline, but **only over the
`unclassified` leftovers**, asking one question: is there a coherent tenth theme the fixed
taxonomy is missing? On the current corpus the unclassified subset clusters into groups
matching the spec's own definition of noise — generic refund complaints naming no product,
generic delivery-speed praise — so no taxonomy change was warranted. A large, coherent
cluster appearing here would be a signal to add a tenth theme, not a theme in itself.

`unclassified` is reported as its own row throughout, never merged into a theme and never
silently dropped.

---

## 3. How insights are generated

There are two paths, and they deliberately share one vocabulary.

### 3.1 Offline synthesis (Phase 06)

`src/synthesize.py` groups enriched records by `theme_id`. **No clustering and no LLM call
happens here** — it is a group-by over labels already assigned, so it is auditable, free,
and reproducible.

Each theme is ranked by `prevalence × severity × strategic_relevance`:

- **Prevalence** — theme size ÷ total corpus.
- **Severity** — `abs(avg_sentiment)`, i.e. how far the theme skews from neutral *in either
  direction*. A strongly positive habit-and-reorder theme is as noteworthy as a strongly
  negative trust barrier; they simply answer different questions.
- **Strategic relevance** — 0.5 base, +0.25 if the theme contains any q-comm comparison
  evidence (the problem statement calls category-to-platform mental models the single most
  important signal), +0.25 if it maps to three or more research questions. Capped at 1.0.

Each theme is also mapped to the research questions it answers via a fixed theme→question
table, and marked `high` confidence if its evidence spans two or more independent sources,
`single_source` otherwise. Outputs: `data/themes/themes.jsonl` and
`data/themes/research_questions.json`. **All eight research questions are currently
answered by at least one theme.**

### 3.2 Live retrieval (the Insight Engine tab)

`src/index.py` embeds all 4,110 evidence records with `BAAI/bge-small-en-v1.5` — the same
local model used in normalize and cluster, so no second embedding space is introduced — and
writes a LanceDB index with two tables (`evidence`, `themes`).

At question time, `app/rag_engine.py`:

1. Embeds the question and retrieves the **top 8 evidence records** by vector similarity.
2. Builds a numbered context block `[1]…[8]`, where each quote carries its metadata —
   source, sentiment, barrier, theme and segment labels — not just its text. Passing the
   enrichment labels is what allows an answer to name specific segments and categories
   instead of paraphrasing complaints in the abstract.
3. Asks the LLM for a structured JSON answer: executive summary citing `[n]`, theme
   breakdown, affected segments, and product recommendations.
4. **Constrains the vocabulary.** The prompt lists the nine theme names and eight segment
   labels and permits nothing else — and `_coerce()` enforces that on the way out,
   case- and punctuation-insensitively, so an off-vocabulary label cannot reach the UI even
   if the model ignores the instruction. This is what keeps the chat speaking the same
   language as the dashboard.
5. Renders each `[n]` as a link to the quote it cites, with every retrieved quote listed
   and numbered beneath the answer.

**Grounding rules.** The summary, themes and segments must come strictly from the retrieved
quotes. Product recommendations are the single field allowed to carry model judgment — an
explicit, documented relaxation of the project's insight-only constraint — and are
labelled as such.

**Graceful degradation.** When the daily LLM quota is exhausted, the engine falls back to a
deterministic extractive summary built entirely from enrichment labels already attached to
the retrieved records: never fabricated, always traceable. The answer's method line states
which path produced it.

---

## 4. How insight quality was validated

`python -m src.validate` reads every stage's output and writes `reports/scorecard.md`.
Eight checks run:

| # | Check | Latest result |
|---|---|---|
| 1 | Gold-set classifier accuracy | **Pending** — see below |
| 2 | Inter-run stability | **0.833** theme agreement (n = 90) |
| 3 | Cross-source triangulation | **9/9** themes span ≥ 2 sources; no single-source themes |
| 4 | Citation audit | **1.0** verbatim match, **1.0** well-formed URLs (n = 20) |
| 5 | Counter-evidence search | Disconfirming records found for all 9 themes |
| 6 | Recency split | Largest drift +6.6pp (category distrust) |
| 7 | Ingest funnel | Full counts per stage |
| 8 | Source coverage + bias flags | 5 themes flagged ≥ 90% single-source |

### 4.1 The gold set is deliberately not automated

Grading an LLM classifier against labels produced by the same LLM is circular. So
`src/gold_label.py` is a resumable CLI that samples 100 seeded items and asks **a human**
to judge relevance and barrier type. Until that is done, the scorecard reports gold-set
metrics as `"status": "pending"` — never a fabricated placeholder.

**This check has not yet been run, so classifier precision/recall against human judgment is
currently unknown.** It is the single most important outstanding gap in the validation
story.

### 4.2 Stability replaces bootstrap re-clustering

The original spec called for re-clustering a 90% bootstrap sample. Since theming moved from
clustering to supervised classification, the equivalent check is run-to-run label
agreement: the classifier is re-run on a fresh sample **with the disk cache bypassed**, so
it is a genuine second independent LLM pass. Agreement was **83.3%** — meaning roughly one
record in six would be labelled differently on a second pass. Theme proportions should be
read as approximate, not precise.

### 4.3 Counter-evidence is searched for, not assumed absent

For each theme, the full corpus is searched for records sharing the theme's dominant
category but opposing its sentiment direction, and **what is found is reported** — e.g.
160 disconfirming records for category-specific distrust, 452 for price and value. The
purpose is to prevent a theme from reading as unanimous when it is merely dominant.

### 4.4 Citations are verified verbatim

Twenty representative quotes were checked to be exact substrings of their stored source
text, with well-formed URLs. Both rates must be 1.0 — quotes are never paraphrased — and
both are.

### 4.5 Known limitations

Stated plainly, because they bound how far these insights should be pushed:

1. **Play Store dominance.** 3,662 of 4,110 enriched records (89%) come from one source.
   Five themes are flagged as ≥ 90% single-source. Cross-source triangulation passes on a
   technicality — every theme has *some* second-source evidence — but the weight is
   lopsided, and app-store reviews skew negative by nature.
2. **Reddit and forums contributed nothing.** Two of seven configured sources are blocked,
   removing exactly the discussion-style evidence that would balance app-store complaints.
3. **Product reviews are proxies.** Only 18 records, from Amazon/Nykaa SKUs rather than
   Blinkit's own PDPs.
4. **The gold set is unlabelled**, so classifier accuracy against human judgment is unknown
   (§4.1).
5. **83.3% run-to-run agreement** means theme sizes carry meaningful uncertainty (§4.2).
6. **The scorecard is one run behind.** `reports/scorecard.md` was generated 2026-07-23
   against a corpus of 36,771 raw / 3,950 enriched records; the current corpus is 41,176
   raw / 4,110 enriched. The checks' conclusions are unlikely to move, but the numbers in
   §4 should be regenerated with `python -m src.validate --config config.yaml` before being
   quoted externally.
7. **Sentiment is bucketed at ±0.2**, and the scores are bimodal (most mass near ±0.8–1.0),
   so the neutral band is thin (11%) and small threshold changes move the split.

---

## Reproducing any figure here

```bash
python -m src.normalize   --config config.yaml     # funnel counts
python -m src.relevance   --config config.yaml     # relevance gate
python -m src.enrich      --config config.yaml     # labels + theme_id
python -m src.cluster     --config config.yaml --input data/clustered/unclassified.jsonl
python -m src.synthesize  --config config.yaml     # themes + research questions
python -m src.validate    --config config.yaml     # reports/scorecard.md
python -m src.index       --config config.yaml     # LanceDB index for the app
streamlit run app/rag_chatbot.py
```

Each stage writes a manifest next to its output; the dashboard reads those manifests
directly, so the app and this document cannot silently disagree.
