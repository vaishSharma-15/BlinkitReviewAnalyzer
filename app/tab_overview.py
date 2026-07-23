"""Overview tab: a dark 'Discovery Health Overview' dashboard modelled on the
spotify-discovery-intel reference layout, rendered as one self-contained dark panel of
custom HTML/CSS so it reads as a cohesive dashboard regardless of the app's light page
background. Every number is computed from the real enriched corpus — the panel never
hard-codes a figure.
"""
from collections import Counter
from datetime import datetime

import pandas as pd
import streamlit as st

from app.data import load_enriched_df, load_themes_df

# Dark palette (brand yellow kept as the primary accent, categorical colors for charts).
BG = "#0b0b0c"
CARD = "#141416"
CARD2 = "#1a1b1f"
BORDER = "#26272b"
TXT = "#ececed"
MUTED = "#9a9aa2"
FAINT = "#6b6b73"
ACCENT = "#F9D507"
POS = "#22c55e"
NEU = "#f59e0b"
NEG = "#ef4444"

CAT_COLORS = ["#f97316", "#3b82f6", "#22c55e", "#10b981", "#a855f7", "#ec4899", "#f59e0b", "#38bdf8", "#eab308"]

SOURCE_META = {
    "play": ("Google Play", "#22c55e"),
    "appstore": ("App Store", "#9ca3af"),
    "youtube": ("YouTube", "#ef4444"),
    "qcomm_comparison": ("Q-Comm Threads", "#f59e0b"),
    "product_review": ("Product Reviews", "#ec4899"),
    "reddit": ("Reddit", "#f97316"),
    "forum": ("Forums", "#3b82f6"),
}

BARRIER_LABELS = {
    "trust_quality": "Trust & Quality",
    "price_premium": "Price Premium",
    "assortment_doubt": "Assortment Doubt",
    "findability": "Findability",
    "no_trigger": "No Trigger to Try",
    "returns_risk": "Returns Risk",
    "brand_absence": "Brand Absence",
    "expiry_freshness": "Expiry & Freshness",
    "prefer_specialist_store": "Prefer Specialist Store",
}

SEGMENT_LABELS = {
    "price_sensitivity=high": ("Price-Sensitive", "💰"),
    "price_sensitivity=low": ("Price-Insensitive", "💳"),
    "family_stage=parent_young_child": ("Parents", "🍼"),
    "family_stage=single": ("Singles", "🧍"),
    "family_stage=couple": ("Couples", "👥"),
    "has_pet=yes": ("Pet Owners", "🐾"),
    "city_tier=metro": ("Metro", "🏙️"),
    "city_tier=tier2": ("Tier-2 City", "🏘️"),
}


def _fmt(n: int) -> str:
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def render():
    df = load_enriched_df()
    themes_df = load_themes_df()

    if df.empty:
        st.warning("No enriched data yet — run `python -m src.enrich` first.")
        return

    total = len(df)
    n_sources = df["source"].nunique()
    avg_rating = df["rating"].dropna().mean()
    avg_sent = df["sentiment"].mean()
    sent_score = round((avg_sent + 1) / 2 * 100)
    pos_share = (df["sentiment"] > 0.2).mean()
    neu_share = df["sentiment"].between(-0.2, 0.2).mean()
    neg_share = (df["sentiment"] < -0.2).mean()
    themed = df[df["barrier_type"] != "none"] if "barrier_type" in df else df
    classified = int((df.get("theme_id", pd.Series(["x"] * total)) != "unclassified").sum()) if "theme_id" in df.columns else total

    html = [_hero(total), _sources(df), _kpis(total, n_sources, classified, avg_rating, sent_score, pos_share)]
    html.append('<div class="ov-row ov-2col">')
    html.append(_struggles(df))
    html.append(_repetition(df))
    html.append("</div>")
    html.append('<div class="ov-row ov-2col">')
    html.append(_segments(df))
    html.append(_sentiment_donut(pos_share, neu_share, neg_share))
    html.append("</div>")
    html.append(_coverage(df))
    html.append(_recent(df))

    panel = f'<div class="ov-panel">{"".join(html)}</div>'
    out = _CSS + panel
    # Strip every line's leading whitespace: Streamlit renders markdown, and any line
    # indented 4+ spaces would be treated as a code block and shown as literal text
    # rather than applied as HTML/CSS. Collapsing to a single line avoids that entirely.
    out = "".join(line.strip() for line in out.splitlines())
    st.markdown(out, unsafe_allow_html=True)


