"""Analytics tab: 'Deep Analytics' — a light Blinkit-palette analytics board
modelled on the spotify-discovery-intel reference. A keyword + source + sentiment filter
bar narrows the corpus, and every panel below (sentiment split, barrier-load tiles,
donut, theme lollipop, source bars, rating distribution, segment cards) recomputes from
the filtered view.
"""
import re

import streamlit as st

from app import ui
from app.data import load_enriched_df, scraped_count

MATCH_LIMIT = 12

# Filter widgets are keyed so the Reset button can clear them from session state.
KW_KEY, SRC_KEY, SENT_KEY = "an_kw", "an_src", "an_sent"


def _reset():
    """Clear the filter bar. Runs as an on_click callback, i.e. before the next
    rerun builds the widgets, which is the only point session state may be written."""
    st.session_state[KW_KEY] = ""
    st.session_state[SRC_KEY] = "All sources"
    st.session_state[SENT_KEY] = "All sentiment"


def render():
    df = load_enriched_df()
    if df.empty:
        st.warning("No enriched data yet — run `python -m src.enrich` first.")
        return

    # The filter row is a Streamlit widget block, which carries no top margin of its own —
    # without this spacer it sits flush against the hero card. Other tabs get their gap
    # from the .ui-label that follows their hero.
    scraped = scraped_count(len(df))
    ui.flush([ui.hero("bar-chart", "Analytics Dashboard", "Deep Analytics",
                      f"Sentiment, barriers and complaint rates from LLM-classified reviews. Filter by keyword, "
                      f"source or sentiment — every panel updates together. {ui.fmt_full(scraped)} reviews "
                      f"scraped, narrowed to the {ui.fmt_full(len(df))} analysed here.",
                      pill=f"{ui.fmt_full(scraped)} scraped · {ui.fmt_full(len(df))} analysed"),
              '<div style="height:20px;"></div>'])

    # --- Filter bar (real Streamlit widgets, styled compact) ----------------
    src_opts = ["All sources"] + [ui.SOURCE_META.get(s, (s, ""))[0] for s in df["source"].value_counts().index]
    sent_opts = ["All sentiment", "Positive", "Neutral", "Negative"]

    c1, c2, c3, c4 = st.columns([3, 1.15, 1.15, 0.75])
    kw = c1.text_input(
        "Search", placeholder="Search by keyword (e.g. fruits, expiry, Zepto)…",
        label_visibility="collapsed", key=KW_KEY,
        help="Filters every panel on this tab to reviews whose text contains this word. "
             "Plain substring match, not semantic — 'expiry' will not match 'expired'.",
    )
    src_sel = c2.selectbox("Source", src_opts, label_visibility="collapsed", key=SRC_KEY)
    sent_sel = c3.selectbox("Sentiment", sent_opts, label_visibility="collapsed", key=SENT_KEY)
    dirty = bool(kw.strip()) or src_sel != src_opts[0] or sent_sel != sent_opts[0]
    c4.button("Reset", use_container_width=True, disabled=not dirty, on_click=_reset,
              help="Clear the keyword, source and sentiment filters.")

    view = df
    if kw.strip():
        # regex=False: the box is a plain keyword filter, and without this a query like
        # "c++" or "*fresh" is compiled as a pattern and raises on the user.
        view = view[view["text"].str.contains(kw.strip(), case=False, na=False, regex=False)]
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

    with st.expander("How this filter bar works", expanded=False):
        st.markdown(
            "**Search** narrows the whole tab to reviews whose text contains your word — "
            "a plain, case-insensitive substring match on the review body, so `expiry` "
            "does not match `expired`, and it never searches theme or barrier labels. "
            "For meaning-based questions, use the **Insight Engine** tab instead.\n\n"
            "**Source** and **Sentiment** stack on top of the search, so "
            "`fruits` + Play Store + Negative gives complaints about fruit from Play Store "
            "reviewers only.\n\n"
            "Every panel below — sentiment split, barrier load, donut, themes, rating "
            "distribution, segments — recomputes from whatever the filters leave. "
            "The matching reviews themselves appear directly beneath this bar once you "
            "type a keyword.\n\n"
            "*Try: `expiry`, `delivery`, `Zepto`, `refund`, `missing`.*"
        )

    st.caption(f"Showing **{len(view):,}** of {len(df):,} reviews matching the current filters.")

    if view.empty:
        st.info("No reviews match these filters — widen the search.")
        return

    if kw.strip():
        ui.flush(_matches(view, kw.strip()))

    pos = (view["sentiment"] > 0.2).mean()
    neu = view["sentiment"].between(-0.2, 0.2).mean()
    neg = (view["sentiment"] < -0.2).mean()
    barrier_share = (view["barrier_type"] != "none").mean()
    neg_barrier = ((view["barrier_type"] != "none") & (view["sentiment"] < -0.2)).mean()
    sent_score = round((view["sentiment"].mean() + 1) / 2 * 100)

    parts = [
        '<div class="ui-label">How Users Feel</div>',
        '<div class="ui-g3">',
        _feel_tile("smile", "Positive", pos, ui.POS), _feel_tile("meh", "Neutral", neu, ui.NEU), _feel_tile("frown", "Negative", neg, ui.NEG),
        "</div>",
        '<div class="ui-label">Barrier Load</div>',
        '<div class="ui-g3">',
        _stat_tile("compass", "Reviews With A Barrier", f"{barrier_share:.0%}", "share flagged with a barrier type", ui.CAT[0]),
        _stat_tile("alert", "Negative Barrier Reviews", f"{neg_barrier:.0%}", "barrier + negative sentiment", ui.NEG),
        _stat_tile("bar-chart", "Sentiment Score", str(sent_score), "0–100 overall mood in view", ui.GREEN),
        "</div>",
        '<div class="ui-row ui-split">', _donut(pos, neu, neg, len(view)), _theme_lolli(view), "</div>",
        '<div class="ui-row ui-split">', _source_bars(view), _rating_bars(view), "</div>",
        '<div class="ui-row">', _segments(view), "</div>",
    ]
    ui.flush(parts)


