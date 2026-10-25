"""Clinical enterprise design system tokens, CSS styles, and reusable UI components for PharmaTrack.

Strictly adheres to:
- Solid white surfaces (#FFFFFF) and light grey sidebar (#F7F8FA)
- Primary text #172B4D, secondary text #667085, border #E4E7EC
- Primary action #2457A7, Success #237A4B, Warning #A15C00, Critical #B42318
- Square corners or maximum 4px radius
- Zero gradients, zero glassmorphism, zero drop shadows
- No emojis as interface icons
- No raw icon ligature text
"""

from typing import Dict, List, Optional
import matplotlib.pyplot as plt
import streamlit as st

# ==============================================================================
# Design Tokens
# ==============================================================================
COLOR_PAGE_BG: str = "#FFFFFF"
COLOR_SIDEBAR_BG: str = "#F7F8FA"
COLOR_TEXT_PRIMARY: str = "#172B4D"
COLOR_TEXT_SECONDARY: str = "#667085"
COLOR_BORDER: str = "#E4E7EC"
COLOR_PRIMARY: str = "#2457A7"
COLOR_SUCCESS: str = "#237A4B"
COLOR_WARNING: str = "#A15C00"
COLOR_CRITICAL: str = "#B42318"
COLOR_ACTIVE_NAV: str = "#E8F1FC"
COLOR_HOVER_BG: str = "#F2F5F9"
COLOR_MUTED_SURFACE: str = "#F9FAFB"

BORDER_RADIUS: str = "3px"
FONT_FAMILY: str = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

# ==============================================================================
# Matplotlib Clinical Chart Configuration
# ==============================================================================
def apply_chart_theme() -> None:
    """Configure Matplotlib default styling for a clean, publication-grade appearance."""
    plt.rcParams.update({
        "figure.facecolor": COLOR_PAGE_BG,
        "figure.edgecolor": COLOR_PAGE_BG,
        "axes.facecolor": COLOR_PAGE_BG,
        "axes.edgecolor": COLOR_BORDER,
        "axes.linewidth": 1.0,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.labelcolor": COLOR_TEXT_PRIMARY,
        "axes.labelsize": 9.5,
        "axes.labelweight": "medium",
        "axes.titlesize": 11.5,
        "axes.titleweight": "semibold",
        "axes.titlecolor": COLOR_TEXT_PRIMARY,
        "axes.titlepad": 10,
        "grid.color": COLOR_BORDER,
        "grid.linestyle": "-",
        "grid.linewidth": 0.75,
        "grid.alpha": 0.85,
        "xtick.color": COLOR_TEXT_SECONDARY,
        "ytick.color": COLOR_TEXT_SECONDARY,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "font.family": "sans-serif",
        "font.sans-serif": ["Inter", "Roboto", "Segoe UI", "DejaVu Sans", "Arial", "sans-serif"],
        "text.color": COLOR_TEXT_PRIMARY,
        "legend.frameon": True,
        "legend.facecolor": COLOR_PAGE_BG,
        "legend.edgecolor": COLOR_BORDER,
        "legend.fontsize": 8.5,
        "legend.title_fontsize": 9.0,
        "legend.shadow": False,
        "legend.borderpad": 0.5,
        "legend.borderaxespad": 0.5,
        "figure.autolayout": False,
    })


