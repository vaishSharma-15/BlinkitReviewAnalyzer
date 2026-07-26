# Methodology

How the Blinkit Review Discovery Engine gathers data, identifies themes, generates
insights, and checks that those insights hold up.

Every figure below is read from the pipeline's own manifests, not estimated.

```
ingest → normalize → relevance gate → enrich → synthesize → validate
                                         ↓
                                  index → Insight Engine (RAG)
```

---

## 1. Gathering and analyzing the data

### Sources

| Source | Coverage | Enriched records |
|---|---|---|
| Play Store | `com.grofers.customerapp`, IN/en | 3,662 |
| YouTube | 10 search terms — hauls, comparisons, reviews | 252 |
| Q-comm threads | Blinkit vs. Zepto / Instamart discussions | 121 |
| App Store | app id 960335206, IN | 57 |
| Product reviews | Category SKUs (pet, baby care, …) | 18 |

Two collection notes, flagged in the data rather than hidden: YouTube uses `yt-dlp`
instead of the official Data API, and Blinkit's own product pages require an
authenticated session, so Amazon/Nykaa SKUs stand in — marked `meta.is_proxy_source`.

### Cleaning

`src/normalize.py` drops anything under 15 characters, filters spam, removes exact and
near-duplicates (embedding cosine > 0.95, compared within source + day), and tags
language as en / hi / hinglish / other using a deterministic keyword-and-script rule —
no ML model, so the step stays auditable.

### Relevance gate

An LLM judges each record relevant or not to the research subject: shopping habits,
category choice, discovery, assortment, category trial.

Two constraints shaped it:

- **Quota.** The free tier allows 500 requests/day, so calls are **batched** — 40 items
  per relevance call, 15 per enrich call, numbered list in, JSON array out. A batch that
  fails to parse is retried, then split in half recursively, so one bad response can't
  drop a whole batch. Results are cached on disk, so reruns cost nothing.
- **A keyword pre-filter** saves further quota, but runs on **English only**. Hindi and
  Hinglish go through unfiltered, because the Latin-script keyword list under-matched
  Devanagari badly — 6.2% survival versus 31.1% for English, a blind spot rather than a
  real signal difference.

### The funnel

| Stage | Count |
|---|---|
| Raw collected | 41,176 |
| After length, spam and dedup filters | 26,569 |
| Judged relevant | **4,110** |
| Enriched (0 failed) | **4,110** |
| Assigned a theme | **3,548** |

The corpus spans **2024-09-05 to 2026-07-23**; a barrier type was identified in 2,912 of
the 4,110 records.

**That ~10% survival rate is the design, not attrition.** The corpus is deliberately
narrowed to reviews about category discovery and barriers, so it is *not* a
representative sample of Blinkit sentiment. Figures drawn from it — such as the 60%
negative / 29% positive split — describe this subset only, not overall satisfaction.

### Enrichment

Each relevant record gets closed-vocabulary labels in a single LLM call: category,
behaviour signal, barrier type, segment signals (family stage, city tier, price
sensitivity, pet ownership), sentiment (−1 to +1), quote-worthiness, and a primary
theme. Every response is validated against the vocabularies in `src/schemas.py`, retried
once on violation, then quarantined. **0 records failed** on the current run.

---

## 2. Identifying themes

**Themes come from supervised classification against a fixed taxonomy, not from
clustering** — a decision made after measuring the alternative.

Unsupervised clustering (embeddings → PCA → HDBSCAN) was built first. On this corpus it
produced **3 clusters with 66% of records in the noise bucket** — too coarse to answer
the eight research questions. Supervised classification leaves only ~14% unclassified.

Nine themes, hand-designed against the research questions, each record getting exactly
one (or `unclassified`) in the same LLM call as the other labels:

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

Clustering still runs, but only over the `unclassified` leftovers, asking whether a tenth
theme is missing. On this corpus those leftovers cluster into what the spec defines as
noise — generic refund complaints naming no product, generic delivery praise — so the
taxonomy stood. `unclassified` is always reported as its own row, never folded into a
theme.

---

## 3. Generating insights

### Offline synthesis

`src/synthesize.py` groups enriched records by theme. **No clustering, no LLM call** — a
group-by over labels already assigned, so it is free and reproducible.

Themes rank by `prevalence × severity × strategic_relevance`:

- **Prevalence** — theme size ÷ corpus size.
- **Severity** — `abs(avg_sentiment)`: distance from neutral in *either* direction, so a
  strongly positive habit theme counts as much as a strongly negative trust barrier.