def _hero(total: int) -> str:
    return f"""
    <div class="ov-hero">
      <div class="ov-hero-icon">🔍</div>
      <div class="ov-hero-text">
        <div class="ov-eyebrow">Reviews Dashboard</div>
        <div class="ov-hero-title">Discovery Health Overview</div>
        <div class="ov-hero-sub">Why Blinkit users stay inside familiar shopping categories — every label read by an LLM, not keywords.</div>
      </div>
      <div class="ov-hero-pill">● {_fmt(total)} reviews analyzed</div>
    </div>"""


def _sources(df) -> str:
    counts = df["source"].value_counts()
    cards = []
    for source in counts.index[:4]:
        name, color = SOURCE_META.get(source, (source.title(), MUTED))
        sub = df[df["source"] == source]
        if source in ("play", "appstore") and sub["rating"].notna().any():
            metric = f"{sub['rating'].dropna().mean():.1f}★ avg rating"
        else:
            s = round((sub["sentiment"].mean() + 1) / 2 * 100)
            metric = f"{s}/100 sentiment"
        cards.append(f"""
        <div class="ov-src" style="border-left:3px solid {color};">
          <div class="ov-src-name">{name}</div>
          <div class="ov-src-count">{_fmt(len(sub))}</div>
          <div class="ov-src-metric">{metric}</div>
        </div>""")
    return f'<div class="ov-label">Sources Analyzed</div><div class="ov-src-grid">{"".join(cards)}</div>'


def _kpis(total, n_sources, classified, avg_rating, sent_score, pos_share) -> str:
    tiles = [
        ("📝", "Total Reviews", _fmt(total), f"Across {n_sources} sources"),
        ("🧭", "Themed Reviews", _fmt(classified), f"{classified/total:.0%} fit a theme"),
        ("⭐", "Avg Rating", f"{avg_rating:.2f}", "Store ratings (1–5★)"),
        ("🙂", "Sentiment Score", str(sent_score), "0–100 overall mood"),
        ("📊", "Positive Share", f"{pos_share:.0%}", "of all reviews"),
    ]
    cells = "".join(f"""
      <div class="ov-kpi">
        <div class="ov-kpi-icon">{i}</div>
        <div class="ov-kpi-body">
          <div class="ov-kpi-label">{l}</div>
          <div class="ov-kpi-sub">{s}</div>
        </div>
        <div class="ov-kpi-value">{v}</div>
      </div>""" for i, l, v, s in tiles)
    return f'<div class="ov-kpi-grid">{cells}</div>'


def _struggles(df) -> str:
    themed = df[df["barrier_type"] != "none"]
    counts = themed["barrier_type"].value_counts().head(7)
    if counts.empty:
        return '<div class="ov-card"><div class="ov-card-title">What Users Struggle With</div><div class="ov-muted">No barrier-labeled items yet.</div></div>'
    top = int(counts.iloc[0])
    rows = []
    for i, (barrier, cnt) in enumerate(counts.items()):
        label = BARRIER_LABELS.get(barrier, barrier)
        color = CAT_COLORS[i % len(CAT_COLORS)]
        pct = cnt / top * 100
        rows.append(f"""
        <div class="ov-lolli">
          <div class="ov-lolli-label"><span class="ov-dot" style="background:{color};"></span>{label}</div>
          <div class="ov-lolli-track"><div class="ov-lolli-fill" style="width:{pct:.0f}%;background:{color};"></div><span class="ov-lolli-knob" style="left:{pct:.0f}%;border-color:{color};"></span></div>
          <div class="ov-lolli-val">{_fmt(cnt)}</div>
        </div>""")
    return f"""
    <div class="ov-card">
      <div class="ov-card-title">What Users Struggle With</div>
      <div class="ov-card-sub">Barrier mentions by frequency, across {_fmt(len(themed))} of {_fmt(len(df))} reviews.</div>
      {"".join(rows)}
    </div>"""


