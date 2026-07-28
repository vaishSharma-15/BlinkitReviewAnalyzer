"""Retrieval + answer-generation engine shared by the Copilot tab (and usable from the
sidebar for the index-status check). Kept separate from tab rendering so the retrieval
logic has no Streamlit-widget code mixed into it.
"""
import json
import logging
import os
from collections import Counter
from pathlib import Path
from typing import List, Optional

import streamlit as st

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "data" / "index" / "lancedb"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Half of the LLM disk-cache key (the other half is the request itself), so bumping this
# retires every cached answer written under the old prompt. The per-version reasoning
# lives with the prompt in build_answer_request, where a change to the wording is
# actually made and the bump is easy to forget.
PROMPT_VERSION = "rag-answer-v10"


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

def segment_choices() -> List[str]:
    """Every behaviour segment in the frozen taxonomy (src/segment.py), named exactly as
    the dashboard names them.

    Read from the taxonomy rather than hardcoded, so adding or renaming a segment is one
    pipeline re-run and not an edit in three files. The old hardcoded list was the eight
    demographic labels, which no longer describe how the app segments anyone.

    This is the vocabulary of the whole corpus, NOT the list an answer may report — that
    is _segment_labels(evidence), the segments the retrieved quotes actually carry.
    """
    from app.data import load_segment_taxonomy

    return [s["name"] for s in load_segment_taxonomy()]

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
        from app.data import segment_lookup

        df = db.open_table("evidence").to_pandas()
        out["total"] = len(df)
        # Behaviour segments, joined on id — the index predates this phase and its rows
        # still carry the old demographic columns, which the app no longer segments on.
        lookup = segment_lookup()
        df = df.assign(segment_name=df["id"].map(lookup))
        named = df[df["segment_name"].notna() & (df["segment_name"] != "")]
        out["segmented_total"] = len(named)
        for name, grp in named.groupby("segment_name"):
            # Same floor the dashboard uses, so tiny groups don't post wild rates.
            if len(grp) >= 10:
                out["segments"].append({
                    "name": name, "n": len(grp),
                    "negative_rate": round(float((grp["sentiment"] < -0.2).mean()), 3),
                })
    out["segments"].sort(key=lambda s: -s["n"])
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
    """The behaviour segment attached to one quote, for the model's context block.

    Joined on id rather than read off the row: the index predates the segment phase, so
    its rows still carry the demographic columns and know nothing about this label. A
    quote whose review earned no segment says 'unknown' — the prompt must not offer the
    model a label the pipeline refused to assign.
    """
    from app.data import segment_lookup

    return segment_lookup().get(e.get("id", ""), "")


def _segment_labels(evidence: List[dict]) -> List[str]:
    """The behaviour segments present in the retrieved quotes, commonest first.

    Same vocabulary as segment_choices(), so the extractive fallback and the generative
    path name segments identically — a reader switching between them should not see the
    corpus described in two languages.
    """
    from app.data import segment_lookup

    lookup = segment_lookup()
    counts = Counter(name for e in evidence if (name := lookup.get(e.get("id", ""))))
    return [name for name, _ in counts.most_common()]


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


# --- Small talk ------------------------------------------------------------
# "hi" is not an out-of-scope request, and answering it with the refusal card reads as
# hostile to someone who has just opened the tab. Greetings, thanks and goodbyes get a
# short human reply instead. Matched deterministically and before retrieval: it costs no
# quota, and it cannot be talked out of the greeting by phrasing.
SMALLTALK_VOCAB = {
    "greeting": {
        "hi", "hii", "hiii", "hey", "heyy", "hello", "helo", "hola", "yo", "namaste",
        "hi there", "hey there", "hello there", "good morning", "good afternoon",
        "good evening", "greetings", "howdy", "sup", "whats up", "what's up",
        "how are you", "how r u", "how are you doing", "who are you", "what are you",
        "what can you do", "what do you do", "help", "start",
    },
    "thanks": {
        "thanks", "thank you", "thankyou", "thanks a lot", "thank you so much", "ty",
        "thx", "tysm", "cheers", "great thanks", "awesome thanks", "perfect thanks",
        "nice", "great", "awesome", "cool", "perfect", "ok thanks", "okay thanks",
    },
    "farewell": {
        "bye", "byee", "goodbye", "good bye", "see you", "see ya", "cya", "bye bye",
        "take care", "later", "good night", "gn",
    },
}

