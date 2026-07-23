"""Analytics tab: 'Deep Discovery Analytics' — a light Blinkit-palette analytics board
modelled on the spotify-discovery-intel reference. A keyword + source + sentiment filter
bar narrows the corpus, and every panel below (sentiment split, barrier-load tiles,
donut, theme lollipop, source bars, rating distribution, segment cards) recomputes from
the filtered view.
"""
import streamlit as st

from app import ui
from app.data import load_enriched_df


def render():
    df = load_enriched_df()
    if df.empty:
        st.warning("No enriched data yet — run `python -m src.enrich` first.")
        return

    ui.flush(ui.hero("📈", "Analytics Dashboard", "Deep Discovery Analytics",
                     "Sentiment, barriers and complaint rates from LLM-classified reviews. Filter by keyword, "
                     "source or sentiment — every panel updates together."))

    # --- Filter bar (real Streamlit widgets, styled compact) ----------------
    c1, c2, c3 = st.columns([3, 1, 1])
    kw = c1.text_input("Search", placeholder="Search by keyword (e.g. fruits, expiry, Zepto)…", label_visibility="collapsed")
    src_opts = ["All sources"] + [ui.SOURCE_META.get(s, (s, ""))[0] for s in df["source"].value_counts().index]
    src_sel = c2.selectbox("Source", src_opts, label_visibility="collapsed")
    sent_sel = c3.selectbox("Sentiment", ["All sentiment", "Positive", "Neutral", "Negative"], label_visibility="collapsed")

    view = df
    if kw.strip():
        view = view[view["text"].str.contains(kw.strip(), case=False, na=False)]
    if src_sel != "All sources":
        name_to_src = {v[0]: k for k, v in ui.SOURCE_META.items()}
        if src_sel in name_to_src:
            view = view[view["source"] == name_to_src[src_sel]]
    if sent_sel == "Positive":
        view = view[view["sentiment"] > 0.2]
    elif sent_sel == "Neutral":
        view = view[view["sentiment"].between(-0.2, 0.2)]
    elif sent_sel == "Negative":
        view = view[view["sentiment"] < -0.2]

    st.caption(f"Showing **{len(view):,}** of {len(df):,} reviews matching the current filters.")

    if view.empty:
        st.info("No reviews match these filters — widen the search.")
        return

    pos = (view["sentiment"] > 0.2).mean()
    neu = view["sentiment"].between(-0.2, 0.2).mean()
    neg = (view["sentiment"] < -0.2).mean()
    barrier_share = (view["barrier_type"] != "none").mean()
    neg_barrier = ((view["barrier_type"] != "none") & (view["sentiment"] < -0.2)).mean()
    sent_score = round((view["sentiment"].mean() + 1) / 2 * 100)

    parts = [
        '<div class="ui-label">How Users Feel</div>',
        '<div class="ui-g3">',
        _feel_tile("🙂", "Positive", pos, ui.POS), _feel_tile("😐", "Neutral", neu, ui.NEU), _feel_tile("🙁", "Negative", neg, ui.NEG),
        "</div>",
        '<div class="ui-label">Barrier Load</div>',
        '<div class="ui-g3">',
        _stat_tile("🧭", "Reviews With A Barrier", f"{barrier_share:.0%}", "share flagged with a barrier type", ui.CAT[0]),
        _stat_tile("⚠️", "Negative Barrier Reviews", f"{neg_barrier:.0%}", "barrier + negative sentiment", ui.NEG),
        _stat_tile("📊", "Sentiment Score", str(sent_score), "0–100 overall mood in view", ui.GREEN),
        "</div>",
        '<div class="ui-row ui-split">', _donut(pos, neu, neg, len(view)), _theme_lolli(view), "</div>",
        '<div class="ui-row ui-split">', _source_bars(view), _rating_bars(view), "</div>",
        '<div class="ui-row">', _segments(view), "</div>",
    ]
    ui.flush(parts)


def _feel_tile(icon, label, val, color):
    return (f'<div class="ui-stat big" style="border-top-color:{color};">'
            f'<div class="ui-stat-top"><div class="ui-stat-icon" style="background:{color}18;">{icon}</div>'
            f'<div><div class="ui-stat-label">{label}</div><div class="ui-stat-sub">of reviews in view</div></div></div>'
            f'<div class="ui-stat-value" style="color:{color};">{val:.0%}</div></div>')


def _stat_tile(icon, label, val, sub, color):
    return (f'<div class="ui-stat big" style="border-top-color:{color};">'
            f'<div class="ui-stat-top"><div class="ui-stat-icon" style="background:{color}18;">{icon}</div>'
            f'<div><div class="ui-stat-label">{label}</div><div class="ui-stat-sub">{sub}</div></div></div>'
            f'<div class="ui-stat-value">{val}</div></div>')


def _donut(pos, neu, neg, n):
    p, nu, ng = pos * 100, neu * 100, neg * 100
    a1, a2 = p, p + nu
    return (f'<div class="ui-card"><div class="ui-card-title">Sentiment Distribution</div>'
            f'<div class="ui-card-sub">Share of the current selection ({ui.fmt(n)} reviews)</div><div class="ui-donut-wrap">'
            f'<div class="ui-donut" style="background:conic-gradient({ui.POS} 0% {a1:.1f}%,{ui.NEU} {a1:.1f}% {a2:.1f}%,{ui.NEG} {a2:.1f}% 100%);">'
            f'<div class="ui-donut-hole"><div class="ui-donut-big" style="color:{ui.POS};">{p:.0f}%</div>'
            f'<div class="ui-donut-lbl">Positive</div></div></div>'
            f'<div style="flex:1;"><div class="ui-leg"><span class="ui-dot" style="background:{ui.POS};"></span>Positive<span class="ui-leg-val">{p:.0f}%</span></div>'
            f'<div class="ui-leg"><span class="ui-dot" style="background:{ui.NEU};"></span>Neutral<span class="ui-leg-val">{nu:.0f}%</span></div>'
            f'<div class="ui-leg"><span class="ui-dot" style="background:{ui.NEG};"></span>Negative<span class="ui-leg-val">{ng:.0f}%</span></div></div></div></div>')