def _repetition(df) -> str:
    themed = df[df["barrier_type"] != "none"]
    counts = themed["barrier_type"].value_counts()
    if counts.empty:
        return '<div class="ov-card"><div class="ov-card-title">The Concentration Problem</div><div class="ov-muted">No barriers yet.</div></div>'
    total_b = int(counts.sum())
    top_barrier = counts.index[0]
    top_pct = counts.iloc[0] / total_b * 100
    bars = []
    for i, (barrier, cnt) in enumerate(counts.head(3).items()):
        label = BARRIER_LABELS.get(barrier, barrier)
        color = CAT_COLORS[i % len(CAT_COLORS)]
        pct = cnt / total_b * 100
        bars.append(f"""
        <div class="ov-rep-row">
          <div class="ov-rep-head"><span>{label}</span><span style="color:{color};font-weight:800;">{pct:.0f}%</span></div>
          <div class="ov-rep-track"><div class="ov-rep-fill" style="width:{pct:.0f}%;background:{color};"></div></div>
        </div>""")
    return f"""
    <div class="ov-card">
      <div class="ov-card-title">The Concentration Problem</div>
      <div class="ov-card-sub">Where the barrier pain concentrates</div>
      <div class="ov-rep-hero">
        <div class="ov-rep-big">{top_pct:.0f}%</div>
        <div class="ov-rep-big-sub">of all barrier mentions are <b>{BARRIER_LABELS.get(top_barrier, top_barrier)}</b> — the single largest blocker to category exploration.</div>
      </div>
      {"".join(bars)}
    </div>"""


def _segments(df) -> str:
    seg_cols = ["price_sensitivity", "family_stage", "has_pet", "city_tier"]
    # Require a minimum sample so a 1-record segment can't rank at "100%" — that's a
    # sampling artifact, not a real segment signal, and would mislead on the leaderboard.
    MIN_SEG_N = 10
    rows = []
    for col in seg_cols:
        known = df[df[col] != "unknown"]
        for value, grp in known.groupby(col):
            if len(grp) < MIN_SEG_N:
                continue
            key = f"{col}={value}"
            label, icon = SEGMENT_LABELS.get(key, (key, "•"))
            n = len(grp)
            rate = (grp["sentiment"] < -0.2).mean()
            rows.append((rate, n, label, icon))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    rows = rows[:5]
    if not rows:
        return '<div class="ov-card"><div class="ov-card-title">Who\'s Most Frustrated</div><div class="ov-muted">No segment signals detected in this corpus.</div></div>'
    body = []
    for i, (rate, n, label, icon) in enumerate(rows, start=1):
        body.append(f"""
        <div class="ov-seg-row">
          <div class="ov-seg-rank">{i}</div>
          <div class="ov-seg-name">{icon}&nbsp;&nbsp;{label}</div>
          <div class="ov-seg-rate">{rate:.0%}</div>
          <div class="ov-seg-n">{_fmt(n)}</div>
        </div>""")
    return f"""
    <div class="ov-card">
      <div class="ov-card-title">Who's Most Frustrated</div>
      <div class="ov-card-sub">Negative-sentiment rate by user segment</div>
      <div class="ov-seg-head"><div>#</div><div>Segment</div><div>Rate</div><div>Reviews</div></div>
      {"".join(body)}
    </div>"""