SMALLTALK_REPLY = {
    "greeting": (
        "Hi! I'm the Blinkit Insight Engine. I read what real Blinkit shoppers wrote in "
        "their reviews, so ask me anything about their behaviour — why people stick to a "
        "few familiar categories, what stops them trying new ones, what frustrates them, "
        "and how different shopper segments differ."
    ),
    "thanks": (
        "Happy to help. Ask another question whenever you like — I can dig into any "
        "category barrier, shopper segment or discovery habit in the reviews."
    ),
    "farewell": (
        "Bye! Come back any time you want to know what Blinkit shoppers are saying."
    ),
}


def detect_smalltalk(query: str) -> Optional[str]:
    """Return 'greeting' | 'thanks' | 'farewell' when the message is *only* small talk.

    Whole-message matching, deliberately. "hi, what stops users exploring?" is a real
    question with a greeting attached and must go down the retrieval path — only a
    message that is nothing but the pleasantry is answered from here.
    """
    cleaned = "".join(ch for ch in query.lower() if ch.isalnum() or ch in " '").strip()
    cleaned = " ".join(cleaned.split())
    if not cleaned or len(cleaned.split()) > 4:
        return None
    for kind, phrases in SMALLTALK_VOCAB.items():
        if cleaned in phrases:
            return kind
    return None


def smalltalk_answer(kind: str) -> dict:
    """A friendly reply card: no evidence, no refusal framing, and — for an opening
    greeting — the same example questions the empty state offers."""
    return {
        "executive_summary": SMALLTALK_REPLY[kind],
        "scope_examples": SCOPE_EXAMPLES if kind == "greeting" else [],
        "theme_breakdown": [], "affected_segments": [], "product_recommendations": [],
        "method": "smalltalk",
    }


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