def _highlight(text: str, kw: str) -> str:
    """Escape the review text, then wrap each case-insensitive hit in <mark>.

    Escaping first means the <mark> tags are the only markup that survives; re.escape
    keeps keywords like "3.5" or "c++" from being read as a pattern.
    """
    safe = ui.esc(text)
    return re.sub(f"({re.escape(ui.esc(kw))})", r'<mark class="ui-mark">\1</mark>', safe, flags=re.I)


def _matches(view, kw: str) -> str:
    """The actual reviews behind the current keyword — the evidence for the panels below."""
    if "date_parsed" in view.columns:
        rows = view.sort_values("date_parsed", ascending=False, na_position="last")
    else:
        rows = view
    cards = []
    for _, r in rows.head(MATCH_LIMIT).iterrows():
        name, color = ui.SOURCE_META.get(r["source"], (str(r["source"]).title(), ui.MUTED))
        scol = ui.sentiment_color(r["sentiment"])
        slabel = ui.sentiment_label(r["sentiment"])
        text = r["text"] if len(r["text"]) <= 320 else r["text"][:320] + "…"
        date = str(r["date"])[:10] if r.get("date") else ""
        url = r.get("url") or ""
        link = (f'<a class="ui-cite" href="{ui.esc(url)}" target="_blank" rel="noopener">'
                f'{ui.icon("link", size=12, color=ui.YELLOW_DK)}view source</a>') if url else ""
        barrier = r.get("barrier_type", "none")
        btag = (f'<span class="ui-badge" style="color:{ui.MUTED};border-color:{ui.BORDER2};">'
                f'{ui.esc(ui.BARRIER_LABELS.get(barrier, barrier))}</span>') if barrier and barrier != "none" else ""
        cards.append(
            f'<div class="ui-rev"><div class="ui-rev-head">'
            f'<span><span class="ui-dot" style="background:{color};"></span>{name}</span>'
            f'<span class="ui-rev-date">{date}</span></div>'
            f'<div class="ui-rev-text">{_highlight(text, kw)}</div>'
            f'<div class="ui-rev-foot" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">'
            f'<span class="ui-badge" style="color:{scol};border-color:{scol}55;background:{scol}12;">● {slabel}</span>'
            f'{btag}{link}</div></div>')

    shown = min(len(rows), MATCH_LIMIT)
    more = (f' Showing the {shown} most recent — refine the filters to narrow further.'
            if len(rows) > MATCH_LIMIT else "")
    return (f'<div class="ui-card ui-row"><div class="ui-card-title">Matching Reviews</div>'
            f'<div class="ui-card-sub">{ui.fmt_full(len(rows))} review(s) contain '
            f'&ldquo;{ui.esc(kw)}&rdquo;.{more}</div>'
            f'<div class="ui-g3">{"".join(cards)}</div></div>')