def _sentiment_donut(pos, neu, neg) -> str:
    p, nu, ng = pos * 100, neu * 100, neg * 100
    a1 = p
    a2 = p + nu
    return f"""
    <div class="ov-card">
      <div class="ov-card-title">Sentiment Breakdown</div>
      <div class="ov-card-sub">Share of all reviews</div>
      <div class="ov-donut-wrap">
        <div class="ov-donut" style="background:conic-gradient({POS} 0% {a1:.1f}%, {NEU} {a1:.1f}% {a2:.1f}%, {NEG} {a2:.1f}% 100%);">
          <div class="ov-donut-hole"><div class="ov-donut-big">{p:.0f}%</div><div class="ov-donut-lbl">Positive</div></div>
        </div>
        <div class="ov-donut-legend">
          <div class="ov-leg"><span class="ov-dot" style="background:{POS};"></span>Positive<span class="ov-leg-val">{p:.0f}%</span></div>
          <div class="ov-leg"><span class="ov-dot" style="background:{NEU};"></span>Neutral<span class="ov-leg-val">{nu:.0f}%</span></div>
          <div class="ov-leg"><span class="ov-dot" style="background:{NEG};"></span>Negative<span class="ov-leg-val">{ng:.0f}%</span></div>
        </div>
      </div>
    </div>"""


def _coverage(df) -> str:
    dated = df.dropna(subset=["date_parsed"]).copy()
    if dated.empty:
        return ""
    dated["year"] = dated["date_parsed"].dt.year
    years = sorted(dated["year"].unique())
    cards = []
    for y in years:
        sub = dated[dated["year"] == y]
        n = len(sub)
        src_counts = sub["source"].value_counts()
        seg = "".join(
            f'<div style="width:{c/n*100:.1f}%;background:{SOURCE_META.get(s, (s, MUTED))[1]};"></div>'
            for s, c in src_counts.items()
        )
        cards.append(f"""
        <div class="ov-year">
          <div class="ov-year-head"><span>{y}</span><span class="ov-year-n">{_fmt(n)}</span></div>
          <div class="ov-year-bar">{seg}</div>
        </div>""")
    legend = "".join(
        f'<div class="ov-leg"><span class="ov-dot" style="background:{SOURCE_META.get(s, (s, MUTED))[1]};"></span>{SOURCE_META.get(s, (s, MUTED))[0]}</div>'
        for s in df["source"].value_counts().index[:5]
    )
    return f"""
    <div class="ov-card ov-wide">
      <div class="ov-card-title">Coverage by Year ({years[0]}–{years[-1]})</div>
      <div class="ov-card-sub">Reviews per year and their source mix.</div>
      <div class="ov-year-grid">{"".join(cards)}</div>
      <div class="ov-year-legend">{legend}</div>
    </div>"""


def _recent(df) -> str:
    recent = df.dropna(subset=["date_parsed"]).sort_values("date_parsed", ascending=False).head(6)
    cards = []
    for _, r in recent.iterrows():
        name, color = SOURCE_META.get(r["source"], (r["source"].title(), MUTED))
        if r["sentiment"] > 0.2:
            badge, bcol = "Positive", POS
        elif r["sentiment"] < -0.2:
            badge, bcol = "Negative", NEG
        else:
            badge, bcol = "Neutral", NEU
        text = (r["text"][:150] + "…") if len(r["text"]) > 150 else r["text"]
        date = str(r["date"])[:10]
        cards.append(f"""
        <div class="ov-rev">
          <div class="ov-rev-head"><span><span class="ov-dot" style="background:{color};"></span>{name}</span><span class="ov-rev-date">{date}</span></div>
          <div class="ov-rev-text">{text}</div>
          <div class="ov-rev-foot"><span class="ov-badge" style="color:{bcol};border-color:{bcol}44;background:{bcol}14;">● {badge}</span></div>
        </div>""")
    return f"""
    <div class="ov-card ov-wide">
      <div class="ov-card-title">Recent Reviews</div>
      <div class="ov-card-sub">Latest feedback across sources</div>
      <div class="ov-rev-grid">{"".join(cards)}</div>
    </div>"""


