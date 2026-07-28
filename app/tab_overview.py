"""Overview tab: a light 'Blinkit Reviews Discovery Engine' dashboard in the Blinkit palette.
Every figure is computed from the real enriched corpus via app.ui helpers; the whole page
is one HTML flush so grid alignment is exact.
"""
import pandas as pd
import streamlit as st

from app import ui
from app.data import (
    load_enriched_df,
    load_funnel,
    load_segment_assignments,
    load_segment_taxonomy,
    scraped_count,
)


def render():
    df = load_enriched_df()
    if df.empty:
        st.warning("No enriched data yet — run `python -m src.enrich` first.")
        return

    total = len(df)
    n_sources = df["source"].nunique()
    avg_rating = df["rating"].dropna().mean()
    avg_sent = df["sentiment"].mean()
    sent_score = round((avg_sent + 1) / 2 * 100)
    pos = (df["sentiment"] > 0.2).mean()
    neu = df["sentiment"].between(-0.2, 0.2).mean()
    neg = (df["sentiment"] < -0.2).mean()
    classified = int((df["theme_id"] != "unclassified").sum())
    # Everything actually pulled from the sources, before the dedup/relevance gates —
    # the pill reports the scrape, the funnel below shows how it narrows to `total`.
    scraped = scraped_count(total)

    parts = [
        ui.hero("grid", "Blinkit · Voice of Customer", "Blinkit Reviews Discovery Engine",
                f"What real Blinkit reviewers reveal about why shoppers stay inside a few familiar "
                f"categories — {ui.fmt_full(scraped)} reviews scraped across {n_sources} sources, "
                f"narrowed to {ui.fmt_full(total)} classified by an LLM, not keyword rules.",
                pill=f"{ui.fmt_full(scraped)} reviews scraped"),
        _sources(df),
        _kpis(total, n_sources, classified, avg_rating, sent_score, pos),
        '<div class="ui-row">', _funnel(df, total, classified), "</div>",
        '<div class="ui-row ui-split">', _struggles(df), _concentration(df), "</div>",
        '<div class="ui-row ui-split">', _segments(df), _donut(pos, neu, neg, total), "</div>",
        '<div class="ui-row">', _behaviour_segments(df), "</div>",
        '<div class="ui-row">', _segment_profile(df), "</div>",
        '<div class="ui-row">', _coverage(df), "</div>",
        '<div class="ui-row">', _recent(df), "</div>",
    ]
    ui.flush(parts)


def _sources(df):
    counts = df["source"].value_counts()
    cards = []
    for src in counts.index:  # every source with data, not just the top 4
        name, color = ui.SOURCE_META.get(src, (src.title(), ui.MUTED))
        sub = df[df["source"] == src]
        # Store/product sources carry star ratings; social sources (YouTube/Q-Comm) don't.
        if src in ("play", "appstore", "product_review") and sub["rating"].notna().any():
            metric = f"{sub['rating'].dropna().mean():.1f}★ avg rating"
        else:
            metric = f"{round((sub['sentiment'].mean()+1)/2*100)}/100 sentiment"
        cards.append(f'<div class="ui-src" style="border-top:3px solid {color};">'
                     f'<div class="ui-src-name">{name}</div>'
                     f'<div class="ui-src-count">{ui.fmt_full(len(sub))}</div>'
                     f'<div class="ui-src-metric">{metric}</div></div>')
    grid = "ui-g5" if len(cards) == 5 else "ui-g4"
    return f'<div class="ui-label">Sources Analyzed</div><div class="{grid}">{"".join(cards)}</div>'


def _stat(icon_name, label, value, sub):
    return (f'<div class="ui-stat"><div class="ui-stat-icon">{ui.icon(icon_name, size=17, color=ui.YELLOW_DK)}</div>'
            f'<div class="ui-stat-body"><div class="ui-stat-label">{label}</div>'
            f'<div class="ui-stat-sub">{sub}</div></div>'
            f'<div class="ui-stat-value">{value}</div></div>')


