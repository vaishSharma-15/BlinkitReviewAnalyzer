"""Retrieval + answer-generation engine shared by the Copilot tab (and usable from the
sidebar for the index-status check). Kept separate from tab rendering so the retrieval
logic has no Streamlit-widget code mixed into it.
"""
import os
from collections import Counter
from pathlib import Path
from typing import List, Optional

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "data" / "index" / "lancedb"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"


@st.cache_resource(show_spinner=False)
def get_embed_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL_NAME)


@st.cache_resource(show_spinner=False)
def get_db():
    import lancedb

    if not INDEX_DIR.exists():
        return None
    return lancedb.connect(str(INDEX_DIR))


def retrieve_evidence(query: str, top_k: int = 8) -> List[dict]:
    db = get_db()
    if db is None or "evidence" not in db.list_tables().tables:
        return []
    model = get_embed_model()
    vector = model.encode([query], normalize_embeddings=True)[0].tolist()
    table = db.open_table("evidence")
    return table.search(vector).limit(top_k).to_list()


def retrieve_themes(query: str, top_k: int = 3) -> List[dict]:
    """Themes have no vector column (small enough to rank by simple keyword overlap
    rather than embedding a second index for a handful of rows).

    Only returns themes with actual overlap > 0 — with a small number of themes total,
    always returning the top-k regardless of match quality means every question shows
    the same theme list, which is what generate_structured_answer's own barrier-derived
    fallback exists to avoid. Matching against name + dominant labels, not just the
    (often generic) name, gives a slightly better chance of a real match."""
    db = get_db()
    if db is None or "themes" not in db.list_tables().tables:
        return []
    table = db.open_table("themes")
    rows = table.to_arrow().to_pylist()
    query_tokens = set(query.lower().split())
    scored = []
    for row in rows:
        name_tokens = set(row["name"].lower().replace(",", "").replace("&", "").split())
        scored.append((len(query_tokens & name_tokens), row))
    scored.sort(key=lambda x: (-x[0], -x[1]["rank_score"]))
    return [row for overlap, row in scored[:top_k] if overlap > 0]


# Heuristic fallback recommendations, keyed by barrier_type, used only when Gemini is
# unavailable (daily quota exhausted). Deliberately generic/directional, not fabricated
# specifics — this is a template keyed off the closed-vocabulary label already attached
# to the evidence, not a claim about what the evidence itself says.
BARRIER_TO_RECOMMENDATION = {
    "trust_quality": "Improve quality-assurance transparency (e.g. visible freshness/authenticity guarantees) for categories with recurring trust complaints.",
    "price_premium": "Clarify pricing/fee breakdowns at checkout so users can compare against other platforms without surprise charges.",
    "assortment_doubt": "Increase visibility of existing catalogue breadth so users don't assume a category isn't stocked.",
    "findability": "Improve in-app search/navigation for categories users report difficulty locating.",
    "no_trigger": "Surface contextual prompts for categories users haven't considered ordering from Blinkit.",
    "returns_risk": "Simplify and clarify the returns/refund process for higher-value or fragile categories.",
    "brand_absence": "Expand brand assortment in categories where users cite absence of trusted/preferred brands.",
    "expiry_freshness": "Strengthen freshness/expiry handling for perishable categories with repeated complaints.",
    "prefer_specialist_store": "Understand what specialist stores offer that Blinkit doesn't, for categories with entrenched alternatives.",
}


# --- Shared vocabulary -----------------------------------------------------
# The chat answer must speak the same language as the Overview/Theme tabs, so its
# theme and segment labels are drawn from the same fixed sets the enrichment pipeline
# uses (src/schemas.py THEMES + the four segment dimensions), rendered with the display
# names the dashboard shows. Without this the LLM invents a fresh vocabulary per
# question ("Search functionality", "Users searching for specific items") that appears
# nowhere in the corpus and matches nothing on the other tabs.
THEME_CHOICES = [
    "Platform Mental Model", "Category-Specific Distrust", "First-Trial Stories",
    "Habit & Reorder", "Discovery Mechanics", "Assortment Gaps", "Price & Value",
    "Life-Event Triggers", "Cross-Platform Comparison",
]