_CSS = f"""
<style>
.ov-panel {{ background:{BG}; border-radius:16px; padding:22px; margin-top:8px; font-family:'Inter',sans-serif; }}
.ov-panel * {{ box-sizing:border-box; }}
.ov-label {{ color:{FAINT}; font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; margin:22px 4px 10px; }}
.ov-muted {{ color:{MUTED}; font-size:13px; }}
.ov-dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:7px; vertical-align:middle; }}

.ov-hero {{ background:linear-gradient(120deg,{CARD} 0%,#101216 100%); border:1px solid {BORDER}; border-radius:14px; padding:24px; display:flex; align-items:flex-start; gap:18px; position:relative; }}
.ov-hero-icon {{ width:52px; height:52px; border-radius:12px; background:{ACCENT}; display:flex; align-items:center; justify-content:center; font-size:24px; flex-shrink:0; }}
.ov-eyebrow {{ color:{ACCENT}; font-size:11px; font-weight:800; letter-spacing:0.14em; text-transform:uppercase; }}
.ov-hero-title {{ color:{TXT}; font-size:30px; font-weight:800; letter-spacing:-0.02em; margin:4px 0; }}
.ov-hero-sub {{ color:{MUTED}; font-size:14px; max-width:640px; line-height:1.5; }}
.ov-hero-pill {{ position:absolute; top:22px; right:22px; background:{ACCENT}1a; color:{ACCENT}; border:1px solid {ACCENT}44; border-radius:9999px; padding:6px 14px; font-size:12px; font-weight:700; white-space:nowrap; }}

.ov-src-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }}
.ov-src {{ background:{CARD}; border:1px solid {BORDER}; border-radius:12px; padding:16px 18px; }}
.ov-src-name {{ color:{TXT}; font-size:13px; font-weight:700; }}
.ov-src-count {{ color:{TXT}; font-size:24px; font-weight:800; margin:2px 0; }}
.ov-src-metric {{ color:{MUTED}; font-size:12px; }}

.ov-kpi-grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-top:16px; }}
.ov-kpi {{ background:{CARD}; border:1px solid {BORDER}; border-radius:12px; padding:16px; display:flex; align-items:center; gap:10px; position:relative; }}
.ov-kpi-icon {{ width:34px; height:34px; border-radius:9px; background:{CARD2}; display:flex; align-items:center; justify-content:center; font-size:16px; flex-shrink:0; }}
.ov-kpi-label {{ color:{MUTED}; font-size:10px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; line-height:1.3; }}
.ov-kpi-sub {{ color:{FAINT}; font-size:10px; margin-top:2px; }}
.ov-kpi-value {{ color:{ACCENT}; font-size:22px; font-weight:800; margin-left:auto; }}

.ov-row {{ margin-top:16px; }}
.ov-2col {{ display:grid; grid-template-columns:1.55fr 1fr; gap:16px; }}
.ov-card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:14px; padding:20px; }}
.ov-card-title {{ color:{TXT}; font-size:16px; font-weight:800; }}
.ov-card-sub {{ color:{MUTED}; font-size:12px; margin:2px 0 16px; }}

.ov-lolli {{ display:grid; grid-template-columns:150px 1fr 46px; align-items:center; gap:12px; margin-bottom:13px; }}
.ov-lolli-label {{ color:{TXT}; font-size:13px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.ov-lolli-track {{ position:relative; height:4px; background:{CARD2}; border-radius:2px; }}
.ov-lolli-fill {{ position:absolute; height:4px; border-radius:2px; }}
.ov-lolli-knob {{ position:absolute; top:50%; width:11px; height:11px; border-radius:50%; background:{BG}; border:2px solid; transform:translate(-50%,-50%); }}
.ov-lolli-val {{ color:{TXT}; font-size:13px; font-weight:700; text-align:right; }}

.ov-rep-hero {{ background:{NEG}0d; border:1px solid {NEG}33; border-radius:12px; padding:16px; display:flex; gap:14px; align-items:center; margin-bottom:16px; }}
.ov-rep-big {{ color:{TXT}; font-size:38px; font-weight:800; line-height:1; }}
.ov-rep-big-sub {{ color:{MUTED}; font-size:12px; line-height:1.45; }}
.ov-rep-row {{ margin-bottom:12px; }}
.ov-rep-head {{ display:flex; justify-content:space-between; color:{TXT}; font-size:13px; font-weight:600; margin-bottom:5px; }}
.ov-rep-track {{ height:6px; background:{CARD2}; border-radius:3px; }}
.ov-rep-fill {{ height:6px; border-radius:3px; }}

.ov-seg-head {{ display:grid; grid-template-columns:24px 1fr 60px 60px; color:{FAINT}; font-size:10px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; padding-bottom:8px; border-bottom:1px solid {BORDER}; }}
.ov-seg-row {{ display:grid; grid-template-columns:24px 1fr 60px 60px; align-items:center; padding:11px 0; border-bottom:1px solid {BORDER}; }}
.ov-seg-rank {{ color:{FAINT}; font-size:13px; font-weight:700; }}
.ov-seg-name {{ color:{TXT}; font-size:13px; font-weight:600; }}
.ov-seg-rate {{ color:{NEG}; font-size:14px; font-weight:800; text-align:right; }}
.ov-seg-n {{ color:{MUTED}; font-size:13px; text-align:right; }}

.ov-donut-wrap {{ display:flex; align-items:center; gap:26px; }}
.ov-donut {{ width:150px; height:150px; border-radius:50%; flex-shrink:0; display:flex; align-items:center; justify-content:center; }}
.ov-donut-hole {{ width:104px; height:104px; border-radius:50%; background:{CARD}; display:flex; flex-direction:column; align-items:center; justify-content:center; }}
.ov-donut-big {{ color:{POS}; font-size:26px; font-weight:800; }}
.ov-donut-lbl {{ color:{MUTED}; font-size:11px; letter-spacing:0.08em; text-transform:uppercase; }}
.ov-donut-legend {{ flex:1; }}
.ov-leg {{ display:flex; align-items:center; color:{TXT}; font-size:13px; padding:7px 0; }}
.ov-leg-val {{ margin-left:auto; font-weight:700; }}

.ov-wide {{ margin-top:16px; }}
.ov-year-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }}
.ov-year {{ background:{CARD2}; border:1px solid {BORDER}; border-radius:10px; padding:14px; }}
.ov-year-head {{ display:flex; justify-content:space-between; color:{TXT}; font-size:14px; font-weight:800; margin-bottom:9px; }}
.ov-year-n {{ color:{MUTED}; font-weight:600; font-size:13px; }}
.ov-year-bar {{ display:flex; height:7px; border-radius:4px; overflow:hidden; background:{BG}; }}
.ov-year-legend {{ display:flex; gap:16px; flex-wrap:wrap; margin-top:14px; }}
.ov-year-legend .ov-leg {{ padding:0; font-size:12px; color:{MUTED}; }}

.ov-rev-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
.ov-rev {{ background:{CARD2}; border:1px solid {BORDER}; border-radius:10px; padding:14px; }}
.ov-rev-head {{ display:flex; justify-content:space-between; align-items:center; color:{TXT}; font-size:12px; font-weight:700; margin-bottom:8px; }}
.ov-rev-date {{ color:{FAINT}; font-weight:500; }}
.ov-rev-text {{ color:{MUTED}; font-size:12px; line-height:1.5; min-height:54px; }}
.ov-rev-foot {{ margin-top:10px; }}
.ov-badge {{ display:inline-block; font-size:11px; font-weight:700; padding:2px 9px; border-radius:9999px; border:1px solid; }}
</style>"""