def _kpis(total, n_sources, classified, avg_rating, sent_score, pos):
    tiles = [
        _stat("file-text", "Reviews Analyzed", ui.fmt_full(total), f"Total across {n_sources} sources"),
        _stat("compass", "Themed Reviews", ui.fmt_full(classified), f"{classified/total:.0%} fit a theme"),
        _stat("star", "Avg Rating", f"{avg_rating:.2f}", "Store ratings (1–5★)"),
        _stat("smile", "Sentiment Score", str(sent_score), "0–100 overall mood"),
        _stat("pie", "Positive Share", f"{pos:.0%}", "of all reviews"),
    ]
    return f'<div class="ui-g5 ui-row">{"".join(tiles)}</div>'


def _funnel(df, total, classified):
    f = load_funnel()
    fn = f.get("normalized", {}).get("funnel", {})
    raw = fn.get("raw") or total
    cleaned = fn.get("after_near_dedup") or total
    steps = [
        ("Collected", raw, "#334155", "raw public reviews pulled from all sources"),
        ("Cleaned & deduped", cleaned, "#0ea5e9", "after length, spam and near-duplicate filters"),
        ("Relevant to research", total, "#d97706", "kept by the LLM relevance gate"),
        ("Classified into themes", classified, ui.GREEN, "assigned one of the 9 discovery themes"),
    ]
    rows = []
    for label, count, color, desc in steps:
        pct = count / raw * 100 if raw else 0
        rows.append(f'<div class="ui-funnel-row"><div class="ui-funnel-label">{label}</div>'
                    f'<div class="ui-funnel-track"><div class="ui-funnel-fill" style="width:{max(pct,3):.1f}%;background:{color};"></div></div>'
                    f'<div class="ui-funnel-meta"><b>{ui.fmt_full(count)}</b> · {pct:.0f}% of collected<br>'
                    f'<span style="font-size:11px;">{desc}</span></div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">Collection Funnel</div>'
            f'<div class="ui-card-sub">From everything scraped down to the themed corpus this dashboard runs on.</div>'
            f'<div class="ui-funnel">{"".join(rows)}</div></div>')


def _struggles(df):
    themed = df[df["barrier_type"] != "none"]
    counts = themed["barrier_type"].value_counts().head(7)
    if counts.empty:
        return '<div class="ui-card"><div class="ui-card-title">What Users Struggle With</div><div class="ui-muted">No barrier-labeled items yet.</div></div>'
    top = int(counts.iloc[0])
    rows = []
    for i, (barrier, cnt) in enumerate(counts.items()):
        label = ui.BARRIER_LABELS.get(barrier, barrier)
        color = ui.CAT[i % len(ui.CAT)]
        pct = cnt / top * 100
        rows.append(f'<div class="ui-lolli"><div class="ui-lolli-label">'
                    f'<span class="ui-dot" style="background:{color};"></span>{label}</div>'
                    f'<div class="ui-lolli-track"><div class="ui-lolli-fill" style="width:{pct:.0f}%;background:{color};"></div>'
                    f'<span class="ui-lolli-knob" style="left:{pct:.0f}%;border-color:{color};"></span></div>'
                    f'<div class="ui-lolli-val">{ui.fmt_full(cnt)}</div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">What Users Struggle With</div>'
            f'<div class="ui-card-sub">Barrier mentions by frequency, across {ui.fmt_full(len(themed))} of {ui.fmt_full(len(df))} reviews.</div>'
            f'{"".join(rows)}</div>')


def _concentration(df):
    themed = df[df["barrier_type"] != "none"]
    counts = themed["barrier_type"].value_counts()
    if counts.empty:
        return '<div class="ui-card"><div class="ui-card-title">The Concentration Problem</div><div class="ui-muted">No barriers yet.</div></div>'
    total_b = int(counts.sum())
    top_barrier = counts.index[0]
    top_pct = counts.iloc[0] / total_b * 100
    bars = []
    for i, (barrier, cnt) in enumerate(counts.head(3).items()):
        label = ui.BARRIER_LABELS.get(barrier, barrier)
        color = ui.CAT[i % len(ui.CAT)]
        pct = cnt / total_b * 100
        bars.append(f'<div class="ui-rep-row"><div class="ui-rep-head"><span>{label}</span>'
                    f'<span style="color:{color};font-weight:800;">{pct:.0f}%</span></div>'
                    f'<div class="ui-rep-track"><div class="ui-rep-fill" style="width:{pct:.0f}%;background:{color};"></div></div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">The Concentration Problem</div>'
            f'<div class="ui-card-sub">Where the barrier pain concentrates</div>'
            f'<div class="ui-rep-hero"><div class="ui-rep-big">{top_pct:.0f}%</div>'
            f'<div class="ui-rep-sub">of all barrier mentions are <b>{ui.BARRIER_LABELS.get(top_barrier, top_barrier)}</b> — '
            f'the single largest blocker to category exploration.</div></div>{"".join(bars)}</div>')