SEGMENT_CHOICES = [
    "Price-Sensitive", "Price-Insensitive", "Parents", "Singles", "Couples",
    "Pet Owners", "Metro", "Tier-2 City",
]

# Which theme a barrier label belongs under, so the extractive path's barrier counts can
# be reported in theme vocabulary instead of raw enrichment keys like "trust_quality".
BARRIER_TO_THEME = {
    "trust_quality": "Category-Specific Distrust",
    "price_premium": "Price & Value",
    "assortment_doubt": "Assortment Gaps",
    "findability": "Discovery Mechanics",
    "no_trigger": "Platform Mental Model",
    "returns_risk": "Category-Specific Distrust",
    "brand_absence": "Assortment Gaps",
    "expiry_freshness": "Category-Specific Distrust",
    "prefer_specialist_store": "Cross-Platform Comparison",
}


def _coerce(values, allowed: List[str]) -> List[str]:
    """Keep only labels from `allowed`, matched case/punctuation-insensitively.

    The prompt constrains the model, but a constraint that is only asked for is not a
    guarantee — this is what actually keeps an off-vocabulary label out of the UI.
    """
    def norm(s):
        return "".join(ch for ch in str(s).lower() if ch.isalnum())

    lookup = {norm(a): a for a in allowed}
    out = []
    for v in values or []:
        hit = lookup.get(norm(v))
        if hit and hit not in out:
            out.append(hit)
    return out


# Enrichment values -> the display labels the dashboard uses (app/tab_overview.SEG_LABELS).
SEGMENT_DISPLAY = {
    ("price_sensitivity", "high"): "Price-Sensitive",
    ("price_sensitivity", "low"): "Price-Insensitive",
    ("family_stage", "parent_young_child"): "Parents",
    ("family_stage", "single"): "Singles",
    ("family_stage", "couple"): "Couples",
    ("has_pet", "yes"): "Pet Owners",
    ("city_tier", "metro"): "Metro",
    ("city_tier", "tier2"): "Tier-2 City",
}


@st.cache_data(show_spinner=False)
def corpus_stats() -> dict:
    """Whole-corpus aggregates: theme sizes and per-segment negative rates.

    Retrieval only ever surfaces 8 quotes, which says what users said but nothing about
    how widespread it is. These are the same counts the dashboard renders, so a chat
    answer and the Overview tab cannot disagree about scale.
    """
    db = get_db()
    out = {"total": 0, "themes": [], "segments": []}
    if db is None:
        return out
    tables = db.list_tables().tables
    if "themes" in tables:
        rows = db.open_table("themes").to_pandas().sort_values("size", ascending=False)
        out["themes"] = [
            {"name": r["name"], "size": int(r["size"]), "avg_sentiment": round(float(r["avg_sentiment"]), 2)}
            for _, r in rows.iterrows()
        ]
    if "evidence" in tables:
        df = db.open_table("evidence").to_pandas()
        out["total"] = len(df)
        for field in ["family_stage", "city_tier", "price_sensitivity", "has_pet"]:
            if field not in df.columns:
                continue
            known = df[df[field] != "unknown"]
            for value, grp in known.groupby(field):
                label = SEGMENT_DISPLAY.get((field, value))
                # Same floor the dashboard uses, so tiny groups don't post wild rates.
                if label and len(grp) >= 10:
                    out["segments"].append({
                        "name": label, "n": len(grp),
                        "negative_rate": round(float((grp["sentiment"] < -0.2).mean()), 3),
                    })
    out["segments"].sort(key=lambda s: -s["negative_rate"])
    return out


def _stats_block(stats: dict) -> str:
    if not stats.get("themes") and not stats.get("segments"):
        return ""
    # Shares are of themed reviews, matching how the Theme Intelligence tab states them —
    # quoting a share of the full corpus instead would read as contradicting the dashboard.
    themed_total = sum(t["size"] for t in stats["themes"]) or 1
    lines = [f"CORPUS TOTALS (all {stats['total']} analysed reviews, not just the quotes below):",
             f"Theme sizes ({themed_total} reviews carry a theme; shares are of that):"]
    for t in stats["themes"]:
        share = t["size"] / themed_total * 100
        lines.append(f"  - {t['name']}: {t['size']} reviews ({share:.1f}% of themed), avg sentiment {t['avg_sentiment']}")
    if stats["segments"]:
        lines.append("Negative-sentiment rate by shopper segment:")
        for s in stats["segments"]:
            lines.append(f"  - {s['name']}: {s['negative_rate']:.0%} negative across {s['n']} reviews")
    return "\n".join(lines)


