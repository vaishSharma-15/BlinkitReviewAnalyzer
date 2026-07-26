# How This Analysis Works

A plain-language guide to where the Blinkit review data comes from, how it becomes
themes and insights, and how we check that those insights are trustworthy.

All numbers come from the pipeline's own output files.

---

## 1. Where the data comes from

We collected public reviews and discussions about Blinkit from five places:

| Source | What it is | Reviews used |
|---|---|---|
| Play Store | Android app reviews | 3,662 |
| YouTube | Comments on hauls, reviews and comparisons | 252 |
| Q-comm threads | Blinkit vs. Zepto / Instamart discussions | 121 |
| App Store | iPhone app reviews | 57 |
| Product reviews | Reviews of specific products | 18 |

The reviews span **September 2024 to July 2026**.

---

## 2. How the data is cleaned and narrowed

We started with **41,176** collected reviews and ended with **4,110** used in the
analysis. Three steps get us there:

**Clean.** Remove very short reviews, spam, and duplicates (including near-duplicates —
the same complaint posted twice in slightly different words). This leaves 26,569.

**Filter for relevance.** An AI model reads each review and decides whether it actually
says something about *how people shop by category* — what they buy, what they avoid,
how they find products, what stops them trying something new. Most reviews are about
delivery speed or app bugs, so most are set aside. This leaves **4,110**.

**Label.** Each surviving review is tagged with a category, the barrier it describes,
the shopper's sentiment (positive to negative), signals about who they are (parent, pet
owner, price-sensitive, city type), and one theme.

| Stage | Reviews |
|---|---|
| Collected | 41,176 |
| After cleaning | 26,569 |
| Relevant to the research | **4,110** |
| Sorted into a theme | **3,548** |

**Keeping only 10% is the intent, not a failure.** We deliberately narrowed to reviews
about category discovery. That also means this set is *not* a general measure of
Blinkit satisfaction — the 60% negative / 29% positive split describes these
discovery-related reviews, not customers overall.

---

## 3. How themes are identified

We defined **nine themes** up front, built around the eight research questions, and the
AI sorts each review into one of them.

| Theme | Reviews | Share |
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
| Didn't fit any theme | 562 | — |

**Why fixed themes instead of letting the computer find them?** We tried the automatic
approach first — grouping reviews by similarity, with no predefined categories. It
produced only **3 vague groups, with two-thirds of reviews left over as "noise"**. Too
blunt to answer the research questions. Fixed themes leave only 14% unsorted.

We still run the automatic grouping on the leftovers, as a check for a tenth theme we
might have missed. So far the leftovers are genuine noise — refund complaints that name
no product, generic praise for fast delivery.

Reviews that fit no theme are always shown as their own line, never quietly folded into
a theme to make the numbers look tidier.

---

## 4. How insights are generated

**On the dashboard**, each theme is scored on three things: how often it appears, how
strongly people feel about it, and how directly it answers the research questions. Every
figure is counted from the labels — nothing is estimated or written by AI at this stage.

**In the Insight Engine chat**, asking a question:

1. Finds the 8 most relevant real reviews.
2. Passes them to the AI *with their labels attached* — source, sentiment, barrier,
   theme, shopper type. This is why answers can name specific groups and categories
   instead of speaking in generalities.
3. Gets back a summary, the themes involved, who's affected, and recommendations.
4. Shows the quotes underneath, numbered, so every claim links to the review behind it.

Three rules keep answers honest:

- The AI may only use themes and shopper groups from our fixed lists, so chat and
  dashboard always use the same language. Anything else it invents is filtered out.
- Summaries, themes and groups must come from the retrieved reviews — not the AI's
  general knowledge. Recommendations are the one place its own judgment is allowed.
- If the AI is unavailable, the app falls back to a summary built purely from the
  labels, and says so.

---

## 5. How we check the quality of the insights

Every claim gets checked by an automated report we can re-run at any time
(`reports/scorecard.md`). Six checks matter most:

**Do the same reviews get the same themes twice?**
We re-ran the theme sorting on a fresh sample, ignoring any saved results, so it was a
genuine second opinion. It agreed with the first pass **83% of the time** — about one
review in six would land differently. Theme sizes are solid enough to rank, but should
be read as approximate, not exact.

**Does each theme appear in more than one place?**
A theme found only in Play Store reviews could be an artifact of that one channel. **All
9 themes appear across at least two independent sources.**

**Are the quotes real?**
We sampled 20 quotes shown as evidence and checked each one against its original review.
**100% matched word for word**, with **100% working links** back to the source. Quotes
are never paraphrased or reconstructed.

**Did we go looking for evidence against ourselves?**
For every theme, we search the full set for reviews that contradict it — same category,
opposite sentiment — and report what we find. Category distrust has 160 reviews pointing
the other way; price complaints have 452. This stops a common theme from being presented
as if everyone agrees.

**Are the complaints current?**
We split the reviews into an older and newer half and compared. Themes are broadly
stable; the biggest movement is category distrust rising about 7 points, so it is a
current problem, not a legacy one.

**Is any theme leaning on a single source?**
The report flags any theme where 90%+ of evidence comes from one place. Five themes are
flagged, all leaning on Play Store reviews — noted below.

---

## 6. What to keep in mind

1. **Most evidence is Play Store reviews** — 3,662 of 4,110 (89%). App-store reviews
   skew negative by nature, so the overall tone is more negative than the customer base
   probably is.
2. **Theme sizes carry ±uncertainty** because of the 83% repeat-agreement above.
3. **Accuracy hasn't been checked against human judgment yet** — that check needs a
   person to hand-label a sample, and it hasn't been done.
4. **Product reviews are stand-ins** — only 18, and from other retailers rather than
   Blinkit's own product pages.
5. **The quality report is one run old** — it was generated on a slightly smaller set
   (3,950 reviews vs. today's 4,110). Re-run it before quoting these figures externally.
6. **Positive/negative is a cut-off, not a fact** — reviews are scored on a scale and
   split at a threshold, so the exact percentages shift if the threshold moves.

---

## Re-running everything

```bash
python -m src.normalize   --config config.yaml    # clean + dedupe
python -m src.relevance   --config config.yaml    # filter for relevance
python -m src.enrich      --config config.yaml    # labels + themes
python -m src.synthesize  --config config.yaml    # theme summaries
python -m src.validate    --config config.yaml    # the quality report
python -m src.index       --config config.yaml    # search index for the app
streamlit run app/rag_chatbot.py                  # the dashboard
```

Each step writes its own record of what it did, and the dashboard reads those records
directly — so the app and this document can't drift apart.
