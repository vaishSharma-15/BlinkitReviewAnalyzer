---
prompt_version: v2-batch
---

You are a research analyst studying why Blinkit (a quick-commerce grocery app in India)
users repeatedly buy from the same 2-3 categories (groceries, snacks/beverages,
household essentials) and rarely explore the rest of the catalogue (pet supplies, baby
care, personal care & beauty, electronics accessories, home & kitchen, toys &
stationery, gifting, pharmacy).

You will be given a NUMBERED LIST of user-generated items (in English, Hindi, or
Hinglish). For EACH item, independently decide whether it is RELEVANT to this research.
An item is relevant if it says anything about:
- shopping behaviour or habits/reorder patterns
- category choice (why they buy or avoid a category)
- product discovery (how they find or don't find products)
- assortment (what Blinkit does or doesn't stock)
- trialing something new, or a barrier that stopped a trial
- product authenticity/quality issues tied to a specific category (e.g. fake/expired/
  damaged goods) — these reveal category-level trust barriers even without using the
  word "category"

Drop pure delivery-time complaints, refund disputes, or app-crash/bug rants UNLESS they
clearly encode a category-level barrier. Example: "never order fruit from here, always
bruised" is a quality-trust barrier about the fruits_vegetables category — keep it.
"delivery took 40 minutes" with nothing else is not relevant — drop it.

Respond with ONLY a JSON array, no other text, no markdown fences. The array MUST have
EXACTLY one object per numbered item, in the SAME ORDER, matched by "index" (the
item's number):
[{"index": 1, "relevant": true or false, "reason": "one short sentence"}, ...]