def ui_sentiment(score: float) -> str:
    return "positive" if score > 0.2 else ("negative" if score < -0.2 else "neutral")


def _evidence_segments(e: dict) -> str:
    """The segment labels attached to one quote, for the model's context block."""
    got = [SEGMENT_DISPLAY[(f, e.get(f))] for f in
           ["family_stage", "city_tier", "price_sensitivity", "has_pet"]
           if (f, e.get(f)) in SEGMENT_DISPLAY]
    return ", ".join(got)


def _segment_labels(evidence: List[dict]) -> List[str]:
    """Dominant segment per dimension, named exactly as the Overview tab names it."""
    labels = []
    for field in ["family_stage", "city_tier", "price_sensitivity", "has_pet"]:
        counts = Counter(e[field] for e in evidence if e.get(field, "unknown") != "unknown")
        if not counts:
            continue
        top_value, _ = counts.most_common(1)[0]
        label = SEGMENT_DISPLAY.get((field, top_value))
        if label and label not in labels:
            labels.append(label)
    return labels


# --- Scope guard -----------------------------------------------------------
# Retrieval always returns its top-k, however far away the nearest quote is, so an
# unrelated question ("book me a Coldplay ticket") still arrives here with 8 reviews
# attached and used to get a confident-sounding answer written from them. Two gates now
# stand in the way: a distance floor for the obvious cases, and an in_scope flag the
# model itself sets for everything subtler.
#
# The floor is deliberately loose. Measured top-hit L2 distances on this index: real
# questions land at 0.47-0.65, "capital of France" at 0.88, "who won the world cup" at
# 0.74, "write me a python script" at 0.70, "book a Coldplay ticket" at 0.69 — but
# "tell me a joke" sits at 0.65, inside the legitimate band. A floor tight enough to
# catch that would start rejecting real questions, so the floor only handles the clear
# cases and the LLM gate handles the rest.
OUT_OF_SCOPE_FLOOR = 0.68

SCOPE_BLURB = (
    "This engine only answers from Blinkit customer reviews. It covers why shoppers stay "
    "inside a few familiar categories — discovery habits, category barriers, trust and "
    "price concerns, and how different shopper segments behave. It has no other knowledge "
    "and cannot take actions such as booking, ordering or account support."
)

SCOPE_EXAMPLES = [
    "What prevents users from exploring new categories?",
    "Which user segments are more likely to experiment?",
    "What frustrations emerge repeatedly?",
]


def _out_of_scope(note: str) -> dict:
    return {
        "executive_summary": note,
        "scope_blurb": SCOPE_BLURB,
        "scope_examples": SCOPE_EXAMPLES,
        "theme_breakdown": [], "affected_segments": [], "product_recommendations": [],
        "method": "out_of_scope",
    }


def is_out_of_retrieval_range(evidence: List[dict]) -> bool:
    """True when even the closest review sits beyond OUT_OF_SCOPE_FLOOR — i.e. nothing in
    the corpus is about this. Missing distances (a non-vector path) never trip the gate."""
    distances = [e["_distance"] for e in evidence if e.get("_distance") is not None]
    return bool(distances) and min(distances) > OUT_OF_SCOPE_FLOOR


