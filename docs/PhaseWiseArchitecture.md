# Phase-wise Architecture

## 1. Objective

This repository is designed to turn public Blinkit-related user feedback into validated research insights about why users stay within a narrow set of familiar shopping categories. The architecture is intentionally pipeline-based so that each stage can run independently, be inspected, and be re-run without corrupting upstream data.

## 2. End-to-end architecture

The system follows nine sequential stages:

1. Ingest
2. Normalize
3. Relevance gate
4. Enrich
4b. Segment
5. Cluster
6. Synthesize
7. Validate
8. Index and serve

Segment is numbered 4b rather than 5 because it was added after the original eight were
built and running. It depends only on Enrich's output, so renumbering everything
downstream would have broken every existing reference for no gain.

Each stage reads from the previous output directory and writes to its own output directory. No stage mutates upstream files.

## 3. Phase-by-phase design

### Phase 01 — Ingest

Purpose:
- Collect public user feedback from multiple sources.
- Capture raw evidence from Play Store, App Store, Reddit, YouTube, forums, product reviews, and quick-commerce comparison discussions.

Inputs:
- Configured source list and date window
- Network access and credentials where required

Outputs:
- Raw JSONL files under data/raw/
- One file per source type

Key concerns:
- Source coverage must include all seven required source types.
- No PII should be stored.
- Public data only, with respectful scraping behavior.

### Phase 02 — Normalize

Purpose:
- Convert all incoming records into a single schema.
- Standardize language handling and remove low-value content.

Inputs:
- Raw JSONL files

Outputs:
- Normalized JSONL records under data/normalized/

Key concerns:
- Language detection for en, hi, hinglish, and other
- Drop short records under the minimum length
- Deduplicate exact and near-duplicate content
- Remove obvious spam and bot-like content

### Phase 03 — Relevance gate

Purpose:
- Identify records that speak to shopping behaviour, category choice, product discovery, assortment, or trial of something new.

Inputs:
- Normalized records

Outputs:
- Relevant records for downstream enrichment

Key concerns:
- Avoid keeping pure delivery or crash complaints unless they reveal a category-level barrier.
- Target a large enough relevant corpus for trustworthy analysis.

### Phase 04 — Enrich

Purpose:
- Add structured labels and research-relevant metadata to each relevant record.

Inputs:
- Relevant records

Outputs:
- Enriched JSONL records under data/enriched/

Key concerns:
- Use a closed vocabulary for categories, behaviour signals, barrier types, and segment signals.
- Enrichment should be deterministic and auditable.
- Failed parses should be quarantined rather than silently dropped.

Note on `segment_signals`. The four fields here (`family_stage`, `city_tier`,
`price_sensitivity`, `has_pet`) are demographic slots, and a public review almost never
states a demographic. The prompt is right to answer `unknown` rather than guess, which is
why three of the four end up unknown for 98–99% of the corpus. They are retained as
self-disclosed attributes, but they are not the shopper segmentation — see Phase 04b.

### Phase 04b — Segment

Purpose:
- Derive shopper segments from the reviews themselves, defined by stated behaviour rather
  than demographics, and assign every record to one or to `unassigned`.

Inputs:
- Enriched records

Outputs:
- `data/segments/taxonomy.json` — the frozen segment definitions
- `data/segments/assignments.jsonl` — one row per record, with its evidence quote
- `data/segments/manifest.json` — counts, including what was rejected

Key concerns:
- **Discovery runs on a stratified sample.** A plain sample of this corpus is ~89% Play
  Store and ~60% negative, which would yield segments describing the sampling bias.
- **Segments may not be defined by demographics.** Age, gender, income, occupation, city
  and family are explicitly forbidden in the prompt: a review does not report those, so
  such a segment would be invention rather than observation.
- **The taxonomy is frozen before assignment**, so classification runs against a stable
  list and re-runs stay comparable.
- **Every assignment must carry a verbatim `evidence_quote`, checked in code.** The quote
  is matched against its own review's text; failure discards the label and records the
  row as `unassigned`. An `off_taxonomy` id is dropped the same way. This is enforcement,
  not instruction — a guess costs the model the label rather than reaching the dashboard.
- **Rejection counts are published** in the manifest, so the cost of the rule is a number
  a reader can check rather than a claim.
- Coverage is expected to be partial. Assigning every record would mean guessing on
  reviews that state no segment-defining behaviour.

### Phase 05 — Cluster

Purpose:
- Group semantically similar items into clusters.
- Separate meaningful topical clusters from noise.

Inputs:
- Enriched records

Outputs:
- Clustered data plus cluster summaries

Key concerns:
- Use embeddings and dimensionality reduction before clustering.
- Keep the noise bucket visible because it may contain meaningful signals.
- Generate cluster names and representative quotes from the data.

### Phase 06 — Synthesize

Purpose:
- Convert clusters into ranked research themes mapped to the eight research questions.

Inputs:
- Cluster outputs
- Enriched evidence items

Outputs:
- Theme records under data/themes/

Key concerns:
- Every theme must be traceable to actual corpus items.
- Themes must include evidence, prevalence metrics, sources covered, confidence, and contradicting evidence.
- Ranking should reflect prevalence, severity, and strategic relevance.

### Phase 07 — Validate

Purpose:
- Measure whether the pipeline is trustworthy.

Inputs:
- Enriched records, themes, and sampled gold labels

Outputs:
- Validation report in reports/scorecard.md

Key concerns:
- Evaluate relevance precision/recall/F1.
- Check inter-run stability.
- Validate cross-source triangulation.
- Audit evidence citations.
- Test counter-evidence and recency stability.
- Report the ingest funnel and source coverage.

### Phase 08 — Index and serve

Purpose:
- Make the evidence searchable and accessible.

Inputs:
- Enriched records and theme outputs

Outputs:
- LanceDB index and Streamlit app

Key concerns:
- The app must answer only from retrieved evidence, not from model priors.
- The landing view should show the scorecard first.
- The deployed application should use a frozen corpus and display the freeze date.
- One live side channel is permitted and bounded: the sidebar's Fetch new reviews panel
  (`app/live_fetch.py`) calls Play and the App Store at request time to show what is
  arriving now. It writes nothing, is never indexed and is never retrievable by the chat,
  so the served corpus stays frozen. See `docs/EdgeCases.md` §8 and §9.

## 4. Repository structure alignment

The architecture maps directly to the repository layout:

- data/raw/ for raw ingest output
- data/normalized/ for normalized records
- data/enriched/ for enriched records
- data/segments/ for the shopper-segment taxonomy and per-record assignments
- data/themes/ for synthesized themes
- data/gold/ for the human-labelled validation set
- reports/ for the scorecard
- app/ for the public query experience, including app/live_fetch.py for the read-only
  live review panel
- .github/workflows/ for the scheduled jobs that keep the deployment reachable
  (keep-awake.yml) and print a live fetch to the run log (preview-reviews.yml)

## 5. Design principles

- Reproducible and offline-friendly where possible
- Resumable and idempotent
- Auditable from raw evidence to final themes
- No fabricated claims
- No solutioning or product recommendations in the repository
