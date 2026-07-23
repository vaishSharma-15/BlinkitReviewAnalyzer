"""Overview tab: a light 'Discovery Health Overview' dashboard in the Blinkit palette,
modelled on the spotify-discovery-intel reference layout. Every figure is computed from
the real enriched corpus via app.ui helpers; the whole page is one HTML flush so the
grid alignment is exact.
"""
import pandas as pd
import streamlit as st

from app import ui
from app.data import load_enriched_df, load_themes_df


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
    classified = int((df["theme_id"] != "unclassified").sum()) if "theme_id" in df.columns else total

    parts = [
        ui.hero("🔍", "Reviews Dashboard", "Discovery Health Overview",
                "Why Blinkit users stay inside familiar shopping categories — every label read by an LLM, not keywords.",
                pill=f"● {ui.fmt(total)} reviews analyzed"),
        _sources(df),
        _kpis(total, n_sources, classified, avg_rating, sent_score, pos),
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
                     f'<div class="ui-src-count">{ui.fmt(len(sub))}</div>'
                     f'<div class="ui-src-metric">{metric}</div></div>')
    return f'<div class="ui-label">Sources Analyzed</div><div class="ui-g4">{"".join(cards)}</div>'


def _kpis(total, n_sources, classified, avg_rating, sent_score, pos):
    tiles = [
        ("📝", "Total Reviews", ui.fmt(total), f"Across {n_sources} sources"),
        ("🧭", "Themed Reviews", ui.fmt(classified), f"{classified/total:.0%} fit a theme"),
        ("⭐", "Avg Rating", f"{avg_rating:.2f}", "Store ratings (1–5★)"),
        ("🙂", "Sentiment Score", str(sent_score), "0–100 overall mood"),
        ("📊", "Positive Share", f"{pos:.0%}", "of all reviews"),
    ]
    cells = "".join(
        f'<div class="ui-stat"><div class="ui-stat-icon">{i}</div>'
        f'<div class="ui-stat-body"><div class="ui-stat-label">{l}</div>'
        f'<div class="ui-stat-sub">{s}</div></div>'
        f'<div class="ui-stat-value">{v}</div></div>'
        for i, l, v, s in tiles
    )
    return f'<div class="ui-g5 ui-row">{cells}</div>'


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
                    f'<div class="ui-lolli-val">{ui.fmt(cnt)}</div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">What Users Struggle With</div>'
            f'<div class="ui-card-sub">Barrier mentions by frequency, across {ui.fmt(len(themed))} of {ui.fmt(len(df))} reviews.</div>'
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


def _segments(df):
    seg_cols = ["price_sensitivity", "family_stage", "has_pet", "city_tier"]
    labels = {
        "price_sensitivity=high": ("Price-Sensitive", "💰"), "price_sensitivity=low": ("Price-Insensitive", "💳"),
        "family_stage=parent_young_child": ("Parents", "🍼"), "family_stage=single": ("Singles", "🧍"),
        "family_stage=couple": ("Couples", "👥"), "has_pet=yes": ("Pet Owners", "🐾"),
        "city_tier=metro": ("Metro", "🏙️"), "city_tier=tier2": ("Tier-2 City", "🏘️"),
    }
    rows = []
    for col in seg_cols:
        known = df[df[col] != "unknown"]
        for value, grp in known.groupby(col):
            if len(grp) < 10:
                continue
            label, icon = labels.get(f"{col}={value}", (f"{col}={value}", "•"))
            rows.append(((grp["sentiment"] < -0.2).mean(), len(grp), label, icon))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    rows = rows[:5]
    if not rows:
        return '<div class="ui-card"><div class="ui-card-title">Who\'s Most Frustrated</div><div class="ui-muted">No segment signals detected in this corpus.</div></div>'
    body = "".join(
        f'<div class="ui-seg-row"><div class="ui-seg-rank">{i}</div>'
        f'<div class="ui-seg-name">{icon}&nbsp;&nbsp;{label}</div>'
        f'<div class="ui-seg-rate">{rate:.0%}</div><div class="ui-seg-n">{ui.fmt(n)}</div></div>'
        for i, (rate, n, label, icon) in enumerate(rows, start=1)
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
    years = sorted(dated["year"].unique())
    cards = []
    for y in years:
        sub = dated[dated["year"] == y]
        n = len(sub)
        seg = "".join(
            f'<div style="width:{c/n*100:.1f}%;background:{ui.SOURCE_META.get(s, (s, ui.MUTED))[1]};"></div>'
            for s, c in sub["source"].value_counts().items()
        )
        cards.append(f'<div class="ui-year"><div class="ui-year-head"><span>{y}</span>'
                     f'<span class="ui-year-n">{ui.fmt(n)}</span></div><div class="ui-year-bar">{seg}</div></div>')
    legend = "".join(
        f'<div class="ui-leg" style="padding:0;font-size:12px;color:{ui.MUTED};">'
        f'<span class="ui-dot" style="background:{ui.SOURCE_META.get(s, (s, ui.MUTED))[1]};"></span>{ui.SOURCE_META.get(s, (s, ui.MUTED))[0]}</div>'
        for s in df["source"].value_counts().index[:5]
    )
    return (f'<div class="ui-card"><div class="ui-card-title">Coverage by Year ({years[0]}–{years[-1]})</div>'
            f'<div class="ui-card-sub">Reviews per year and their source mix.</div>'
            f'<div class="ui-g4">{"".join(cards)}</div>'
            f'<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:14px;">{legend}</div></div>')


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
