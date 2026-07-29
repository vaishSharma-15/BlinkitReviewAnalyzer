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
- Every number, theme and answer in the app must come from a frozen snapshot, never from
  a live call made while someone is looking at the page.
- The **Fetch new reviews** panel (§10) is the single exception to live traffic, and it is
  walled off from the analysis: it writes nothing, is never indexed, and is never
  retrievable by the chat. The constraint it preserves is that the *corpus* is frozen, not
  that the app never opens a socket.
- A live panel must not be mistakable for corpus data. Reviews it shows are labelled as a
  preview and kept visually separate from anything the pipeline produced.

### Insufficient evidence in the app
- If the retrieval layer does not find enough evidence, the app should say so clearly instead of answering from model priors.

### Public deployment constraints
- The app should not expose secrets or rely on live credentials in the deployed environment.

## 9. Live review fetch edge cases

The sidebar's Fetch new reviews panel (`app/live_fetch.py`) is the only part of the app
that calls a source at request time. It runs inside a page render, so every failure mode
is one a person is waiting on.

### A store is unreachable, slow, or rate-limiting
- Play and the App Store are fetched independently. A failure in one is reported as a step
  and must not cost the other its results.
- If both fail, the panel must say so (`Couldn't fetch · <ErrorType>`). An empty result
  presented as success would read as "there are no new reviews", which is a different and
  false claim.
- The scraper is an unofficial client of a private endpoint. It can break without notice;
  that is a reported failure, not an exception that takes the page down.

### Nothing new is found
- "No new reviews" is a real answer and must be shown as one. Every id returned already
  being in `data/raw/` is the expected result minutes after a previous run.

### The sample is unrepresentative
- Newest-first is not neutral: the newest 100 Play reviews are 78% four-or-five-star with
  a median length of 11 characters. Sampling one review per star rating is what keeps the
  panel from being a wall of "good".
- A rating bucket with no substantial review still shows its newest short one rather than
  going empty, so a missing rating never implies nobody rated that way.

### Links that cannot be honest
- Play links carry the review id and locale and resolve to that review.
- Apple publishes no per-review permalink; the only review-specific URL in its feed is the
  reviewer's profile, which is PII this repo does not persist. Those cards link to the
  reviews list and are labelled *Open in App Store*, not *Open review*.

### Duplicate detection depends on a file the app only reads
- "New" means an id absent from `data/raw/{play,appstore}.jsonl`, cached for the session.
- On a deployment whose `data/raw/` is older than the repo, the baseline is the deployed
  snapshot — the count is honest about what *this instance* has, which is what the label
  claims.

### Sidebar space
- The result panel must occupy bounded height regardless of how many reviews return:
  the list scrolls inside its own box. An unbounded panel pushes the account chip off the
  bottom of the sidebar and makes the whole sidebar scroll.

## 10. Conversation-state edge cases

### Clearing a conversation
- Clear chat drops the conversation from session state only. The LLM disk cache is
  untouched, so re-asking a cleared question costs no quota.
- The control is present but disabled before there is anything to clear, rather than
  appearing mid-conversation and shifting the layout under the reader.
- It must remain reachable during a long conversation — it lives in the sticky heading, so
  scroll depth never hides it.

### Answers landing behind fixed chrome
- Anything pinned above the conversation (Streamlit's header, the sticky banner) has to be
  subtracted from the scroll target, or a new answer arrives with its first lines hidden.
- The offset is measured from the banner's own height at scroll time, not hardcoded: the
  banner grows a line when the window narrows.

## 11. Operating principles for these edge cases

- Prefer explicit reporting over silent guessing.
- Preserve traceability from each theme to its source evidence.
- If evidence is missing, report the gap directly.
- Do not fabricate themes, quotes, or supporting claims.
