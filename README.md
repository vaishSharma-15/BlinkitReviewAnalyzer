<div align="center">

<img src="app/assets/blinkit-logo.png" width="72" alt="Blinkit"/>

# Blinkit Review Discovery Engine

**Why do users stay locked inside 2–3 familiar shopping categories — in their own words, at scale.**

[![Python](https://img.shields.io/badge/python-3.11-F9D507?style=flat-square&labelColor=191c1e)](runtime.txt)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-F9D507?style=flat-square&labelColor=191c1e)](app/rag_chatbot.py)
[![LLM](https://img.shields.io/badge/LLM-Gemini-F9D507?style=flat-square&labelColor=191c1e)](src/llm.py)
[![Vector store](https://img.shields.io/badge/vector%20store-LanceDB-F9D507?style=flat-square&labelColor=191c1e)](data/lancedb)
[![License](https://img.shields.io/badge/license-unlicensed-F9D507?style=flat-square&labelColor=191c1e)](#license)

[Overview](#overview) · [Pipeline](#the-pipeline) · [Quickstart](#quickstart) · [App](#the-app) · [Scorecard](#insight-quality-scorecard) · [Docs](#further-reading)

</div>

---

## Overview

Blinkit is a weekly habit for millions of urban Indian shoppers — and that habit is also its
ceiling. Most users buy the same 2–3 categories (groceries, snacks, household essentials) on
repeat and never touch the rest of the catalogue, even though Blinkit already stocks pet
supplies, baby care, beauty, electronics accessories, toys, home & kitchen, and gifting.

Nobody actually knows *why*. Is it trust? Price? Not knowing the products exist? A bad past
experience? Each answer points to a different fix, and today it's all internal opinion — even
though the evidence already exists in tens of thousands of app reviews, forum posts, and social
threads where users explain their own behaviour, unprompted.

This project turns that raw, unstructured feedback into a **ranked, evidence-linked set of
themes**, each one traceable back to verbatim quotes — answering eight fixed research questions
about category exploration, discovery, habit, and unmet needs.

|  |  |
|---|---|
| **Corpus** | 32,725+ raw reviews across Play Store and App Store, ingested from 7 candidate sources |
| **Relevant & enriched** | 4,110 reviews carrying structured labels (category, barrier type, sentiment, segment) |
| **Themes** | 9, each mapped to the research question(s) it answers |
| **Shopper segments** | 5, discovered from stated behaviour in the reviews themselves — not assumed demographics |
| **Trust layer** | An Insight Quality Scorecard: gold-set accuracy, inter-run stability, citation audit, counter-evidence search |

This is a research/insight deliverable, not a product feature build — the pipeline stops at
validated insight, which becomes the input to the next stage of the work.

## The pipeline

Every stage writes JSONL to `data/`, never overwrites the stage before it, and is resumable —
re-running a stage after a partial failure or a quota reset continues from where it stopped.

```
 ingest → normalize → relevance gate → enrich → segment → cluster (safety net) → synthesize → validate
  (7 sources)  (dedup,      (LLM:          (LLM:        (behaviour-    (unsupervised    (group by     (scorecard:
               lang detect)  relevant?)     labels +     based           check on the     theme,        accuracy,
                                             theme_id)    segments,       "unclassified"   rank by       stability,
                                             ↓            evidence-       leftover)        prevalence)   citations,
                                        data/enriched/    checked)                                       counter-
                                                                                                          evidence)
```

| Phase | What it does | Detail |
|---|---|---|
| 01 · Ingest | Pulls public Blinkit feedback from Play Store, App Store, Reddit, YouTube, forums, product reviews, and quick-commerce discussions — idempotent, resumable, PII-stripped at collection time | [docs/Pipeline.md](docs/Pipeline.md#phase-01--ingest) |
| 02 · Normalize | Dedups (exact + near-duplicate via embedding cosine), filters spam, detects language (en/hi/hinglish) deterministically | [docs/Pipeline.md](docs/Pipeline.md#phase-02--normalize) |
| 03 · Relevance gate | LLM-classifies each item against the research theme, with a keyword pre-filter on English text to conserve free-tier quota | [docs/Pipeline.md](docs/Pipeline.md#phase-03--relevance-gate) |
| 04 · Enrich | Adds closed-vocabulary labels (category, barrier type, sentiment, segment signals) and a `theme_id` from a fixed 9-theme taxonomy | [docs/Pipeline.md](docs/Pipeline.md#phase-04--enrich) |
| 04b · Segment | Derives 5 behaviour-based shopper segments from the reviews themselves; every label is verified against a verbatim quote in code, not just asked for in the prompt | [docs/Pipeline.md](docs/Pipeline.md#phase-04b--segment) |
| 05 · Cluster | Unsupervised HDBSCAN pass over only what the fixed taxonomy left `unclassified`, as a check for a missing theme | [docs/Pipeline.md](docs/Pipeline.md#phase-05--cluster-secondary-check-only) |
| 06 · Synthesize | Groups enriched records by theme, maps each to the research questions it answers, ranks by prevalence × severity × strategic relevance | [docs/Pipeline.md](docs/Pipeline.md#phase-06--synthesize) |
| 07 · Validate | Produces the Insight Quality Scorecard — see below | [docs/Pipeline.md](docs/Pipeline.md#phase-07--validate-the-insight-quality-scorecard) |

The full phase-by-phase log — every quota constraint, blocked source, and design tradeoff behind
these stages — lives in **[docs/Pipeline.md](docs/Pipeline.md)**.

## Quickstart

```bash
git clone https://github.com/vaishSharma-15/BlinkitReviewAnalyzer.git
cd BlinkitReviewAnalyzer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY, REDDIT_*, YOUTUBE_API_KEY as available
```

Run a pipeline stage (always smoke-test with `--limit` first):

```bash
python -m src.ingest.play_store --config config.yaml --limit 50
python -m src.normalize --config config.yaml
python -m src.relevance --config config.yaml
python -m src.enrich --config config.yaml
python -m src.segment discover && python -m src.segment assign
python -m src.synthesize --config config.yaml
python -m src.validate --config config.yaml
```

Launch the app:

```bash
streamlit run app/rag_chatbot.py
```

## The app

A Streamlit dashboard and RAG chatbot over the classified corpus, styled in Blinkit's own yellow
(`#F9D507`) and near-black — see [app/theme.py](app/theme.py).

- **Overview** — corpus-wide dashboard: sources, sentiment, category mix
- **Themes & User Voice** — the 9 themes, ranked, each backed by verbatim evidence quotes
- **Deep Analytics** — filterable breakdowns by segment, source, and category
- **Insight Engine** — ask a question in plain English, get a cited answer retrieved from the
  LanceDB index over the enriched corpus, with a graceful fallback to an extractive summary if
  the LLM call fails or the free-tier quota is exhausted
- **Fetch new reviews** — pulls Blinkit's newest App Store / Play Store reviews live, for
  preview only; it never writes to the corpus the index and scorecard are built from, so the
  numbers above always agree with each other

## Insight Quality Scorecard

Every theme is checked, not just asserted. `reports/scorecard.md` (regenerated by
`python -m src.validate`) reports:

- **Gold-set classifier accuracy** — against human-graded labels, so it's never circular
- **Inter-run stability** — a fresh, cache-bypassed LLM pass re-classifies a sample; theme
  agreement rate: **83.3%**
- **Cross-source triangulation** — 9/9 themes confirmed by ≥2 independent sources
- **Citation audit** — verbatim quote match rate: **100%**, valid source URL rate: **100%**
- **Counter-evidence search** — disconfirming records surfaced per theme, not hidden
- **Recency split** — theme prevalence compared across an older/newer date split, to catch
  drift rather than assume the corpus is static

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| Ingest | `google-play-scraper`, Apple's public reviews feed, `praw`, `yt-dlp`, `httpx` + `selectolax` |
| LLM | Google Gemini (`gemini-3.5-flash-lite`), disk-cached by `sha256(prompt_version + text)` |
| Embeddings | `sentence-transformers` |
| Clustering | `scikit-learn` (PCA + HDBSCAN), unsupervised safety net only |
| Vector store | `lancedb` — file-based, lives in the repo |
| App | `streamlit` |
| Data format | JSONL at every stage, one record per line, upstream stages never overwritten |

## Repo structure

```
src/            pipeline stages — ingest, normalize, relevance, enrich, segment, cluster, synthesize, validate
app/            Streamlit dashboard + RAG chatbot, Blinkit-themed
prompts/        versioned LLM prompts, one file per stage
data/           JSONL at every stage (raw → normalized → relevant → enriched → segments → themes)
docs/           problem statement, methodology, phase-wise architecture, edge cases, pipeline log
reports/        generated Insight Quality Scorecard
config.yaml     source targets, model pins, thresholds
```

## Further reading

- [docs/ProblemStatement.md](docs/ProblemStatement.md) — the business problem, the eight research questions, and the tech-stack decisions behind this build
- [docs/Pipeline.md](docs/Pipeline.md) — the full phase-by-phase engineering log
- [docs/Methodology.md](docs/Methodology.md) — research methodology
- [docs/PhaseWiseArchitecture.md](docs/PhaseWiseArchitecture.md) — architecture per phase
- [docs/EdgeCases.md](docs/EdgeCases.md) — edge cases and how they're handled

## License

No license file is currently included — all rights reserved by default. Open an issue if you'd
like to discuss reuse.
