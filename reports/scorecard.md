# Insight Quality Scorecard

_Generated 2026-07-23T23:04:27.899320+00:00_

## 1. Gold-set classifier accuracy
**Status: pending.** data/gold/labels.jsonl not found — run: python -m src.gold_label

## 2. Inter-run stability (theme classification)
- n = 90 records re-classified fresh (cache bypassed)
- theme_id agreement rate: **0.833**

## 3. Cross-source triangulation
- 9/9 themes are high-confidence (>=2 independent sources)
- single-source themes: none

## 4. Citation audit
- n = 20 sampled representative quotes
- verbatim match rate: **1.0** (must be 1.0 — quotes are never paraphrased)
- well-formed URL rate: **1.0**

## 5. Counter-evidence search
- **category_specific_distrust** (dominant category: fruits_vegetables, theme leans negative): 160 disconfirming records found (e.g. play_d85f23b2-f861-4b08-9f04-abf91f2bafda, play_d49b1443-6bb7-4fe5-aa7e-8748424b643f, play_1701768c-cd4f-442a-b9cc-6973d0b70184)
- **habit_and_reorder** (dominant category: grocery_staples, theme leans positive): 325 disconfirming records found (e.g. play_dfd12228-dd90-452c-8b44-568dbd3fccd9, play_f450a80b-d451-4a3d-9fd7-7d6edb26b596, play_eef14d9a-db0b-42e2-80b8-2a53eea05fa4)
- **price_and_value** (dominant category: grocery_staples, theme leans negative): 452 disconfirming records found (e.g. play_5fc329bb-162d-4950-8c0a-cd19d281383d, play_d85f23b2-f861-4b08-9f04-abf91f2bafda, play_d49b1443-6bb7-4fe5-aa7e-8748424b643f)
- **cross_platform_comparison** (dominant category: grocery_staples, theme leans negative): 453 disconfirming records found (e.g. play_5fc329bb-162d-4950-8c0a-cd19d281383d, play_d85f23b2-f861-4b08-9f04-abf91f2bafda, play_d49b1443-6bb7-4fe5-aa7e-8748424b643f)
- **assortment_gaps** (dominant category: grocery_staples, theme leans negative): 464 disconfirming records found (e.g. play_5fc329bb-162d-4950-8c0a-cd19d281383d, play_d85f23b2-f861-4b08-9f04-abf91f2bafda, play_d49b1443-6bb7-4fe5-aa7e-8748424b643f)
- **discovery_mechanics** (dominant category: grocery_staples, theme leans positive): 329 disconfirming records found (e.g. play_dfd12228-dd90-452c-8b44-568dbd3fccd9, play_14126854-bb66-43c6-83fa-b517355bc6bc, play_f450a80b-d451-4a3d-9fd7-7d6edb26b596)
- **platform_mental_model** (dominant category: grocery_staples, theme leans positive): 325 disconfirming records found (e.g. play_dfd12228-dd90-452c-8b44-568dbd3fccd9, play_14126854-bb66-43c6-83fa-b517355bc6bc, play_f450a80b-d451-4a3d-9fd7-7d6edb26b596)
- **first_trial_story** (dominant category: snacks_beverages, theme leans positive): 274 disconfirming records found (e.g. play_cac6f4af-4134-4237-b187-afac97058f46, play_ecbe5c03-22bb-4b4c-822e-93ba5370a12c, play_5dd4602c-474c-4949-8ae5-366c4a10d93f)
- **life_event_trigger** (dominant category: baby_care, theme leans positive): 23 disconfirming records found (e.g. play_a07d95f1-bd79-4485-b586-ad541ac5fb54, play_f65225ea-3af0-4c6c-b8ce-7ac4f832b483, play_76f640a6-dbfb-4009-abb5-302080f3834d)

## 6. Recency split
- split date: 2026-06-11 (n_older=1975, n_newer=1975)

| theme_id | older % | newer % | delta |
|---|---|---|---|
| category_specific_distrust | 33.1 | 39.7 | +6.6 |
| cross_platform_comparison | 10.6 | 7.3 | -3.3 |
| assortment_gaps | 12.2 | 9.1 | -3.1 |
| unclassified | 12.4 | 15.3 | +2.9 |
| habit_and_reorder | 12.9 | 10.3 | -2.6 |
| discovery_mechanics | 1.6 | 2.5 | +1.0 |
| first_trial_story | 4.0 | 3.3 | -0.7 |
| price_and_value | 10.3 | 9.8 | -0.5 |
| platform_mental_model | 1.9 | 1.8 | -0.2 |
| life_event_trigger | 1.0 | 0.9 | -0.1 |

## 7. Ingest funnel
| stage | count |
|---|---|
| raw | 36771 |
| after length filter | 25155 |
| after spam filter | 25078 |
| after dedup | 23835 |
| relevant | 3950 |
| enriched | 3950 |

## 8. Source coverage
| source | raw | enriched | notes |
|---|---|---|---|
| play | 32139 | 3662 | Primary volume source, unblocked. |
| appstore | 500 | 44 | Apple's public RSS feed hard-caps at ~500 most-recent reviews — that's the full available volume, not a partial run. |
| reddit | 0 | 0 | BLOCKED: robots.txt disallows all agents; public search.json 403s without OAuth creds not available in this environment. |
| youtube | 2816 | 181 | Used yt-dlp + youtube-comment-downloader (no YOUTUBE_API_KEY available) — approved substitution, more fragile than the official API. |
| forum | 0 | 0 | BLOCKED: Quora disallows scraping; MouthShut explicitly disallows ClaudeBot. Two substitute forums checked and also ruled out. |
| product_review | 49 | 2 | Blinkit PDP reviews require an authenticated session; falls back to Amazon/Nykaa proxy SKUs, labelled meta.is_proxy_source=true. |
| qcomm_comparison | 1267 | 61 | Targeted slice tagged at ingest across Reddit/YouTube/forums — exposes category-to-platform mental models directly. |

**Source-bias flag** (theme >= 90% from one source):
- category_specific_distrust: 95.8% from `play`
- habit_and_reorder: 95.9% from `play`
- price_and_value: 92.7% from `play`
- assortment_gaps: 97.4% from `play`
- life_event_trigger: 91.9% from `play`