# ==============================================================================
# CSS Injection
# ==============================================================================
CLINICAL_CSS: str = f"""
<style>
/* -------------------------------------------------------------------------- */
/* Global Reset & Typography */
/* -------------------------------------------------------------------------- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

html, body, p, div, span, h1, h2, h3, h4, h5, h6, input, select, button, label {{
    font-family: {FONT_FAMILY};
    color: {COLOR_TEXT_PRIMARY};
}}

/* Strictly ensure icon ligatures never render as visible text strings */
[data-testid="stIconMaterial"], .material-symbols-rounded, [class*="material-symbols"] {{
    font-family: 'Material Symbols Rounded' !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-size: 18px !important;
    line-height: 1 !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    display: inline-block !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-smoothing: antialiased !important;
}}

/* Force clean white background on main view */
.stApp {{
    background-color: {COLOR_PAGE_BG} !important;
}}

/* Top header / toolbar cleanup */
header[data-testid="stHeader"] {{
    background-color: {COLOR_PAGE_BG} !important;
    border-bottom: 1px solid {COLOR_BORDER} !important;
    box-shadow: none !important;
    height: 3rem !important;
}}

/* Hide raw text leak from collapse buttons */
header[data-testid="stHeader"] [data-testid="stSidebarCollapseButton"] {{
    color: {COLOR_TEXT_SECONDARY} !important;
}}

/* Main container layout padding */
.main .block-container {{
    padding-top: 1.5rem !important;
    padding-bottom: 2.5rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1440px !important;
}}

/* -------------------------------------------------------------------------- */
/* Sidebar Layout & Styling (220-240px enterprise standard) */
/* -------------------------------------------------------------------------- */
section[data-testid="stSidebar"] {{
    background-color: {COLOR_SIDEBAR_BG} !important;
    border-right: 1px solid {COLOR_BORDER} !important;
    box-shadow: none !important;
    width: 235px !important;
    min-width: 235px !important;
}}

section[data-testid="stSidebar"] .block-container {{
    padding-top: 1.25rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}}

/* Sidebar navigation links */
[data-testid="stSidebarNav"] {{
    padding-top: 0.25rem !important;
    border-bottom: 1px solid {COLOR_BORDER} !important;
    padding-bottom: 0.75rem !important;
    margin-bottom: 0.75rem !important;
}}

[data-testid="stSidebarNav"] ul {{
    gap: 3px !important;
}}

[data-testid="stSidebarNav"] a {{
    border-radius: {BORDER_RADIUS} !important;
    padding: 6px 10px !important;
    color: {COLOR_TEXT_PRIMARY} !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    text-decoration: none !important;
    transition: none !important;
    border: 1px solid transparent !important;
}}

[data-testid="stSidebarNav"] a:hover {{
    background-color: {COLOR_HOVER_BG} !important;
    color: {COLOR_PRIMARY} !important;
}}

[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background-color: {COLOR_ACTIVE_NAV} !important;
    color: {COLOR_PRIMARY} !important;
    font-weight: 600 !important;
    border: 1px solid #C8DCF8 !important;
}}

/* Ensure the entry point 'app' link is cleanly presented as 'Overview' */
[data-testid="stSidebarNav"] li:first-child a span {{
    font-size: 0 !important;
    line-height: 0 !important;
}}
[data-testid="stSidebarNav"] li:first-child a span::after {{
    content: "Overview" !important;
    font-size: 13px !important;
    line-height: 1.4 !important;
    display: inline-block !important;
}}

/* -------------------------------------------------------------------------- */
/* Strict Visual Restriction Overrides: No Gradients, Blur, Shadows */
/* -------------------------------------------------------------------------- */
* {{
    box-shadow: none !important;
    text-shadow: none !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
}}

/* Buttons */
.stButton > button, button[kind="primary"], button[kind="secondary"] {{
    border-radius: {BORDER_RADIUS} !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 6px 14px !important;
    min-height: 34px !important;
    border: 1px solid {COLOR_PRIMARY} !important;
    background-color: {COLOR_PRIMARY} !important;
    color: #FFFFFF !important;
    box-shadow: none !important;
    transition: none !important;
}}

.stButton > button:hover {{
    background-color: #1B4588 !important;
    border-color: #1B4588 !important;
    color: #FFFFFF !important;
}}

/* Download Button (Secondary / Export style) */
.stDownloadButton > button {{
    border-radius: {BORDER_RADIUS} !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 6px 14px !important;
    min-height: 34px !important;
    border: 1px solid {COLOR_BORDER} !important;
    background-color: #FFFFFF !important;
    color: {COLOR_TEXT_PRIMARY} !important;
    box-shadow: none !important;
}}

.stDownloadButton > button:hover {{
    background-color: {COLOR_HOVER_BG} !important;
    border-color: #D0D5DD !important;
    color: {COLOR_PRIMARY} !important;
}}

/* Inputs, Selects, Number inputs */
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stNumberInput > div > div > input,
.stDateInput > div > div > input {{
    border-radius: {BORDER_RADIUS} !important;
    border: 1px solid {COLOR_BORDER} !important;
    font-size: 13px !important;
    color: {COLOR_TEXT_PRIMARY} !important;
    background-color: #FFFFFF !important;
    box-shadow: none !important;
    padding: 5px 10px !important;
}}

.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stDateInput > div > div > input:focus {{
    border-color: {COLOR_PRIMARY} !important;
    outline: none !important;
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
    border-bottom: 1px solid {COLOR_BORDER} !important;
    gap: 4px !important;
    background-color: transparent !important;
}}

.stTabs [data-baseweb="tab"] {{
    border-radius: 0px !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    padding: 8px 16px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: {COLOR_TEXT_SECONDARY} !important;
    background-color: transparent !important;
}}

.stTabs [data-baseweb="tab"]:hover {{
    color: {COLOR_PRIMARY} !important;
}}

.stTabs [aria-selected="true"] {{
    border-bottom: 2px solid {COLOR_PRIMARY} !important;
    color: {COLOR_PRIMARY} !important;
    font-weight: 600 !important;
    background-color: transparent !important;
}}

/* DataFrames & Tables */
[data-testid="stDataFrame"] {{
    border: 1px solid {COLOR_BORDER} !important;
    border-radius: {BORDER_RADIUS} !important;
    background-color: #FFFFFF !important;
}}

/* Native Metrics Override */
[data-testid="stMetric"] {{
    background-color: #FFFFFF !important;
    border: 1px solid {COLOR_BORDER} !important;
    border-radius: {BORDER_RADIUS} !important;
    padding: 10px 14px !important;
    box-shadow: none !important;
}}

[data-testid="stMetricLabel"] {{
    font-size: 12px !important;
    font-weight: 500 !important;
    color: {COLOR_TEXT_SECONDARY} !important;
    margin-bottom: 2px !important;
    text-transform: none !important;
}}

[data-testid="stMetricValue"] {{
    font-size: 24px !important;
    font-weight: 600 !important;
    color: {COLOR_TEXT_PRIMARY} !important;
}}

[data-testid="stMetricDelta"] {{
    font-size: 12px !important;
    font-weight: 500 !important;
}}

/* Horizontal Dividers */
hr {{
    margin: 1.25rem 0 !important;
    border: none !important;
    border-top: 1px solid {COLOR_BORDER} !important;
}}

/* Radio and Checkboxes */
.stRadio > div {{
    gap: 8px !important;
}}

/* Alert callout containers (info, success, warning, error) */
.stAlert {{
    border-radius: {BORDER_RADIUS} !important;
    border-width: 1px !important;
    border-style: solid !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
    box-shadow: none !important;
}}

div[data-baseweb="notification"] {{
    border-radius: {BORDER_RADIUS} !important;
    box-shadow: none !important;
}}

/* -------------------------------------------------------------------------- */
/* Custom Clinical UI Components */
/* -------------------------------------------------------------------------- */
.pt-shell-header {{
    padding-bottom: 12px;
    margin-bottom: 16px;
    border-bottom: 1px solid {COLOR_BORDER};
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
}}

.pt-title {{
    font-size: 26px;
    font-weight: 600;
    color: {COLOR_TEXT_PRIMARY};
    margin: 0;
    line-height: 1.2;
    letter-spacing: -0.3px;
}}

.pt-subtitle {{
    font-size: 13px;
    color: {COLOR_TEXT_SECONDARY};
    margin-top: 4px;
    margin-bottom: 0;
}}

.pt-section-title {{
    font-size: 16px;
    font-weight: 600;
    color: {COLOR_TEXT_PRIMARY};
    margin-top: 18px;
    margin-bottom: 8px;
}}

.pt-badge {{
    display: inline-flex;
    align-items: center;
    padding: 2px 7px;
    font-size: 11px;
    font-weight: 500;
    border-radius: 2px;
}}

.pt-badge-neutral {{
    background-color: #F7F8FA;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
}}

.pt-badge-success {{
    background-color: #F2F9F5;
    color: {COLOR_SUCCESS};
    border: 1px solid #BCE3CE;
}}

.pt-badge-warning {{
    background-color: #FFF9F0;
    color: {COLOR_WARNING};
    border: 1px solid #F5D5A5;
}}

.pt-badge-critical {{
    background-color: #FDF3F2;
    color: {COLOR_CRITICAL};
    border: 1px solid #F8C3BF;
}}

.pt-badge-primary {{
    background-color: #F0F5FC;
    color: {COLOR_PRIMARY};
    border: 1px solid #C8DCF8;
}}

.pt-kpi-card {{
    background: #FFFFFF;
    border: 1px solid {COLOR_BORDER};
    border-radius: {BORDER_RADIUS};
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 92px;
}}

.pt-kpi-card-fin {{
    background: #FFFFFF;
    border: 1px solid {COLOR_BORDER};
    border-radius: {BORDER_RADIUS};
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 76px;
}}

.pt-kpi-label {{
    font-size: 12px;
    font-weight: 500;
    color: {COLOR_TEXT_SECONDARY};
    margin-bottom: 2px;
}}

.pt-kpi-val {{
    font-size: 25px;
    font-weight: 600;
    color: {COLOR_TEXT_PRIMARY};
    line-height: 1.15;
    margin-bottom: 3px;
}}

.pt-kpi-val-fin {{
    font-size: 20px;
    font-weight: 600;
    color: {COLOR_TEXT_PRIMARY};
    line-height: 1.15;
    margin-bottom: 2px;
}}

.pt-kpi-subtext {{
    font-size: 12px;
    color: {COLOR_TEXT_SECONDARY};
    font-weight: 400;
}}

.pt-kpi-subtext-success {{
    color: {COLOR_SUCCESS};
    font-weight: 500;
}}

.pt-kpi-subtext-warning {{
    color: {COLOR_WARNING};
    font-weight: 500;
}}

.pt-kpi-subtext-critical {{
    color: {COLOR_CRITICAL};
    font-weight: 500;
}}

.pt-sidebar-brand {{
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 2px 0 10px 0;
    border-bottom: 1px solid {COLOR_BORDER};
    margin-bottom: 10px;
}}

.pt-sidebar-brand-title {{
    font-size: 15px;
    font-weight: 600;
    color: {COLOR_TEXT_PRIMARY};
    letter-spacing: 0.2px;
    line-height: 1.1;
}}

.pt-sidebar-brand-sub {{
    font-size: 11px;
    color: {COLOR_TEXT_SECONDARY};
    margin-top: 2px;
}}

.pt-table-header {{
    font-size: 14px;
    font-weight: 600;
    color: {COLOR_TEXT_PRIMARY};
    margin-bottom: 6px;
}}

.pt-meta-box {{
    background: #FFFFFF;
    border: 1px solid {COLOR_BORDER};
    border-radius: {BORDER_RADIUS};
    padding: 6px 12px;
    font-size: 12px;
    color: {COLOR_TEXT_SECONDARY};
    display: inline-flex;
    align-items: center;
}}
</style>
"""

