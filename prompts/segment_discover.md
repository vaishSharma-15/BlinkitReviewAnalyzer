---
prompt_version: segment-discover-v1
---

You are a research analyst studying why Blinkit (an Indian quick-commerce grocery app)
shoppers stay inside a narrow set of familiar categories instead of exploring the rest
of the catalogue.

You will be given a NUMBERED LIST of real reviews. Read them and identify the distinct
SHOPPER SEGMENTS that are directly evidenced in this text.

WHAT A SEGMENT MAY BE BUILT FROM
A segment must be defined by what shoppers state about their own shopping — what they
buy, how they choose, what they refuse to buy and why, what they compare against, what
would change their mind. These things are written down in the reviews.

WHAT A SEGMENT MAY NOT BE BUILT FROM
Never define a segment by age, gender, income, occupation, family size, city or any
other demographic attribute. A review does not report these, so any such segment would
be invention. If a reviewer states such an attribute themselves ("as a mother of two"),
you may use it only as supporting evidence inside a behaviour-defined segment, never as
the segment's definition.

RULES
- Propose between 4 and 7 segments. Fewer, well-evidenced segments beat more thin ones.
- Segments must be distinguishable: a reader given one review must be able to place it
  in at most one segment. State what separates each from its nearest neighbour.
- Every segment needs at least 3 supporting reviews from the list below.
- Every example quote must be copied VERBATIM from the review it comes from — the exact
  characters, no paraphrase, no cleanup, no ellipsis. Quotes are checked against the
  source text and a segment whose quotes do not match is discarded.
- Do not propose a segment for reviews that only complain about delivery, app bugs or
  refunds with no product or category involved. Those shoppers are not a segment.

For each segment give:
  segment_id: lower_snake_case, stable, descriptive (e.g. "emergency_top_up_only")
  name: 2-4 words, plain English, how a PM would say it
  definition: one sentence — who this shopper is, in terms of stated behaviour
  inclusion_rule: one sentence a labeller could apply to a single review to decide
    whether it belongs — written as an observable test on the review's own words
  distinguished_from: one clause naming the nearest other segment and the difference
  evidence_indices: the item numbers supporting this segment (at least 3)
  example_quotes: 2-3 verbatim spans from those items

Respond with ONLY a JSON object, no markdown fences:
{"segments": [{"segment_id": "...", "name": "...", "definition": "...",
  "inclusion_rule": "...", "distinguished_from": "...", "evidence_indices": [1, 2, 3],
  "example_quotes": ["...", "..."]}]}
