# -*- coding: utf-8 -*-
"""
app.py
======
"موازنتي" — Citizen Budget 2026/2027 educational web app.

A modern, RTL-first, Arabic-language Streamlit interface that turns the
official Citizen Budget (موازنة المواطن) into readable numbers, interactive
charts, a source-grounded AI assistant, a short quiz, and a citizen feedback
channel.

The document is organized into clearly labelled sections (see the headers
below) so that navigating and maintaining a single-file Streamlit app stays
manageable:

    Configuration -> Session State -> Theme & CSS -> Data Helpers ->
    Reusable UI Components -> Navigation -> Pages -> Footer
"""

from __future__ import annotations

import os
from html import escape
from typing import Any, Optional

import streamlit as st
import plotly.graph_objects as go

from utils.data import load_budget_data, SOURCE_LABEL
from utils.database import init_db, save_feedback, save_quiz_result
from utils import rag


# =============================================================================
# CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="موازنتي | افهم موازنة مصر ببساطة",
    page_icon="🇪🇬",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
VIDEO_PATH = os.path.join(ASSETS_DIR, "budget_explainer.mp4")

BUDGET_YEAR_LABEL = "2026/2027"

# `init_db` only creates tables if missing, so calling it on every rerun is
# cheap and keeps the app resilient to a fresh/empty database directory.
init_db()
budget = load_budget_data()


# =============================================================================
# SESSION STATE
# =============================================================================

NAV_ITEMS = [
    ("الرئيسية", "🏠", "الرئيسية"),
    ("شاهد الشرح", "🎬", "شاهد الشرح"),
    ("استكشف الموازنة", "📊", "استكشف الموازنة"),
    ("اعرف أكتر", "📚", "اعرف أكتر"),
    ("ماذا تعني للمواطن؟", "👥", "ماذا تعني الموازنة للمواطن؟"),
    ("اسأل عن الموازنة", "🤖", "اسأل عن الموازنة"),
    ("اختبار قصير", "📝", "اختبار قصير"),
    ("رأيك يهمنا", "💬", "رأيك يهمنا"),
]
PAGE_KEYS = [item[0] for item in NAV_ITEMS]
NAV_DISPLAY = {key: (icon, label) for key, icon, label in NAV_ITEMS}


def initialize_session_state() -> None:
    """Set up every piece of session state the app relies on, once."""
    defaults: dict[str, Any] = {
        "page": "الرئيسية",
        "dark_mode": False,
        "chat_history": [],
        "pending_question": None,
        "quiz_answers": {},
        "quiz_submitted": False,
        "quiz_saved": False,
        "explorer_view": "عرض مختصر",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if st.session_state["page"] not in PAGE_KEYS:
        st.session_state["page"] = "الرئيسية"


initialize_session_state()


# =============================================================================
# THEME & CSS
# =============================================================================

LIGHT_THEME = {
    "bg": "#f4f6f9",
    "surface": "#ffffff",
    "surface_secondary": "#f7f9fc",
    "text": "#141a24",
    "text_muted": "#616b7a",
    "border": "#e4e8ee",
    "primary": "#0f6b54",
    "primary_hover": "#0a4c3c",
    "primary_soft": "#e7f3ef",
    "success": "#1b7a4d",
    "warning": "#a9711f",
    "danger": "#b3413a",
    "info": "#2f5f9c",
    "shadow": "0 10px 28px rgba(16, 30, 51, 0.07)",
    "radius": "16px",
    "plot_template": "plotly_white",
}

DARK_THEME = {
    "bg": "#0e1418",
    "surface": "#161e24",
    "surface_secondary": "#1c252c",
    "text": "#eef2f4",
    "text_muted": "#9aa7b0",
    "border": "#2a353d",
    "primary": "#28a67d",
    "primary_hover": "#33c495",
    "primary_soft": "#173229",
    "success": "#33b074",
    "warning": "#d3a054",
    "danger": "#e2685f",
    "info": "#6ea3e0",
    "shadow": "0 10px 28px rgba(0, 0, 0, 0.45)",
    "radius": "16px",
    "plot_template": "plotly_dark",
}


def get_theme() -> dict:
    """Return the active theme's color/token dictionary."""
    return DARK_THEME if st.session_state["dark_mode"] else LIGHT_THEME


def build_css(theme: dict) -> str:
    """Build the application stylesheet from the active theme tokens."""
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');

:root {{
    --bg: {theme['bg']};
    --surface: {theme['surface']};
    --surface-secondary: {theme['surface_secondary']};
    --text: {theme['text']};
    --text-muted: {theme['text_muted']};
    --border: {theme['border']};
    --primary: {theme['primary']};
    --primary-hover: {theme['primary_hover']};
    --primary-soft: {theme['primary_soft']};
    --success: {theme['success']};
    --warning: {theme['warning']};
    --danger: {theme['danger']};
    --info: {theme['info']};
    --shadow: {theme['shadow']};
    --radius: {theme['radius']};
}}

html, body, [class*="css"], .stApp {{
    font-family: "Cairo", "Tajawal", "Noto Sans Arabic", Arial, sans-serif;
    direction: rtl;
}}

.stApp {{
    background: var(--bg);
    color: var(--text);
}}

.block-container {{
    max-width: 1240px;
    padding-top: 1.4rem;
    padding-bottom: 3rem;
}}

h1, h2, h3, h4, h5, h6 {{ color: var(--text); }}
p, span, label, li {{ color: var(--text); }}

/* ---------------------------------------------------------------------- */
/* Sidebar / navigation                                                    */
/* ---------------------------------------------------------------------- */

[data-testid="stSidebar"] {{
    background: var(--surface);
    border-left: 1px solid var(--border);
}}

[data-testid="stSidebar"] .block-container {{
    padding-top: 1.2rem;
}}

.sidebar-brand {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.35rem;
    font-weight: 800;
    color: var(--text);
    margin-bottom: 0.1rem;
}}

.sidebar-caption {{
    color: var(--text-muted);
    font-size: 0.8rem;
    margin-bottom: 0.9rem;
}}

[data-testid="stSidebar"] [role="radiogroup"] {{
    gap: 0.35rem !important;
}}

[data-testid="stSidebar"] [role="radiogroup"] label {{
    position: relative;
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    min-height: 44px !important;
    background: transparent !important;
    border: 1px solid transparent !important;
    border-radius: 12px !important;
    padding: 0.55rem 0.75rem !important;
    margin: 0 !important;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease;
    outline: none !important;
    box-shadow: none !important;
}}

[data-testid="stSidebar"] [role="radiogroup"] label:hover {{
    background: var(--primary-soft) !important;
}}

[data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"],
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
    background: var(--primary-soft) !important;
    border-color: var(--primary) !important;
}}

[data-testid="stSidebar"] [role="radiogroup"] label:focus,
[data-testid="stSidebar"] [role="radiogroup"] label:focus-visible,
[data-testid="stSidebar"] [role="radiogroup"] label:focus-within {{
    outline: none !important;
    box-shadow: none !important;
}}

[data-testid="stSidebar"] [role="radiogroup"] input[type="radio"]:focus,
[data-testid="stSidebar"] [role="radiogroup"] input[type="radio"]:focus-visible {{
    outline: none !important;
    box-shadow: none !important;
}}