- **Strategic relevance** — 0.5 base, +0.25 for q-comm comparison evidence, +0.25 if the
  theme answers three or more research questions.

Each theme maps to the research questions it answers. **All eight are currently answered
by at least one theme.**

### Live retrieval (Insight Engine)

All 4,110 records are embedded with `BAAI/bge-small-en-v1.5` — the same model used
earlier in the pipeline — into a LanceDB index. At question time:

1. Retrieve the **top 8 records** by vector similarity.
2. Build a numbered context `[1]…[8]` where each quote carries its **metadata** — source,
   sentiment, barrier, theme, segments — not just text. That is what lets an answer name
   specific segments and categories instead of paraphrasing complaints in the abstract.
3. Request structured JSON: summary citing `[n]`, theme breakdown, affected segments,
   recommendations.
4. **Constrain the vocabulary** to the nine themes and eight segment labels — and enforce
   it on the way out with `_coerce()`, so an off-vocabulary label cannot reach the UI even
   if the model ignores the instruction. This keeps chat and dashboard speaking the same
   language.
5. Render each `[n]` as a link to the quote it cites, with all retrieved quotes listed
   and numbered below.

Summary, themes and segments must come strictly from retrieved quotes. **Product
recommendations are the one field allowed to carry model judgment**, an explicit
relaxation of the insight-only constraint. When the daily quota runs out, the engine
falls back to a deterministic extractive summary built from enrichment labels — never
fabricated — and says which path produced the answer.

---

## 4. Validating insight quality

`python -m src.validate` writes `reports/scorecard.md`. Eight checks:

| # | Check | Result |
|---|---|---|
| 1 | Gold-set classifier accuracy | **Pending** |
| 2 | Inter-run stability | **0.833** agreement (n = 90) |
| 3 | Cross-source triangulation | **9/9** themes span ≥ 2 sources |
| 4 | Citation audit | **1.0** verbatim, **1.0** valid URLs (n = 20) |
| 5 | Counter-evidence search | Disconfirming records found for all 9 themes |
| 6 | Recency split | Largest drift +6.6pp |
| 7 | Ingest funnel | Counts per stage |
| 8 | Source coverage + bias flags | 5 themes ≥ 90% single-source |

Three of these deserve explanation:

**The gold set is deliberately manual.** Grading an LLM against labels made by the same
LLM is circular, so `src/gold_label.py` asks a human to judge 100 sampled items. Until
that happens the scorecard reports `"pending"` — never a placeholder number. **It has not
been run, so accuracy against human judgment is unknown.**

**Stability replaces bootstrap re-clustering.** The classifier is re-run on a fresh
sample with the cache bypassed — a genuine second LLM pass. Agreement is **83.3%**, so
roughly one record in six would be labelled differently next time. Read theme
proportions as approximate.

**Counter-evidence is searched for, not assumed absent.** For each theme the corpus is
scanned for records sharing its dominant category but opposing its sentiment, and what
turns up is reported — 160 disconfirming records for category distrust, 452 for price and
value — so a dominant theme never reads as unanimous.

### Known limitations

1. **Play Store dominance** — 3,662 of 4,110 records (89%) come from one source, and five
   themes are flagged ≥ 90% single-source. Triangulation passes on a technicality; the
   weight is lopsided, and app-store reviews skew negative by nature.
2. **Product reviews are proxies** — 18 records, from Amazon/Nykaa rather than Blinkit.
3. **The gold set is unlabelled**, so classifier accuracy is unverified.
4. **83.3% run-to-run agreement** means theme sizes carry real uncertainty.
5. **The scorecard is one run behind** — generated against 36,771 raw / 3,950 enriched
   versus today's 41,176 / 4,110. Rerun `python -m src.validate` before quoting §4
   externally.
6. **Sentiment buckets at ±0.2** and the scores are bimodal, so the neutral band is thin
   (11%) and small threshold changes move the split.

---

## Reproducing any figure

```bash
python -m src.normalize   --config config.yaml     # funnel counts
python -m src.relevance   --config config.yaml     # relevance gate
python -m src.enrich      --config config.yaml     # labels + theme_id
python -m src.synthesize  --config config.yaml     # themes + research questions
python -m src.validate    --config config.yaml     # reports/scorecard.md
python -m src.index       --config config.yaml     # LanceDB index
streamlit run app/rag_chatbot.py
```

Each stage writes a manifest beside its output, and the dashboard reads those manifests
directly — so the app and this document cannot silently disagree.