SEG_ICON = {"price_sensitivity": "tag", "family_stage": "users", "has_pet": "heart", "city_tier": "pin"}
SEG_LABELS = {
    "price_sensitivity=high": "Price-Sensitive", "price_sensitivity=low": "Price-Insensitive",
    "family_stage=parent_young_child": "Parents", "family_stage=single": "Singles",
    "family_stage=couple": "Couples", "has_pet=yes": "Pet Owners",
    "city_tier=metro": "Metro", "city_tier=tier2": "Tier-2 City",
}


# The four segment dimensions the enrichment pipeline assigns (src/schemas.py), in the
# order they are worth reading: the one with real coverage first.
SEG_DIMENSIONS = [
    ("price_sensitivity", "Price sensitivity", ["high", "low"]),
    ("family_stage", "Life stage", ["parent_young_child", "single", "couple"]),
    ("city_tier", "City tier", ["metro", "tier2"]),
    ("has_pet", "Pet ownership", ["yes"]),
]

# Below this a rate is noise, not a measurement. Kept identical to the floor
# rag_engine.corpus_stats applies, so the chat answer and this panel agree on which
# segments are reportable.
MIN_SEGMENT_N = 10


def _seg_rows(df):
    """(dimension label, segment label, n, negative rate) for every labelled segment,
    including the ones too small to report — they are shown flagged rather than dropped,
    because a segment silently missing from the chart reads as a segment with no data."""
    out = []
    for col, dim_label, values in SEG_DIMENSIONS:
        for value in values:
            grp = df[df[col] == value]
            if grp.empty:
                continue
            label = SEG_LABELS.get(f"{col}={value}", f"{col}={value}")
            out.append((dim_label, label, len(grp), float((grp["sentiment"] < -0.2).mean())))
    return out


def segmented(df):
    """`df` joined to its behaviour segment, keeping only reviews that earned one.

    This is what "user segment" means everywhere in the app now: the behaviour-defined
    segments derived from the reviews (src/segment.py), not the demographic slots the
    enrichment pass leaves unknown for 98% of the corpus.
    """
    assignments = load_segment_assignments()
    if assignments.empty or df.empty:
        return pd.DataFrame()
    names = {s["segment_id"]: s["name"] for s in load_segment_taxonomy()}
    merged = df.merge(assignments, on="id", how="inner")
    merged = merged[merged["segment_id"] != "unassigned"].copy()
    merged["segment_name"] = merged["segment_id"].map(names)
    return merged[merged["segment_name"].notna()]


def _segments(df):
    """Negative-sentiment rate per segment, against the corpus average.

    A bare ranking said which segment was angriest but not whether that was unusual —
    at a 60% corpus-wide negative rate, a 59% segment is ordinary. The dashed rule is
    the corpus average, so the comparison is positional and the bars need no second
    colour to carry it.
    """
    seg = segmented(df)
    if seg.empty:
        return ('<div class="ui-card"><div class="ui-card-title">Who\'s Most Frustrated</div>'
                '<div class="ui-muted">No segments assigned yet — run '
                '<code>python -m src.segment discover</code> then <code>assign</code>.</div></div>')
    corpus_rate = float((df["sentiment"] < -0.2).mean())
    rows = []
    for name, grp in seg.groupby("segment_name"):
        if len(grp) >= MIN_SEGMENT_N:
            rows.append((name, len(grp), float((grp["sentiment"] < -0.2).mean())))
    rows.sort(key=lambda r: (-r[2], -r[1]))

    bars = []
    for label, n, rate in rows:
        bars.append(
            f'<div class="ui-hb wide" title="{ui.esc(label)}: {rate:.0%} negative across {n:,} reviews">'
            f'<div class="ui-hb-label">{ui.esc(label)}</div>'
            f'<div class="ui-hb-track"><div class="ui-hb-fill" style="width:{rate*100:.1f}%;background:{ui.NEG};"></div>'
            f'<div class="ui-hb-ref" style="left:{corpus_rate*100:.1f}%;"></div></div>'
            f'<div class="ui-hb-val">{rate:.0%} <span>· {ui.fmt_full(n)}</span></div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">Who\'s Most Frustrated</div>'
            f'<div class="ui-card-sub">Negative-sentiment rate by shopper segment, against the '
            f'{corpus_rate:.0%} corpus average. Value shows rate · reviews.</div>'
            f'{"".join(bars)}'
            f'<div class="ui-hb-reflabel" style="margin-left:196px;">Dashed rule = {corpus_rate:.0%} corpus '
            f'average · segments under {MIN_SEGMENT_N} reviews are excluded</div></div>')