def _theme_lolli(view):
    counts = view[view["theme_id"] != "unclassified"]["theme_id"].value_counts().head(8)
    if counts.empty:
        return '<div class="ui-card"><div class="ui-card-title">Themes</div><div class="ui-muted">No themed reviews in view.</div></div>'
    top = int(counts.iloc[0])
    rows = []
    for i, (theme, cnt) in enumerate(counts.items()):
        name = ui.THEME_META.get(theme, (theme, ""))[0]
        color = ui.CAT[i % len(ui.CAT)]
        pct = cnt / top * 100
        rows.append(f'<div class="ui-lolli"><div class="ui-lolli-label">'
                    f'<span class="ui-dot" style="background:{color};"></span>{name}</div>'
                    f'<div class="ui-lolli-track"><div class="ui-lolli-fill" style="width:{pct:.0f}%;background:{color};"></div>'
                    f'<span class="ui-lolli-knob" style="left:{pct:.0f}%;border-color:{color};"></span></div>'
                    f'<div class="ui-lolli-val">{ui.fmt(cnt)}</div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">Themes</div>'
            f'<div class="ui-card-sub">Reviews per theme in the current view</div>{"".join(rows)}</div>')


def _source_bars(view):
    counts = view["source"].value_counts()
    top = int(counts.iloc[0])
    rows = []
    for s, c in counts.items():
        name, color = ui.SOURCE_META.get(s, (s.title(), ui.MUTED))
        pct = c / top * 100
        rows.append(f'<div class="ui-bar"><div class="ui-bar-label">{name}</div>'
                    f'<div class="ui-bar-track"><div class="ui-bar-fill" style="width:{pct:.0f}%;background:{color};"></div></div>'
                    f'<div class="ui-bar-val">{ui.fmt(c)}</div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">Source Breakdown</div>'
            f'<div class="ui-card-sub">Reviews per channel</div>{"".join(rows)}</div>')


def _rating_bars(view):
    rated = view.dropna(subset=["rating"])
    if rated.empty:
        return '<div class="ui-card"><div class="ui-card-title">Rating Distribution</div><div class="ui-muted">No star ratings in view.</div></div>'
    counts = rated["rating"].value_counts()
    top = int(counts.max())
    rat_colors = {1: ui.NEG, 2: "#f97316", 3: ui.NEU, 4: "#84cc16", 5: ui.POS}
    bars = []
    for star in [1, 2, 3, 4, 5]:
        c = int(counts.get(star, 0))
        h = (c / top * 100) if top else 0
        bars.append(f'<div class="ui-vbar"><div class="ui-vbar-n">{ui.fmt(c) if c else ""}</div>'
                    f'<div class="ui-vbar-fill" style="height:{h:.0f}%;background:{rat_colors[star]};"></div>'
                    f'<div class="ui-vbar-x">{star}★</div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">Rating Distribution</div>'
            f'<div class="ui-card-sub">Store ratings — Google Play + App Store (social sources have no star rating)</div>'
            f'<div class="ui-vbars">{"".join(bars)}</div></div>')


def _segments(view):
    seg_cols = ["price_sensitivity", "family_stage", "has_pet", "city_tier"]
    labels = {
        "price_sensitivity=high": ("Price-Sensitive", "💰"), "price_sensitivity=low": ("Price-Insensitive", "💳"),
        "family_stage=parent_young_child": ("Parents", "🍼"), "family_stage=single": ("Singles", "🧍"),
        "family_stage=couple": ("Couples", "👥"), "has_pet=yes": ("Pet Owners", "🐾"),
        "city_tier=metro": ("Metro", "🏙️"), "city_tier=tier2": ("Tier-2 City", "🏘️"),
    }
    rows = []
    for col in seg_cols:
        known = view[view[col] != "unknown"]
        for value, grp in known.groupby(col):
            if len(grp) < 10:
                continue
            label, icon = labels.get(f"{col}={value}", (f"{col}={value}", "•"))
            rows.append(((grp["sentiment"] < -0.2).mean(), len(grp), label, icon))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    rows = rows[:4]
    if not rows:
        return '<div class="ui-card"><div class="ui-card-title">User Segments</div><div class="ui-muted">No segment signals in view (segment fields are sparse in review text).</div></div>'
    cards = []
    colors = [ui.NEG, "#f97316", ui.NEU, ui.GREEN]
    for i, (rate, n, label, icon) in enumerate(rows):
        cards.append(f'<div class="ui-segcard"><div class="ui-segcard-rank">#{i+1}</div>'
                     f'<div class="ui-segcard-icon">{icon}</div>'
                     f'<div class="ui-segcard-pct" style="color:{colors[i]};">{rate:.0%}</div>'
                     f'<div class="ui-segcard-name">{label}</div>'
                     f'<div class="ui-segcard-sub">{ui.fmt(n)} reviews · negative rate</div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">User Segments</div>'
            f'<div class="ui-card-sub">Negative-sentiment rate by segment — who is most frustrated</div>'
            f'<div class="ui-g4">{"".join(cards)}</div></div>')