def generate_structured_answer(query: str, evidence: List[dict], matched_themes: List[dict]) -> dict:
    """Returns {executive_summary, theme_breakdown: [str], affected_segments: [str],
    product_recommendations: [str], method}. Tries Gemini for a real synthesis first
    (subject to the shared daily quota); falls back to a deterministic summary built
    entirely from the enrichment labels already attached to the retrieved evidence —
    never fabricated, always traceable to real records. product_recommendations is the
    one field allowed to be judgment rather than pure evidence extraction — the
    project's insight-only constraint (docs/ProblemStatement.md) is intentionally
    relaxed here at the user's explicit request."""
    if not evidence:
        return _out_of_scope("No matching evidence found in the indexed corpus for this question.")

    if is_out_of_retrieval_range(evidence):
        return _out_of_scope(
            "That question isn't something the Blinkit review corpus can speak to — nothing "
            "in it is close to this topic, so there is no evidence to answer from."
        )

    if os.getenv("GEMINI_API_KEY"):
        try:
            from src.llm import DailyQuotaExhausted, call_llm

            # Each quote carries its enrichment labels, not just its text. Without the
            # segment/barrier/theme fields the model can only paraphrase complaints in
            # the abstract ("users are frustrated by delays"), which is what made answers
            # to questions like "which segments are most frustrated?" read generically.
            context = "\n\n".join(
                f"[{i+1}] source={e['source']} sentiment={ui_sentiment(e['sentiment'])} "
                f"barrier={e.get('barrier_type', 'none')} theme={e.get('theme_id', 'unclassified')} "
                f"segments={_evidence_segments(e) or 'unknown'} date={str(e.get('date', ''))[:10]}\n"
                f"\"{e['text'][:400]}\""
                for i, e in enumerate(evidence)
            )
            system_prompt = (
                "You are a product research assistant. Answer strictly from the numbered "
                "evidence quotes below — real Blinkit user reviews. Do not invent facts or "
                "use outside knowledge for the summary/themes/segments. Respond with ONLY a "
                "JSON object, no markdown fences: "
                '{"in_scope": true or false, '
                '"executive_summary": "2-3 sentence answer citing [n] evidence numbers", '
                '"theme_breakdown": ["theme label", ...], '
                '"affected_segments": ["segment label", ...], '
                '"product_recommendations": ["short, directional product recommendation", ...]}. '
                "FIRST decide in_scope, on the SUBJECT of the question only. Set in_scope=false, "
                "and every other field empty, in exactly two cases: (a) the question is not about "
                "Blinkit shoppers, their reviews, or their shopping/discovery behaviour — e.g. "
                "general knowledge, chit-chat, coding, other companies, or facts about Blinkit as "
                "a company rather than about its shoppers; (b) it asks you to perform a task or "
                "transaction — booking, ordering, account or password help, customer support. "
                "Then put ONE plain sentence in executive_summary saying you cannot answer it and "
                "why, with no citations and no partial answer built from the quotes. "
                "Otherwise in_scope=true. A question about shopper behaviour, segments, barriers, "
                "categories, discovery or sentiment is ALWAYS in scope — including when the "
                "retrieved quotes cover it only partly. Never decline such a question: answer it "
                "from the corpus totals and whatever the quotes do support, and say plainly which "
                "part is thinly evidenced. Weak evidence is a caveat to state, not a reason to "
                "refuse. "
                "theme_breakdown MUST use only these exact labels, and only those actually "
                f"evidenced in the quotes: {', '.join(THEME_CHOICES)}. "
                "affected_segments MUST use only these exact labels, and only where the quotes "
                f"actually show that group: {', '.join(SEGMENT_CHOICES)}. "
                "Do not invent new theme or segment labels; return an empty list if none apply. "
                "Two kinds of input follow. CORPUS TOTALS are counts over every analysed "
                "review — use them for any claim about scale, prevalence, ranking or which "
                "group is 'most' anything, and quote the figure. The numbered EVIDENCE "
                "quotes are what users actually said — use them for the substance of the "
                "answer and cite them as [n]. Never infer prevalence from how many of the "
                "quotes mention something, and never state a number that is not in the "
                "corpus totals. "
                "Be specific, not generic: answer the question that was asked directly in the "
                "first sentence, and use the concrete detail in the quotes and their metadata — "
                "name the actual categories, products, competitors, segments and sources the "
                "evidence mentions, and say how many of the quotes support each point. If the "
                "question asks which group or segment, lead with the segment labels in the "
                "metadata rather than describing complaints in general. Never write a sentence "
                "that would read the same for any other question. Cite [n] after each claim. "
                "product_recommendations may reflect your own product judgment (unlike the other "
                "fields, which must stay strictly evidence-grounded) — each must respond to a "
                "specific problem in the quotes, naming it, not restate a generic best practice."
            )
            stats_block = _stats_block(corpus_stats())
            user_content = (f"Question: {query}\n\n{stats_block}\n\nEVIDENCE:\n{context}"
                            if stats_block else f"Question: {query}\n\nEvidence:\n{context}")
            # v6: corpus totals added to the context, so cached v3-v5 answers (which were
            # written without any prevalence data) must not be served.
            # v8: adds the in_scope gate, so cached v6 answers (written before the model
            # could decline) must not be served for out-of-scope questions. v7 scoped it
            # on evidence fit as well as subject, which declined real questions whose
            # quotes were only a partial match.
            raw = call_llm(system_prompt, user_content, "rag-answer-v8", json_mode=True)
            if raw:
                import json
                import re

                cleaned = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
                data = json.loads(cleaned)
                if data.get("in_scope") is False:
                    return _out_of_scope(
                        data.get("executive_summary")
                        or "That question is outside what the Blinkit review corpus can answer."
                    )
                return {
                    "executive_summary": data.get("executive_summary", ""),
                    # Enforced, not merely requested — see _coerce.
                    "theme_breakdown": _coerce(data.get("theme_breakdown"), THEME_CHOICES),
                    "affected_segments": _coerce(data.get("affected_segments"), SEGMENT_CHOICES),
                    "product_recommendations": data.get("product_recommendations", []),
                    "method": "gemini",
                }
        except DailyQuotaExhausted:
            st.info("Gemini daily quota exhausted — showing an extractive (non-generative) summary instead.")
        except Exception:
            pass

    # Deterministic fallback.
    n = len(evidence)
    avg_sentiment = sum(e["sentiment"] for e in evidence) / n
    tone = "negative" if avg_sentiment < -0.2 else ("positive" if avg_sentiment > 0.2 else "mixed")
    barrier_counts = Counter(e["barrier_type"] for e in evidence if e["barrier_type"] != "none")
    behaviour_counts = Counter(e["behaviour_signal"] for e in evidence if e["behaviour_signal"] != "none")
    top_barrier = barrier_counts.most_common(1)[0][0] if barrier_counts else None
    top_behaviour = behaviour_counts.most_common(1)[0][0] if behaviour_counts else None

    summary = f"Across the {n} most relevant retrieved reviews, sentiment is {tone} (avg {avg_sentiment:.2f})."
    if top_behaviour:
        summary += f" The dominant behaviour signal is {top_behaviour}."
    if top_barrier:
        summary += f" The most common barrier mentioned is {top_barrier}."
    sources = Counter(e["source"] for e in evidence)
    if len(sources) == 1:
        summary += f" ⚠️ All evidence comes from a single source ({next(iter(sources))}) — low confidence until other sources are enriched."

    # Ground the retrieved sample in the whole corpus, so this path also reports scale
    # rather than describing 8 quotes as though they were the population.
    stats = corpus_stats()
    if stats.get("themes"):
        top = stats["themes"][0]
        themed_total = sum(t["size"] for t in stats["themes"]) or 1
        summary += (f" Across all {stats['total']:,} analysed reviews, the largest theme is "
                    f"{top['name']} ({top['size']:,} reviews, {top['size'] / themed_total:.0%} of themed).")
    if stats.get("segments"):
        worst = stats["segments"][0]
        summary += (f" The segment with the highest negative rate is {worst['name']} "
                    f"({worst['negative_rate']:.0%} of {worst['n']:,} reviews).")

    # Themes come from the matched taxonomy rows; the barrier fallback is coerced to the
    # same theme vocabulary so this path can never print a label the other tabs lack.
    theme_breakdown = _coerce([t["name"] for t in matched_themes], THEME_CHOICES) or _coerce(
        [BARRIER_TO_THEME.get(k, "") for k, _ in barrier_counts.most_common(3)], THEME_CHOICES
    )
    recommendations = [
        BARRIER_TO_RECOMMENDATION[b] for b, _ in barrier_counts.most_common(3) if b in BARRIER_TO_RECOMMENDATION
    ]

    return {
        "executive_summary": summary,
        "theme_breakdown": theme_breakdown,
        "affected_segments": _segment_labels(evidence),
        "product_recommendations": recommendations,
        "method": "extractive",
    }