def _behaviour_segments(df):
    """The segments derived from the reviews themselves (src/segment.py).

    Every bar here is a count of reviews whose own words earned the label — the
    pipeline threw away any assignment whose evidence quote could not be found in the
    review text. The unassigned share is shown rather than hidden: it is most of the
    corpus, and it is what strictness costs.
    """
    taxonomy = load_segment_taxonomy()
    assignments = load_segment_assignments()
    if not taxonomy or assignments.empty:
        return ""

    names = {s["segment_id"]: s["name"] for s in taxonomy}
    defs = {s["segment_id"]: s["definition"] for s in taxonomy}
    quotes = dict(zip(assignments["id"], assignments["evidence_quote"]))
    merged = df.merge(assignments, on="id", how="inner")
    labelled = len(merged)
    if not labelled:
        return ""

    counts = merged[merged["segment_id"] != "unassigned"]["segment_id"].value_counts()
    assigned = int(counts.sum())
    biggest = int(counts.iloc[0]) if not counts.empty else 1

    bars = []
    for seg_id, n in counts.items():
        bars.append(
            f'<div class="ui-hb wide" title="{ui.esc(defs.get(seg_id, seg_id))}">'
            f'<div class="ui-hb-label">{ui.esc(names.get(seg_id, seg_id))}</div>'
            f'<div class="ui-hb-track"><div class="ui-hb-fill" style="width:{n/biggest*100:.1f}%;background:{ui.CAT[1]};"></div></div>'
            f'<div class="ui-hb-val">{ui.fmt_full(int(n))} <span>· {n/assigned:.0%}</span></div></div>')

    # One real quote per segment, so the definition is never the only thing on offer.
    cards = []
    for seg_id, n in list(counts.items())[:4]:
        grp = merged[merged["segment_id"] == seg_id]
        example = next((quotes.get(i, "") for i in grp["id"] if quotes.get(i)), "")
        if not example:
            continue
        cards.append(
            f'<div class="ui-segcard"><div style="color:{ui.TXT};font-size:13px;font-weight:700;">'
            f'{ui.esc(names.get(seg_id, seg_id))}</div>'
            f'<div style="color:{ui.MUTED};font-size:12px;line-height:1.5;margin:4px 0 8px;">'
            f'{ui.esc(defs.get(seg_id, ""))}</div>'
            f'<div style="color:{ui.TXT};font-size:12px;font-style:italic;line-height:1.5;'
            f'border-left:2px solid {ui.YELLOW};padding-left:9px;">"{ui.esc(example[:180])}"</div></div>')

    return (
        f'<div class="ui-card"><div class="ui-card-title">Shopper Segments, Read From The Reviews</div>'
        f'<div class="ui-card-sub">Behaviour-defined segments the LLM derived from the corpus, then '
        f'assigned review by review. A label was only kept when a verbatim quote from that review '
        f'supported it — {ui.fmt_full(assigned)} of {ui.fmt_full(labelled)} reviews '
        f'({assigned/labelled:.0%}) cleared that bar.</div>'
        f'{"".join(bars)}'
        f'<div class="ui-hb-reflabel" style="margin-left:196px;">Value shows reviews · share of all segmented reviews. '
        f'The remaining {ui.fmt_full(labelled - assigned)} reviews state no segment-defining behaviour '
        f'and are left unassigned rather than guessed.</div>'
        f'<div class="ui-secline">Evidence</div><div class="ui-g4">{"".join(cards)}</div></div>')