def inject_clinical_styles() -> None:
    """Inject the unified clinical CSS stylesheet and initialize chart theme."""
    st.markdown(CLINICAL_CSS, unsafe_allow_html=True)
    apply_chart_theme()


# ==============================================================================
# Reusable UI Layout Components
# ==============================================================================
def render_sidebar_brand(reference_date: Optional[str] = None) -> None:
    """Render consistent medical brand identity in the left sidebar without emojis."""
    icon_svg = (
        f'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
        f'stroke="{COLOR_PRIMARY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/>'
        f'<path d="m8.5 8.5 7 7"/>'
        f'</svg>'
    )
    brand_html = f"""
    <div class="pt-sidebar-brand">
        <div style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border: 1px solid {COLOR_BORDER}; background: #FFFFFF; border-radius: 3px;">
            {icon_svg}
        </div>
        <div>
            <div class="pt-sidebar-brand-title">PharmaTrack</div>
            <div class="pt-sidebar-brand-sub">Pharmacy Operations</div>
        </div>
    </div>
    """
    st.sidebar.markdown(brand_html, unsafe_allow_html=True)


def render_page_header(
    title: str,
    subtitle: str,
    right_label: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Render a structured clinical page header with strict hierarchy and no emojis."""
    right_html = f'<div class="pt-meta-box">{right_label}</div>' if right_label else ""
    header_html = f"""
    <div class="pt-shell-header">
        <div>
            <h1 class="pt-title">{title}</h1>
            <p class="pt-subtitle">{subtitle}</p>
        </div>
        <div>
            {right_html}
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


def render_kpi_card(
    label: str,
    value: str,
    subtext: str = "",
    status: str = "normal",
    is_financial: bool = False,
) -> str:
    """Return HTML markup for a restrained, 1px bordered clinical KPI card."""
    card_class = "pt-kpi-card-fin" if is_financial else "pt-kpi-card"
    val_class = "pt-kpi-val-fin" if is_financial else "pt-kpi-val"

    sub_class = "pt-kpi-subtext"
    if status == "success":
        sub_class += " pt-kpi-subtext-success"
    elif status == "warning":
        sub_class += " pt-kpi-subtext-warning"
    elif status == "critical" or status == "error":
        sub_class += " pt-kpi-subtext-critical"

    card_html = f"""
    <div class="{card_class}">
        <div class="pt-kpi-label">{label}</div>
        <div class="{val_class}">{value}</div>
        <div class="{sub_class}">{subtext}</div>
    </div>
    """
    return card_html


def render_kpi_grid(cards: List[Dict[str, str]], is_financial: bool = False) -> None:
    """Render a horizontal grid of clinical KPI cards using Streamlit columns."""
    if not cards:
        return
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        with col:
            html = render_kpi_card(
                label=card.get("label", ""),
                value=card.get("value", ""),
                subtext=card.get("subtext", ""),
                status=card.get("status", "normal"),
                is_financial=is_financial,
            )
            st.markdown(html, unsafe_allow_html=True)


def render_status_badge(text: str, status_type: str = "neutral") -> str:
    """Return inline HTML for a rectangular clinical status badge."""
    css_class = f"pt-badge pt-badge-{status_type}"
    return f'<span class="{css_class}">{text}</span>'