def build_answer_request(query: str, evidence: List[dict]) -> dict:
    """The exact request generate_structured_answer would send Gemini for this question.

    Split out so src/warm_cache.py can pre-compute an answer under the identical
    system_prompt, user_content and prompt_version. The disk cache is keyed on
    sha256(prompt_version + user_content), so a seeded entry only ever gets served if the
    request is byte-identical — building the prompt in two places would produce two keys
    and a seed cache that silently never hits.

    Callers must apply the smalltalk / empty-evidence / out-of-range guards first; this
    assumes a question that has genuinely earned a generative answer.
    """
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
    # affected_segments describes the quotes shown under the answer, so the
    # allowed list is the segments THIS evidence carries — not the whole
    # taxonomy. Offering the taxonomy let the model name a segment it had read
    # off the corpus-totals block ("which segment is most frustrated?" reported
    # High Value Electronics Gambler with that segment in none of the 8 quotes),
    # and the UI renders the field immediately above Supporting Evidence, where
    # it reads as a description of them. Corpus totals still carry any claim
    # about scale or ranking — in the prose, where the figure is stated and
    # attributed, not as an unbacked chip.
    #
    # Same list in the prompt and in _coerce: asking for a label that is then
    # discarded just moves the inconsistency out of sight.
    seg_choices = _segment_labels(evidence)
    system_prompt = (
        "You are a product research assistant. Answer strictly from the numbered "
        "evidence quotes below — real Blinkit user reviews. Do not invent facts or "
        "use outside knowledge for the summary/themes/segments. Respond with ONLY a "
        "JSON object, no markdown fences: "
        '{"in_scope": true or false, "smalltalk": true or false, '
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
        "A greeting, a thank-you or a goodbye is NEITHER of those cases: set "
        "smalltalk=true (with in_scope=false) and make executive_summary a short, warm "
        "reply that invites a question about what shoppers say in their reviews. Never "
        "tell someone who said hello that their question cannot be answered. "
        "Otherwise in_scope=true. A question about shopper behaviour, segments, barriers, "
        "categories, discovery or sentiment is ALWAYS in scope — including when the "
        "retrieved quotes cover it only partly. Never decline such a question: answer it "
        "from the corpus totals and whatever the quotes do support, and say plainly which "
        "part is thinly evidenced. Weak evidence is a caveat to state, not a reason to "
        "refuse. "
        "theme_breakdown MUST use only these exact labels, and only those actually "
        f"evidenced in the quotes: {', '.join(THEME_CHOICES)}. "
        + ("affected_segments MUST use only these exact labels — the shopper segments "
           "the quotes below actually carry — and only where the quote for that group "
           f"supports the point: {', '.join(seg_choices)}. "
           if seg_choices else
           "affected_segments MUST be an empty list: none of the quotes below carries a "
           "shopper segment, so there is no segment this evidence can name. ") +
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
    # v9: greetings get a warm reply rather than the refusal. v8 added the
    # in_scope gate, so cached v6 answers (written before the model could decline)
    # must not be served for out-of-scope questions; v7 scoped that gate on
    # evidence fit as well as subject, which declined real questions whose quotes
    # were only a partial match.
    # v10: affected_segments is constrained to the segments the retrieved quotes
    # carry, so cached v9 answers (free to name any segment in the taxonomy, and
    # observed doing it from the corpus-totals block) must not be served.
    return {
        "system_prompt": system_prompt,
        "user_content": user_content,
        "prompt_version": PROMPT_VERSION,
        "seg_choices": seg_choices,
    }


def generate_structured_answer(query: str, evidence: List[dict], matched_themes: List[dict]) -> dict:
    """Returns {executive_summary, theme_breakdown: [str], affected_segments: [str],
    product_recommendations: [str], method}. Tries Gemini for a real synthesis first
    (subject to the shared daily quota); falls back to a deterministic summary built
    entirely from the enrichment labels already attached to the retrieved evidence —
    never fabricated, always traceable to real records. product_recommendations is the
    one field allowed to be judgment rather than pure evidence extraction — the
    project's insight-only constraint (docs/ProblemStatement.md) is intentionally
    relaxed here at the user's explicit request."""
    # Safety net: the tab short-circuits small talk before retrieval, but this keeps any
    # other caller from routing "hi" into the refusal path.
    kind = detect_smalltalk(query)
    if kind:
        return smalltalk_answer(kind)

    if not evidence:
        return _out_of_scope("No matching evidence found in the indexed corpus for this question.")

    if is_out_of_retrieval_range(evidence):
        return _out_of_scope(
            "That question isn't something the Blinkit review corpus can speak to — nothing "
            "in it is close to this topic, so there is no evidence to answer from."
        )

    # Deliberately not gated on GEMINI_API_KEY being present. call_llm checks the disk
    # cache — including the committed seed cache — before it needs a key at all, so
    # gating here meant a keyless deployment skipped straight to the extractive answer
    # while a perfectly good written answer sat unread on disk. A missing key is now
    # call_llm's business: it logs and returns None, and the fallback below still runs.
    try:
        from src.llm import DailyQuotaExhausted, call_llm

        req = build_answer_request(query, evidence)
        seg_choices = req["seg_choices"]
        raw = call_llm(req["system_prompt"], req["user_content"],
                       req["prompt_version"], json_mode=True)
        if raw:
            import re

            cleaned = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
            data = json.loads(cleaned)
            if data.get("smalltalk") is True:
                reply = smalltalk_answer("greeting")
                if data.get("executive_summary"):
                    reply["executive_summary"] = data["executive_summary"]
                return reply
            if data.get("in_scope") is False:
                return _out_of_scope(
                    data.get("executive_summary")
                    or "That question is outside what the Blinkit review corpus can answer."
                )
            return {
                "executive_summary": data.get("executive_summary", ""),
                # Enforced, not merely requested — see _coerce.
                "theme_breakdown": _coerce(data.get("theme_breakdown"), THEME_CHOICES),
                "affected_segments": _coerce(data.get("affected_segments"), seg_choices),
                "product_recommendations": data.get("product_recommendations", []),
                "method": "gemini",
            }
    except DailyQuotaExhausted:
        st.info("Gemini daily quota exhausted — showing an extractive (non-generative) summary instead.")
    except Exception:
        # Falling through to the extractive answer is the right behaviour — it is
        # evidence-grounded and complete, so the user still gets a real answer. What
        # was wrong was doing it silently: a rate-limited call, a timeout and a
        # malformed response all looked identical to a working app, and the quality
        # drop was invisible from the outside. The log line is what makes a
        # degradation on a deployed instance diagnosable at all.
        logger.exception("Generative answer failed; using the extractive fallback.")

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
