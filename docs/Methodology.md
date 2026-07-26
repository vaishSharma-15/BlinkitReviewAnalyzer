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

Everything shown anywhere in the app is built from the 4,110 cleaned, labelled reviews.
Nothing draws on raw uncleaned data, and nothing draws on what the AI happens to know
about Blinkit from elsewhere.

### On the dashboard: counting

The dashboard is pure arithmetic over the labels — **no AI runs at this stage at all**,
so the same data always produces the same page. Themes are ranked on three factors
multiplied together:

| Factor | Means | Example: Category-Specific Distrust |
|---|---|---|
| How common | Share of the corpus | 36% of all reviews |
| How strongly felt | Distance from neutral, either direction | −0.73 (strongly negative) |
| How relevant | Does it answer the research questions, and does it involve competitor comparisons | Highest weighting |

Distance from neutral counts in *either* direction on purpose: a strongly positive
theme like Habit & Reorder (+0.76) is as informative as a strongly negative one — they
just answer different questions.

That produces the running order: Category-Specific Distrust ranks far above everything
else, then Habit & Reorder, then Price & Value. Each theme is also matched to the
research questions it answers — **all eight are currently answered**, by between one and
nine themes each.

### In the Insight Engine chat: retrieving

The 4,110 filtered reviews are stored in a **vector database** — a search index that
matches by meaning rather than by exact words. Only these reviews are in it; the ones
dropped during cleaning and filtering are not.

The flow is: **your question → vector database → matching reviews → one request to the
AI → the answer you see.** Every answer therefore passes through the filtered reviews on
its way to you.

In detail, five steps:

1. **The whole-corpus totals are handed to the AI** — every theme's size and average
   sentiment, plus each shopper segment's negative rate. These are the same counts the
   dashboard renders, so the two can't disagree.
2. **The question goes to the vector database**, which returns the 8 closest reviews by
   meaning — a question about "expensive" surfaces reviews saying "overpriced" or
   "cheaper on Zepto", even though neither uses the word.
3. **Those reviews go to the AI with their labels attached** — source, sentiment,
   barrier, theme, shopper type — which is why answers can name specific groups and
   categories instead of speaking in generalities.
4. **The AI returns** a summary, the themes involved, who's affected, and
   recommendations, in one request.
5. **The quotes are listed underneath, numbered**, so every `[3]` in the answer links to
   the review behind it.

The reason for step 1 is worth stating plainly. Eight quotes tell you *what* people say,
but nothing about *how many* people say it. Without the totals, a question like "which
segment is most frustrated?" would be answered from whichever eight reviews came back.
With them, it is answered from all 667 price-sensitive reviews. So:

> **Totals answer "how much". Quotes answer "what".** The AI is told to use the totals
> for any claim about scale or ranking, never to infer prevalence from how many of its
> eight quotes mention something, and never to state a number that isn't in the totals.

Four rules keep answers honest:

- **Fixed vocabulary.** The AI may only name themes and shopper groups from our lists,
  so chat and dashboard speak the same language. Anything else it invents is stripped
  out before display — the instruction alone isn't trusted.
- **Evidence-bound.** Summaries, themes and groups must come from the retrieved reviews,
  not the AI's general knowledge.
- **One honest exception.** Recommendations are the single place the AI's own judgment
  is allowed, because a recommendation is by definition not something a reviewer said.
- **Graceful failure.** If the AI is unavailable, the app answers from the labels and
  totals alone — never a fabricated summary — and states which method it used.

---

## 5. How we check the quality of the insights

Quality is checked in three ways: an automated report over the whole analysis, rules
built into the app so a bad answer can't reach the screen, and reading the answers
ourselves to confirm they match the evidence behind them.

### The quality report

One command regenerates it (`reports/scorecard.md`), so these are repeatable checks, not
a one-off review. Each asks a specific question:

| Question | Method | Result |
|---|---|---|
| Are themes repeatable? | Re-sort a fresh sample, ignoring saved results | **83% agreement** (90 reviews) |
| Is each theme in more than one source? | Count distinct sources per theme | **9 of 9** pass |
| Are the quotes real? | Match each against its original review | **100%** exact, **100%** valid links (20 quotes) |
| Does contrary evidence exist? | Search for reviews that contradict each theme | Found for **all 9** themes |
| Are complaints current? | Compare older vs. newer half | Stable; largest shift **+7 points** |
| Is a theme leaning on one source? | Flag anything ≥90% from one place | **5 themes** flagged |

**Are themes repeatable?** We re-ran the theme sorting on a fresh sample with saved
results ignored, so it was a genuine second opinion rather than a replay. It agreed with
the first pass **83% of the time** — about one review in six would land differently.
That is good enough to rank themes confidently, but theme sizes should be read as
approximate rather than exact.

**Is each theme in more than one source?** A theme visible only in Play Store reviews
could be an artifact of that channel rather than a real pattern. **All 9 appear in at
least two independent sources** — though see the caveat below about how lopsided that
balance is.

**Are the quotes real?** We took 20 quotes shown as evidence and checked each against its
original review. **100% matched word for word**, with **100% working links** back to the
source. Quotes are never paraphrased, shortened misleadingly, or reconstructed — this
check has to come back perfect or the evidence trail is broken.

**Does contrary evidence exist?** For every theme we deliberately search for reviews that
contradict it — same product category, opposite sentiment — and report what turns up.
Category distrust has **160** reviews pointing the other way; price complaints have
**452**. The point is to stop a common theme being presented as though everyone agrees.

**Are complaints current?** We split the reviews into older and newer halves and compared
theme shares. Themes are broadly stable, and the largest movement is category distrust
rising about **7 points** — so it is a live problem, not a legacy one being recycled.

**Is a theme leaning on one source?** The report flags any theme drawing 90%+ of its
evidence from a single place. **Five are flagged**, all leaning on Play Store reviews.
That flag is why the first caveat below exists.

### Checks built into the app

Three guardrails run every time an answer is produced, so quality doesn't depend on
anyone reading the report:

- **Vocabulary is enforced, not requested.** The AI is told to use only our nine themes
  and eight shopper groups — and anything outside those lists is removed from its answer
  before display. It cannot invent a category that exists nowhere in the data.
- **Every claim is traceable.** Each numbered citation in an answer links to the actual
  review it came from, listed underneath. A claim with no quote behind it is visible as
  such.
- **Scale comes from counts, not impressions.** Prevalence claims must come from the
  corpus totals (§4), so "most users" reflects 4,110 reviews rather than eight.

### Reading the answers

The last check is done by a person, because some things only a reader can catch. We ask
the engine real questions and read what comes back, checking three things:

1. **Does the answer actually address the question asked**, or is it a general statement
   about Blinkit that would fit any question?
2. **Does each claim trace to a quote below it?** The numbered links make this quick —
   click `[3]`, read review 3, confirm it says what the summary claims it says.
3. **Do the themes named match the reviews retrieved?** If an answer is built on quotes
   about expiry and freshness, it should be reporting Category-Specific Distrust — not a
   theme those reviews don't carry.

This is a manual spot-check, not a scored metric, and it is repeated whenever the way we
ask the AI changes. It is how we caught two real problems: answers inventing their own
theme names instead of ours, and answers describing complaints generically because the
AI was only shown quote text with none of the labels attached. Both were fixed by
changing what the AI receives — the enforced vocabulary and the labelled quotes described
in §4.

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