[data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"] p,
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p,
[data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"] span,
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) span {{
    color: var(--primary) !important;
    font-weight: 700;
}}

.sidebar-footer {{
    margin-top: 1.4rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 0.75rem;
    line-height: 1.7;
}}

.theme-toggle-row .stButton > button {{
    min-height: 38px;
    font-size: 0.85rem;
}}

/* ---------------------------------------------------------------------- */
/* Hero / page headers                                                     */
/* ---------------------------------------------------------------------- */

.hero {{
    background: linear-gradient(135deg, var(--primary) 0%, {theme['info']} 130%);
    border-radius: 24px;
    padding: 2.1rem 2.3rem;
    color: #ffffff;
    box-shadow: var(--shadow);
    margin-bottom: 1.3rem;
    position: relative;
    overflow: hidden;
}}

.hero * {{ color: #ffffff; }}

.hero-badge {{
    display: inline-block;
    background: rgba(255,255,255,0.16);
    border: 1px solid rgba(255,255,255,0.24);
    padding: 0.32rem 0.75rem;
    border-radius: 999px;
    font-size: 0.82rem;
    margin-bottom: 0.75rem;
}}

.hero h1 {{
    font-size: clamp(1.7rem, 3.6vw, 2.8rem);
    line-height: 1.35;
    margin: 0;
    font-weight: 800;
}}

.hero p {{
    font-size: 1.02rem;
    max-width: 720px;
    margin: 0.65rem 0 0;
    opacity: 0.92;
}}

.trust-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: rgba(255,255,255,0.14);
    border: 1px solid rgba(255,255,255,0.22);
    border-radius: 999px;
    padding: 0.35rem 0.8rem;
    font-size: 0.82rem;
    margin-top: 0.9rem;
}}

.section-title {{
    font-weight: 800;
    font-size: 1.3rem;
    margin: 1.6rem 0 0.75rem;
    color: var(--text);
}}

.section-subtitle {{
    color: var(--text-muted);
    font-size: 0.92rem;
    margin: -0.5rem 0 0.9rem;
}}

/* ---------------------------------------------------------------------- */
/* Cards                                                                   */
/* ---------------------------------------------------------------------- */

.card, .soft-card, .citizen-card, .topic-card, .article-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.1rem 1.2rem;
    height: 100%;
    transition: box-shadow 0.15s ease, transform 0.15s ease;
}}

.card:hover, .soft-card:hover, .citizen-card:hover, .topic-card:hover, .article-card:hover {{
    box-shadow: var(--shadow);
}}

.stat-label {{
    color: var(--text-muted);
    font-size: 0.86rem;
    margin-bottom: 0.3rem;
}}

.stat-value {{
    font-size: 1.55rem;
    font-weight: 800;
    color: var(--primary);
    line-height: 1.3;
}}

.stat-note {{
    color: var(--text-muted);
    font-size: 0.78rem;
    margin-top: 0.3rem;
}}

.stat-source {{
    color: var(--text-muted);
    font-size: 0.72rem;
    margin-top: 0.55rem;
    border-top: 1px dashed var(--border);
    padding-top: 0.45rem;
}}

.feature-icon {{
    width: 42px;
    height: 42px;
    display: grid;
    place-items: center;
    border-radius: 12px;
    background: var(--primary-soft);
    font-size: 1.2rem;
    margin-bottom: 0.5rem;
}}

.source-pill {{
    display: inline-block;
    background: var(--surface-secondary);
    color: var(--info);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.2rem 0.6rem;
    font-size: 0.72rem;
}}

.category-pill {{
    display: inline-block;
    background: var(--primary-soft);
    color: var(--primary);
    border-radius: 999px;
    padding: 0.18rem 0.6rem;
    font-size: 0.72rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
}}

/* ---------------------------------------------------------------------- */
/* Budget flow / timeline                                                  */
/* ---------------------------------------------------------------------- */

.flow-wrap {{
    display: flex;
    flex-wrap: wrap;
    align-items: stretch;
    gap: 0.5rem;
    margin: 0.5rem 0 0.5rem;
}}

.flow-step {{
    flex: 1 1 150px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 0.9rem 0.8rem;
    text-align: center;
    font-weight: 700;
    font-size: 0.88rem;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 0.3rem;
}}

.flow-step .flow-icon {{ font-size: 1.3rem; }}

.flow-arrow {{
    align-self: center;
    color: var(--text-muted);
    font-size: 1.3rem;
    flex: 0 0 auto;
}}

/* ---------------------------------------------------------------------- */
/* AI status / chat                                                        */
/* ---------------------------------------------------------------------- */

.status-dot {{
    display: inline-block;
    width: 9px;
    height: 9px;
    border-radius: 50%;
    margin-left: 0.4rem;
}}

.status-online {{ background: var(--success); }}
.status-limited {{ background: var(--warning); }}

.level-chip {{
    display: inline-block;
    background: var(--surface-secondary);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.5rem 0.7rem;
    font-size: 0.82rem;
    color: var(--text-muted);
    margin-bottom: 0.3rem;
}}

[data-testid="stChatMessage"] {{
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 0.35rem 0.6rem;
    margin-bottom: 0.5rem;
    background: var(--surface);
}}

.source-card {{
    background: var(--surface-secondary);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.55rem 0.8rem;
    margin-top: 0.5rem;
    font-size: 0.78rem;
    color: var(--text-muted);
}}

.source-card b {{ color: var(--text); }}

.grounding-note {{
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 0.3rem;
}}

/* ---------------------------------------------------------------------- */
/* Generic components                                                      */
/* ---------------------------------------------------------------------- */

[data-testid="stMetric"] {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.8rem 1rem;
}}

[data-testid="stMetricLabel"], [data-testid="stMetricValue"] {{
    color: var(--text) !important;
}}

.stButton > button {{
    border-radius: 12px;
    border: 1px solid var(--border);
    font-family: "Cairo", sans-serif;
    font-weight: 700;
    min-height: 44px;
    background: var(--surface);
    color: var(--text);
    outline: none !important;
    box-shadow: none !important;
    transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}}

.stButton > button:hover {{
    border-color: var(--primary);
    background: var(--primary-soft);
}}

.stButton > button:focus,
.stButton > button:focus-visible,
.stButton > button:active {{
    outline: none !important;
    box-shadow: none !important;
}}

.stButton > button:active {{
    transform: translateY(1px);
}}

.stButton > button:disabled {{
    opacity: 0.55;
    cursor: not-allowed;
}}

.stButton > button[kind="primary"] {{
    background: var(--primary);
    color: #ffffff;
    border-color: var(--primary);
}}

.stButton > button[kind="primary"]:hover {{
    background: var(--primary-hover);
    border-color: var(--primary-hover);
}}

.stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"] {{
    border-radius: 10px !important;
}}

[data-testid="stExpander"] {{
    border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
    background: var(--surface);
}}

[data-testid="stDataFrame"] {{
    border-radius: 12px;
    overflow: hidden;
}}

hr {{ border-color: var(--border); }}

.footer-note {{
    color: var(--text-muted);
    font-size: 0.8rem;
    text-align: center;
    line-height: 1.8;
    margin-top: 2.4rem;
    padding-top: 1.2rem;
    border-top: 1px solid var(--border);
}}

.empty-state {{
    background: var(--surface-secondary);
    border: 1px dashed var(--border);
    border-radius: var(--radius);
    padding: 1.4rem;
    text-align: center;
    color: var(--text-muted);
}}

