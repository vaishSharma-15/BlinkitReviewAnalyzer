# Edge Cases and Failure Modes

## 1. Data quality edge cases

### Short or low-information records
- Records below the required length should be dropped during normalization.
- Very short text may not contain enough context to support a reliable relevance decision.

### Duplicate and near-duplicate content
- Exact duplicates should be removed.
- Near-duplicates should be handled using similarity thresholds to avoid over-counting the same user voice.

### Spam and bot content
- Referral-code spam, repeated promotional strings, and pure emoji content should be filtered.
- This reduces noise and prevents inflated theme prevalence.

## 2. Language and transliteration issues

### Mixed-language input
- The pipeline must support English, Hindi, and Hinglish content.
- Transliteration should be preserved rather than discarded when it carries usable meaning.

### Low-confidence language handling
- Records that cannot be confidently categorized should be flagged as other and processed conservatively.

## 3. Relevance classification edge cases

### Delivery and refund complaints
- Pure app-crash or refund rants should generally be filtered out.
- They should be retained only when they clearly encode a category-level barrier such as quality or trust concerns.

### Ambiguous items
- Some items may mention a category indirectly or only briefly.
- These should be reviewed carefully because they may not meet the threshold for a strong evidence signal.

## 4. LLM and enrichment edge cases

### Parse failures
- Enrichment output must be strict JSON.
- If parsing fails, the system should retry once with a repair prompt.
- If it still fails, the item should be quarantined for review instead of silently dropped.

### Prompt-version drift
- Cache keys should include the prompt version so that changes in prompts do not accidentally reuse outdated results.

### Closed-vocabulary violations
- Enrichment labels must stay inside the approved vocabularies.
- Free-text labels should never be invented.

## 5. Source-level edge cases

### Low-volume or blocked sources
- Some sources may be genuinely difficult to scrape.
- If a required source is blocked, the documentation must record the blocker and the substitute used.

### Source imbalance
- A theme that appears mostly in Play Store reviews may be biased toward more frustrated users.
- The validation stage should explicitly flag source skew and over-reliance on one channel.

### Cross-source disagreement
- Different sources may present conflicting evidence.
- Contradicting evidence should be stored and surfaced rather than ignored.

## 6. Validation edge cases

### No supporting evidence for a theme
- If a theme cannot be grounded in corpus items, it should not be published.
- The system should report that the research question is unanswerable rather than fabricating a theme.

### Weak triangulation
- A theme supported by only one source should be marked as low-confidence or explicitly single-source.
- High-confidence themes should require evidence from at least two independent sources.

### Citation failures
- Evidence quotes must be verbatim and linked to URLs that resolve.
- Citation audit failures should be surfaced in the scorecard.

## 7. Stability and robustness edge cases

### Re-run safety
- Re-running the pipeline must not corrupt earlier outputs.
- The pipeline should be safe to restart after a crash.

### Partial execution failures
- If one item fails in the middle of a large run, the pipeline should preserve progress and avoid losing prior work.

### Dataset shift over time
- Themes can become stale if the corpus shifts significantly.
- Recency comparisons should be used to identify complaints that may already have been fixed.

## 8. Product and deployment edge cases

### Frozen corpus in the app
- The deployed app must not scrape live data.
- It should use a frozen snapshot and display the freeze date.

### Insufficient evidence in the app
- If the retrieval layer does not find enough evidence, the app should say so clearly instead of answering from model priors.

### Public deployment constraints
- The app should not expose secrets or rely on live credentials in the deployed environment.

## 9. Operating principles for these edge cases

- Prefer explicit reporting over silent guessing.
- Preserve traceability from each theme to its source evidence.
- If evidence is missing, report the gap directly.
- Do not fabricate themes, quotes, or supporting claims.