def _segment_profile(df):
    """The demographic attributes reviewers happen to disclose about themselves.

    No longer "the segmentation" — that is now the behaviour-defined set above. This
    stays as a secondary, clearly-bounded panel because the numbers are real and
    occasionally useful, but it must never be mistaken for a shopper segmentation: a
    review rarely says whether its writer has children or a dog, so three of the four
    dimensions are unknown for nearly everyone. Sizes are counts, coverage is a share of
    the corpus; the two are shown separately because they share no scale.
    """
    total = len(df)
    rows = _seg_rows(df)
    if not rows:
        return ""
    biggest = max(r[2] for r in rows)

    size_html = []
    current_dim = None
    for dim_label, label, n, _rate in rows:
        if dim_label != current_dim:
            size_html.append(f'<div class="ui-dim">{dim_label}</div>')
            current_dim = dim_label
        flag = f'<span class="ui-flag" title="Under {MIN_SEGMENT_N} reviews — too small to report a rate">LOW n</span>' \
            if n < MIN_SEGMENT_N else ""
        size_html.append(
            f'<div class="ui-hb" title="{ui.esc(label)}: {n:,} reviews, {n/total:.1%} of the corpus">'
            f'<div class="ui-hb-label">{label}{flag}</div>'
            f'<div class="ui-hb-track"><div class="ui-hb-fill" style="width:{n/biggest*100:.1f}%;background:{ui.CAT[1]};"></div></div>'
            f'<div class="ui-hb-val">{ui.fmt_full(n)} <span>· {n/total:.1%}</span></div></div>')

    cov_html = []
    for col, dim_label, _values in SEG_DIMENSIONS:
        labelled = int((df[col] != "unknown").sum())
        share = labelled / total if total else 0
        cov_html.append(
            f'<div class="ui-hb" title="{dim_label}: {labelled:,} of {total:,} reviews carry a label">'
            f'<div class="ui-hb-label">{dim_label}</div>'
            f'<div class="ui-stack">'
            f'<div style="width:{max(share*100, 0.4):.1f}%;background:{ui.CAT[1]};"></div>'
            f'<div style="width:{(1-share)*100:.1f}%;background:{ui.BORDER};"></div></div>'
            f'<div class="ui-hb-val">{share:.1%} <span>· {ui.fmt_full(labelled)}</span></div></div>')

    return (
        f'<div class="ui-card"><div class="ui-card-title">Self-Disclosed Demographics</div>'
        f'<div class="ui-card-sub">Secondary to the shopper segments above, and not a segmentation: '
        f'these are demographic attributes a reviewer happened to mention about themselves, on the '
        f'rare occasions they did.</div>'
        f'<div class="ui-g2">'
        f'<div><div class="ui-secline">Reviews disclosing each attribute</div>{"".join(size_html)}</div>'
        f'<div><div class="ui-secline">Labelled coverage</div>'
        f'<div class="ui-legend"><span><i style="background:{ui.CAT[1]};"></i>Labelled</span>'
        f'<span><i style="background:{ui.BORDER};"></i>Unknown</span></div>'
        f'{"".join(cov_html)}'
        f'<div style="color:{ui.MUTED};font-size:12px;line-height:1.55;margin-top:14px;">'
        f'Only price sensitivity is labelled on a meaningful slice of the corpus. An app-store '
        f'review rarely reveals whether its writer has children, a pet or lives in a metro, so '
        f'the enricher leaves those unknown rather than guessing — read the life-stage, city and '
        f'pet splits as directional, and the price split as measured.</div>'
        f'</div></div></div>')


