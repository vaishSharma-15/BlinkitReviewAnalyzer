"""Overview tab: a light 'Discovery Health Overview' dashboard in the Blinkit palette.
Every figure is computed from the real enriched corpus via app.ui helpers; the whole page
is one HTML flush so grid alignment is exact.
"""
import streamlit as st

from app import ui
from app.data import load_enriched_df, load_funnel


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

    parts = [
        ui.hero("grid", "Blinkit · Voice of Customer", "Discovery Health Overview",
                f"What real Blinkit reviewers reveal about why shoppers stay inside a few familiar "
                f"categories — {ui.fmt_full(total)} public reviews, each classified by an LLM, not keyword rules.",
                pill=f"{ui.fmt_full(total)} reviews analyzed"),
        _sources(df),
        _kpis(total, n_sources, classified, avg_rating, sent_score, pos),
        '<div class="ui-row">', _funnel(df, total, classified), "</div>",
        '<div class="ui-row ui-split">', _struggles(df), _concentration(df), "</div>",
        '<div class="ui-row ui-split">', _segments(df), _donut(pos, neu, neg), "</div>",
        '<div class="ui-row">', _coverage(df), "</div>",
        '<div class="ui-row">', _recent(df), "</div>",
    ]
    ui.flush(parts)


def _sources(df):
    counts = df["source"].value_counts()
    cards = []
    for src in counts.index[:4]:
        name, color = ui.SOURCE_META.get(src, (src.title(), ui.MUTED))
        sub = df[df["source"] == src]
        if src in ("play", "appstore") and sub["rating"].notna().any():
            metric = f"{sub['rating'].dropna().mean():.1f}★ avg rating"
        else:
            metric = f"{round((sub['sentiment'].mean()+1)/2*100)}/100 sentiment"
        cards.append(f'<div class="ui-src" style="border-top:3px solid {color};">'
                     f'<div class="ui-src-name">{name}</div>'
                     f'<div class="ui-src-count">{ui.fmt_full(len(sub))}</div>'
                     f'<div class="ui-src-metric">{metric}</div></div>')
    return f'<div class="ui-label">Sources Analyzed</div><div class="ui-g4">{"".join(cards)}</div>'


def _stat(icon_name, label, value, sub):
    return (f'<div class="ui-stat"><div class="ui-stat-icon">{ui.icon(icon_name, size=17, color=ui.YELLOW_DK)}</div>'
            f'<div class="ui-stat-body"><div class="ui-stat-label">{label}</div>'
            f'<div class="ui-stat-sub">{sub}</div></div>'
            f'<div class="ui-stat-value">{value}</div></div>')


def _kpis(total, n_sources, classified, avg_rating, sent_score, pos):
    tiles = [
        _stat("file-text", "Total Reviews", ui.fmt_full(total), f"Across {n_sources} sources"),
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


def _segments(df):
    rows = []
    for col in ["price_sensitivity", "family_stage", "has_pet", "city_tier"]:
        known = df[df[col] != "unknown"]
        for value, grp in known.groupby(col):
            if len(grp) < 10:
                continue
            label = SEG_LABELS.get(f"{col}={value}", f"{col}={value}")
            rows.append(((grp["sentiment"] < -0.2).mean(), len(grp), label, SEG_ICON.get(col, "user")))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    rows = rows[:5]
    if not rows:
        return '<div class="ui-card"><div class="ui-card-title">Who\'s Most Frustrated</div><div class="ui-muted">No segment signals detected in this corpus.</div></div>'
    body = "".join(
        f'<div class="ui-seg-row"><div class="ui-seg-rank">{i}</div>'
        f'<div class="ui-seg-name" style="display:flex;align-items:center;gap:8px;">'
        f'<span style="color:{ui.FAINT};">{ui.icon(ic, size=15, color=ui.MUTED)}</span>{label}</div>'
        f'<div class="ui-seg-rate">{rate:.0%}</div><div class="ui-seg-n">{ui.fmt_full(n)}</div></div>'
        for i, (rate, n, label, ic) in enumerate(rows, start=1)
    )
    return (f'<div class="ui-card"><div class="ui-card-title">Who\'s Most Frustrated</div>'
            f'<div class="ui-card-sub">Negative-sentiment rate by user segment</div>'
            f'<div class="ui-seg-head"><div>#</div><div>Segment</div><div>Rate</div><div>Reviews</div></div>{body}</div>')


def _donut(pos, neu, neg):
    p, nu, ng = pos * 100, neu * 100, neg * 100
    a1, a2 = p, p + nu
    return (f'<div class="ui-card"><div class="ui-card-title">Sentiment Breakdown</div>'
            f'<div class="ui-card-sub">Share of all reviews</div><div class="ui-donut-wrap">'
            f'<div class="ui-donut" style="background:conic-gradient({ui.POS} 0% {a1:.1f}%,{ui.NEU} {a1:.1f}% {a2:.1f}%,{ui.NEG} {a2:.1f}% 100%);">'
            f'<div class="ui-donut-hole"><div class="ui-donut-big" style="color:{ui.POS};">{p:.0f}%</div>'
            f'<div class="ui-donut-lbl">Positive</div></div></div>'
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
        breakdown = "".join(
            f'<span><span class="ui-dot" style="width:8px;height:8px;background:{ui.SOURCE_META.get(s, (s, ui.MUTED))[1]};"></span>'
            f'{ui.SOURCE_META.get(s, (s, ui.MUTED))[0]}&nbsp;<b style="color:{ui.TXT};">{ui.fmt_full(c)}</b></span>'
            for s, c in vc.items()
        )
        cards.append(f'<div class="ui-year"><div class="ui-year-head"><span>{y}</span>'
                     f'<span class="ui-year-n">{ui.fmt_full(n)}</span></div>'
                     f'<div class="ui-year-bar">{seg}</div>'
                     f'<div class="ui-year-src">{breakdown}</div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">Coverage by Year ({years[0]}–{years[-1]})</div>'
            f'<div class="ui-card-sub">Reviews per year and their source mix. Bars use a minimum width so smaller '
            f'sources stay visible next to Play Store\'s volume — exact counts are listed under each year.</div>'
            f'<div class="ui-g4">{"".join(cards)}</div></div>')


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