/* ---------------------------------------------------------------------- */
/* Responsive breakpoints                                                  */
/* ---------------------------------------------------------------------- */

@media (max-width: 1024px) {{
    .block-container {{ max-width: 100%; }}
}}

@media (max-width: 768px) {{
    .block-container {{
        padding-top: 0.7rem;
        padding-left: 0.85rem;
        padding-right: 0.85rem;
    }}

    .hero {{ padding: 1.4rem 1.2rem; border-radius: 18px; }}
    .hero h1 {{ font-size: 1.6rem; }}
    .hero p {{ font-size: 0.94rem; }}

    .flow-step {{ flex: 1 1 100%; }}
    .flow-arrow {{ transform: rotate(90deg); }}

    .stButton > button {{ width: 100%; }}
}}

@media (max-width: 480px) {{
    .stat-value {{ font-size: 1.3rem; }}
    .section-title {{ font-size: 1.12rem; }}
}}
</style>
"""


st.markdown(build_css(get_theme()), unsafe_allow_html=True)


# =============================================================================
# DATA HELPERS
# =============================================================================

def get_value(data: Optional[dict], section: str, key: str) -> Optional[dict]:
    """Return a structured budget entry safely, or None if unavailable."""
    if not isinstance(data, dict):
        return None
    section_data = data.get(section)
    if not isinstance(section_data, dict):
        return None
    entry = section_data.get(key)
    return entry if isinstance(entry, dict) else None


def format_source(entry: Optional[dict]) -> str:
    """Format source metadata (document + page) for UI display."""
    if not isinstance(entry, dict):
        return SOURCE_LABEL
    source = entry.get("source") or SOURCE_LABEL
    page = entry.get("page")
    return f"{source} · صفحة {page}" if page is not None else source


def format_value(entry: Optional[dict]) -> str:
    """Format one structured budget value as 'value unit'."""
    if not entry or entry.get("value") is None:
        return "—"
    value = entry.get("value")
    unit = entry.get("unit", "")
    return f"{value} {unit}".strip()


# =============================================================================
# REUSABLE UI COMPONENTS
# =============================================================================

def render_html(*parts: str) -> None:
    """
    Render one or more HTML fragments as a single compact block.

    Streamlit's markdown renderer follows CommonMark rules: a blank line or
    a run of leading spaces inside an HTML block can make the parser bail
    out of "raw HTML" mode and print the remaining tags as literal text.
    Joining everything into one whitespace-free string sidesteps that
    entirely, regardless of which parts are empty/optional.
    """
    st.markdown("".join(part for part in parts if part), unsafe_allow_html=True)


def render_hero(badge: str, title_html: str, subtitle: str, trust_text: str = "") -> None:
    """Render the main marketing-style hero block used on the home page."""
    trust_html = f'<div class="trust-badge">✓ {escape(trust_text)}</div>' if trust_text else ""
    render_html(
        '<div class="hero">',
        f'<div class="hero-badge">{escape(badge)}</div>',
        f"<h1>{title_html}</h1>",
        f"<p>{escape(subtitle)}</p>",
        trust_html,
        "</div>",
    )


def page_header(title: str, subtitle: str, icon: str = "") -> None:
    """Render a consistent, compact hero for inner pages."""
    render_html(
        '<div class="hero" style="padding:1.4rem 1.7rem; margin-bottom:1rem;">',
        f'<div class="hero-badge">{escape(icon)} موازنتي {BUDGET_YEAR_LABEL}</div>',
        f'<h1 style="font-size:1.75rem;">{escape(title)}</h1>',
        f"<p>{escape(subtitle)}</p>",
        "</div>",
    )


def render_section_header(title: str, subtitle: str = "") -> None:
    """Render a section title with an optional muted subtitle."""
    st.markdown(f'<div class="section-title">{escape(title)}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{escape(subtitle)}</div>', unsafe_allow_html=True)


def render_stat_card(label: str, entry: Optional[dict], note: str = "") -> None:
    """Render a verified KPI/statistic card with label, value, and source."""
    value = escape(format_value(entry))
    source = escape(format_source(entry)) if entry else "غير متاح في البيانات المنظمة"
    note_html = f'<div class="stat-note">{escape(note)}</div>' if note else ""
    render_html(
        '<div class="card">',
        f'<div class="stat-label">{escape(label)}</div>',
        f'<div class="stat-value">{value}</div>',
        note_html,
        f'<div class="stat-source">📎 {source}</div>',
        "</div>",
    )


def render_source_badge(entry_or_text) -> None:
    """Render a small inline source pill, accepting either a dict entry or text."""
    text = format_source(entry_or_text) if isinstance(entry_or_text, dict) else str(entry_or_text)
    st.markdown(f'<span class="source-pill">📎 {escape(text)}</span>', unsafe_allow_html=True)


def render_topic_card(icon: str, title: str, text: str) -> None:
    """Render a simple icon + title + text card, used for 'why it matters'."""
    render_html(
        '<div class="topic-card">',
        f'<div class="feature-icon">{icon}</div>',
        f'<h4 style="margin:0 0 0.4rem;">{escape(title)}</h4>',
        f'<div style="color:var(--text-muted); line-height:1.8; font-size:0.92rem;">{escape(text)}</div>',
        "</div>",
    )


def render_article_card(icon: str, title: str, description: str, category: str, page_no: int) -> None:
    """Render a knowledge-center article preview card with an expandable body."""
    render_html(
        '<div class="article-card" style="margin-bottom:0.7rem;">',
        f'<span class="category-pill">{escape(category)}</span>',
        f'<h4 style="margin:0 0 0.4rem;">{icon} {escape(title)}</h4>',
        "</div>",
    )
    with st.expander("اقرأ المزيد"):
        st.write(description)
        render_source_badge(f"{SOURCE_LABEL} · صفحة {page_no}")


def render_citizen_card(title: str, says: str, means: str, page_no: int) -> None:
    """Render a citizen-impact card structured as: says / means / source."""
    render_html(
        '<div class="citizen-card">',
        f'<h4 style="margin:0 0 0.6rem;">{escape(title)}</h4>',
        '<div class="stat-label" style="margin-bottom:0.15rem;">ما الذي تقوله الموازنة؟</div>',
        f'<div style="color:var(--text); line-height:1.85; font-size:0.92rem; margin-bottom:0.6rem;">{escape(says)}</div>',
        '<div class="stat-label" style="margin-bottom:0.15rem;">ماذا يعني هذا للمواطن؟</div>',
        f'<div style="color:var(--text-muted); line-height:1.85; font-size:0.92rem; margin-bottom:0.7rem;">{escape(means)}</div>',
        f'<span class="source-pill">📎 {escape(SOURCE_LABEL)} · صفحة {page_no}</span>',
        "</div>",
    )


def render_empty_state(message: str, icon: str = "ℹ️") -> None:
    """Render a calm placeholder instead of a broken-looking blank area."""
    st.markdown(
        f'<div class="empty-state">{icon}<br>{escape(message)}</div>',
        unsafe_allow_html=True,
    )


def render_chart_insight(text: str) -> None:
    """Render the 'ماذا يعني ذلك؟' data-storytelling block after a chart."""
    st.markdown("**ماذا يعني ذلك؟**")
    st.markdown(f'<div style="color:var(--text-muted); line-height:1.85;">{escape(text)}</div>', unsafe_allow_html=True)


def apply_plotly_theme(fig: go.Figure, dark_mode: bool = False, height: int = 420) -> go.Figure:
    """Apply a consistent, theme-aware layout to every Plotly chart."""
    theme = DARK_THEME if dark_mode else LIGHT_THEME
    fig.update_layout(
        template=theme["plot_template"],
        height=height,
        margin=dict(l=20, r=20, t=30, b=20),
        font=dict(family="Cairo, Tajawal, sans-serif", color=theme["text"]),
        paper_bgcolor=theme["surface"],
        plot_bgcolor=theme["surface"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(font_family="Cairo, sans-serif"),
    )
    fig.update_xaxes(gridcolor=theme["border"], zerolinecolor=theme["border"])
    fig.update_yaxes(gridcolor=theme["border"], zerolinecolor=theme["border"])
    return fig


def render_footer() -> None:
    """Render the closing footer with source attribution and a disclaimer."""
    render_html(
        '<div class="footer-note">',
        "<b>موازنتي 🇪🇬 — افهم موازنة مصر ببساطة</b><br>",
        f"{escape(SOURCE_LABEL)}<br>",
        "المعلومات الواردة في التطبيق مبنية على الوثيقة الرسمية لموازنة المواطن.<br>",
        "هذا التطبيق تعليمي ولا يمثل استشارة مالية أو قانونية.",
        "</div>",
    )


# =============================================================================
# NAVIGATION
# =============================================================================

with st.sidebar:
    st.markdown('<div class="sidebar-brand">🇪🇬 موازنتي</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sidebar-caption">Citizen Budget {BUDGET_YEAR_LABEL}</div>',
        unsafe_allow_html=True,
    )

    theme_col_light, theme_col_dark = st.columns(2)
    with theme_col_light:
        if st.button("☀️ فاتح", use_container_width=True, disabled=not st.session_state["dark_mode"]):
            st.session_state["dark_mode"] = False
            st.rerun()
    with theme_col_dark:
        if st.button("🌙 داكن", use_container_width=True, disabled=st.session_state["dark_mode"]):
            st.session_state["dark_mode"] = True
            st.rerun()

    st.markdown("---")

    current_page = st.session_state["page"]
    selected_page = st.radio(
        "التنقل",
        PAGE_KEYS,
        index=PAGE_KEYS.index(current_page),
        format_func=lambda key: "{}  {}".format(*NAV_DISPLAY[key]),
        label_visibility="collapsed",
    )
    st.session_state["page"] = selected_page

    render_html(
        '<div class="sidebar-footer">',
        f"📎 المصدر: {escape(SOURCE_LABEL)}<br>",
        "محتوى تعليمي مبسّط، وليس استشارة مالية أو قانونية.<br><br>",
        f"<b>موازنتي {BUDGET_YEAR_LABEL}</b><br>",
        "تجربة تعليمية مبنية على المصدر الرسمي",
        "</div>",
    )

page = st.session_state["page"]


def go_to(page_name: str) -> None:
    """Navigate to another page and trigger a rerun."""
    st.session_state["page"] = page_name


# =============================================================================
# HOME
# =============================================================================

if page == "الرئيسية":
    render_hero(
        badge="🇪🇬 الموازنة العامة بشكل أسهل",
        title_html="افهم موازنة مصر<br>في دقائق، مش عشرات الصفحات",
        subtitle=(
            "من أين تأتي أموال الدولة؟ أين تُنفق؟ وما الذي تعنيه الموازنة للمواطن؟ "
            "منصة تعليمية تفاعلية تحول بيانات موازنة المواطن "
            f"{BUDGET_YEAR_LABEL} إلى أرقام مفهومة ورسوم تفاعلية وإجابات موثقة من المصدر الرسمي."
        ),
        trust_text=f"أرقام موثقة من موازنة المواطن {BUDGET_YEAR_LABEL}",
    )

    action_a, action_b, action_c = st.columns(3)
    if action_a.button("📊 استكشف الموازنة", use_container_width=True, type="primary"):
        go_to("استكشف الموازنة")
        st.rerun()
    if action_b.button("🤖 اسأل المساعد الذكي", use_container_width=True):
        go_to("اسأل عن الموازنة")
        st.rerun()
    if action_c.button("🎬 شاهد الشرح", use_container_width=True):
        go_to("شاهد الشرح")
        st.rerun()

    render_section_header("أهم الأرقام في نظرة واحدة")

    home_entries = [
        ("إجمالي المصروفات", get_value(budget, "expenditures", "total_expenditure_budget_sector")),
        ("إجمالي الإيرادات", get_value(budget, "revenues", "total_revenues_budget_sector")),
        ("الفائض الأولي المستهدف", get_value(budget, "primary_surplus", "target_pct_of_gdp")),
        ("العجز الكلي / الناتج", get_value(budget, "deficit", "overall_deficit_to_gdp")),
        ("النمو الاقتصادي", get_value(budget, "economic_indicators", "real_growth_rate")),
        ("الدين / الناتج المستهدف", get_value(budget, "debt", "budget_sector_debt_to_gdp_target")),
        ("مخصصات الصحة", get_value(budget, "health", "health_total_allocation")),
        ("مخصصات التعليم", get_value(budget, "education", "education_total_allocation")),
    ]

    for start in range(0, len(home_entries), 4):
        cols = st.columns(4)
        for i, (label, entry) in enumerate(home_entries[start:start + 4]):
            with cols[i]:
                render_stat_card(label, entry)

    render_section_header(
        "رحلة الموازنة",
        "من أين تبدأ الأموال، وأين تنتهي؟",
    )

    flow_steps = [
        ("💰", "إيرادات الدولة"),
        ("🧭", "تخصيص الموارد"),
        ("🏗️", "الإنفاق على الأولويات"),
        ("⚖️", "العجز / الفائض"),
        ("🏦", "التمويل وإدارة الدين"),
    ]
    flow_html = '<div class="flow-wrap">'
    for index, (icon, label) in enumerate(flow_steps):
        flow_html += f'<div class="flow-step"><span class="flow-icon">{icon}</span>{escape(label)}</div>'
        if index < len(flow_steps) - 1:
            flow_html += '<div class="flow-arrow">‹</div>'
    flow_html += "</div>"
    st.markdown(flow_html, unsafe_allow_html=True)

    render_section_header("لماذا تهمك الموازنة؟")

    why_it_matters = [
        ("🏥", "الصحة", "مخصصات الصحة تمول التأمين الصحي الشامل والأدوية والمستلزمات الطبية التي قد تحتاجها أنت أو أسرتك."),
        ("🎓", "التعليم", "تمويل التعليم ينعكس على جودة المدارس والكتب المدرسية والتغذية المدرسية لأبنائك."),
        ("🛡️", "الحماية الاجتماعية", "برامج مثل تكافل وكرامة ودعم السلع التموينية تصل مباشرة إلى الأسر الأولى بالرعاية."),
        ("🏭", "الصناعة وفرص العمل", "حوافز المشروعات الصغيرة والقطاعات الإنتاجية ترتبط بفرص العمل المتاحة في السوق."),
        ("🚆", "النقل", "موارد النقل والسكك الحديدية تؤثر على تنقلك اليومي وتكلفته."),
        ("💰", "الضرائب", "السياسة الضريبية تحدد كيف تُموَّل كل هذه الخدمات، وتؤثر على دخلك ومعاملاتك."),
    ]
    for start in range(0, len(why_it_matters), 3):
        cols = st.columns(3)
        for i, (icon, title, text) in enumerate(why_it_matters[start:start + 3]):
            with cols[i]:
                render_topic_card(icon, title, text)

    render_section_header("إزاي تستخدم موازنتي؟")
    f1, f2, f3 = st.columns(3)
    how_to_use = [
        (f1, "📊", "استكشف", "قارن الإيرادات والمصروفات والدين وأهم برامج الدعم برسوم تفاعلية."),
        (f2, "🤖", "اسأل", "اكتب سؤالك بالعربية واحصل على إجابة مرتبطة بنصوص الوثيقة الرسمية."),
        (f3, "🧠", "اختبر نفسك", "اختبار قصير يثبت أهم المفاهيم والأرقام بطريقة بسيطة وسريعة."),
    ]
    for col, icon, title, text in how_to_use:
        with col:
            render_topic_card(icon, title, text)


# =============================================================================
# VIDEO
# =============================================================================

elif page == "شاهد الشرح":
    page_header(
        "🎬 افهم الموازنة في أقل من 3 دقائق",
        "ابدأ من هنا لو عايز تفهم الفكرة العامة للموازنة قبل الدخول في التفاصيل.",
        "🎬",
    )

    left, right = st.columns([1.5, 1])
    with left:
        if os.path.exists(VIDEO_PATH):
            st.video(VIDEO_PATH)
        else:
            render_empty_state(
                "الفيديو التعريفي قيد الإضافة. ضع الملف باسم "
                "budget_explainer.mp4 داخل مجلد assets وسيظهر تلقائيًا هنا.",
                icon="🎬",
            )

    with right:
        st.markdown("### في أقل من 3 دقائق هتعرف")
        st.markdown(
            """
            - ما هي الموازنة العامة؟
            - الدولة تحصل على أموالها من أين؟
            - أين تنفق الدولة هذه الأموال؟
            - ماذا يعني العجز والفائض الأولي؟
            - ما أبرز مستهدفات موازنة {year}؟
            """.format(year=BUDGET_YEAR_LABEL)
        )
        render_source_badge(SOURCE_LABEL)


# =============================================================================
# EXPLORER
# =============================================================================

elif page == "استكشف الموازنة":
    page_header(
        "لوحة الموازنة",
        "استكشف أهم الأرقام والمؤشرات بطريقة تفاعلية.",
        "📊",
    )

    dark_mode = st.session_state["dark_mode"]

    view_toggle_col, _ = st.columns([1, 2])
    with view_toggle_col:
        st.session_state["explorer_view"] = st.radio(
            "طريقة العرض",
            ["عرض مختصر", "عرض تفصيلي"],
            horizontal=True,
            index=["عرض مختصر", "عرض تفصيلي"].index(st.session_state["explorer_view"]),
        )
    detailed_view = st.session_state["explorer_view"] == "عرض تفصيلي"

    tab_finance, tab_services, tab_economy, tab_social = st.tabs(
        ["المالية العامة", "الخدمات", "الاقتصاد", "الحماية الاجتماعية"]
    )

    # -- المالية العامة: revenues vs expenditure, debt, macro table ---------
    with tab_finance:
        rev = get_value(budget, "revenues", "total_revenues_budget_sector")
        exp = get_value(budget, "expenditures", "total_expenditure_budget_sector")

        if rev and exp:
            m1, m2, m3 = st.columns(3)
            m1.metric("الإيرادات", format_value(rev))
            m2.metric("المصروفات", format_value(exp))
            try:
                gap = float(exp["value"]) - float(rev["value"])
                m3.metric("الفجوة التقريبية", f"{gap:.1f} {exp.get('unit', '')}")
            except (TypeError, ValueError):
                m3.metric("الفجوة التقريبية", "—")

            st.markdown("#### أين تذهب أموال الموازنة؟")
            fig = go.Figure()
            fig.add_bar(name="الإيرادات", x=[BUDGET_YEAR_LABEL], y=[rev["value"]])
            fig.add_bar(name="المصروفات", x=[BUDGET_YEAR_LABEL], y=[exp["value"]])
            fig.update_layout(barmode="group", yaxis_title=exp.get("unit") or rev.get("unit") or "")
            st.plotly_chart(apply_plotly_theme(fig, dark_mode), use_container_width=True)
            st.caption(f"المصدر: {format_source(rev)} · {format_source(exp)}")
            render_chart_insight(
                "المصروفات المستهدفة أعلى من الإيرادات، وهو ما يرتبط بالعجز المستهدف في الموازنة."
            )
        else:
            render_empty_state("بيانات الإيرادات والمصروفات غير متاحة في البيانات المنظمة.")

        st.markdown("#### الدين كنسبة من الناتج المحلي")
        debt_keys = [
            ("2025/2026", "debt_to_gdp_2025_2026"),
            ("2026/2027", "debt_to_gdp_2026_2027"),
            ("2027/2028", "debt_to_gdp_2027_2028"),
            ("2028/2029", "debt_to_gdp_2028_2029"),
            ("2029/2030", "debt_to_gdp_2029_2030"),
        ]
        debt_points = []
        for year, key in debt_keys:
            entry = get_value(budget, "debt", key)
            if entry and entry.get("value") is not None:
                debt_points.append((year, entry))

        if len(debt_points) >= 2:
            years = [x[0] for x in debt_points]
            values = [x[1]["value"] for x in debt_points]
            fig = go.Figure(
                go.Scatter(
                    x=years, y=values, mode="lines+markers+text",
                    text=[f"{v}%" for v in values], textposition="top center",
                )
            )
            fig.update_layout(yaxis_title="% من الناتج المحلي الإجمالي")
            st.plotly_chart(apply_plotly_theme(fig, dark_mode), use_container_width=True)
            render_source_badge(debt_points[0][1])
            render_chart_insight("الاتجاه العام يستهدف خفض نسبة الدين إلى الناتج المحلي تدريجيًا خلال السنوات القادمة.")
        else:
            target = get_value(budget, "debt", "budget_sector_debt_to_gdp_target")
            if target:
                fig = go.Figure(go.Bar(x=[BUDGET_YEAR_LABEL], y=[target["value"]]))
                fig.update_layout(yaxis_title="% من الناتج المحلي الإجمالي")
                st.plotly_chart(apply_plotly_theme(fig, dark_mode, 340), use_container_width=True)
                render_source_badge(target)
            else:
                render_empty_state("بيانات الدين غير متاحة في البيانات المنظمة.")

        if detailed_view:
            st.markdown("#### أهم مستهدفات الاقتصاد الكلي")
            macro_keys = [
                ("معدل النمو الحقيقي", "real_growth_rate"),
                ("معدل التضخم", "inflation_deflator"),
                ("معدل الاستثمار", "investment_rate"),
                ("معدل الادخار", "savings_rate"),
                ("معدل البطالة المستهدف", "target_unemployment_rate"),
            ]
            table_rows = []
            for label, key in macro_keys:
                entry = get_value(budget, "economic_indicators", key)
                if entry and entry.get("value") is not None:
                    table_rows.append(
                        {"المؤشر": label, "القيمة": format_value(entry), "المصدر": format_source(entry)}
                    )
            if table_rows:
                st.dataframe(table_rows, use_container_width=True, hide_index=True)
            else:
                render_empty_state("بيانات مؤشرات الاقتصاد الكلي غير متاحة.")

    # -- الخدمات: health / education / research ------------------------------
    with tab_services:
        st.markdown("#### الصحة والتعليم والبحث العلمي")
        he_items = [
            ("الصحة", get_value(budget, "health", "health_total_allocation")),
            ("التعليم", get_value(budget, "education", "education_total_allocation")),
            ("البحث العلمي", get_value(budget, "education", "scientific_research_allocation")),
        ]
        he_labels, he_values, he_sources = [], [], []
        for label, entry in he_items:
            if entry and entry.get("pct_of_gdp") is not None:
                he_labels.append(label)
                he_values.append(entry["pct_of_gdp"])
                he_sources.append(entry)

        if he_values:
            fig = go.Figure(go.Bar(x=he_labels, y=he_values, text=[f"{v}%" for v in he_values], textposition="outside"))
            fig.update_layout(yaxis_title="% من الناتج المحلي الإجمالي")
            st.plotly_chart(apply_plotly_theme(fig, dark_mode, 400), use_container_width=True)
            st.caption(" · ".join(format_source(x) for x in he_sources))
            render_chart_insight(
                "تخصيص موارد للصحة والتعليم والبحث العلمي يعكس أولوية الاستثمار في الإنسان ضمن الموازنة."
            )
        else:
            render_empty_state("بيانات الصحة والتعليم والبحث العلمي غير متاحة.")

        if detailed_view:
            c1, c2 = st.columns(2)
            with c1:
                render_stat_card("مخصصات الصحة", get_value(budget, "health", "health_total_allocation"))
            with c2:
                render_stat_card("مخصصات التعليم", get_value(budget, "education", "education_total_allocation"))

    # -- الاقتصاد: economic support -------------------------------------------
    with tab_economy:
        st.markdown("#### دعم النشاط الاقتصادي")
        support_keys = {
            "دعم الصادرات": "export_burden_refund_support",
            "القطاعات الإنتاجية": "productive_sectors_financing_facilities",
            "السياحة": "tourism_sector_support",
            "صناعة السيارات": "car_industry_support",
            "المشروعات الصغيرة": "small_medium_enterprises_incentives",
            "الصناعات ذات الأولوية": "priority_industries_incentives",
        }
        labels, values, src = [], [], []
        for label, key in support_keys.items():
            entry = get_value(budget, "economic_support", key)
            if entry and entry.get("value") is not None:
                labels.append(label)
                values.append(entry["value"])
                src.append(entry)

        if values:
            fig = go.Figure(go.Bar(x=values, y=labels, orientation="h"))
            fig.update_layout(xaxis_title="مليار جنيه")
            st.plotly_chart(apply_plotly_theme(fig, dark_mode, 410), use_container_width=True)
            render_source_badge(src[0])
            render_chart_insight(
                "برامج دعم النشاط الاقتصادي تستهدف تحفيز التصدير والصناعة والسياحة والمشروعات الصغيرة والمتوسطة."
            )
        else:
            render_empty_state("بيانات دعم النشاط الاقتصادي غير متاحة.")

    # -- الحماية الاجتماعية ----------------------------------------------------
    with tab_social:
        st.markdown("#### الحماية الاجتماعية")
        social_keys = {
            "السلع التموينية": "commodity_supply_subsidy",
            "الكهرباء": "electricity_subsidy",
            "الأدوية": "medicine_allocation",
            "المستلزمات الطبية": "medical_supplies_allocation",
            "شراء القمح المحلي": "local_wheat_purchase_financing",
            "الإسكان لمحدودي الدخل": "housing_low_middle_income",
        }
        labels, values, src = [], [], []
        for label, key in social_keys.items():
            entry = get_value(budget, "social_protection", key)
            if entry and entry.get("value") is not None:
                labels.append(label)
                values.append(entry["value"])
                src.append(entry)

        if values:
            fig = go.Figure(go.Bar(x=labels, y=values))
            fig.update_layout(yaxis_title="مليار جنيه")
            st.plotly_chart(apply_plotly_theme(fig, dark_mode, 410), use_container_width=True)
            render_source_badge(src[0])
            render_chart_insight(
                "هذه المخصصات تصل بشكل مباشر إلى الأسر عبر دعم السلع والطاقة والصحة والإسكان."
            )
        else:
            render_empty_state("بيانات الحماية الاجتماعية غير متاحة.")


# =============================================================================
# ARTICLES
# =============================================================================

elif page == "اعرف أكتر":
    page_header(
        "اعرف أكتر",
        "مقالات قصيرة تشرح أهم مفاهيم الموازنة بلغة مباشرة وبعيدة عن التعقيد.",
        "📚",
    )

    ARTICLES = [
        ("💡", "ما هي الموازنة العامة؟", "أساسيات",
         "الموازنة العامة هي خطة الدولة المالية للعام القادم، وتوضح الإيرادات المتوقعة وأولويات الإنفاق لتحقيق الأهداف الاقتصادية والاجتماعية.", 4),
        ("💰", "من أين تحصل الدولة على الإيرادات؟", "الإيرادات",
         "تستهدف موازنة {y} إجمالي إيرادات بنحو 4.1 تريليون جنيه، وتمثل الإيرادات الضريبية الجزء الأكبر منها.".format(y=BUDGET_YEAR_LABEL), 13),
        ("🏗️", "أين تنفق الدولة أموالها؟", "المصروفات",
         "تشمل المصروفات الأجور والدعم والمنح والمزايا الاجتماعية والفوائد والاستثمارات والخدمات العامة المختلفة.", 13),
        ("⚖️", "ما هو عجز الموازنة؟", "العجز والدين",
         "العجز يحدث عندما تزيد المصروفات على الإيرادات. وتستهدف الموازنة خفض العجز الكلي إلى نحو 4.9% من الناتج المحلي الإجمالي.", 13),
        ("📈", "ما هو الفائض الأولي؟", "العجز والدين",
         "هو الفرق بين الإيرادات والمصروفات قبل احتساب فوائد الدين. وتستهدف الموازنة فائضًا أوليًا يعادل 5% من الناتج المحلي.", 13),
        ("🏦", "ما هو الدين العام؟", "العجز والدين",
         "الدين يمثل التزامات تمويلية على الدولة، وتستهدف الموازنة خفض دين أجهزة الموازنة كنسبة من الناتج المحلي تدريجيًا.", 50),
        ("🛡️", "الحماية الاجتماعية", "الخدمات",
         "تتضمن الموازنة مخصصات للسلع التموينية والكهرباء وتكافل وكرامة وبرامج أخرى تستهدف الفئات الأولى بالرعاية.", 20),
        ("🏭", "دعم النشاط الاقتصادي", "الاقتصاد",
         "تتضمن الموازنة برامج لدعم التصدير والسياحة والصناعة والمشروعات الصغيرة والمتوسطة لتحفيز النشاط الاقتصادي.", 14),
        ("🏥", "الصحة والتعليم", "الخدمات",
         "تخصص الموازنة موارد كبيرة للصحة والتعليم والبحث العلمي باعتبارها استثمارات أساسية في الإنسان والخدمات العامة.", 26),
        ("🧑‍🤝‍🧑", "لماذا تهم الموازنة المواطن؟", "أساسيات",
         "لأن قرارات الموازنة تنعكس على جودة الخدمات والدعم والاستثمارات العامة وفرص العمل ومستوى النشاط الاقتصادي.", 4),
    ]

    categories = ["الكل"] + sorted({item[2] for item in ARTICLES})
    selected_category = st.selectbox("تصفية حسب التصنيف", categories)

    filtered_articles = [
        item for item in ARTICLES if selected_category == "الكل" or item[2] == selected_category
    ]

    if not filtered_articles:
        render_empty_state("لا توجد مقالات في هذا التصنيف حاليًا.")
    else:
        for start in range(0, len(filtered_articles), 2):
            cols = st.columns(2)
            for i, (icon, title, category, body, page_no) in enumerate(filtered_articles[start:start + 2]):
                with cols[i]:
                    render_article_card(icon, title, body, category, page_no)


# =============================================================================
# CITIZEN IMPACT
# =============================================================================

elif page == "ماذا تعني للمواطن؟":
    page_header(
        "ماذا تعني الموازنة للمواطن؟",
        "ربط الأرقام بما يهم الناس: الصحة، التعليم، الدعم، الضرائب، النقل، وفرص النشاط الاقتصادي.",
        "👥",
    )

    CITIZEN_TOPICS = [
        ("🏥 الصحة",
         "بلغت مخصصات الصحة 862.9 مليار جنيه، وتشمل موارد للتأمين الصحي الشامل والأدوية والمستلزمات الطبية.",
         "زيادة مخصصات الصحة ترتبط بتحسين إتاحة الخدمة الصحية والتغطية التأمينية للمواطنين.", 26),
        ("🎓 التعليم",
         "تتضمن مخصصات التعليم تمويل الخدمات التعليمية والكتب المدرسية والتغذية المدرسية وحوافز للعاملين بالقطاع.",
         "هذا التمويل ينعكس مباشرة على جودة المدارس والخدمات المقدمة للطلاب وأسرهم.", 26),
        ("🛡️ الحماية الاجتماعية",
         "تضم الموازنة برامج دعم السلع التموينية والكهرباء وبرامج التحويلات النقدية مثل تكافل وكرامة.",
         "هذه البرامج تستهدف دعم الأسر الأولى بالرعاية بشكل مباشر في دخلها ونفقاتها الأساسية.", 20),
        ("🏭 المشروعات الصغيرة",
         "توجد حوافز وبرامج تمويلية لدعم المشروعات الصغيرة والمتوسطة والقطاعات الإنتاجية ذات الأولوية.",
         "هذا الدعم يرتبط بفرص العمل الجديدة وبيئة الأعمال المتاحة لأصحاب المشروعات الصغيرة.", 14),
        ("🚆 النقل",
         "تتضمن الموازنة موارد مرتبطة بخدمات النقل والسكك الحديدية ودعم بعض الاشتراكات والخدمات العامة.",
         "هذه الموارد تؤثر على جودة وتكلفة تنقلك اليومي عبر وسائل النقل العام.", 21),
        ("💰 الضرائب",
         "تسعى السياسة الضريبية إلى زيادة الحصيلة مع تبسيط الإجراءات ورفع كفاءة التحصيل دون الاعتماد على أرقام غير موثقة خارج الوثيقة.",
         "السياسة الضريبية هي المصدر الأساسي لتمويل الخدمات العامة التي تستفيد منها بشكل يومي.", 42),
    ]

    for start in range(0, len(CITIZEN_TOPICS), 2):
        cols = st.columns(2)
        for i, (title, says, means, page_no) in enumerate(CITIZEN_TOPICS[start:start + 2]):
            with cols[i]:
                render_citizen_card(title, says, means, page_no)


# =============================================================================
# CHATBOT
# =============================================================================

elif page == "اسأل عن الموازنة":
    page_header(
        "اسأل موازنتي",
        f"اسأل عن أرقام ومفاهيم موازنة {BUDGET_YEAR_LABEL} وسأجيبك من الوثيقة الرسمية.",
        "🤖",
    )

    st.markdown(
        '<div class="grounding-note">الإجابة مبنية على المعلومات المسترجعة من الوثيقة الرسمية.</div>',
        unsafe_allow_html=True,
    )

    controls_left, controls_right = st.columns([2, 1])
    with controls_left:
        level = st.radio("طريقة الشرح", ["ببساطة", "لطالب", "بتفصيل"], horizontal=True)
        level_captions = {
            "ببساطة": "شرح سريع ومباشر.",
            "لطالب": "شرح متوسط بتفاصيل إضافية.",
            "بتفصيل": "شرح أعمق مع أرقام وسياق أوسع.",
        }
        st.markdown(f'<span class="level-chip">{level_captions[level]}</span>', unsafe_allow_html=True)
    with controls_right:
        if st.button("🗑️ مسح المحادثة", use_container_width=True):
            st.session_state["chat_history"] = []
            st.rerun()

    with st.expander("⚙️ حالة المساعد"):
        try:
            llm_ok = rag.is_llm_available()
        except Exception:
            llm_ok = False

        if llm_ok:
            st.markdown(
                '<span class="status-dot status-online"></span> '
                '**المساعد متاح** — يمكنك طرح سؤالك.',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="status-dot status-limited"></span> '
                '**المساعد يعمل بوضع محدود** — يمكنك الاستمرار في استخدام المحتوى.',
                unsafe_allow_html=True,
            )

    if not st.session_state["chat_history"]:
        st.info(
            "أهلًا بيك 👋 اسأل أي سؤال عن موازنة المواطن، وهجاوبك بالاعتماد على النص الرسمي مع ذكر المصدر.",
            icon="💬",
        )

    st.markdown("### أسئلة مقترحة")
    suggested = list(getattr(rag, "SUGGESTED_QUESTIONS", []))[:4]
    if suggested:
        cols = st.columns(2)
        for i, question_text in enumerate(suggested):
            if cols[i % 2].button(question_text, key=f"suggested_{i}", use_container_width=True):
                st.session_state["pending_question"] = question_text
                st.rerun()

    st.markdown("---")

    def render_sources(sources: list) -> None:
        """Render a compact, de-duplicated source card for a chat answer."""
        if not sources:
            return
        unique, seen = [], set()
        for source in sources:
            page_no = source.get("page", "—")
            section = source.get("section", "غير محدد")
            key = (page_no, section)
            if key not in seen:
                seen.add(key)
                unique.append(f"صفحة {page_no} · {section}")
        render_html(
            '<div class="source-card">',
            "📎 <b>المصدر الرسمي</b><br>",
            f"{escape(SOURCE_LABEL)}<br>",
            " | ".join(escape(u) for u in unique),
            "</div>",
        )

    for message in st.session_state["chat_history"][-20:]:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            render_sources(message.get("sources") or [])

    user_input = st.chat_input("اكتب سؤالك عن الموازنة هنا...")
    question = user_input or st.session_state.pop("pending_question", None)

    if question:
        st.session_state["chat_history"].append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            with st.status("🔎 أبحث في الوثيقة الرسمية...", expanded=False) as status:
                try:
                    calc_answer = rag.calculate_from_structured_data(question, budget)
                except Exception:
                    calc_answer = None

                if calc_answer:
                    answer_text = calc_answer
                    sources = []
                    status.update(label="✅ تم إيجاد إجابة من البيانات المنظمة.", state="complete")
                else:
                    status.update(label="🤖 أصيغ الإجابة...", state="running")
                    try:
                        result = rag.answer_question(question, level=level)
                        answer_text = result.get("answer") or "لم أجد في الوثيقة الرسمية معلومات كافية للإجابة بدقة على هذا السؤال."
                        sources = result.get("sources", []) or []
                        status.update(label="✅ تم إنشاء الإجابة.", state="complete")
                    except Exception:
                        answer_text = (
                            "عذرًا، تعذر تنفيذ الطلب حاليًا. "
                            "حاول مرة أخرى بعد قليل."
                        )
                        sources = []
                        status.update(
                            label="⚠️ تعذر تنفيذ الطلب، حاول مرة أخرى.",
                            state="error",
                        )

            st.write(answer_text)
            render_sources(sources)

            st.session_state["chat_history"].append(
                {"role": "assistant", "content": answer_text, "sources": sources}
            )


# =============================================================================
# QUIZ
# =============================================================================

elif page == "اختبار قصير":
    page_header(
        "اختبر فهمك",
        "خمسة أسئلة سريعة لتثبيت أهم مفاهيم وأرقام الموازنة.",
        "📝",
    )

    QUIZ = [
        {
            "q": "ما المقصود بالفائض الأولي؟",
            "options": [
                "الفرق بين الإيرادات والمصروفات باستثناء فوائد الدين",
                "إجمالي الضرائب فقط",
                "إجمالي الدين الخارجي",
            ],
            "answer": 0,
            "explain": "الفائض الأولي يقيس الفرق بين الإيرادات والمصروفات قبل احتساب فوائد الدين.",
        },
        {
            "q": "كم يبلغ إجمالي المصروفات المستهدف تقريبًا؟",
            "options": ["3.5 تريليون جنيه", "5.2 تريليون جنيه", "8.3 تريليون جنيه"],
            "answer": 1,
            "explain": "إجمالي المصروفات المستهدف يقارب 5.2 تريليون جنيه.",
        },
        {
            "q": "ما العجز الكلي المستهدف كنسبة من الناتج المحلي؟",
            "options": ["4.9%", "14.4%", "78.1%"],
            "answer": 0,
            "explain": "المستهدف هو خفض العجز الكلي إلى نحو 4.9% من الناتج المحلي الإجمالي.",
        },
        {
            "q": "ما نسبة مخصصات التعليم إلى الناتج المحلي؟",
            "options": ["4.2%", "6%", "1%"],
            "answer": 1,
            "explain": "مخصصات التعليم تعادل نحو 6% من الناتج المحلي وفق البيانات الرسمية المستخدمة في المشروع.",
        },
        {
            "q": "ما الهدف الأساسي من موازنة المواطن؟",
            "options": ["تبسيط المعلومات المالية للمواطن", "استبدال الموازنة العامة", "تقديم استشارات استثمارية"],
            "answer": 0,
            "explain": "موازنة المواطن تهدف إلى تبسيط البيانات العامة وإتاحتها بصورة أكثر وضوحًا للجمهور.",
        },
    ]
    total_questions = len(QUIZ)

    if not st.session_state["quiz_submitted"]:
        answered = sum(
            1 for i in range(total_questions)
            if st.session_state["quiz_answers"].get(i) is not None
        )
        st.progress(answered / total_questions, text=f"أجبت {answered} من {total_questions}")

        for i, item in enumerate(QUIZ):
            st.markdown(f"**السؤال {i + 1} من {total_questions} — {item['q']}**")
            current_choice = st.session_state["quiz_answers"].get(i)
            selected = st.radio(
                f"quiz_q_{i}",
                item["options"],
                index=item["options"].index(current_choice) if current_choice in item["options"] else None,
                key=f"quiz_widget_{i}",
                label_visibility="collapsed",
            )
            st.session_state["quiz_answers"][i] = selected
            st.markdown("")

        all_answered = all(
            st.session_state["quiz_answers"].get(i) is not None for i in range(total_questions)
        )
        if st.button("✅ عرض النتيجة", type="primary", use_container_width=True, disabled=not all_answered):
            st.session_state["quiz_submitted"] = True
            st.session_state["quiz_saved"] = False
            st.rerun()

        if not all_answered:
            st.caption("جاوب على كل الأسئلة عشان تقدر تشوف نتيجتك.")

    else:
        answers = st.session_state["quiz_answers"]
        score = 0
        st.markdown("### مراجعة الإجابات")

        for i, item in enumerate(QUIZ):
            selected = answers.get(i)
            correct_answer = item["options"][item["answer"]]
            is_correct = selected == correct_answer
            score += int(is_correct)

            if is_correct:
                st.success(f"{i + 1}) إجابة صحيحة — {item['explain']}")
            else:
                st.error(f"{i + 1}) الإجابة الصحيحة: {correct_answer} — {item['explain']}")

        percent = round((score / total_questions) * 100)

        if percent >= 80:
            headline = "🎉 ممتاز!"
        elif percent >= 50:
            headline = "👍 نتيجة جيدة!"
        else:
            headline = "💪 استمر في التعلم!"

        st.markdown(f"## {headline}")
        st.metric("النتيجة النهائية", f"{score} / {total_questions}", f"{percent}%")

        if not st.session_state["quiz_saved"]:
            try:
                if save_quiz_result(score, total_questions):
                    st.session_state["quiz_saved"] = True
            except Exception:
                pass

        if st.button("🔄 إعادة الاختبار", use_container_width=True):
            for i in range(total_questions):
                st.session_state.pop(f"quiz_widget_{i}", None)
            st.session_state["quiz_answers"] = {}
            st.session_state["quiz_submitted"] = False
            st.session_state["quiz_saved"] = False
            st.rerun()


# =============================================================================
# FEEDBACK
# =============================================================================

elif page == "رأيك يهمنا":
    page_header(
        "رأيك يهمنا",
        "ساعدنا نخلّي فهم الموازنة أسهل وأوضح.",
        "💬",
    )

    left, right = st.columns([1.4, 1])

    with left:
        with st.form("feedback_form", clear_on_submit=True):
            helpful = st.radio("هل ساعدك الموقع على فهم الموازنة؟", ["نعم", "إلى حد ما", "لا"], horizontal=True)
            topic = st.selectbox(
                "ما الموضوع الذي تريد معرفة المزيد عنه؟",
                ["التعليم", "الصحة", "الدعم", "الضرائب", "الدين", "الاستثمار", "الصناعة", "موضوع آخر"],
            )
            comment = st.text_area("تعليق إضافي", placeholder="اكتب اقتراحك أو ملاحظتك هنا...", max_chars=1000)
            submitted = st.form_submit_button("إرسال الملاحظة", type="primary", use_container_width=True)

        if submitted:
            try:
                ok = save_feedback(helpful, topic, comment)
            except Exception:
                ok = False

            if ok:
                st.success("شكرًا لمشاركتك — تم حفظ رأيك بنجاح. 🙏")
            else:
                st.error("تعذر حفظ الملاحظة الآن. جرّب مرة أخرى.")

    with right:
        render_topic_card(
            "💬",
            "ليه رأيك مهم؟",
            "الهدف من المشروع مش بس عرض الموازنة، لكن اختبار هل المواطن فعلاً قدر يفهمها بسهولة. "
            "ملاحظتك تساعد في تحسين المحتوى وطريقة الشرح.",
        )


# =============================================================================
# FOOTER
# =============================================================================

render_footer()