def _donut(pos, neu, neg, total):
    p, nu, ng = pos * 100, neu * 100, neg * 100
    a1, a2 = p, p + nu
    # Centre carries the corpus size rather than the positive share: a lone "29%
    # POSITIVE" over a mostly-negative ring read as the headline figure.
    return (f'<div class="ui-card"><div class="ui-card-title">Sentiment Breakdown</div>'
            f'<div class="ui-card-sub">Share of all reviews</div><div class="ui-donut-wrap">'
            f'<div class="ui-donut" style="background:conic-gradient({ui.POS} 0% {a1:.1f}%,{ui.NEU} {a1:.1f}% {a2:.1f}%,{ui.NEG} {a2:.1f}% 100%);">'
            f'<div class="ui-donut-hole"><div class="ui-donut-big" style="color:{ui.TXT};">{ui.fmt_full(total)}</div>'
            f'<div class="ui-donut-lbl">Reviews</div></div></div>'
            f'<div style="flex:1;"><div class="ui-leg"><span class="ui-dot" style="background:{ui.POS};"></span>Positive<span class="ui-leg-val">{p:.0f}%</span></div>'
            f'<div class="ui-leg"><span class="ui-dot" style="background:{ui.NEU};"></span>Neutral<span class="ui-leg-val">{nu:.0f}%</span></div>'
            f'<div class="ui-leg"><span class="ui-dot" style="background:{ui.NEG};"></span>Negative<span class="ui-leg-val">{ng:.0f}%</span></div></div></div></div>')


def _coverage(df):
    dated = df.dropna(subset=["date_parsed"]).copy()
    if dated.empty:
        return ""
    dated["year"] = dated["date_parsed"].dt.year
    # Drop years with too few reviews to be meaningful (e.g. 2024 with just 2) so the
    # chart isn't padded with a near-empty bar. Threshold keeps any year with real volume.
    MIN_YEAR_COUNT = 10
    year_counts = dated["year"].value_counts()
    years = sorted(y for y in dated["year"].unique() if year_counts[y] >= MIN_YEAR_COUNT)
    if not years:
        return ""
    dated = dated[dated["year"].isin(years)]
    cards = []
    for y in years:
        sub = dated[dated["year"] == y]
        n = len(sub)
        vc = sub["source"].value_counts()
        # flex-grow keeps the bar proportional, but min-width guarantees every present
        # source shows as a visible sliver even when Play Store dominates the volume.
        seg = "".join(
            f'<div style="flex:{c} 1 0;min-width:8px;background:{ui.SOURCE_META.get(s, (s, ui.MUTED))[1]};"></div>'
            for s, c in vc.items()
        )
        cards.append(f'<div class="ui-year"><div class="ui-year-head"><span>{y}</span>'
                     f'<span class="ui-year-n">{ui.fmt_full(n)}</span></div>'
                     f'<div class="ui-year-bar">{seg}</div></div>')
    # One shared colour key for all years (union of sources present), instead of repeating
    # the source list inside each year card.
    sources_present = dated["source"].value_counts().index
    legend = "".join(
        f'<div class="ui-leg" style="padding:0;font-size:12px;color:{ui.MUTED};">'
        f'<span class="ui-dot" style="background:{ui.SOURCE_META.get(s, (s, ui.MUTED))[1]};"></span>{ui.SOURCE_META.get(s, (s, ui.MUTED))[0]}</div>'
        for s in sources_present
    )
    return (f'<div class="ui-card"><div class="ui-card-title">Coverage by Year ({years[0]}–{years[-1]})</div>'
            f'<div class="ui-card-sub">Reviews per year and their source mix. Bars use a minimum width so smaller '
            f'sources stay visible next to Play Store\'s volume.</div>'
            f'<div class="ui-g4">{"".join(cards)}</div>'
            f'<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:16px;">{legend}</div></div>')


def _recent(df):
    recent = df.dropna(subset=["date_parsed"]).sort_values("date_parsed", ascending=False).head(6)
    cards = []
    for _, r in recent.iterrows():
        name, color = ui.SOURCE_META.get(r["source"], (r["source"].title(), ui.MUTED))
        bcol = ui.sentiment_color(r["sentiment"])
        badge = ui.sentiment_label(r["sentiment"])
        text = ui.esc((r["text"][:150] + "…") if len(r["text"]) > 150 else r["text"])
        cards.append(f'<div class="ui-rev"><div class="ui-rev-head">'
                     f'<span><span class="ui-dot" style="background:{color};"></span>{name}</span>'
                     f'<span class="ui-rev-date">{str(r["date"])[:10]}</span></div>'
                     f'<div class="ui-rev-text">{text}</div>'
                     f'<div class="ui-rev-foot"><span class="ui-badge" style="color:{bcol};border-color:{bcol}55;background:{bcol}12;">● {badge}</span></div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">Recent Reviews</div>'
            f'<div class="ui-card-sub">Latest feedback across sources</div>'
            f'<div class="ui-g3">{"".join(cards)}</div></div>')
