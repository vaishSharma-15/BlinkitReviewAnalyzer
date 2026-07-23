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


def _segment_labels(evidence: List[dict]) -> List[str]:
    labels = []
    for field, prefix in [
        ("family_stage", ""), ("city_tier", ""), ("price_sensitivity", "price sensitivity: "),
        ("has_pet", "has pet: "),
    ]:
        counts = Counter(e[field] for e in evidence if e.get(field, "unknown") != "unknown")
        if counts:
            top_value, n = counts.most_common(1)[0]
            labels.append(f"{prefix}{top_value} ({n} items)")
    return labels


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
        return {
            "executive_summary": "No matching evidence found in the indexed corpus for this question.",
            "theme_breakdown": [], "affected_segments": [], "product_recommendations": [], "method": "none",
        }

    if os.getenv("GEMINI_API_KEY"):
        try:
            from src.llm import DailyQuotaExhausted, call_llm

            context = "\n\n".join(
                f"[{i+1}] (source: {e['source']}) \"{e['text'][:400]}\""
                for i, e in enumerate(evidence)
            )
            system_prompt = (
                "You are a product research assistant. Answer strictly from the numbered "
                "evidence quotes below — real Blinkit user reviews. Do not invent facts or "
                "use outside knowledge for the summary/themes/segments. Respond with ONLY a "
                "JSON object, no markdown fences: "
                '{"executive_summary": "2-3 sentence answer citing [n] evidence numbers", '
                '"theme_breakdown": ["short theme label", ...], '
                '"affected_segments": ["short segment description", ...], '
                '"product_recommendations": ["short, directional product recommendation", ...]}. '
                "product_recommendations may reflect your own product judgment (unlike the other "
                "fields, which must stay strictly evidence-grounded) — keep each one short and "
                "directional, not a detailed spec."
            )
            raw = call_llm(system_prompt, f"Question: {query}\n\nEvidence:\n{context}", "rag-answer-v3", json_mode=True)
            if raw:
                import json
                import re

                cleaned = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
                data = json.loads(cleaned)
                return {
                    "executive_summary": data.get("executive_summary", ""),
                    "theme_breakdown": data.get("theme_breakdown", []),
                    "affected_segments": data.get("affected_segments", []),
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

    theme_breakdown = [t["name"] for t in matched_themes] or (
        [f"{k} ({v} items)" for k, v in barrier_counts.most_common(3)]
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