def _feel_tile(icon_name, label, val, color):
    return (f'<div class="ui-stat big" style="border-top-color:{color};">'
            f'<div class="ui-stat-top"><div class="ui-stat-icon" style="background:{color}18;">{ui.icon(icon_name, size=17, color=color)}</div>'
            f'<div><div class="ui-stat-label">{label}</div><div class="ui-stat-sub">of reviews in view</div></div></div>'
            f'<div class="ui-stat-value" style="color:{color};">{val:.0%}</div></div>')


def _stat_tile(icon_name, label, val, sub, color):
    return (f'<div class="ui-stat big" style="border-top-color:{color};">'
            f'<div class="ui-stat-top"><div class="ui-stat-icon" style="background:{color}18;">{ui.icon(icon_name, size=17, color=color)}</div>'
            f'<div><div class="ui-stat-label">{label}</div><div class="ui-stat-sub">{sub}</div></div></div>'
            f'<div class="ui-stat-value">{val}</div></div>')


def _donut(pos, neu, neg, n):
    p, nu, ng = pos * 100, neu * 100, neg * 100
    a1, a2 = p, p + nu
    return (f'<div class="ui-card"><div class="ui-card-title">Sentiment Distribution</div>'
            f'<div class="ui-card-sub">Share of the current selection ({ui.fmt_full(n)} reviews)</div><div class="ui-donut-wrap">'
            f'<div class="ui-donut" style="background:conic-gradient({ui.POS} 0% {a1:.1f}%,{ui.NEU} {a1:.1f}% {a2:.1f}%,{ui.NEG} {a2:.1f}% 100%);">'
            # Matches Overview: the corpus size, not the positive share, which read as
            # the headline number over a mostly-negative ring.
            f'<div class="ui-donut-hole"><div class="ui-donut-big" style="color:{ui.TXT};">{ui.fmt_full(n)}</div>'
            f'<div class="ui-donut-lbl">Reviews</div></div></div>'
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
                    f'<div class="ui-lolli-val">{ui.fmt_full(cnt)}</div></div>')
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
                    f'<div class="ui-bar-val">{ui.fmt_full(c)}</div></div>')
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
        bars.append(f'<div class="ui-vbar"><div class="ui-vbar-n">{ui.fmt_full(c) if c else ""}</div>'
                    f'<div class="ui-vbar-fill" style="height:{h:.0f}%;background:{rat_colors[star]};"></div>'
                    f'<div class="ui-vbar-x">{star}★</div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">Rating Distribution</div>'
            f'<div class="ui-card-sub">Store ratings — Play Store + App Store (social sources have no star rating)</div>'
            f'<div class="ui-vbars">{"".join(bars)}</div></div>')


SEG_ICON = {"price_sensitivity": "tag", "family_stage": "users", "has_pet": "heart", "city_tier": "pin"}
SEG_LABELS = {
    "price_sensitivity=high": "Price-Sensitive", "price_sensitivity=low": "Price-Insensitive",
    "family_stage=parent_young_child": "Parents", "family_stage=single": "Singles",
    "family_stage=couple": "Couples", "has_pet=yes": "Pet Owners",
    "city_tier=metro": "Metro", "city_tier=tier2": "Tier-2 City",
}


def _segments(view):
    rows = []
    for col in ["price_sensitivity", "family_stage", "has_pet", "city_tier"]:
        known = view[view[col] != "unknown"]
        for value, grp in known.groupby(col):
            if len(grp) < 10:
                continue
            label = SEG_LABELS.get(f"{col}={value}", f"{col}={value}")
            rows.append(((grp["sentiment"] < -0.2).mean(), len(grp), label, SEG_ICON.get(col, "user")))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    rows = rows[:4]
    if not rows:
        return '<div class="ui-card"><div class="ui-card-title">User Segments</div><div class="ui-muted">No segment signals in view (segment fields are sparse in review text).</div></div>'
    cards = []
    colors = [ui.NEG, "#f97316", ui.NEU, ui.GREEN]
    for i, (rate, n, label, ic) in enumerate(rows):
        cards.append(f'<div class="ui-segcard"><div class="ui-segcard-rank">#{i+1}</div>'
                     f'<div class="ui-segcard-icon">{ui.icon(ic, size=15, color=ui.YELLOW_DK)}</div>'
                     f'<div class="ui-segcard-pct" style="color:{colors[i]};">{rate:.0%}</div>'
                     f'<div class="ui-segcard-name">{label}</div>'
                     f'<div class="ui-segcard-sub">{ui.fmt_full(n)} reviews · negative rate</div></div>')
    return (f'<div class="ui-card"><div class="ui-card-title">User Segments</div>'
            f'<div class="ui-card-sub">Negative-sentiment rate by segment — who is most frustrated</div>'
            f'<div class="ui-g4">{"".join(cards)}</div></div>')
