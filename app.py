"""
Crypto & Equity Signals Dashboard
Run with: streamlit run app.py
"""

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
import html
from table_pick import clicked_pick
import io
import json
import re
import threading
import time
import traceback
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots
from streamlit.errors import StreamlitInvalidLayoutContextError
from supabase import create_client

# A pop-out tab shows one part of the dashboard on its own: ?view=social
_POPOUT_SECTION_IDS = (
    "quick_snapshot",
    "crypto_scores",
    "equity_scores",
    "interactive_chart",
    "score_breakdown",
    "market_mood",
    "market_mood_crypto",
    "market_mood_stock",
    "max_pain",
    "leverage",
    "market_sentiment_panel",
    "signal_matrix",
)
_POPOUT_VIEWS = ("social",) + _POPOUT_SECTION_IDS
_POPOUT_VIEW = str(st.query_params.get("view") or "")
if _POPOUT_VIEW not in _POPOUT_VIEWS:
    _POPOUT_VIEW = ""
_POPOUT_MARK = "popout-tab"

_RUN_STARTED = time.perf_counter()

st.set_page_config(
    page_title=(
        "angstrom signals - " + _POPOUT_VIEW.replace("_", " ")
        if _POPOUT_VIEW else "angstrom signals"
    ),
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


if _POPOUT_VIEW:
    st.markdown(
        "<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl'],"
        "[data-testid='stHeader'],[data-testid='stToolbar'],.st-key-page_header,"
        ".st-key-sec_help_guides,[class*='st-key-hide_'],.angstrom-sidebar-tab,#social-stream-root .edge"
        "{display:none !important;}"
        # Trim the room around a lone section: less padding, and no gaps between the hidden helpers.
        "[data-testid='stMainBlockContainer'],.stMainBlockContainer"
        "{padding-top:0.75rem !important;padding-bottom:0.75rem !important;}"
        "[data-testid='stMainBlockContainer'] > [data-testid='stVerticalBlock'],"
        ".stMainBlockContainer > [data-testid='stVerticalBlock']{gap:0 !important;}"
        "[data-testid='stMain'] footer,[data-testid='stBottom']{display:none !important;}"
        # Hidden sections and helper pieces leave empty slots. Take the slots out as well,
        # and close the gaps only in the blocks that hold the section itself.
        "div:has(> [class*='st-key-hide_']:only-child){display:none !important;}"
        "[data-testid='stElementContainer']:has(> .stBidiComponent[style*='display: none']){display:none !important;}"
        "[data-testid='stElementContainer']:has(> [data-testid='stHtml'] > div:only-child:empty){display:none !important;}"
        "[data-testid='stVerticalBlock']:has([class*='st-key-pop_']){gap:0 !important;}</style>",
        unsafe_allow_html=True,
    )


def _active_theme() -> str:
    """The theme this browser is using. Light when Streamlit has not reported one yet."""
    try:
        kind = st.context.theme.type
    except Exception:
        kind = None
    return kind if kind in ("light", "dark") else "light"


def _paint_chart(fig) -> None:
    """Chart paper follows the same surface as the cards. Dark mode is grey, not black."""
    dark = _active_theme() == "dark"
    paper = "#262730" if dark else "#ffffff"
    ink = "#e5e7eb" if dark else "#374151"
    grid = "#3f4654" if dark else "#e5e7eb"
    fig.update_layout(paper_bgcolor=paper, plot_bgcolor=paper, font=dict(color=ink))
    fig.update_xaxes(gridcolor=grid, zerolinecolor=grid, tickfont=dict(color=ink), title_font=dict(color=ink))
    fig.update_yaxes(gridcolor=grid, zerolinecolor=grid, tickfont=dict(color=ink), title_font=dict(color=ink))


def _brand_mark(width: int, *, align: str = "center") -> str:
    """Both logos, with the current theme shown first. The page swaps them when the theme changes."""
    folder = Path(__file__).resolve().parent / "assets"
    light = folder / "logo-light.png"
    dark = folder / "logo-dark.png"
    if not light.is_file() or not dark.is_file():
        return ""

    def source(path: Path) -> str:
        return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")

    mode = _active_theme()
    light_hidden = " aria-hidden='true'" if mode == "dark" else ""
    dark_hidden = " aria-hidden='true'" if mode != "dark" else ""
    margin = "0" if align == "left" else "0.15rem 0 0.35rem"
    return (
        "<style>.brand-mark img{display:none}.brand-mark.is-light .logo-light,"
        ".brand-mark.is-dark .logo-dark{display:inline}</style>"
        f"<div class='brand-mark is-{mode}' style='text-align:{align};margin:{margin};line-height:0;'>"
        f"<img class='logo-light' src='{source(light)}' alt='Angstrom Signals'{light_hidden} "
        f"width='{width}' style='width:{width}px;max-width:100%;height:auto;'>"
        f"<img class='logo-dark' src='{source(dark)}' alt=''{dark_hidden} "
        f"width='{width}' style='width:{width}px;max-width:100%;height:auto;'>"
        "</div>"
    )


_BRAND_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const chosen = data || {};
  const paintColour = (name, value) => {
    if (typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value)) {
      document.documentElement.style.setProperty(name, value);
    }
  };
  paintColour("--ang-page-day", chosen.pageDay);
  paintColour("--ang-page-night", chosen.pageNight);
  paintColour("--ang-heading-day", chosen.headingDay);
  paintColour("--ang-heading-night", chosen.headingNight);
  paintColour("--ang-section-day", chosen.sectionDay);
  paintColour("--ang-section-night", chosen.sectionNight);
  paintColour("--ang-hover-day", chosen.hoverDay);
  paintColour("--ang-hover-night", chosen.hoverNight);
  paintColour("--ang-side-day", chosen.sidebarDay);
  paintColour("--ang-side-night", chosen.sidebarNight);
  paintColour("--ang-social-day", chosen.socialDay);
  paintColour("--ang-social-night", chosen.socialNight);
  paintColour("--ang-border-day", chosen.borderDay);
  paintColour("--ang-border-night", chosen.borderNight);
  let style = document.getElementById("angstrom-brand-style");
  if (style && style.dataset.layout !== "ruled") {
    style.remove();
    style = null;
  }
  if (!style) {
    style = document.createElement("style");
    style.id = "angstrom-brand-style";
    style.dataset.layout = "ruled";
    style.textContent = [
      "html{--ang-surface:#ffffff;--ang-border:var(--ang-border-day,#e5e7eb);--ang-text:#111827;--ang-muted:#6b7280;--ang-soft:#374151;--ang-track:#e5e7eb;--ang-line:var(--ang-border);--ang-select:#e5e7eb;--ang-select-text:#111827;--ang-page:var(--ang-page-day,#d6e8f8);--ang-heading:var(--ang-heading-day,#ffffff);--ang-section:var(--ang-section-day,#ffffff);--ang-hover:var(--ang-hover-day,#f3f4f6);--ang-side:var(--ang-side-day,#ffffff);--ang-social:var(--ang-social-day,#ffffff);}",
      "html.angstrom-night{--ang-surface:#262730;--ang-border:var(--ang-border-night,#000000);--ang-text:#f3f4f6;--ang-muted:#9ca3af;--ang-soft:#d1d5db;--ang-track:#3f4654;--ang-line:var(--ang-border);--ang-select:#3a4050;--ang-select-text:#f9fafb;--ang-page:var(--ang-page-night,#0e1117);--ang-heading:var(--ang-heading-night,#262730);--ang-section:var(--ang-section-night,#262730);--ang-hover:var(--ang-hover-night,#31333f);--ang-side:var(--ang-side-night,#16181f);--ang-social:var(--ang-social-night,#1c1f27);}",
      ".ang-card{background:var(--ang-surface);color:var(--ang-text);border:1px solid var(--ang-border);border-radius:10px;padding:12px 16px;}",
      ".ang-kicker{font-size:.8rem;color:var(--ang-muted);margin-bottom:4px;}",
      ".ang-copy{color:var(--ang-text);font-size:.95rem;line-height:1.4;}",
      ".ang-title{color:var(--ang-text);font-weight:600;}",
      ".ang-track{flex:1;background:var(--ang-track);border-radius:6px;height:14px;overflow:hidden;}",
      ".ang-table{width:100%;border-collapse:collapse;font-size:.95rem;color:var(--ang-text);}",
      ".ang-table thead tr{border-bottom:2px solid var(--ang-border);}",
      ".ang-table tbody tr{border-bottom:1px solid var(--ang-line);}",
      ".ang-table tr.ang-row-on{background:var(--ang-select);color:var(--ang-select-text);}",
      "[data-testid='stAppViewContainer'],[data-testid='stHeader'],[data-testid='stBottom']{background:var(--ang-page) !important;}",
      "html:not(.angstrom-night) [data-testid='stSidebar']{background:var(--ang-side) !important;border-right:1px solid var(--ang-border);}",
      "html:not(.angstrom-night) [data-testid='stMain'] [data-testid='stVerticalBlockBorderWrapper']{background:#ffffff !important;border-color:var(--ang-border) !important;}",
      "[data-testid='stForm']{background:transparent !important;border-color:transparent !important;}",
      "[data-testid='stExpander'] details{background:var(--ang-section) !important;border-color:var(--ang-border) !important;}",
      "[data-testid='stExpander'] details > summary{background:var(--ang-heading) !important;}",
      "[data-testid='stExpander'] details > summary:has(.ang-header-score){display:flex !important;align-items:center;}",
      ".ang-header-score{margin-left:auto;margin-right:0.55rem;flex:none;display:inline-block;min-width:52px;text-align:center;border-radius:4px;padding:2px 8px;font-weight:600;line-height:1;}",
      "[data-testid='stExpander'] details > summary:hover,[data-testid='stExpander'] details > summary:focus-visible,[data-testid='stExpander'] details > summary:active{background:var(--ang-hover) !important;}",
      "html.angstrom-night [data-testid='stSidebar']{background:var(--ang-side) !important;border-right:1px solid var(--ang-border);}",
      "html.angstrom-night [data-testid='stMain'] [data-testid='stVerticalBlockBorderWrapper'],html.angstrom-night [data-testid='stMetric']{background:var(--ang-surface) !important;border-color:var(--ang-border) !important;}",
      "html.angstrom-night [data-baseweb='input'],html.angstrom-night [data-baseweb='textarea'],html.angstrom-night [data-baseweb='select'] > div,html.angstrom-night [data-testid='stFileUploaderDropzone']{background-color:#31333f !important;border-color:var(--ang-border) !important;color:var(--ang-text) !important;}",
      "html.angstrom-night [data-baseweb='input'] input,html.angstrom-night [data-baseweb='textarea'] textarea{background:transparent !important;color:var(--ang-text) !important;-webkit-text-fill-color:var(--ang-text);}",
      "html.angstrom-night [data-testid='stBaseButton-secondary']{background:#31333f !important;border-color:#4b5563 !important;color:var(--ang-text) !important;}",
      "html.angstrom-night [data-testid='stBaseButton-secondary']:hover{border-color:#e5e7eb !important;color:#ffffff !important;}",
      "button.angstrom-jump{display:flex;align-items:center;gap:0.75rem;width:100%;box-sizing:border-box;min-height:3.25rem;height:auto;padding:0.55rem 0.85rem;border-radius:0.5rem;border:1px solid rgba(49,51,63,0.2);background:#ffffff;color:#31333f;font:inherit;line-height:1.35;text-align:left;cursor:pointer;white-space:normal;}",
      "button.angstrom-jump .angstrom-jump-icon{flex:none;font-size:2.25rem;line-height:1;}",
      "button.angstrom-jump .angstrom-jump-text{flex:1;min-width:0;text-align:left;}",
      "button.angstrom-jump:hover{border-color:#ff4b4b;color:#ff4b4b;}",
      "html.angstrom-night button.angstrom-jump{background:#31333f;border-color:#4b5563;color:var(--ang-text);}",
      "html.angstrom-night button.angstrom-jump:hover{border-color:#e5e7eb;color:#ffffff;}",
      "html.angstrom-night [data-baseweb='popover'] > div,html.angstrom-night [data-baseweb='menu'],html.angstrom-night [data-testid='stDialog'] [role='dialog']{background:#262730 !important;color:var(--ang-text) !important;}",
      "html.angstrom-night [data-testid='stCode'],html.angstrom-night pre{background:#262730 !important;color:var(--ang-text);border:1px solid var(--ang-border);border-radius:8px;}",
      ".brand-mark img{display:none;}",
      ".brand-mark.is-light .logo-light,.brand-mark.is-dark .logo-dark{display:inline;}",
      ".sentiment-card{background:var(--ang-surface);color:var(--ang-text);border:1px solid var(--ang-border);border-radius:10px;padding:14px 16px;}",
      ".sentiment-kicker{font-size:.8rem;color:var(--ang-muted);margin-bottom:4px;}",
      ".sentiment-score{display:inline-flex;align-items:center;gap:6px;padding:2px 8px;border-radius:4px;font-weight:600;}",
      ".sentiment-coverage{margin-top:8px;font-weight:600;}",
      ".sentiment-body{margin-top:8px;color:var(--ang-text);}",
      ".sentiment-side{margin-top:12px;}",
      ".sentiment-side .sentiment-body{margin-top:4px;}",
      ".sentiment-side-label{font-size:.75rem;font-weight:700;}",
      ".sentiment-drivers{margin:10px 0 0;padding-left:1.15rem;}",
      ".sentiment-drivers li{margin:4px 0;color:var(--ang-soft);}",
      ".headline-group{margin:14px 0 0;font-weight:700;font-size:.95rem;color:var(--ang-text);}",
      "[class*='st-key-article_box_']{background:var(--ang-surface) !important;border:1px solid var(--ang-border) !important;border-radius:10px !important;}",
      "[class*='st-key-article_box_mood_'][class*='_readings']{margin-top:1rem !important;}",
      ".article-sheet > .headline-group:first-child,.article-sheet > div:first-child{margin-top:0 !important;}",
      ".headline-aside{margin:4px 0 8px;font-size:.8rem;color:var(--ang-muted);line-height:1.35;}",
      "html.angstrom-night [class*='_take_box']{background:var(--ang-surface) !important;border-color:var(--ang-border) !important;}",
      ".headline-head,.headline-row{display:flex;gap:16px;}",
      ".headline-head{align-items:center;padding:4px 0 8px;font-size:.8rem;font-weight:600;color:var(--ang-muted);}",
      ".headline-row{align-items:flex-start;padding:8px 0;border-top:1px solid var(--ang-line);}",
      ".headline-title{flex:1.1;min-width:0;}",
      ".headline-date{width:112px;flex:none;white-space:nowrap;color:var(--ang-soft);}",
      ".headline-note{flex:1.3;min-width:0;color:var(--ang-soft);font-size:.9rem;line-height:1.35;}",
      ".headline-score{width:76px;flex:none;text-align:right;}",
      ".headline-ai .headline-score{width:6.25rem;white-space:nowrap;}",
      ".headline-empty{color:#6b7280;}",
      ".headline-title a:link{color:#15803d;}",
      ".headline-title a:visited{color:#6d28d9;}",
      ".headline-title a:hover{color:#166534;}",
      "html.angstrom-night .headline-date,html.angstrom-night .headline-note{color:var(--ang-soft) !important;}",
      "html.angstrom-night .headline-title a:link{color:#5ce488 !important;}",
      "html.angstrom-night .headline-title a:visited{color:#d8b4fe !important;}",
      "html.angstrom-night .headline-title a:hover{color:#bbf7d0 !important;}",
      "html.angstrom-night .headline-source,html.angstrom-night .headline-empty{color:#d1d5db;}"
    ].join("");
    document.head.appendChild(style);
  }
  let sideStyle = document.getElementById("angstrom-sidebar-tab-style");
  if (sideStyle && sideStyle.dataset.layout !== "match") {
    sideStyle.remove();
    sideStyle = null;
  }
  if (!sideStyle) {
    sideStyle = document.createElement("style");
    sideStyle.id = "angstrom-sidebar-tab-style";
    sideStyle.dataset.layout = "match";
    sideStyle.textContent = [
      ".angstrom-sidebar-tab{position:fixed;top:4.75rem;left:0;z-index:10000001;display:flex;align-items:center;justify-content:center;width:2rem;height:2rem;padding:0;border:1px solid rgba(49,51,63,.2);border-left:0;border-radius:0 .5rem .5rem 0;background:#fff;color:#808495;cursor:pointer;box-shadow:1px 1px 4px rgba(0,0,0,.08);transition:background .15s ease,color .15s ease;}",
      ".angstrom-sidebar-tab:hover{background:#f0f2f6;color:#ff4b4b;}",
      ".angstrom-sidebar-tab.is-closed svg{transform:scaleX(-1);}",
      "html.angstrom-night .angstrom-sidebar-tab{background:#262730;color:#c5c8d0;border-color:#4b5563;}",
      "html.angstrom-night .angstrom-sidebar-tab:hover{background:#31333f;color:#ff4b4b;}",
      "[data-testid='stSidebarCollapseButton'],[data-testid='stExpandSidebarButton']{visibility:hidden !important;pointer-events:none !important;position:absolute !important;width:0 !important;min-width:0 !important;height:0 !important;margin:0 !important;overflow:hidden !important;}",
      "@media print{.angstrom-sidebar-tab{display:none !important;}}"
    ].join("");
    document.head.appendChild(sideStyle);
  }
  const singleMark = "url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27%3E%3Crect x=%272.4%27 y=%272.4%27 width=%2719.2%27 height=%2719.2%27 fill=%27none%27 stroke=%27black%27 stroke-width=%272%27/%3E%3C/svg%3E')";
  const wideMark = "url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27%3E%3Crect x=%272.4%27 y=%272.4%27 width=%2719.2%27 height=%2719.2%27 fill=%27none%27 stroke=%27black%27 stroke-width=%272%27/%3E%3Cpath d=%27M2.4 9.1H21.6M12 9.1V21.6%27 fill=%27none%27 stroke=%27black%27 stroke-width=%272%27/%3E%3C/svg%3E')";
  const openMark = "url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27%3E%3Cpath d=%27M12 5.83 15.17 9l1.41-1.41L12 3 7.41 7.59 8.83 9 12 5.83zm0 12.34L8.83 15l-1.41 1.41L12 21l4.59-4.59L15.17 15 12 18.17z%27/%3E%3C/svg%3E')";
  const closeMark = "url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27%3E%3Cpath d=%27M7.41 18.59 8.83 20 12 16.83 15.17 20l1.41-1.41L12 15 7.41 18.59zm9.18-13.18L15.17 4 12 7.17 8.83 4 7.41 5.41 12 10l4.59-4.59z%27/%3E%3C/svg%3E')";
  let layoutStyle = document.getElementById("angstrom-layout-controls");
  const layoutCss = [
      "[class*='st-key-layout_single'],[class*='st-key-layout_wide'],[class*='st-key-open_all_sections'],[class*='st-key-collapse_all_sections']{width:fit-content !important;max-width:max-content !important;flex:0 0 auto !important;}",
      ".st-key-layout_single button,.st-key-layout_wide button,.st-key-open_all_sections button,.st-key-collapse_all_sections button{position:relative;width:2.05rem !important;height:2.05rem !important;min-height:2.05rem !important;padding:0 !important;border-radius:.4rem !important;display:inline-flex !important;align-items:center;justify-content:center;font-size:0 !important;line-height:0 !important;color:#111827 !important;background:#fff !important;border:1px solid rgba(49,51,63,.28) !important;box-shadow:none !important;}",
      ".st-key-layout_single button > *,.st-key-layout_wide button > *,.st-key-open_all_sections button > *,.st-key-collapse_all_sections button > *{position:absolute !important;width:1px !important;height:1px !important;overflow:hidden !important;clip:rect(0,0,0,0) !important;}",
      ".st-key-layout_single button::before,.st-key-layout_wide button::before,.st-key-open_all_sections button::before,.st-key-collapse_all_sections button::before{content:'';position:absolute;left:50%;top:50%;width:15px;height:15px;transform:translate(-50%,-50%);background:currentColor;-webkit-mask:var(--mark) center / contain no-repeat;mask:var(--mark) center / contain no-repeat;}",
      ".st-key-layout_single button{--mark:" + singleMark + ";}",
      ".st-key-layout_wide button{--mark:" + wideMark + ";}",
      ".st-key-layout_single button:hover,.st-key-layout_wide button:hover,.st-key-open_all_sections button:hover,.st-key-collapse_all_sections button:hover{border-color:#111827 !important;}",
      ".st-key-layout_single button[data-testid='stBaseButton-primary'],.st-key-layout_wide button[data-testid='stBaseButton-primary']{background:#111827 !important;color:#fff !important;border-color:#111827 !important;}",
      "html.angstrom-night .st-key-layout_single button,html.angstrom-night .st-key-layout_wide button,html.angstrom-night .st-key-open_all_sections button,html.angstrom-night .st-key-collapse_all_sections button{background:#262730 !important;color:#fafafa !important;border-color:#4b5563 !important;}",
      "html.angstrom-night .st-key-layout_single button:hover,html.angstrom-night .st-key-layout_wide button:hover,html.angstrom-night .st-key-open_all_sections button:hover,html.angstrom-night .st-key-collapse_all_sections button:hover{border-color:#e5e7eb !important;}",
      "html.angstrom-night .st-key-layout_single button[data-testid='stBaseButton-primary'],html.angstrom-night .st-key-layout_wide button[data-testid='stBaseButton-primary']{background:#f3f4f6 !important;color:#111827 !important;border-color:#f3f4f6 !important;}",
      ".st-key-open_all_sections button{--mark:" + openMark + ";}",
      ".st-key-collapse_all_sections button{--mark:" + closeMark + ";}",
      "[data-testid='stElementContainer']:not(:has([data-testid='stElementContainer'])):is(:has(#interactive-chart),:has(#market-mood-crypto),:has(#market-mood-stock),:has(#market-sentiment),:has(#score-breakdown)),[class*='st-key-scroll_to_chart'],[class*='st-key-wide_column_split']{position:absolute !important;width:0 !important;height:0 !important;min-height:0 !important;margin:0 !important;padding:0 !important;overflow:visible !important;}",
      "[class*='st-key-favourite_watch'],[class*='st-key-alert_asset_pick'],[class*='st-key-section_toggle_watch'],[class*='st-key-colour_copy'],[data-testid='stLayoutWrapper']:has(> [data-testid='stVerticalBlock'] > [class*='st-key-favourite_watch']),[data-testid='stLayoutWrapper']:has(> [data-testid='stVerticalBlock'] > [class*='st-key-section_toggle_watch']),[data-testid='stLayoutWrapper']:has(> [data-testid='stVerticalBlock'] > [class*='st-key-colour_copy']){position:absolute !important;width:0 !important;height:0 !important;min-height:0 !important;margin:0 !important;padding:0 !important;overflow:hidden !important;border:0 !important;}",
      "[class*='st-key-colour_'].ang-colour-drop{outline:2px solid #2563eb;outline-offset:2px;border-radius:8px;}",
      "[class*='st-key-colour_'] button[draggable='true']{cursor:grab;}",
      "#angstrom-wide-split{position:absolute;z-index:30;width:12px;margin-left:-6px;top:0;cursor:col-resize;touch-action:none;}",
      "#angstrom-wide-split .grip{position:absolute;top:50%;left:4px;width:4px;height:48px;margin-top:-24px;border-radius:999px;background:#9ca3af;}",
      "#angstrom-wide-split:hover .grip,#angstrom-wide-split.is-dragging .grip{background:#111827;}",
      "html.angstrom-night #angstrom-wide-split .grip{background:#6b7280;}",
      "html.angstrom-night #angstrom-wide-split:hover .grip,html.angstrom-night #angstrom-wide-split.is-dragging .grip{background:#e5e7eb;}",
      "#interactive-chart,#market-mood-crypto,#market-mood-stock,#market-sentiment,#score-breakdown{height:0;margin:0;padding:0;scroll-margin-top:4.5rem;}",
      ".st-key-admin_feedback_table,.st-key-admin_reports_table,.st-key-admin_blacklist_table,.st-key-admin_beta_table{max-height:32rem !important;overflow:auto !important;border:1px solid var(--ang-border);}",
      ".st-key-admin_feedback_table [data-testid='stHorizontalBlock'],.st-key-admin_reports_table [data-testid='stHorizontalBlock'],.st-key-admin_blacklist_table [data-testid='stHorizontalBlock'],.st-key-admin_beta_table [data-testid='stHorizontalBlock']{border-bottom:1px solid var(--ang-border);}",
      ".st-key-admin_feedback_table [data-testid='stVerticalBlock'],.st-key-admin_reports_table [data-testid='stVerticalBlock'],.st-key-admin_blacklist_table [data-testid='stVerticalBlock'],.st-key-admin_beta_table [data-testid='stVerticalBlock']{gap:0 !important;}",
      ".st-key-admin_feedback_table [data-testid='stHorizontalBlock'],.st-key-admin_reports_table [data-testid='stHorizontalBlock'],.st-key-admin_blacklist_table [data-testid='stHorizontalBlock'],.st-key-admin_beta_table [data-testid='stHorizontalBlock'],.st-key-admin_feedback_table [data-testid='stElementContainer'],.st-key-admin_reports_table [data-testid='stElementContainer'],.st-key-admin_blacklist_table [data-testid='stElementContainer'],.st-key-admin_beta_table [data-testid='stElementContainer'],.st-key-admin_feedback_table [data-testid='stMarkdown'],.st-key-admin_reports_table [data-testid='stMarkdown'],.st-key-admin_blacklist_table [data-testid='stMarkdown'],.st-key-admin_beta_table [data-testid='stMarkdown']{margin-top:0 !important;margin-bottom:0 !important;padding-top:0 !important;padding-bottom:0 !important;}",
      ".st-key-admin_feedback_table [data-testid='stMarkdownContainer'] p,.st-key-admin_reports_table [data-testid='stMarkdownContainer'] p,.st-key-admin_blacklist_table [data-testid='stMarkdownContainer'] p,.st-key-admin_beta_table [data-testid='stMarkdownContainer'] p,.st-key-admin_feedback_table [data-testid='stText'] p,.st-key-admin_reports_table [data-testid='stText'] p,.st-key-admin_blacklist_table [data-testid='stText'] p,.st-key-admin_beta_table [data-testid='stText'] p{margin:0 !important;padding:0 !important;line-height:1.25 !important;}",
      ".st-key-admin_feedback_table [data-testid='stSelectbox'],.st-key-admin_reports_table [data-testid='stSelectbox']{margin-top:0 !important;margin-bottom:0 !important;padding-top:0 !important;padding-bottom:0 !important;}",
      ".st-key-admin_feedback_table [data-baseweb='select'] > div,.st-key-admin_reports_table [data-baseweb='select'] > div{min-height:1.35rem !important;padding-top:0 !important;padding-bottom:0 !important;}",
      ".st-key-admin_beta_table{max-height:none !important;overflow:visible !important;}",
      ".st-key-admin_beta_table .bt-scroll{overflow-x:auto;}",
      ".st-key-admin_beta_table .bt-row{display:grid;grid-template-columns:6.6rem 6rem minmax(9.5rem,1.4fr) 7.6rem 3.8rem 5rem 5.6rem minmax(5rem,1fr) minmax(10rem,2.2fr) 4.6rem;column-gap:.5rem;align-items:start;min-width:64rem;padding:.45rem .5rem;font-size:.78rem;line-height:1.35;}",
      ".st-key-admin_beta_table .bt-headrow{font-weight:700;font-size:.74rem;text-transform:uppercase;letter-spacing:.03em;opacity:.8;}",
      ".st-key-admin_beta_table .bt-cell{min-width:0;overflow-wrap:anywhere;word-break:break-word;}",
      ".st-key-admin_beta_table [data-testid='stHorizontalBlock']{border-bottom:0 !important;align-items:center !important;height:auto !important;min-height:2.8rem;}",
      ".st-key-admin_beta_table [data-testid='stColumn'],.st-key-admin_beta_table [data-testid='stElementContainer'],.st-key-admin_beta_table [data-testid='stMarkdown']{height:auto !important;overflow:visible !important;}",
      ".st-key-admin_beta_table .bt-scroll{overflow-y:hidden;}",
      ".st-key-admin_beta_table .bt-row{padding:.7rem .6rem !important;border-bottom:1px solid var(--ang-border);}",
      ".st-key-admin_beta_table .bt-headrow{padding:.8rem .6rem .6rem !important;border-bottom:1px solid var(--ang-border);}",
      ".st-key-admin_beta_head{position:static !important;}",
      ".st-key-admin_beta_table button{min-height:1.9rem !important;padding:0 !important;white-space:nowrap;}",
      ".st-key-admin_beta_table button p{font-size:1.25rem !important;line-height:1 !important;font-weight:800 !important;margin:0 !important;}",
      ".st-key-admin_beta_table [class*='st-key-admin_beta_yes_'] button p{color:#16a34a !important;}",
      ".st-key-admin_beta_table [class*='st-key-admin_beta_no_'] button p{color:#dc2626 !important;}",
      "[data-baseweb='input'],[data-baseweb='textarea'],[data-baseweb='select'] > div,[data-testid='stFileUploaderDropzone']{border:1px solid var(--ang-border) !important;}",
      "[data-testid='stTextInputRootElement'],[data-testid='stNumberInputContainer'],[data-testid='stTextAreaRootElement'],[data-testid='stDateInputField'],[data-testid='stMultiSelect'] [data-baseweb='select'] > div{border-color:var(--ang-border) !important;}",
      "[class*='_take_box'] [data-testid='stForm'],[class*='_take_box'] [data-testid='stForm'] *:not(input):not(textarea):not(button):not([data-baseweb]):not([data-baseweb] *){background:transparent !important;background-color:transparent !important;}",
      ".theme-pick .theme-name{text-align:center;font-size:.85rem;color:var(--ang-text);padding-bottom:2px;}",
      "[class*='st-key-colours_save_slot'] button,[class*='st-key-colours_back_slot'] button,[class*='st-key-reset_colours'] button{width:2.05rem !important;min-width:2.05rem !important;height:2.05rem !important;min-height:2.05rem !important;padding:0 !important;display:inline-flex;align-items:center;justify-content:center;}",
      "[class*='st-key-colours_save_slot'],[class*='st-key-colours_back_slot'],[class*='st-key-reset_colours']{width:2.05rem !important;flex:0 0 auto !important;}",
      ".st-key-palette_table [data-testid='stVerticalBlock']{gap:.2rem !important;}",
      ".st-key-palette_table [data-testid='stHorizontalBlock']{gap:.5rem !important;align-items:center !important;}",
      ".st-key-palette_table [data-testid='stElementContainer'],.st-key-palette_table [data-testid='stMarkdown']{margin:0 !important;padding:0 !important;}",
      ".st-key-palette_table [data-testid='stColorPicker']{margin:0 !important;padding:0 !important;height:2.6rem;display:flex;align-items:center;}",
      ".st-key-palette_table [data-testid='stColorPicker'] > div{margin:0 !important;gap:.3rem;align-items:center;}",
      ".st-key-palette_table [data-testid='stColorPickerBlock']{width:2.1rem !important;height:2.1rem !important;border-radius:.45rem !important;}",
      ".st-key-palette_table .pal-name{font-size:.8rem;line-height:1.15;color:var(--ang-text);overflow-wrap:anywhere;height:2.6rem;margin:0;padding:0;display:flex;align-items:center;}",
      ".st-key-palette_table [data-testid='stMarkdownContainer'] p,.st-key-palette_table [data-testid='stHtml']{margin:0 !important;padding:0 !important;}",
      ".st-key-palette_table [data-testid='stColumn']{justify-content:center;}",
      ".st-key-admin_feedback_head,.st-key-admin_reports_head,.st-key-admin_blacklist_head,.st-key-admin_beta_head{position:sticky;top:0;z-index:4;background:var(--ang-section);}",
      ".st-key-admin_feedback_table [class*='st-key-admin_feedback_sort_'] button,.st-key-admin_reports_table [class*='st-key-admin_reports_sort_'] button,.st-key-admin_blacklist_table [class*='st-key-admin_blacklist_sort_'] button{background:transparent !important;border:0 !important;box-shadow:none !important;padding:0 !important;min-height:0 !important;height:auto !important;justify-content:flex-start !important;font-weight:700 !important;color:var(--ang-text) !important;}",
      ".st-key-admin_feedback_table [class*='st-key-admin_feedback_sort_'] button:hover,.st-key-admin_reports_table [class*='st-key-admin_reports_sort_'] button:hover,.st-key-admin_blacklist_table [class*='st-key-admin_blacklist_sort_'] button:hover{background:var(--ang-hover) !important;}",
      ".st-key-admin_blacklist_table [class*='st-key-admin_blacklist_remove_'] button{width:1.2rem !important;min-width:1.2rem !important;height:1.2rem !important;min-height:1.2rem !important;padding:0 !important;border-radius:999px !important;line-height:1 !important;}"
  ].join("");
  if (layoutStyle && layoutStyle.textContent !== layoutCss) {
    layoutStyle.remove();
    layoutStyle = null;
  }
  if (!layoutStyle) {
    layoutStyle = document.createElement("style");
    layoutStyle.id = "angstrom-layout-controls";
    layoutStyle.dataset.layout = "ruled";
    layoutStyle.textContent = layoutCss;
    document.head.appendChild(layoutStyle);
  }
  const apply = () => {
    const app = document.querySelector(".stApp");
    if (!app) return;
    const parts = getComputedStyle(app).backgroundColor.match(/\\d+/g);
    const shade = parts
      ? (0.299 * Number(parts[0])) + (0.587 * Number(parts[1])) + (0.114 * Number(parts[2]))
      : 255;
    const dark = shade < 140;
    const stream = document.getElementById("social-stream-root");
    if (stream) stream.classList.toggle("is-dark", dark);
    document.documentElement.classList.toggle("angstrom-night", dark);
    document.querySelectorAll(".brand-mark").forEach((mark) => {
      mark.classList.toggle("is-dark", dark);
      mark.classList.toggle("is-light", !dark);
      const light = mark.querySelector(".logo-light");
      const night = mark.querySelector(".logo-dark");
      if (light) light.toggleAttribute("aria-hidden", dark);
      if (night) night.toggleAttribute("aria-hidden", !dark);
    });
  };
  apply();
  if (!window.angstromBrandWatch) {
    window.angstromBrandWatch = true;
    document.addEventListener("mousedown", (event) => {
      const button = event.target.closest && event.target.closest(".take-face");
      if (!button) return;
      event.preventDefault();
      const row = button.closest(".take-faces");
      const box = button.closest("[class*='_take_box']");
      const input = box && box.querySelector("[data-testid='stTextInputField']");
      if (!input) return;
      const face = button.getAttribute("data-face") || "";
      const limit = Number((row && row.getAttribute("data-limit")) || "160");
      const current = input.value;
      const gap = current && !/\\s$/.test(current) ? " " : "";
      let next = current + gap + face;
      if (next.length > limit) {
        next = current + face;
        if (next.length > limit) return;
      }
      const setValue = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      setValue.call(input, next);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus();
      const end = input.value.length;
      if (input.setSelectionRange) input.setSelectionRange(end, end);
    }, true);
    const arm = () => {
      const app = document.querySelector(".stApp");
      if (!app || app.dataset.brandWatch) return;
      app.dataset.brandWatch = "1";
      new MutationObserver(apply).observe(app, { attributes: true });
    };
    arm();
    document.addEventListener("click", () => {
      setTimeout(apply, 60);
      setTimeout(apply, 350);
    });
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    if (media.addEventListener) media.addEventListener("change", apply);
    const tab = document.createElement("button");
    tab.type = "button";
    tab.id = "angstrom-sidebar-tab";
    tab.className = "angstrom-sidebar-tab";
    tab.setAttribute("aria-controls", "stSidebar");
    tab.innerHTML = "<svg viewBox='0 0 24 24' width='22' height='22' aria-hidden='true'><path d='M15.2 6.2 9.4 12l5.8 5.8' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/><path d='M10.2 6.2 4.4 12l5.8 5.8' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/></svg>";
    document.body.appendChild(tab);
    const placeSidebarTab = () => {
      const sidebar = document.querySelector("[data-testid='stSidebar']");
      if (!sidebar) {
        tab.hidden = true;
        return;
      }
      tab.hidden = false;
      const collapsed = sidebar.getAttribute("data-collapsed") === "true";
      tab.classList.toggle("is-closed", collapsed);
      const label = collapsed ? "Expand sidebar" : "Collapse sidebar";
      tab.title = label;
      tab.setAttribute("aria-label", label);
      tab.setAttribute("aria-expanded", collapsed ? "false" : "true");
      if (collapsed) {
        tab.style.left = "0px";
        return;
      }
      const edge = Math.max(0, Math.round(sidebar.getBoundingClientRect().right));
      tab.style.left = edge + "px";
    };
    let tracking = 0;
    const followSidebarTab = (ms) => {
      cancelAnimationFrame(tracking);
      const stop = performance.now() + ms;
      const step = (now) => {
        placeSidebarTab();
        if (now < stop) tracking = requestAnimationFrame(step);
      };
      tracking = requestAnimationFrame(step);
    };
    tab.addEventListener("click", () => {
      const sidebar = document.querySelector("[data-testid='stSidebar']");
      const collapsed = sidebar && sidebar.getAttribute("data-collapsed") === "true";
      const target = collapsed
        ? document.querySelector("[data-testid='stExpandSidebarButton']")
        : document.querySelector("[data-testid='stSidebarCollapseButton'] button");
      if (target) target.click();
      followSidebarTab(400);
    });
    const watchSidebar = () => {
      const sidebar = document.querySelector("[data-testid='stSidebar']");
      if (!sidebar || sidebar.dataset.tabWatch) return;
      sidebar.dataset.tabWatch = "1";
      new ResizeObserver(() => placeSidebarTab()).observe(sidebar);
    };
    watchSidebar();
    placeSidebarTab();
    const shell = document.querySelector(".stApp") || document.body;
    new MutationObserver(() => {
      watchSidebar();
      placeSidebarTab();
    }).observe(shell, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-collapsed", "style", "class"]
    });
    window.addEventListener("resize", () => placeSidebarTab());
    // While the sidebar width is dragged its text re-wraps and the content changes height. Keep the
    // item at the top of the view where it is on screen, so the view does not slide away.
    let dragAnchor = null;
    const sideBox = () => document.querySelector("[data-testid='stSidebarContent']");
    const pickAnchor = () => {
      const box = sideBox();
      if (!box || box.scrollTop < 2) return null;
      const rect = box.getBoundingClientRect();
      let node = document.elementFromPoint(rect.left + Math.min(40, rect.width / 2), rect.top + 30);
      if (!node || node === box || !box.contains(node)) return null;
      while (node.parentElement && node.parentElement !== box && node.getBoundingClientRect().height < 24) {
        node = node.parentElement;
      }
      return { node, offset: node.getBoundingClientRect().top - rect.top };
    };
    const holdAnchor = () => {
      const box = sideBox();
      if (!dragAnchor || !box || !dragAnchor.node.isConnected) return;
      const rect = box.getBoundingClientRect();
      const shift = (dragAnchor.node.getBoundingClientRect().top - rect.top) - dragAnchor.offset;
      if (Math.abs(shift) > 1) box.scrollTop += shift;
    };
    const holdLoop = () => {
      if (!dragAnchor) return;
      holdAnchor();
      requestAnimationFrame(holdLoop);
    };
    document.addEventListener("pointerdown", (event) => {
      const sidebar = document.querySelector("[data-testid='stSidebar']");
      if (!sidebar || sidebar.getAttribute("data-collapsed") === "true") return;
      const edge = sidebar.getBoundingClientRect().right;
      if (Math.abs(event.clientX - edge) > 10) return;
      dragAnchor = pickAnchor();
      if (dragAnchor) requestAnimationFrame(holdLoop);
    }, true);
    document.addEventListener("pointerup", () => {
      if (dragAnchor) setTimeout(() => { holdAnchor(); dragAnchor = null; }, 300);
    }, true);
  }
  return () => {};
}
"""
_brand_watch = st.components.v2.component(
    "brand_watch",
    js=_BRAND_JS,
    isolate_styles=False,
)

# A drag from one colour block onto another copies that colour. The click still opens the picker.
_COLOUR_COPY_JS = """
export default function(component) {
  const { setTriggerValue, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  window.__angstromColourCopy = setTriggerValue;
  // Only a real colour picker counts, whatever the names of the boxes around other controls are.
  const isPicker = (el) => !!el && !!el.querySelector && !!el.querySelector("[data-testid='stColorPicker']");
  const pickerOf = (node) => {
    const found = node && node.closest ? node.closest("[class*='st-key-colour_']") : null;
    return isPicker(found) ? found : null;
  };
  const keyOf = (el) => {
    const match = String(el.className || "").match(/st-key-(colour_[a-z0-9_]+)/);
    return match ? match[1] : "";
  };
  const hexOf = (picker) => {
    const block = picker.querySelector("button div") || picker.querySelector("button");
    if (!block) return "";
    const parts = getComputedStyle(block).backgroundColor.match(/\\d+/g);
    if (!parts || parts.length < 3) return "";
    const hex = parts.slice(0, 3).map((part) => Number(part).toString(16).padStart(2, "0")).join("");
    return "#" + hex;
  };
  const arm = () => {
    document.querySelectorAll("[class*='st-key-colour_']").forEach((picker) => {
      if (keyOf(picker) === "colour_copy" || !isPicker(picker)) return;
      const handle = picker.querySelector("button");
      if (!handle || handle.getAttribute("draggable") === "true") return;
      handle.setAttribute("draggable", "true");
      handle.title = "Drag onto another colour to copy it";
    });
  };
  const pointAt = (el, clientX, clientY) => {
    if (!el) return;
    const pointed = {
      bubbles: true,
      cancelable: true,
      view: window,
      clientX: clientX,
      clientY: clientY,
      pageX: clientX + window.scrollX,
      pageY: clientY + window.scrollY,
    };
    el.dispatchEvent(new MouseEvent("mousedown", pointed));
    window.dispatchEvent(new MouseEvent("mouseup", pointed));
  };
  const moveSelector = (saturation, brightness) => {
    const white = document.querySelector(".saturation-white");
    const container = white && white.parentElement;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return;
    const across = Math.max(0, Math.min(100, saturation)) / 100;
    const down = (100 - Math.max(0, Math.min(100, brightness))) / 100;
    pointAt(container, rect.left + across * rect.width, rect.top + down * rect.height);
  };
  const moveHue = (degrees) => {
    const bar = document.querySelector(".hue-horizontal");
    if (!bar) return;
    const rect = bar.getBoundingClientRect();
    if (rect.width < 2) return;
    const across = Math.max(0, Math.min(360, degrees)) / 360;
    pointAt(bar, rect.left + across * rect.width, rect.top + rect.height / 2);
  };
  const hexToHsv = (raw) => {
    const text = String(raw || "").replace("#", "").trim();
    if (!/^[0-9a-fA-F]{6}$/.test(text)) return null;
    const red = parseInt(text.slice(0, 2), 16) / 255;
    const green = parseInt(text.slice(2, 4), 16) / 255;
    const blue = parseInt(text.slice(4, 6), 16) / 255;
    const max = Math.max(red, green, blue);
    const min = Math.min(red, green, blue);
    const delta = max - min;
    let hue = 0;
    if (delta !== 0) {
      if (max === red) hue = ((green - blue) / delta) % 6;
      else if (max === green) hue = (blue - red) / delta + 2;
      else hue = (red - green) / delta + 4;
      hue *= 60;
      if (hue < 0) hue += 360;
    }
    return { h: hue, s: max === 0 ? 0 : (delta / max) * 100, v: max * 100 };
  };
  const readHsv = (hueBar) => {
    const satPointer = document.querySelector(".saturation-black > div");
    const huePointer = hueBar.querySelector("div");
    let hue = NaN;
    let saturation = NaN;
    let brightness = NaN;
    if (satPointer) {
      saturation = parseFloat(satPointer.style.left);
      const top = parseFloat(satPointer.style.top);
      if (!Number.isNaN(top)) brightness = 100 - top;
    }
    if (huePointer) {
      const left = parseFloat(huePointer.style.left);
      if (!Number.isNaN(left)) hue = (left / 100) * 360;
    }
    if (!Number.isNaN(hue) && !Number.isNaN(saturation) && !Number.isNaN(brightness)) {
      return { h: hue, s: saturation, v: brightness };
    }
    let node = hueBar;
    while (node && node !== document.body) {
      const inputs = node.querySelectorAll("input");
      for (const input of inputs) {
        const fromHex = hexToHsv(input.value);
        if (fromHex) return fromHex;
      }
      node = node.parentElement;
    }
    return null;
  };
  const placeAxes = () => {
    const hueBar = document.querySelector(".hue-horizontal");
    let axes = document.getElementById("ang-colour-axes");
    if (!hueBar) {
      if (axes) axes.remove();
      return;
    }
    if (!document.getElementById("ang-colour-axes-style")) {
      const style = document.createElement("style");
      style.id = "ang-colour-axes-style";
      style.textContent = "div:has(> div > .hue-horizontal){margin-bottom:124px !important;}#ang-colour-axes{position:fixed;z-index:10000020;display:flex;flex-direction:column;gap:4px;}#ang-colour-axes label{display:flex;flex-direction:column;gap:1px;font:600 11px/1.2 sans-serif;color:#31333f;}#ang-colour-axes input{width:100%;margin:0;}html.angstrom-night #ang-colour-axes label{color:#f3f4f6;}";
      document.head.appendChild(style);
    }
    const current = readHsv(hueBar) || { h: 0, s: 0, v: 0 };
    if (!axes) {
      axes = document.createElement("div");
      axes.id = "ang-colour-axes";
      const shown = {
        h: Math.round(current.h),
        s: Math.round(current.s),
        v: Math.round(current.v),
      };
      axes.innerHTML = "<label>Hue<input type='range' min='0' max='360' data-axis='h' value='" + shown.h + "'></label><label>Saturation<input type='range' min='0' max='100' data-axis='s' value='" + shown.s + "'></label><label>Brightness<input type='range' min='0' max='100' data-axis='v' value='" + shown.v + "'></label>";
      const keepOpen = (event) => event.stopPropagation();
      axes.addEventListener("mousedown", keepOpen);
      axes.addEventListener("click", keepOpen);
      axes.addEventListener("input", (event) => {
        const axis = event.target.getAttribute("data-axis");
        if (axis === "h") {
          moveHue(Number(event.target.value));
          return;
        }
        const saturation = axes.querySelector("[data-axis='s']");
        const brightness = axes.querySelector("[data-axis='v']");
        moveSelector(Number(saturation.value), Number(brightness.value));
      });
      document.body.appendChild(axes);
    }
    const rect = hueBar.getBoundingClientRect();
    let layer = 10000020;
    let node = hueBar;
    while (node && node !== document.body) {
      const value = Number(getComputedStyle(node).zIndex);
      if (value > layer) layer = value + 1;
      node = node.parentElement;
    }
    axes.style.zIndex = String(layer);
    axes.style.left = rect.left + "px";
    axes.style.top = (rect.bottom + 8) + "px";
    axes.style.width = rect.width + "px";
    const hsv = readHsv(hueBar);
    if (!hsv) return;
    const hueSlider = axes.querySelector("[data-axis='h']");
    const saturationSlider = axes.querySelector("[data-axis='s']");
    const brightnessSlider = axes.querySelector("[data-axis='v']");
    if (hueSlider && document.activeElement !== hueSlider) hueSlider.value = String(Math.round(hsv.h));
    if (saturationSlider && document.activeElement !== saturationSlider) saturationSlider.value = String(Math.round(hsv.s));
    if (brightnessSlider && document.activeElement !== brightnessSlider) brightnessSlider.value = String(Math.round(hsv.v));
  };
  window.__angstromPlaceAxes = placeAxes;
  if (!window.__angstromColourDrag) {
    window.__angstromColourDrag = true;
    let dragged = false;
    document.addEventListener("dragstart", (event) => {
      const picker = pickerOf(event.target);
      if (!picker) return;
      const key = keyOf(picker);
      const hex = hexOf(picker);
      if (!key || key === "colour_copy" || !hex) return;
      dragged = true;
      event.dataTransfer.setData("text/plain", key + "|" + hex);
      event.dataTransfer.effectAllowed = "copy";
    });
    document.addEventListener("dragover", (event) => {
      const picker = pickerOf(event.target);
      if (!picker || keyOf(picker) === "colour_copy") return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      picker.classList.add("ang-colour-drop");
    });
    document.addEventListener("dragleave", (event) => {
      const picker = pickerOf(event.target);
      if (!picker) return;
      const next = event.relatedTarget;
      if (next && picker.contains(next)) return;
      picker.classList.remove("ang-colour-drop");
    });
    document.addEventListener("dragend", () => {
      document.querySelectorAll(".ang-colour-drop").forEach((el) => el.classList.remove("ang-colour-drop"));
    });
    document.addEventListener("drop", (event) => {
      const picker = pickerOf(event.target);
      document.querySelectorAll(".ang-colour-drop").forEach((el) => el.classList.remove("ang-colour-drop"));
      if (!picker) return;
      event.preventDefault();
      const raw = event.dataTransfer.getData("text/plain") || "";
      const parts = raw.split("|");
      const target = keyOf(picker);
      const send = window.__angstromColourCopy;
      if (!send || parts.length !== 2 || !target || target === parts[0]) return;
      if (!/^#[0-9a-fA-F]{6}$/.test(parts[1])) return;
      send("copied", target + "|" + parts[1].toLowerCase() + "|" + Date.now());
    });
    document.addEventListener("click", (event) => {
      const card = event.target && event.target.closest ? event.target.closest("[data-theme-pick]") : null;
      if (card && window.__angstromColourCopy) {
        window.__angstromColourCopy("copied", "themepick|" + card.getAttribute("data-theme-pick") + "|" + Date.now());
        return;
      }
      if (!dragged || !pickerOf(event.target)) return;
      dragged = false;
      event.preventDefault();
      event.stopPropagation();
    }, true);
    const follow = () => {
      arm();
      if (window.__angstromPlaceAxes) window.__angstromPlaceAxes();
    };
    new MutationObserver(follow).observe(document.body, { childList: true, subtree: true });
    document.addEventListener("scroll", follow, true);
    window.addEventListener("resize", follow);
    const tick = () => {
      if (document.querySelector(".hue-horizontal") && window.__angstromPlaceAxes) window.__angstromPlaceAxes();
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  arm();
  placeAxes();
  return () => {};
}
"""
_colour_copy = st.components.v2.component(
    "colour_copy",
    js=_COLOUR_COPY_JS,
    isolate_styles=False,
)

# A normal link starts a new Streamlit session and logs the user out.
# This stays on the page and reports the clicked name back to Python.
# Comment balloons open the social signals stream on this page. They do not navigate away.
_COMMENT_BIND_JS = """
  const bindComments = (root) => {
    root.querySelectorAll("button[data-stream-key]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        button.blur();
        if (window.openSocialStream) {
          window.openSocialStream(button.getAttribute("data-stream-key") || "");
        }
      });
    });
  };
"""
_SCORE_TABLE_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  let host = parentElement.querySelector("[data-score-host]");
  Array.from(parentElement.children).forEach((child) => {
    if (child !== host) child.remove();
  });
  if (!host) {
    host = document.createElement("div");
    host.setAttribute("data-score-host", "");
    parentElement.appendChild(host);
  }
  host.innerHTML = typeof data === "string" ? data : "";
  const openSection = (targetId) => {
    const anchor = document.getElementById(targetId);
    if (!anchor) return null;
    let section = anchor;
    let node = anchor;
    for (let step = 0; step < 8 && node; step += 1) {
      const sibling = node.nextElementSibling;
      const expander = sibling && sibling.querySelector
        ? sibling.querySelector('[data-testid="stExpander"]')
        : null;
      if (expander) {
        section = expander;
        const details = expander.querySelector('[data-testid="stExpanderDetails"]');
        const summary = expander.querySelector("summary");
        if (details && details.hasAttribute("inert") && summary) {
          window.__angstromSectionBulk = true;
          summary.click();
          window.setTimeout(() => { window.__angstromSectionBulk = false; }, 80);
        }
        break;
      }
      node = node.parentElement;
    }
    return section;
  };
  const openAndScroll = (targetId) => {
    const section = openSection(targetId);
    if (!section) return;
    const go = () => {
      const current = section.isConnected ? section : document.getElementById(targetId);
      if (!current) return;
      current.scrollIntoView({behavior: "auto", block: "start"});
      const scroller = current.closest('[data-testid="stMain"]') || current.closest("section.main");
      if (!scroller) return;
      const top = current.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 72;
      scroller.scrollTop = Math.max(0, top);
    };
    go();
    window.setTimeout(go, 50);
    window.setTimeout(go, 250);
    window.setTimeout(go, 700);
  };
  const sendPick = (pick) => {
    const now = Date.now();
    if (window.__angstromPickAt && now - window.__angstromPickAt < 400) return;
    window.__angstromPickAt = now;
    setTriggerValue("picked", pick);
  };
  host.querySelectorAll("button[data-pick]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      button.blur();
      const pick = button.getAttribute("data-pick") || "";
      const noteId = button.getAttribute("data-note") || "";
      if (noteId) {
        // Shown as read straight away; the server records it with this click.
        button.removeAttribute("data-note");
        const card = button.firstElementChild;
        if (card) {
          card.style.borderColor = "#e5e7eb";
          if (card.firstElementChild) card.firstElementChild.style.fontWeight = "500";
        }
      }
      const sendRead = () => {
        if (noteId && window.__angstromPickAsset) window.__angstromPickAsset("picked", "read|" + noteId);
      };
      if (pick.indexOf("mood|") === 0) {
        openAndScroll("market-mood-" + pick.split("|")[1]);
        sendRead();
        return;
      }
      const parts = pick.split("|");
      if (parts[2] === "breakdown") {
        const id = parts[0] + "|" + parts[1];
        const loaded = Array.from(
          document.querySelectorAll("tr.ang-row-on button[data-pick]")
        ).some((el) => {
          const value = el.getAttribute("data-pick") || "";
          return value === id || value.indexOf(id + "|") === 0;
        });
        if (loaded && document.getElementById("score-breakdown")) {
          openSection("interactive-chart");
          window.setTimeout(() => openAndScroll("score-breakdown"), 90);
          return;
        }
        sendPick(pick);
        return;
      }
      const already = parts.length === 2 && Array.from(
        document.querySelectorAll("tr.ang-row-on button[data-pick]")
      ).some((el) => (el.getAttribute("data-pick") || "") === pick);
      if (already) {
        openAndScroll("interactive-chart");
        sendRead();
        return;
      }
      if (button.hasAttribute("data-alert") && window.__angstromPickAsset) {
        window.__angstromPickAsset("picked", pick + (noteId ? "|note:" + noteId : ""));
        return;
      }
      sendPick(pick);
    });
  });
  host.querySelectorAll("td[data-sentiment-pick]").forEach((cell) => {
    cell.addEventListener("click", (event) => {
      if (event.target.closest("button")) return;
      sendPick(cell.getAttribute("data-sentiment-pick") || "");
    });
  });
  const valueOf = (row, col) => {
    const cell = row.cells[col];
    if (!cell) return null;
    const raw = cell.getAttribute("data-sort");
    if (raw === null || raw === "") return null;
    const num = Number(raw);
    return Number.isFinite(num) ? num : raw.toLowerCase();
  };
  const applySort = (table, col, dir) => {
    const body = table.querySelector("tbody");
    if (!body) return;
    const rows = Array.from(body.querySelectorAll("tr"));
    const numeric = rows.some((row) => typeof valueOf(row, col) === "number");
    rows.sort((a, b) => {
      const av = valueOf(a, col);
      const bv = valueOf(b, col);
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      const cmp = numeric ? av - bv : String(av).localeCompare(String(bv));
      return cmp * dir;
    });
    rows.forEach((row) => body.appendChild(row));
    table.querySelectorAll("[data-sort-mark]").forEach((mark) => {
      mark.textContent = "";
    });
    const active = table.querySelector('button[data-sort-col="' + col + '"] [data-sort-mark]');
    if (active) active.textContent = dir < 0 ? " ↓" : " ↑";
  };
  host.querySelectorAll("table[data-table]").forEach((table) => {
    const key = table.getAttribute("data-table");
    const saved = window.scoreTableSort && window.scoreTableSort[key];
    if (saved) applySort(table, saved.col, saved.dir);
  });
  host.querySelectorAll("button[data-sort-col]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const table = button.closest("table");
      const col = Number(button.getAttribute("data-sort-col"));
      const key = table.getAttribute("data-table") || "table";
      const state = window.scoreTableSort || (window.scoreTableSort = {});
      const prev = state[key];
      const rows = Array.from(table.querySelectorAll("tbody tr"));
      const numeric = rows.some((row) => typeof valueOf(row, col) === "number");
      let dir = numeric ? -1 : 1;
      if (prev && prev.col === col) dir = prev.dir * -1;
      else if (!prev && col === 2) dir = 1;
      state[key] = {col: col, dir: dir};
      applySort(table, col, dir);
    });
  });
""" + _COMMENT_BIND_JS + """
  bindComments(host);
  return () => host.remove();
}
"""
_score_table = st.components.v2.component(
    "score_table",
    js=_SCORE_TABLE_JS,
    isolate_styles=False,
)
_COMMENT_ROW_JS = """
export default function(component) {
  const { data, parentElement } = component;
  let host = parentElement.querySelector("[data-comment-host]");
  Array.from(parentElement.children).forEach((child) => {
    if (child !== host) child.remove();
  });
  if (!host) {
    host = document.createElement("div");
    host.setAttribute("data-comment-host", "");
    parentElement.appendChild(host);
  }
  host.innerHTML = typeof data === "string" ? data : "";
""" + _COMMENT_BIND_JS + """
  bindComments(host);
  return () => host.remove();
}
"""
_comment_row = st.components.v2.component(
    "comment_row",
    js=_COMMENT_ROW_JS,
    isolate_styles=False,
)
_CROWD_SYNC_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  let payload = data;
  if (typeof data === "string") {
    try { payload = JSON.parse(data); } catch (error) { payload = null; }
  }
  if (!payload || !payload.asset) return () => {};
  const cells = (attr) => {
    const found = [];
    const scan = (root) => {
      if (!root || !root.querySelectorAll) return;
      root.querySelectorAll("[" + attr + "]").forEach((cell) => {
        if (cell.getAttribute(attr) === payload.asset) found.push(cell);
      });
      root.querySelectorAll("*").forEach((el) => {
        if (el.shadowRoot) scan(el.shadowRoot);
      });
    };
    scan(document);
    return found;
  };
  const paint = () => {
    cells("data-crowd-mark").forEach((cell) => {
      cell.innerHTML = payload.mark || "";
      cell.setAttribute("data-sort", payload.markSort || "");
    });
    cells("data-crowd-avg").forEach((cell) => {
      cell.innerHTML = payload.average || "";
      cell.setAttribute("data-sort", payload.averageSort || "");
    });
  };
  paint();
  const timers = [40, 180, 500].map((wait) => setTimeout(paint, wait));
  return () => timers.forEach((timer) => clearTimeout(timer));
}
"""
_crowd_sync = st.components.v2.component(
    "crowd_sync",
    js=_CROWD_SYNC_JS,
    isolate_styles=False,
)

_SOCIAL_STREAM_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  let items = [];
  let savedAsset = "";
  let account = "";
  let panelPrefs = {};
  window.socialPopout = false;
  try {
    const parsed = typeof data === "string" ? JSON.parse(data || "[]") : data;
    if (Array.isArray(parsed)) {
      items = parsed;
    } else if (parsed && typeof parsed === "object") {
      items = Array.isArray(parsed.items) ? parsed.items : [];
      const savedScopes = { watchlist: "watchlist", crypto: "crypto", stock: "stock" };
      savedAsset = savedScopes[parsed.asset] || "";
      window.socialChatReady = Array.isArray(parsed.chat);
      window.socialChat = window.socialChatReady ? parsed.chat : [];
      window.socialMe = parsed.me && typeof parsed.me === "object" ? parsed.me : {};
      window.socialFavourites = Array.isArray(parsed.favourites) ? parsed.favourites.map(String) : [];
      window.socialGroups = Array.isArray(parsed.groups) ? parsed.groups : [];
      window.socialChatNotice = typeof parsed.notice === "string" ? parsed.notice : "";
      window.socialChatFaces = Array.isArray(parsed.faces) ? parsed.faces : [];
      window.socialChatLimit = Number(parsed.limit) || 160;
      account = String(parsed.account || "");
      panelPrefs = parsed.panel && typeof parsed.panel === "object" ? parsed.panel : {};
      window.socialPopout = !!parsed.popout;
      window.socialPopoutOpts = { asWindow: parsed.popoutWindow !== false, fold: parsed.popoutFold !== false };
    }
  } catch (error) {
    items = [];
    window.socialGroups = [];
  }
  if (window.socialAccount !== account) {
    window.socialAccount = account;
    window.socialStreamState = null;
    const width = Number(panelPrefs.width);
    const split = Number(panelPrefs.split);
    window.socialPanelWidth = width >= 320 && width <= 900 ? Math.round(width) : 420;
    window.socialPanelSplit = split > 0.08 && split < 0.92 ? split : 0.5;
    window.socialPanelPinned = !!panelPrefs.pinned;
    window.socialPanelLayout = panelPrefs.layout === "side" ? "side" : "stacked";
    const existing = document.getElementById("social-stream-root");
    if (existing) existing.remove();
  }
  window.socialStreamItems = items;
  window.__angstromTabId = window.__angstromTabId || Math.random().toString(36).slice(2);
  window.socialStreamReport = (name, value) => {
    setTriggerValue(name, value);
    if ((name === "chat" || name === "signal") && "BroadcastChannel" in window) {
      // Tell the other tabs a comment changed, once the server has had time to save it.
      window.setTimeout(() => {
        if (!window.__angstromChangeTx) window.__angstromChangeTx = new BroadcastChannel("angstrom-link");
        window.__angstromChangeTx.postMessage({ type: "changed", from: window.__angstromTabId });
      }, 1500);
    }
  };
  installSocialStream(savedAsset);
  window.renderSocialStream();
  if (window.socialRefit) window.socialRefit();
  if (window.socialPopout && !window.__angstromLinkRx && "BroadcastChannel" in window) {
    window.__angstromLinkRx = new BroadcastChannel("angstrom-link");
    window.__angstromLinkRx.onmessage = (event) => {
      const msg = event.data || {};
      const state = window.socialStreamState;
      if (msg.type === "changed" && msg.from !== window.__angstromTabId && window.socialStreamReport) {
        window.socialStreamReport("refresh", String(Date.now()));
        return;
      }
      if (msg.type !== "asset" || !msg.key || !state) return;
      state.linked = { key: String(msg.key), label: String(msg.label || msg.key) };
      if (state.follow) {
        state.asset = state.linked.key;
        window.renderSocialStream();
      }
    };
    window.__angstromLinkRx.postMessage({ type: "hello" });
  }
  return () => {};

  function installSocialStream(savedAsset) {
    window.socialStreamState = window.socialStreamState || {
      open: !!window.socialPopout, side: "", asset: savedAsset || "", person: "",
      layout: window.socialPanelLayout || "stacked", follow: true
    };
    window.socialApplyLayout = (panel) => {
      const state = window.socialStreamState || {};
      const side = !!window.socialPopout && state.layout === "side" && window.innerWidth >= 760;
      panel.classList.toggle("is-popout", !!window.socialPopout);
      panel.classList.toggle("is-side", side);
    };
    if (typeof window.socialStreamState.pinned !== "boolean") {
      window.socialStreamState.pinned = !!window.socialPanelPinned;
    }
    if (String(window.socialChatNotice || "") === "Invite sent.") {
      window.socialStreamState.groupFor = null;
    }
    const reportNotice = String(window.socialChatNotice || "");
    if (reportNotice.indexOf("Report sent") === 0 || reportNotice.indexOf("Report already") === 0) {
      window.socialStreamState.report = null;
    }
    let style = document.getElementById("social-stream-style");
    if (style && style.dataset.layout !== "flag2") {
      style.remove();
      style = null;
    }
    if (!style) {
      style = document.createElement("style");
      style.id = "social-stream-style";
      style.dataset.layout = "flag2";
      style.textContent = [
        "#social-stream-root{position:fixed;inset:0;z-index:10000000;pointer-events:none;}",
        "#social-stream-root.is-open{pointer-events:auto;}",
        "#social-stream-root.is-open.is-pinned{pointer-events:none;}",
        "#social-stream-root .scrim{position:absolute;inset:0;background:rgba(17,24,39,0.35);opacity:0;transition:opacity .2s ease;}",
        "#social-stream-root.is-open .scrim{opacity:1;}",
        "#social-stream-root.is-open.is-pinned .scrim{opacity:0;pointer-events:none;}",
        "#social-stream-root.is-open.is-pinned .panel,#social-stream-root.is-open.is-pinned .edge{pointer-events:auto;}",
        "#social-stream-root .panel{position:absolute;top:0;right:0;height:100%;width:min(var(--social-width,420px),100vw);background:var(--ang-social,#fff);color:#111827;box-shadow:-12px 0 40px rgba(17,24,39,.18);transform:translateX(100%);transition:transform .22s ease;display:flex;flex-direction:column;overflow:hidden;pointer-events:auto;}",
        "#social-stream-root .width-grip{position:absolute;top:0;bottom:0;left:0;width:12px;z-index:3;cursor:col-resize;touch-action:none;user-select:none;}",
        "#social-stream-root .width-grip::before{content:'';position:absolute;top:50%;left:3px;width:4px;height:48px;margin-top:-24px;border-radius:999px;background:#9ca3af;}",
        "#social-stream-root .width-grip:hover::before,#social-stream-root .width-grip.is-dragging::before{background:#111827;}",
        "#social-stream-root.is-width-dragging,#social-stream-root.is-width-dragging *{cursor:col-resize !important;user-select:none !important;}",
        "#social-stream-root.is-width-dragging .panel,#social-stream-root.is-width-dragging .edge{transition:none;}",
        "#social-stream-root .stream-pane,#social-stream-root .chat-pane{display:flex;flex-direction:column;min-height:0;overflow:hidden;}",
        "#social-stream-root .splitter{position:relative;flex:none;height:16px;cursor:row-resize;background:#9ca3af;border-top:1px solid #4b5563;border-bottom:1px solid #4b5563;display:flex;align-items:center;justify-content:center;touch-action:none;user-select:none;}",
        "#social-stream-root .splitter::before{content:'';width:64px;height:4px;border-radius:999px;background:#1f2937;}",
        "#social-stream-root .splitter::after{content:'';position:absolute;left:0;right:0;top:-10px;bottom:-10px;}",
        "#social-stream-root .splitter:hover,#social-stream-root .splitter.is-dragging{background:#4b5563;}",
        "#social-stream-root .splitter:hover::before,#social-stream-root .splitter.is-dragging::before{background:#111827;}",
        "#social-stream-root.is-dragging,#social-stream-root.is-dragging *{cursor:row-resize !important;user-select:none !important;}",
        "#social-stream-root.is-open .panel{transform:none;}",
        "#social-stream-root .finder{flex:none;padding:14px 18px 0;}",
        "#social-stream-root .finder input{width:100%;box-sizing:border-box;font:inherit;font-size:.9rem;color:#111827;border:1px solid #d1d5db;border-radius:8px;padding:7px 10px;background:#fff;}",
        "#social-stream-root .head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:18px 18px 4px;}",
        "#social-stream-root h2{margin:0;font-size:1.15rem;line-height:1.25;font-weight:650;}",
        "#social-stream-root .kicker{font-size:.72rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#6b7280;margin-bottom:2px;}",
        "#social-stream-root .head-actions{display:flex;gap:6px;flex:none;}",
        "#social-stream-root .close,#social-stream-root .pin{background:#f3f4f6;border:0;border-radius:999px;padding:6px 12px;font:inherit;font-weight:600;cursor:pointer;color:#111827;}",
        "#social-stream-root .pin.is-on{background:#111827;color:#fff;}",
        "#social-stream-root .edge{position:fixed;top:4.75rem;right:0;z-index:2;pointer-events:auto;display:flex;align-items:center;justify-content:center;width:2rem;height:2rem;padding:0;border:1px solid rgba(49,51,63,.2);border-right:0;border-radius:.5rem 0 0 .5rem;background:#fff;color:#808495;cursor:pointer;box-shadow:-1px 1px 4px rgba(0,0,0,.08);transition:right .22s ease,background .15s ease,color .15s ease;}",
        "#social-stream-root .edge:hover{background:#f0f2f6;color:#ff4b4b;}",
        "#social-stream-root.is-open .edge{right:min(var(--social-width,420px),calc(100vw - 2.25rem));}",
        "#social-stream-root.is-open .edge svg{transform:scaleX(-1);}",
        "#social-stream-root .filters{padding:10px 18px 0;}",
        "#social-stream-root .chips{display:flex;flex-wrap:wrap;gap:6px;}",
        "#social-stream-root .chips button{background:#fff;border:1px solid #d1d5db;border-radius:999px;padding:4px 10px;font:inherit;font-size:.82rem;cursor:pointer;color:#374151;}",
        "#social-stream-root .chips button.is-on{background:#111827;border-color:#111827;color:#fff;}",
        "#social-stream-root .picks{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;}",
        "#social-stream-root .picks label{display:flex;flex-direction:column;gap:4px;font-size:.75rem;font-weight:600;color:#6b7280;}",
        "#social-stream-root select{font:inherit;font-size:.85rem;color:#111827;border:1px solid #d1d5db;border-radius:8px;padding:6px 8px;background:#fff;}",
        "#social-stream-root .count{padding:10px 18px 0;font-size:.78rem;color:#6b7280;}",
        "#social-stream-root .list,#social-stream-root .chat-list{flex:1;overflow:auto;min-height:0;padding:8px 18px 12px;}",
        "#social-stream-root .chat-head{padding:10px 18px 0;}",
        "#social-stream-root .composer{padding:8px 18px 14px;border-top:1px solid #f3f4f6;}",
        "#social-stream-root .chat-box{width:100%;box-sizing:border-box;min-height:58px;max-height:120px;resize:vertical;font:inherit;font-size:.9rem;border:1px solid #d1d5db;border-radius:8px;padding:8px;}",
        "#social-stream-root .faces{display:flex;gap:4px;margin-top:6px;}",
        "#social-stream-root .faces button{flex:1;min-width:0;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:2px 0;cursor:pointer;font-size:1rem;line-height:1.2;}",
        "#social-stream-root .faces button.face-poop{font-size:1.45rem;line-height:1;}",
        "#social-stream-root .composer-row{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:6px;}",
        "#social-stream-root .chars{color:#6b7280;font-size:.75rem;}",
        "#social-stream-root .post{background:#111827;color:#fff;border:0;border-radius:999px;padding:6px 14px;font:inherit;font-weight:600;cursor:pointer;}",
        "#social-stream-root .post:disabled{opacity:.45;cursor:default;}",
        "#social-stream-root .replying{display:flex;justify-content:space-between;gap:8px;margin-bottom:6px;color:#6b7280;font-size:.78rem;}",
        "#social-stream-root .replying button{background:none;border:0;padding:0;color:#1d4ed8;cursor:pointer;font:inherit;font-size:.78rem;}",
        "#social-stream-root .chat-card{padding:12px 0;border-top:1px solid #e5e7eb;}",
        "#social-stream-root .reply{margin:8px 0 0 28px;padding-left:10px;border-left:2px solid #e5e7eb;}",
        "#social-stream-root .chat-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;}",
        "#social-stream-root .chat-actions button{background:#fff;border:1px solid #e5e7eb;border-radius:999px;padding:2px 8px;font:inherit;font-size:.78rem;cursor:pointer;color:#374151;}",
        "#social-stream-root .chat-actions button.thumb-up,#social-stream-root .chat-actions button.thumb-down{display:inline-flex;align-items:center;gap:4px;font-weight:700;background:transparent;}",
        "#social-stream-root .chat-actions button.thumb-up{color:#15803d;}",
        "#social-stream-root .chat-actions button.thumb-down{color:#b91c1c;}",
        "#social-stream-root .chat-actions button.thumb-up.is-on{background:#dcfce7;border-color:#15803d;color:#15803d;}",
        "#social-stream-root .chat-actions button.thumb-down.is-on{background:#fee2e2;border-color:#b91c1c;color:#b91c1c;}",
        "#social-stream-root .chat-actions button.reply-note,#social-stream-root .chat-actions button.delete-note{font-size:1rem;line-height:1;padding:2px 7px;}",
        "#social-stream-root .chat-actions button.delete-note{color:#b91c1c;}",
        "#social-stream-root .report-box{flex:none;margin:10px 18px 0;padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px;background:#f8fafc;}",
        "#social-stream-root .report-title{font-weight:650;font-size:.9rem;}",
        "#social-stream-root .report-quote{margin-top:6px;font-size:.82rem;line-height:1.35;color:#374151;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}",
        "#social-stream-root .report-label{display:flex;flex-direction:column;gap:4px;margin-top:8px;font-size:.75rem;font-weight:600;color:#6b7280;}",
        "#social-stream-root .report-reason,#social-stream-root .report-note{width:100%;box-sizing:border-box;font:inherit;font-size:.85rem;color:#111827;border:1px solid #d1d5db;border-radius:8px;padding:6px 8px;background:#fff;}",
        "#social-stream-root .report-note{min-height:64px;resize:vertical;margin-top:8px;}",
        "#social-stream-root .report-hint{min-height:1rem;color:#b45309;font-size:.75rem;margin-top:4px;}",
        "#social-stream-root .chat-notice{color:#b45309;font-size:.8rem;line-height:1.35;margin-bottom:6px;}",
        "#social-stream-root .card{padding:14px 0;border-top:1px solid #e5e7eb;}",
        "#social-stream-root .chat-filters{padding:8px 18px 0;}",
        "#social-stream-root .chat-filters .picks{grid-template-columns:1fr;margin-top:0;}",
        "#social-stream-root .person{display:flex;gap:10px;align-items:center;}",
        "#social-stream-root .person .identity{flex:1;min-width:0;}",
        "#social-stream-root .person-tools{margin-left:auto;display:flex;align-items:center;gap:2px;flex:none;}",
        "#social-stream-root .favourite{flex:none;background:none;border:0;padding:0 2px;cursor:pointer;font-size:1.2rem;line-height:1;color:#9ca3af;}",
        "#social-stream-root .favourite.is-on{color:#d97706;}",
        "#social-stream-root .group-invite{flex:none;display:inline-flex;align-items:center;background:none;border:0;padding:0 2px;cursor:pointer;color:#6b7280;}",
        "#social-stream-root .group-invite:hover{color:#111827;}",
        "#social-stream-root .report-flag{flex:none;display:inline-flex;align-items:center;background:none;border:0;padding:0 2px;cursor:pointer;color:#6b7280;}",
        "#social-stream-root .report-flag:hover{color:#111827;}",
        "#social-stream-root .group-box{margin:8px 18px 0;padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px;background:#f8fafc;}",
        "#social-stream-root .group-box-title{font-weight:650;font-size:.9rem;}",
        "#social-stream-root .group-name,#social-stream-root .group-pick{width:100%;box-sizing:border-box;font:inherit;font-size:.85rem;color:#111827;border:1px solid #d1d5db;border-radius:8px;padding:6px 8px;background:#fff;margin-top:6px;}",
        "#social-stream-root .group-hint{min-height:1rem;color:#b45309;font-size:.75rem;margin-top:4px;}",
        "#social-stream-root .group-box-actions{display:flex;gap:8px;margin-top:8px;}",
        "#social-stream-root .group-send,#social-stream-root .group-cancel{border-radius:999px;padding:4px 12px;font:inherit;font-weight:600;cursor:pointer;}",
        "#social-stream-root .group-send{background:#111827;color:#fff;border:0;}",
        "#social-stream-root .group-cancel{background:#fff;color:#111827;border:1px solid #d1d5db;}",
        "#social-stream-root .face{width:36px;height:36px;border-radius:50%;object-fit:cover;background:#dbeafe;color:#1d4ed8;display:flex;align-items:center;justify-content:center;font-weight:700;flex:none;}",
        "#social-stream-root .who{display:flex;align-items:center;gap:6px;min-width:0;font-weight:600;font-size:.92rem;}",
        "#social-stream-root .who .name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}",
        "#social-stream-root .social-score{flex:none;font-size:.68rem;font-weight:600;line-height:1.4;color:#6b7280;background:#f3f4f6;border-radius:999px;padding:1px 6px;}",
        "#social-stream-root .when{color:#6b7280;font-size:.78rem;margin-top:1px;}",
        "#social-stream-root .saying{margin:8px 0 0;font-size:.95rem;line-height:1.4;white-space:pre-wrap;word-break:break-word;}",
        "#social-stream-root .context{margin-top:10px;background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;}",
        "#social-stream-root .context-label{font-size:.72rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#6b7280;}",
        "#social-stream-root .context-head{display:flex;align-items:center;gap:8px;margin-top:6px;flex-wrap:wrap;}",
        "#social-stream-root .asset{font-weight:600;}",
        "#social-stream-root .logo{width:18px;height:18px;border-radius:50%;object-fit:cover;flex:none;}",
        "#social-stream-root .badge{font-size:.78rem;font-weight:700;border-radius:4px;padding:1px 6px;}",
        "#social-stream-root .coverage{margin-top:4px;font-size:.8rem;font-weight:600;}",
        "#social-stream-root .summary{margin:4px 0 0;color:#374151;font-size:.82rem;line-height:1.4;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}",
        "#social-stream-root .empty{color:#6b7280;padding:18px 0;font-size:.9rem;line-height:1.4;}",
        "#social-stream-root.is-dark .panel{background:var(--ang-social,#1c1f27);color:#fafafa;box-shadow:-12px 0 40px rgba(0,0,0,.45);}",
        "#social-stream-root.is-dark .width-grip::before{background:#6b7280;}",
        "#social-stream-root.is-dark .width-grip:hover::before,#social-stream-root.is-dark .width-grip.is-dragging::before{background:#e5e7eb;}",
        "#social-stream-root.is-dark .kicker,#social-stream-root.is-dark .count,#social-stream-root.is-dark .chars,#social-stream-root.is-dark .when,#social-stream-root.is-dark .empty,#social-stream-root.is-dark .picks label,#social-stream-root.is-dark .context-label,#social-stream-root.is-dark .replying{color:#9ca3af;}",
        "#social-stream-root.is-dark .social-score{color:#d1d5db;background:#31333f;}",
        "#social-stream-root.is-dark .finder input,#social-stream-root.is-dark select,#social-stream-root.is-dark .chat-box{background:#262730;color:#fafafa;border-color:#4b5563;color-scheme:dark;}",
        "#social-stream-root.is-dark .finder input::placeholder,#social-stream-root.is-dark .chat-box::placeholder{color:#9ca3af;}",
        "#social-stream-root.is-dark .close,#social-stream-root.is-dark .pin{background:#262730;color:#fafafa;}",
        "#social-stream-root.is-dark .pin.is-on{background:#f3f4f6;color:#111827;}",
        "#social-stream-root.is-dark .edge{background:#262730;color:#c5c8d0;border-color:#4b5563;}",
        "#social-stream-root.is-dark .edge:hover{background:#31333f;color:#ff4b4b;}",
        "#social-stream-root.is-dark .chips button,#social-stream-root.is-dark .faces button,#social-stream-root.is-dark .chat-actions button{background:#262730;border-color:#4b5563;color:#e5e7eb;}",
        "#social-stream-root.is-dark .chips button.is-on{background:#f3f4f6;border-color:#f3f4f6;color:#111827;}",
        "#social-stream-root.is-dark .composer{border-top-color:#31333f;}",
        "#social-stream-root.is-dark .post{background:#f3f4f6;color:#111827;}",
        "#social-stream-root.is-dark .chat-card,#social-stream-root.is-dark .card{border-top-color:#31333f;}",
        "#social-stream-root.is-dark .reply{border-left-color:#4b5563;}",
        "#social-stream-root.is-dark .chat-actions button.thumb-up{color:#4ade80;background:transparent;}",
        "#social-stream-root.is-dark .chat-actions button.thumb-down,#social-stream-root.is-dark .chat-actions button.delete-note{color:#f87171;background:transparent;}",
        "#social-stream-root.is-dark .chat-actions button.thumb-up.is-on{background:#14532d;border-color:#4ade80;color:#4ade80;}",
        "#social-stream-root.is-dark .chat-actions button.thumb-down.is-on{background:#7f1d1d;border-color:#f87171;color:#fca5a5;}",
        "#social-stream-root.is-dark .chat-actions button.delete-note{background:#262730;}",
        "#social-stream-root.is-dark .replying button{color:#93c5fd;}",
        "#social-stream-root.is-dark .context{background:#262730;border-color:#3d4452;}",
        "#social-stream-root.is-dark .summary{color:#d1d5db;}",
        "#social-stream-root.is-dark .face{background:#1e3a5f;color:#93c5fd;}",
        "#social-stream-root.is-dark .favourite{color:#6b7280;}",
        "#social-stream-root.is-dark .favourite.is-on{color:#fbbf24;}",
        "#social-stream-root.is-dark .group-invite{color:#9ca3af;}",
        "#social-stream-root.is-dark .group-invite:hover{color:#fafafa;}",
        "#social-stream-root.is-dark .report-flag{color:#9ca3af;}",
        "#social-stream-root.is-dark .report-flag:hover{color:#fafafa;}",
        "#social-stream-root.is-dark .group-box{background:#262730;border-color:#4b5563;}",
        "#social-stream-root.is-dark .group-name,#social-stream-root.is-dark .group-pick{background:#31333f;color:#fafafa;border-color:#4b5563;}",
        "#social-stream-root.is-dark .group-cancel{background:#31333f;color:#fafafa;border-color:#4b5563;}",
        "#social-stream-root.is-dark .group-hint,#social-stream-root.is-dark .report-hint{color:#fbbf24;}",
        "#social-stream-root.is-dark .chat-notice{color:#fbbf24;}",
        "#social-stream-root.is-dark .report-box{background:#262730;border-color:#4b5563;}",
        "#social-stream-root.is-dark .report-quote{color:#d1d5db;}",
        "#social-stream-root.is-dark .report-reason,#social-stream-root.is-dark .report-note{background:#31333f;color:#fafafa;border-color:#4b5563;}",
        "#social-stream-root .popout-btn{background:#f3f4f6;border:0;border-radius:999px;padding:6px 12px;font:inherit;font-weight:600;cursor:pointer;color:#111827;}",
        "#social-stream-root .tool{width:28px;height:28px;padding:0;display:inline-flex;align-items:center;justify-content:center;border-radius:.4rem;background:#fff;color:#111827;border:1px solid rgba(49,51,63,.28);cursor:pointer;}",
        "#social-stream-root .tool[hidden]{display:none;}",
        "#social-stream-root .tool:hover{border-color:#111827;}",
        "#social-stream-root .tool.is-on{background:#111827;color:#fff;border-color:#111827;}",
        "#social-stream-root .close,#social-stream-root .pin,#social-stream-root .popout-btn{width:28px;height:28px;padding:0;display:inline-flex;align-items:center;justify-content:center;}",
        "#social-stream-root .replying[hidden],#social-stream-root .chat-notice[hidden]{display:none;}",
        "#social-stream-root.is-dark .popout-btn{background:#262730;color:#fafafa;}",
        "#social-stream-root.is-dark .tool{background:#262730;color:#fafafa;border-color:#4b5563;}",
        "#social-stream-root.is-dark .tool:hover{border-color:#e5e7eb;}",
        "#social-stream-root.is-dark .tool.is-on{background:#fafafa;color:#111827;border-color:#fafafa;}",
        "#social-stream-root.is-popout .panel{left:0;right:0;width:100vw;box-shadow:none;transform:none;}",
        "#social-stream-root.is-popout .scrim,#social-stream-root.is-popout .edge,#social-stream-root.is-popout .close,#social-stream-root.is-popout .pin,#social-stream-root.is-popout .width-grip,#social-stream-root.is-popout .popout-btn{display:none !important;}",
        "#social-stream-root.is-popout.is-open{pointer-events:auto;}",
        "#social-stream-root.is-popout.is-side .panel{display:grid;grid-template-columns:1fr 16px 1fr;grid-template-rows:auto auto minmax(0,1fr);}",
        "#social-stream-root.is-popout.is-side .finder,#social-stream-root.is-popout.is-side .report-box{grid-column:1 / -1;}",
        "#social-stream-root.is-popout.is-side .stream-pane{grid-column:1;grid-row:3;min-width:0;}",
        "#social-stream-root.is-popout.is-side .chat-pane{grid-column:3;grid-row:3;min-width:0;}",
        "#social-stream-root.is-popout.is-side .splitter{grid-column:2;grid-row:3;height:auto;width:16px;cursor:col-resize;border-top:0;border-bottom:0;border-left:1px solid #4b5563;border-right:1px solid #4b5563;}",
        "#social-stream-root.is-popout.is-side .splitter::before{width:4px;height:64px;}",
        "#social-stream-root.is-popout.is-side.is-dragging,#social-stream-root.is-popout.is-side.is-dragging *{cursor:col-resize !important;}"
      ].join("");
      document.head.appendChild(style);
    }
    let root = document.getElementById("social-stream-root");
    if (root && root.dataset.layout !== "member") {
      root.remove();
      root = null;
    }
    if (!root) {
      if (window.socialStreamAbort) window.socialStreamAbort.abort();
      window.socialStreamAbort = new AbortController();
      const streamSignal = window.socialStreamAbort.signal;
      root = document.createElement("div");
      root.id = "social-stream-root";
      root.dataset.layout = "member";
      root.innerHTML = [
        "<div class='scrim'></div>",
        "<aside class='panel' role='dialog' aria-label='Social signals and chat'>",
        "<div class='width-grip' role='separator' aria-orientation='vertical' title='Drag to resize the panel'></div>",
        "<div class='finder'><input id='panel-search' type='search' placeholder='Search the stream and the chat' aria-label='Search the stream and the chat'></div>",
        "<div class='report-box' hidden>",
        "<div class='report-title'>Report this comment</div>",
        "<div class='report-quote'></div>",
        "<label class='report-label'>Reason<select class='report-reason' aria-label='Reason'>",
        "<option value='promotion'>Promoting an asset</option>",
        "<option value='advice'>Presented as financial advice</option>",
        "<option value='harassment'>Harassment or a personal attack</option>",
        "<option value='spam'>Spam</option>",
        "<option value='other'>Something else</option>",
        "</select></label>",
        "<textarea class='report-note' maxlength='500' placeholder='What should we look at? Add a note for Something else.'></textarea>",
        "<div class='report-hint'></div>",
        "<div class='group-box-actions'><button type='button' class='group-send report-send'>Send report</button><button type='button' class='group-cancel report-cancel'>Cancel</button></div>",
        "</div>",
        "<div class='stream-pane'>",
        "<header class='head'><div>",
        "<div class='kicker'>Social signals</div>",
        "<h2>Social signals stream</h2>",
        "</div><div class='head-actions'><button type='button' class='follow tool' hidden title='Follow the asset picked in the main tab' aria-label='Follow the asset picked in the main tab'><svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1'/><path d='M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.7l1-1'/></svg></button><button type='button' class='layout-btn tool' data-layout='stacked' hidden title='Stream above chat' aria-label='Stream above chat'><svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2'><rect x='2.4' y='2.4' width='19.2' height='19.2'/><path d='M2.4 12H21.6'/></svg></button><button type='button' class='layout-btn tool' data-layout='side' hidden title='Stream beside chat' aria-label='Stream beside chat'><svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2'><rect x='2.4' y='2.4' width='19.2' height='19.2'/><path d='M12 2.4V21.6'/></svg></button><button type='button' class='popout-btn' title='Open this panel in its own window' aria-label='Open this panel in its own window'><svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 4h6v6'/><path d='M20 4 10 14'/><path d='M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5'/></svg></button><button type='button' class='pin' title='Pin the panel' aria-label='Pin the panel'><svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M9 4h6l-1 6 3 3H7l3-3z'/><path d='M12 13v7'/></svg></button><button type='button' class='close' title='Close' aria-label='Close'><svg viewBox='0 0 24 24' width='15' height='15' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M6 6l12 12'/><path d='M18 6 6 18'/></svg></button></div></header>",
        "<div class='filters'><div class='chips'>",
        "<button type='button' data-side=''>All</button>",
        "<button type='button' data-side='positive'>Positive</button>",
        "<button type='button' data-side='negative'>Negative</button>",
        "<button type='button' data-side='mixed'>Mixed</button>",
        "</div><div class='picks'>",
        "<label>Asset<select id='stream-asset'></select></label>",
        "<label>Person<select id='stream-person'></select></label>",
        "</div></div>",
        "<div class='count'></div>",
        "<div class='group-box' hidden>",
        "<div class='group-box-title'></div>",
        "<input class='group-name' maxlength='40' placeholder='New group name' aria-label='New group name'>",
        "<select class='group-pick' aria-label='Group you lead'></select>",
        "<div class='group-hint'></div>",
        "<div class='group-box-actions'><button type='button' class='group-send'>Invite</button><button type='button' class='group-cancel'>Cancel</button></div>",
        "</div>",
        "<div class='list'></div></div>",
        "<div class='splitter' role='separator' aria-orientation='horizontal' title='Drag to resize the stream and the chat'></div>",
        "<div class='chat-pane'>",
        "<header class='chat-head'><div class='kicker'>Chat</div>",
        "<h2>General chat</h2>",
        "<div class='chat-filters'><div class='picks'>",
        "<label>Person<select id='chat-person'></select></label>",
        "</div></div></header>",
        "<div class='chat-list'></div>",
        "<form class='composer'>",
        "<div class='replying' hidden><span class='replying-label'></span><button type='button' class='reply-cancel'>Cancel</button></div>",
        "<div class='chat-notice' hidden></div>",
        "<textarea class='chat-box' maxlength='160' placeholder='Write a comment'></textarea>",
        "<div class='faces'></div>",
        "<div class='composer-row'><span class='chars'>0/160</span><button type='submit' class='post'>Post comment</button></div>",
        "</form></div></aside>",
        "<button type='button' class='edge' aria-label='Open social signals and chat' aria-expanded='false'>",
        "<svg viewBox='0 0 24 24' width='22' height='22' aria-hidden='true'>",
        "<path d='M15.2 6.2 9.4 12l5.8 5.8' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/>",
        "<path d='M10.2 6.2 4.4 12l5.8 5.8' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/>",
        "</svg></button>"
      ].join("");
      document.body.appendChild(root);
      const font = getComputedStyle(document.body).fontFamily;
      if (font) root.querySelector(".panel").style.fontFamily = font;
      const closeStream = () => {
        window.socialStreamState.open = false;
        window.renderSocialStream();
      };
      root.querySelector(".scrim").addEventListener("click", closeStream);
      root.querySelector(".close").addEventListener("click", closeStream);
      const reportPanel = () => {
        if (!window.socialStreamReport) return;
        window.socialStreamReport("panel", JSON.stringify({
          width: Number(window.socialPanelWidth) || 420,
          split: Number(window.socialPanelSplit) || 0.5,
          pinned: !!(window.socialStreamState && window.socialStreamState.pinned),
          layout: (window.socialStreamState && window.socialStreamState.layout) || "stacked"
        }));
      };
      root.querySelector(".pin").addEventListener("click", () => {
        window.socialStreamState.pinned = !window.socialStreamState.pinned;
        window.renderSocialStream();
        reportPanel();
      });
      root.querySelector(".edge").addEventListener("click", () => {
        window.socialStreamState.open = !window.socialStreamState.open;
        window.renderSocialStream();
        if (window.socialStreamState.open) {
          const closeButton = root.querySelector(".close");
          if (closeButton) closeButton.focus();
        }
      });
      root.querySelectorAll("[data-side]").forEach((button) => {
        button.addEventListener("click", () => {
          window.socialStreamState.side = button.getAttribute("data-side") || "";
          window.renderSocialStream();
        });
      });
      root.querySelector("#stream-asset").addEventListener("change", (event) => {
        const choice = event.target.value;
        window.socialStreamState.follow = false;
        window.socialStreamState.asset = choice;
        window.renderSocialStream();
        const reported = { "": "all", watchlist: "watchlist", crypto: "crypto", stock: "stock" };
        if (Object.prototype.hasOwnProperty.call(reported, choice) && window.socialStreamReport) {
          window.socialStreamReport("asset", reported[choice]);
        }
      });
      root.querySelector("#stream-person").addEventListener("change", (event) => {
        window.socialStreamState.person = event.target.value;
        window.renderSocialStream();
      });
      root.querySelector("#chat-person").addEventListener("change", (event) => {
        window.socialStreamState.chatPerson = event.target.value;
        window.renderSocialStream();
      });
      const sendGroupInvite = () => {
        const invite = (window.socialStreamState || {}).groupFor;
        if (!invite || !window.socialStreamReport) return;
        const nameBox = root.querySelector(".group-name");
        const pick = root.querySelector(".group-pick");
        const hint = root.querySelector(".group-hint");
        const name = nameBox ? nameBox.value.replace(/\\s+/g, " ").trim() : "";
        const group = pick ? pick.value : "";
        if (!name && !group) {
          if (hint) hint.textContent = "Enter a name or choose a group.";
          return;
        }
        if (hint) hint.textContent = "";
        window.socialStreamReport("group", JSON.stringify({
          n: Date.now(),
          user: invite.id,
          name: name,
          group: name ? 0 : Number(group)
        }));
      };
      const groupBox = root.querySelector(".group-box");
      const closeGroupBox = () => {
        window.socialStreamState.groupFor = null;
        const hint = groupBox.querySelector(".group-hint");
        if (hint) hint.textContent = "";
        window.renderSocialStream();
      };
      groupBox.querySelector(".group-send").addEventListener("click", sendGroupInvite);
      groupBox.querySelector(".group-cancel").addEventListener("click", closeGroupBox);
      root.querySelector(".group-name").addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          sendGroupInvite();
        }
      });
      const sendReport = root.querySelector(".report-send");
      const cancelReport = root.querySelector(".report-cancel");
      if (sendReport) sendReport.addEventListener("click", () => submitReport(root));
      if (cancelReport) {
        cancelReport.addEventListener("click", () => {
          window.socialStreamState.report = null;
          paintReport(root);
        });
      }
      const finder = root.querySelector("#panel-search");
      if (finder) {
        finder.addEventListener("input", () => {
          window.socialStreamState.query = finder.value;
          window.renderSocialStream();
        });
      }
      document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape" || !window.socialStreamState.open) return;
        const sheet = root.querySelector(".panel");
        if (window.socialStreamState.pinned && sheet && !sheet.contains(document.activeElement)) return;
        const box = root.querySelector(".chat-box");
        if (box && document.activeElement === box && window.socialStreamState.reply) {
          window.socialStreamState.reply = null;
          paintReply(root);
          return;
        }
        if (window.socialStreamState.report) {
          window.socialStreamState.report = null;
          paintReport(root);
          return;
        }
        closeStream();
      }, {signal: streamSignal});
      const applyWidth = (px) => {
        const max = Math.max(320, Math.min(900, window.innerWidth - 36));
        const next = Math.min(max, Math.max(320, Math.round(px)));
        root.style.setProperty("--social-width", next + "px");
        window.socialPanelWidth = next;
      };
      applyWidth(Number(window.socialPanelWidth) >= 320 ? Number(window.socialPanelWidth) : 420);
      const grip = root.querySelector(".width-grip");
      if (grip) {
        grip.addEventListener("pointerdown", (event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          event.stopPropagation();
          root.classList.add("is-width-dragging");
          grip.classList.add("is-dragging");
          try { grip.setPointerCapture(event.pointerId); } catch (error) {}
          const move = (moveEvent) => applyWidth(window.innerWidth - moveEvent.clientX);
          const stop = (endEvent) => {
            root.classList.remove("is-width-dragging");
            grip.classList.remove("is-dragging");
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", stop);
            window.removeEventListener("pointercancel", stop);
            try { grip.releasePointerCapture(endEvent.pointerId); } catch (error) {}
            reportPanel();
          };
          window.addEventListener("pointermove", move);
          window.addEventListener("pointerup", stop);
          window.addEventListener("pointercancel", stop);
          move(event);
        });
      }
      const splitter = root.querySelector(".splitter");
      let heldRatio = 0.5;
      const applySplit = (streamHeight) => {
        const panelBox = root.querySelector(".panel");
        const streamPane = root.querySelector(".stream-pane");
        const chatPane = root.querySelector(".chat-pane");
        if (!panelBox || !streamPane || !chatPane || !splitter) return;
        panelBox.style.gridTemplateColumns = "";
        const finderBox = root.querySelector(".finder");
        const available = panelBox.clientHeight - splitter.offsetHeight - (finderBox ? finderBox.offsetHeight : 0);
        if (available < 80) return;
        let streamFloor = 120;
        let chatFloor = 150;
        if (streamFloor + chatFloor > available) {
          streamFloor = Math.max(72, Math.floor(available * 0.4));
          chatFloor = available - streamFloor;
        }
        const next = Math.min(available - chatFloor, Math.max(streamFloor, streamHeight));
        streamPane.style.flex = "none";
        streamPane.style.height = next + "px";
        chatPane.style.flex = "1 1 auto";
        chatPane.style.height = "auto";
        heldRatio = next / available;
        window.socialPanelSplit = heldRatio;
      };
      let wideRatio = 0.5;
      const applyWide = (ratio) => {
        const panelBox = root.querySelector(".panel");
        const streamPane = root.querySelector(".stream-pane");
        const chatPane = root.querySelector(".chat-pane");
        if (!panelBox || !streamPane || !chatPane) return;
        const next = Math.min(0.8, Math.max(0.2, Number(ratio) || 0.5));
        streamPane.style.flex = "";
        streamPane.style.height = "";
        chatPane.style.flex = "";
        chatPane.style.height = "";
        panelBox.style.gridTemplateColumns = next + "fr 16px " + (1 - next) + "fr";
        wideRatio = next;
      };
      if (splitter) {
        splitter.addEventListener("pointerdown", (event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          root.classList.add("is-dragging");
          splitter.classList.add("is-dragging");
          try { splitter.setPointerCapture(event.pointerId); } catch (error) {}
          const move = (moveEvent) => {
            const panelBox = root.querySelector(".panel");
            if (!panelBox) return;
            if (root.classList.contains("is-side")) {
              const area = panelBox.getBoundingClientRect();
              applyWide((moveEvent.clientX - area.left) / Math.max(1, area.width - 16));
              return;
            }
            applySplit(moveEvent.clientY - panelBox.getBoundingClientRect().top);
          };
          const stop = (endEvent) => {
            root.classList.remove("is-dragging");
            splitter.classList.remove("is-dragging");
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", stop);
            window.removeEventListener("pointercancel", stop);
            try { splitter.releasePointerCapture(endEvent.pointerId); } catch (error) {}
            reportPanel();
          };
          window.addEventListener("pointermove", move);
          window.addEventListener("pointerup", stop);
          window.addEventListener("pointercancel", stop);
          move(event);
        });
      }
      const composer = root.querySelector(".composer");
      const box = root.querySelector(".chat-box");
      if (box) box.addEventListener("input", () => updateChatCount(root));
      if (composer) {
        composer.addEventListener("submit", (event) => {
          event.preventDefault();
          submitChat(root);
        });
      }
      if (box) {
        box.addEventListener("keydown", (event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submitChat(root);
          }
        });
      }
      const cancelReply = root.querySelector(".reply-cancel");
      if (cancelReply) {
        cancelReply.addEventListener("click", () => {
          window.socialStreamState.reply = null;
          paintReply(root);
        });
      }
      const storedRatio = Number(window.socialPanelSplit);
      if (storedRatio > 0.08 && storedRatio < 0.92) heldRatio = storedRatio;
      const panelBox = root.querySelector(".panel");
      const fitSplit = () => {
        if (root.classList.contains("is-side")) {
          applyWide(wideRatio);
          return;
        }
        const finderBox = root.querySelector(".finder");
        const chrome = (splitter ? splitter.offsetHeight : 0) + (finderBox ? finderBox.offsetHeight : 0);
        const height = panelBox ? panelBox.clientHeight - chrome : 0;
        applySplit(height ? heldRatio * height : 0);
      };
      fitSplit();
      window.socialRefit = fitSplit;
      root.querySelectorAll(".layout-btn").forEach((layoutButton) => {
        layoutButton.addEventListener("click", () => {
          const wanted = layoutButton.getAttribute("data-layout") === "side" ? "side" : "stacked";
          if (window.socialStreamState.layout === wanted) return;
          window.socialStreamState.layout = wanted;
          window.socialPanelLayout = wanted;
          window.renderSocialStream();
          fitSplit();
          reportPanel();
        });
      });
      const followButton = root.querySelector(".follow");
      if (followButton) {
        followButton.addEventListener("click", () => {
          const state = window.socialStreamState;
          state.follow = !state.follow;
          if (state.follow && state.linked && state.linked.key) state.asset = state.linked.key;
          window.renderSocialStream();
        });
      }
      const popButton = root.querySelector(".popout-btn");
      if (popButton) {
        popButton.addEventListener("click", () => {
          const address = window.location.origin + window.location.pathname + "?view=social";
          const opts = window.socialPopoutOpts || { asWindow: true, fold: true };
          const opened = opts.asWindow
            ? window.open(address, "ang_popout_social", "popup=yes,width=980,height=820")
            : null;
          if (!opened) {
            window.open(address, "_blank");
          }
          // Put the side panel away while the stream lives in its own window.
          if (opts.fold) {
            window.socialStreamState.open = false;
            window.renderSocialStream();
          }
        });
      }
      window.addEventListener("resize", () => {
        applyWidth(Number(window.socialPanelWidth) >= 320 ? Number(window.socialPanelWidth) : 420);
        if (window.socialApplyLayout) window.socialApplyLayout(root);
        const wideEnough = window.innerWidth >= 760;
        root.querySelectorAll(".layout-btn").forEach((button) => {
          button.hidden = !window.socialPopout || !wideEnough;
        });
        fitSplit();
      }, {signal: streamSignal});
    }
    window.openSocialStream = (assetKey) => {
      window.socialStreamState.open = true;
      window.socialStreamState.asset = assetKey || "";
      window.socialStreamState.side = "";
      window.socialStreamState.person = "";
      window.socialStreamState.query = "";
      window.renderSocialStream();
      const closeButton = document.querySelector("#social-stream-root .close");
      if (closeButton) closeButton.focus();
    };
    window.renderSocialStream = () => {
      const panel = document.getElementById("social-stream-root");
      if (!panel) return;
      const state = window.socialStreamState;
      panel.classList.toggle("is-open", !!state.open);
      panel.classList.toggle("is-pinned", !!state.pinned);
      if (window.socialPopout) {
        state.open = true;
        state.pinned = false;
        panel.classList.add("is-open");
        panel.classList.remove("is-pinned");
      }
      window.socialApplyLayout(panel);
      panel.querySelectorAll(".layout-btn").forEach((button) => {
        const mine = (button.getAttribute("data-layout") || "") === state.layout;
        button.hidden = !window.socialPopout || window.innerWidth < 760;
        button.classList.toggle("is-on", mine);
        button.setAttribute("aria-pressed", mine ? "true" : "false");
      });
      const followBtn = panel.querySelector(".follow");
      if (followBtn) {
        followBtn.hidden = !window.socialPopout;
        followBtn.classList.toggle("is-on", !!state.follow);
        followBtn.setAttribute("aria-pressed", state.follow ? "true" : "false");
        followBtn.title = state.follow
          ? "Following the asset picked in your main tab. Press to stop."
          : "Not following. Press to follow the asset picked in your main tab.";
        followBtn.setAttribute("aria-label", followBtn.title);
      }
      const app = document.querySelector(".stApp");
      const parts = app ? getComputedStyle(app).backgroundColor.match(/\\d+/g) : null;
      const shade = parts
        ? (0.299 * Number(parts[0])) + (0.587 * Number(parts[1])) + (0.114 * Number(parts[2]))
        : 255;
      panel.classList.toggle("is-dark", shade < 140);
      const main = document.querySelector("[data-testid='stMain']");
      if (main) main.style.paddingRight = state.open && state.pinned ? "min(420px, 100vw)" : "";
      const pin = panel.querySelector(".pin");
      if (pin) {
        pin.classList.toggle("is-on", !!state.pinned);
        pin.title = state.pinned ? "Unpin the panel" : "Pin the panel";
        pin.setAttribute("aria-label", pin.title);
        pin.setAttribute("aria-pressed", state.pinned ? "true" : "false");
      }
      const edge = panel.querySelector(".edge");
      if (edge) {
        const edgeLabel = state.open ? "Close social signals and chat" : "Open social signals and chat";
        edge.setAttribute("aria-label", edgeLabel);
        edge.setAttribute("title", edgeLabel);
        edge.setAttribute("aria-expanded", state.open ? "true" : "false");
      }
      const items = window.socialStreamItems || [];
      const assets = [];
      const seenAssets = {};
      const marketKeys = { "Mood|crypto": true, "Mood|stock": true };
      items.forEach((item) => {
        if (item.key && !seenAssets[item.key] && !marketKeys[item.key]) {
          seenAssets[item.key] = true;
          assets.push([item.key, item.asset || item.key]);
        }
      });
      const people = collectPeople(items);
      const seenPeople = {};
      people.forEach((name) => { seenPeople[name] = true; });
      const streamScores = personScores(items);
      const chatPeople = collectPeople(window.socialChat || []);
      const seenChatPeople = {};
      chatPeople.forEach((name) => { seenChatPeople[name] = true; });
      const chatScores = personScores(window.socialChat || []);
      if (state.linked && state.linked.key === state.asset && !seenAssets[state.asset]) {
        seenAssets[state.asset] = true;
        assets.push([state.linked.key, state.linked.label]);
      }
      assets.sort((a, b) => String(a[1]).localeCompare(String(b[1])));
      people.sort((a, b) => a.localeCompare(b));
      fillStreamSelect(
        panel.querySelector("#stream-asset"),
        "All Assets & Sentiments",
        assets,
        state.asset,
        [
          ["watchlist", "My watchlists"],
          ["crypto", "My Crypto Watchlist"],
          ["stock", "My Equities Watchlist"],
          ["Mood|crypto", "Crypto market"],
          ["Mood|stock", "Stock market"]
        ],
        true
      );
      const personChoices = [["me", "Me"]].concat(groupChoices(), [["favourites", "Favourites"]]);
      fillStreamSelect(
        panel.querySelector("#stream-person"),
        "All people",
        people.map((name) => [name, name + "  ✦ " + (streamScores[name] || 0)]),
        state.person,
        personChoices
      );
      fillStreamSelect(
        panel.querySelector("#chat-person"),
        "All people",
        chatPeople.map((name) => [name, name + "  ✦ " + (chatScores[name] || 0)]),
        state.chatPerson || "",
        personChoices
      );
      const streamScopes = {
        watchlist: true, crypto: true, stock: true, "Mood|crypto": true, "Mood|stock": true
      };
      if (!streamScopes[state.asset] && !seenAssets[state.asset]) state.asset = "";
      const keptPeople = { favourites: true, me: true };
      (window.socialGroups || []).forEach((group) => { keptPeople["group:" + group.id] = true; });
      if (!keptPeople[state.person] && !seenPeople[state.person]) state.person = "";
      if (!keptPeople[state.chatPerson || ""] && !seenChatPeople[state.chatPerson || ""]) state.chatPerson = "";
      panel.querySelector("#stream-asset").value = state.asset;
      panel.querySelector("#stream-person").value = state.person;
      const chatPerson = panel.querySelector("#chat-person");
      if (chatPerson) chatPerson.value = state.chatPerson || "";
      const finder = panel.querySelector("#panel-search");
      if (finder && document.activeElement !== finder) finder.value = state.query || "";
      panel.querySelectorAll("[data-side]").forEach((button) => {
        button.classList.toggle("is-on", (button.getAttribute("data-side") || "") === state.side);
      });
      const shown = items.filter((item) => {
        if (state.asset === "watchlist") {
          if (!item.watchlist) return false;
        } else if (state.asset === "crypto" || state.asset === "stock") {
          if (item.list !== state.asset) return false;
        } else if (state.asset && item.key !== state.asset) return false;
        if (!matchesPerson(item, state.person)) return false;
        if (!matchesQuery(item, state.query)) return false;
        if (state.side && item.side !== state.side) return false;
        return true;
      });
      const count = panel.querySelector(".count");
      count.textContent = shown.length === 1 ? "1 comment" : shown.length + " comments";
      paintGroupBox(panel);
      paintReport(panel);
      const list = panel.querySelector(".list");
      if (list) {
        const keptScroll = list.scrollTop;
        list.replaceChildren();
        if (!shown.length) {
          const empty = document.createElement("div");
          empty.className = "empty";
          empty.textContent = state.person === "me"
            ? "No comments from you yet."
            : String(state.person || "").indexOf("group:") === 0
            ? "No comments from that group yet."
            : state.person === "favourites" && !favouriteSet().size
            ? "No favourites yet. Press the star beside a name."
            : items.length
            ? "No comments match these filters."
            : "No comments yet. Each one stays for 12 hours after it is posted.";
          list.appendChild(empty);
        } else {
          shown.forEach((item) => list.appendChild(streamCard(item)));
        }
        list.scrollTop = keptScroll;
      }
      renderChat(panel);
    };
  }

  function reportChat(action) {
    if (!window.socialStreamReport) return;
    window.socialStreamReport("chat", JSON.stringify({
      n: Date.now(),
      action: action.action,
      text: action.text || "",
      parent: action.parent || 0,
      message: action.message || 0,
      vote: action.vote || 0
    }));
  }

  function reportSignal(action) {
    if (!window.socialStreamReport) return;
    window.socialStreamReport("signal", JSON.stringify({
      n: Date.now(),
      action: action.action,
      text: action.text || "",
      parent: action.parent || 0,
      message: action.message || 0,
      vote: action.vote || 0,
      kind: action.kind || "comment"
    }));
  }

  function updateChatCount(panel) {
    const box = panel.querySelector(".chat-box");
    const chars = panel.querySelector(".chars");
    const post = panel.querySelector(".post");
    if (!box || !chars || !post) return;
    const limit = window.socialChatLimit || 160;
    box.maxLength = limit;
    chars.textContent = box.value.length + "/" + limit;
    post.disabled = !box.value.trim();
  }

  function addChatFace(panel, face) {
    const box = panel.querySelector(".chat-box");
    if (!box) return;
    const limit = window.socialChatLimit || 160;
    const current = box.value;
    const gap = current && !/\\s$/.test(current) ? " " : "";
    const next = current + gap + face;
    if (next.length <= limit) box.value = next;
    updateChatCount(panel);
    box.focus();
  }

  function paintReport(panel) {
    const box = panel && panel.querySelector(".report-box");
    if (!box) return;
    const report = (window.socialStreamState || {}).report;
    box.hidden = !report;
    if (!report) return;
    const quote = box.querySelector(".report-quote");
    const text = String(report.text || "").replace(/\\s+/g, " ").trim();
    const where = report.place === "chat" ? "General chat" : "Social signals";
    const asset = report.asset ? " on " + report.asset : "";
    if (quote) quote.textContent = where + asset + " · " + report.name + ": " + text;
    const hint = box.querySelector(".report-hint");
    const notice = String(window.socialChatNotice || "");
    if (hint && notice.indexOf("Report") === 0 && notice.indexOf("Report sent") !== 0) {
      hint.textContent = notice;
    } else if (hint && !hint.textContent) {
      hint.textContent = "This follows the socials policy in About. It is not shown on the stream.";
    }
  }

  function submitReport(panel) {
    const report = (window.socialStreamState || {}).report;
    if (!report || !window.socialStreamReport) return;
    const reasonBox = panel.querySelector(".report-reason");
    const noteBox = panel.querySelector(".report-note");
    const hint = panel.querySelector(".report-hint");
    const reason = reasonBox ? reasonBox.value : "";
    const note = noteBox ? noteBox.value.replace(/\\s+/g, " ").trim() : "";
    if (reason === "other" && note.length < 4) {
      if (hint) hint.textContent = "Add a few words for Something else.";
      return;
    }
    if (hint) hint.textContent = "Sending the report.";
    window.socialStreamReport("report", JSON.stringify({
      n: Date.now(),
      place: report.place,
      message: report.id,
      kind: report.kind,
      reason: reason,
      note: note,
      asset: report.asset || ""
    }));
  }

  function reportButton(item, place, kind) {
    if (item.mine || item.pending || !(Number(item.id) > 0)) return null;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "report-flag";
    button.innerHTML = "<svg width='16' height='16' viewBox='0 0 16 16' aria-hidden='true'><path d='M3.2 1.8h1.1v12.4H3.2z' fill='currentColor'/><path d='M4.3 2.2h8l-1.7 2.5 1.7 2.5H4.3z' fill='currentColor'/></svg>";
    button.title = "Report";
    button.setAttribute("aria-label", "Report");
    button.addEventListener("click", () => {
      window.socialStreamState.reply = null;
      window.socialStreamState.report = {
        place: place,
        id: Number(item.id),
        kind: kind,
        name: String(item.name || "Member"),
        text: String(item.text || ""),
        asset: String(item.asset || "")
      };
      const panel = document.getElementById("social-stream-root");
      const noteBox = panel && panel.querySelector("textarea.report-note");
      const hint = panel && panel.querySelector(".report-hint");
      if (noteBox) noteBox.value = "";
      if (hint) hint.textContent = "";
      paintReply(panel);
      paintReport(panel);
      if (noteBox) noteBox.focus();
    });
    return button;
  }

  function paintReply(panel) {
    const row = panel.querySelector(".replying");
    const label = panel.querySelector(".replying-label");
    const reply = (window.socialStreamState || {}).reply;
    if (!row || !label) return;
    row.hidden = !reply;
    label.replaceChildren();
    if (reply) {
      label.append("Replying to " + reply.name + " ");
      label.appendChild(socialMark(reply.social));
    }
    const composer = panel.querySelector(".composer");
    if (composer) composer.hidden = window.socialChatReady === false && !(reply && reply.kind === "signal");
  }

  function submitChat(panel) {
    const box = panel.querySelector(".chat-box");
    if (!box) return;
    const text = box.value.replace(/\\s+/g, " ").trim();
    if (!text) return;
    const reply = (window.socialStreamState || {}).reply;
    const parent = reply && reply.id ? reply.id : 0;
    if (reply && reply.kind === "signal") {
      const note = {
        id: "local-" + Date.now(),
        user: (window.socialMe || {}).id || "",
        name: (window.socialMe || {}).name || "You",
        social: Math.max(0, Number((window.socialMe || {}).social) || 0),
        avatar: (window.socialMe || {}).avatar || "",
        text: text,
        at: new Date().toISOString(),
        mine: true,
        up: 0,
        down: 0,
        vote: 0,
        pending: true
      };
      const host = (window.socialStreamItems || []).find((item) => item.id === parent);
      if (host) host.replies = (host.replies || []).concat([note]);
      box.value = "";
      window.socialStreamState.reply = null;
      if (window.renderSocialStream) window.renderSocialStream();
      reportSignal({ action: "post", text: text, parent: parent });
      return;
    }
    const note = {
      id: "local-" + Date.now(),
      user: (window.socialMe || {}).id || "",
      name: (window.socialMe || {}).name || "You",
      social: Math.max(0, Number((window.socialMe || {}).social) || 0),
      avatar: (window.socialMe || {}).avatar || "",
      text: text,
      at: new Date().toISOString(),
      mine: true,
      up: 0,
      down: 0,
      vote: 0,
      pending: true,
      replies: []
    };
    const threads = Array.isArray(window.socialChat) ? window.socialChat.slice() : [];
    if (parent) {
      const host = threads.find((item) => item.id === parent);
      if (host) host.replies = (host.replies || []).concat([note]);
      else threads.unshift(note);
    } else {
      threads.unshift(note);
    }
    window.socialChat = threads;
    box.value = "";
    if (window.socialStreamState) window.socialStreamState.reply = null;
    renderChat(panel);
    reportChat({ action: "post", text: text, parent: parent });
  }

  function dropMessage(list, messageId) {
    return (list || []).filter((item) => item.id !== messageId).map((item) => {
      item.replies = (item.replies || []).filter((reply) => reply.id !== messageId);
      return item;
    });
  }

  function deleteNoteButton(prompt, onDelete) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "delete-note";
    button.textContent = "🗑️";
    button.title = "Delete";
    button.setAttribute("aria-label", "Delete");
    button.addEventListener("click", () => {
      if (window.confirm(prompt)) onDelete();
    });
    return button;
  }

  function thumbButton(direction, count, selected) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = direction === 1 ? "thumb-up" : "thumb-down";
    button.classList.toggle("is-on", !!selected);
    const mark = document.createElement("span");
    mark.textContent = direction === 1 ? "👍" : "👎";
    const number = Math.max(0, Number(count) || 0);
    const total = document.createElement("span");
    total.textContent = number > 100 ? ">100" : String(number);
    if (number > 100) button.title = String(number);
    button.append(mark, total);
    return button;
  }

  function chatVoteButton(item, direction) {
    const count = direction === 1 ? item.up : item.down;
    const button = thumbButton(direction, count, item.vote === direction);
    button.addEventListener("click", () => {
      const next = item.vote === direction ? 0 : direction;
      if (item.vote === 1) item.up = Math.max(0, (Number(item.up) || 0) - 1);
      if (item.vote === -1) item.down = Math.max(0, (Number(item.down) || 0) - 1);
      item.vote = next;
      if (next === 1) item.up = (Number(item.up) || 0) + 1;
      if (next === -1) item.down = (Number(item.down) || 0) + 1;
      const panel = document.getElementById("social-stream-root");
      if (panel) renderChat(panel);
      reportChat({ action: "vote", message: item.id, vote: next });
    });
    return button;
  }

  function groupChoices() {
    const groups = (window.socialGroups || []).slice().sort((a, b) => {
      return String(a.name || "").localeCompare(String(b.name || ""));
    });
    const counts = {};
    groups.forEach((group) => {
      const label = group.name || "Group";
      counts[label] = (counts[label] || 0) + 1;
    });
    return groups.map((group) => {
      let label = group.name || "Group";
      if (counts[label] > 1 && !group.lead && group.leader) label = label + " (" + group.leader + ")";
      return ["group:" + group.id, label + " (group)"];
    });
  }

  function paintGroupBox(panel) {
    const box = panel.querySelector(".group-box");
    if (!box) return;
    const invite = (window.socialStreamState || {}).groupFor;
    box.hidden = !invite;
    if (!invite) return;
    const title = box.querySelector(".group-box-title");
    if (title) title.textContent = "Invite " + invite.name + " to a group";
    const switched = box.dataset.user !== String(invite.id);
    if (switched) {
      box.dataset.user = String(invite.id);
      const nameBox = box.querySelector(".group-name");
      const hint = box.querySelector(".group-hint");
      if (nameBox) nameBox.value = "";
      if (hint) hint.textContent = "";
    }
    const memberWarning = "They are already in that group.";
    if (String(window.socialChatNotice || "") === memberWarning) {
      const hint = box.querySelector(".group-hint");
      if (hint) hint.textContent = memberWarning;
      if (box.dataset.closing !== "1") {
        box.dataset.closing = "1";
        setTimeout(() => {
          box.dataset.closing = "";
          if (window.socialStreamState) window.socialStreamState.groupFor = null;
          if (window.socialChatNotice === memberWarning) window.socialChatNotice = "";
          if (window.renderSocialStream) window.renderSocialStream();
        }, 1600);
      }
    }
    const select = box.querySelector(".group-pick");
    if (!select) return;
    const current = switched ? "" : select.value;
    select.replaceChildren();
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "Or choose a group you lead";
    select.appendChild(blank);
    (window.socialGroups || []).filter((group) => group.lead).forEach((group) => {
      const option = document.createElement("option");
      option.value = String(group.id);
      option.textContent = group.name || "Group";
      select.appendChild(option);
    });
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  }

  function groupButton(item) {
    const id = String(item.user || "");
    const mine = String((window.socialMe || {}).id || "");
    if (!id || item.mine || id === mine) return null;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "group-invite";
    button.innerHTML = "<svg width='16' height='16' viewBox='0 0 16 16' aria-hidden='true'><circle cx='6' cy='5' r='2' fill='currentColor'/><circle cx='11' cy='5.5' r='1.6' fill='currentColor'/><path d='M1.8 13.2c.6-2.2 2.1-3.3 4.2-3.3s3.6 1.1 4.2 3.3' fill='currentColor'/><path d='M9.2 13.2c.3-1.2 1.1-2 2.3-2 1.1 0 1.9.7 2.3 2' fill='currentColor'/></svg>";
    button.title = "Invite to a group";
    button.setAttribute("aria-label", button.title);
    button.addEventListener("click", () => {
      window.socialStreamState.groupFor = { id: id, name: String(item.name || "Member") };
      const panel = document.getElementById("social-stream-root");
      if (window.renderSocialStream) window.renderSocialStream();
      const nameBox = panel && panel.querySelector(".group-name");
      if (nameBox) nameBox.focus();
    });
    return button;
  }

  function favouriteSet() {
    return new Set((window.socialFavourites || []).map((id) => String(id)));
  }

  function toggleFavourite(userId) {
    const id = String(userId || "");
    const mine = String((window.socialMe || {}).id || "");
    if (!id || id === mine) return;
    const current = (window.socialFavourites || []).map(String);
    const on = current.indexOf(id) === -1;
    window.socialFavourites = on ? current.concat([id]) : current.filter((item) => item !== id);
    if (window.renderSocialStream) window.renderSocialStream();
    if (window.__angstromSetFavourite) {
      window.__angstromSetFavourite("picked", JSON.stringify({ n: Date.now(), user: id, on: on }));
    }
  }

  function favouriteButton(item) {
    const id = String(item.user || "");
    const mine = String((window.socialMe || {}).id || "");
    if (!id || item.mine || id === mine) return null;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "favourite";
    const on = favouriteSet().has(id);
    button.classList.toggle("is-on", on);
    button.textContent = on ? "★" : "☆";
    button.title = on ? "Remove from favourites" : "Add to favourites";
    button.setAttribute("aria-label", button.title);
    button.addEventListener("click", () => toggleFavourite(id));
    return button;
  }

  function socialMark(score) {
    const points = Math.max(0, Number(score) || 0);
    const mark = document.createElement("span");
    mark.className = "social-score";
    mark.textContent = "✦ " + points;
    mark.title = "Social score " + points;
    return mark;
  }

  function personRow(item, place, kind) {
    const person = document.createElement("div");
    person.className = "person";
    const name = String(item.name || "Member");
    person.appendChild(streamFace(name, item.avatar));
    const identity = document.createElement("div");
    identity.className = "identity";
    const who = document.createElement("div");
    who.className = "who";
    const label = document.createElement("span");
    label.className = "name";
    label.textContent = name;
    who.appendChild(label);
    who.appendChild(socialMark(item.social));
    const when = document.createElement("div");
    when.className = "when";
    const parsedAt = new Date(item.at);
    when.textContent = Number.isNaN(parsedAt.getTime()) ? "" : parsedAt.toLocaleString(undefined, {
      month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit"
    });
    identity.appendChild(who);
    identity.appendChild(when);
    person.appendChild(identity);
    const tools = document.createElement("div");
    tools.className = "person-tools";
    const flag = reportButton(item, place, kind);
    if (flag) tools.appendChild(flag);
    const group = groupButton(item);
    if (group) tools.appendChild(group);
    const star = favouriteButton(item);
    if (star) tools.appendChild(star);
    if (tools.childElementCount) person.appendChild(tools);
    return person;
  }

  function personScores(rows) {
    const scores = {};
    const visit = (item) => {
      const person = item.name || "Member";
      const points = Math.max(0, Number(item.social) || 0);
      if (scores[person] === undefined || points > scores[person]) scores[person] = points;
      (item.replies || []).forEach(visit);
    };
    (rows || []).forEach(visit);
    return scores;
  }

  function collectPeople(rows) {
    const people = [];
    const seen = {};
    const visit = (item) => {
      const person = item.name || "Member";
      if (!seen[person]) {
        seen[person] = true;
        people.push(person);
      }
      (item.replies || []).forEach(visit);
    };
    (rows || []).forEach(visit);
    people.sort((a, b) => a.localeCompare(b));
    return people;
  }

  function matchesPerson(item, person) {
    if (!person) return true;
    const notes = [item].concat(item.replies || []);
    if (person === "me") {
      const mine = String((window.socialMe || {}).id || "");
      return notes.some((note) => note.mine || (mine && String(note.user || "") === mine));
    }
    if (person === "favourites") {
      const stars = favouriteSet();
      return notes.some((note) => stars.has(String(note.user || "")));
    }
    if (String(person).indexOf("group:") === 0) {
      const id = String(person).slice(6);
      const group = (window.socialGroups || []).find((item) => String(item.id) === id);
      const members = new Set(((group && group.members) || []).map((member) => String(member)));
      return notes.some((note) => members.has(String(note.user || "")));
    }
    return notes.some((note) => (note.name || "Member") === person);
  }

  function matchesQuery(item, query) {
    const needle = String(query || "").trim().toLowerCase();
    if (!needle) return true;
    const notes = [item].concat(item.replies || []);
    return notes.some((note) => {
      const hay = [note.text, note.name, item.asset].join(" ").toLowerCase();
      return hay.indexOf(needle) !== -1;
    });
  }

  function chatCard(item, rootId) {
    const card = document.createElement("article");
    card.className = item.id === rootId ? "chat-card" : "reply";
    const person = personRow(item, "chat", item.id === rootId ? "comment" : "reply");
    const saying = document.createElement("p");
    saying.className = "saying";
    saying.textContent = String(item.text || "");
    card.appendChild(person);
    card.appendChild(saying);
    const actions = document.createElement("div");
    actions.className = "chat-actions";
    if (!item.pending) {
      actions.appendChild(chatVoteButton(item, 1));
      actions.appendChild(chatVoteButton(item, -1));
    }
    if (!item.pending) {
      const reply = document.createElement("button");
      reply.type = "button";
      reply.className = "reply-note";
      reply.textContent = "↩️";
      reply.title = "Reply";
      reply.setAttribute("aria-label", "Reply");
      reply.addEventListener("click", () => {
        window.socialStreamState.reply = { id: rootId, name: String(item.name || "Member"), social: item.social };
        paintReply(document.getElementById("social-stream-root"));
        const box = document.querySelector("#social-stream-root .chat-box");
        if (box) box.focus();
      });
      actions.appendChild(reply);
    }
    if (item.mine && !item.pending && Number(item.id) > 0) {
      const top = item.id === rootId;
      actions.appendChild(deleteNoteButton(
        top ? "Delete this comment and its replies?" : "Delete this reply?",
        () => {
          window.socialChat = dropMessage(window.socialChat, item.id);
          const panel = document.getElementById("social-stream-root");
          if (panel) renderChat(panel);
          reportChat({ action: "delete", message: item.id });
        }
      ));
    }
    card.appendChild(actions);
    (item.replies || []).forEach((reply) => card.appendChild(chatCard(reply, rootId)));
    return card;
  }

  function renderChat(panel) {
    const list = panel.querySelector(".chat-list");
    const composer = panel.querySelector(".composer");
    if (!list || !composer) return;
    const keptScroll = list.scrollTop;
    const ready = window.socialChatReady !== false;
    composer.hidden = !ready;
    list.replaceChildren();
    if (!ready) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Chat storage is not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor.";
      list.appendChild(empty);
      return;
    }
    const threads = window.socialChat || [];
    const chatPerson = (window.socialStreamState || {}).chatPerson || "";
    const query = (window.socialStreamState || {}).query || "";
    const shownThreads = threads.filter((item) => matchesPerson(item, chatPerson) && matchesQuery(item, query));
    if (!threads.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "No chat comments yet. Post the first one below.";
      list.appendChild(empty);
    } else if (!shownThreads.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = chatPerson === "me"
        ? "No chat comments from you yet."
        : String(chatPerson || "").indexOf("group:") === 0
        ? "No chat comments from that group yet."
        : chatPerson === "favourites" && !favouriteSet().size && !String(query).trim()
        ? "No favourites yet. Press the star beside a name."
        : "No chat comments match.";
      list.appendChild(empty);
    } else {
      shownThreads.forEach((item) => list.appendChild(chatCard(item, item.id)));
    }
    const notice = panel.querySelector(".chat-notice");
    if (notice) {
      const text = window.socialChatNotice || "";
      const shownInGroup = text === "They are already in that group."
        && window.socialStreamState
        && window.socialStreamState.groupFor;
      notice.hidden = !text || shownInGroup;
      notice.textContent = shownInGroup ? "" : text;
    }
    const faces = panel.querySelector(".faces");
    if (faces && (!faces.childElementCount || !faces.querySelector(".face-poop"))) {
      faces.replaceChildren();
      (window.socialChatFaces || []).forEach((face) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = String(face);
        if (face === "💩") button.className = "face-poop";
        button.addEventListener("click", () => addChatFace(panel, String(face)));
        faces.appendChild(button);
      });
    }
    paintReply(panel);
    updateChatCount(panel);
    list.scrollTop = keptScroll;
  }

  function fillStreamSelect(select, placeholder, pairs, selected, extras, divide) {
    if (!select) return;
    select.replaceChildren();
    const all = document.createElement("option");
    all.value = "";
    all.textContent = placeholder;
    select.appendChild(all);
    (extras || []).forEach((pair) => {
      const option = document.createElement("option");
      option.value = pair[0];
      option.textContent = pair[1];
      select.appendChild(option);
    });
    if (divide && pairs.length) select.appendChild(document.createElement("hr"));
    pairs.forEach((pair) => {
      const option = document.createElement("option");
      option.value = pair[0];
      option.textContent = pair[1];
      select.appendChild(option);
    });
    const allowed = new Set(pairs.map((pair) => pair[0]));
    (extras || []).forEach((pair) => allowed.add(pair[0]));
    select.value = allowed.has(selected) ? selected : "";
  }

  function streamTone(score) {
    const number = Number(score);
    if (!Number.isFinite(number)) return null;
    if (number >= 53) return { bg: "#dcfce7", fg: "#15803d", arrow: "↑" };
    if (number >= 47) return { bg: "#fef3c7", fg: "#b45309", arrow: "→" };
    return { bg: "#fee2e2", fg: "#b91c1c", arrow: "↓" };
  }

  function streamFace(name, avatar) {
    const face = document.createElement(avatar ? "img" : "div");
    face.className = "face";
    if (avatar) {
      face.alt = "";
      face.src = avatar;
      face.addEventListener("error", () => {
        const fallback = document.createElement("div");
        fallback.className = "face";
        fallback.textContent = (String(name).trim().charAt(0) || "?").toUpperCase();
        face.replaceWith(fallback);
      });
    } else {
      face.textContent = (String(name).trim().charAt(0) || "?").toUpperCase();
    }
    return face;
  }

  function streamCard(item) {
    const card = document.createElement("article");
    card.className = "card";
    const person = personRow(item, "signal", "comment");
    const saying = document.createElement("p");
    saying.className = "saying";
    saying.textContent = String(item.text || "");
    const context = document.createElement("div");
    context.className = "context";
    const label = document.createElement("div");
    label.className = "context-label";
    label.textContent = "Responding to";
    const head = document.createElement("div");
    head.className = "context-head";
    if (item.logo) {
      const logo = document.createElement("img");
      logo.className = "logo";
      logo.alt = "";
      logo.src = item.logo;
      logo.addEventListener("error", () => logo.remove());
      head.appendChild(logo);
    }
    const asset = document.createElement("span");
    asset.className = "asset";
    asset.textContent = String(item.asset || "This asset");
    head.appendChild(asset);
    const tone = streamTone(item.score);
    if (tone) {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.style.background = tone.bg;
      badge.style.color = tone.fg;
      badge.textContent = tone.arrow + " " + item.score;
      head.appendChild(badge);
    }
    context.appendChild(label);
    context.appendChild(head);
    if (item.coverage) {
      const coverage = document.createElement("div");
      coverage.className = "coverage";
      if (tone) coverage.style.color = tone.fg;
      coverage.textContent = String(item.coverage);
      context.appendChild(coverage);
    }
    if (item.summary) {
      const summary = document.createElement("p");
      summary.className = "summary";
      summary.textContent = String(item.summary);
      context.appendChild(summary);
    }
    card.appendChild(person);
    card.appendChild(saying);
    if (Number(item.id) > 0 || (item.replies || []).length) {
      card.appendChild(signalActions(item, item.id, "comment"));
      (item.replies || []).forEach((reply) => card.appendChild(signalReply(reply, item.id)));
    }
    card.appendChild(context);
    return card;
  }

  function signalVoteButton(item, direction, kind) {
    const count = direction === 1 ? item.up : item.down;
    const button = thumbButton(direction, count, item.vote === direction);
    button.addEventListener("click", () => {
      const next = item.vote === direction ? 0 : direction;
      if (item.vote === 1) item.up = Math.max(0, (Number(item.up) || 0) - 1);
      if (item.vote === -1) item.down = Math.max(0, (Number(item.down) || 0) - 1);
      item.vote = next;
      if (next === 1) item.up = (Number(item.up) || 0) + 1;
      if (next === -1) item.down = (Number(item.down) || 0) + 1;
      if (window.renderSocialStream) window.renderSocialStream();
      reportSignal({ action: "vote", message: item.id, vote: next, kind: kind });
    });
    return button;
  }

  function signalActions(item, rootId, kind) {
    const actions = document.createElement("div");
    actions.className = "chat-actions";
    if (!item.pending && Number(item.id) > 0) {
      actions.appendChild(signalVoteButton(item, 1, kind));
      actions.appendChild(signalVoteButton(item, -1, kind));
    }
    if (!item.pending && Number(rootId) > 0) {
      const reply = document.createElement("button");
      reply.type = "button";
      reply.className = "reply-note";
      reply.textContent = "↩️";
      reply.title = "Reply";
      reply.setAttribute("aria-label", "Reply");
      reply.addEventListener("click", () => {
        window.socialStreamState.reply = { id: rootId, name: String(item.name || "Member"), social: item.social, kind: "signal" };
        const panel = document.getElementById("social-stream-root");
        paintReply(panel);
        const box = panel && panel.querySelector(".chat-box");
        if (box) box.focus();
      });
      actions.appendChild(reply);
    }
    if (item.mine && !item.pending && Number(item.id) > 0) {
      actions.appendChild(deleteNoteButton(
        kind === "reply" ? "Delete this reply?" : "Delete this comment and its replies?",
        () => {
          window.socialStreamItems = dropMessage(window.socialStreamItems, item.id);
          if (window.renderSocialStream) window.renderSocialStream();
          reportSignal({ action: "delete", message: item.id, kind: kind });
        }
      ));
    }
    return actions;
  }

  function signalReply(item, rootId) {
    const card = document.createElement("article");
    card.className = "reply";
    const person = personRow(item, "signal", "reply");
    const saying = document.createElement("p");
    saying.className = "saying";
    saying.textContent = String(item.text || "");
    card.appendChild(person);
    card.appendChild(saying);
    card.appendChild(signalActions(item, rootId, "reply"));
    return card;
  }
}
"""
_social_stream = st.components.v2.component(
    "social_member",
    js=_SOCIAL_STREAM_JS,
    isolate_styles=False,
)

_SCROLL_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const token = String((data && data.token) || "");
  const targetId = String((data && data.target) || "interactive-chart");
  if (!token || window.scrollChartToken === token) return;
  window.scrollChartToken = token;
  const sectionFor = (id) => {
    const anchor = document.getElementById(id);
    if (!anchor) return null;
    let node = anchor;
    for (let step = 0; step < 8 && node; step += 1) {
      const sibling = node.nextElementSibling;
      const expander = sibling && sibling.querySelector
        ? sibling.querySelector('[data-testid="stExpander"]')
        : null;
      if (expander) return expander;
      node = node.parentElement;
    }
    return anchor;
  };
  const alreadyOnScreen = () => {
    if (targetId !== "interactive-chart") return false;
    const target = sectionFor(targetId);
    if (!target) return false;
    const scroller = target.closest('[data-testid="stMain"]') || target.closest("section.main");
    const viewTop = scroller ? scroller.getBoundingClientRect().top : 0;
    const rect = target.getBoundingClientRect();
    return rect.top >= viewTop - 16 && rect.top <= viewTop + 96;
  };
  const openClosed = () => {
    const target = sectionFor(targetId);
    if (!target || target.id) return;
    const details = target.querySelector('[data-testid="stExpanderDetails"]');
    const summary = target.querySelector("summary");
    if (details && details.hasAttribute("inert") && summary) {
      window.__angstromSectionBulk = true;
      summary.click();
      window.setTimeout(() => { window.__angstromSectionBulk = false; }, 80);
    }
  };
  const go = () => {
    if (alreadyOnScreen()) return;
    const target = sectionFor(targetId);
    if (!target) return;
    target.scrollIntoView({behavior: "auto", block: "start"});
    const scroller = target.closest('[data-testid="stMain"]') || target.closest("section.main");
    if (!scroller) return;
    const top = target.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 72;
    scroller.scrollTop = Math.max(0, top);
  };
  go();
  setTimeout(openClosed, 50);
  setTimeout(go, 50);
  setTimeout(go, 250);
  setTimeout(go, 700);
}
"""
_scroll_chart = st.components.v2.component(
    "scroll_chart",
    js=_SCROLL_JS,
    isolate_styles=False,
)

_BACK_TO_TOP_JS = """
export default function(component) {
  const { parentElement } = component;
  let host = parentElement.querySelector("[data-top-host]");
  Array.from(parentElement.children).forEach((child) => {
    if (child !== host) child.remove();
  });
  if (!host) {
    host = document.createElement("div");
    host.setAttribute("data-top-host", "");
    parentElement.appendChild(host);
  }
  host.style.textAlign = "right";
  host.innerHTML = "<button type='button' data-back-to-top "
    + "style='background:none;border:none;padding:4px 0;margin:0;color:#6b7280;"
    + "font:inherit;font-weight:600;cursor:pointer;white-space:nowrap;'>↑ Top</button>";
  host.querySelector("button").addEventListener("click", (event) => {
    event.preventDefault();
    const scroller = document.querySelector('[data-testid="stMain"]')
      || document.querySelector("section.main");
    if (scroller) scroller.scrollTop = 0;
    window.scrollTo({top: 0, behavior: "auto"});
  });
}
"""
_back_to_top = st.components.v2.component(
    "back_to_top",
    js=_BACK_TO_TOP_JS,
    isolate_styles=False,
)

# One floating ↑ Top for the whole page. Hidden until the main page has been scrolled.
_PAGE_TOP_JS = """
export default function(component) {
  const { parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const generation = (window.__angstromPageTopGen || 0) + 1;
  window.__angstromPageTopGen = generation;
  let style = document.getElementById("angstrom-page-top-style");
  if (style && style.dataset.layout !== "float") {
    style.remove();
    style = null;
  }
  if (!style) {
    style = document.createElement("style");
    style.id = "angstrom-page-top-style";
    style.dataset.layout = "float";
    style.textContent = [
      "#angstrom-page-top{position:fixed;right:1.25rem;bottom:1.25rem;z-index:10000002;display:none;",
      "background:#fff;color:#6b7280;border:1px solid rgba(49,51,63,.2);border-radius:999px;",
      "padding:8px 14px;margin:0;font:inherit;font-weight:600;line-height:1.2;cursor:pointer;",
      "box-shadow:0 1px 4px rgba(0,0,0,.08);white-space:nowrap;}",
      "#angstrom-page-top.is-on{display:inline-block;}",
      "#angstrom-page-top:hover{color:#111827;border-color:#111827;}",
      "html.angstrom-night #angstrom-page-top{background:#262730;color:#e5e7eb;border-color:#4b5563;}",
      "html.angstrom-night #angstrom-page-top:hover{color:#fafafa;border-color:#e5e7eb;}",
      "@media print{#angstrom-page-top{display:none !important;}}"
    ].join("");
    document.head.appendChild(style);
  }
  let button = document.getElementById("angstrom-page-top");
  if (!button) {
    button = document.createElement("button");
    button.id = "angstrom-page-top";
    button.type = "button";
    button.textContent = "↑ Top";
    document.body.appendChild(button);
  }
  const scrollers = () => document.querySelectorAll(
    "[data-testid='stMain'], [data-testid='stAppViewContainer'], [data-testid='stAppScrollToBottomContainer']"
  );
  const scrolled = () => {
    if (window.scrollY > 120) return true;
    for (const node of scrollers()) {
      if (node.scrollTop > 120) return true;
    }
    return false;
  };
  const place = () => {
    const root = document.getElementById("social-stream-root");
    const panel = root && root.classList.contains("is-open") ? root.querySelector(".panel") : null;
    const width = panel ? Math.round(panel.getBoundingClientRect().width) : 0;
    button.style.right = (20 + width) + "px";
  };
  const sync = () => {
    if (!button.isConnected || window.__angstromPageTopGen !== generation) return;
    place();
    button.classList.toggle("is-on", scrolled());
  };
  if (!button.dataset.bound) {
    button.dataset.bound = "1";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      window.scrollTo({top: 0, behavior: "auto"});
      scrollers().forEach((node) => { node.scrollTop = 0; });
      sync();
    });
  }
  window.__angstromPageTopSync = sync;
  if (!window.angstromPageTopScroll) {
    window.angstromPageTopScroll = true;
    document.addEventListener("scroll", () => {
      if (window.__angstromPageTopSync) window.__angstromPageTopSync();
    }, {capture: true, passive: true});
  }
  window.clearInterval(window.__angstromPageTopTimer);
  window.__angstromPageTopTimer = window.setInterval(sync, 500);
  sync();
  return () => {
    if (window.__angstromPageTopGen !== generation) return;
    window.clearInterval(window.__angstromPageTopTimer);
    const current = document.getElementById("angstrom-page-top");
    if (current) current.remove();
  };
}
"""
_page_top = st.components.v2.component(
    "page_top",
    js=_PAGE_TOP_JS,
    isolate_styles=False,
)

# The wide layout's two bottom columns. 0.5 is an even split of that pair only.
_WIDE_SPLIT_MIN = 0.2
_WIDE_SPLIT_MAX = 0.8
_WIDE_SPLIT_JS = """
export default function(component) {
  const { parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const minSplit = 0.2;
  const maxSplit = 0.8;
  const remember = (ratio) => {
    try { localStorage.setItem("angstrom-wide-split", Number(ratio).toFixed(3)); } catch (error) {}
  };
  const remembered = () => {
    try { return localStorage.getItem("angstrom-wide-split"); } catch (error) { return null; }
  };
  const stale = document.getElementById("angstrom-wide-split");
  if (stale) stale.remove();
  const handle = document.createElement("div");
  handle.id = "angstrom-wide-split";
  handle.dataset.drive = "local";
  handle.title = "Drag to resize these two columns";
  const grip = document.createElement("div");
  grip.className = "grip";
  handle.appendChild(grip);
  let watching = null;
  let observer = null;
  const pair = () => {
    const chart = document.getElementById("interactive-chart");
    if (!chart) return null;
    const mood = document.getElementById("market-mood-crypto") || document.getElementById("market-mood-stock");
    let node = chart.parentElement;
    while (node && node !== document.body) {
      if (node.getAttribute("data-testid") === "stHorizontalBlock" && (!mood || node.contains(mood))) {
        const columns = [...node.children].filter((el) => el.getAttribute("data-testid") === "stColumn");
        if (columns.length >= 2 && node.contains(chart)) return { block: node, columns };
      }
      node = node.parentElement;
    }
    return null;
  };
  const stacked = (columns) => {
    const left = columns[0].getBoundingClientRect();
    const right = columns[1].getBoundingClientRect();
    return right.top > left.bottom - 8;
  };
  const place = () => {
    const found = pair();
    if (!found || stacked(found.columns)) {
      handle.style.display = "none";
      return;
    }
    const { block, columns } = found;
    const stored = remembered();
    if (stored && !handle.classList.contains("is-dragging")) {
      const ratio = Math.min(maxSplit, Math.max(minSplit, parseFloat(stored)));
      const current = parseFloat(columns[0].style.flex);
      if (Number.isFinite(ratio) && !(Number.isFinite(current) && Math.abs(current - ratio) < 0.004)) {
        applyRatio(ratio, columns);
      }
    }
    if (handle.parentElement !== block) block.appendChild(handle);
    block.style.position = "relative";
    const blockRect = block.getBoundingClientRect();
    const left = columns[0].getBoundingClientRect();
    const right = columns[1].getBoundingClientRect();
    handle.style.display = "block";
    handle.style.position = "absolute";
    handle.style.zIndex = "30";
    handle.style.width = "12px";
    handle.style.marginLeft = "-6px";
    handle.style.top = "0";
    handle.style.cursor = "col-resize";
    handle.style.left = ((left.right + right.left) / 2 - blockRect.left) + "px";
    handle.style.height = blockRect.height + "px";
    if (watching !== block) {
      if (observer) observer.disconnect();
      watching = block;
      observer = new ResizeObserver(() => place());
      observer.observe(block);
    }
  };
  const ratioFor = (clientX, block, columns) => {
    const rect = block.getBoundingClientRect();
    const width = rect.width || 1;
    const gap = Math.max(0, columns[1].getBoundingClientRect().left - columns[0].getBoundingClientRect().right);
    const pointer = Math.min(Math.max(clientX - rect.left, 0), width);
    const ratio = (pointer - gap / 2) / Math.max(width - gap, 1);
    return Math.min(maxSplit, Math.max(minSplit, ratio));
  };
  const applyRatio = (ratio, columns) => {
    columns[0].style.flex = ratio + " 1 0px";
    columns[1].style.flex = (1 - ratio) + " 1 0px";
    columns[0].style.minWidth = "0";
    columns[1].style.minWidth = "0";
  };
  handle.addEventListener("pointerdown", (event) => {
    const found = pair();
    if (!found || stacked(found.columns) || event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    handle.classList.add("is-dragging");
    handle.setPointerCapture(event.pointerId);
    const move = (ev) => {
      const current = pair();
      if (!current) return;
      applyRatio(ratioFor(ev.clientX, current.block, current.columns), current.columns);
      place();
    };
    const stop = (ev) => {
      handle.classList.remove("is-dragging");
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", stop);
      handle.removeEventListener("pointercancel", stop);
      const current = pair();
      if (!current) return;
      const ratio = ratioFor(ev.clientX, current.block, current.columns);
      applyRatio(ratio, current.columns);
      remember(ratio);
      place();
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", stop);
    handle.addEventListener("pointercancel", stop);
  });
  place();
  const retry = window.setInterval(place, 400);
  const stopRetry = window.setTimeout(() => window.clearInterval(retry), 8000);
  return () => {
    window.clearInterval(retry);
    window.clearTimeout(stopRetry);
    if (observer) observer.disconnect();
    handle.remove();
  };
}
"""
_wide_split_handle = st.components.v2.component(
    "wide_split",
    js=_WIDE_SPLIT_JS,
    isolate_styles=False,
)

_COUNTDOWN_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const timerKey = "cd_" + ((data && data.key) || "x");
  window.clearInterval(window[timerKey]);
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "block";
  shell.style.height = "auto";
  shell.style.width = "100%";
  let button = shell.querySelector("button.angstrom-jump");
  if (!button) {
    button = document.createElement("button");
    button.type = "button";
    button.className = "angstrom-jump";
    shell.appendChild(button);
  }
  button.dataset.target = String((data && data.target) || "");
  button.title = String((data && data.help) || "");
  let icon = button.querySelector(".angstrom-jump-icon");
  let text = button.querySelector(".angstrom-jump-text");
  if (!icon || !text) {
    button.textContent = "";
    icon = document.createElement("span");
    icon.className = "angstrom-jump-icon";
    icon.setAttribute("aria-hidden", "true");
    text = document.createElement("span");
    text.className = "angstrom-jump-text";
    button.appendChild(icon);
    button.appendChild(text);
  }
  const mark = String((data && data.icon) || "");
  icon.textContent = mark;
  icon.style.display = mark ? "" : "none";
  button.onclick = () => {
    const targetId = button.dataset.target || "";
    const anchor = document.getElementById(targetId);
    if (!anchor) return;
    let section = anchor;
    let node = anchor;
    for (let step = 0; step < 8 && node; step += 1) {
      const sibling = node.nextElementSibling;
      const expander = sibling && sibling.querySelector
        ? sibling.querySelector('[data-testid="stExpander"]')
        : null;
      if (expander) {
        section = expander;
        const details = expander.querySelector('[data-testid="stExpanderDetails"]');
        const summary = expander.querySelector("summary");
        if (details && details.hasAttribute("inert") && summary) summary.click();
        break;
      }
      node = node.parentElement;
    }
    const go = () => {
      const current = section && section.isConnected ? section : document.getElementById(targetId);
      if (!current) return;
      current.scrollIntoView({behavior: "auto", block: "start"});
      const scroller = current.closest('[data-testid="stMain"]') || current.closest("section.main");
      if (!scroller) return;
      const top = current.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 72;
      scroller.scrollTop = Math.max(0, top);
    };
    go();
    window.setTimeout(go, 50);
    window.setTimeout(go, 250);
    window.setTimeout(go, 700);
  };
  const end = Number(data && data.deadlineMs);
  const token = String((data && data.token) || "");
  function render() {
    if (!Number.isFinite(end)) return;
    const left = Math.max(0, Math.round((end - Date.now()) / 1000));
    const hours = Math.floor(left / 3600);
    const minutes = Math.floor((left % 3600) / 60);
    const seconds = String(left % 60).padStart(2, "0");
    const clock = hours + ":" + String(minutes).padStart(2, "0") + ":" + seconds;
    const title = (data && data.label) || "Refresh";
    const lead = (data && data.lead) || "";
    if (left <= 0) text.textContent = title + " (update due)";
    else if (lead) text.textContent = title + " (" + lead + " " + clock + ")";
    else text.textContent = title + " (" + clock + ")";
    const seenKey = timerKey + "_seen";
    const sentKey = timerKey + "_sent";
    if (window[seenKey] !== token) {
      window[seenKey] = token;
      // Switching asset shows a deadline that is already due. Rebuild only
      // when this same timer counts down to zero, not on that first paint.
      if (left <= 0) window[sentKey] = token;
    }
    if (left <= 0 && token && window[sentKey] !== token) {
      window.clearInterval(window[timerKey]);
      window[sentKey] = token;
      setTriggerValue("due", token);
    }
  }
  render();
  window[timerKey] = setInterval(render, 1000);
  return () => {
    window.clearInterval(window[timerKey]);
  };
}
"""
_countdown = st.components.v2.component(
    "refresh_countdown",
    js=_COUNTDOWN_JS,
    isolate_styles=False,
)

_HEADER_SCORE_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  let payload = data;
  if (typeof data === "string") {
    try { payload = JSON.parse(data); } catch (error) { payload = null; }
  }
  const expander = shell.closest('[data-testid="stExpander"]');
  const summary = expander && expander.querySelector("summary");
  if (!summary) return () => {};
  let badge = summary.querySelector(":scope > .ang-header-score");
  if (!badge) {
    badge = document.createElement("span");
    badge.className = "ang-header-score";
    const icon = summary.querySelector('[data-testid="stExpanderToggleIcon"], [data-testid="stExpanderIcon"]');
    let slot = icon;
    while (slot && slot.parentElement !== summary) slot = slot.parentElement;
    if (slot) summary.insertBefore(badge, slot);
    else summary.appendChild(badge);
  }
  const raw = payload ? payload.score : null;
  const score = raw === null || raw === undefined || raw === "" ? NaN : Number(raw);
  const color = (payload && payload.color) || "#6b7280";
  const background = (payload && payload.background) || "transparent";
  badge.textContent = Number.isFinite(score) ? String(Math.round(score)) : "—";
  badge.style.color = color;
  badge.style.background = Number.isFinite(score) ? background : "transparent";
  return () => badge.remove();
}
"""
_header_score = st.components.v2.component(
    "header_score",
    js=_HEADER_SCORE_JS,
    isolate_styles=False,
)

# Opening a section is only show and hide. This records that choice without
# asking Streamlit to rebuild the page.
_SECTION_TOGGLE_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const mainIds = new Set((data && data.main) || []);
  const closeIds = new Set((data && data.collapseAlso) || []);
  window.__angstromSetSection = (name, value) => {
    if (window.__angstromSectionBulk && String(value || "").indexOf("all:") !== 0) return;
    setTriggerValue(name, value);
  };
  const sectionIdOf = (expander) => {
    let node = expander;
    while (node) {
      const names = typeof node.className === "string" ? node.className.split(" ") : [];
      const hit = names.find((name) => name.indexOf("st-key-sec_") === 0);
      if (hit) return hit.slice("st-key-sec_".length);
      node = node.parentElement;
    }
    return "";
  };
  const expanderOpen = (expander) => {
    const details = expander.querySelector("details");
    return !!(details && details.open);
  };
  const applyBulk = (open) => {
    window.__angstromSectionBulk = true;
    document.querySelectorAll('[data-testid="stExpander"]').forEach((expander) => {
      const sectionId = sectionIdOf(expander);
      if (!sectionId) return;
      const included = open ? mainIds.has(sectionId) : (mainIds.has(sectionId) || closeIds.has(sectionId));
      if (!included || expanderOpen(expander) === open) return;
      const summary = expander.querySelector("summary");
      if (summary) summary.click();
    });
    window.setTimeout(() => { window.__angstromSectionBulk = false; }, 80);
  };
  if (typeof window.__angstromSectionWatch === "function") {
    document.removeEventListener("click", window.__angstromSectionWatch, true);
  }
  const watch = (event) => {
    const target = event.target;
    if (!target || !target.closest || window.__angstromSectionBulk) return;
    const button = target.closest("button");
    const bulkHost = button && button.closest("[class*='st-key-open_all_sections'], [class*='st-key-collapse_all_sections']");
    if (bulkHost) {
      event.preventDefault();
      event.stopPropagation();
      const open = String(bulkHost.className).indexOf("st-key-open_all_sections") !== -1;
      applyBulk(open);
      const send = window.__angstromSetSection;
      if (send) send("toggle", open ? "all:1" : "all:0");
      return;
    }
    const summary = target.closest("summary");
    if (!summary) return;
    const expander = summary.closest('[data-testid="stExpander"]');
    if (!expander) return;
    const sectionId = sectionIdOf(expander);
    if (!sectionId) return;
    window.setTimeout(() => {
      const details = expander.querySelector('[data-testid="stExpanderDetails"]');
      const opened = !!(details && !details.hasAttribute("inert"));
      const send = window.__angstromSetSection;
      if (send) send("toggle", sectionId + ":" + (opened ? "1" : "0"));
    }, 40);
  };
  window.__angstromSectionWatch = watch;
  document.addEventListener("click", watch, true);
  return () => {
    if (window.__angstromSectionWatch === watch) {
      document.removeEventListener("click", watch, true);
      window.__angstromSectionWatch = null;
    }
  };
}
"""
_section_toggle = st.components.v2.component(
    "section_toggle",
    js=_SECTION_TOGGLE_JS,
    isolate_styles=False,
)

# The reset link comes back in the address hash, which Streamlit does not send
# to Python. This reads it once and hands the session to the password form.
_RECOVERY_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  // Google refuses to sign in inside the app frame, so the return lands on the
  // outer page. The code is read from whichever address actually has it.
  let codeOwner = window;
  try {
    if (window.top && new URLSearchParams(window.top.location.search).get("code")) {
      codeOwner = window.top;
    }
  } catch (err) {}
  const search = new URLSearchParams(codeOwner.location.search);
  const code = search.get("code") || "";
  const savePkce = (value) => {
    try { sessionStorage.setItem("angstrom-pkce", value); } catch (err) {}
    try { localStorage.setItem("angstrom-pkce", value); } catch (err) {}
    const secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = "angstrom_pkce=" + encodeURIComponent(value) + "; Path=/; Max-Age=600; SameSite=Lax" + secure;
  };
  const readPkce = () => {
    try {
      const saved = sessionStorage.getItem("angstrom-pkce");
      if (saved) return saved;
    } catch (err) {}
    const parts = (document.cookie || "").split("; ");
    for (const part of parts) {
      if (part.indexOf("angstrom_pkce=") === 0) {
        return decodeURIComponent(part.slice("angstrom_pkce=".length));
      }
    }
    try { return localStorage.getItem("angstrom-pkce") || ""; } catch (err) {}
    return "";
  };
  if (!code && data && data.verifier) {
    window.angstromPkce = String(data.verifier);
    savePkce(window.angstromPkce);
  }
  if (!window.angstromPkceWatch) {
    window.angstromPkceWatch = true;
    document.addEventListener("click", (event) => {
      const link = event.target && event.target.closest ? event.target.closest("a") : null;
      if (!link || !window.angstromPkce) return;
      const href = link.getAttribute("href") || "";
      if (href.indexOf("provider=google") === -1 && !link.classList.contains("angstrom-google")) return;
      savePkce(window.angstromPkce);
    }, true);
  }
  if (code && !window.angstromCodeSent) {
    window.angstromCodeSent = true;
    setTriggerValue("oauth", JSON.stringify({
      code: code,
      verifier: readPkce()
    }));
    search.delete("code");
    const rest = search.toString();
    codeOwner.history.replaceState(null, "", codeOwner.location.pathname + (rest ? "?" + rest : "") + codeOwner.location.hash);
  }
  if (data && data.clear) {
    if (window.location.hash) {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    return;
  }
  if (window.angstromRecoverySent) return;
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const type = params.get("type") || "";
  const access = params.get("access_token") || "";
  const refresh = params.get("refresh_token") || "";
  const error = params.get("error_description") || params.get("error_code") || "";
  if (!(access && refresh) && !error) return;
  window.angstromRecoverySent = true;
  setTriggerValue("recovery", JSON.stringify({
    type: type,
    access: access,
    refresh: refresh,
    error: error
  }));
  if (type !== "recovery") {
    history.replaceState(null, "", window.location.pathname + window.location.search);
  }
}
"""
_recovery_link = st.components.v2.component(
    "password_recovery",
    js=_RECOVERY_JS,
    isolate_styles=False,
)

# The app frame cannot move the main window, and Google will not sign in inside
# that frame. A short-lived window is allowed to move this tab, then it closes.
_GOOGLE_BUTTON_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.height = "auto";
  shell.style.width = "100%";
  if (!document.getElementById("angstrom-google-btn")) {
    const style = document.createElement("style");
    style.id = "angstrom-google-btn";
    style.textContent = [
      "a.angstrom-google{display:flex;align-items:center;justify-content:center;width:100%;box-sizing:border-box;min-height:2.5rem;padding:0.25rem 0.75rem;border-radius:0.5rem;text-decoration:none;background:#fff;color:#31333f;border:1px solid rgba(49,51,63,0.2);}",
      "a.angstrom-google:hover{background:#f0f2f6;color:#31333f;}",
      "html.angstrom-night a.angstrom-google{background:#262730;color:#fafafa;border-color:#4b5563;}",
      "html.angstrom-night a.angstrom-google:hover{background:#31333f;color:#fafafa;}"
    ].join("");
    document.head.appendChild(style);
  }
  let link = shell.querySelector("a.angstrom-google");
  if (!link) {
    link = document.createElement("a");
    link.className = "angstrom-google";
    link.textContent = "Continue with Google";
    shell.appendChild(link);
  }
  link.removeAttribute("target");
  const url = data && data.url ? String(data.url) : "";
  const verifier = data && data.verifier ? String(data.verifier) : "";
  link.href = url || "#";
  link.onclick = (event) => {
    if (!url) return;
    event.preventDefault();
    if (verifier) {
      try { sessionStorage.setItem("angstrom-pkce", verifier); } catch (err) {}
      try { localStorage.setItem("angstrom-pkce", verifier); } catch (err) {}
      const secure = location.protocol === "https:" ? "; Secure" : "";
      document.cookie = "angstrom_pkce=" + encodeURIComponent(verifier) + "; Path=/; Max-Age=600; SameSite=Lax" + secure;
    }
    const quoted = JSON.stringify(url);
    const page = "<!doctype html><title>Continue</title><script>try{window.opener.top.location.replace(" + quoted + ");window.close();}catch(e){location.replace(" + quoted + ");}<" + "/script>";
    const popup = window.open(URL.createObjectURL(new Blob([page], { type: "text/html" })), "_blank");
    if (!popup) window.location.assign(url);
  };
}
"""
_google_button = st.components.v2.component(
    "google_sign_in",
    js=_GOOGLE_BUTTON_JS,
    isolate_styles=False,
)


def _countdown_due(
    deadline: float | None,
    widget_key: str,
    label: str | None = None,
    target: str = "",
    help_text: str = "",
    icon: str = "",
) -> bool:
    """Show the time until a shared update. A missing time stays on 'update due'.

    The button opens its section in the browser. Pressing it does not rebuild the page.
    """
    if deadline is None:
        token = ""
        deadline_ms = 0
    else:
        token = str(int(deadline * 1000))
        deadline_ms = int(deadline * 1000)
    payload = {
        "deadlineMs": deadline_ms,
        "token": token,
        "key": widget_key,
        "lead": "update in",
        "target": target,
        "help": help_text,
    }
    if label:
        payload["label"] = label
    if icon:
        payload["icon"] = icon
    result = _countdown(
        key=widget_key,
        data=payload,
        on_due_change=lambda: None,
    )
    return bool(token) and result.due == token


def _rerun_fragment() -> None:
    """Rerun the current section, or the whole page when that is not allowed.

    A fragment-scoped rerun is rejected while that fragment is only running as
    part of a full page load. The sentiment timer hits this when its click
    arrives together with another full-page update.
    """
    try:
        st.rerun(scope="fragment")
    except StreamlitInvalidLayoutContextError:
        st.rerun()
    except RuntimeError as exc:
        if "current_fragment_id" not in str(exc):
            raise
        st.rerun()


# Main sections start open. The guide and the sidebar start closed.
# Open all and Collapse all move only the main sections. Collapse all also closes the guide.
_MAIN_SECTION_IDS = _POPOUT_SECTION_IDS
_SECTION_IDS = _MAIN_SECTION_IDS + (
    "help_guides",
    "account",
    "my_groups",
    "edit_profile",
    "invite",
    "notifications",
    "alert_feed",
    "alert_rules",
    "watchlists",
    "edit_crypto",
    "edit_stocks",
    "weights",
    "settings_panel",
    "colours",
    "feedback",
    "about",
    "socials_policy",
    "terms",
    "privacy",
    "admin_panel",
    "admin_feedback",
    "admin_reports",
    "admin_blacklist",
    "admin_beta",
)


def _section_map() -> dict:
    """A copy of the open or collapsed choice saved on this account."""
    stored = (st.session_state.get("cloud_prefs") or {}).get("settings") or {}
    raw = stored.get("sections") if isinstance(stored, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {str(key): bool(value) for key, value in raw.items() if isinstance(value, bool)}


def _section_expanded(section_id: str, default: bool) -> bool:
    states = _section_map()
    if section_id in states:
        return states[section_id]
    return default


def _remember_section(section_id: str, opened: bool) -> None:
    states = _section_map()
    opened = bool(opened)
    if section_id in states and states[section_id] is opened:
        return
    states[section_id] = opened
    save_account_settings({"sections": states})


def _apply_section_bulk(opening: bool) -> None:
    """Open or close every main section together. Collapse also closes the guide."""
    states = _section_map()
    opening = bool(opening)
    for section_id in _MAIN_SECTION_IDS:
        states[section_id] = opening
    if not opening:
        states["help_guides"] = False
    save_account_settings({"sections": states})


def tracked_expander(label: str, section_id: str, *, default: bool = False, sidebar: bool = False):
    """One collapsible whose open or collapsed state is saved on the account.

    The header toggles in the browser. A separate watcher saves that choice,
    so opening or closing a section does not rebuild the page.
    """
    expanded = _section_expanded(section_id, default)
    opener = st.sidebar.expander if sidebar else st.expander
    return opener(label, expanded=expanded, key=f"sec_{section_id}")


@st.fragment
def remember_section_clicks() -> None:
    """Write one open or closed section onto the account, and leave the page as it is."""
    reported = _section_toggle(
        key="section_toggle_watch",
        data={"main": list(_MAIN_SECTION_IDS), "collapseAlso": ["help_guides"]},
        on_toggle_change=lambda: None,
    )
    raw = str(getattr(reported, "toggle", "") or "")
    if raw in ("all:1", "all:0"):
        _apply_section_bulk(raw == "all:1")
        return
    if ":" not in raw:
        return
    section_id, flag = raw.rsplit(":", 1)
    if not section_id or flag not in ("0", "1"):
        return
    token = f"{section_id}:{flag}"
    if st.session_state.get("_section_toggle_seen") == token:
        return
    st.session_state["_section_toggle_seen"] = token
    _remember_section(section_id, flag == "1")


_FAVOURITE_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  window.__angstromSetFavourite = setTriggerValue;
  if (!data) return;
  let problem = null;
  try {
    problem = JSON.parse(data);
  } catch (error) {
    problem = null;
  }
  if (!problem || !problem.revert || window.__angstromFavSeen === problem.n) return;
  window.__angstromFavSeen = problem.n;
  const id = String(problem.user || "").toLowerCase();
  const current = (window.socialFavourites || []).map(String);
  if (problem.on) window.socialFavourites = current.filter((item) => item !== id);
  else if (id && current.indexOf(id) === -1) window.socialFavourites = current.concat([id]);
  window.socialChatNotice = problem.notice || "That favourite could not be saved. Try again.";
  if (window.renderSocialStream) window.renderSocialStream();
}
"""
_favourite_watch = st.components.v2.component(
    "favourite_watch",
    js=_FAVOURITE_JS,
    isolate_styles=False,
)


@st.fragment
def remember_favourites() -> None:
    """Save one star from the social panel without rebuilding the page."""
    problem = st.session_state.get("fav_problem") or ""
    reported = _favourite_watch(
        key="favourite_watch",
        data=problem,
        on_picked_change=lambda: None,
    )
    if problem:
        st.session_state.pop("fav_problem", None)
    event = _favourite_event(getattr(reported, "picked", None))
    if not event or st.session_state.get("favourite_done") == event.get("n"):
        return
    st.session_state["favourite_done"] = event.get("n")
    notice = _apply_favourite(event)
    if not notice:
        return
    st.session_state["fav_problem"] = json.dumps({
        "revert": True,
        "n": event.get("n"),
        "user": str(event.get("user") or ""),
        "on": bool(event.get("on")),
        "notice": notice,
    })
    _rerun_fragment()


def section_expander(label: str, section_id: str):
    """A main-page section. Open all and Collapse all move every one of these together."""
    if _POPOUT_VIEW and _POPOUT_VIEW != "social":
        # A pop-out tab shows one section. The others still run, because later
        # sections use what earlier ones set up, but they are hidden.
        if section_id == _POPOUT_VIEW:
            return st.expander(label, expanded=True, key=f"pop_{section_id}")
        return st.container(key=f"hide_{section_id}")
    return tracked_expander(label, section_id, default=True)


def _reveal_section(section_id: str, anchor: str) -> None:
    """Open one section and scroll to it, without folding the others."""
    _remember_section(section_id, True)
    st.session_state.scroll_target = anchor
    st.session_state.scroll_token = str(time.time_ns())


from email_brand import render_email
import beta_emails
import chart_plan
import score_rules
from digest import COMMON_ZONES
import session_guard
import colour_themes

BETA_REQUEST_URL = "https://angstromsignals.com/beta.html"

try:
    from alerts import HELD_BEARISH, HELD_BULLISH, dismiss_read_alerts
    from data_fetchers import (
        crypto_logo_urls,
        crypto_market_caps,
        crypto_market_stats,
        crypto_ticker,
        fetch_crypto_data,
        fetch_stock_data,
        find_crypto,
        format_market_cap,
        stock_logo_url,
        stock_market_caps,
        stock_next_earnings,
        period_for_days,
        resolve_crypto_id,
        search_crypto_matches,
        search_stock_matches,
    )
    from market_store import (
        asset_logo,
        asset_market_key,
        COMMENT_EMOTICONS,
        COMMENT_LIMIT,
        comment_balloon,
        crowd_mark,
        holder_counts,
        holders_mark,
        delete_chat_message,
        delete_signal_message,
        load_chat,
        load_market_moods,
        market_mood_crowd,
        frame_from_row,
        load_shared_market,
        earnings_from_rows,
        held_report_dates,
        load_earnings_status,
        load_earnings_history,
        market_stats_from_rows,
        recent_closes,
        row_timestamp,
        save_logos,
        save_earnings,
        save_market_stats,
        save_market_mood,
        set_chat_vote,
        set_signal_vote,
        set_market_mood_vote,
        post_chat,
        save_price_paths,
        post_signal_reply,
        save_sentiment,
        sentiment_comment_lists,
        sentiment_crowd,
        sentiment_replies,
        social_stream_items,
        set_sentiment_comment,
        set_sentiment_vote,
        sentiment_from_row,
        sparkline_svg,
        trend_tone,
    )
    from scoring import calculate_indicators, compute_score, find_column
    from shared_refresh import (
        create_price_row,
        ensure_new_asset,
        next_update,
        slice_history,
    )
    from max_pain import (
        list_expiries,
        load_open_interest,
        options_market,
        pain_strike,
        window_strikes,
    )
    from market_gauges import market_gauge_groups
    from sentiment import (
        analyze_market_mood,
        analyze_market_sentiment,
        MACRO_MOODS,
        cached_sentiment_score,
        newest_first,
        remember_sentiment,
        sentiment_query,
        sentiment_ready,
        SENTIMENT_REFRESH_SECONDS,
        TECHNICAL_REFRESH_SECONDS,
    )
except Exception:
    st.error("The dashboard could not load its scoring code.")
    st.code(traceback.format_exc())
    st.stop()


def jwt_role(key: str) -> str | None:
    try:
        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("role")
    except Exception:
        return None


def _secret(name: str):
    try:
        return st.secrets["supabase"][name]
    except Exception:
        return None


def _optional_secret(*names: str) -> str:
    """One secret value. Empty when that name is not set. The value is never shown."""
    try:
        value = st.secrets
        for name in names:
            value = value[name]
        return str(value or "").strip()
    except Exception:
        return ""


_BARRED_NOTICE = (
    "This account is barred at this time. You can email report@angstromsignals.com."
)
_CLOSED_BETA_NOTICE = (
    "Angstrom Signals is in closed beta, and that email has not been approved yet. "
    "Use the email you applied with, or request access at angstromsignals.com."
)


def _clean_invite_email(value: str) -> str:
    """A lower-case email, or empty when the text is not an address."""
    text = " ".join(str(value or "").split()).lower()
    if text.count("@") != 1 or any(ch.isspace() for ch in text):
        return ""
    local, domain = text.split("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        return ""
    return text


def _flag_is_true(data) -> bool:
    if isinstance(data, str):
        return data.strip().strip('"').lower() == "true"
    return data is True


_HANDOFF_HOST_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const holder = shell.closest('[data-testid="stElementContainer"]');
  if (holder) holder.style.display = "none";
  if (!("BroadcastChannel" in window)) return;
  const access = String((data && data.access) || "");
  window.__angstromAccess = access;
  if (!window.__angstromHandoffHost) {
    const channel = new BroadcastChannel("angstrom-handoff");
    window.__angstromHandoffHost = channel;
    channel.onmessage = (event) => {
      const msg = event.data || {};
      if (msg.type === "ask" && window.__angstromAccess) {
        channel.postMessage({ type: "token", to: String(msg.id || ""), access: window.__angstromAccess });
      }
    };
  }
  if (access && window.__angstromAccessSent !== access) {
    window.__angstromAccessSent = access;
    window.__angstromHandoffHost.postMessage({ type: "token", to: "*", access: access });
  }
}
"""
_handoff_host = st.components.v2.component(
    "pop_out_handoff_host",
    js=_HANDOFF_HOST_JS,
    isolate_styles=False,
)

_HANDOFF_ASK_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const holder = shell.closest('[data-testid="stElementContainer"]');
  if (holder) holder.style.display = "none";
  window.__angstromHandoffSet = setTriggerValue;
  const current = String((data && data.current) || "");
  if (!("BroadcastChannel" in window)) {
    if (!current) setTriggerValue("none", String(Date.now()));
    return;
  }
  window.__angstromHandoffCurrent = current;
  if (window.__angstromHandoffAsk) return;
  const id = Math.random().toString(36).slice(2);
  const channel = new BroadcastChannel("angstrom-handoff");
  window.__angstromHandoffAsk = channel;
  channel.onmessage = (event) => {
    const msg = event.data || {};
    if (msg.type === "logout") {
      // The member chose to keep pop-outs open after signing out: leave this tab as it is.
      if (msg.keep) return;
      // Otherwise close this tab, or reload it onto the sign-in page.
      window.close();
      window.setTimeout(() => window.location.reload(), 400);
      return;
    }
    if (msg.type !== "token" || !msg.access) return;
    if (msg.to !== id && msg.to !== "*") return;
    if (msg.access === window.__angstromHandoffCurrent) return;
    window.__angstromHandoffCurrent = msg.access;
    window.__angstromHandoffSet("token", msg.access);
  };
  let tries = 0;
  const ask = () => {
    if (window.__angstromHandoffCurrent) return;
    tries += 1;
    if (tries > 5) {
      window.__angstromHandoffSet("none", String(Date.now()));
      return;
    }
    channel.postMessage({ type: "ask", id: id });
    window.setTimeout(ask, 700);
  };
  ask();
}
"""
_handoff_ask = st.components.v2.component(
    "pop_out_handoff_ask",
    js=_HANDOFF_ASK_JS,
    isolate_styles=False,
)

_LOGOUT_CAST_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const holder = shell.closest('[data-testid="stElementContainer"]');
  if (holder) holder.style.display = "none";
  if (!("BroadcastChannel" in window)) return;
  const token = String((data && data.n) || "");
  if (!token || window.__angstromLogoutSent === token) return;
  window.__angstromLogoutSent = token;
  const channel = new BroadcastChannel("angstrom-handoff");
  channel.postMessage({ type: "logout", keep: !!(data && data.keep) });
  window.setTimeout(() => channel.close(), 500);
}
"""
_logout_cast = st.components.v2.component(
    "pop_out_logout_cast",
    js=_LOGOUT_CAST_JS,
    isolate_styles=False,
)

# "Keep me signed in": one browser cookie holds the sign-in refresh token for 30 days.
# It is set only after a person ticks the box, and cleared when they log out.
_KEEP_COOKIE = "angstrom_keep"
_KEEP_COOKIE_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const holder = shell.closest('[data-testid="stElementContainer"]');
  if (holder) holder.style.display = "none";
  const value = String((data && data.value) || "");
  const pref = String((data && data.pref) || "");
  const secure = location.protocol === "https:" ? "; Secure" : "";
  if (value) {
    document.cookie = "angstrom_keep=" + encodeURIComponent(value) + "; Path=/; Max-Age=2592000; SameSite=Lax" + secure;
  } else {
    document.cookie = "angstrom_keep=; Path=/; Max-Age=0; SameSite=Lax" + secure;
  }
  // Remember only the choice (never a token), so the box starts ticked next time on this device.
  if (pref === "1") {
    document.cookie = "angstrom_keep_pref=1; Path=/; Max-Age=31536000; SameSite=Lax" + secure;
  } else if (pref === "0") {
    document.cookie = "angstrom_keep_pref=; Path=/; Max-Age=0; SameSite=Lax" + secure;
  }
}
"""
_keep_cookie = st.components.v2.component(
    "keep_signed_in_cookie",
    js=_KEEP_COOKIE_JS,
    isolate_styles=False,
)


def _keep_cookie_read() -> str:
    """The saved sign-in from this browser, or empty."""
    try:
        return str(st.context.cookies.get(_KEEP_COOKIE) or "")
    except Exception:
        return ""


def _keep_pref_read() -> bool:
    """True when this device was last signed in with Keep me signed in ticked."""
    try:
        return str(st.context.cookies.get(_KEEP_COOKIE + "_pref") or "") == "1"
    except Exception:
        return False


def _keep_cookie_write(value: str, pref: str = "") -> None:
    """Save (or, with an empty value, clear) the cookie. pref "1" or "0" also remembers the choice.
    Pop-out tabs never touch it."""
    if _POPOUT_VIEW:
        return
    count = int(st.session_state.get("_keep_n", 0)) + 1
    st.session_state["_keep_n"] = count
    _keep_cookie(key=f"keep_cookie_{count}", data={"value": str(value or ""), "pref": pref})

_POPOUT_BUTTONS_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const holder = shell.closest('[data-testid="stElementContainer"]');
  if (holder) holder.style.display = "none";
  const ids = Array.isArray(data && data.ids) ? data.ids.map(String) : [];
  window.__angstromPopoutIds = ids;
  window.__angstromPopoutOpts = { asWindow: !(data && data.asWindow === false), fold: !(data && data.fold === false) };
  if (window.__angstromPopoutTimer) return;
  if (!document.getElementById("ang-popout-style")) {
    const style = document.createElement("style");
    style.id = "ang-popout-style";
    style.textContent = ".ang-popout{margin-left:6px;flex:none;display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;padding:0;border:0;border-radius:999px;background:transparent;color:inherit;opacity:.55;cursor:pointer;}.ang-popout:hover{opacity:1;background:rgba(128,128,128,.18);}";
    document.head.appendChild(style);
  }
  const place = (summary, button) => {
    // Just left of the open/close arrow, and after the score when the header has one.
    const icon = summary.querySelector('[data-testid="stExpanderToggleIcon"], [data-testid="stExpanderIcon"]');
    let slot = icon;
    while (slot && slot.parentElement !== summary) slot = slot.parentElement;
    const badge = summary.querySelector(":scope > .ang-header-score");
    if (slot) {
      if (button.nextElementSibling !== slot) summary.insertBefore(button, slot);
    } else if (button.parentElement !== summary || button !== summary.lastElementChild) {
      summary.appendChild(button);
    }
    button.style.marginLeft = badge ? "6px" : "auto";
  };
  const add = () => {
    (window.__angstromPopoutIds || []).forEach((id) => {
      const box = document.querySelector(".st-key-sec_" + id);
      const summary = box ? box.querySelector("summary") : null;
      if (!summary) return;
      const existing = summary.querySelector(".ang-popout");
      if (existing) {
        place(summary, existing);
        return;
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ang-popout";
      button.title = "Open this section in its own window";
      button.setAttribute("aria-label", "Open this section in its own window");
      button.innerHTML = "<svg viewBox='0 0 24 24' width='14' height='14' aria-hidden='true' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 4h6v6'/><path d='M20 4 10 14'/><path d='M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5'/></svg>";
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const box = document.querySelector(".st-key-sec_" + id);
        const address = window.location.origin + window.location.pathname + "?view=" + encodeURIComponent(id);
        // A window of its own, reused if this section is already open in one.
        const opts = window.__angstromPopoutOpts || { asWindow: true, fold: true };
        const opened = opts.asWindow
          ? window.open(address, "ang_popout_" + id, "popup=yes,width=1100,height=760")
          : null;
        if (!opened) {
          window.open(address, "_blank");
        }
        // Fold the section here while it lives in its own window.
        const details = box ? box.querySelector("details") : null;
        const header = box ? box.querySelector("summary") : null;
        if (opts.fold && details && details.open && header) header.click();
      });
      place(summary, button);
    });
  };
  add();
  window.__angstromPopoutTimer = window.setInterval(add, 1500);
}
"""
_popout_buttons = st.components.v2.component(
    "pop_out_buttons",
    js=_POPOUT_BUTTONS_JS,
    isolate_styles=False,
)

_ASSET_FOLLOW_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const holder = shell.closest('[data-testid="stElementContainer"]');
  if (holder) holder.style.display = "none";
  if (!("BroadcastChannel" in window) || window.__angstromFollowRx) return;
  const channel = new BroadcastChannel("angstrom-link");
  window.__angstromFollowRx = channel;
  // The main page follows too, but quietly: it does not scroll, and it does not ask the other tabs
  // what they have open (that would let a pop-out override the main page's own choice on load).
  const quiet = !!(data && data.quiet);
  const pick = (kind, id, tries) => {
    if (window.__angstromPickAsset) {
      window.__angstromPickAsset("picked", kind + "|" + id + (quiet ? "|quiet" : ""));
    } else if (tries < 10) {
      window.setTimeout(() => pick(kind, id, tries + 1), 300);
    }
  };
  channel.onmessage = (event) => {
    const msg = event.data || {};
    if (msg.type === "asset" && msg.kind && msg.id) pick(String(msg.kind), String(msg.id), 0);
  };
  if (!quiet) channel.postMessage({ type: "hello" });
}
"""
_asset_follow = st.components.v2.component(
    "pop_out_asset_follow",
    js=_ASSET_FOLLOW_JS,
    isolate_styles=False,
)

_SOCIAL_CLEAR_JS = """
export default function(component) {
  const { parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const holder = shell.closest('[data-testid="stElementContainer"]');
  if (holder) holder.style.display = "none";
  // Signed out: the social panel and its pull-out tab belong to the signed-in page.
  if (window.socialStreamAbort) window.socialStreamAbort.abort();
  const root = document.getElementById("social-stream-root");
  if (root) root.remove();
  const style = document.getElementById("social-stream-style");
  if (style) style.remove();
  const main = document.querySelector("[data-testid='stMain']");
  if (main) main.style.paddingRight = "";
  window.socialStreamState = null;
  window.socialAccount = "";
  window.socialStreamItems = [];
  window.socialChat = [];
}
"""
_social_clear = st.components.v2.component(
    "social_panel_clear",
    js=_SOCIAL_CLEAR_JS,
    isolate_styles=False,
)

_ASSET_LINK_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const holder = shell.closest('[data-testid="stElementContainer"]');
  if (holder) holder.style.display = "none";
  if (!("BroadcastChannel" in window)) return;
  window.__angstromLinkRefresh = setTriggerValue;
  const key = String((data && data.key) || "");
  const label = String((data && data.label) || key);
  const kind = String((data && data.kind) || "");
  const assetId = String((data && data.id) || "");
  window.__angstromLinkCurrent = { key: key, label: label, kind: kind, id: assetId };
  if (!window.__angstromLinkTx) {
    const channel = new BroadcastChannel("angstrom-link");
    window.__angstromLinkTx = channel;
    channel.onmessage = (event) => {
      const msg = event.data || {};
      const now = window.__angstromLinkCurrent;
      if (msg.type === "hello" && now && now.key) {
        channel.postMessage({ type: "asset", key: now.key, label: now.label, kind: now.kind, id: now.id });
      }
      if (msg.type === "changed" && msg.from !== window.__angstromTabId && window.__angstromLinkRefresh) {
        window.__angstromLinkRefresh("refresh", String(Date.now()));
      }
    };
  }
  if (key && window.__angstromLinkSent !== key) {
    window.__angstromLinkSent = key;
    window.__angstromLinkTx.postMessage({ type: "asset", key: key, label: label, kind: kind, id: assetId });
  }
}
"""
_asset_link = st.components.v2.component(
    "pop_out_asset_link",
    js=_ASSET_LINK_JS,
    isolate_styles=False,
)


def get_supabase():
    """A new client per script run, authenticated only for this browser session."""
    url = _secret("url")
    key = _secret("anon_key") or _secret("key")

    if not url or not key:
        st.error(
            "Add your Supabase URL and anon key to `.streamlit/secrets.toml` "
            "under `[supabase]` as `url` and `anon_key`."
        )
        st.stop()

    if jwt_role(key) == "service_role":
        st.error(
            "This app is using the Supabase service-role key. Put the anon key in "
            "`.streamlit/secrets.toml` as `anon_key`. Keep the service-role key only "
            "on the alert worker."
        )
        st.stop()

    client = create_client(url, key)
    access = st.session_state.get("access_token")
    refresh = st.session_state.get("refresh_token")
    if access and refresh:
        try:
            client.postgrest.auth(access)
            barred = client.rpc("account_barred").execute()
        except Exception:
            barred = None
        if barred is not None and _flag_is_true(barred.data):
            try:
                client.auth.set_session(access, refresh)
                client.auth.sign_out()
            except Exception:
                pass
            st.session_state.auth_error = _BARRED_NOTICE
            st.session_state.user = None
            st.session_state.access_token = None
            st.session_state.refresh_token = None
            st.session_state.pop("cloud_prefs", None)
            st.session_state.pop("profile", None)
            st.session_state.pop("prefs_user", None)
            return create_client(url, key)
        if refresh == _POPOUT_MARK:
            # A pop-out tab borrows the main tab's short-lived access token and never
            # refreshes it, so the two tabs cannot invalidate each other's login.
            return client
        try:
            restored = client.auth.set_session(access, refresh)
            fresh = getattr(restored, "session", None)
            if fresh is not None and fresh.access_token and fresh.refresh_token:
                if fresh.refresh_token != refresh:
                    # The sign-in had run out (for example a page left idle for over an hour),
                    # so set_session swapped in a new refresh token. The saved "Keep me
                    # signed in" copy must follow, or the next page load cannot restore it.
                    _store_session_tokens(fresh.access_token, fresh.refresh_token)
                else:
                    st.session_state.access_token = fresh.access_token
                    st.session_state.refresh_token = fresh.refresh_token
        except Exception as exc:
            st.session_state.user = None
            st.session_state.access_token = None
            st.session_state.refresh_token = None
            if "banned" in str(exc).lower():
                st.session_state.auth_error = _BARRED_NOTICE
            client = create_client(url, key)
    return session_guard.FreshClient(
        client,
        get_tokens=lambda: (st.session_state.get("access_token"), st.session_state.get("refresh_token")),
        store_tokens=_store_session_tokens,
        in_page_thread=_in_page_thread,
        skip_refresh=lambda refresh: refresh == _POPOUT_MARK,
        on_failure=_session_failed,
    )


def _store_session_tokens(access: str, refresh: str) -> None:
    st.session_state.access_token = access
    st.session_state.refresh_token = refresh
    if st.session_state.get("_keep_signed_in") and refresh and refresh != _POPOUT_MARK:
        _keep_cookie_write(refresh)  # the refresh token changed, so the saved copy must too


def _session_failed(exc: Exception) -> None:
    """A refresh token works once. If it was already used, another tab took this login over."""
    text = str(exc).lower()
    if "invalid refresh token" not in text and "already used" not in text:
        return
    st.session_state.user = None
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state["_keep_signed_in"] = False
    for name in ("cloud_prefs", "profile", "prefs_user"):
        st.session_state.pop(name, None)
    st.session_state.auth_error = "You were signed out because this account was opened in another tab. Log in again here."
    st.rerun()


def _in_page_thread() -> bool:
    """True on the thread that draws the page. Background jobs run on others and must not refresh."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


def clear_session():
    st.session_state["_keep_clear"] = True
    st.session_state["_keep_signed_in"] = False
    saved_now = (st.session_state.get("cloud_prefs") or {}).get("settings") or {}
    close_popouts = st.session_state.get(
        "popouts_close_on_logout", saved_now.get("popouts_close_on_logout", True)
    )
    st.session_state["_announce_logout_keep"] = not bool(close_popouts)
    st.session_state["_announce_logout"] = str(time.time_ns())
    st.session_state.user = None
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.pop("cloud_prefs", None)
    st.session_state.pop("profile", None)
    st.session_state.pop("prefs_user", None)


def _signup_open() -> bool:
    """True when anyone may create an account. Closed (False) unless the database says otherwise."""
    cached = st.session_state.get("_signup_open_seen")
    if cached and time.time() - cached[0] < 60:
        return bool(cached[1])
    try:
        result = supabase.rpc("signup_is_open").execute()
        opened = _flag_is_true(result.data)
    except Exception:
        opened = False
    st.session_state["_signup_open_seen"] = (time.time(), opened)
    return opened


def _email_is_barred(address: str) -> bool:
    """True when this address is on the blacklist. A missing function is not a bar."""
    clean = _clean_invite_email(address)
    if not clean:
        return False
    try:
        result = supabase.rpc("email_is_barred", {"address": clean}).execute()
    except Exception:
        return False
    return _flag_is_true(result.data)


def _end_barred_session() -> None:
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    clear_session()
    st.session_state.auth_error = _BARRED_NOTICE
    st.rerun()


def _session_is_barred() -> bool:
    try:
        result = supabase.rpc("account_barred").execute()
    except Exception:
        return False
    return _flag_is_true(result.data)


# Widget values stay in the browser session after logout. The next person to
# sign in on that same page would otherwise see them and save them as their own.
_ACCOUNT_STATE_KEYS = (
    "popouts_close_on_logout",
    "popouts_as_window",
    "popouts_fold_section",
    "show_reasons",
    "show_extra_metrics",
    "show_period_changes",
    "days_history",
    "trade_markets",
    "section_layout",
    "wide_split",
    "reset_weights",
    "chart_pick",
    "chart_pick_from_row",
    "asset_type",
    "asset_crypto",
    "asset_stock",
    "alert_enabled_cb",
    "min_score_slider",
    "max_score_slider",
    "profile_display_name",
    "profile_bio",
    "invite_email",
    "load_profile_sb",
    "_seen_trade_markets",
    "_seen_show_reasons",
    "_seen_show_extra_metrics",
    "_seen_show_period_changes",
    "_seen_days_history",
    "colour_page_day",
    "colour_page_night",
    "colour_heading_day",
    "colour_heading_night",
    "colour_section_day",
    "colour_section_night",
    "colour_hover_day",
    "colour_hover_night",
    "colour_sidebar_day",
    "colour_sidebar_night",
    "colour_social_day",
    "colour_social_night",
    "colour_border_day",
    "colour_border_night",
    "score_visit_baseline",
    "score_visit_seen",
    "score_visit_saved",
)
_WEIGHT_NAMES = (
    "rsi", "stochastic", "sma", "adx", "macd", "ichimoku", "bb", "volume", "obv", "performance",
)


def _use_account(account_id: str) -> None:
    """Drop the previous account's choices so this login loads its own."""
    if st.session_state.get("prefs_user") == account_id:
        return
    for key in _ACCOUNT_STATE_KEYS:
        st.session_state.pop(key, None)
    for name in _WEIGHT_NAMES:
        st.session_state.pop(f"weight_{name}", None)
    for section_id in _SECTION_IDS:
        st.session_state.pop(f"sec_{section_id}", None)
    st.session_state.pop("section_pins", None)
    st.session_state.pop("section_fold", None)
    st.session_state.pop("cloud_prefs", None)
    st.session_state.pop("profile", None)
    st.session_state.prefs_user = account_id


def _app_url() -> str:
    """The address in the browser, without a query or hash. Used in the reset mail."""
    try:
        url = str(st.context.url or "").strip()
    except Exception:
        url = ""
    if url.startswith("http"):
        return url.split("#", 1)[0].split("?", 1)[0]
    return "https://app.angstromsignals.com"


def _reset_link_error(raw: str) -> str:
    return "That reset link has expired. Request a new one."


def _google_oauth() -> tuple[str, str]:
    """The Google sign-in address, and the matching secret that finishes it on return."""
    response = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {"redirect_to": _app_url(), "scopes": "email profile"},
    })
    verifier = supabase.auth._storage.get_item(f"{supabase.auth._storage_key}-code-verifier") or ""
    return response.url, verifier


def _sign_in_from_tokens(access: str, refresh: str) -> None:
    supabase.auth.set_session(access, refresh)
    session = supabase.auth.get_session()
    if session is None:
        raise RuntimeError("missing session")
    st.session_state.user = session.user
    st.session_state.access_token = session.access_token
    st.session_state.refresh_token = session.refresh_token
    st.session_state.pop("recovery_access", None)
    st.session_state.pop("recovery_refresh", None)
    st.session_state.pop("recovery_error", None)
    st.session_state.pop("auth_error", None)
    st.session_state.pop("google_url", None)
    st.session_state.pop("google_verifier", None)
    st.rerun()


def _note_auth_error(raw: str, link_type: str = "") -> None:
    text = " ".join(str(raw or "").replace("+", " ").split()).lower()
    if "banned" in text:
        st.session_state.auth_error = _BARRED_NOTICE
        return
    if "database error saving new user" in text or "closed beta" in text:
        st.session_state.auth_error = _CLOSED_BETA_NOTICE
        return
    if link_type == "recovery" or "otp" in text:
        st.session_state.recovery_error = _reset_link_error(raw)
        return
    st.session_state.auth_error = (
        "That sign-in did not finish. Switch this provider on in Supabase, then try again."
    )


def _take_password_reset(google_verifier: str = "") -> None:
    """Keep a recovery session from the reset link, then drop it from the address."""
    token_hash = str(st.query_params.get("token_hash") or "")
    link_type = str(st.query_params.get("type") or "")
    query_error = str(
        st.query_params.get("error_description") or st.query_params.get("error_code") or ""
    )
    if token_hash and link_type == "recovery":
        try:
            response = supabase.auth.verify_otp({"token_hash": token_hash, "type": "recovery"})
            session = response.session
            if session is not None:
                st.session_state.recovery_access = session.access_token
                st.session_state.recovery_refresh = session.refresh_token
            else:
                st.session_state.recovery_error = _reset_link_error("")
        except Exception:
            st.session_state.recovery_error = _reset_link_error("")
    elif query_error:
        _note_auth_error(query_error, link_type)
    for name in ("token_hash", "type", "error", "error_code", "error_description"):
        if name in st.query_params:
            del st.query_params[name]

    ready = bool(st.session_state.get("recovery_access") or st.session_state.get("recovery_error"))
    result = _recovery_link(
        key="password_recovery",
        data={"clear": ready, "verifier": google_verifier},
        on_recovery_change=lambda: None,
        on_oauth_change=lambda: None,
    )
    oauth_payload = getattr(result, "oauth", None)
    if oauth_payload and not st.session_state.get("recovery_access"):
        try:
            oauth_data = json.loads(oauth_payload)
        except Exception:
            oauth_data = None
        code = str((oauth_data or {}).get("code") or "") if isinstance(oauth_data, dict) else ""
        verifier = str((oauth_data or {}).get("verifier") or "") if isinstance(oauth_data, dict) else ""
        if "code" in st.query_params:
            del st.query_params["code"]
        if code and verifier:
            session = None
            try:
                response = supabase.auth.exchange_code_for_session({
                    "auth_code": code,
                    "code_verifier": verifier,
                })
                session = response.session
            except Exception:
                session = None
            if session is not None and session.user and session.access_token and session.refresh_token:
                st.session_state.user = session.user
                st.session_state.access_token = session.access_token
                st.session_state.refresh_token = session.refresh_token
                st.session_state.pop("recovery_access", None)
                st.session_state.pop("recovery_refresh", None)
                st.session_state.pop("recovery_error", None)
                st.session_state.pop("auth_error", None)
                st.session_state.pop("google_url", None)
                st.session_state.pop("google_verifier", None)
                st.rerun()
            else:
                st.session_state.auth_error = "Google sign-in did not finish. Please try again."
        elif code:
            st.session_state.auth_error = "Google sign-in did not finish. Please try again."
    payload = getattr(result, "recovery", None)
    if not payload or st.session_state.get("recovery_access"):
        return
    try:
        data = json.loads(payload)
    except Exception:
        return
    if not isinstance(data, dict):
        return
    access = str(data.get("access") or "")
    refresh = str(data.get("refresh") or "")
    link_type = str(data.get("type") or "")
    if data.get("error") and not (access and refresh):
        _note_auth_error(str(data.get("error")), link_type)
        return
    if link_type == "recovery" and access and refresh:
        st.session_state.recovery_access = access
        st.session_state.recovery_refresh = refresh
        st.session_state.pop("recovery_error", None)
        st.session_state.pop("auth_error", None)
        return
    if access and refresh:
        try:
            _sign_in_from_tokens(access, refresh)
        except Exception:
            st.session_state.auth_error = (
                "That sign-in did not finish. Switch this provider on in Supabase, then try again."
            )


if "user" not in st.session_state:
    st.session_state.user = None
if st.session_state.user is not None and not st.session_state.get("access_token"):
    st.session_state.user = None
if "data_nonce" not in st.session_state:
    st.session_state.data_nonce = 0

supabase = get_supabase()

if st.session_state.user is not None and _session_is_barred():
    _end_barred_session()

if st.session_state.user is not None and st.session_state.pop("_keep_write_pending", False):
    if st.session_state.get("refresh_token") != _POPOUT_MARK:
        if st.session_state.get("_keep_signed_in"):
            _keep_cookie_write(str(st.session_state.get("refresh_token") or ""), pref="1")
        else:
            _keep_cookie_write("", pref="0")  # logged in without the tick: remember that choice too

if st.session_state.user is None and not _POPOUT_VIEW and not st.session_state.get("_keep_tried"):
    # A fresh page load with no login: use the saved sign-in, if the person asked for one.
    st.session_state["_keep_tried"] = True
    _saved_login = _keep_cookie_read()
    if _saved_login:
        try:
            _restored = supabase.auth.refresh_session(_saved_login)
            _session = getattr(_restored, "session", None)
            _member = getattr(_restored, "user", None) or getattr(_session, "user", None)
            if _session is None or _member is None or not _session.access_token or not _session.refresh_token:
                raise RuntimeError("no session")
            st.session_state.user = _member
            st.session_state.access_token = _session.access_token
            st.session_state.refresh_token = _session.refresh_token
            st.session_state["_keep_signed_in"] = True
            st.session_state["_keep_write_pending"] = True
            st.rerun()
        except Exception:
            _keep_cookie_write("")  # that saved sign-in no longer works

def _take_handoff() -> None:
    """A pop-out tab has no login yet. Ask the signed-in tab in this browser for one."""
    reported = _handoff_ask(
        key="handoff_ask",
        data={"current": ""},
        on_token_change=lambda: None,
        on_none_change=lambda: None,
    )
    token = str(getattr(reported, "token", "") or "")
    if token:
        member = None
        try:
            member = supabase.auth.get_user(token).user
        except Exception:
            member = None
        if member is not None:
            st.session_state.user = member
            st.session_state.access_token = token
            st.session_state.refresh_token = _POPOUT_MARK
            st.session_state.pop("auth_error", None)
        else:
            st.session_state.popout_handoff_failed = True
        st.rerun()
    if getattr(reported, "none", None):
        st.session_state.popout_handoff_failed = True
        st.rerun()
    st.caption("Connecting this tab to your signed-in dashboard tab...")
    st.stop()


if st.session_state.user is None and _POPOUT_VIEW and not st.session_state.get("popout_handoff_failed"):
    _take_handoff()

if st.session_state.user is None:
    _social_clear(key="social_clear")
    if st.session_state.pop("_keep_clear", False):
        _keep_cookie_write("")
    if st.session_state.get("_announce_logout") and not _POPOUT_VIEW:
        _logout_cast(
            key="logout_cast",
            data={
                "n": st.session_state["_announce_logout"],
                "keep": bool(st.session_state.get("_announce_logout_keep")),
            },
        )
    if not st.session_state.get("google_url") or not st.session_state.get("google_verifier"):
        st.session_state.google_url, st.session_state.google_verifier = _google_oauth()
    google_url = st.session_state.google_url
    google_verifier = st.session_state.google_verifier
    _take_password_reset(google_verifier)
    _brand_watch(key="brand_watch")
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    _, col_center, _ = st.columns([1, 1.2, 1])

    with col_center:
        st.markdown(_brand_mark(200), unsafe_allow_html=True)
        st.title("angstrom signals")
        st.caption("Market sentiment and technical signals, with the crowd alongside.")

        if st.session_state.get("recovery_access"):
            st.markdown("### Choose a new password")
            new_password = st.text_input("New password", type="password", key="recover_password")
            new_password_again = st.text_input(
                "Repeat the new password", type="password", key="recover_password_again",
            )
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            if st.button("Save password", type="primary", use_container_width=True, key="recover_save"):
                if len(new_password) < 6:
                    st.error("Use at least 6 characters.")
                elif new_password != new_password_again:
                    st.error("Those passwords do not match.")
                else:
                    try:
                        supabase.auth.set_session(
                            st.session_state.recovery_access,
                            st.session_state.recovery_refresh,
                        )
                        supabase.auth.update_user({"password": new_password})
                        session = supabase.auth.get_session()
                        if session is None:
                            raise RuntimeError("missing session")
                        st.session_state.user = session.user
                        st.session_state.access_token = session.access_token
                        st.session_state.refresh_token = session.refresh_token
                        st.session_state.pop("recovery_access", None)
                        st.session_state.pop("recovery_refresh", None)
                        st.session_state.pop("recovery_error", None)
                        st.session_state.show_recover = False
                        st.rerun()
                    except Exception as exc:
                        code = str(getattr(exc, "code", "") or "")
                        if code == "weak_password":
                            st.error("Choose a longer password.")
                        elif code == "same_password":
                            st.session_state.pop("recovery_access", None)
                            st.session_state.pop("recovery_refresh", None)
                            st.session_state.recovery_error = "That is already the password. Log in with it."
                            st.rerun()
                        else:
                            st.session_state.pop("recovery_access", None)
                            st.session_state.pop("recovery_refresh", None)
                            st.session_state.recovery_error = _reset_link_error("")
                            st.rerun()
        else:
            signup_open = _signup_open()
            auth_tab1, auth_tab2 = st.tabs(["🔑 Log In", "📝 Sign Up" if signup_open else "✅ Beta Access Accepted?"])

        if not st.session_state.get("recovery_access"):
            with auth_tab1:
                if st.session_state.get("recovery_error") and not st.session_state.get("show_recover"):
                    st.error(st.session_state.recovery_error)
                if st.session_state.get("show_recover"):
                    st.markdown("### Reset password")
                    st.caption("We'll email a link. Check junk mail if it does not arrive.")
                    recover_email = st.text_input("Email", key="recover_email")
                    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                    if st.button("Send reset link", type="primary", use_container_width=True, key="recover_send"):
                        email = " ".join(str(recover_email or "").split())
                        if not email:
                            st.error("Enter the email on the account.")
                        else:
                            try:
                                supabase.auth.reset_password_for_email(email, {"redirect_to": _app_url()})
                                st.session_state.recover_sent = True
                            except Exception as exc:
                                code = str(getattr(exc, "code", "") or "")
                                if code == "over_email_send_rate_limit":
                                    st.error("The reset mail is limited for a while. Wait a few minutes and try again.")
                                else:
                                    st.error("The reset mail could not be sent. Try again in a few minutes.")
                    if st.session_state.get("recover_sent"):
                        st.success("If that email has an account, the reset link is on its way.")
                    if st.button("Back to log in", use_container_width=True, key="recover_back"):
                        st.session_state.show_recover = False
                        st.session_state.recover_sent = False
                        st.rerun()
                else:
                    st.markdown("### Welcome Back")
                    with st.form("login", border=False):
                        login_email = st.text_input(
                            "Email",
                            key="login_email",
                            type="email",
                            autocomplete="username",
                            icon="",
                            placeholder="",
                        )
                        login_password = st.text_input(
                            "Password",
                            type="password",
                            key="login_password",
                            autocomplete="current-password",
                        )
                        if "login_keep" not in st.session_state:
                            st.session_state["login_keep"] = _keep_pref_read()
                        keep_me = st.checkbox(
                            "Keep me signed in on this device",
                            key="login_keep",
                            help="Stay signed in for up to 30 days, even after you close this tab. Do not tick this on a shared computer.",
                        )
                        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                        submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)
                    if submitted:
                        try:
                            response = supabase.auth.sign_in_with_password({
                                "email": login_email,
                                "password": login_password,
                            })
                            session = response.session
                            if session is None:
                                st.error("Login did not return a session. Confirm your email, then try again.")
                            else:
                                st.session_state.user = response.user
                                st.session_state.access_token = session.access_token
                                st.session_state.refresh_token = session.refresh_token
                                st.session_state["_keep_signed_in"] = bool(keep_me)
                                st.session_state["_keep_write_pending"] = True
                                st.rerun()
                        except Exception as exc:
                            if "banned" in str(exc).lower():
                                st.error(_BARRED_NOTICE)
                            else:
                                st.error("Login failed. Check your email and password.")
                    if st.button("Forgot password?", use_container_width=True, key="forgot_password"):
                        st.session_state.recover_email = st.session_state.get("login_email", "")
                        st.session_state.show_recover = True
                        st.session_state.recover_sent = False
                        st.session_state.pop("recovery_error", None)
                        st.rerun()

            with auth_tab2:
                if signup_open:
                    st.markdown("### Create New Account")
                else:
                    st.markdown("### Invited to the beta?")
                    st.caption(
                        "Angstrom Signals is invite-only while we build with experienced traders. "
                        "If you have been accepted, create your account here with the email you applied with. "
                        "Not invited yet? Request access at angstromsignals.com."
                    )
                with st.form("signup", border=False):
                    signup_email = st.text_input(
                        "Email",
                        key="signup_email",
                        type="email",
                        autocomplete="email",
                        icon="",
                        placeholder="",
                    )
                    signup_password = st.text_input(
                        "Password",
                        type="password",
                        key="signup_password",
                        autocomplete="new-password",
                    )
                    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                    created = st.form_submit_button(
                        "Create Account" if signup_open else "Create my account",
                        type="primary",
                        use_container_width=True,
                    )
                if created:
                    if _email_is_barred(signup_email):
                        st.error(_BARRED_NOTICE)
                    else:
                        try:
                            supabase.auth.sign_up({
                                "email": signup_email,
                                "password": signup_password,
                            })
                            st.success("Account created. Confirm the email if required, then log in.")
                        except Exception as exc:
                            if "banned" in str(exc).lower():
                                st.error(_BARRED_NOTICE)
                            elif not signup_open:
                                st.error(_CLOSED_BETA_NOTICE)
                            else:
                                st.error("Sign up failed. Try a different email, or a longer password.")

            if st.session_state.get("auth_error"):
                st.error(st.session_state.auth_error)
            st.caption("Or continue with")
            _google_button(
                key="google_sign_in",
                data={"url": google_url, "verifier": google_verifier},
            )

    st.stop()


user_id = st.session_state.user.id
_use_account(user_id)


def _favourite_ids(raw) -> list[str]:
    """Account ids saved as favourites. Blank, your own id, and anything else are left out."""
    if not isinstance(raw, list):
        return []
    own = str(user_id or "").strip().lower()
    seen = []
    for item in raw:
        text = str(item or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text):
            continue
        if text == own or text in seen:
            continue
        seen.append(text)
    return seen[:100]


def load_user_preferences():
    default_crypto = {
        "bitcoin": "Bitcoin (BTC)",
        "ethereum": "Ethereum (ETH)",
        "solana": "Solana (SOL)",
        "cardano": "Cardano (ADA)",
        "ripple": "XRP",
        "polkadot": "Dot",
        "sui": "Sui",
    }
    default_stock = {
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "NVDA": "NVIDIA",
        "TSLA": "Tesla",
        "GOOGL": "GOOGL",
    }
    default_weights = {
        "rsi": 1.0, "stochastic": 1.0, "sma": 1.0, "adx": 1.0,
        "macd": 1.0, "ichimoku": 1.0, "bb": 1.0, "volume": 1.0, "obv": 1.0, "performance": 1.0,
    }
    default_settings = {
        "days_history": 200,
        "show_reasons": True,
        "show_extra_metrics": True,
        "show_period_changes": True,
        "trade_crypto": True,
        "trade_equities": True,
    }

    try:
        response = supabase.table("user_preferences").select("*").eq("user_id", user_id).execute()
        data = response.data

        if data and len(data) > 0:
            row = data[0]
            prefs_dict = {
                "crypto": row.get("crypto_watchlist") or default_crypto,
                "stock": row.get("stock_watchlist") or default_stock,
                "weights": row.get("scoring_weights") or default_weights,
                "profiles": row.get("weight_profiles") or {},
                "settings": row.get("settings") or default_settings,
            }
        else:
            initial_row = {
                "user_id": user_id,
                "crypto_watchlist": default_crypto,
                "stock_watchlist": default_stock,
                "scoring_weights": default_weights,
                "weight_profiles": {},
                "settings": default_settings,
            }
            supabase.table("user_preferences").insert(initial_row).execute()
            prefs_dict = {
                "crypto": default_crypto,
                "stock": default_stock,
                "weights": default_weights,
                "profiles": {},
                "settings": default_settings,
            }

        alert_res = supabase.table("alert_preferences").select("*").eq("user_id", user_id).execute()
        if alert_res.data and len(alert_res.data) > 0:
            prefs_dict["alerts"] = alert_res.data[0]
        else:
            basic_alerts = {
                "user_id": user_id,
                "enabled": True,
                "min_score_alert": 70,
                "max_score_alert": 30,
            }
            # New accounts: asset and market alerts on, delivered as one daily digest
            # at 08:00 in the browser's time zone, with no instant emails.
            default_alerts = dict(basic_alerts)
            default_alerts.update({
                "market_alerts_enabled": True,
                "instant_email": False,
                "digest_enabled": True,
                "digest_hour": 8,
            })
            try:
                browser_zone = str(getattr(st.context, "timezone", "") or "")
            except Exception:
                browser_zone = ""
            # Unset until the browser reports its zone; the settings panel fills it in.
            default_alerts["digest_tz"] = browser_zone or None
            try:
                inserted = supabase.table("alert_preferences").insert(default_alerts).execute()
            except Exception:
                # The newer columns are missing until supabase_rls.sql is re-run.
                default_alerts = basic_alerts
                inserted = supabase.table("alert_preferences").insert(default_alerts).execute()
            # The stored row carries the column defaults, so every setting shows at once.
            prefs_dict["alerts"] = (inserted.data or [default_alerts])[0]

        return prefs_dict

    except Exception as exc:
        st.error(f"Error loading cloud preferences: {exc}")
        return {
            "crypto": default_crypto,
            "stock": default_stock,
            "weights": default_weights,
            "profiles": {},
            "settings": default_settings,
            "alerts": {"enabled": True, "min_score_alert": 70, "max_score_alert": 30},
        }


def save_preferences_to_cloud(updates: dict):
    try:
        supabase.table("user_preferences").update(updates).eq("user_id", user_id).execute()
    except Exception as exc:
        st.error(f"Error saving preferences to cloud: {exc}")


def save_account_settings(updates: dict) -> None:
    """Merge choices into this account's settings. Other keys stay put."""
    prefs_now = st.session_state.get("cloud_prefs")
    if not isinstance(prefs_now, dict):
        return
    stored = prefs_now.get("settings")
    if not isinstance(stored, dict):
        stored = {}
        prefs_now["settings"] = stored
    changed = False
    for key, value in updates.items():
        if stored.get(key) != value:
            stored[key] = value
            changed = True
    if changed:
        save_preferences_to_cloud({"settings": stored})


def account_panel() -> dict:
    """The social panel size saved on this account."""
    stored = (st.session_state.get("cloud_prefs") or {}).get("settings") or {}
    try:
        width = int(stored.get("stream_width") or 420)
    except (TypeError, ValueError):
        width = 420
    width = min(900, max(320, width))
    try:
        split = float(stored.get("stream_split") or 0.5)
    except (TypeError, ValueError):
        split = 0.5
    if not 0.08 < split < 0.92:
        split = 0.5
    return {
        "width": width,
        "split": round(split, 3),
        "pinned": bool(stored.get("stream_pinned", False)),
        "layout": "side" if stored.get("stream_layout") == "side" else "stacked",
    }


def save_alert_preferences_to_cloud(updates: dict):
    try:
        supabase.table("alert_preferences").update(updates).eq("user_id", user_id).execute()
    except Exception as exc:
        st.error(f"Error saving alert preferences: {exc}")


def _member_ids(raw) -> list[str]:
    if isinstance(raw, list):
        parts = [str(item) for item in raw if item]
    else:
        text = str(raw or "").strip().strip("{}")
        parts = [part.strip().strip('"') for part in text.split(",") if part.strip()]
    return [part.strip().lower() for part in parts if part.strip()]


def _load_my_groups():
    """Groups this account leads or belongs to. None when the functions are not installed."""
    try:
        response = supabase.rpc("my_groups").execute()
    except Exception:
        return None
    return response.data or []


def _groups_for_stream() -> list[dict]:
    rows = _load_my_groups() or []
    cleaned = []
    for row in rows:
        try:
            gid = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        cleaned.append({
            "id": gid,
            "name": " ".join(str(row.get("name") or "").split())[:40] or "Group",
            "lead": bool(row.get("is_leader")),
            "leader": " ".join(str(row.get("leader_name") or "").split())[:40],
            "members": _member_ids(row.get("members")),
        })
    return cleaned


def fetch_user_notifications():
    try:
        supabase.rpc("expire_my_group_invites").execute()
    except Exception:
        pass
    try:
        res = (
            supabase.table("user_notifications")
            .select("*")
            .eq("user_id", user_id)
            .not_.in_("alert_type", [HELD_BULLISH, HELD_BEARISH])
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        rows = list(res.data or [])
    except Exception:
        return []
    try:
        extra = (
            supabase.table("user_notifications")
            .select("*")
            .eq("user_id", user_id)
            .in_("alert_type", ["group_invite", "moderation_warning", "report_update"])
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
    except Exception:
        extra = None
    seen = {row.get("id") for row in rows}
    for row in (getattr(extra, "data", None) or []):
        if row.get("id") not in seen:
            rows.append(row)
    rows = [
        row for row in rows
        if str(row.get("alert_type") or "") not in (HELD_BULLISH, HELD_BEARISH)
    ]
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return rows


def load_profile():
    try:
        response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
        if response.data:
            return response.data[0]
    except Exception:
        return None
    return {}


def save_profile(updates: dict):
    payload = {
        "user_id": user_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **updates,
    }
    supabase.table("profiles").upsert(payload).execute()


def upload_avatar(uploaded) -> str:
    if uploaded.size > 5_000_000:
        raise ValueError("Use a photo smaller than 5 MB.")
    from PIL import Image

    image = Image.open(io.BytesIO(uploaded.getvalue())).convert("RGB")
    image.thumbnail((512, 512))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    path = f"{user_id}/avatar.jpg"
    bucket = supabase.storage.from_("avatars")
    file_options = {"content-type": "image/jpeg", "upsert": "true"}
    try:
        bucket.upload(path, buffer.getvalue(), file_options)
    except Exception:
        bucket.update(path, buffer.getvalue(), {"content-type": "image/jpeg"})
    public_url = bucket.get_public_url(path)
    return f"{public_url}?v={int(time.time())}"


def profile_card(profile: dict, email: str) -> str:
    name = (profile or {}).get("display_name") or email.split("@")[0]
    bio = ((profile or {}).get("bio") or "").strip()
    avatar = (profile or {}).get("avatar_url") or ""
    safe_name = html.escape(name)
    safe_email = html.escape(email)
    if avatar:
        face = (
            f"<img src='{html.escape(avatar, quote=True)}' alt='' "
            "style='width:52px;height:52px;border-radius:50%;object-fit:cover;display:block;'>"
        )
    else:
        initial = html.escape((name[:1] or "?").upper())
        face = (
            "<div style='width:52px;height:52px;border-radius:50%;background:#dbeafe;color:#1d4ed8;"
            "display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.2rem;'>"
            f"{initial}</div>"
        )
    try:
        social_score = int((profile or {}).get("social_score") or 0)
    except (TypeError, ValueError):
        social_score = 0
    bio_html = (
        f"<div class='ang-copy' style='margin-top:8px;font-size:0.85rem;'>{html.escape(bio)}</div>"
        if bio else ""
    )
    return (
        "<div class='ang-card'>"
        "<div style='display:flex;gap:10px;align-items:center;'>"
        f"{face}<div><div class='ang-title' style='display:flex;align-items:center;gap:6px;'>"
        f"{safe_name}<span title='Social score {social_score}' "
        "style='flex:none;font-size:0.68rem;font-weight:600;line-height:1.4;color:var(--ang-muted);"
        "background:var(--ang-line);border-radius:999px;padding:1px 6px;'>✦ "
        f"{social_score}</span></div>"
        f"<div class='ang-kicker' style='margin:0;font-size:0.78rem;'>{safe_email}</div>"
        "</div></div>"
        f"{bio_html}</div>"
    )


def _store_invite(address: str) -> str:
    """Save one invite for this account. 'exists' means that address was already invited."""
    try:
        supabase.table("invites").insert({
            "inviter_id": user_id,
            "email": address,
        }).execute()
    except Exception as exc:
        code = str(getattr(exc, "code", "") or "")
        text = str(exc).lower()
        if code == "23505" or "duplicate" in text:
            return "exists"
        if "invite limit" in text:
            return "limit"
        if "someone else" in text:
            return "self"
        return "error"
    return ""


def _my_invites() -> list:
    """This account's invites, newest first."""
    try:
        response = (
            supabase.table("invites")
            .select("email,created_at,credited_at")
            .eq("inviter_id", user_id)
            .order("created_at", desc=True)
            .limit(12)
            .execute()
        )
    except Exception:
        return []
    return response.data or []


def _settle_social_score() -> None:
    """Award invite points for this new account, then read this account's score."""
    try:
        supabase.rpc("claim_invite_points").execute()
    except Exception:
        pass
    profile_now = st.session_state.get("profile")
    if not isinstance(profile_now, dict):
        return
    try:
        response = (
            supabase.table("profiles")
            .select("social_score")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        row = (response.data or [{}])[0]
        profile_now["social_score"] = int(row.get("social_score") or 0)
    except Exception:
        profile_now.setdefault("social_score", 0)
    st.session_state.profile = profile_now


if "cloud_prefs" not in st.session_state:
    st.session_state.cloud_prefs = load_user_preferences()
if "profile" not in st.session_state:
    st.session_state.profile = load_profile()
_settle_social_score()

prefs = st.session_state.cloud_prefs
alert_prefs = prefs.get("alerts", {})
profile = st.session_state.profile

_THEME_COLOURS = (
    ("page_day", "#d6e8f8"),
    ("page_night", "#0e1117"),
    ("heading_day", "#ffffff"),
    ("heading_night", "#262730"),
    ("section_day", "#ffffff"),
    ("section_night", "#262730"),
    ("hover_day", "#f3f4f6"),
    ("hover_night", "#31333f"),
    ("sidebar_day", "#ffffff"),
    ("sidebar_night", "#16181f"),
    ("social_day", "#ffffff"),
    ("social_night", "#1c1f27"),
    ("border_day", "#e5e7eb"),
    ("border_night", "#000000"),
)


def _hex_colour(value, fallback: str) -> str:
    """A #rrggbb colour, or the fallback when the saved text is not one."""
    text = str(value or "").strip()
    if len(text) == 7 and text.startswith("#") and all(ch in "0123456789abcdefABCDEF" for ch in text[1:]):
        return text.lower()
    return fallback


def _saved_colours() -> dict:
    stored = (st.session_state.get("cloud_prefs") or {}).get("settings")
    saved = stored.get("colours") if isinstance(stored, dict) else None
    if not isinstance(saved, dict):
        saved = {}
    return {key: _hex_colour(saved.get(key), default) for key, default in _THEME_COLOURS}


def _active_colours() -> dict:
    """Picker values when this session has them, otherwise the colours saved on the account."""
    saved = _saved_colours()
    chosen = {}
    for key, _default in _THEME_COLOURS:
        widget = st.session_state.get(f"colour_{key}")
        chosen[key] = _hex_colour(widget, saved[key]) if widget else saved[key]
    return chosen


def _use_colours(colours: dict) -> None:
    """Load a set of colours into the pickers on the next run."""
    st.session_state["_apply_colours"] = dict(colours)


def _saved_colour_slot():
    """The one set of colours this account has saved with Save current, or None."""
    stored = (st.session_state.get("cloud_prefs") or {}).get("settings")
    saved = stored.get("colours_saved") if isinstance(stored, dict) else None
    if not isinstance(saved, dict):
        return None
    return colour_themes.clean_set(saved, dict(_THEME_COLOURS))


def _save_colour_slot() -> None:
    chosen = {
        key: _hex_colour(st.session_state.get(f"colour_{key}"), default)
        for key, default in _THEME_COLOURS
    }
    save_account_settings({"colours_saved": chosen})
    st.toast("Saved. Back to saved will return to these colours.")


def _take_colour_copy() -> None:
    """A drop names the block that should take the dragged colour. One drop applies once."""
    reported = _colour_copy(key="colour_copy", on_copied_change=lambda: None)
    raw = str(getattr(reported, "copied", "") or "")
    parts = raw.split("|")
    if len(parts) != 3 or st.session_state.get("_colour_copy_seen") == raw:
        return
    target, hex_value = parts[0], parts[1]
    if target == "themepick":
        theme = colour_themes.THEMES.get(hex_value)
        if theme:
            st.session_state["_colour_copy_seen"] = raw
            for key, default in _THEME_COLOURS:
                st.session_state[f"colour_{key}"] = _hex_colour(theme.get(key), default)
        return
    allowed = {f"colour_{key}" for key, _default in _THEME_COLOURS}
    cleaned = _hex_colour(hex_value, "")
    if target not in allowed or not cleaned:
        return
    st.session_state["_colour_copy_seen"] = raw
    st.session_state[target] = cleaned


def _colour_payload(chosen: dict) -> dict:
    return {
        "pageDay": chosen["page_day"],
        "pageNight": chosen["page_night"],
        "headingDay": chosen["heading_day"],
        "headingNight": chosen["heading_night"],
        "sectionDay": chosen["section_day"],
        "sectionNight": chosen["section_night"],
        "hoverDay": chosen["hover_day"],
        "hoverNight": chosen["hover_night"],
        "sidebarDay": chosen["sidebar_day"],
        "sidebarNight": chosen["sidebar_night"],
        "socialDay": chosen["social_day"],
        "socialNight": chosen["social_night"],
        "borderDay": chosen["border_day"],
        "borderNight": chosen["border_night"],
    }


if st.session_state.pop("_reset_colours", False):
    for key, default in _THEME_COLOURS:
        st.session_state[f"colour_{key}"] = default
_pending_colours = st.session_state.pop("_apply_colours", None)
if isinstance(_pending_colours, dict):
    for key, default in _THEME_COLOURS:
        st.session_state[f"colour_{key}"] = _hex_colour(_pending_colours.get(key), default)
_take_colour_copy()
account_colours = _active_colours()
_brand_watch(key="brand_watch", data=_colour_payload(account_colours))
st.sidebar.markdown(
    "<div style='margin:0.4rem 0 0.75rem;'>"
    "<div style='display:flex;align-items:center;gap:0.85rem;'>"
    f"{_brand_mark(58, align='left')}"
    "<h1 style='margin:0;padding:0;line-height:1.15;font-size:2.25rem;font-weight:700;'>"
    "angstrom<br>signals</h1></div>"
    "<div style='margin-top:0.55rem;font-size:0.82rem;font-weight:500;line-height:1.35;opacity:0.72;'>"
    "Market sentiment and technical signals, with the crowd alongside.</div></div>",
    unsafe_allow_html=True,
)

@st.fragment
def invite_someone() -> None:
    """Send one invite. This form redraws on its own."""
    st.caption("Know an experienced trader who would suit the beta? We will email them. Seats are approved by our team, and you get 100 social points once they join.")
    address_text = st.text_input(
        "Their email",
        key="invite_email",
        placeholder="name@example.com",
    )
    if st.button("Send invite", key="invite_send", use_container_width=True):
        address = _clean_invite_email(address_text)
        own = _clean_invite_email(getattr(st.session_state.user, "email", "") or "")
        if not address:
            st.warning("Enter a valid email address.")
        elif address == own:
            st.warning("Use someone else's email address.")
        else:
            stored = _store_invite(address)
            if stored == "limit":
                st.warning("The day's invites are used. Try again tomorrow.")
            elif stored == "error":
                st.warning(
                    "That invite could not be saved. Run the latest supabase_rls.sql in Supabase, then try again."
                )
            else:
                inviter = (st.session_state.get("profile") or {}).get("display_name")
                if not inviter:
                    inviter = own.split("@")[0] if own else "Someone"
                sent, reason = _email_invite(address, str(inviter))
                if sent and stored == "exists":
                    st.success("That invite was already saved. The email was sent again.")
                elif sent:
                    st.success("Invite sent.")
                elif stored == "exists":
                    st.warning(f"That invite is already saved. The email was not sent: {reason}.")
                else:
                    st.warning(f"Invite saved. The email was not sent: {reason}.")
    for row in _my_invites():
        state = "Joined" if row.get("credited_at") else "Waiting"
        st.caption(f"{row.get('email') or ''} · {state}")


def _group_member_count(row) -> int:
    return len(_member_ids(row.get("members")))


def _group_people(row) -> list[dict]:
    """People in one group: id, name, and photo. Alphabetical by name."""
    raw = row.get("people")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    if not isinstance(raw, list):
        return []
    people = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        person_id = str(item.get("id") or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", person_id):
            continue
        name = " ".join(str(item.get("name") or "Member").split())[:40] or "Member"
        avatar = str(item.get("avatar") or "").strip()
        if not avatar.startswith("https://") or any(mark in avatar for mark in (" ", '"', "'", "<", ">", "\\")):
            avatar = ""
        people.append({"id": person_id, "name": name, "avatar": avatar})
    people.sort(key=lambda person: person["name"].lower())
    return people


def _person_face(name: str, avatar: str) -> str:
    """A round photo, or the first letter when there is no photo."""
    if avatar:
        return (
            f"<img src='{html.escape(avatar, quote=True)}' alt='' "
            "style='width:32px;height:32px;border-radius:50%;object-fit:cover;display:block;'>"
        )
    initial = html.escape((name[:1] or "?").upper())
    return (
        "<div style='width:32px;height:32px;border-radius:50%;background:#dbeafe;color:#1d4ed8;"
        "display:flex;align-items:center;justify-content:center;font-weight:700;'>"
        f"{initial}</div>"
    )


def _remove_group_member(group_id: int, person_id: str) -> str:
    """Remove one member. Only the leader can, and the leader stays. Empty means it worked."""
    try:
        result = supabase.rpc("remove_group_member", {
            "chosen_group": group_id,
            "person": person_id,
        }).execute()
    except Exception:
        return "That person could not be removed. Run the latest supabase_rls.sql, then try again."
    code = str(result.data or "").strip().strip('"')
    if code == "ok":
        return ""
    if code == "self":
        return "The leader stays until the group is deleted."
    return "That person could not be removed. Run the latest supabase_rls.sql, then try again."


def _group_member_list(row, group_id: int) -> None:
    """Faces and names inside one group. The leader can remove anyone except themselves."""
    people = _group_people(row)
    if not people:
        st.caption("The member list is not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor.")
        return
    leader_id = str(row.get("leader_id") or "").strip().lower()
    is_leader = bool(row.get("is_leader"))
    for person in people:
        remove = False
        with st.container(
            horizontal=True,
            vertical_alignment="center",
            gap="small",
            wrap=False,
            key=f"group_person_{group_id}_{person['id']}",
        ):
            st.markdown(
                _person_face(person["name"], person["avatar"]),
                unsafe_allow_html=True,
                width="content",
            )
            st.markdown(html.escape(person["name"]), width="stretch")
            if person["id"] == leader_id:
                st.markdown(
                    "<span style='color:var(--ang-muted);font-size:0.85rem;'>Leader</span>",
                    unsafe_allow_html=True,
                    width="content",
                )
            elif is_leader:
                remove = st.button(
                    "×",
                    key=f"group_remove_{group_id}_{person['id']}",
                    help="Remove from the group",
                    type="tertiary",
                )
        if not remove:
            continue
        note = _remove_group_member(group_id, person["id"])
        if note:
            st.warning(note)
        else:
            st.rerun()


@st.fragment
def my_groups_panel() -> None:
    """Groups you lead, and groups you belong to. Delete and Leave redraw this section."""
    groups = _load_my_groups()
    if groups is None:
        st.caption("Groups are not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor.")
        return
    led = [row for row in groups if row.get("is_leader")]
    joined = [row for row in groups if not row.get("is_leader")]
    if not led and not joined:
        st.caption("You have no groups yet. Use the people icon beside a name in the social stream.")
        return
    st.markdown(
        "<style>"
        "[class*='st-key-group_fold_'] [data-testid='stMarkdownContainer'] p{margin:0 !important;display:flex;align-items:center;}"
        "[class*='st-key-group_person_']{align-items:center !important;flex-wrap:nowrap !important;}"
        "[class*='st-key-group_person_'] [data-testid='stElementContainer']{align-self:center !important;margin-top:0 !important;margin-bottom:0 !important;display:flex !important;align-items:center !important;}"
        "[class*='st-key-group_person_'] [data-testid='stMarkdownContainer']{margin:0 !important;}"
        "[class*='st-key-group_person_'] [data-testid='stMarkdownContainer'] p{margin:0 !important;line-height:1.2 !important;display:flex;align-items:center;}"
        "[class*='st-key-group_remove_'] button,[class*='st-key-group_xdelete_'] button{color:#b91c1c !important;background:transparent !important;"
        "border:none !important;box-shadow:none !important;font-size:2.16rem !important;font-weight:700 !important;"
        "line-height:1 !important;min-height:0 !important;height:2.16rem !important;padding:0 !important;"
        "display:inline-flex !important;align-items:center !important;justify-content:center !important;}"
        "[class*='st-key-group_remove_'] button *,[class*='st-key-group_xdelete_'] button *{font-size:2.16rem !important;line-height:1 !important;color:#b91c1c !important;}"
        "[class*='st-key-group_leave_'] button{width:1.728rem !important;height:1.728rem !important;min-width:0 !important;min-height:0 !important;"
        "padding:0 !important;border:none !important;box-shadow:none !important;background-color:transparent !important;"
        "background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23b91c1c' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4'/%3E%3Cpolyline points='16 17 21 12 16 7'/%3E%3Cline x1='21' y1='12' x2='9' y2='12'/%3E%3C/svg%3E\") !important;"
        "background-repeat:no-repeat !important;background-position:center !important;background-size:1.728rem 1.728rem !important;"
        "color:transparent !important;font-size:0 !important;}"
        "[class*='st-key-group_leave_'] button *{font-size:0 !important;color:transparent !important;}"
        "</style>",
        unsafe_allow_html=True,
    )
    if led:
        st.caption("Groups you lead")
        for row in led:
            try:
                gid = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            name = " ".join(str(row.get("name") or "").split()) or "Group"
            count = _group_member_count(row)
            detail = f"{count} member" if count == 1 else f"{count} members"
            delete_group = False
            with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                with st.expander(f"{name} · {detail}", expanded=False, key=f"group_fold_{gid}"):
                    _group_member_list(row, gid)
                delete_group = st.button(
                    "×",
                    key=f"group_xdelete_{gid}",
                    help="Delete this group",
                    type="tertiary",
                )
            if delete_group:
                st.session_state["group_delete_id"] = gid
            if st.session_state.get("group_delete_id") == gid:
                st.caption("Delete this group? Members will lose it.")
                yes, no = st.columns(2)
                if yes.button("Delete group", key=f"group_delete_yes_{gid}", use_container_width=True):
                    try:
                        supabase.rpc("delete_my_group", {"chosen_group": gid}).execute()
                    except Exception:
                        st.warning("That group could not be deleted. Run the latest supabase_rls.sql, then try again.")
                    else:
                        st.session_state.pop("group_delete_id", None)
                        st.rerun()
                if no.button("Cancel", key=f"group_delete_no_{gid}", use_container_width=True):
                    st.session_state.pop("group_delete_id", None)
                    _rerun_fragment()
    if joined:
        st.caption("Groups you belong to")
        for row in joined:
            try:
                gid = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            name = " ".join(str(row.get("name") or "").split()) or "Group"
            leader = " ".join(str(row.get("leader_name") or "").split())
            label = f"{name} · {leader}" if leader else name
            leave_group = False
            with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                with st.expander(label, expanded=False, key=f"group_fold_{gid}"):
                    _group_member_list(row, gid)
                leave_group = st.button(
                    "Leave",
                    key=f"group_leave_{gid}",
                    help="Leave group",
                    type="tertiary",
                )
            if leave_group:
                st.session_state["group_leave_id"] = gid
            if st.session_state.get("group_leave_id") == gid:
                st.caption("Leave this group?")
                yes, no = st.columns(2)
                if yes.button("Leave group", key=f"group_leave_yes_{gid}", use_container_width=True):
                    try:
                        supabase.rpc("leave_group", {"chosen_group": gid}).execute()
                    except Exception:
                        st.warning("Could not leave that group. Run the latest supabase_rls.sql, then try again.")
                    else:
                        st.session_state.pop("group_leave_id", None)
                        st.rerun()
                if no.button("Cancel", key=f"group_leave_no_{gid}", use_container_width=True):
                    st.session_state.pop("group_leave_id", None)
                    _rerun_fragment()


with tracked_expander("👤 Account", "account", sidebar=True):
    if profile is None:
        st.warning("Profile storage is not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor.")
        profile = {}
    st.markdown(profile_card(profile, st.session_state.user.email or ""), unsafe_allow_html=True)
    with tracked_expander("Edit profile", "edit_profile"):
        profile_name = st.text_input(
            "Display name",
            value=profile.get("display_name") or "",
            max_chars=40,
            key="profile_display_name",
        )
        profile_bio = st.text_area(
            "Short bio",
            value=profile.get("bio") or "",
            max_chars=160,
            height=80,
            key="profile_bio",
            placeholder="A line about you, for when social features arrive.",
        )
        profile_photo = st.file_uploader(
            "Profile photo",
            type=["png", "jpg", "jpeg", "webp"],
            key="profile_photo",
        )
        if profile.get("avatar_url"):
            st.caption("A new photo replaces the current one.")
        if st.button("Save profile", use_container_width=True):
            updates = {
                "display_name": profile_name.strip() or None,
                "bio": profile_bio.strip() or None,
            }
            try:
                if profile_photo is not None:
                    updates["avatar_url"] = upload_avatar(profile_photo)
                save_profile(updates)
                st.session_state.profile = {**profile, **updates}
                st.success("Profile saved.")
                st.rerun()
            except Exception as exc:
                st.error(
                    "Could not save the profile. If this is the first time, "
                    f"run the latest supabase_rls.sql in Supabase. {exc}"
                )

    with tracked_expander("Invite", "invite"):
        invite_someone()

    if st.button("Log Out", use_container_width=True):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        clear_session()
        st.rerun()

with tracked_expander("👥 My Groups", "my_groups", sidebar=True):
    my_groups_panel()

def tone(score):
    """Text color, badge background, arrow, and bar color for a score."""
    if score is None or pd.isna(score):
        return "#6b7280", "#f3f4f6", "—", "#6b7280"
    if score >= 53:
        return "#15803d", "#dcfce7", "↑", "#22c55e"
    if score >= 47:
        return "#b45309", "#fef3c7", "→", "#f59e0b"
    return "#b91c1c", "#fee2e2", "↓", "#ef4444"


def _sync_table_crowd(kind: str, asset_id: str, voice: dict) -> None:
    """Write this asset's fresh crowd numbers into the scores table already on the page."""
    if str(kind) not in ("Crypto", "Stock"):
        return
    try:
        balance = int(voice.get("up") or 0) - int(voice.get("down") or 0)
    except (TypeError, ValueError):
        balance = 0
    average = voice.get("alt_avg")
    try:
        average_sort = "" if average is None or pd.isna(average) else f"{float(average):.8f}"
    except (TypeError, ValueError):
        average_sort = ""
    _crowd_sync(
        key=f"crowd_sync_{kind}",
        data={
            "asset": f"{kind}|{asset_id}",
            "mark": crowd_mark(
                voice.get("up"),
                voice.get("down"),
                True,
                voice.get("alt_count"),
                average,
                voice.get("alt_spread"),
            ),
            "markSort": f"{float(balance):.8f}",
            "average": crowd_average_badge(
                average, voice.get("alt_count"), voice.get("alt_spread"), True,
            ),
            "averageSort": average_sort,
        },
    )


def crowd_average_badge(average, count, spread, active: bool = True) -> str:
    """The personal-score average, in the same colored box as the headline sentiment."""
    try:
        scored = int(count or 0)
    except (TypeError, ValueError):
        scored = 0
    if not active or scored < 1 or average is None or pd.isna(average):
        return "<span style='color:#6b7280;'>—</span>"
    title = f"Average of {scored} personal score" + ("s." if scored != 1 else ".")
    if scored >= 2 and spread is not None and not pd.isna(spread):
        title += f" The spread is ±{round(float(spread))}."
    return f"<span title='{html.escape(title)}'>{sentiment_badge(average)}</span>"


LIQ_KEY = "liq"


def _liquidation_record(asset_id) -> dict | None:
    """The stored liquidation estimate for one coin, with when it was made. None if not ready."""
    try:
        rows = (
            supabase.table("asset_market")
            .select("liq_levels, liq_updated_at")
            .eq("asset_key", asset_market_key("Crypto", asset_id))
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:
        return None
    if not rows or not isinstance(rows[0].get("liq_levels"), dict):
        return None
    record = dict(rows[0]["liq_levels"])
    record["updated_at"] = rows[0].get("liq_updated_at")
    return record


def _short_usd(value) -> str:
    value = float(value or 0)
    for size, mark in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if value >= size:
            return f"${value / size:.1f}{mark}"
    return f"${value:.0f}"


def _number_or_none(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _draw_liquidation_levels(fig, record, last_x) -> None:
    """Faint lines at the strongest estimated levels: red longs below, green shorts above.
    Brighter and thicker means more money would be liquidated there."""
    if not record or record.get("status") != "ok":
        return
    rows = [("longs", r) for r in record.get("longs") or []] + [("shorts", r) for r in record.get("shorts") or []]
    rows = [(side, r) for side, r in rows if _number_or_none(r.get("price")) and _number_or_none(r.get("usd"))]
    if not rows:
        return
    biggest = max(float(r["usd"]) for _side, r in rows) or 1.0
    xs, ys, texts, colours = [], [], [], []
    for side, row in rows:
        share = float(row["usd"]) / biggest
        colour = "#ef4444" if side == "longs" else "#22c55e"
        fig.add_hline(
            y=float(row["price"]), line_color=colour, line_width=1 + 4 * share,
            opacity=0.15 + 0.55 * share, row=1, col=1,
        )
        who = "Longs" if side == "longs" else "Shorts"
        xs.append(last_x)
        ys.append(float(row["price"]))
        texts.append(f"{who} liquidated near {float(row['price']):,.4g}: about {_short_usd(row['usd'])} (estimate)")
        colours.append(colour)
    fig.add_trace(
        go.Scatter(
            x=xs, y=ys, mode="markers", name="🔥 Liquidation levels (estimate)",
            marker=dict(symbol="diamond", size=8, color=colours, line=dict(width=0)),
            hovertext=texts, hoverinfo="text",
        ),
        row=1, col=1,
    )


def _liquidation_caption(record) -> str:
    credit = "Data: [Coinalyze](https://coinalyze.net)."
    if not record:
        return "🔥 Estimated liquidation levels appear within about an hour of a coin being watched. " + credit
    status = record.get("status")
    if status == "no_market":
        return "🔥 No futures market for this coin on Binance, Bybit or OKX, so there are no liquidation levels."
    if status != "ok":
        return "🔥 The liquidation levels could not be worked out on the last try. They are retried about hourly."
    when = str(record.get("updated_at") or "")[:16].replace("T", " ")
    return (
        "🔥 Estimated liquidation levels (not part of the score). Red lines below the price are where long "
        "positions would be force-closed, green lines above are shorts. Brighter means more money. "
        "Worked out from the last 7 days of open interest, assuming a typical leverage mix"
        + (f", updated {when} UTC" if when else "")
        + ". "
        + credit
    )


def coinglass_heatmap_url(asset_id) -> str:
    """CoinGlass's liquidation heatmap page for one coin. Empty when the coin has no known ticker."""
    ticker = crypto_ticker(asset_id) or ""
    ticker = "".join(ch for ch in ticker.upper() if ch.isalnum())
    if not ticker:
        return ""
    return f"https://www.coinglass.com/pro/futures/LiquidationHeatMap?coin={ticker}"


def sentiment_badge(score, pick: str | None = None) -> str:
    """Colored number box used for a headline score. A dash when there is no score yet."""
    if score is None or pd.isna(score):
        return "<span style='color:#6b7280;'>—</span>"
    color, background, _arrow, _bar = tone(score)
    box = (
        f"<span style='display:inline-block;min-width:52px;text-align:center;background:{background};"
        f"color:{color};border-radius:4px;padding:2px 8px;font-weight:600;line-height:1;'>"
        f"{float(score):.0f}</span>"
    )
    if not pick:
        return box
    safe_pick = html.escape(pick, quote=True)
    return (
        f"<button type='button' data-pick='{safe_pick}' "
        "style='display:inline-block;margin:0;padding:0;border:none;background:transparent;"
        "cursor:pointer;font:inherit;line-height:1;'>"
        f"{box}</button>"
    )


def _paint_section_score(section_key: str, score, ready: bool) -> None:
    """Put this section's sentiment score in its header, using the same colors as the body."""
    shown = score if ready else None
    try:
        missing = shown is None or pd.isna(shown)
    except TypeError:
        missing = shown is None
    if missing:
        payload = {"score": None, "color": "#6b7280", "background": "transparent"}
    else:
        color, background, _arrow, _bar = tone(shown)
        payload = {"score": round(float(shown)), "color": color, "background": background}
    _header_score(key=f"section_score_{section_key}", data=payload)


def score_from_alert(note: dict):
    message = str(note.get("message") or "")
    if "/100" in message:
        token = message.split("/100", 1)[0].rsplit(None, 1)[-1]
        try:
            return float(token)
        except ValueError:
            pass
    kind = str(note.get("alert_type") or "")
    if kind.startswith("BULLISH"):
        return 70.0
    if kind.startswith("BEARISH"):
        return 30.0
    return None


@st.fragment
def _respond_group_invite(invite_id: int, accept: bool) -> str:
    """Accept or dismiss one group invite. Empty means it worked."""
    try:
        result = supabase.rpc("respond_group_invite", {
            "invite_id": invite_id,
            "accept": accept,
        }).execute()
    except Exception:
        return "That invite could not be updated. Run the latest supabase_rls.sql, then try again."
    code = str(result.data or "").strip().strip('"')
    if code in ("ok", "dismissed", "gone"):
        return ""
    if code == "expired":
        return "That invite has expired."
    if code == "full":
        return "That group already has 50 members."
    return "That invite could not be updated. Run the latest supabase_rls.sql, then try again."


@st.fragment
def notifications_panel() -> None:
    """Alerts and alert rules. A filter, a button, or a slider redraws this section, not the page."""
    notifications_list = fetch_user_notifications()
    unread_count = sum(1 for note in notifications_list if not note.get("is_read", False))
    notifications_label = "🔔 Notifications" + (f" ({unread_count})" if unread_count else "")

    with tracked_expander(notifications_label, "notifications", sidebar=True):
        with tracked_expander("Alert Feed", "alert_feed"):
            if not notifications_list:
                st.caption("No alerts yet. When a watchlist asset crosses a threshold, it shows up here.")
            else:
                def _is_alert(note) -> bool:
                    return str(note.get("alert_type") or "") != "group_invite"

                has_unread = any(_is_alert(n) and not n.get("is_read", False) for n in notifications_list)
                has_read = any(_is_alert(n) and n.get("is_read", False) for n in notifications_list)
                has_any = any(_is_alert(n) for n in notifications_list)

                def _mark_all_read() -> None:
                    (
                        supabase.table("user_notifications")
                        .update({"is_read": True})
                        .eq("user_id", user_id)
                        .neq("alert_type", "group_invite")
                        .execute()
                    )

                # One row of icons. Group invites are never touched: they need Accept or Dismiss.
                with st.container(horizontal=True, gap="small", key="alert_feed_tools"):
                    read_all = st.button(
                        "✅", key="alerts_read_all", disabled=not has_unread,
                        help="Mark all as read",
                    )
                    clear_read = st.button(
                        "🧹", key="alerts_clear_read", disabled=not has_read,
                        help="Clear read alerts",
                    )
                    clear_all = st.button(
                        "🗑️", key="alerts_clear_all", disabled=not has_any,
                        help="Clear all alerts. Each one was already sent by email or in your digest.",
                    )
                if read_all or clear_read or clear_all:
                    try:
                        if read_all or clear_all:
                            _mark_all_read()
                        if clear_read or clear_all:
                            dismiss_read_alerts(supabase, user_id)
                        _rerun_fragment()
                    except Exception as exc:
                        st.error(f"Could not update your alerts: {exc}")

                # Unread first, then newest first. Read alerts are shown faded.
                filtered_notifs = sorted(
                    notifications_list, key=lambda note: str(note.get("created_at") or ""), reverse=True
                )
                filtered_notifs.sort(key=lambda note: bool(note.get("is_read", False)) and _is_alert(note))

                if not filtered_notifs:
                    st.caption("No notifications.")
                else:
                    crypto_list = prefs.get("crypto") or {}
                    stock_list = prefs.get("stock") or {}

                    def notification_target(symbol: str):
                        raw = str(symbol or "").strip()
                        if not raw:
                            return None
                        if raw in crypto_list:
                            return "Crypto", raw
                        if raw in stock_list:
                            return "Stock", raw
                        crypto_ids = {str(key).lower(): key for key in crypto_list}
                        stock_ids = {str(key).upper(): key for key in stock_list}
                        if raw.lower() in crypto_ids:
                            return "Crypto", crypto_ids[raw.lower()]
                        if raw.upper() in stock_ids:
                            return "Stock", stock_ids[raw.upper()]
                        return None

                    quiet_notes = {
                        "invite_joined", "group_invite", "group_joined",
                        "moderation_warning", "report_update",
                    }
                    asset_notes = [
                        note for note in filtered_notifs
                        if str(note.get("alert_type") or "") not in quiet_notes
                        and (
                            notification_target(note.get("asset_symbol"))
                            or str(note.get("asset_symbol") or "").lower().startswith("market:")
                        )
                    ]
                    if asset_notes:
                        st.caption(
                            "Click an alert to open it: an asset opens on the chart, "
                            "a market alert opens that market's sentiment."
                        )
                    for note in filtered_notifs:
                        name = html.escape(str(note.get("asset_name") or "Asset"))
                        message = html.escape(str(note.get("message") or ""))
                        created = html.escape(str(note.get("created_at") or "")[:16].replace("T", " "))
                        weight = "700" if not note.get("is_read") else "500"
                        kind = str(note.get("alert_type") or "")
                        if kind in ("invite_joined", "group_invite", "group_joined", "moderation_warning", "report_update"):
                            titles = {
                                "invite_joined": "Invite accepted",
                                "group_invite": "Group invite",
                                "group_joined": "Group",
                                "moderation_warning": "Warning",
                                "report_update": "Report",
                            }
                            border = "#93c5fd" if not note.get("is_read") else "#e5e7eb"
                            card = (
                                "<div style='background:#f8fafc;border:1px solid "
                                f"{border};border-radius:8px;padding:8px 10px;margin-bottom:8px;'>"
                                f"<div style='font-weight:{weight};color:#1e3a8a;'>{titles[kind]}</div>"
                                f"<div style='font-size:0.8rem;color:#374151;margin-top:2px;'>{message}</div>"
                                f"<div style='font-size:0.75rem;color:#6b7280;margin-top:2px;'>{created}</div></div>"
                            )
                            _score_table(key=f"notif_{note.get('id') or name}", data=card)
                            if kind == "group_invite":
                                invite_raw = str(note.get("asset_symbol") or "")
                                invite_id = None
                                if invite_raw.startswith("group:"):
                                    try:
                                        invite_id = int(invite_raw.split(":", 1)[1])
                                    except ValueError:
                                        invite_id = None
                                if invite_id:
                                    yes, no = st.columns(2)
                                    if yes.button("Accept", key=f"group_accept_{invite_id}", use_container_width=True):
                                        answer = _respond_group_invite(invite_id, True)
                                        if answer:
                                            st.warning(answer)
                                        else:
                                            _rerun_fragment()
                                    if no.button("Dismiss", key=f"group_dismiss_{invite_id}", use_container_width=True):
                                        _respond_group_invite(invite_id, False)
                                        _rerun_fragment()
                            continue
                        color, background, arrow, _bar = tone(score_from_alert(note))
                        border = color if not note.get("is_read") else "#e5e7eb"
                        target = notification_target(note.get("asset_symbol"))
                        card = (
                            "<div style='background:"
                            f"{background};border:1px solid {border};border-radius:8px;padding:8px 10px;margin-bottom:8px;'>"
                            f"<div style='font-weight:{weight};color:{color};'>{arrow} {name}</div>"
                            f"<div style='font-size:0.8rem;color:#374151;margin-top:2px;'>{message}</div>"
                            f"<div style='font-size:0.75rem;color:#6b7280;margin-top:2px;'>{created}</div></div>"
                        )
                        note_id = note.get("id") or name
                        note_ref = html.escape(str(note.get("id") or "") if not note.get("is_read") else "", quote=True)
                        market = str(note.get("asset_symbol") or "").strip().lower()
                        if market in ("market:crypto", "market:stock"):
                            # A market alert opens that market's sentiment section and jumps to it.
                            pick_value = html.escape("mood|" + market.split(":", 1)[1], quote=True)
                            card = (
                                f"<button type='button' data-alert='1' data-note='{note_ref}' data-pick='{pick_value}' "
                                "title='Open this market sentiment section' "
                                "style='display:block;width:100%;margin:0;padding:0;border:none;"
                                "background:transparent;text-align:left;cursor:pointer;font:inherit;color:inherit;'>"
                                f"{card}</button>"
                            )
                        elif target:
                            kind_name, asset_id = target
                            pick_value = html.escape(f"{kind_name}|{asset_id}", quote=True)
                            card = (
                                f"<button type='button' data-alert='1' data-note='{note_ref}' data-pick='{pick_value}' "
                                "style='display:block;width:100%;margin:0;padding:0;border:none;"
                                "background:transparent;text-align:left;cursor:pointer;font:inherit;color:inherit;'>"
                                f"{card}</button>"
                            )
                        _score_table(
                            key=f"notif_{note_id}",
                            data=card,
                        )


        with tracked_expander("Configure Alert Rules", "alert_rules"):
            st.caption(
                "Scores describe current conditions and are not forecasts. Each alert is sent once "
                "when a score crosses a line, and again only after it moves 10 points back and crosses again."
            )
            alert_enabled = st.checkbox(
                "📈 Asset score alerts",
                value=alert_prefs.get("enabled", True) is not False,
                key="alert_enabled_cb",
                help=(
                    "Alert when the technical score of an asset on your watchlists crosses one of your lines. "
                    "Scores are checked about every 5 minutes."
                ),
            )
            min_score = int(alert_prefs.get("min_score_alert", 70))
            max_score = int(alert_prefs.get("max_score_alert", 30))
            if alert_enabled:
                min_score = st.slider(
                    ":green[▲] Strongly positive at or above",
                    50, 95, min_score,
                    key="min_score_slider",
                    help="An asset score at or above this line sends a positive alert. The default is 70.",
                )
                max_score = st.slider(
                    ":red[▼] Strongly negative at or below",
                    5, 50, max_score,
                    key="max_score_slider",
                    help="An asset score at or below this line sends a negative alert. The default is 30.",
                )

            new_alert_settings = {
                "enabled": alert_enabled,
                "min_score_alert": min_score,
                "max_score_alert": max_score,
            }

            # Market sentiment alerts need the columns from the latest supabase_rls.sql.
            if "market_alerts_enabled" in alert_prefs:
                market_on = st.checkbox(
                    "🌐 Market sentiment alerts",
                    value=bool(alert_prefs.get("market_alerts_enabled")),
                    key="alert_market_cb",
                    help=(
                        "Alert when the crypto or stock market sentiment score crosses one of your lines. "
                        "It covers the markets you have switched on. Market sentiment updates about every 12 hours."
                    ),
                )
                market_high = int(float(alert_prefs.get("market_high_alert") or 65))
                market_low = int(float(alert_prefs.get("market_low_alert") or 35))
                if market_on:
                    market_high = st.slider(
                        ":green[▲] Strongly positive mood at or above",
                        55, 90, market_high,
                        key="market_high_slider",
                        help="Market sentiment at or above this line sends a positive alert. The default is 65.",
                    )
                    market_low = st.slider(
                        ":red[▼] Strongly negative mood at or below",
                        10, 45, market_low,
                        key="market_low_slider",
                        help="Market sentiment at or below this line sends a negative alert. The default is 35.",
                    )
                new_alert_settings.update({
                    "market_alerts_enabled": market_on,
                    "market_high_alert": market_high,
                    "market_low_alert": market_low,
                })

            # The email options need the digest columns from the latest supabase_rls.sql.
            # Until that has been run, show the old settings only.
            if "digest_enabled" not in alert_prefs:
                st.caption(
                    "Email options (instant alerts and a daily digest) appear after the latest "
                    "supabase_rls.sql has been run in Supabase."
                )
            else:
                # With every alert type off there is nothing to email, so the email
                # choices are greyed out. Their saved values are kept for later.
                emails_off = not alert_enabled and not new_alert_settings.get("market_alerts_enabled")
                st.markdown("**Emails**")
                instant_on = st.checkbox(
                    "⚡ Instant alerts",
                    value=alert_prefs.get("instant_email") is not False,
                    key="alert_instant_cb",
                    help="One email as soon as a score crosses a boundary.",
                    disabled=emails_off,
                )
                digest_on = st.checkbox(
                    "📬 Daily digest",
                    value=bool(alert_prefs.get("digest_enabled")),
                    key="alert_digest_cb",
                    disabled=emails_off,
                    help=(
                        "One email a day that gathers everything that crossed. "
                        "Nothing is sent on days with no alerts. "
                        "You can use this with or without instant alerts."
                    ),
                )
                saved_hour = alert_prefs.get("digest_hour")
                saved_hour = 8 if saved_hour is None else int(saved_hour)
                stored_zone = alert_prefs.get("digest_tz") or ""
                try:
                    browser_zone = str(getattr(st.context, "timezone", "") or "")
                except Exception:
                    browser_zone = ""
                saved_zone = stored_zone
                # The database column defaults to "UTC", and earlier versions also
                # saved "UTC" as a guess. For anyone who has not switched the digest
                # on, that is not a real choice, so prefer the browser's zone.
                if browser_zone and (not saved_zone or (saved_zone == "UTC" and not alert_prefs.get("digest_enabled"))):
                    saved_zone = browser_zone
                zone_choices = list(COMMON_ZONES)
                if saved_zone and saved_zone not in zone_choices:
                    zone_choices.insert(0, saved_zone)
                # While the digest is off, keep whatever is stored, so nothing is
                # saved just because the panel was opened.
                digest_hour_choice = alert_prefs.get("digest_hour")
                digest_zone_choice = alert_prefs.get("digest_tz")
                if digest_on:
                    hour_col, zone_col = st.columns(2)
                    digest_hour_choice = hour_col.selectbox(
                        "Send at",
                        list(range(24)),
                        index=saved_hour if 0 <= saved_hour <= 23 else 8,
                        format_func=lambda hour: f"{hour:02d}:00",
                        key="alert_digest_hour",
                        disabled=emails_off,
                    )
                    start_zone = saved_zone or "UTC"
                    digest_zone_choice = zone_col.selectbox(
                        "Time zone",
                        zone_choices,
                        index=zone_choices.index(start_zone) if start_zone in zone_choices else 0,
                        key="alert_digest_zone",
                        disabled=emails_off,
                    )
                    if browser_zone and digest_zone_choice != browser_zone:
                        st.caption(f"Your browser's time zone is {browser_zone}.")
                if digest_on and not stored_zone and not browser_zone and digest_zone_choice == "UTC":
                    # The browser has not reported its zone yet. Leave the zone unset
                    # rather than storing a guess; a later run fills it in.
                    digest_zone_choice = None
                new_alert_settings.update({
                    "instant_email": instant_on,
                    "digest_enabled": digest_on,
                    "digest_hour": None if digest_hour_choice is None else int(digest_hour_choice),
                    "digest_tz": digest_zone_choice,
                })
                if emails_off:
                    st.caption("Tick an alert type above to choose how its emails arrive.")
                elif not instant_on and not digest_on:
                    st.caption("Both are off, so alerts only appear in the dashboard.")

            changed = new_alert_settings != {name: alert_prefs.get(name) for name in new_alert_settings}
            if changed:
                to_save = dict(new_alert_settings)
                if to_save.get("digest_enabled") and not alert_prefs.get("digest_enabled"):
                    # Switched on now: the first digest goes out at the next chosen hour,
                    # not at once with whatever happened earlier today.
                    to_save["last_digest_at"] = datetime.now(timezone.utc).isoformat()
                alert_prefs.update(to_save)
                prefs["alerts"] = alert_prefs
                save_alert_preferences_to_cloud(to_save)


notifications_panel()


if st.session_state.get("section_layout") not in ("Single column", "Wide"):
    saved_layout = (prefs.get("settings") or {}).get("section_layout")
    st.session_state.section_layout = saved_layout if saved_layout in ("Single column", "Wide") else "Single column"
wide_on = st.session_state.section_layout == "Wide"
# A market or settings change rebuilds sections and can arrive as a click on
# Single column. Extra metrics only changes the score table, so it never does.
# Either way, that rerun must leave the wide or single choice alone.
_layout_watched = (
    ("_seen_trade_markets", "trade_markets"),
    ("_seen_show_reasons", "show_reasons"),
    ("_seen_show_extra_metrics", "show_extra_metrics"),
    ("_seen_show_period_changes", "show_period_changes"),
    ("_seen_days_history", "days_history"),
)
hold_layout = False
for _seen_name, _state_name in _layout_watched:
    if _state_name not in st.session_state:
        continue
    _seen_value = st.session_state.get(_seen_name)
    if _seen_value is not None and st.session_state[_state_name] != _seen_value:
        hold_layout = True
        break
with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute", key="page_header"):
    st.markdown(
        "<div style='display:flex;align-items:center;gap:0.85rem;margin:0.4rem 0;'>"
        f"{_brand_mark(58, align='left')}"
        "<div style='display:flex;align-items:baseline;flex-wrap:wrap;gap:0.35rem 0.85rem;'>"
        "<h1 style='margin:0;padding:0;line-height:1.15;font-size:2.25rem;font-weight:700;white-space:nowrap;'>"
        "angstrom signals</h1>"
        "<span style='font-size:0.82rem;font-weight:500;line-height:1;opacity:0.72;'>"
        "Market sentiment and technical signals, with the crowd alongside.</span></div></div>",
        unsafe_allow_html=True,
    )
    with st.container(horizontal=True, vertical_alignment="center", gap="xsmall", width="content"):
        single_layout = st.button(
            "Single column",
            key="layout_single",
            type="primary" if not wide_on else "secondary",
            help="Stack every section in one column, with Quick Snapshot first.",
        )
        wide_layout_click = st.button(
            "Wide",
            key="layout_wide",
            type="primary" if wide_on else "secondary",
            help=(
                "Snapshot and score tables across the top, market sentiment on the left, "
                "and the chart sections on the right. The two bottom columns start equal. "
                "Drag the line between them to resize."
            ),
        )
        open_sections = st.button("Open all", key="open_all_sections", width="content", help="Open all sections")
        collapse_sections = st.button("Collapse all", key="collapse_all_sections", width="content", help="Collapse all sections")
        # A layout button on this same run must not win. The buttons normally
        # fold the sections in the browser. This covers a click that still
        # reaches Streamlit, and the wide or single choice stays as it was.
        if open_sections or collapse_sections:
            _apply_section_bulk(not collapse_sections)
            st.session_state.section_layout = st.session_state.section_layout
        elif hold_layout:
            st.session_state.section_layout = "Wide" if wide_on else "Single column"
        elif single_layout:
            st.session_state.section_layout = "Single column"
            st.rerun()
        elif wide_layout_click:
            st.session_state.section_layout = "Wide"
            st.rerun()
save_account_settings({"section_layout": st.session_state.section_layout})
if not _POPOUT_VIEW:
    remember_section_clicks()

with tracked_expander("📖 Help and guides", "help_guides", default=False):
    (
        tab_start, tab_scores, tab_chart, tab_sentiment, tab_alerts, tab_social, tab_layout,
    ) = st.tabs([
        "🚀 Start here", "📈 Scores", "📊 Chart & tools", "📰 Sentiment",
        "🔔 Alerts", "💬 Social", "🧭 Layout & settings",
    ])

    with tab_start:
        st.markdown("""
**Angstrom Signals reads current market conditions for the crypto and stocks on your watchlists.**
Each asset gets a technical score from 0 to 100, a news sentiment score, and tools to look closer.
It is a research tool, not financial advice. The score describes conditions now; in our long-run
tests it has not predicted what price did next.

**A quick tour**
1. **Quick Snapshot** opens with *What changed*: scores that crossed your alert lines, and the biggest moves.
2. **Crypto Scores** and **Equity Scores** rank your watchlists, strongest first. Click a name to open it on the chart.
3. **Interactive Chart** shows the asset with the indicators you pick. Underneath sit Score Breakdown,
   Max pain, Leverage & liquidations, Market sentiment and Signal matrix, all for that asset.
4. **Notifications**, in the sidebar, holds your alerts and their settings.
5. The arrow on the right edge opens **Social signals and chat**.
""")
        bands = [
            ("Strongly positive", "70+", "#15803d", "#dcfce7"),
            ("Positive", "53–69", "#15803d", "#dcfce7"),
            ("Mixed", "47–52", "#b45309", "#fef3c7"),
            ("Negative", "30–46", "#b91c1c", "#fee2e2"),
            ("Strongly negative", "below 30", "#b91c1c", "#fee2e2"),
        ]
        band_cols = st.columns(len(bands))
        for column, (name, span, color, background) in zip(band_cols, bands):
            column.markdown(
                f"<div style='background:{background};color:{color};border-radius:8px;padding:12px 14px;'>"
                f"<div style='font-size:0.8rem;font-weight:600;'>{name}</div>"
                f"<div style='font-size:1.6rem;font-weight:700;line-height:1.2;'>{span}</div></div>",
                unsafe_allow_html=True,
            )
        st.caption("The same green, amber and red are used for technical and sentiment scores everywhere.")

    with tab_scores:
        st.markdown("""
**How the score works.** Every score starts at 50. Each indicator adds or subtracts points, and the
total is kept between 0 and 100. Higher means more of the indicators read positive.
""")
        left, right = st.columns(2)
        with left:
            st.markdown("""
**What moves it** (at weight 1.0)
- **RSI**: oversold adds up to 8, overbought subtracts up to 8
- **Stochastic**: below 20 adds 5, above 80 subtracts 5
- **Moving averages**: ±4 each for price versus SMA 20, 50 and 200
- **ADX**: a strong trend adds or subtracts 4
- **MACD**: up to 4 for the line, 3 for the signal cross, 2 for the histogram
""")
        with right:
            st.markdown("""
**More factors**
- **Ichimoku**: 5 for price versus the cloud, 3 for Tenkan versus Kijun
- **Bollinger Bands**: near the lower band adds 4, the upper subtracts 4
- **Volume**: a high-volume up bar adds 3, a down bar subtracts 3
- **OBV**: ±3 for volume flow versus its average
- **7-day move**: up to 4 either way
""")
        st.markdown("""
**Your own weights.** *Scoring Balance Weights* in the sidebar scales each factor; 0 switches it off.
Save a mix as a named set. *How the score adds up* shows the rules with your weights.

**The tables**
- Click a column title to sort. Hover a TA score to see why it landed there; click it for Score Breakdown.
- **Extra metrics** (Settings) add 7d %, Market Cap, ATR % (typical daily move) and Vol (volume versus its
  20-day average). Another tick box adds 1d % and 30d %.
- **Watching** shows how many accounts follow the asset. **30-day trend** is a small price line.

**Freshness.** Prices are saved about every 5 minutes and sentiment about every 12 hours, for everyone.
Your score is worked out from those saved prices with your own weights.
""")

    with tab_chart:
        st.markdown("""
**Interactive Chart.** Candles with SMA 20 and 50 and Bollinger Bands, plus volume and RSI underneath.
The icon row adds more:
- 📏 SMA 200 · ☁️ Ichimoku cloud · 〰️ MACD · 🎚️ Stochastic · 🧭 ADX · 📊 OBV
- 🔥 **Liquidation levels** (crypto): estimated prices where leveraged positions would be force-closed,
  red below the price for longs, green above for shorts. Brighter means more money.
- **CoinGlass liquidation heatmap ↗** (crypto), under the icons, opens CoinGlass's own heatmap in a new tab.
- **Overlay** draws RSI, Stochastic and ADX on the price chart; **earnings dates** (stocks) mark report days.

Your choices are saved on your account.

**Score Breakdown** shows how many points each factor added or took away, with the reasons.

**🎯 Max pain** (stocks, Bitcoin, Ethereum): the options strike where open contracts would be worth the
least at expiry. It opens on the next expiry after today; one with almost no open contracts says so.
It is not a price target.

**🔥 Leverage & liquidations** (crypto): open interest, funding rate, long/short ratio and the last 24
hours of liquidations, a ladder and table of the estimated liquidation levels with their change since
the last update, and 7 days of hourly charts. Estimated from Coinalyze data, refreshed about hourly.

**▦ Signal matrix** lines up price with each signal over recent weeks, and shows how each one has lined
up with the price change that followed. The evidence view shows the long-run test for this asset.

None of these tools change the technical score.
""")

    with tab_sentiment:
        st.markdown("""
**What it is.** An AI reads recent headlines and scores each from 0 (very negative) to 100 (very
positive). The sentiment score is their average. It is separate from the technical score.

**Where it shows**
- **Market sentiment – Crypto / Stocks**: the whole market, from headlines plus public readings
  (central banks, the dollar and yields, Fear & Greed, market breadth and more).
- **Market sentiment – asset**, under the chart: the headlines for that asset, newest first, each with
  its score and a one-line summary, plus Positive and Negative paragraphs.
- The **Sentiment** column in the tables.

**Your take.** 👍 if you agree, 👎 if you don't, then pick your own score from 0 to 100 and add a short
comment. The **Crowd** box shows everyone's average; hover the 👎 for how spread out they are.
A new sentiment update clears the takes, because they belonged to the old score.

Sentiment updates about every 12 hours for everyone. The timers in Quick Snapshot show when.
""")

    with tab_alerts:
        st.markdown("""
**Setting up** (Notifications → Configure Alert Rules)
- 📈 **Asset score alerts**: an alert when an asset's technical score reaches your positive line
  (default 70) or drops to your negative line (default 30). Checked about every 5 minutes.
- 🌐 **Market sentiment alerts**: the same for the crypto or stock market sentiment (default 65 and 35),
  for the markets you trade. Updated about every 12 hours.
- **Emails**: ⚡ **Instant** (one email per alert, straight away) and/or 📬 **Daily digest** (one email a
  day at your chosen hour and time zone, only on days with alerts). Greyed out while no alert type is on.

**No repeats on a wobble.** After an alert, the same one can only fire again once the score has moved
10 points back (for example up to 40 after a 30 alert) and then crosses again.

**The Alert Feed**
- Unread alerts sit at the top. Click one to open it: an asset opens on the chart, a market alert opens
  that market's sentiment. Clicking marks it read.
- ✅ marks all as read · 🧹 clears read alerts · 🗑️ clears all. Group invites stay until you answer them.

**Always on.** Alerts are checked in the background, whether or not this page is open. Emails go only
to your account's address; the digest also lists market sentiment and your strongest and weakest assets.
""")

    with tab_social:
        st.markdown("""
**Open it** with the arrow on the right edge, or a 💬 speech balloon. Drag its left edge to resize,
drag the bar in the middle to split it, and 📌 **Pin** keeps it open while you use the page.

**Social signals** (top): comments on sentiment scores, newest first, kept for 12 hours with their
replies. Filter by Positive / Negative / Mixed, by asset or watchlist, and by person: Me, your groups,
or your ⭐ favourites.

**General chat** (bottom): a shared room not tied to an asset. Enter posts; Shift+Enter adds a line.

**On any note**: 👍 / 👎 · ↩ reply · ⭐ add the person to favourites · 👥 invite them to a group ·
🚩 report a comment that breaks the socials policy · 🗑️ delete your own note.

**Search**, at the top, filters both halves by words, names or assets.
""")

    with tab_layout:
        st.markdown("""
**Sections.** Every section folds open or shut from its header. **Open all** and **Collapse all** sit
by the page title. Each section's ↗ opens it in its own window, which follows the asset you pick.

**Layout.** ▢ stacks everything in one column; the wide layout puts the tables on top, market sentiment
on the left and the chart and its tools on the right. Drag the line between the columns to resize.

**Settings** (sidebar)
- **I trade cryptos / equities / both** hides the markets you don't trade.
- **Watchlists** add or remove assets; **Account** holds your name, picture and bio.
- **Feedback** sends us an issue or an idea.

**Saved on your account**: layout, open sections, chart choices, weights, alert settings, the social
panel, and the asset on the chart. They come back on any device.

**Keep me signed in** (at login) remembers you on this device for 30 days. Logging out forgets it.
""")

CRYPTO_WATCHLIST = prefs["crypto"]
STOCK_WATCHLIST = prefs["stock"]
current_weights = prefs["weights"]
custom_profiles = prefs["profiles"]
settings = prefs["settings"]
_TRADE_CRYPTOS = "I trade cryptos"
_TRADE_EQUITIES = "I trade equities"
_TRADE_BOTH = "I trade both"
_TRADE_CHOICES = (_TRADE_CRYPTOS, _TRADE_EQUITIES, _TRADE_BOTH)


def _trade_choice(crypto: bool, equities: bool) -> str:
    """The radio label for a saved pair. Both off is not a choice, so it reads as both."""
    if crypto and not equities:
        return _TRADE_CRYPTOS
    if equities and not crypto:
        return _TRADE_EQUITIES
    return _TRADE_BOTH


def _trade_flags(choice: str) -> tuple[bool, bool]:
    if choice == _TRADE_CRYPTOS:
        return True, False
    if choice == _TRADE_EQUITIES:
        return False, True
    return True, True


if st.session_state.get("trade_markets") not in _TRADE_CHOICES:
    st.session_state.trade_markets = _trade_choice(
        bool(settings.get("trade_crypto", True)),
        bool(settings.get("trade_equities", True)),
    )
trade_crypto, trade_equities = _trade_flags(st.session_state.trade_markets)


def get_builtin_profiles():
    return {
        "📊 Trend Following": {
            "rsi": 0.8, "stochastic": 0.8, "sma": 1.5, "adx": 1.0,
            "macd": 1.2, "ichimoku": 1.0, "bb": 0.8, "volume": 1.0,
            "obv": 1.0, "performance": 1.2,
        },
        "📉 Mean Reversion": {
            "rsi": 1.5, "stochastic": 1.2, "sma": 0.8, "adx": 1.0,
            "macd": 0.8, "ichimoku": 1.0, "bb": 1.5, "volume": 0.8,
            "obv": 0.8, "performance": 0.8,
        },
        "🚀 Momentum Heavy": {
            "rsi": 1.0, "stochastic": 1.2, "sma": 1.0, "adx": 1.0,
            "macd": 1.5, "ichimoku": 1.0, "bb": 1.0, "volume": 1.2,
            "obv": 1.2, "performance": 1.5,
        },
    }


built_in_profiles = get_builtin_profiles()
all_profiles = {**built_in_profiles, **custom_profiles}

indicators = ["rsi", "stochastic", "sma", "adx", "macd", "ichimoku", "bb", "volume", "obv", "performance"]


def stored_weight(name: str) -> float:
    raw = current_weights.get(name, 1.0) if isinstance(current_weights, dict) else 1.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 1.0
    return min(2.0, max(0.0, round(value, 1)))


# A slider with no starting value mounts at 0. That blank set was saved, and
# every factor then adds nothing, so every score stays at 50.
weights_blank = all(stored_weight(name) == 0.0 for name in indicators)
if weights_blank:
    current_weights = {name: 1.0 for name in indicators}
    prefs["weights"] = current_weights
    save_preferences_to_cloud({"scoring_weights": current_weights})

for indicator in indicators:
    key_name = f"weight_{indicator}"
    if weights_blank or key_name not in st.session_state:
        st.session_state[key_name] = stored_weight(indicator)

if st.session_state.get("reset_weights"):
    for indicator in indicators:
        st.session_state[f"weight_{indicator}"] = 1.0
    current_weights = {indicator: 1.0 for indicator in indicators}
    prefs["weights"] = current_weights
    save_preferences_to_cloud({"scoring_weights": current_weights})
    st.session_state.reset_weights = False

def _ensure_added(kind: str, asset_id: str, label: str) -> None:
    """Write the first shared prices and sentiment when this asset is new."""
    try:
        days = int((settings or {}).get("days_history", 200) or 200)
    except (TypeError, ValueError):
        days = 200
    try:
        with st.spinner(f"Saving the first shared reading for {label}..."):
            ensure_new_asset(supabase, kind, asset_id, label, days)
    except Exception as exc:
        print(f"First shared reading failed for {asset_id}: {exc}")


with tracked_expander("⭐ Watchlists", "watchlists", sidebar=True):
    if trade_crypto:
        with tracked_expander("Edit Crypto", "edit_crypto"):
            st.caption("Type a name or ticker, press Enter, then pick the match.")
            if st.session_state.pop("_clear_new_crypto", False):
                st.session_state["new_crypto"] = ""
            new_crypto = st.text_input("Add crypto", key="new_crypto", placeholder="e.g. XLM or Stellar")
            crypto_query = (new_crypto or "").strip()
            crypto_choice = None
            if crypto_query:
                crypto_matches = search_crypto_matches(crypto_query)
                if not crypto_matches:
                    # CoinGecko search can be out of reach. A coin we already know still resolves.
                    known = find_crypto(crypto_query)
                    if known:
                        known_ticker = crypto_ticker(known[0]) or ""
                        crypto_matches = [{"id": known[0], "name": str(known[1]), "symbol": known_ticker, "rank": None}]
                if crypto_matches:
                    crypto_options = {match["id"]: match for match in crypto_matches}

                    def _crypto_option(coin_id, options=crypto_options):
                        match = options[coin_id]
                        symbol = f" ({match['symbol']})" if match["symbol"] and match["symbol"] not in match["name"].upper() else ""
                        rank = f"  ·  rank {match['rank']}" if match["rank"] else ""
                        return f"{match['name']}{symbol}{rank}"

                    picked_id = st.selectbox(
                        "Pick the coin",
                        list(crypto_options),
                        format_func=_crypto_option,
                        key="pick_crypto",
                        label_visibility="collapsed",
                    )
                    crypto_choice = crypto_options.get(picked_id)
                else:
                    st.warning(f"No coin found for '{crypto_query}'. Check the spelling, or try the ticker, such as XLM.")
            if st.button("Add Crypto", disabled=crypto_choice is None):
                cid = crypto_choice["id"]
                symbol = crypto_choice["symbol"]
                label = f"{crypto_choice['name']} ({symbol})" if symbol and symbol not in crypto_choice["name"].upper() else crypto_choice["name"]
                ticker = crypto_ticker(cid)
                alias = (ticker or "").lower()
                fresh = bool(cid) and cid not in CRYPTO_WATCHLIST
                changed = False
                if alias and alias != cid and alias in CRYPTO_WATCHLIST:
                    CRYPTO_WATCHLIST.pop(alias, None)
                    changed = True
                if fresh:
                    CRYPTO_WATCHLIST[cid] = label
                    changed = True
                if changed:
                    prefs["crypto"] = CRYPTO_WATCHLIST
                    save_preferences_to_cloud({"crypto_watchlist": CRYPTO_WATCHLIST})
                    if fresh:
                        _ensure_added("Crypto", cid, str(label))
                    st.session_state["_clear_new_crypto"] = True
                    st.rerun()
                else:
                    st.info(f"{label} is already on your list.")
            if CRYPTO_WATCHLIST:
                to_remove = st.selectbox("Remove crypto", [""] + list(CRYPTO_WATCHLIST.keys()), key="rm_crypto")
                if to_remove and st.button("Remove Crypto"):
                    CRYPTO_WATCHLIST.pop(to_remove, None)
                    prefs["crypto"] = CRYPTO_WATCHLIST
                    save_preferences_to_cloud({"crypto_watchlist": CRYPTO_WATCHLIST})
                    st.rerun()

    if trade_equities:
        with tracked_expander("Edit Stocks", "edit_stocks"):
            st.caption("Type a company name or ticker, press Enter, then pick the match.")
            if st.session_state.pop("_clear_new_stock", False):
                st.session_state["new_stock"] = ""
            new_stock = st.text_input("Add stock or ETF", key="new_stock", placeholder="e.g. Apple, GOOGL or SIE.DE")
            stock_query = (new_stock or "").strip()
            stock_choice = None
            if stock_query:
                stock_matches = search_stock_matches(stock_query)
                unchecked = False
                if not stock_matches and re.fullmatch(r"[A-Za-z0-9.\-^=]{1,12}", stock_query):
                    # Search is out of reach. Offer the ticker as typed, and say it is unchecked.
                    stock_matches = [{"symbol": stock_query.upper(), "name": stock_query.upper(), "exchange": "", "type": "Stock"}]
                    unchecked = True
                if stock_matches:
                    stock_options = {match["symbol"]: match for match in stock_matches}

                    def _stock_option(symbol, options=stock_options):
                        match = options[symbol]
                        parts = [symbol]
                        if match["name"] and match["name"] != symbol:
                            parts.append(match["name"])
                        if match["exchange"]:
                            parts.append(match["exchange"])
                        if match["type"] == "ETF":
                            parts.append("ETF")
                        return "  ·  ".join(parts)

                    picked_symbol = st.selectbox(
                        "Pick the stock",
                        list(stock_options),
                        format_func=_stock_option,
                        key="pick_stock",
                        label_visibility="collapsed",
                    )
                    stock_choice = stock_options.get(picked_symbol)
                    if unchecked:
                        st.caption("Search is not available right now, so this ticker has not been checked.")
                else:
                    st.warning(f"No stock found for '{stock_query}'. Try the company name or the ticker.")
            if st.button("Add Stock", disabled=stock_choice is None):
                tic = stock_choice["symbol"]
                if tic in STOCK_WATCHLIST:
                    st.info(f"{tic} is already on your list.")
                else:
                    label = stock_choice["name"] or tic
                    STOCK_WATCHLIST[tic] = label
                    prefs["stock"] = STOCK_WATCHLIST
                    save_preferences_to_cloud({"stock_watchlist": STOCK_WATCHLIST})
                    _ensure_added("Stock", tic, label)
                    st.session_state["_clear_new_stock"] = True
                    st.rerun()
            if STOCK_WATCHLIST:
                to_remove = st.selectbox("Remove stock", [""] + list(STOCK_WATCHLIST.keys()), key="rm_stock")
                if to_remove and st.button("Remove Stock"):
                    STOCK_WATCHLIST.pop(to_remove, None)
                    prefs["stock"] = STOCK_WATCHLIST
                    save_preferences_to_cloud({"stock_watchlist": STOCK_WATCHLIST})
                    st.rerun()

def _score_rules_popover(weights) -> None:
    """An info button that opens the plain-words scoring rules, with the user's own weights applied."""
    with st.popover("ℹ️", help="How the score is worked out"):
        st.markdown("**How the score is worked out**")
        st.write(score_rules.HOW_IT_ADDS_UP)
        table = []
        for rule in score_rules.weighted_rows(weights if isinstance(weights, dict) else None):
            for index, (when, points) in enumerate(rule["rows"]):
                table.append({
                    "Indicator": f"{rule['name']} (weight {rule['weight']:g})" if index == 0 else "",
                    "When": when,
                    "Points": f"{points:+g}" if points else "0",
                })
        # A plain table: not sortable, because the indicator name only sits on its first row.
        st.table(table)
        st.markdown("**What each one measures**")
        for rule in score_rules.weighted_rows(None):
            st.markdown(f"- **{rule['name']}**: {rule['measures']}")
        st.markdown("**Reading the total**")
        for line in score_rules.band_lines():
            st.markdown(f"- {line}")
        st.caption(score_rules.CONFLUENCE)
        st.info(score_rules.HONEST_NOTE)


with tracked_expander("⚖️ Scoring Balance Weights", "weights", sidebar=True):
    st.caption("Adjust the relative importance of each indicator. Every slider changes the score.")
    _score_rules_popover(current_weights)

    st.markdown("**Named Weight Sets**")
    profile_names = ["Select saved set..."] + list(all_profiles.keys())
    selected_profile = st.selectbox("Load Saved Set", profile_names, key="load_profile_sb")

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("Load Set") and selected_profile != "Select saved set...":
            if selected_profile in all_profiles:
                loaded = all_profiles[selected_profile]
                for indicator in indicators:
                    st.session_state[f"weight_{indicator}"] = float(loaded.get(indicator, 1.0))
                current_weights = loaded
                prefs["weights"] = current_weights
                save_preferences_to_cloud({"scoring_weights": current_weights})
                st.success(f"Loaded '{selected_profile}'.")
                st.rerun()
    with col_p2:
        if st.button("Delete Set") and selected_profile != "Select saved set...":
            if selected_profile in built_in_profiles:
                st.error("Built-in profiles cannot be deleted.")
            elif selected_profile in custom_profiles:
                custom_profiles.pop(selected_profile)
                prefs["profiles"] = custom_profiles
                save_preferences_to_cloud({"weight_profiles": custom_profiles})
                st.success(f"Deleted '{selected_profile}'.")
                st.rerun()

    new_profile_name = st.text_input("New set name", placeholder="e.g. Volatility Focus")
    if st.button("Save Current as New Set") and new_profile_name:
        pname = new_profile_name.strip()
        if pname:
            if pname in built_in_profiles:
                st.error("Cannot overwrite a built-in profile name.")
            else:
                custom_profiles[pname] = current_weights
                prefs["profiles"] = custom_profiles
                save_preferences_to_cloud({"weight_profiles": custom_profiles})
                st.success(f"Saved set '{pname}'.")
                st.rerun()

    st.markdown("---")

    def weight_slider(label: str, name: str):
        key_name = f"weight_{name}"
        # Pass the saved weight as the value. Without it, the slider's own
        # default is the bottom of the range, which is 0.
        return st.slider(
            label,
            0.0,
            2.0,
            float(st.session_state[key_name]),
            step=0.1,
            key=key_name,
        )

    w_rsi = weight_slider("RSI Weight", "rsi")
    w_stoch = weight_slider("Stochastic Weight", "stochastic")
    w_sma = weight_slider("Moving Averages Weight", "sma")
    w_adx = weight_slider("ADX Trend Weight", "adx")
    w_macd = weight_slider("MACD & Hist Weight", "macd")
    w_ichi = weight_slider("Ichimoku Cloud Weight", "ichimoku")
    w_bb = weight_slider("Bollinger Bands Weight", "bb")
    w_vol = weight_slider("Volume Weight", "volume")
    w_obv = weight_slider("OBV Weight", "obv")
    w_perf = weight_slider("Performance Weight", "performance")

    new_weights = {
        "rsi": w_rsi, "stochastic": w_stoch, "sma": w_sma, "adx": w_adx,
        "macd": w_macd, "ichimoku": w_ichi, "bb": w_bb, "volume": w_vol,
        "obv": w_obv, "performance": w_perf,
    }

    # Every slider at 0 is the blank mount, not a mix worth keeping.
    # One slider can still be 0 to turn that single factor off.
    if new_weights != current_weights and any(float(value) != 0 for value in new_weights.values()):
        save_preferences_to_cloud({"scoring_weights": new_weights})
        current_weights = new_weights
        prefs["weights"] = current_weights

    st.checkbox(
        "Adapt to the market (experimental)",
        key="adaptive_scoring",
        help=(
            "Trending markets give more say to trend indicators (moving averages, MACD, Ichimoku, ADX, OBV) "
            "and less to RSI, Stochastic and Bollinger Bands. Ranging markets do the opposite. "
            "Your sliders still apply on top. Only affects this session; alerts use the standard weights."
        ),
    )

    if st.button("🔄 Reset to Default (1.0)"):
        st.session_state.reset_weights = True
        st.rerun()

with tracked_expander("⚙️ Settings", "settings_panel", sidebar=True):
    if "show_reasons" not in st.session_state:
        st.session_state.show_reasons = bool(settings.get("show_reasons", True))
    if "show_extra_metrics" not in st.session_state:
        st.session_state.show_extra_metrics = bool(settings.get("show_extra_metrics", True))
    if "show_period_changes" not in st.session_state:
        st.session_state.show_period_changes = bool(settings.get("show_period_changes", True))
    if "days_history" not in st.session_state:
        try:
            saved_days = int(settings.get("days_history", 200))
        except (TypeError, ValueError):
            saved_days = 200
        st.session_state.days_history = min(365, max(90, saved_days))
    # Keep these for the whole session. A partial redraw otherwise drops them,
    # and the next full run saves the blank defaults (90 days, toggles off, cryptos).
    st.markdown("**Markets you trade**")
    st.radio(
        "Markets you trade",
        _TRADE_CHOICES,
        key="trade_markets",
        persist_state="session",
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown("**Days of history**")
    days_history = st.slider(
        "Days of history",
        90,
        365,
        key="days_history",
        persist_state="session",
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown("**TA analysis**")
    show_reasons = st.checkbox(
        "Show score breakdown",
        key="show_reasons",
        persist_state="session",
    )
    show_extra_metrics = st.checkbox(
        "Show extra metrics (7d, market cap, ATR, volume)",
        key="show_extra_metrics",
        persist_state="session",
    )
    show_period_changes = st.checkbox(
        "Show 1-day and 30-day changes",
        key="show_period_changes",
        persist_state="session",
    )
    st.divider()
    st.markdown("**UI pop-out options**")
    if "popouts_close_on_logout" not in st.session_state:
        st.session_state.popouts_close_on_logout = bool(settings.get("popouts_close_on_logout", True))
    if "popouts_as_window" not in st.session_state:
        st.session_state.popouts_as_window = bool(settings.get("popouts_as_window", True))
    if "popouts_fold_section" not in st.session_state:
        st.session_state.popouts_fold_section = bool(settings.get("popouts_fold_section", True))
    popouts_as_window = st.checkbox(
        "Open pop-outs in a new window",
        key="popouts_as_window",
        persist_state="session",
        help="Off opens them in a new browser tab instead.",
    )
    popouts_fold_section = st.checkbox(
        "Fold a section here when I pop it out",
        key="popouts_fold_section",
        persist_state="session",
        help="The section closes on the main page while it is open in its own window.",
    )
    close_popouts_on_logout = st.checkbox(
        "Close pop-out tabs when I log out",
        key="popouts_close_on_logout",
        persist_state="session",
        help=(
            "Switch this off to keep your pop-out windows where they are. "
            "They reconnect when you log in again on the main tab, as long as "
            "that is within about an hour. Leave it on if other people use this computer."
        ),
    )

    st.divider()
    with tracked_expander("UI Colours", "colours"):
        st.caption("Your colours save on this account as you change them. Press a theme's button to try a different colour scheme.")
        slot = _saved_colour_slot()
        st.markdown("**My saved colours**")
        if slot:
            st.html(
                "<div class='theme-pick' style='width:8.5rem;'>" + colour_themes.swatch_html(slot)
                + "<div class='theme-name'>Saved</div></div>"
            )
        else:
            st.caption("Nothing saved yet. Press the disk icon to keep these colours.")
        with st.container(horizontal=True, gap="xsmall", width="content", key="themepick_icons"):
            st.button(
                ":material/save:", key="colours_save_slot", on_click=_save_colour_slot, width="content",
                help="Save current: keeps the colours you have now, so you can come back to them after experimenting.",
            )
            st.button(
                ":material/undo:", key="colours_back_slot", on_click=_use_colours, args=(slot or {},),
                disabled=not slot, width="content",
                help="Back to saved: puts the pickers back to your saved colours.",
            )
            if st.button(":material/restart_alt:", key="reset_colours", width="content",
                         help="Reset to default: the original Angstrom colours."):
                st.session_state._reset_colours = True
                save_account_settings({"colours": {key: default for key, default in _THEME_COLOURS}})
                st.rerun()
        st.markdown("**Ready-made themes**")
        st.caption("Press a theme's button to try it. You can still change any colour afterwards, and the undo arrow returns to your saved colours.")
        theme_names = list(colour_themes.THEMES)
        for start in range(0, len(theme_names), 2):
            for column, name in zip(st.columns(2, gap="small"), theme_names[start:start + 2]):
                with column:
                    st.html("<div class='theme-pick'>" + colour_themes.swatch_html(colour_themes.THEMES[name]) + "</div>")
                    st.button(
                        name, key=f"theme_use_{name.lower().replace(' ', '_')}",
                        on_click=_use_colours, args=(colour_themes.THEMES[name],), use_container_width=True,
                        help=f"Try the {name} colours",
                    )
        st.markdown("**Fine tune**")
        st.caption("Change the colour of individual UI elements. Drag and drop colours to copy them. Save and reset using the icons above.")
        widths = [1.5, 1, 1]
        with st.container(key="palette_table", gap=0):
            head = st.columns(widths, gap="xsmall", vertical_alignment="center")
            head[1].caption("**Day**")
            head[2].caption("**Night**")
            for label, day_key, night_key in (
                ("Page", "page_day", "page_night"),
                ("Section heading", "heading_day", "heading_night"),
                ("Section background", "section_day", "section_night"),
                ("Heading hover", "hover_day", "hover_night"),
                ("Sidebar", "sidebar_day", "sidebar_night"),
                ("Social and chat", "social_day", "social_night"),
                ("Borders", "border_day", "border_night"),
            ):
                cells = st.columns(widths, gap="xsmall", vertical_alignment="center")
                cells[0].html(f"<div class='pal-name'>{html.escape(label)}</div>")
                for column, part in ((cells[1], day_key), (cells[2], night_key)):
                    state_key = f"colour_{part}"
                    if state_key not in st.session_state:
                        st.session_state[state_key] = account_colours[part]
                    column.color_picker(
                        label,
                        key=state_key,
                        label_visibility="collapsed",
                        persist_state="session",
                    )
    chosen_colours = {
        key: _hex_colour(st.session_state.get(f"colour_{key}"), default)
        for key, default in _THEME_COLOURS
    }

    save_account_settings({
        "days_history": int(days_history),
        "show_reasons": bool(show_reasons),
        "show_extra_metrics": bool(show_extra_metrics),
        "show_period_changes": bool(show_period_changes),
        "popouts_close_on_logout": bool(close_popouts_on_logout),
        "popouts_as_window": bool(popouts_as_window),
        "popouts_fold_section": bool(popouts_fold_section),
        "trade_crypto": bool(trade_crypto),
        "trade_equities": bool(trade_equities),
        "colours": chosen_colours,
    })
    st.session_state._seen_trade_markets = st.session_state.get("trade_markets")
    st.session_state._seen_show_reasons = bool(show_reasons)
    st.session_state._seen_show_extra_metrics = bool(show_extra_metrics)
    st.session_state._seen_show_period_changes = bool(show_period_changes)
    st.session_state._seen_days_history = int(days_history)


def _feedback_setting(env_name: str, *secret_paths: tuple[str, ...]) -> str:
    """A mail setting from the environment, then from Streamlit secrets. Empty when unset."""
    import os

    found = (os.getenv(env_name) or "").strip()
    if found:
        return found
    for path in ((env_name,), *secret_paths):
        found = _optional_secret(*path)
        if found:
            return found
    return ""


def _mailbox(value: str) -> str:
    """The address inside Name <email>, or the text itself."""
    text = " ".join(str(value or "").split())
    if "<" in text and text.endswith(">"):
        text = text.rsplit("<", 1)[-1][:-1].strip()
    return text


def _feedback_mail_settings() -> tuple[str, str, str]:
    """Resend key, sender, and the inbox that receives feedback. Empty pieces stay empty."""
    api_key = _feedback_setting("RESEND_API_KEY", ("resend", "api_key"))
    sender = _feedback_setting("RESEND_FROM", ("resend", "from_email"), ("resend", "from"))
    inbox = _feedback_setting("FEEDBACK_TO", ("resend", "feedback_to"), ("resend", "to"))
    return api_key, sender or "Angstrom Signals <onboarding@resend.dev>", _mailbox(inbox)


def _resend_reason(response) -> str:
    """A short Resend error, with no key or address list."""
    message = ""
    try:
        message = str((response.json() or {}).get("message") or "")
    except Exception:
        message = ""
    message = " ".join(message.split())
    if not message or "re_" in message.lower():
        return f"Resend returned status {response.status_code}"
    return message[:180]


def _email_invite(address: str, inviter_name: str) -> tuple[bool, str]:
    """Mail one invite. The reason is empty when the send is accepted."""
    api_key, sender, _inbox = _feedback_mail_settings()
    if not api_key:
        return False, "the Resend key is missing from the Streamlit secrets"
    safe_name = html.escape(inviter_name or "Someone")
    link = html.escape(_app_url(), quote=True)
    page, plain = render_email(
        f"{safe_name} invited you to Angstrom Signals",
        [
            "Angstrom Signals is market sentiment and technical signals, with the crowd alongside.",
            "It is invite-only while we build with experienced traders. If you are not in yet, "
            f"you can <a href=\"{BETA_REQUEST_URL}\" style=\"color:#1d5fd1;\">ask for a seat</a>.",
        ],
        button=("Open Angstrom Signals", _app_url()),
        preheader=f"{inviter_name or 'Someone'} invited you to Angstrom Signals.",
    )
    payload = {
        "from": sender,
        "to": [address],
        "subject": "You are invited to Angstrom Signals",
        "html": page,
        "text": plain,
    }
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
    except Exception:
        return False, "Resend could not be reached"
    if response.status_code < 300:
        return True, ""
    return False, _resend_reason(response)


def _email_feedback(kind: str, body: str, user_email: str, user_id: str) -> tuple[bool, str]:
    """Mail one saved note. The reason is empty when the send is accepted."""
    api_key, sender, inbox = _feedback_mail_settings()
    if not api_key and not inbox:
        return False, "the Resend key and feedback inbox are missing from the Streamlit secrets"
    if not api_key:
        return False, "the Resend key is missing from the Streamlit secrets"
    if not inbox:
        return False, "the feedback inbox is missing from the Streamlit secrets"
    label = "Enhancement" if kind == "enhancement" else "Issue"
    safe_body = "<br>".join(html.escape(body).splitlines()) or html.escape(body)
    payload = {
        "from": sender,
        "to": [inbox],
        "subject": f"Angstrom feedback: {label}",
        "html": (
            f"<p><strong>{label}</strong> from {html.escape(user_email or 'unknown account')}</p>"
            f"<p>User {html.escape(user_id)} · status submitted</p>"
            f"<p>{safe_body}</p>"
        ),
    }
    if "@" in user_email:
        payload["reply_to"] = user_email
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
    except Exception:
        return False, "Resend could not be reached"
    if response.status_code < 300:
        return True, ""
    return False, _resend_reason(response)


_REPORT_REASONS = {
    "promotion": "Promoting an asset",
    "advice": "Presented as financial advice",
    "harassment": "Harassment or a personal attack",
    "spam": "Spam",
    "other": "Something else",
}


def _report_inbox() -> str:
    """Where a comment report is mailed. The public address unless a secret overrides it."""
    found = _feedback_setting("REPORT_TO", ("resend", "report_to"))
    return _mailbox(found) or "report@angstromsignals.com"


def _email_report(reason: str, note: str, place: str, kind: str, row: dict, asset: str) -> tuple[bool, str]:
    """Mail one comment report. The reason is empty when the send is accepted."""
    api_key, sender, _inbox = _feedback_mail_settings()
    inbox = _report_inbox()
    if not api_key:
        return False, "the Resend key is missing from the Streamlit secrets"
    if not inbox:
        return False, "the report inbox is missing"
    user = st.session_state.user
    user_email = str(getattr(user, "email", "") or "")
    reporter = str(getattr(user, "id", "") or "")
    label = _REPORT_REASONS.get(reason, "Comment report")
    where = "General chat" if place == "chat" else "Social signals"
    note_kind = "reply" if kind == "reply" else "comment"
    safe_note = "<br>".join(html.escape(note).splitlines()) if note else "None"
    payload = {
        "from": sender,
        "to": [inbox],
        "subject": f"Angstrom report: {label}",
        "html": (
            f"<p><strong>{html.escape(label)}</strong> · {html.escape(where)} {html.escape(note_kind)}</p>"
            f"<p>Comment: {html.escape(str(row.get('body') or ''))}</p>"
            f"<p>Author {html.escape(str(row.get('user_id') or ''))}"
            + (f" · {html.escape(asset)}" if asset else "")
            + f"<br>Posted {html.escape(str(row.get('created_at') or ''))}</p>"
            f"<p>Note: {safe_note}</p>"
            f"<p>Reported by {html.escape(user_email or 'unknown account')} · {html.escape(reporter)}</p>"
        ),
    }
    if "@" in user_email:
        payload["reply_to"] = user_email
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
    except Exception:
        return False, "Resend could not be reached"
    if response.status_code < 300:
        return True, ""
    return False, _resend_reason(response)


def _email_barred(address: str) -> tuple[bool, str]:
    """Tell one address that the account is barred. The reason is empty when the send is accepted."""
    api_key, sender, _inbox = _feedback_mail_settings()
    inbox = _report_inbox()
    if not api_key:
        return False, "the Resend key is missing from the Streamlit secrets"
    page, plain = render_email(
        "Your account is barred",
        [
            "Your Angstrom Signals account is barred at this time.",
            f"You can email <a href=\"mailto:{html.escape(inbox, quote=True)}\" style=\"color:#1d5fd1;\">"
            f"{html.escape(inbox)}</a>.",
        ],
        tone="down",
    )
    payload = {
        "from": sender,
        "to": [address],
        "subject": "Your Angstrom Signals account is barred",
        "html": page,
        "text": plain,
    }
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
    except Exception:
        return False, "Resend could not be reached"
    if response.status_code < 300:
        return True, ""
    return False, _resend_reason(response)


def _reported_comment(place: str, kind: str, message_id: int) -> dict | None:
    """The stored comment a report points at. None when that row is gone."""
    if place == "chat":
        table, columns = "chat_messages", "id, user_id, body, created_at"
    elif kind == "reply":
        table, columns = "sentiment_replies", "id, user_id, body, created_at"
    else:
        table, columns = "sentiment_comments", "id, user_id, body, created_at, asset_key"
    response = (
        supabase.table(table)
        .select(columns)
        .eq("id", message_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def _report_action(raw):
    """One comment report from the social panel. None when this run has nothing new."""
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("place") not in ("chat", "signal"):
        return None
    if data.get("reason") not in _REPORT_REASONS:
        return None
    try:
        token = int(data.get("n") or 0)
        message = int(data.get("message") or 0)
    except (TypeError, ValueError):
        return None
    if token <= 0 or message <= 0:
        return None
    return data


def _apply_comment_report(action) -> str:
    """Save one report and email it. The returned note is shown once in the panel."""
    place = action.get("place")
    kind = "reply" if action.get("kind") == "reply" else "comment"
    reason = str(action.get("reason") or "")
    note = " ".join(str(action.get("note") or "").split())[:500]
    if reason == "other" and len(note) < 4:
        return "Report needs a few words when the reason is Something else."
    try:
        message_id = int(action.get("message") or 0)
    except (TypeError, ValueError):
        return "Report could not be sent."
    try:
        row = _reported_comment(place, kind, message_id)
    except Exception:
        return "Report could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again."
    if not row or not str(row.get("body") or "").strip():
        return "Report could not find that comment. It may already have expired."
    author_id = str(row.get("user_id") or "")
    if author_id and author_id == str(user_id):
        return "Report your own comment by deleting it."
    asset = " ".join(str(row.get("asset_key") or action.get("asset") or "").split())[:200]
    user = st.session_state.user
    user_email = str(getattr(user, "email", "") or "")
    payload = {
        "user_id": str(user_id),
        "user_email": user_email or "unknown",
        "place": place,
        "message_id": message_id,
        "message_kind": kind,
        "asset_key": asset,
        "comment_body": " ".join(str(row.get("body") or "").split())[:160],
        "reason": reason,
        "note": note,
        "status": "reported",
    }
    if len(author_id) == 36:
        payload["author_id"] = author_id
    try:
        supabase.table("comment_reports").insert(payload).execute()
    except Exception as exc:
        text = str(exc).lower()
        if "duplicate" in text or "23505" in text:
            return "Report already sent for this comment."
        return "Report could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again."
    sent, why = _email_report(reason, note, place, kind, row, asset)
    if sent:
        return "Report sent. Thank you."
    return f"Report saved. The email was not sent: {why}."


_FEEDBACK_STATUS = {
    "submitted": "Submitted",
    "under_review": "Under review",
    "accepted": "Accepted",
    "in_development": "In development",
    "in_production": "In production",
    "rejected": "Rejected",
    "closed": "Closed",
}
_FEEDBACK_NEXT = {
    "submitted": [("under_review", "Mark under review")],
    "under_review": [("accepted", "Accept"), ("rejected", "Reject")],
    "accepted": [("in_development", "Mark in development")],
    "in_development": [("in_production", "Mark in production")],
    "in_production": [("closed", "Close")],
    "rejected": [("closed", "Close")],
}
_REPORT_STATUS = {
    "reported": "Reported",
    "submitted": "Reported",
    "under_review": "Under review",
    "rejected": "Rejected",
    "upheld": "Upheld",
}
_REPORT_NEXT = {
    "reported": [("under_review", "Mark under review")],
    "submitted": [("under_review", "Mark under review")],
    "under_review": [("rejected", "Reject the report"), ("upheld", "Uphold and remove the comment")],
}


def _admin_when(value) -> str:
    return str(value or "").replace("T", " ")[:16]


def _admin_rows(function: str):
    """Rows for an admin list. None when the database functions are not installed."""
    try:
        response = supabase.rpc(function).execute()
    except Exception:
        return None
    data = response.data
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
    if isinstance(data, dict):
        data = [data]
    return data if isinstance(data, list) else []


def _admin_review(function: str, arguments: dict) -> str:
    """Run one admin status change. Empty means it worked."""
    try:
        result = supabase.rpc(function, arguments).execute()
    except Exception as exc:
        detail = " ".join(str(exc).split())
        if len(detail) > 220:
            detail = detail[:220].rstrip() + "…"
        note = "That could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again."
        return f"{note} ({detail})" if detail else note
    code = str(result.data or "").strip().strip('"')
    return {
        "ok": "",
        "reason": "Write a short reason first.",
        "step": "That status change is not the next step.",
        "missing": "That item is no longer there.",
        "forbidden": "This account cannot change that.",
    }.get(code, "That could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again.")


def _ago(seconds) -> str:
    if seconds is None:
        return "never"
    seconds = float(seconds)
    if seconds < 90:
        return "just now"
    if seconds < 5400:
        return f"{round(seconds / 60)} min ago"
    if seconds < 172800:
        return f"{seconds / 3600:.1f} hours ago"
    return f"{seconds / 86400:.1f} days ago"


def _show_earnings_status() -> None:
    """Whether the earnings date lookups are working. Stocks that were never checked stand out."""
    with st.expander("Earnings dates (lookup status)", expanded=False):
        status = load_earnings_status(supabase)
        if status is None:
            st.caption("The saved earnings dates could not be read.")
            return
        if not status["stocks"]:
            st.caption("No stocks have been saved yet.")
            return
        st.write(
            f"{status['stocks']} stocks: {status['with_date']} with a date, "
            f"{status['none_known']} with none known, {status['never_checked']} never checked."
        )
        st.write(
            f"Last check: {_ago(status['newest_check_ago'])}. "
            f"Oldest check: {_ago(status['oldest_check_ago'])}. A lookup runs about every 12 hours."
        )
        if status["with_date"] == 0 and status["stocks"] >= 3:
            st.warning("No stock has a date. The lookups may be failing, so check the Finnhub key and the app log.")
        st.dataframe(
            [
                {"Stock": line["ticker"], "Next report": line["next_earnings"] or "-",
                 "State": line["state"], "Checked": _ago(line["checked_ago"])}
                for line in status["lines"]
            ],
            hide_index=True,
            width="stretch",
        )


@st.fragment
def admin_panel() -> None:
    """Feedback and comment reports. Only an admin account reaches this section."""
    feedback = _admin_rows("admin_feedback")
    reports = _admin_rows("admin_reports")
    with tracked_expander("Admin", "admin_panel"):
        if feedback is None or reports is None:
            st.caption("Admin tools are not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor.")
            return
        open_reports = [
            row for row in reports
            if isinstance(row, dict) and str(row.get("status") or "") not in ("rejected", "upheld")
        ]
        open_feedback = [
            row for row in feedback
            if isinstance(row, dict) and str(row.get("status") or "") != "closed"
        ]
        with tracked_expander(f"Feedback ({len(open_feedback)} open)", "admin_feedback"):
            st.caption(
                "Click a column title to sort. The list scrolls inside this section once it is long. "
                "Search filters the rows. Closed notes stay hidden until Show closed is on. "
                "Choosing a status saves it. Rejected asks for a reason."
            )
            _show_feedback(feedback)
        with tracked_expander(f"Reported comments ({len(open_reports)} open)", "admin_reports"):
            st.caption(
                "Click a column title to sort. The list scrolls inside this section once it is long. "
                "Search filters the rows. Decided reports stay hidden until Show decided is on. "
                "Choosing a status saves it. Uphold asks you to confirm before the comment is removed. "
                "Reject leaves the comment up and tells the reporter. "
                "Uphold removes the comment, warns the author, and tells the reporter."
            )
            _show_reports(reports)
        _show_beta()
        _show_earnings_status()
        _show_blacklist()
        perf = st.session_state.get("_perf") or {}
        if perf:
            with st.expander("Page timing (last load of the dashboard)", expanded=False):
                st.caption("Milliseconds spent on each step the last time the dashboard drew. Slowest first.")
                for label, spent in sorted(perf.items(), key=lambda item: item[1], reverse=True):
                    st.write(f"{label}: {spent}" if "worked out" in label else f"{label}: {spent} ms")
                runs = st.session_state.get("_perf_runs") or []
                if runs:
                    st.caption(
                        "Recent redraws, newest first. 'whole page' is a full rerun; 'dashboard' is the "
                        "scores, chart and sections redrawing on their own after a click."
                    )
                    for run in reversed(runs):
                        st.write(f"{run['when']} · {run['what']}: {run['ms']} ms")
                lacking = st.session_state.get("_logo_lacking") or []
                st.write("Assets with no stored logo: " + (", ".join(lacking) if lacking else "none"))


def _email_beta_welcome(address: str, name: str) -> tuple[bool, str]:
    """Tell an accepted person how to get in. The reason is empty when the send is accepted."""
    api_key, sender, _inbox = _feedback_mail_settings()
    if not api_key:
        return False, "the Resend key is missing from the Streamlit secrets"
    subject, page, plain = beta_emails.welcome_email(name, _app_url())
    payload = {
        "from": sender,
        "to": [address],
        "subject": subject,
        "html": page,
        "text": plain,
    }
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
    except Exception:
        return False, "Resend could not be reached"
    if response.status_code < 300:
        return True, ""
    return False, _resend_reason(response)


def _beta_call(function: str, arguments: dict) -> str:
    try:
        result = supabase.rpc(function, arguments).execute()
    except Exception:
        return "failed"
    return str(result.data or "").strip().strip('"') or "failed"


def _beta_note(kind: str, text: str) -> None:
    st.session_state["admin_beta_notice"] = f"{kind}\n{text}"


def _beta_review(request_id: int, decision: str, email: str, name: str) -> None:
    """Approve or decline one request before the section redraws."""
    code = _beta_call("review_beta_request", {"request_id": int(request_id), "decision": decision})
    if code != "ok":
        _beta_note("warn", {
            "missing": "That request is no longer there.",
            "forbidden": "This account cannot change beta requests.",
        }.get(code, "That could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again."))
        return
    if decision == "approved":
        sent, why = _email_beta_welcome(email, name)
        if sent:
            _beta_note("ok", f"{email} is approved. The welcome email was sent.")
        else:
            _beta_note("warn", f"{email} is approved. The welcome email was not sent: {why}. Tell them yourself.")
    else:
        _beta_note("ok", f"{email} is declined. No email was sent, and they cannot create an account.")


def _beta_add() -> None:
    clean = _clean_invite_email(st.session_state.get("admin_beta_email"))
    if not clean:
        _beta_note("warn", "Enter a valid email.")
        return
    code = _beta_call("add_beta_email", {"address": clean})
    if code != "ok":
        _beta_note("warn", {
            "exists": "That email is already approved.",
            "email": "Enter a valid email.",
            "forbidden": "This account cannot change beta access.",
        }.get(code, "That could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again."))
        return
    sent, why = _email_beta_welcome(clean, "")
    if sent:
        _beta_note("ok", f"{clean} is approved. The welcome email was sent.")
    else:
        _beta_note("warn", f"{clean} is approved. The welcome email was not sent: {why}. Tell them yourself.")
    st.session_state["admin_beta_clear"] = True


def _beta_set_open() -> None:
    wanted = bool(st.session_state.get("admin_beta_open"))
    code = _beta_call("set_signup_open", {"open_now": wanted})
    st.session_state.pop("_signup_open_seen", None)
    if code != "ok":
        st.session_state["admin_beta_open"] = not wanted
        _beta_note("warn", "That could not be saved.")
    else:
        _beta_note("ok", "Sign-up is open to everyone." if wanted else "Sign-up is closed. Only approved emails can create accounts.")


@st.fragment
def _show_beta() -> None:
    """Beta access requests from the website. Approve to let someone create an account."""
    rows = _admin_rows("admin_beta_requests")
    pending = [r for r in (rows or []) if isinstance(r, dict) and str(r.get("status") or "") == "pending"]
    with tracked_expander(f"Beta requests ({len(pending)} pending)", "admin_beta"):
        if rows is None:
            st.caption("Beta access is not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor.")
            return
        notice = st.session_state.pop("admin_beta_notice", "")
        if notice.startswith("ok\n"):
            st.success(notice[3:])
        elif notice.startswith("warn\n"):
            st.warning(notice[5:])
        st.caption(
            "Requests arrive from the website form. ✓ approves, which lets that email create an account "
            "and sends a welcome email. ✗ declines, or takes approval back. "
            "People who already have an account keep it either way."
        )
        if "admin_beta_open" not in st.session_state:
            try:
                opened = _flag_is_true(supabase.rpc("admin_signup_open").execute().data)
            except Exception:
                opened = False
            st.session_state["admin_beta_open"] = opened
        st.toggle(
            "Open sign-up to everyone (public launch)",
            key="admin_beta_open",
            on_change=_beta_set_open,
            help="Off keeps the closed beta. On puts the Sign Up tab back and lets anyone create an account.",
        )
        if st.session_state.pop("admin_beta_clear", False):
            st.session_state["admin_beta_email"] = ""
        add = st.columns([4.2, 1.2], vertical_alignment="center")
        add[0].text_input(
            "Email to approve",
            key="admin_beta_email",
            placeholder="Approve an email directly: name@example.com",
            label_visibility="collapsed",
        )
        add[1].button("Approve email", key="admin_beta_add", on_click=_beta_add)
        clean_rows = [row for row in rows if isinstance(row, dict)]
        if not clean_rows:
            st.caption("No requests yet.")
            return
        show_decided = st.toggle("Show decided", key="admin_beta_show_decided")
        query = " ".join(str(st.text_input(
            "Search the requests",
            key="admin_beta_search",
            placeholder="Search names, emails, tools or reasons",
            label_visibility="collapsed",
        ) or "").split()).casefold()
        visible = []
        for row in clean_rows:
            if not show_decided and str(row.get("status") or "") != "pending":
                continue
            haystack = " ".join(str(row.get(k) or "") for k in ("name", "email", "phone", "markets", "years_trading", "activity", "tools", "why", "country")).casefold()
            if query and query not in haystack:
                continue
            visible.append(row)
        if not visible:
            st.caption("Nothing pending." if not show_decided else "No request matches that search.")
            return
        titles = ["Applied", "Name", "Email", "Phone", "Markets", "Years", "Active", "Tools", "Why", "Status"]
        status_label = {"pending": "Pending", "approved": "Approved", "declined": "Declined"}
        status_tone = {"pending": "#b45309", "approved": "#15803d", "declined": "#b91c1c"}

        def beta_cell(text, full="", tone=""):
            clean = html.escape(str(text or ""))
            tip = f" title='{html.escape(str(full), quote=True)}'" if full else ""
            style = f" style='color:{tone};font-weight:700;'" if tone else ""
            return f"<div class='bt-cell'{tip}><span{style}>{clean or '&mdash;'}</span></div>"

        with st.container(key="admin_beta_table", gap=0):
            with st.container(key="admin_beta_head", gap=0):
                head = st.columns([20, 0.7, 0.7], vertical_alignment="center")
                head[0].markdown(
                    "<div class='bt-scroll'><div class='bt-row bt-headrow'>"
                    + "".join(f"<div class='bt-cell'>{title}</div>" for title in titles)
                    + "</div></div>",
                    unsafe_allow_html=True,
                )
            for row in visible:
                request_id = int(row.get("id") or 0)
                email = str(row.get("email") or "")
                name = str(row.get("name") or "")
                status = str(row.get("status") or "pending")
                why = " ".join(str(row.get("why") or "").split())
                tools = " ".join(str(row.get("tools") or "").split())
                when = _admin_when(row.get("created_at"))
                cells = st.columns([20, 0.7, 0.7], vertical_alignment="center")
                cells[0].markdown(
                    "<div class='bt-scroll'><div class='bt-row'>"
                    + beta_cell(when.replace(" ", " \u00b7 "))
                    + beta_cell(name)
                    + beta_cell(email)
                    + beta_cell(row.get("phone"))
                    + beta_cell(row.get("markets"))
                    + beta_cell(row.get("years_trading"))
                    + beta_cell(row.get("activity"))
                    + beta_cell(tools, tools)
                    + beta_cell(why, why)
                    + beta_cell(status_label.get(status, status), tone=status_tone.get(status, ""))
                    + "</div></div>",
                    unsafe_allow_html=True,
                )
                if status != "approved":
                    cells[1].button(
                        "✓", key=f"admin_beta_yes_{request_id}", help="Approve and send the welcome email",
                        on_click=_beta_review, args=(request_id, "approved", email, name), use_container_width=True,
                    )
                if status != "declined":
                    cells[2].button(
                        "✗", key=f"admin_beta_no_{request_id}", help="Decline, or take approval back",
                        on_click=_beta_review, args=(request_id, "declined", email, name), use_container_width=True,
                    )


def _feedback_username(row: dict) -> str:
    name = " ".join(str(row.get("username") or "").split())
    if name:
        return name
    email = str(row.get("email") or "")
    if "@" in email:
        return email.split("@", 1)[0]
    return email or "Member"


def _admin_face(name: str, avatar: str, extra: str = "") -> str:
    """A name with that person's photo on the left. A letter stands in when there is no photo."""
    label = " ".join(str(name or "Member").split()) or "Member"
    safe = str(avatar or "").strip()
    if not safe.startswith("https://") or any(mark in safe for mark in (" ", '"', "'", "<", ">", "\\")):
        safe = ""
    if safe:
        face = (
            f"<img src='{html.escape(safe, quote=True)}' alt='' "
            "style='width:18px;height:18px;border-radius:50%;object-fit:cover;flex:none;'>"
        )
    else:
        initial = html.escape(label[:1].upper())
        face = (
            "<span style='width:18px;height:18px;border-radius:50%;background:#dbeafe;color:#1d4ed8;"
            "display:inline-flex;align-items:center;justify-content:center;font-size:.7rem;"
            "font-weight:700;flex:none;line-height:1;'>"
            f"{initial}</span>"
        )
    text = html.escape(label + extra)
    return (
        "<span style='display:inline-flex;align-items:center;gap:6px;vertical-align:middle;'>"
        f"{face}<span>{text}</span></span>"
    )


def _feedback_sort_value(row: dict, key: str) -> str:
    if key == "type":
        return "enhancement" if row.get("kind") == "enhancement" else "issue"
    if key == "comment":
        return str(row.get("body") or "").casefold()
    if key == "username":
        return _feedback_username(row).casefold()
    if key == "email":
        return str(row.get("email") or "").casefold()
    if key == "status":
        return _FEEDBACK_STATUS.get(str(row.get("status") or ""), "").casefold()
    return str(row.get("created_at") or "")


def _show_feedback(rows) -> None:
    clean = [row for row in rows if isinstance(row, dict)]
    if not clean:
        st.caption("No feedback yet.")
        return
    notice = st.session_state.pop("admin_feedback_notice", "")
    if notice:
        st.warning(notice)
    tools = st.columns([4.2, 1.2], vertical_alignment="center")
    query = " ".join(str(tools[0].text_input(
        "Search feedback",
        key="admin_feedback_search",
        placeholder="Search feedback",
        label_visibility="collapsed",
    ) or "").split()).casefold()
    show_closed = tools[1].checkbox("Show closed", key="admin_feedback_show_closed")
    visible = []
    for row in clean:
        status = str(row.get("status") or "")
        if not show_closed and status == "closed":
            continue
        if query:
            haystack = " ".join((
                "enhancement" if row.get("kind") == "enhancement" else "issue",
                str(row.get("body") or ""),
                _admin_when(row.get("created_at")),
                _feedback_username(row),
                str(row.get("email") or ""),
                _FEEDBACK_STATUS.get(status, status),
            )).casefold()
            if query not in haystack:
                continue
        visible.append(row)
    if not visible:
        st.caption("No feedback matches that search." if query else "No open feedback.")
        return
    sort_key = st.session_state.get("admin_feedback_sort", "date")
    sort_desc = bool(st.session_state.get("admin_feedback_sort_desc", True))
    columns = (
        ("type", "Type"),
        ("comment", "Comment"),
        ("date", "Submit date"),
        ("username", "Username"),
        ("email", "Email"),
        ("status", "Status"),
    )
    if sort_key not in {key for key, _title in columns}:
        sort_key = "date"
    widths = [1.1, 3.2, 1.5, 1.4, 2.1, 1.8]
    with st.container(key="admin_feedback_table", gap=0):
        with st.container(key="admin_feedback_head", gap=0):
            header = st.columns(widths, vertical_alignment="center")
            for column, (key, title) in zip(header, columns):
                mark = ""
                if key == sort_key:
                    mark = " ↓" if sort_desc else " ↑"
                if column.button(
                    title + mark,
                    key=f"admin_feedback_sort_{key}",
                    help=f"Sort by {title}",
                    type="tertiary",
                    width="stretch",
                ):
                    if sort_key == key:
                        sort_desc = not sort_desc
                    else:
                        sort_key = key
                        sort_desc = False
                    st.session_state["admin_feedback_sort"] = sort_key
                    st.session_state["admin_feedback_sort_desc"] = sort_desc
        ordered = sorted(
            visible,
            key=lambda row: (_feedback_sort_value(row, sort_key), str(row.get("id") or "")),
            reverse=sort_desc,
        )
        for row in ordered:
            try:
                item_id = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            status = str(row.get("status") or "submitted")
            if status not in _FEEDBACK_STATUS:
                status = "submitted"
            options = [status]
            for step, _label in _FEEDBACK_NEXT.get(status) or []:
                if step not in options:
                    options.append(step)
            kind = "Enhancement" if row.get("kind") == "enhancement" else "Issue"
            comment = html.escape(str(row.get("body") or "").strip()).replace("\n", "<br>")
            cells = st.columns(widths, vertical_alignment="center")
            cells[0].write(kind)
            cells[1].markdown(comment or "—", unsafe_allow_html=True)
            cells[2].write(_admin_when(row.get("created_at")))
            cells[3].markdown(
                _admin_face(_feedback_username(row), str(row.get("avatar") or "")),
                unsafe_allow_html=True,
            )
            cells[4].write(str(row.get("email") or ""))
            choice_key = f"admin_feedback_status_{item_id}"
            reset = st.session_state.pop(f"admin_feedback_reset_{item_id}", None)
            if reset in options:
                st.session_state[choice_key] = reset
            elif st.session_state.get(choice_key) not in options:
                st.session_state[choice_key] = status
            picked = cells[5].selectbox(
                "Status",
                options,
                format_func=lambda value: _FEEDBACK_STATUS.get(value, value),
                key=choice_key,
                label_visibility="collapsed",
                disabled=len(options) < 2,
            )
            if picked == status:
                continue
            reason = ""
            if picked == "rejected":
                reason = cells[5].text_input(
                    "Rejection reason",
                    key=f"admin_feedback_reason_{item_id}",
                    max_chars=500,
                    placeholder="Rejection reason",
                    label_visibility="collapsed",
                )
                if not cells[5].button("Save rejection", key=f"admin_feedback_reject_{item_id}"):
                    continue
                if len(" ".join(str(reason).split())) < 4:
                    cells[5].caption("Write a short reason first.")
                    continue
            problem = _admin_review("review_feedback", {
                "note_id": item_id,
                "next_status": picked,
                "reason": reason,
            })
            if problem:
                st.session_state[f"admin_feedback_reset_{item_id}"] = status
                st.session_state["admin_feedback_notice"] = problem
            _rerun_fragment()


def _blacklist_call(function: str, address: str) -> str:
    try:
        result = supabase.rpc(function, {"address": address}).execute()
    except Exception:
        return "failed"
    return str(result.data or "").strip().strip('"') or "failed"


def _blacklist_add() -> None:
    """Bar one email before the blacklist section redraws. The button click redraws that section."""
    clean = _clean_invite_email(st.session_state.get("admin_blacklist_email"))
    if not clean:
        st.session_state["admin_blacklist_notice"] = "warn\nEnter a valid email."
        return
    code = _blacklist_call("add_blacklist_email", clean)
    if code != "ok":
        st.session_state["admin_blacklist_notice"] = "warn\n" + {
            "exists": "That email is already on the list.",
            "self": "That is the admin account. It stays able to log in.",
            "email": "Enter a valid email.",
            "forbidden": "This account cannot change the blacklist.",
        }.get(code, "That could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again.")
        return
    sent, why = _email_barred(clean)
    if sent:
        st.session_state["admin_blacklist_notice"] = f"ok\n{clean} is barred. The email was sent."
    else:
        st.session_state["admin_blacklist_notice"] = f"warn\n{clean} is barred. The email was not sent: {why}."
    st.session_state["admin_blacklist_clear"] = True


def _blacklist_remove(email: str) -> None:
    """Lift one bar before the blacklist section redraws. The rest of the page stays as it is."""
    code = _blacklist_call("remove_blacklist_email", email)
    if code == "ok":
        st.session_state["admin_blacklist_notice"] = f"ok\n{email} was removed."
    elif code == "missing":
        st.session_state["admin_blacklist_notice"] = "warn\nThat email is no longer on the list."
    else:
        st.session_state["admin_blacklist_notice"] = "warn\nThat could not be removed."


@st.fragment
def _show_blacklist() -> None:
    """Add, search, and remove barred emails. Only the admin panel calls this."""
    rows = _admin_rows("admin_blacklist")
    with tracked_expander(
        f"Blacklist ({len(rows) if rows is not None else 0})",
        "admin_blacklist",
    ):
        if rows is None:
            st.caption("The blacklist is not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor.")
            return
        notice = st.session_state.pop("admin_blacklist_notice", "")
        if notice.startswith("ok\n"):
            st.success(notice[3:])
        elif notice.startswith("warn\n"):
            st.warning(notice[5:])
        st.caption(
            "Click a column title to sort. The list scrolls inside this section once it is long. "
            "Search filters the rows. A barred email cannot log in or sign up. "
            "An open session is closed, and that address is emailed. "
            "The × removes an email and lets that person log in again."
        )
        if st.session_state.pop("admin_blacklist_clear", False):
            st.session_state["admin_blacklist_email"] = ""
        add = st.columns([4.2, 1.2], vertical_alignment="center")
        add[0].text_input(
            "Email to bar",
            key="admin_blacklist_email",
            placeholder="name@example.com",
            label_visibility="collapsed",
        )
        add[1].button("Add to blacklist", key="admin_blacklist_add", on_click=_blacklist_add)
        clean_rows = [row for row in rows if isinstance(row, dict)]
        if not clean_rows:
            st.caption("No barred emails.")
            return
        query = " ".join(str(st.text_input(
            "Search the blacklist",
            key="admin_blacklist_search",
            placeholder="Search emails",
            label_visibility="collapsed",
        ) or "").split()).casefold()
        visible = [
            row for row in clean_rows
            if not query or query in str(row.get("email") or "").casefold()
        ]
        if not visible:
            st.caption("No email matches that search.")
            return
        sort_key = st.session_state.get("admin_blacklist_sort", "date")
        sort_desc = bool(st.session_state.get("admin_blacklist_sort_desc", True))
        columns = (("email", "Email"), ("date", "Added"))
        if sort_key not in {key for key, _title in columns}:
            sort_key = "date"
        widths = [4.2, 1.8, 0.4]
        with st.container(key="admin_blacklist_table", gap=0):
            with st.container(key="admin_blacklist_head", gap=0):
                header = st.columns(widths, vertical_alignment="center")
                for column, (key, title) in zip(header, columns):
                    mark = ""
                    if key == sort_key:
                        mark = " ↓" if sort_desc else " ↑"
                    if column.button(
                        title + mark,
                        key=f"admin_blacklist_sort_{key}",
                        help=f"Sort by {title}",
                        type="tertiary",
                        width="stretch",
                    ):
                        if sort_key == key:
                            sort_desc = not sort_desc
                        else:
                            sort_key = key
                            sort_desc = key == "date"
                        st.session_state["admin_blacklist_sort"] = sort_key
                        st.session_state["admin_blacklist_sort_desc"] = sort_desc
            ordered = sorted(
                visible,
                key=lambda row: (
                    str(row.get("created_at") or "") if sort_key == "date" else str(row.get("email") or "").casefold(),
                    str(row.get("email") or ""),
                ),
                reverse=sort_desc,
            )
            for row in ordered:
                email = str(row.get("email") or "")
                cells = st.columns(widths, vertical_alignment="center")
                cells[0].write(email)
                cells[1].write(_admin_when(row.get("created_at")))
                cells[2].button(
                    "×",
                    key=f"admin_blacklist_remove_{email}",
                    help="Remove from the blacklist",
                    on_click=_blacklist_remove,
                    args=(email,),
                )


def _report_where(row: dict) -> str:
    place = "General chat" if row.get("place") == "chat" else "Social signals"
    kind = "reply" if row.get("message_kind") == "reply" else "comment"
    asset = " ".join(str(row.get("asset_key") or "").split())
    text = f"{place} {kind}"
    if asset:
        text += f" · {asset}"
    return text


def _report_person(row: dict, name_key: str, email_key: str) -> str:
    name = " ".join(str(row.get(name_key) or "").split())
    if name:
        return name
    email = str(row.get(email_key) or "")
    if "@" in email:
        return email.split("@", 1)[0]
    return email or "Member"


def _report_sort_value(row: dict, key: str) -> str:
    if key == "comment":
        return str(row.get("comment_body") or "").casefold()
    if key == "reason":
        return _REPORT_REASONS.get(str(row.get("reason") or ""), str(row.get("reason") or "")).casefold()
    if key == "author":
        return _report_person(row, "author_name", "").casefold()
    if key == "reporter":
        return _report_person(row, "reporter_name", "reporter_email").casefold()
    if key == "status":
        status = str(row.get("status") or "")
        return _REPORT_STATUS.get(status, status).casefold()
    return str(row.get("created_at") or "")


def _show_reports(rows) -> None:
    clean = [row for row in rows if isinstance(row, dict)]
    if not clean:
        st.caption("No reports yet.")
        return
    notice = st.session_state.pop("admin_report_notice", "")
    if notice:
        st.warning(notice)
    tools = st.columns([4.2, 1.3], vertical_alignment="center")
    query = " ".join(str(tools[0].text_input(
        "Search reports",
        key="admin_reports_search",
        placeholder="Search reports",
        label_visibility="collapsed",
    ) or "").split()).casefold()
    show_decided = tools[1].checkbox("Show decided", key="admin_reports_show_decided")
    visible = []
    for row in clean:
        status = str(row.get("status") or "")
        if not show_decided and status in ("rejected", "upheld"):
            continue
        if query:
            haystack = " ".join((
                str(row.get("comment_body") or ""),
                _report_where(row),
                _REPORT_REASONS.get(str(row.get("reason") or ""), str(row.get("reason") or "")),
                str(row.get("note") or ""),
                _admin_when(row.get("created_at")),
                _report_person(row, "author_name", ""),
                _report_person(row, "reporter_name", "reporter_email"),
                str(row.get("reporter_email") or ""),
                _REPORT_STATUS.get(status, status),
            )).casefold()
            if query not in haystack:
                continue
        visible.append(row)
    if not visible:
        st.caption("No reports match that search." if query else "No open reports.")
        return
    sort_key = st.session_state.get("admin_reports_sort", "date")
    sort_desc = bool(st.session_state.get("admin_reports_sort_desc", True))
    columns = (
        ("comment", "Comment"),
        ("reason", "Reason"),
        ("date", "Reported"),
        ("author", "Author"),
        ("reporter", "Reporter"),
        ("status", "Status"),
    )
    if sort_key not in {key for key, _title in columns}:
        sort_key = "date"
    widths = [2.4, 1.6, 1.35, 1.25, 1.45, 1.55]
    with st.container(key="admin_reports_table", gap=0):
        with st.container(key="admin_reports_head", gap=0):
            header = st.columns(widths, vertical_alignment="center")
            for column, (key, title) in zip(header, columns):
                mark = ""
                if key == sort_key:
                    mark = " ↓" if sort_desc else " ↑"
                if column.button(
                    title + mark,
                    key=f"admin_reports_sort_{key}",
                    help=f"Sort by {title}",
                    type="tertiary",
                    width="stretch",
                ):
                    if sort_key == key:
                        sort_desc = not sort_desc
                    else:
                        sort_key = key
                        sort_desc = False
                    st.session_state["admin_reports_sort"] = sort_key
                    st.session_state["admin_reports_sort_desc"] = sort_desc
        ordered = sorted(
            visible,
            key=lambda row: (_report_sort_value(row, sort_key), str(row.get("id") or "")),
            reverse=sort_desc,
        )
        for row in ordered:
            try:
                item_id = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            status = str(row.get("status") or "reported")
            if status not in _REPORT_STATUS:
                status = "reported"
            options = [status]
            for step, _label in _REPORT_NEXT.get(status) or []:
                if step not in options:
                    options.append(step)
            comment = html.escape(" ".join(str(row.get("comment_body") or "").split()))
            where = html.escape(_report_where(row))
            comment = f"{comment or '—'}<br><span style='opacity:.72'>{where}</span>"
            reason = html.escape(_REPORT_REASONS.get(str(row.get("reason") or ""), str(row.get("reason") or "")))
            note = " ".join(str(row.get("note") or "").split())
            if note:
                reason += f"<br><span style='opacity:.72'>{html.escape(note)}</span>"
            author = _report_person(row, "author_name", "")
            try:
                warnings = int(row.get("warnings") or 0)
            except (TypeError, ValueError):
                warnings = 0
            warning = ""
            if warnings:
                warning = " · 1 warning" if warnings == 1 else f" · {warnings} warnings"
            cells = st.columns(widths, vertical_alignment="center")
            cells[0].markdown(comment, unsafe_allow_html=True)
            cells[1].markdown(reason or "—", unsafe_allow_html=True)
            cells[2].write(_admin_when(row.get("created_at")))
            cells[3].markdown(
                _admin_face(author, str(row.get("author_avatar") or ""), warning),
                unsafe_allow_html=True,
            )
            cells[4].markdown(
                _admin_face(
                    _report_person(row, "reporter_name", "reporter_email"),
                    str(row.get("reporter_avatar") or ""),
                ),
                unsafe_allow_html=True,
            )
            choice_key = f"admin_report_status_{item_id}"
            reset = st.session_state.pop(f"admin_report_reset_{item_id}", None)
            if reset in options:
                st.session_state[choice_key] = reset
            elif st.session_state.get(choice_key) not in options:
                st.session_state[choice_key] = status
            picked = cells[5].selectbox(
                "Status",
                options,
                format_func=lambda value: _REPORT_STATUS.get(value, value),
                key=choice_key,
                label_visibility="collapsed",
                disabled=len(options) < 2,
            )
            if picked == status:
                continue
            if picked == "upheld" and not cells[5].button(
                "Remove comment",
                key=f"admin_report_uphold_{item_id}",
            ):
                continue
            problem = _admin_review("review_comment_report", {
                "report_id": item_id,
                "next_status": picked,
            })
            if problem:
                st.session_state[f"admin_report_reset_{item_id}"] = status
                st.session_state["admin_report_notice"] = problem
            _rerun_fragment()


def _store_feedback(kind: str, body: str) -> str:
    """Save one note as submitted and email it. The message says which part worked."""
    text = body.strip()
    if not text:
        return "Write a few words first."
    user = st.session_state.user
    user_id = str(getattr(user, "id", "") or "")
    user_email = str(getattr(user, "email", "") or "")
    try:
        supabase.table("feedback_notes").insert({
            "user_id": user_id,
            "user_email": user_email or "unknown",
            "kind": kind,
            "body": text[:4000],
            "status": "submitted",
        }).execute()
    except Exception:
        return "That could not be saved. Please try again."
    sent, reason = _email_feedback(kind, text[:4000], user_email, user_id)
    if sent:
        return "Saved and emailed. Thank you."
    return f"Saved. The email was not sent: {reason}."


@st.fragment
def feedback_form() -> None:
    """Issue or enhancement. Choosing one redraws this form, not the page."""
    if st.session_state.pop("feedback_clear", False):
        st.session_state["feedback_body"] = ""
    st.caption("An issue or an idea. It is stored as submitted, with your account and the date.")
    feedback_kind = st.radio(
        "Type",
        ["Issue", "Enhancement"],
        horizontal=True,
        key="feedback_kind",
    )
    feedback_body = st.text_area(
        "Details",
        max_chars=4000,
        height=120,
        key="feedback_body",
        placeholder="What happened, or what would you like?",
    )
    if st.button("Submit", key="feedback_submit", use_container_width=True):
        st.session_state.feedback_notice = _store_feedback(
            "enhancement" if feedback_kind == "Enhancement" else "issue",
            feedback_body,
        )
        if str(st.session_state.feedback_notice).startswith("Saved"):
            st.session_state.feedback_clear = True
        _rerun_fragment()
    feedback_notice = st.session_state.pop("feedback_notice", "")
    if feedback_notice.startswith("Saved and emailed"):
        st.success(feedback_notice)
    elif feedback_notice.startswith("Saved"):
        st.warning(feedback_notice)
    elif feedback_notice:
        st.warning(feedback_notice)


with tracked_expander("📝 Feedback", "feedback", sidebar=True):
    feedback_form()

with tracked_expander("ℹ️ About", "about", sidebar=True):
    st.markdown(_brand_mark(72), unsafe_allow_html=True)
    st.markdown("**angstrom signals**")
    st.caption("Market sentiment and technical signals, with the crowd alongside.")
    st.markdown(
        "Angstrom Signals is a platform for traders who want aggregated signals "
        "for whole markets and for individual assets. Technical scores and market "
        "sentiment sit together and update as conditions change. A real-time social "
        "stream lets the crowd react alongside those signals."
    )
    st.markdown(
        "General: [info@angstromsignals.com](mailto:info@angstromsignals.com)  \n"
        "Support: [support@angstromsignals.com](mailto:support@angstromsignals.com)  \n"
        "Investors: [investors@angstromsignals.com](mailto:investors@angstromsignals.com)"
    )
    with tracked_expander("Socials policy", "socials_policy"):
        st.markdown(
            "The social signals stream and the general chat are for reacting to the signals on this page."
        )
        st.markdown(
            "Nothing on this site is financial advice. A comment, a reply, a thumb, or a crowd score "
            "is one person's reaction. It is not a recommendation to buy, sell, or hold any asset."
        )
        st.markdown(
            "Do not promote an asset. That includes telling people to buy or sell, posting a tip or a "
            "referral link, or pushing a coin or ticker the note is not answering."
        )
        st.markdown(
            "Be civil. No harassment, threats, or personal attacks. No spam, and no posting the same note over and over."
        )
        st.markdown(
            "Use the flag on a comment that breaks these rules. The form opens at the top of the social panel. "
            "It is emailed to [report@angstromsignals.com](mailto:report@angstromsignals.com) "
            "and is not shown to the crowd. A comment that breaks these rules can be removed."
        )
    with tracked_expander("Terms", "terms"):
        st.markdown("Last updated 26 October 2026.")
        st.markdown(
            "Using Angstrom Signals means you accept these terms and the socials policy above. "
            "If you do not accept them, do not use the site."
        )
        st.markdown(
            "The site is a research tool. Scores, sentiment, alerts, and comments are information "
            "for you to read. They are not financial advice, not a recommendation to buy, sell, or hold, "
            "and not an offer from us. We do not hold your money or place trades for you."
        )
        st.markdown(
            "Figures can be late, missing, or wrong. A past score is not a promise of what happens next. "
            "You decide what to do with your own money, and you carry that risk."
        )
        st.markdown(
            "Keep your sign-in to yourself. You are responsible for what is posted from your account. "
            "We can remove a comment that breaks the socials policy, and we can close an account that "
            "breaks these terms or is barred."
        )
        st.markdown(
            "The site can change, pause, or stop. These terms can change too. The date above is the version "
            "on the site. Questions go to [info@angstromsignals.com](mailto:info@angstromsignals.com)."
        )
    with tracked_expander("Privacy", "privacy"):
        st.markdown("Last updated 26 October 2026.")
        st.markdown(
            "We keep the details needed to run your account. That is your email, and if you sign in with "
            "Google, the name and email Google shares for that sign-in. A password is stored by the sign-in "
            "service, not on this page."
        )
        st.markdown(
            "We also keep what you add: display name, bio, picture, watchlists, weights, colours, and other "
            "settings. Comments, chat, replies, favourites, groups, feedback, and reports of comments are "
            "stored with your account. If you turn alerts on, we store those alerts and email the ones you asked for."
        )
        st.markdown(
            "The account and the page are stored with Supabase. Mail is sent with Resend. Google is used only "
            "if you choose that sign-in. Market prices and sentiment come from data providers and are not your "
            "personal details. A short-lived cookie is used to finish a Google sign-in. If you tick Keep me signed in, one more cookie holds your sign-in on that device for up to 30 days, and logging out removes it. A small cookie also remembers whether you ticked the box, for up to a year, and holds no sign-in details. We do not sell personal information."
        )
        st.markdown(
            "Email [support@angstromsignals.com](mailto:support@angstromsignals.com) to ask what we hold, "
            "to correct it, or to close the account. Reports of comments go to "
            "[report@angstromsignals.com](mailto:report@angstromsignals.com)."
        )


@st.cache_data(ttl=300)
def load_crypto(coin_id, days, nonce):
    del nonce
    return fetch_crypto_data(coin_id, days)


@st.cache_data(ttl=300)
def load_stock(ticker, days, nonce):
    del nonce
    return fetch_stock_data(ticker, period=period_for_days(days))


# Market caps move slowly, so ask the data providers about every half hour, not every five minutes.
_CAPS_SECONDS = 1800


_CAPS_STORE: dict = {}
_CAPS_BUSY: set = set()
_CAPS_RETRY_SECONDS = 120


def _fetch_market_caps(token, crypto_ids, stock_tickers) -> dict:
    """Ask the data providers, keep the answer, and save it for next time. Safe to run behind the scenes.
    An empty answer is a failed ask, not a result, so the last good numbers stay and it tries again soon."""
    previous = _CAPS_STORE.get(token)
    base = previous[1] if previous else {"crypto": {}, "rank": {}, "stock": {}}
    try:
        crypto_stats = crypto_market_stats(crypto_ids) if crypto_ids else {}
        stock_caps = stock_market_caps(stock_tickers) if stock_tickers else {}
        fresh = {
            "crypto": {k: v["cap"] for k, v in crypto_stats.items() if v.get("cap") is not None},
            "rank": {k: v["rank"] for k, v in crypto_stats.items() if v.get("rank") is not None},
            "stock": dict(stock_caps),
        }
        complete = (not crypto_ids or bool(crypto_stats)) and (not stock_tickers or bool(stock_caps))
        merged = {name: {**base.get(name, {}), **fresh[name]} for name in fresh}
        if complete:
            _CAPS_STORE[token] = (time.time(), merged)
        else:
            _CAPS_STORE[token] = (time.time() - _CAPS_SECONDS + _CAPS_RETRY_SECONDS, merged)
        rows = [
            {"kind": "Crypto", "asset_id": coin_id, "cap": stats.get("cap"), "rank": stats.get("rank")}
            for coin_id, stats in crypto_stats.items()
        ]
        rows += [{"kind": "Stock", "asset_id": ticker, "cap": cap, "rank": None} for ticker, cap in stock_caps.items()]
        save_market_stats(supabase, rows)
        return merged
    except Exception as exc:
        print(f"market caps failed: {exc}")
        _CAPS_STORE[token] = (time.time() - _CAPS_SECONDS + _CAPS_RETRY_SECONDS, base)
        return base
    finally:
        _CAPS_BUSY.discard(token)


def load_market_caps(crypto_ids, stock_tickers, nonce, shared=None):
    """Market caps and crypto ranks for the watchlists. They are saved in the database, so a restart
    shows the last saved numbers straight away. The very first ask with nothing saved waits for the
    answer. After that the page never waits, and a refresh runs behind the scenes about every half hour."""
    token = (tuple(crypto_ids), tuple(stock_tickers))
    stored = _CAPS_STORE.get(token)
    if stored is None:
        # Even numbers from days ago beat making the page wait. The refresh below replaces them.
        saved = market_stats_from_rows(shared or {}, max_age_seconds=30 * 24 * 3600)
        wanted_crypto = {str(c).lower() for c in crypto_ids}
        wanted_stock = {str(t).upper() for t in stock_tickers}
        from_db = {
            "crypto": {k: v["cap"] for k, v in saved["crypto"].items() if k in wanted_crypto and v.get("cap") is not None},
            "rank": {k: v["rank"] for k, v in saved["crypto"].items() if k in wanted_crypto and v.get("rank") is not None},
            "stock": {k: v["cap"] for k, v in saved["stock"].items() if k in wanted_stock and v.get("cap") is not None},
        }
        if from_db["crypto"] or from_db["stock"]:
            _CAPS_STORE[token] = (time.time() - _CAPS_SECONDS - 1, from_db)
            stored = _CAPS_STORE[token]
        else:
            _CAPS_BUSY.add(token)
            return _fetch_market_caps(token, crypto_ids, stock_tickers)
    saved_at, data = stored
    asked_nonce = st.session_state.get("_caps_nonce_seen")
    wanted_now = asked_nonce is not None and asked_nonce != nonce
    st.session_state["_caps_nonce_seen"] = nonce
    if (time.time() - saved_at > _CAPS_SECONDS or wanted_now) and token not in _CAPS_BUSY:
        _CAPS_BUSY.add(token)
        _background(_fetch_market_caps, token, crypto_ids, stock_tickers)
    return data


_BACKGROUND = ThreadPoolExecutor(max_workers=2)
_SCORING_NOW = 0
_SCORING_LOCK = threading.Lock()


class _scoring_busy:
    """Marks that scores are being worked out, so background jobs wait their turn instead of
    competing with the page for the same processor."""

    def __enter__(self):
        global _SCORING_NOW
        with _SCORING_LOCK:
            _SCORING_NOW += 1

    def __exit__(self, *_exc):
        global _SCORING_NOW
        with _SCORING_LOCK:
            _SCORING_NOW = max(0, _SCORING_NOW - 1)
        return False


def _run_when_quiet(function, *args):
    """Run a background job once no page is working out scores. It never waits longer than 30 seconds."""
    waited = 0.0
    while _SCORING_NOW > 0 and waited < 30:
        time.sleep(0.1)
        waited += 0.1
    return function(*args)


def _background(function, *args) -> None:
    _BACKGROUND.submit(_run_when_quiet, function, *args)


_EARN_STORE: dict = {}
_EARN_BUSY: set = set()
_EARN_SECONDS = 12 * 3600


def _fetch_earnings(token) -> None:
    """Look up each stock's next report date behind the scenes, keep it, and save it for next time."""
    try:
        found = stock_next_earnings(list(token))
        previous = _EARN_STORE.get(token)
        # A stock the lookup could not answer keeps the date it had.
        kept = {**(previous[1] if previous else {}), **found}
        _EARN_STORE[token] = (time.time(), kept)
        save_earnings(supabase, found)
    except Exception as exc:
        print(f"earnings dates failed: {exc}")
        previous = _EARN_STORE.get(token)
        _EARN_STORE[token] = (time.time() - _EARN_SECONDS + 600, previous[1] if previous else {})
    finally:
        _EARN_BUSY.discard(token)


def load_earnings(stock_tickers, shared=None) -> dict:
    """{TICKER: "YYYY-MM-DD" or None}. Never makes the page wait: it uses what is saved, and the
    lookup runs behind the scenes about twice a day. A stock shows a dash until its first lookup is done."""
    token = tuple(str(t).upper() for t in stock_tickers)
    if not token:
        return {}
    stored = _EARN_STORE.get(token)
    if stored is None:
        saved = earnings_from_rows(shared or {})
        data = {ticker: saved[ticker] for ticker in token if ticker in saved}
        complete = len(data) == len(token)
        stored = (time.time() if complete else 0.0, data)
        _EARN_STORE[token] = stored
    saved_at, data = stored
    if time.time() - saved_at > _EARN_SECONDS and token not in _EARN_BUSY:
        _EARN_BUSY.add(token)
        _background(_fetch_earnings, token)
    return data


@st.cache_data(ttl=3600, show_spinner=False)
def _past_report_dates(ticker: str) -> list:
    """Past earnings days we saw held until the report. Empty until history has been saved."""
    return held_report_dates(load_earnings_history(supabase, ticker))


@contextmanager
def _timed(label: str):
    """Record how long a step took on this load. The Admin panel shows the list."""
    started = time.perf_counter()
    try:
        yield
    finally:
        spent = (time.perf_counter() - started) * 1000
        try:
            st.session_state.setdefault("_perf", {})[label] = round(spent)
        except Exception:
            pass
        print(f"perf {label}: {spent:.0f} ms")


def _together(jobs: dict) -> dict:
    """Run independent lookups at the same time. Each job is a function with no arguments.
    A job that fails is run again on its own, so the page still draws."""
    if len(jobs) < 2:
        return {name: job() for name, job in jobs.items()}
    results = {}
    failed = []
    with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as pool:
        futures = {name: pool.submit(job) for name, job in jobs.items()}
        for name, future in futures.items():
            try:
                results[name] = future.result(timeout=60)
            except Exception:
                failed.append(name)
    for name in failed:
        results[name] = jobs[name]()
    return results


_SCORES_WORKED_OUT = 0


@st.cache_data(ttl=900, max_entries=4000, show_spinner=False)
def _scored_asset(kind: str, asset_id: str, days: int, weights_key: tuple, stamp: tuple, _df, adaptive: bool = False):
    """The indicators and score for one asset. The same prices and weights give the same answer,
    so it is worked out once and reused across clicks and across accounts."""
    del kind, asset_id, days, stamp
    global _SCORES_WORKED_OUT
    _SCORES_WORKED_OUT += 1
    frame = calculate_indicators(_df)
    return compute_score(frame, weights=dict(weights_key) if weights_key else None, adaptive=adaptive)


def load_market_sentiment(query: str, enabled: bool, force: bool = False):
    return analyze_market_sentiment(query, enabled, force=force)


def _chat_viewer() -> dict:
    """The signed-in name and picture shown on a comment posted from this page."""
    email = getattr(st.session_state.user, "email", "") or ""
    name = " ".join(str((profile or {}).get("display_name") or "").split())
    if not name and "@" in email:
        name = email.split("@", 1)[0]
    avatar = str((profile or {}).get("avatar_url") or "").strip()
    if not avatar.startswith("https://") or any(mark in avatar for mark in (" ", '"', "'", "<", ">", "\\")):
        avatar = ""
    try:
        social = int((profile or {}).get("social_score") or 0)
    except (TypeError, ValueError):
        social = 0
    return {
        "id": str(user_id or ""),
        "name": (name or "Member")[:40],
        "avatar": avatar,
        "social": social if social > 0 else 0,
    }


def _favourite_event(raw):
    """One star press from the panel. None when this run has nothing new."""
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        token = int(data.get("n") or 0)
    except (TypeError, ValueError):
        return None
    if token <= 0:
        return None
    return data


def _apply_favourite(data) -> str:
    """Save or remove one person on this account. The returned note is shown once."""
    target = str(data.get("user") or "").strip().lower()
    allowed = _favourite_ids([target])
    if not allowed:
        return ""
    try:
        stored = prefs.setdefault("settings", {})
        current = _favourite_ids(stored.get("favourites"))
        person = allowed[0]
        if data.get("on"):
            if person not in current:
                current.append(person)
        else:
            current = [item for item in current if item != person]
        if current != _favourite_ids(stored.get("favourites")):
            save_account_settings({"favourites": current})
        return ""
    except Exception:
        return "That favourite could not be saved. Try again."


def _apply_group_invite(data) -> str:
    """Invite one person into a group this account leads. The note is shown once."""
    allowed = _favourite_ids([str(data.get("user") or "")])
    if not allowed:
        return ""
    name = " ".join(str(data.get("name") or "").split())[:40]
    try:
        chosen = int(data.get("group") or 0)
    except (TypeError, ValueError):
        chosen = 0
    try:
        result = supabase.rpc("create_group_invite", {
            "target": allowed[0],
            "group_name": name,
            "chosen_group": chosen or None,
        }).execute()
    except Exception:
        return "That invite could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again."
    code = str(result.data or "").strip().strip('"')
    return {
        "ok": "Invite sent.",
        "member": "They are already in that group.",
        "pending": "They already have an invite to that group.",
        "limit": "You already have 20 groups.",
        "full": "That group already has 50 members.",
        "name": "Enter a group name of up to 40 characters.",
        "missing": "Choose a group you lead, or enter a new name.",
        "self": "",
    }.get(code, "That invite could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again.")


def _chat_action(raw):
    """One post or thumb from the chat panel. None when this run has nothing new."""
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("action") not in ("post", "vote", "delete"):
        return None
    try:
        token = int(data.get("n") or 0)
    except (TypeError, ValueError):
        return None
    if token <= 0:
        return None
    return data


def _apply_chat_action(action) -> str:
    """Save a chat post or thumb. The returned note is shown once in the panel."""
    try:
        if action.get("action") == "post":
            parent = int(action.get("parent") or 0)
            post_chat(supabase, user_id, action.get("text") or "", parent or None)
            return ""
        if action.get("action") == "delete":
            delete_chat_message(supabase, user_id, int(action.get("message") or 0))
            return ""
        message_id = int(action.get("message") or 0)
        vote = int(action.get("vote") or 0)
        set_chat_vote(supabase, user_id, message_id, vote)
        return ""
    except Exception:
        return "That could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again."


def _apply_signal_action(action) -> str:
    """Save a thumb or a reply on a social signals comment."""
    try:
        if action.get("action") == "post":
            post_signal_reply(supabase, user_id, int(action.get("parent") or 0), action.get("text") or "")
            return ""
        if action.get("action") == "delete":
            delete_signal_message(
                supabase,
                user_id,
                int(action.get("message") or 0),
                "reply" if action.get("kind") == "reply" else "comment",
            )
            return ""
        set_signal_vote(
            supabase,
            user_id,
            int(action.get("message") or 0),
            int(action.get("vote") or 0),
            "reply" if action.get("kind") == "reply" else "comment",
        )
        return ""
    except Exception:
        return "That could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again."


def _social_stream_json(crypto_watchlist, stock_watchlist, shared, logos, feed) -> str:
    """The comments for the social stream, as the panel reads them."""
    crypto_keys = [asset_market_key("Crypto", asset_id) for asset_id in crypto_watchlist]
    stock_keys = [asset_market_key("Stock", asset_id) for asset_id in stock_watchlist]
    market_keys = crypto_keys + stock_keys
    stream_names = {}
    for kind, watchlist in (("Crypto", crypto_watchlist), ("Stock", stock_watchlist)):
        for asset_id, label in watchlist.items():
            market_key = asset_market_key(kind, asset_id)
            shown = " ".join(str(label or "").split())
            if kind == "Stock":
                ticker = str(asset_id).upper()
                if ticker and ticker not in shown.upper():
                    shown = f"{shown} ({ticker})" if shown else ticker
            stream_names[market_key] = shown or str(asset_id)
    stream_names["Mood|crypto"] = "Crypto market"
    stream_names["Mood|stock"] = "Stock market"
    return json.dumps(
        social_stream_items(
            feed, shared, stream_names, logos, market_keys,
            {"crypto": crypto_keys, "stock": stock_keys},
            sentiment_replies(supabase),
        ),
        ensure_ascii=False,
    )


def _share_market_rows(crypto_watchlist, stock_watchlist, crypto_results, stock_results):
    """Save this refresh's closes and reuse any headline score already stored."""
    priced = []
    for kind, results in (("Crypto", crypto_results), ("Stock", stock_results)):
        for row in results:
            priced.append({"kind": kind, "asset_id": row.get("key"), "closes": row.get("closes")})
    pairs = [("Crypto", asset_id) for asset_id in crypto_watchlist]
    pairs += [("Stock", asset_id) for asset_id in stock_watchlist]
    crypto_keys = [asset_market_key("Crypto", asset_id) for asset_id in crypto_watchlist]
    stock_keys = [asset_market_key("Stock", asset_id) for asset_id in stock_watchlist]
    market_keys = crypto_keys + stock_keys
    # The prices were read a moment ago at the top of this load. Read them again only when
    # something has just been saved, or the earlier read was empty.
    earlier = st.session_state.get("_shared_rows")
    # An asset with no saved row yet is simply missing, and reading again would not change that.
    reuse_shared = earlier is not None and not st.session_state.get("_shared_reread")
    # Saving the closes is not needed to draw the page, so it runs behind the scenes.
    _background(save_price_paths, supabase, priced)
    prefetch = st.session_state.get("_prefetch") or {}
    jobs = {}
    if not reuse_shared:
        jobs["shared"] = lambda: load_shared_market(supabase, market_keys)
    for name, job in (
        ("counts", lambda: holder_counts(supabase)),
        ("crowd", lambda: sentiment_crowd(supabase, market_keys)),
        ("comments", lambda: sentiment_comment_lists(supabase, market_keys)),
        ("feed", lambda: sentiment_comment_lists(supabase, market_keys, every=True)),
    ):
        if name not in prefetch:
            jobs[name] = job
    with _timed("  extra lookups (should be none)"):
        got = _together(jobs) if jobs else {}
    shared = earlier if reuse_shared else got["shared"]
    counts = prefetch["counts"] if "counts" in prefetch else got["counts"]
    crowd = prefetch["crowd"] if "crowd" in prefetch else got["crowd"]
    comments = prefetch["comments"] if "comments" in prefetch else got["comments"]
    feed = prefetch["feed"] if "feed" in prefetch else got["feed"]
    with _timed("  logos"):
        logos = _asset_logos(crypto_watchlist, stock_watchlist, shared)
    with _timed("  social stream build"):
        st.session_state["social_stream"] = _social_stream_json(crypto_watchlist, stock_watchlist, shared, logos, feed)
    for kind, results, watchlist in (
        ("Crypto", crypto_results, crypto_watchlist),
        ("Stock", stock_results, stock_watchlist),
    ):
        for row in results:
            asset_id = row.get("key")
            market_key = asset_market_key(kind, asset_id)
            row["holders"] = counts.get(market_key, 0)
            row["logo_url"] = logos.get(market_key) or ""
            voices = crowd.get(market_key) or {}
            row["thumbs_up"] = voices.get("up", 0)
            row["thumbs_down"] = voices.get("down", 0)
            row["alt_count"] = voices.get("alt_count", 0)
            row["alt_avg"] = voices.get("alt_avg")
            row["alt_spread"] = voices.get("alt_spread")
            row["comments"] = comments.get(market_key) or []
            stored = shared.get(asset_market_key(kind, asset_id))
            if not row.get("closes") and stored and stored.get("closes"):
                row["closes"] = stored.get("closes")
            report, stored_at = sentiment_from_row(stored)
            label = watchlist.get(asset_id)
            if report and stored_at is not None and label:
                ticker = crypto_ticker(asset_id) if kind == "Crypto" else asset_id
                remember_sentiment(sentiment_query(kind, str(label), ticker), report, stored_at)


def _stored_logo(row: dict | None) -> str:
    url = (row or {}).get("logo_url")
    return url.strip() if isinstance(url, str) and url.strip().startswith("https://") else ""


_LOGO_ASKED: dict[str, float] = {}


def _fetch_logos_later(crypto_ids, stock_tickers) -> None:
    """Ask CoinGecko and Finnhub for logos, and save what they return. Runs behind the scenes,
    so a slow or busy provider never holds up the page. The logos show from the next load."""
    fresh = []
    try:
        for coin_id, url in crypto_logo_urls(crypto_ids).items():
            fresh.append({"kind": "Crypto", "asset_id": coin_id, "logo_url": url})
        for ticker in stock_tickers:
            url = stock_logo_url(ticker)
            if url:
                fresh.append({"kind": "Stock", "asset_id": ticker, "logo_url": url})
        save_logos(supabase, fresh)
    except Exception as exc:
        print(f"logo fetch failed: {exc}")


def _asset_logos(crypto_watchlist, stock_watchlist, shared: dict) -> dict[str, str]:
    """Reuse a saved logo. An asset with none yet is looked up behind the scenes, at most once an hour."""
    logos = {}
    missing_crypto = []
    missing_stock = []
    lacking = []
    now = time.time()
    for kind, watchlist in (("Crypto", crypto_watchlist), ("Stock", stock_watchlist)):
        for asset_id in watchlist:
            key = asset_market_key(kind, asset_id)
            saved = _stored_logo(shared.get(key))
            if not saved:
                lacking.append(str(asset_id))
            if saved:
                logos[key] = saved
            elif now - _LOGO_ASKED.get(key, 0.0) >= 3600:
                _LOGO_ASKED[key] = now
                (missing_crypto if kind == "Crypto" else missing_stock).append(asset_id)
    if missing_crypto or missing_stock:
        _background(_fetch_logos_later, list(missing_crypto), list(missing_stock))
    st.session_state["asset_logos"] = logos
    st.session_state["_logo_lacking"] = lacking
    return logos


def _section_mark(mark_html: str, title: str) -> str:
    """A large icon with a name of the same height beside it."""
    safe = html.escape(" ".join(str(title or "").split()))
    return (
        "<div style='display:flex;align-items:center;gap:12px;margin:0.15rem 0 0.25rem;'>"
        f"{mark_html}"
        f"<span class='ang-title' style='font-size:2rem;line-height:1;font-weight:600;'>{safe}</span>"
        "</div>"
    )


def _emoji_mark(emoji: str, size: int = 32) -> str:
    """The section emoji at the same size as an asset logo."""
    return (
        f"<span style='font-size:{size}px;line-height:1;display:inline-flex;"
        "align-items:center;flex:none;'>"
        f"{emoji}</span>"
    )


def _ticker_label(kind: str, asset_id: str, fallback: str) -> str:
    """Short name beside a logo. SUI for a crypto, AAPL for a stock."""
    if str(kind) == "Stock":
        ticker = str(asset_id or "").strip().upper()
        return ticker or " ".join(str(fallback or "").split())
    ticker = crypto_ticker(str(asset_id or ""))
    if ticker:
        return str(ticker).upper()
    return " ".join(str(fallback or "").split())


def _stored_bars(kind: str, asset_id: str, days: int):
    """Bars saved for every account. A missing row is written once, then only read."""
    token = (str(kind), str(asset_id), int(days))
    run = st.session_state.setdefault("_bar_run", {})
    if token in run:
        return run[token]
    key = asset_market_key(kind, asset_id)
    shared = st.session_state.get("_shared_rows") or {}
    frame = frame_from_row(shared.get(key))
    if frame is None or frame.empty:
        frame = frame_from_row(load_shared_market(supabase, [key]).get(key))
    if frame is not None and len(frame) >= 15:
        result = (slice_history(frame, days), None)
        run[token] = result
        return result
    memory = st.session_state.setdefault("_bar_memory", {})
    remembered = memory.get(key)
    if remembered is not None and len(remembered) >= 15:
        result = (slice_history(remembered, days), None)
        run[token] = result
        return result
    flag = f"price_fill_{key}"
    if st.session_state.get(flag):
        result = (pd.DataFrame(), "Shared prices are not ready yet.")
        run[token] = result
        return result
    with st.spinner(f"Saving shared prices for {asset_id}..."):
        frame, err, saved = create_price_row(supabase, kind, asset_id, days)
    if err or frame is None or getattr(frame, "empty", True):
        st.session_state[flag] = True
        result = (pd.DataFrame(), err or "Shared prices are not ready yet.")
        run[token] = result
        return result
    memory[key] = frame
    if saved:
        st.session_state["_shared_reread"] = True
    result = (frame, None)
    run[token] = result
    return result


def _visit_asset_key(kind, asset_id) -> str:
    return f"{kind}:{asset_id}"


def _boundary_text(value: float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.1f}"


def _factor_shift(previous: dict, current: dict) -> tuple[str, float]:
    """The factor whose points changed the most between two visits."""
    best_name = ""
    best_delta = 0.0
    for name in set(previous) | set(current):
        try:
            delta = float(current.get(name) or 0) - float(previous.get(name) or 0)
        except (TypeError, ValueError):
            continue
        if abs(delta) > abs(best_delta):
            best_name = str(name)
            best_delta = delta
    return best_name, best_delta


def _boundary_cross(previous: float, current: float, bull: float, bear: float) -> str:
    """above or below when the score enters that side. Already being there is not a cross."""
    if previous < bull <= current:
        return "above"
    if previous > bear >= current:
        return "below"
    return ""


def _score_snapshot(rows) -> dict:
    snapshot = {}
    for row in rows:
        score = row.get("score")
        try:
            if score is None or pd.isna(score):
                continue
            score = round(float(score), 1)
        except (TypeError, ValueError):
            continue
        kind = str(row.get("type") or "")
        asset_id = str(row.get("key") or "")
        if kind not in ("Crypto", "Stock") or not asset_id:
            continue
        factors = {}
        raw = row.get("contributions") or {}
        if isinstance(raw, dict):
            for name, points in raw.items():
                try:
                    factors[str(name)] = round(float(points), 1)
                except (TypeError, ValueError):
                    continue
        snapshot[_visit_asset_key(kind, asset_id)] = {
            "score": score,
            "factors": factors,
        }
    return snapshot


def _remember_score_visit(rows) -> tuple[dict, bool]:
    """Keep the previous visit's scores for this session, and store today's for the next one."""
    if "score_visit_baseline" not in st.session_state:
        stored = (prefs.get("settings") or {}).get("score_visit")
        if isinstance(stored, dict) and stored:
            st.session_state.score_visit_baseline = stored
            st.session_state.score_visit_seen = True
        else:
            st.session_state.score_visit_baseline = {}
            st.session_state.score_visit_seen = False
    current = _score_snapshot(rows)
    if current and not st.session_state.get("score_visit_saved"):
        if isinstance(st.session_state.get("cloud_prefs"), dict):
            save_account_settings({"score_visit": current})
            st.session_state.score_visit_saved = True
    return st.session_state.score_visit_baseline, bool(st.session_state.score_visit_seen)


def _change_button(pick: str, title: str, detail: str, color: str, logo: str = "") -> str:
    safe_pick = html.escape(pick, quote=True)
    return (
        f"<button type='button' data-pick='{safe_pick}' "
        "style='display:block;width:100%;margin:0;padding:10px 0 2px;border:none;"
        "border-top:1px solid var(--ang-border);background:transparent;text-align:left;"
        "cursor:pointer;font:inherit;color:inherit;'>"
        "<div style='display:flex;align-items:center;gap:8px;'>"
        f"{logo}<span style='font-weight:600;color:{color};'>{html.escape(title)}</span></div>"
        f"<div class='ang-kicker' style='margin:2px 0 8px;'>{html.escape(detail)}</div></button>"
    )


def _what_changed_html(rows, baseline, seen: bool) -> str:
    """Crossings since the last visit, then the largest other moves."""
    try:
        bull = float(alert_prefs.get("min_score_alert", 70))
    except (TypeError, ValueError):
        bull = 70.0
    try:
        bear = float(alert_prefs.get("max_score_alert", 30))
    except (TypeError, ValueError):
        bear = 30.0
    bull_label = _boundary_text(bull)
    bear_label = _boundary_text(bear)
    parts = [
        "<div class='ang-card' style='margin-bottom:12px;'>",
        "<div class='ang-kicker'>What changed</div>",
    ]
    if not seen:
        parts.append("<div style='margin-top:8px;'>Changes show here from your next visit.</div></div>")
        return "".join(parts)

    crossings = []
    moves = []
    logos = st.session_state.get("asset_logos") or {}
    for row in rows:
        kind = str(row.get("type") or "")
        asset_id = str(row.get("key") or "")
        previous = baseline.get(_visit_asset_key(kind, asset_id)) if isinstance(baseline, dict) else None
        if not isinstance(previous, dict):
            continue
        try:
            current_score = round(float(row.get("score")), 1)
            previous_score = round(float(previous.get("score")), 1)
        except (TypeError, ValueError):
            continue
        factors = {}
        raw = row.get("contributions") or {}
        if isinstance(raw, dict):
            for name, points in raw.items():
                try:
                    factors[str(name)] = round(float(points), 1)
                except (TypeError, ValueError):
                    continue
        previous_factors = previous.get("factors") if isinstance(previous.get("factors"), dict) else {}
        factor_name, factor_delta = _factor_shift(previous_factors, factors)
        detail = f"{previous_score:.1f} to {current_score:.1f}."
        if factor_name and abs(factor_delta) >= 0.05:
            detail = f"{detail} {factor_name} moved it most ({factor_delta:+.1f})."
        delta = round(current_score - previous_score, 1)
        color = "#15803d" if delta > 0 else "#b91c1c" if delta < 0 else "#6b7280"
        symbol = str(row.get("symbol") or asset_id)
        item = {
            "delta": delta,
            "pick": f"{kind}|{asset_id}",
            "detail": detail,
            "color": color,
            "symbol": symbol,
            "logo": asset_logo(logos.get(asset_market_key(kind, asset_id)), symbol, size=20),
        }
        cross = _boundary_cross(previous_score, current_score, bull, bear)
        if cross == "above":
            item["title"] = f"{item['symbol']} crossed above {bull_label}"
            crossings.append(item)
        elif cross == "below":
            item["title"] = f"{item['symbol']} crossed below {bear_label}"
            crossings.append(item)
        elif abs(delta) >= 1:
            item["title"] = f"{item['symbol']} moved"
            moves.append(item)

    crossings.sort(key=lambda item: abs(item["delta"]), reverse=True)
    moves.sort(key=lambda item: abs(item["delta"]), reverse=True)
    moves = moves[:3]
    if not crossings:
        parts.append(
            "<div style='margin-top:8px;'>No score crossed a boundary since your last visit.</div>"
        )
    for item in crossings:
        parts.append(_change_button(item["pick"], item["title"], item["detail"], item["color"], item["logo"]))
    if moves:
        parts.append("<div class='ang-kicker' style='margin-top:10px;'>Largest moves</div>")
        for item in moves:
            parts.append(_change_button(item["pick"], item["title"], item["detail"], item["color"], item["logo"]))
    parts.append("</div>")
    return "".join(parts)


def _score_sentence(reasons) -> str:
    """One line for the TA score hover. Neutral notes stay in the breakdown."""
    if reasons is None or isinstance(reasons, str):
        return "Open the score breakdown."
    try:
        reasons = list(reasons)
    except TypeError:
        return "Open the score breakdown."
    quiet = ("neutral", "inside bollinger", "inside the ichimoku", "weak trend", "developing trend")
    kept = []
    for reason in reasons or []:
        text = " ".join(str(reason).split())
        if not text or any(piece in text.lower() for piece in quiet):
            continue
        kept.append(text)
        if len(kept) == 3:
            break
    if not kept:
        return "Open the score breakdown."
    if len(kept) == 1:
        sentence = kept[0]
    else:
        sentence = ", ".join(kept[:-1]) + ", and " + kept[-1]
    if not sentence.endswith("."):
        sentence += "."
    return sentence


def _draw_social_stream(stream_items, scope, *, popout: bool = False):
    """Draw the social panel with the comments, chat and saved panel choices."""
    chat_notice = st.session_state.pop("chat_notice", "")
    return _social_stream(
        key="social_stream_host",
        data=json.dumps(
            {
                "items": stream_items,
                "asset": scope,
                "chat": load_chat(supabase),
                "me": _chat_viewer(),
                "favourites": _favourite_ids((prefs.get("settings") or {}).get("favourites")),
                "groups": _groups_for_stream(),
                "notice": chat_notice,
                "faces": list(COMMENT_EMOTICONS),
                "limit": COMMENT_LIMIT,
                "account": str(user_id),
                "panel": account_panel(),
                "popout": popout,
                "popoutWindow": bool(st.session_state.get("popouts_as_window", True)),
                "popoutFold": bool(st.session_state.get("popouts_fold_section", True)),
            },
            ensure_ascii=False,
        ),
        on_asset_change=lambda: None,
        on_chat_change=lambda: None,
        on_signal_change=lambda: None,
        on_group_change=lambda: None,
        on_panel_change=lambda: None,
        on_report_change=lambda: None,
        on_refresh_change=lambda: None,
    )


def _handle_stream_events(stream_state) -> None:
    """Act on whatever the social panel reported this run. Shared by the page and the pop-out."""
    chosen_scope = stream_state.asset
    chat_event = _chat_action(getattr(stream_state, "chat", None))
    signal_event = _chat_action(getattr(stream_state, "signal", None))
    group_event = _favourite_event(getattr(stream_state, "group", None))
    report_event = _report_action(getattr(stream_state, "report", None))
    if chat_event and chat_event.get("n") != st.session_state.get("chat_done"):
        st.session_state["chat_done"] = chat_event.get("n")
        st.session_state["chat_notice"] = _apply_chat_action(chat_event)
        _rerun_fragment()
    if signal_event and signal_event.get("n") != st.session_state.get("signal_done"):
        st.session_state["signal_done"] = signal_event.get("n")
        st.session_state["chat_notice"] = _apply_signal_action(signal_event)
        _rerun_fragment()
    if report_event and report_event.get("n") != st.session_state.get("report_done"):
        st.session_state["report_done"] = report_event.get("n")
        st.session_state["chat_notice"] = _apply_comment_report(report_event)
        _rerun_fragment()
    if group_event and group_event.get("n") != st.session_state.get("group_done"):
        st.session_state["group_done"] = group_event.get("n")
        st.session_state["chat_notice"] = _apply_group_invite(group_event)
        _rerun_fragment()
    if chosen_scope in ("all", "watchlist", "crypto", "stock"):
        stored = prefs.setdefault("settings", {})
        if stored.get("stream_asset") != chosen_scope:
            save_account_settings({"stream_asset": chosen_scope})
    panel_raw = getattr(stream_state, "panel", None)
    if panel_raw:
        try:
            panel_choice = json.loads(panel_raw) if isinstance(panel_raw, str) else panel_raw
        except (TypeError, json.JSONDecodeError):
            panel_choice = None
        if isinstance(panel_choice, dict):
            panel_updates = {}
            try:
                panel_width = int(panel_choice.get("width"))
            except (TypeError, ValueError):
                panel_width = 0
            if 320 <= panel_width <= 900:
                panel_updates["stream_width"] = panel_width
            try:
                panel_split = float(panel_choice.get("split"))
            except (TypeError, ValueError):
                panel_split = 0.0
            if 0.08 < panel_split < 0.92:
                panel_updates["stream_split"] = round(panel_split, 3)
            if isinstance(panel_choice.get("pinned"), bool):
                panel_updates["stream_pinned"] = panel_choice["pinned"]
            if panel_choice.get("layout") in ("stacked", "side"):
                panel_updates["stream_layout"] = panel_choice["layout"]
            if panel_updates:
                save_account_settings(panel_updates)


def _record_run(what: str, started: float) -> None:
    """Keep the last 20 redraws (whole page or dashboard part) for the Page timing panel."""
    try:
        runs = st.session_state.setdefault("_perf_runs", [])
        runs.append({
            "when": time.strftime("%H:%M:%S"),
            "what": what,
            "ms": round((time.perf_counter() - started) * 1000),
        })
        del runs[:-20]
    except Exception:
        pass


@st.fragment
def render_dashboard(*args, **kwargs):
    """The dashboard redraws on its own when something inside it is clicked."""
    started = time.perf_counter()
    try:
        _render_dashboard_body(*args, **kwargs)
    finally:
        _record_run("dashboard", started)


def _render_dashboard_body(crypto_watchlist, stock_watchlist, history_days, weights, show_reasons_flag, show_extra_metrics_flag, show_period_changes_flag, trade_crypto, trade_equities):
    st.session_state["_bar_run"] = {}
    shared_keys = []
    if trade_crypto:
        shared_keys.extend(asset_market_key("Crypto", asset_id) for asset_id in crypto_watchlist)
    if trade_equities:
        shared_keys.extend(asset_market_key("Stock", asset_id) for asset_id in stock_watchlist)
    st.session_state["_perf"] = {}
    all_keys = [asset_market_key("Crypto", asset_id) for asset_id in crypto_watchlist]
    all_keys += [asset_market_key("Stock", asset_id) for asset_id in stock_watchlist]
    # Every lookup this load needs goes out at once, so the wait is the slowest one, not the sum.
    # Prices, market moods and holder counts change slowly, so a result under 30 seconds old is reused.
    # Comments and votes are always read fresh.
    memo = st.session_state.setdefault("_memo", {})
    nonce_now = st.session_state.data_nonce

    def _recent(name, token):
        entry = memo.get(name)
        if entry and entry[2] == token and time.time() - entry[0] < 30:
            return entry[1], True
        return None, False

    shared_now, shared_hit = (None, False) if st.session_state.get("_shared_reread") else _recent(
        "shared", (nonce_now, tuple(all_keys)))
    moods_now, moods_hit = _recent("moods", nonce_now)
    counts_now, counts_hit = _recent("counts", nonce_now)
    jobs = {
        "crowd": lambda: sentiment_crowd(supabase, all_keys),
        "comments": lambda: sentiment_comment_lists(supabase, all_keys),
        "feed": lambda: sentiment_comment_lists(supabase, all_keys, every=True),
    }
    if not shared_hit:
        jobs["shared"] = lambda: load_shared_market(supabase, all_keys)
    if not moods_hit:
        jobs["moods"] = lambda: load_market_moods(supabase)
    if not counts_hit:
        jobs["counts"] = lambda: holder_counts(supabase)
    with _timed("lookups, run together"):
        got = _together(jobs)
    if not shared_hit:
        shared_now = got["shared"]
        memo["shared"] = (time.time(), shared_now, (nonce_now, tuple(all_keys)))
    if not moods_hit:
        moods_now = got["moods"]
        memo["moods"] = (time.time(), moods_now, nonce_now)
    if not counts_hit:
        counts_now = got["counts"]
        memo["counts"] = (time.time(), counts_now, nonce_now)
    st.session_state["_shared_rows"] = shared_now
    st.session_state["_prefetch"] = {
        "counts": counts_now,
        "crowd": got["crowd"],
        "comments": got["comments"],
        "feed": got["feed"],
    }
    _moods_now = moods_now

    wide_layout = st.session_state.get("section_layout") == "Wide" and not _POPOUT_VIEW
    allowed_kinds = []
    if trade_crypto:
        allowed_kinds.append("Crypto")
    if trade_equities:
        allowed_kinds.append("Stock")
    with section_expander("📸 Quick Snapshot", "quick_snapshot"):
        def open_asset():
            """The asset on the chart: kind, id, label, and its sentiment search."""
            pick = st.session_state.get("chart_pick")
            kind = asset_id = None
            if pick and pick[0] in allowed_kinds:
                kind, asset_id = pick[0], pick[1]
                watchlist = crypto_watchlist if kind == "Crypto" else stock_watchlist
                if asset_id not in watchlist:
                    kind = asset_id = None
            if kind is None:
                if "Crypto" in allowed_kinds and crypto_watchlist:
                    kind, asset_id = "Crypto", next(iter(crypto_watchlist))
                elif "Stock" in allowed_kinds and stock_watchlist:
                    kind, asset_id = "Stock", next(iter(stock_watchlist))
                else:
                    return None
            watchlist = crypto_watchlist if kind == "Crypto" else stock_watchlist
            if asset_id not in watchlist:
                return None
            label = str(watchlist[asset_id])
            ticker = crypto_ticker(asset_id) if kind == "Crypto" else asset_id
            return kind, asset_id, label, sentiment_query(kind, label, ticker)

        jumps = []
        moods = _moods_now or {}
        if trade_crypto:
            jumps.append((
                "Market Sentiment - Crypto",
                "jump_mood_crypto",
                "mood_countdown_crypto",
                next_update(row_timestamp(moods.get("crypto"), "sentiment_updated_at"), SENTIMENT_REFRESH_SECONDS),
                "market_mood_crypto",
                "market-mood-crypto",
                "Open crypto market sentiment. The time is the next shared update. Pressing this does not refresh it.",
                "🪙",
            ))
        if trade_equities:
            jumps.append((
                "Market Sentiment - Equities",
                "jump_mood_stock",
                "mood_countdown_stock",
                next_update(row_timestamp(moods.get("stock"), "sentiment_updated_at"), SENTIMENT_REFRESH_SECONDS),
                "market_mood_stock",
                "market-mood-stock",
                "Open stock market sentiment. The time is the next shared update. Pressing this does not refresh it.",
                "📈",
            ))
        opened = open_asset()
        if opened:
            opened_kind, opened_id, _opened_label, _opened_query = opened
            opened_row = (st.session_state.get("_shared_rows") or {}).get(asset_market_key(opened_kind, opened_id))
            jumps.append((
                "Market Sentiment - Selected Asset",
                "jump_sentiment",
                "sentiment_countdown",
                next_update(row_timestamp(opened_row, "sentiment_updated_at"), SENTIMENT_REFRESH_SECONDS),
                "market_sentiment_panel",
                "market-sentiment",
                "Open sentiment for the asset on the chart. The time is the next shared update. Pressing this does not refresh it.",
                "📰",
            ))
            jumps.append((
                "Technical Data - Selected Asset",
                "jump_technical",
                "technical_countdown",
                next_update(row_timestamp(opened_row, "prices_updated_at"), TECHNICAL_REFRESH_SECONDS),
                "interactive_chart",
                "interactive-chart",
                "Open the chart. The time is the next shared price update. Pressing this does not refresh it.",
                "📊",
            ))
        if jumps:
            # One control per column, so each timer writes onto its own button.
            jump_columns = st.columns(len(jumps))
            honored = st.session_state.setdefault("countdown_seen", {})
            reread = False
            for column, (title, _button_key, timer_key, deadline, _section_id, anchor, jump_help, jump_icon) in zip(jump_columns, jumps):
                with column:
                    due = _countdown_due(deadline, timer_key, title, anchor, jump_help, jump_icon)
                    token = "" if deadline is None else str(int(deadline * 1000))
                    if due and token and honored.get(timer_key) != token:
                        honored[timer_key] = token
                        reread = True
            if reread and not st.session_state.pop("_chart_row_quiet", False):
                _rerun_fragment()

        # Market cap still uses a short cache. Prices and sentiment come from the shared rows.
        nonce = st.session_state.data_nonce

        spent = {"bars": 0.0, "maths": 0.0}

        def process_watchlist(watchlist, is_crypto=True):
            results = []
            for key, name in watchlist.items():
                if is_crypto:
                    ticker = crypto_ticker(key)
                    if ticker and str(key).strip().upper() == ticker:
                        name = ticker
                kind = "Crypto" if is_crypto else "Stock"
                bars_from = time.perf_counter()
                df, err = _stored_bars(kind, key, history_days)
                spent["bars"] += time.perf_counter() - bars_from

                result = {
                    "symbol": name if is_crypto else f"{name} ({key})",
                    "score": None,
                    "label": "No data",
                    "reasons": [err] if err else [],
                    "latest_price": None,
                    "rsi": None,
                    "change_1d": None,
                    "change_7d": None,
                    "change_30d": None,
                    "atr_pct": None,
                    "volume_ratio": None,
                    "bb_position": None,
                    "adx": None,
                    "confluence": None,
                    "contributions": {},
                    "type": "Crypto" if is_crypto else "Stock",
                    "key": key,
                }

                if err:
                    results.append(result)
                    continue

                if df is not None and not df.empty and "close" in df.columns:
                    result["closes"] = recent_closes(df["close"].tolist())

                if df is not None and not df.empty and len(df) >= 15:
                    try:
                        try:
                            weights_key = tuple(sorted((str(k), float(v)) for k, v in (weights or {}).items()))
                        except (TypeError, ValueError):
                            weights_key = (("_uncached", time.time_ns()),)
                        shared_row = (st.session_state.get("_shared_rows") or {}).get(asset_market_key(kind, key))
                        stamp = (
                            row_timestamp(shared_row, "prices_updated_at"),
                            len(df),
                            float(df["close"].iloc[-1]),
                        )
                        maths_from = time.perf_counter()
                        try:
                            scored = _scored_asset(kind, str(key), int(history_days), weights_key, stamp, df, bool(st.session_state.get("adaptive_scoring")))
                        except Exception:
                            scored = compute_score(calculate_indicators(df), weights=weights, adaptive=bool(st.session_state.get("adaptive_scoring")))
                        spent["maths"] += time.perf_counter() - maths_from
                        if isinstance(scored, dict):
                            result.update(scored)
                            result["symbol"] = name if is_crypto else f"{name} ({key})"
                            result["type"] = "Crypto" if is_crypto else "Stock"
                            result["key"] = key
                    except Exception as exc:
                        result["label"] = "Error"
                        result["reasons"] = [str(exc)]

                results.append(result)
            return results

        worked_before = _SCORES_WORKED_OUT
        with _timed("scores for every asset"), _scoring_busy():
            crypto_results = process_watchlist(crypto_watchlist, is_crypto=True) if trade_crypto else []
            stock_results = process_watchlist(stock_watchlist, is_crypto=False) if trade_equities else []
        st.session_state["_perf"]["  of which loading saved prices"] = round(spent["bars"] * 1000)
        st.session_state["_perf"]["  of which indicator maths"] = round(spent["maths"] * 1000)
        st.session_state["_perf"]["  scores worked out fresh (0 means all remembered)"] = _SCORES_WORKED_OUT - worked_before
        # Crypto ranks always show, so crypto is always asked about. Stock caps only when extra metrics are on.
        stock_for_caps = tuple(stock_watchlist) if (trade_equities and show_extra_metrics_flag) else ()
        crypto_for_caps = tuple(crypto_watchlist) if trade_crypto else ()
        if crypto_for_caps or stock_for_caps:
            with _timed("market caps and ranks"):
                caps = load_market_caps(crypto_for_caps, stock_for_caps, nonce, st.session_state.get("_shared_rows"))
            for row in crypto_results:
                coin = str(row.get("key") or "").lower()
                row["market_cap"] = (caps.get("crypto") or {}).get(coin)
                row["market_rank"] = (caps.get("rank") or {}).get(coin)
            for row in stock_results:
                row["market_cap"] = (caps.get("stock") or {}).get(str(row.get("key") or "").upper())
        if trade_equities and stock_results:
            earnings = load_earnings(tuple(stock_watchlist), st.session_state.get("_shared_rows"))
            for row in stock_results:
                row["next_earnings"] = earnings.get(str(row.get("key") or "").upper())
        change_rows = crypto_results + stock_results
        change_baseline, change_seen = _remember_score_visit(change_rows)
        with _timed("shared rows, crowd and comments"):
            _share_market_rows(crypto_watchlist, stock_watchlist, crypto_results, stock_results)
        saved_scope = (prefs.get("settings") or {}).get("stream_asset")
        scope = saved_scope if saved_scope in ("watchlist", "crypto", "stock") else ""
        try:
            stream_items = json.loads(st.session_state.get("social_stream") or "[]")
        except (TypeError, json.JSONDecodeError):
            stream_items = []
        if not isinstance(stream_items, list):
            stream_items = []
        if not _POPOUT_VIEW:
            stream_state = _draw_social_stream(stream_items, scope)
            _handle_stream_events(stream_state)

        def get_top_bottom(results):
            valid = [row for row in results if row.get("score") is not None and not pd.isna(row.get("score"))]
            if not valid:
                return None, None
            ordered = sorted(valid, key=lambda row: row["score"], reverse=True)
            return ordered[0], ordered[-1]

        crypto_top, crypto_bot = get_top_bottom(crypto_results)
        stock_top, stock_bot = get_top_bottom(stock_results)

        def _select_chart_asset(raw):
            """Point the chart at one asset. The click already reran this section, so draw it once."""
            parts = str(raw).split("|")
            if len(parts) < 2:
                return
            kind_name, asset_id = parts[0], parts[1]
            destination = parts[2] if len(parts) > 2 else "chart"
            chosen = crypto_watchlist if kind_name == "Crypto" else stock_watchlist if kind_name == "Stock" else None
            if not chosen or asset_id not in chosen:
                return
            if destination == "sentiment":
                st.session_state.scroll_target = "market-sentiment"
                section_id = "market_sentiment_panel"
            elif destination == "breakdown":
                st.session_state.scroll_target = "score-breakdown"
                _remember_section("interactive_chart", True)
                section_id = "score_breakdown"
            else:
                st.session_state.scroll_target = "interactive-chart"
                section_id = "interactive_chart"
            st.session_state.scroll_token = str(time.time_ns())
            st.session_state.chart_pick = (kind_name, asset_id)
            st.session_state.chart_pick_from_row = True
            st.session_state["_chart_from_row"] = True
            st.session_state["_chart_row_quiet"] = True
            st.session_state.asset_type = kind_name
            if kind_name == "Crypto":
                st.session_state.asset_crypto = asset_id
            else:
                st.session_state.asset_stock = asset_id
            _remember_section(section_id, True)

        snapshot_cards = []
        if trade_crypto:
            snapshot_cards.append(("Top Watchlist Crypto", crypto_top, "Crypto", "snapshot_crypto_top"))
            snapshot_cards.append(("Weakest Watchlist Crypto", crypto_bot, "Crypto", "snapshot_crypto_weak"))
        if trade_equities:
            snapshot_cards.append(("Top Watchlist Stock", stock_top, "Stock", "snapshot_stock_top"))
            snapshot_cards.append(("Weakest Watchlist Stock", stock_bot, "Stock", "snapshot_stock_weak"))

        def render_mood_snapshot(label, score, summary, mood_key, voice):
            safe_label = html.escape(label)
            scored = score is not None and not pd.isna(score)
            if not scored:
                badge = sentiment_badge(None)
                status = "<div style='margin-top:8px;color:#6b7280;font-weight:600;'>Not scored yet</div>"
            else:
                color = tone(score)[0]
                badge = sentiment_badge(score)
                status = (
                    f"<div style='margin-top:8px;color:{color};font-weight:600;'>"
                    f"{html.escape(_mood_coverage(float(score)))}</div>"
                )
            text = " ".join(str(summary or "").split())
            summary_html = ""
            if text:
                summary_html = (
                    "<div class='ang-copy' style='flex:1;min-width:0;'>"
                    f"{html.escape(text)}</div>"
                )
            crowd = (
                "<div style='flex:none;margin-left:auto;display:flex;align-items:center;gap:8px;'>"
                + crowd_mark(
                    voice.get("up"),
                    voice.get("down"),
                    scored,
                    voice.get("alt_count"),
                    voice.get("alt_avg"),
                    voice.get("alt_spread"),
                )
                + crowd_average_badge(
                    voice.get("alt_avg"),
                    voice.get("alt_count"),
                    voice.get("alt_spread"),
                    scored,
                )
                + "</div>"
            )
            jump = html.escape(f"mood|{mood_key}", quote=True)
            jump_title = html.escape(f"Open {label} sentiment", quote=True)
            return (
                f"<button type='button' data-pick='{jump}' title='{jump_title}' "
                "style='display:block;width:100%;margin:0;padding:0;border:none;background:transparent;"
                "text-align:left;cursor:pointer;font:inherit;color:inherit;'>"
                "<div class='ang-card'>"
                f"<div class='ang-kicker' style='margin-bottom:8px;'>{safe_label}</div>"
                "<div style='display:flex;align-items:flex-start;gap:16px;'>"
                f"<div style='flex:none;'>{badge}{status}</div>"
                f"{summary_html}{crowd}</div></div></button>"
            )

        changed = _score_table(
            key="snapshot_changes",
            data=_what_changed_html(change_rows, change_baseline, change_seen),
            on_picked_change=lambda: None,
        ).picked
        if changed:
            _select_chart_asset(str(changed))

        mood_specs = []
        if trade_crypto:
            mood_specs.append(("crypto", "Crypto market"))
        if trade_equities:
            mood_specs.append(("stock", "Stock market"))
        stored_moods = load_market_moods(supabase)
        mood_voices = market_mood_crowd(supabase, [key for key, _label in mood_specs]) if mood_specs else {}
        if stored_moods is not None and mood_specs:
            mood_columns = st.columns(2)
            for column, (mood_key, mood_label) in zip(mood_columns, mood_specs):
                report, _stored_at = sentiment_from_row(stored_moods.get(mood_key))
                mood_score = (report or {}).get("score")
                try:
                    mood_score = float(mood_score)
                except (TypeError, ValueError):
                    mood_score = None
                if mood_score is not None and pd.isna(mood_score):
                    mood_score = None
                with column:
                    _score_table(
                        key=f"snapshot_mood_{mood_key}",
                        data=render_mood_snapshot(
                            mood_label,
                            mood_score,
                            (report or {}).get("summary"),
                            mood_key,
                            mood_voices.get(mood_key) or {},
                        ),
                    )

        snapshot_columns = st.columns(len(snapshot_cards))

        def render_snapshot_card(title, name, score, pick, logo_url=None):
            color, bg, arrow, _bar = tone(score)
            score_str = f"{score:.1f}/100" if score is not None and not pd.isna(score) else "—"
            safe_title = html.escape(str(title))
            safe_name = html.escape(str(name))
            logo = asset_logo(logo_url, name) if name and name != "—" else ""
            body = (
                "<div class='ang-card'>"
                f"<div class='ang-kicker'>{safe_title}</div>"
                "<div class='ang-title' style='display:flex;align-items:center;gap:8px;font-size:1.1rem;"
                "margin-bottom:8px;white-space:nowrap;overflow:hidden;'>"
                f"{logo}<span style='overflow:hidden;text-overflow:ellipsis;'>{safe_name}</span></div>"
                f"<div style='display: inline-flex; align-items: center; gap: 4px; background: {bg}; "
                f"color: {color}; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: 600;'>"
                f"{arrow} {score_str}</div></div>"
            )
            if not pick:
                return body
            safe_pick = html.escape(pick, quote=True)
            return (
                f"<button type='button' data-pick='{safe_pick}' "
                "style='display:block;width:100%;margin:0;padding:0;border:none;background:transparent;"
                "text-align:left;cursor:pointer;font:inherit;color:inherit;'>"
                f"{body}</button>"
            )

        def show_snapshot(column, title, row, kind, widget_key):
            pick = None
            name = "—"
            score = None
            logo_url = None
            if row and row.get("key"):
                name = row["symbol"]
                score = row.get("score")
                pick = f"{kind}|{row['key']}"
                logo_url = row.get("logo_url")
            with column:
                picked = _score_table(
                    key=widget_key,
                    data=render_snapshot_card(title, name, score, pick, logo_url),
                    on_picked_change=lambda: None,
                ).picked
                if picked:
                    _select_chart_asset(str(picked))

        for column, (card_title, card_row, card_kind, card_key) in zip(snapshot_columns, snapshot_cards):
            show_snapshot(column, card_title, card_row, card_kind, card_key)
        st.caption("Click a change or a box to open that asset on the chart.")

    if not wide_layout:
        show_market_moods(trade_crypto, trade_equities)

    def render_score_bar(score):
        if score is None or pd.isna(score):
            pct, color = 0, "#6b7280"
        else:
            pct = max(0, min(100, float(score)))
            color = tone(score)[3]
        return (
            '<div style="display:flex;align-items:center;gap:8px;width:100%;min-width:100px;">'
            '<div class="ang-track">'
            f'<div style="width:{pct}%;background:{color};height:100%;border-radius:6px;"></div></div>'
            f"{sentiment_badge(score)}</div>"
        )

    def sort_token(value, numeric=False):
        try:
            missing = value is None or pd.isna(value)
        except TypeError:
            missing = value is None
        if missing:
            return ""
        if numeric:
            try:
                return f"{float(value):.8f}"
            except (TypeError, ValueError):
                return ""
        return html.escape(str(value), quote=True)

    def cell(value, sort_value=None, numeric=False):
        token = sort_token(value if sort_value is None else sort_value, numeric)
        return (
            f"<td data-sort='{token}' style='padding:10px;white-space:nowrap;'>"
            f"{html.escape(str(value))}</td>"
        )

    def earnings_cell(value):
        """Next report date with the days left. Orange inside a week, because scores can swing then."""
        try:
            day = datetime.strptime(str(value or "")[:10], "%Y-%m-%d").date()
        except ValueError:
            return "<td data-sort='' style='padding:10px;white-space:nowrap;color:#6b7280;'>—</td>"
        left = (day - datetime.now(timezone.utc).date()).days
        if left < 0:
            return "<td data-sort='' style='padding:10px;white-space:nowrap;color:#6b7280;'>—</td>"
        when = "today" if left == 0 else "tomorrow" if left == 1 else f"in {left}d"
        soon = left <= 7
        style = "color:#b45309;font-weight:700;" if soon else ""
        hint = "Reports soon. Scores can swing around earnings." if soon else "Next earnings report."
        return (
            f"<td data-sort='{float(left):.8f}' title='{hint}' style='padding:10px;white-space:nowrap;'>"
            f"<span style='{style}'>{day.strftime('%b')} {day.day} · {when}</span></td>"
        )

    def percent_change_cell(value, match_trend=False):
        if value is None or pd.isna(value):
            inner = "<span style='color:#6b7280;'>—</span>"
            token = ""
        else:
            number = float(value)
            if match_trend:
                color = trend_tone(number)
            elif number > 0:
                color = "#15803d"
            elif number < 0:
                color = "#b91c1c"
            else:
                color = "#6b7280"
            inner = f"<span style='color:{color};font-weight:600;'>{number:+.1f}%</span>"
            token = sort_token(number, numeric=True)
        return f"<td data-sort='{token}' style='padding:10px;white-space:nowrap;'>{inner}</td>"

    def style_and_show_table(results, title, kind, section_id):
        with section_expander(title, section_id):
            if not results:
                st.caption("This watchlist is empty.")
                return
            frame = pd.DataFrame(results).sort_values("score", ascending=False, na_position="last")
            st.caption("Click a column title to sort. The table starts with the strongest score at the top. Click a name to show that asset on the chart. Hover a TA score to read why it landed there, and click it to open the score breakdown. Click the sentiment score, the thumbs, or the crowd average to open its headlines. Watching is how many accounts hold that asset. The Crowd box is the average of personal scores. Hover the down thumb for the spread. A comment balloon, or the arrow on the right edge, opens the social signals and chat. The 30-day trend uses the same colors as 30d %.")

            headers = ["Asset", "Watching"] + (["Rank"] if kind == "Crypto" else []) + ["TA Score", "Signal", "Price", "RSI"]
            if kind == "Stock":
                headers.append("Earnings")
            if show_period_changes_flag:
                headers.append("1d %")
            if show_extra_metrics_flag:
                headers.append("7d %")
            if show_period_changes_flag:
                headers.append("30d %")
            if show_extra_metrics_flag:
                headers += ["Market Cap", "ATR %", "Vol"]
            show_comments = any(row.get("comments") for row in results)
            headers += ["Sentiment", "Crowd"]
            if show_comments:
                headers.append("Comments")
            headers.append("30-day trend")
            lead = 3 if kind == "Crypto" else 2
            sort_at = {"Asset": 0, "Watching": 1, "TA Score": lead, "Signal": lead + 1, "Price": lead + 2, "RSI": lead + 3}
            if kind == "Crypto":
                sort_at["Rank"] = 2
            column = lead + 4
            if kind == "Stock":
                sort_at["Earnings"] = column
                column += 1
            for name in ("1d %", "7d %", "30d %", "Market Cap", "ATR %", "Vol"):
                if name in headers:
                    sort_at[name] = column
                    column += 1
            sort_at["Sentiment"] = column
            sort_at["Crowd"] = column + 2
            next_column = column + 3
            if show_comments:
                sort_at["Comments"] = next_column
                next_column += 1
            sort_at["30-day trend"] = next_column

            def header_button(name, align="left", colspan=1):
                mark = " ↓" if name == "TA Score" else ""
                span = f" colspan='{colspan}'" if colspan > 1 else ""
                return (
                    f"<th{span} style='padding:8px 10px;text-align:{align};white-space:nowrap;'>"
                    f"<button type='button' data-sort-col='{sort_at[name]}' "
                    "style='background:none;border:none;padding:0;margin:0;color:inherit;"
                    "font:inherit;font-weight:600;cursor:pointer;white-space:nowrap;'>"
                    f"{html.escape(name)}<span data-sort-mark>{mark}</span></button></th>"
                )

            header_html = ""
            for name in headers:
                if name == "Crowd":
                    header_html += header_button(name, "center", 2)
                    continue
                align = "right" if name in ("Sentiment", "30-day trend") else "center" if name == "Comments" else "left"
                header_html += header_button(name, align)

            pick = st.session_state.get("chart_pick")
            # A row click arrives after the tables are drawn, so read it now to highlight at once.
            pick = clicked_pick(st.session_state) or pick
            rows_html = ""
            for _, row in frame.iterrows():
                asset_id = str(row["key"])
                selected = pick == (kind, asset_id)
                row_class = "ang-row-on" if selected else ""
                price = row.get("latest_price")
                rsi = row.get("rsi")
                price_str = f"${price:,.2f}" if pd.notna(price) else "—"
                rsi_str = f"{rsi:.1f}" if pd.notna(rsi) else "—"
                pick_value = html.escape(f"{kind}|{asset_id}", quote=True)
                name_button = (
                    "<button type='button' data-pick='"
                    f"{pick_value}' style='background:none;border:none;padding:0;margin:0;"
                    "color:inherit;font:inherit;font-weight:600;text-decoration:underline;"
                    "cursor:pointer;white-space:nowrap;'>"
                    f"{html.escape(str(row['symbol']))}</button>"
                )
                rank_cell = ""
                if kind == "Crypto":
                    rank_value = row.get("market_rank")
                    rank_ok = rank_value is not None and not pd.isna(rank_value)
                    rank_cell = cell(f"#{int(rank_value):,}" if rank_ok else "—", rank_value if rank_ok else None, numeric=True)
                score_box = render_score_bar(row["score"])
                scored = row.get("score") is not None and not pd.isna(row.get("score"))
                if scored:
                    reason = html.escape(_score_sentence(row.get("reasons")), quote=True)
                    score_box = (
                        f"<button type='button' data-pick='{pick_value}|breakdown' title='{reason}' "
                        "style='display:block;width:100%;margin:0;padding:0;border:none;background:transparent;"
                        "text-align:left;cursor:pointer;font:inherit;color:inherit;'>"
                        f"{score_box}</button>"
                    )
                rows_html += (
                    f"<tr class='{row_class}'>"
                    f"<td data-sort='{sort_token(row.get('symbol'))}' style='padding:10px;white-space:nowrap;'>"
                    "<span style='display:inline-flex;align-items:center;gap:8px;'>"
                    f"{asset_logo(row.get('logo_url'), row.get('symbol'))}{name_button}</span></td>"
                    f"<td data-sort='{sort_token(row.get('holders'), numeric=True)}' "
                    f"style='padding:8px 10px;white-space:nowrap;'>{holders_mark(row.get('holders'))}</td>"
                    f"{rank_cell}"
                    f"<td data-sort='{sort_token(row.get('score'), numeric=True)}' "
                    f"style='padding:10px;min-width:168px;'>{score_box}</td>"
                    f"{cell(row.get('label') or '—', row.get('label') or '')}"
                    f"{cell(price_str, price, numeric=True)}{cell(rsi_str, rsi, numeric=True)}"
                    f"{earnings_cell(row.get('next_earnings')) if kind == 'Stock' else ''}"
                )
                if show_period_changes_flag:
                    rows_html += percent_change_cell(row.get("change_1d"))
                if show_extra_metrics_flag:
                    rows_html += percent_change_cell(row.get("change_7d"))
                if show_period_changes_flag:
                    rows_html += percent_change_cell(row.get("change_30d"), match_trend=True)
                if show_extra_metrics_flag:
                    atr = row.get("atr_pct")
                    volume = row.get("volume_ratio")
                    rows_html += (
                        f"{cell(format_market_cap(row.get('market_cap')), row.get('market_cap'), numeric=True)}"
                        f"{cell(f'{atr:.2f}' if pd.notna(atr) else '—', atr, numeric=True)}"
                        f"{cell(f'{volume:.2f}' if pd.notna(volume) else '—', volume, numeric=True)}"
                    )
                watchlist = crypto_watchlist if kind == "Crypto" else stock_watchlist
                label = watchlist.get(asset_id)
                headline_score = None
                if label:
                    ticker = crypto_ticker(asset_id) if kind == "Crypto" else asset_id
                    headline_score = cached_sentiment_score(sentiment_query(kind, str(label), ticker))
                sentiment_pick = f"{kind}|{asset_id}|sentiment" if headline_score is not None else None
                jump_attr = ""
                pointer = ""
                if sentiment_pick:
                    jump_attr = (
                        f" data-sentiment-pick='{html.escape(sentiment_pick, quote=True)}'"
                        " title='Open market sentiment for this asset'"
                    )
                    pointer = "cursor:pointer;"
                rows_html += (
                    f"<td data-sort='{sort_token(headline_score, numeric=True)}' "
                    f"style='padding:10px;text-align:right;white-space:nowrap;{pointer}'{jump_attr}>"
                    f"{sentiment_badge(headline_score, sentiment_pick)}</td>"
                    f"<td data-crowd-mark='{pick_value}' "
                    f"data-sort='{sort_token((row.get('thumbs_up') or 0) - (row.get('thumbs_down') or 0), numeric=True)}' "
                    f"style='padding:10px 4px 10px 10px;text-align:right;white-space:nowrap;{pointer}'{jump_attr}>"
                    f"{crowd_mark(row.get('thumbs_up'), row.get('thumbs_down'), headline_score is not None, row.get('alt_count'), row.get('alt_avg'), row.get('alt_spread'))}</td>"
                    f"<td data-crowd-avg='{pick_value}' "
                    f"data-sort='{sort_token(row.get('alt_avg'), numeric=True)}' "
                    f"style='padding:10px 10px 10px 4px;text-align:left;white-space:nowrap;{pointer}'{jump_attr}>"
                    f"{crowd_average_badge(row.get('alt_avg'), row.get('alt_count'), row.get('alt_spread'), headline_score is not None)}</td>"
                )
                if show_comments:
                    rows_html += (
                        f"<td data-sort='{sort_token(len(row.get('comments') or []), numeric=True)}' "
                        f"style='padding:10px;text-align:center;white-space:nowrap;'>"
                        f"{comment_balloon(row.get('comments'), asset_market_key(kind, asset_id))}</td>"
                    )
                rows_html += (
                    f"<td data-sort='{sort_token(row.get('change_30d'), numeric=True)}' "
                    f"style='padding:6px 10px;width:84px;'>{sparkline_svg(row.get('closes'), row.get('change_30d'))}</td></tr>"
                )

            table_key = html.escape(kind + "|" + "|".join(headers), quote=True)
            table_html = (
                "<div style='width:100%;overflow-x:auto;margin-bottom:8px;-webkit-overflow-scrolling:touch;'>"
                "<table class='ang-table' data-table='"
                f"{table_key}'>"
                f"<thead><tr>{header_html}</tr></thead>"
                f"<tbody>{rows_html}</tbody></table></div>"
            )
            picked = _score_table(
                key=f"score_table_{kind}",
                data=table_html,
                on_picked_change=lambda: None,
            ).picked
            if picked:
                _select_chart_asset(str(picked))

            problems = [
                f"{row['symbol']}: {row['reasons'][0]}"
                for row in results
                if row.get("label") in ("No data", "Error") and row.get("reasons")
            ]
            for problem in problems:
                st.text(problem)

    chosen_kind = st.query_params.get("chart_kind")
    chosen_asset = st.query_params.get("chart_asset")
    if chosen_kind and chosen_asset:
        chosen_kind = str(chosen_kind)
        chosen_asset = str(chosen_asset)
        chosen_list = crypto_watchlist if chosen_kind == "Crypto" else stock_watchlist if chosen_kind == "Stock" else {}
        if chosen_kind in allowed_kinds and chosen_asset in chosen_list:
            st.session_state.chart_pick = (chosen_kind, chosen_asset)
            st.session_state.chart_pick_from_row = True
        del st.query_params["chart_kind"]
        del st.query_params["chart_asset"]

    if "chart_pick" not in st.session_state:
        saved_kind = str((prefs.get("settings") or {}).get("chart_kind") or "")
        saved_asset = str((prefs.get("settings") or {}).get("chart_asset") or "")
        saved_list = crypto_watchlist if saved_kind == "Crypto" else stock_watchlist if saved_kind == "Stock" else {}
        if saved_kind in allowed_kinds and saved_asset in saved_list:
            st.session_state.chart_pick = (saved_kind, saved_asset)

    pick = st.session_state.get("chart_pick")
    if not pick or pick[0] not in allowed_kinds:
        if "Crypto" in allowed_kinds and crypto_watchlist:
            asset_id = next(iter(crypto_watchlist))
            st.session_state.chart_pick = ("Crypto", asset_id)
            st.session_state.asset_type = "Crypto"
            st.session_state.asset_crypto = asset_id
        elif "Stock" in allowed_kinds and stock_watchlist:
            asset_id = next(iter(stock_watchlist))
            st.session_state.chart_pick = ("Stock", asset_id)
            st.session_state.asset_type = "Stock"
            st.session_state.asset_stock = asset_id
        else:
            st.session_state.pop("chart_pick", None)
    elif st.session_state.get("asset_type") not in allowed_kinds:
        st.session_state.asset_type = pick[0]

    if trade_crypto:
        style_and_show_table(crypto_results, "₿ Crypto Scores", "Crypto", "crypto_scores")
    if trade_equities:
        style_and_show_table(stock_results, "📈 Equity Scores", "Stock", "equity_scores")

    pick = st.session_state.get("chart_pick")
    if pick and pick[0] in allowed_kinds and (
        st.session_state.pop("chart_pick_from_row", False)
        or "asset_type" not in st.session_state
    ):
        pick_kind, pick_key = pick
        pick_list = crypto_watchlist if pick_kind == "Crypto" else stock_watchlist
        if pick_key in pick_list:
            st.session_state.asset_type = pick_kind
            if pick_kind == "Crypto":
                st.session_state.asset_crypto = pick_key
            else:
                st.session_state.asset_stock = pick_key

    def selected_chart_name():
        kind = st.session_state.get("asset_type")
        if kind not in allowed_kinds:
            kind = allowed_kinds[0] if allowed_kinds else "Crypto"
        watchlist = crypto_watchlist if kind == "Crypto" else stock_watchlist
        state_key = "asset_crypto" if kind == "Crypto" else "asset_stock"
        asset_id = st.session_state.get(state_key)
        if asset_id not in watchlist:
            asset_id = next(iter(watchlist), None)
        if not asset_id:
            return "", kind, ""
        if kind == "Crypto":
            return str(watchlist[asset_id]), kind, asset_id
        return f"{watchlist[asset_id]} ({asset_id})", kind, asset_id

    chart_name, chart_kind, chart_asset = selected_chart_name()
    if chart_kind in ("Crypto", "Stock") and chart_asset:
        _asset_link(
            key="asset_link",
            data={
                "key": asset_market_key(chart_kind, chart_asset),
                "label": " ".join(str(chart_name or chart_asset).split()),
                "kind": chart_kind,
                "id": str(chart_asset),
            },
            on_refresh_change=lambda: None,
        )
    if chart_kind in ("Crypto", "Stock") and chart_asset:
        save_account_settings({"chart_kind": chart_kind, "chart_asset": str(chart_asset)})
    chart_logo = (st.session_state.get("asset_logos") or {}).get(asset_market_key(chart_kind, chart_asset))
    chart_label = f"📊 Interactive Chart - {chart_name}" if chart_name else "📊 Interactive Chart"
    if wide_layout:
        # Tops stay level. Do not put a widget above the chart expander in asset_col.
        if "wide_split" not in st.session_state:
            try:
                stored_split = float((prefs.get("settings") or {}).get("wide_split", 0.5))
            except (TypeError, ValueError):
                stored_split = 0.5
            st.session_state.wide_split = min(_WIDE_SPLIT_MAX, max(_WIDE_SPLIT_MIN, stored_split))
        reported = _wide_split_handle(
            key="wide_column_split",
            data={"split": f"{float(st.session_state.wide_split):.3f}"},
            on_split_change=lambda: None,
        )
        raw_split = getattr(reported, "split", None)
        if raw_split not in (None, ""):
            try:
                next_split = float(raw_split)
            except (TypeError, ValueError):
                next_split = None
            if next_split is not None:
                next_split = min(_WIDE_SPLIT_MAX, max(_WIDE_SPLIT_MIN, next_split))
                if abs(next_split - float(st.session_state.wide_split)) > 0.004:
                    st.session_state.wide_split = next_split
                    save_account_settings({"wide_split": round(next_split, 3)})
        split = min(_WIDE_SPLIT_MAX, max(_WIDE_SPLIT_MIN, float(st.session_state.wide_split)))
        mood_col, asset_col = st.columns([split, 1 - split], gap="medium", vertical_alignment="top")
        with mood_col:
            show_market_moods(trade_crypto, trade_equities)
        asset_area = asset_col
    else:
        asset_area = nullcontext()
    with asset_area:
        st.html(
            "<div id='interactive-chart' style='scroll-margin-top:4.5rem;'></div>"
        )
        with section_expander(chart_label, "interactive_chart"):
            mark_col, chart_top = st.columns([5.2, 0.9], vertical_alignment="center")
            with mark_col:
                if chart_name:
                    st.markdown(
                        _section_mark(
                            asset_logo(chart_logo, chart_name, size=32),
                            _ticker_label(chart_kind, chart_asset, chart_name),
                        ),
                        unsafe_allow_html=True,
                    )
            with chart_top:
                _back_to_top(key="chart_back_to_top")

            if len(allowed_kinds) > 1:
                col1, col2 = st.columns([1, 3])
                with col1:
                    asset_type = st.selectbox("Type", allowed_kinds, key="asset_type")
                asset_box = col2
            else:
                asset_type = allowed_kinds[0]
                asset_box = st.container()
            with asset_box:
                watchlist = crypto_watchlist if asset_type == "Crypto" else stock_watchlist
                options = list(watchlist.keys())
                asset_state_key = "asset_crypto" if asset_type == "Crypto" else "asset_stock"
                if options and st.session_state.get(asset_state_key) not in options:
                    st.session_state[asset_state_key] = options[0]
                if options:
                    asset_key = st.selectbox(
                        "Asset",
                        options,
                        format_func=lambda item: watchlist[item] if asset_type == "Crypto" else f"{watchlist[item]} ({item})",
                        key=asset_state_key,
                    )
                else:
                    asset_key = None
                    st.caption("This watchlist is empty.")

            wanted = (asset_type, asset_key)
            pick_now = st.session_state.get("chart_pick")
            if (
                asset_key
                and st.session_state.get("_chart_from_row")
                and pick_now
                and pick_now[0] in allowed_kinds
                and pick_now != wanted
            ):
                # A table click already chose the asset. Paint that once.
                # Do not let the selectbox pull the chart back and run again.
                row_hold = ("row", pick_now)
                if st.session_state.get("_chart_sync_hold") != row_hold:
                    st.session_state["_chart_sync_hold"] = row_hold
                    _rerun_fragment()
                else:
                    asset_type, asset_key = pick_now
            elif asset_key and pick_now != wanted:
                st.session_state.chart_pick = wanted
                if st.session_state.get("_chart_sync_hold") != wanted:
                    st.session_state["_chart_sync_hold"] = wanted
                    _rerun_fragment()
            else:
                st.session_state.pop("_chart_sync_hold", None)

            if not asset_key:
                st.info("Add an asset to this watchlist to see a chart.")
                st.session_state.pop("_chart_from_row", None)
                st.session_state.pop("_chart_row_quiet", None)
                return

            df_chart, chart_err = _stored_bars(asset_type, asset_key, history_days)
            if asset_type == "Crypto":
                title = crypto_watchlist[asset_key]
            else:
                title = f"{stock_watchlist[asset_key]} ({asset_key})"

            if chart_err or df_chart.empty:
                st.warning(chart_err or "Could not load chart data. Check your internet connection.")
                st.session_state.pop("_chart_from_row", None)
                st.session_state.pop("_chart_row_quiet", None)
                return

            df_chart = calculate_indicators(df_chart)
            indicator_keys = chart_plan.available(df_chart.columns)
            indicator_icons = {"sma200": "📏", "ichimoku": "☁️", "macd": "〰️", "stoch": "🎚️", "adx": "🧭", "obv": "📊"}
            # Crypto charts also offer estimated liquidation levels, drawn by this page, not chart_plan.
            if asset_type == "Crypto":
                indicator_keys = list(indicator_keys) + [LIQ_KEY]

            def _indicator_label(key):
                if key == LIQ_KEY:
                    return "🔥 Liquidation levels"
                return f"{indicator_icons.get(key, '')} {chart_plan.INDICATORS[key]['label']}".strip()

            # The chart choices belong to the account. Start from what was saved, and keep a saved
            # choice this asset cannot draw (too little history) so it comes back on the next asset.
            saved_chart = (st.session_state.get("cloud_prefs") or {}).get("settings") or {}
            saved_picks = [k for k in (saved_chart.get("chart_indicators") or []) if k in chart_plan.INDICATORS]
            # The liquidation choice is kept apart, so a stock chart (which has no levels)
            # does not switch it off for the next coin.
            if "_chart_liq_on" not in st.session_state:
                st.session_state["_chart_liq_on"] = bool(saved_chart.get("chart_liq", False))
            if "chart_indicators" not in st.session_state:
                st.session_state["chart_indicators"] = [k for k in saved_picks if k in indicator_keys]
            else:
                st.session_state["chart_indicators"] = [
                    k for k in (st.session_state.get("chart_indicators") or []) if k in indicator_keys
                ]
            # Put the choice back only when the icon was not on offer last time (first load,
            # or coming from a stock chart). Otherwise the icon itself is the choice, so
            # switching it off stays off.
            liq_offered_before = bool(st.session_state.get("_chart_liq_offered"))
            st.session_state["_chart_liq_offered"] = LIQ_KEY in indicator_keys
            if LIQ_KEY in indicator_keys and not liq_offered_before and st.session_state["_chart_liq_on"]:
                if LIQ_KEY not in st.session_state["chart_indicators"]:
                    st.session_state["chart_indicators"] = list(st.session_state["chart_indicators"]) + [LIQ_KEY]
            if "chart_overlay" not in st.session_state:
                st.session_state["chart_overlay"] = bool(saved_chart.get("chart_overlay", False))
            if "chart_earnings" not in st.session_state:
                st.session_state["chart_earnings"] = bool(saved_chart.get("chart_earnings", True))
            chosen_indicators = []
            # Crypto only: a link to CoinGlass's liquidation heatmap for the coin on the chart.
            heatmap_url = coinglass_heatmap_url(asset_key) if asset_type == "Crypto" else ""
            if indicator_keys:
                if hasattr(st, "pills"):
                    chosen_indicators = st.pills(
                        "Chart indicators",
                        indicator_keys,
                        selection_mode="multi",
                        format_func=_indicator_label,
                        key="chart_indicators",
                        label_visibility="collapsed",
                    ) or []
                else:
                    chosen_indicators = st.multiselect(
                        "Chart indicators",
                        indicator_keys,
                        format_func=_indicator_label,
                        key="chart_indicators",
                    )
            if heatmap_url:
                # A plain link with the usual "opens elsewhere" mark, so it does not look like
                # one more chart toggle.
                tip = html.escape(
                    f"CoinGlass's liquidation heatmap for {title}, in a new tab. "
                    "CoinGlass asks you to log in, free, to see the full data.",
                    quote=True,
                )
                st.markdown(
                    f"<a href='{html.escape(heatmap_url, quote=True)}' target='_blank' rel='noopener' "
                    f"title='{tip}' style='display:inline-flex;align-items:center;gap:5px;"
                    "font-size:0.9rem;text-decoration:none;'>"
                    "CoinGlass liquidation heatmap"
                    "<svg viewBox='0 0 24 24' width='14' height='14' aria-hidden='true' fill='none' "
                    "stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>"
                    "<path d='M14 4h6v6'/><path d='M20 4 10 14'/>"
                    "<path d='M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5'/></svg></a>",
                    unsafe_allow_html=True,
                )
            if LIQ_KEY in indicator_keys:
                st.session_state["_chart_liq_on"] = LIQ_KEY in chosen_indicators
            liq_on = LIQ_KEY in chosen_indicators
            chosen_indicators = [k for k in chosen_indicators if k != LIQ_KEY]
            overlay_curves = st.checkbox(
                "Overlay RSI, Stochastic and ADX on the price chart",
                key="chart_overlay",
                help=(
                    "Draws these curves on the price chart against a 0 to 100 scale on the right, "
                    "instead of in panels underneath. MACD and OBV have no fixed range, so they stay in their own panels."
                ),
            )
            show_earnings = False
            if asset_type != "Crypto":
                show_earnings = st.checkbox(
                    "Show earnings report dates",
                    key="chart_earnings",
                    help=(
                        "Marks past report days with dotted lines and the next one with a dashed line. "
                        "The chart stretches to the right to fit the next date (only when it is within 6 weeks), so switch this off "
                        "if it is months away and you want the chart to end at today."
                    ),
                )
            wanted_picks = [k for k in saved_picks if k not in indicator_keys] + [
                k for k in chosen_indicators if k in chart_plan.INDICATORS
            ]
            chart_choices = {
                "chart_indicators": [k for k in chart_plan.INDICATORS if k in wanted_picks],
                "chart_overlay": bool(overlay_curves),
                "chart_liq": bool(st.session_state.get("_chart_liq_on")),
            }
            if asset_type != "Crypto":
                chart_choices["chart_earnings"] = bool(show_earnings)
            save_account_settings(chart_choices)
            layout = chart_plan.plan(chosen_indicators, df_chart.columns, overlay_curves=overlay_curves)
            panel_titles = {
                "volume": "Volume", "rsi": "RSI (14)", "macd": "MACD", "stoch": "Stochastic (14, 3)",
                "adx": "ADX (14)", "obv": "On-balance volume",
            }
            panels = layout["panels"]
            row_of = {name: index + 2 for index, name in enumerate(panels)}
            fig = make_subplots(
                rows=1 + len(panels), cols=1,
                shared_xaxes=True,
                vertical_spacing=0.04,
                row_heights=layout["heights"],
                subplot_titles=tuple([f"{title} Price"] + [panel_titles[name] for name in panels]),
                specs=[[{"secondary_y": True}]] + [[{}] for _ in panels],
            )

            def _put(trace, key):
                """Draw on the price chart's right-hand axis, or in this curve's own panel."""
                if key in layout["secondary"]:
                    fig.add_trace(trace, row=1, col=1, secondary_y=True)
                else:
                    fig.add_trace(trace, row=row_of[key], col=1)

            def _guide(key, level, colour, dash="dash"):
                if key in layout["secondary"]:
                    fig.add_hline(y=level, line_dash=dash, line_color=colour, opacity=0.4, row=1, col=1, secondary_y=True)
                else:
                    fig.add_hline(y=level, line_dash=dash, line_color=colour, opacity=0.5, row=row_of[key], col=1)
            fig.add_trace(
                go.Candlestick(
                    x=df_chart.index, open=df_chart["open"], high=df_chart["high"],
                    low=df_chart["low"], close=df_chart["close"], name="Price",
                ),
                row=1, col=1,
            )
            if "sma_20" in df_chart.columns:
                fig.add_trace(
                    go.Scatter(x=df_chart.index, y=df_chart["sma_20"], name="SMA 20", line=dict(color="orange", width=1.5)),
                    row=1, col=1,
                )
            if "sma_50" in df_chart.columns:
                fig.add_trace(
                    go.Scatter(x=df_chart.index, y=df_chart["sma_50"], name="SMA 50", line=dict(color="royalblue", width=1.5)),
                    row=1, col=1,
                )
            if "sma200" in layout["overlays"]:
                fig.add_trace(
                    go.Scatter(x=df_chart.index, y=df_chart["sma_200"], name="SMA 200", line=dict(color="#9333ea", width=1.5)),
                    row=1, col=1,
                )
            if "ichimoku" in layout["overlays"]:
                fig.add_trace(
                    go.Scatter(x=df_chart.index, y=df_chart["ichi_span_a"], name="Cloud edge A",
                               line=dict(color="rgba(34,197,94,0.5)", width=1), showlegend=False),
                    row=1, col=1,
                )
                fig.add_trace(
                    go.Scatter(x=df_chart.index, y=df_chart["ichi_span_b"], name="Ichimoku cloud",
                               line=dict(color="rgba(239,68,68,0.5)", width=1), fill="tonexty",
                               fillcolor="rgba(128,128,128,0.12)"),
                    row=1, col=1,
                )
                fig.add_trace(
                    go.Scatter(x=df_chart.index, y=df_chart["ichi_tenkan"], name="Tenkan",
                               line=dict(color="#0ea5e9", width=1)),
                    row=1, col=1,
                )
                fig.add_trace(
                    go.Scatter(x=df_chart.index, y=df_chart["ichi_kijun"], name="Kijun",
                               line=dict(color="#f43f5e", width=1)),
                    row=1, col=1,
                )

            upper_name = find_column(df_chart, "BBU_")
            lower_name = find_column(df_chart, "BBL_")
            if upper_name and lower_name:
                fig.add_trace(
                    go.Scatter(
                        x=df_chart.index, y=df_chart[upper_name], name="BB Upper",
                        line=dict(color="gray", width=1, dash="dot"), showlegend=False,
                    ),
                    row=1, col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=df_chart.index, y=df_chart[lower_name], name="BB Lower",
                        line=dict(color="gray", width=1, dash="dot"), fill="tonexty",
                        fillcolor="rgba(128,128,128,0.08)", showlegend=False,
                    ),
                    row=1, col=1,
                )

            liq_record = _liquidation_record(asset_key) if liq_on else None
            if liq_on:
                _draw_liquidation_levels(fig, liq_record, df_chart.index[-1])

            colors = [
                "green" if df_chart["close"].iloc[i] >= df_chart["open"].iloc[i] else "red"
                for i in range(len(df_chart))
            ]
            fig.add_trace(
                go.Bar(x=df_chart.index, y=df_chart["volume"], name="Volume", marker_color=colors, opacity=0.6),
                row=row_of["volume"], col=1,
            )
            if "rsi" in df_chart.columns:
                _put(go.Scatter(x=df_chart.index, y=df_chart["rsi"], name="RSI", line=dict(color="purple", width=1.5)), "rsi")
                _guide("rsi", 70, "red")
                _guide("rsi", 30, "green")
                if "rsi" not in layout["secondary"]:
                    _guide("rsi", 50, "gray", "dot")
            if "macd" in row_of:
                macd_row = row_of["macd"]
                hist_col = find_column(df_chart, "MACDh_")
                line_col = find_column(df_chart, "MACD_")
                signal_col = find_column(df_chart, "MACDs_")
                if hist_col:
                    hist = df_chart[hist_col]
                    fig.add_trace(
                        go.Bar(x=df_chart.index, y=hist, name="MACD histogram", opacity=0.6,
                               marker_color=["green" if (v or 0) >= 0 else "red" for v in hist]),
                        row=macd_row, col=1,
                    )
                if line_col:
                    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart[line_col], name="MACD",
                                             line=dict(color="royalblue", width=1.5)), row=macd_row, col=1)
                if signal_col:
                    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart[signal_col], name="MACD signal",
                                             line=dict(color="orange", width=1.5)), row=macd_row, col=1)
            if "stoch" in layout["panels"] + layout["secondary"]:
                _put(go.Scatter(x=df_chart.index, y=df_chart["stoch_k"], name="Stochastic %K",
                                line=dict(color="#0ea5e9", width=1.5)), "stoch")
                if "stoch" not in layout["secondary"]:
                    _guide("stoch", 80, "red")
                    _guide("stoch", 20, "green")
            if "adx" in layout["panels"] + layout["secondary"]:
                _put(go.Scatter(x=df_chart.index, y=df_chart["adx"], name="ADX",
                                line=dict(color="#a16207", width=1.5)), "adx")
                if "adx" not in layout["secondary"]:
                    _guide("adx", 25, "gray")
            if "obv" in row_of:
                obv_row = row_of["obv"]
                fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["obv"], name="OBV",
                                         line=dict(color="#14b8a6", width=1.5)), row=obv_row, col=1)
                if "obv_sma_20" in df_chart.columns:
                    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["obv_sma_20"], name="OBV average",
                                             line=dict(color="orange", width=1.2, dash="dot")), row=obv_row, col=1)

            earnings_on = None
            if show_earnings and stock_watchlist:
                try:
                    earnings_on = load_earnings(
                        tuple(stock_watchlist), st.session_state.get("_shared_rows")
                    ).get(str(asset_key).upper())
                except Exception:
                    earnings_on = None
            if show_earnings:
                try:
                    chart_start = pd.Timestamp(df_chart.index[0]).tz_localize(None)
                    for past_day in _past_report_dates(str(asset_key).upper()):
                        if pd.Timestamp(past_day) >= chart_start:
                            fig.add_vline(x=past_day, line_dash="dot", line_color="#f59e0b", line_width=1.5, opacity=0.6)
                except Exception:
                    pass
            if earnings_on:
                try:
                    report_day = pd.Timestamp(earnings_on).tz_localize(None).normalize()
                    last_bar = pd.Timestamp(df_chart.index[-1]).tz_localize(None).normalize()
                    first_bar = pd.Timestamp(df_chart.index[0]).tz_localize(None)
                    if last_bar <= report_day <= last_bar + pd.Timedelta(days=42):
                        fig.add_vline(x=report_day.isoformat(), line_dash="dash", line_color="#f59e0b", line_width=2, opacity=0.9)
                        fig.add_annotation(
                            x=report_day.isoformat(), y=1, yref="paper", yanchor="bottom",
                            text=f"Earnings {report_day:%d %b}", showarrow=False,
                            font=dict(color="#f59e0b", size=12),
                        )
                        pad = max(3, (report_day - last_bar).days // 10)
                        fig.update_xaxes(range=[first_bar.isoformat(), (report_day + pd.Timedelta(days=pad)).isoformat()])
                except Exception:
                    pass

            fig.update_layout(
                height=750 + 150 * (len(panels) - 2) if len(panels) > 2 else 750 - 100 * (2 - len(panels)),
                xaxis_rangeslider_visible=False,
                showlegend=True,
                # The legend sits under the chart, in its own strip, so it never meets the toolbar
                # that appears top right when the mouse is over the chart.
                legend=dict(orientation="h", yref="container", y=0, yanchor="bottom", xref="paper", x=0, xanchor="left"),
                margin=dict(t=60, b=150),
            )
            fig.update_yaxes(title_text="Price", row=1, col=1)
            fig.update_yaxes(title_text="Volume", row=row_of["volume"], col=1)
            if "rsi" in row_of:
                fig.update_yaxes(title_text="RSI", range=[0, 100], row=row_of["rsi"], col=1)
            if "stoch" in row_of:
                fig.update_yaxes(range=[0, 100], row=row_of["stoch"], col=1)
            if layout["secondary"]:
                fig.update_yaxes(
                    title_text="0 to 100", range=[0, 100], showgrid=False,
                    row=1, col=1, secondary_y=True,
                )
            _paint_chart(fig)
            st.plotly_chart(fig, width="stretch")
            if liq_on:
                st.caption(_liquidation_caption(liq_record))

            result = compute_score(df_chart, weights=weights, adaptive=bool(st.session_state.get("adaptive_scoring")))
            score_val = result["score"]
            color, _bg, arrow, _bar = tone(score_val)
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.markdown(
                    "<div style='font-size: 0.85rem; color: #6b7280; margin-bottom: 2px;'>Current Score</div>"
                    f"<div style='font-size: 2.2rem; font-weight: 600; line-height: 1.1; margin-bottom: 4px;'>{score_val}/100</div>"
                    f"<div style='font-size: 0.95rem; font-weight: 500; color: {color};'>"
                    f"{arrow} {html.escape(str(result['label']))}</div>",
                    unsafe_allow_html=True,
                )
            if result.get("change_7d") is not None:
                change = result["change_7d"]
                if change > 0:
                    change_color = "#15803d"
                elif change < 0:
                    change_color = "#b91c1c"
                else:
                    change_color = "#6b7280"
                col_b.markdown(
                    "<div style='font-size: 0.85rem; color: #6b7280; margin-bottom: 2px;'>7-Day Change</div>"
                    f"<div style='font-size: 2.2rem; font-weight: 600; line-height: 1.1; color: {change_color};'>"
                    f"{change:+.1f}%</div>",
                    unsafe_allow_html=True,
                )
            if result.get("atr_pct") is not None:
                col_c.metric(
                    "Typical daily move (ATR%)",
                    f"{result['atr_pct']:.2f}%",
                    help="The average distance price travels in a day, as a share of its price. "
                    "In testing this was the one reading that reliably said how big the next few days' moves would be. "
                    "It does not say which way.",
                )

        reveal_breakdown = st.session_state.get("scroll_target") == "score-breakdown"
        if (show_reasons_flag or reveal_breakdown) and result.get("reasons") and result.get("score") is not None:
            st.html("<div id='score-breakdown' style='scroll-margin-top:4.5rem;'></div>")
            with section_expander(f"🔍 Score Breakdown — {title}", "score_breakdown"):
                _paint_section_score("breakdown", result["score"], result.get("score") is not None)
                _score_rules_popover(weights)
                table_rows = crypto_results if asset_type == "Crypto" else stock_results
                matched = next(
                    (row for row in table_rows if str(row.get("key")) == str(asset_key)),
                    None,
                )
                summary = _score_sentence((matched or result).get("reasons"))
                st.markdown(
                    "<div style='margin:0 0 12px;'>"
                    f"{sentiment_badge(result['score'])}"
                    f"<div style='margin-top:8px;color:{color};font-weight:600;'>"
                    f"{html.escape(str(result['label']))}</div>"
                    f"<div class='ang-copy' style='margin-top:6px;'>Summary: {html.escape(summary)}</div></div>",
                    unsafe_allow_html=True,
                )
                breakdown_col1, breakdown_col2 = st.columns(2)
                with breakdown_col1:
                    contributions = result.get("contributions") or {}
                    if contributions:
                        fig_contrib = go.Figure(go.Bar(
                            x=list(contributions.values()),
                            y=list(contributions.keys()),
                            orientation="h",
                            marker_color=["#22c55e" if points >= 0 else "#ef4444" for points in contributions.values()],
                        ))
                        fig_contrib.update_layout(
                            title="Indicator Point Contributions",
                            xaxis_title="Points Added or Subtracted",
                            yaxis=dict(autorange="reversed"),
                            height=320,
                            margin=dict(t=30, b=20, l=10, r=10),
                        )
                        fig_contrib.add_vline(x=0, line_width=1.5, line_dash="dash", line_color="gray", opacity=0.7)
                        _paint_chart(fig_contrib)
                        st.plotly_chart(fig_contrib, width="stretch")
                with breakdown_col2:
                    st.markdown("**Detailed Reasons**")
                    for reason in result["reasons"]:
                        st.caption(f"• {reason}")

        sentiment_label = crypto_watchlist[asset_key] if asset_type == "Crypto" else stock_watchlist[asset_key]
        with _timed("section: max pain"):
            show_max_pain(asset_type, asset_key, title, float(df_chart["close"].iloc[-1]))
        with _timed("section: leverage & liquidations"):
            show_leverage(asset_type, asset_key, title)
        with _timed("section: market sentiment"):
            show_market_sentiment(
                asset_type,
                asset_key,
                sentiment_label,
                crypto_ticker(asset_key) if asset_type == "Crypto" else asset_key,
            )
        with _timed("section: signal matrix"):
            show_signal_matrix(asset_type, asset_key, title, df_chart, weights)
    # Outside both wide columns, so it cannot push the chart header down.
    _scroll_chart(
        key="scroll_to_chart",
        data={
            "token": st.session_state.get("scroll_token") or "",
            "target": st.session_state.get("scroll_target") or "interactive-chart",
        },
    )
    st.session_state.pop("_chart_row_quiet", None)
    from_row = st.session_state.pop("_chart_from_row", False)
    if st.session_state.pop("_shared_reread", False) and not from_row:
        _rerun_fragment()


def _store_mood_vote(market_key: str, sentiment_at, vote, alt_score=None) -> bool:
    """Save a market thumb. The take box reruns on its own, so this does not refresh the page."""
    try:
        set_market_mood_vote(supabase, user_id, market_key, sentiment_at, vote, alt_score)
    except Exception:
        return False
    return True


def _store_sentiment_vote(kind: str, asset_id: str, sentiment_at, vote, alt_score=None) -> bool:
    """Save an asset thumb. The take box reruns on its own, so this does not refresh the page."""
    try:
        set_sentiment_vote(supabase, user_id, kind, asset_id, sentiment_at, vote, alt_score)
    except Exception:
        return False
    return True


def _store_sentiment_comment(
    kind: str, asset_id: str, sentiment_at, body: str, responded_score=None, responded_summary: str = "",
) -> bool:
    """Save a comment. The take box reruns on its own, so this does not refresh the page."""
    try:
        set_sentiment_comment(
            supabase, user_id, kind, asset_id, sentiment_at, body, responded_score, responded_summary,
        )
    except Exception:
        return False
    return True


def _take_result(prefix: str, ok: bool, message: str) -> None:
    """Remember a save failure for the next paint of this take box."""
    note = f"{prefix}_take_error"
    if ok:
        st.session_state.pop(note, None)
    else:
        st.session_state[note] = message


@st.fragment
def _sentiment_thumbs(
    kind: str, asset_id: str, sentiment_at, title: str, responded_score=None, responded_summary: str = "",
    *, prefix: str = "sentiment", voice: dict | None = None, on_vote=None, on_comment=None,
) -> None:
    """Agree or disagree, then one short comment. A click redraws only this box."""
    del title, voice
    if not sentiment_at:
        st.caption("Thumbs and comments open once this sentiment is saved.")
        return
    key = asset_market_key(kind, asset_id)
    if str(kind) == "Mood":
        voice = market_mood_crowd(supabase, [str(asset_id)]).get(str(asset_id)) or {}
    else:
        voice = sentiment_crowd(supabase, [key]).get(key) or {}
    if on_vote is None:
        on_vote = lambda vote, alt_score=None: _store_sentiment_vote(
            kind, asset_id, sentiment_at, vote, alt_score,
        )
    if on_comment is None:
        on_comment = lambda text: _store_sentiment_comment(
            kind, asset_id, sentiment_at, text, responded_score, responded_summary,
        )
    mine = voice.get("mine")
    mine_score = voice.get("alt")
    selected = (
        int(mine_score)
        if mine_score is not None and float(mine_score) in (0, 20, 40, 60, 80, 100)
        else None
    )
    selected_color = ""
    if selected is not None:
        color, _background, _arrow, _bar = tone(selected)
        selected_color = f"""
        .st-key-{prefix}_alt_{selected} [data-testid="stBaseButton-primary"],
        .st-key-{prefix}_alt_{selected} [data-testid="stBaseButton-primary"]:hover,
        .st-key-{prefix}_alt_{selected} [data-testid="stBaseButton-primary"]:focus,
        .st-key-{prefix}_alt_{selected} [data-testid="stBaseButton-primary"]:active {{
            background-color: {color};
            border-color: {color};
            color: #ffffff;
        }}
        .st-key-{prefix}_alt_{selected} [data-testid="stBaseButton-primary"] p {{
            color: #ffffff;
        }}
        """
    st.html(
        f"""
        <style>
        [class*="st-key-market_sentiment_panel"] details[open],
        [class*="st-key-market_mood_"] details[open] {{
            overflow: visible !important;
        }}
        .st-key-{prefix}_take_box {{
            background: var(--ang-surface, #ffffff);
            border: 1px solid var(--ang-border, #e5e7eb) !important;
            border-radius: 10px !important;
            overflow: visible !important;
        }}
        .st-key-{prefix}_agree,
        .st-key-{prefix}_disagree {{
            position: relative;
            overflow: visible !important;
        }}
        .st-key-{prefix}_agree:hover::after,
        .st-key-{prefix}_disagree:hover::after {{
            position: absolute;
            z-index: 30;
            left: 0;
            right: 0;
            bottom: calc(100% + 6px);
            background: #31333f;
            color: #ffffff;
            font-size: 0.8rem;
            font-weight: 400;
            line-height: 1.35;
            padding: 8px 10px;
            border-radius: 4px;
            pointer-events: none;
            white-space: normal;
        }}
        .st-key-{prefix}_agree:hover::after {{
            content: "You agree with this sentiment. Press again to clear it.";
        }}
        .st-key-{prefix}_disagree:hover::after {{
            content: "You disagree with this sentiment. Press again to clear it.";
        }}
        .st-key-{prefix}_agree [data-testid="stBaseButton-primary"],
        .st-key-{prefix}_agree [data-testid="stBaseButton-primary"]:hover,
        .st-key-{prefix}_agree [data-testid="stBaseButton-primary"]:focus,
        .st-key-{prefix}_agree [data-testid="stBaseButton-primary"]:active {{
            background-color: #15803d;
            border-color: #15803d;
            color: #ffffff;
        }}
        .st-key-{prefix}_agree [data-testid="stBaseButton-primary"] p {{
            color: #ffffff;
        }}
        .st-key-{prefix}_take_box .stColumn {{
            min-width: 0 !important;
        }}
        .st-key-{prefix}_comment_row {{
            margin-top: 6px;
        }}
        .st-key-{prefix}_comment_form {{
            border: none;
            padding: 0;
            background: transparent;
        }}
        .take-faces {{
            display: flex;
            gap: 4px;
            margin-top: 4px;
        }}
        .take-face {{
            flex: 1;
            min-width: 0;
            padding: 0.15rem 0;
            font: inherit;
            font-size: 1rem;
            line-height: 1.1;
            cursor: pointer;
            border-radius: 0.5rem;
            border: 1px solid rgba(49, 51, 63, 0.2);
            background: #f0f2f6;
            color: inherit;
        }}
        .take-face-poop {{
            font-size: 1.45rem;
            line-height: 1;
        }}
        .take-face:hover {{
            border-color: #ff4b4b;
        }}
        html.angstrom-night .take-face {{
            background: #262730;
            border-color: #4b5563;
            color: #fafafa;
        }}
        .st-key-{prefix}_alt_0 button,
        .st-key-{prefix}_alt_20 button,
        .st-key-{prefix}_alt_40 button,
        .st-key-{prefix}_alt_60 button,
        .st-key-{prefix}_alt_80 button,
        .st-key-{prefix}_alt_100 button {{
            min-width: 0;
            padding: 0.3rem 0;
        }}
        .st-key-{prefix}_alt_0 button p,
        .st-key-{prefix}_alt_20 button p,
        .st-key-{prefix}_alt_40 button p,
        .st-key-{prefix}_alt_60 button p,
        .st-key-{prefix}_alt_80 button p,
        .st-key-{prefix}_alt_100 button p {{
            font-size: 0.8rem;
        }}
        {selected_color}
        </style>
        """
    )
    st.session_state[f"{prefix}_saved_vote"] = mine
    with st.container(border=True, key=f"{prefix}_take_box"):
        st.markdown("**Your take**")
        problem = st.session_state.get(f"{prefix}_take_error")
        if problem:
            st.warning(problem)

        def _click_agree(saver=on_vote, box=prefix) -> None:
            current = st.session_state.get(f"{box}_saved_vote")
            _take_result(
                box,
                bool(saver(None if current == 1 else 1)),
                "That thumb could not be saved. Please try again.",
            )

        def _click_disagree(saver=on_vote, box=prefix) -> None:
            current = st.session_state.get(f"{box}_saved_vote")
            _take_result(
                box,
                bool(saver(None if current == -1 else -1)),
                "That thumb could not be saved. Please try again.",
            )

        st.button(
            "👍 Agree",
            key=f"{prefix}_agree",
            use_container_width=True,
            type="primary" if mine == 1 else "secondary",
            on_click=_click_agree,
        )
        st.button(
            "👎 Disagree",
            key=f"{prefix}_disagree",
            use_container_width=True,
            type="primary" if mine == -1 else "secondary",
            on_click=_click_disagree,
        )
        if mine == -1:
            _sentiment_alt_score(kind, asset_id, sentiment_at, mine_score, selected, prefix, on_vote)
        notes = sentiment_comment_lists(supabase, [key]).get(key) or []
        mine_text = next((item["text"] for item in notes if item.get("mine")), "")
        _comment_row(
            key=f"{prefix}_comment_row",
            data=(
                "<div style='display:flex;align-items:center;gap:8px;flex-wrap:wrap;'>"
                + crowd_mark(
                    voice.get("up"),
                    voice.get("down"),
                    alt_count=voice.get("alt_count"),
                    alt_avg=voice.get("alt_avg"),
                    alt_spread=voice.get("alt_spread"),
                )
                + crowd_average_badge(
                    voice.get("alt_avg"),
                    voice.get("alt_count"),
                    voice.get("alt_spread"),
                )
                + comment_balloon(notes, key)
                + "</div>"
            ),
        )
        if str(kind) in ("Crypto", "Stock"):
            _sync_table_crowd(kind, asset_id, voice)
        box_key = f"sentiment_comment_box_{key}"
        posted_key = f"{box_key}_posted"
        st.session_state[f"{prefix}_saved_comment"] = mine_text
        if box_key not in st.session_state:
            st.session_state[box_key] = mine_text
        elif st.session_state.get(posted_key) == st.session_state.get(box_key) and st.session_state.get(box_key) != mine_text:
            st.session_state[box_key] = mine_text
        st.session_state[posted_key] = mine_text

        def _post_comment(saver=on_comment, box=prefix, field=box_key) -> None:
            text = " ".join(str(st.session_state.get(field) or "").split())
            previous = str(st.session_state.get(f"{box}_saved_comment") or "")
            if not text and not previous:
                return
            _take_result(box, bool(saver(text)), "That comment could not be saved. Please try again.")

        with st.form(f"{prefix}_comment_form", clear_on_submit=False, border=False):
            st.text_input(
                "Comment",
                max_chars=COMMENT_LIMIT,
                key=box_key,
                label_visibility="collapsed",
                placeholder="Add a short comment",
            )
            faces = []
            for index, emoticon in enumerate(COMMENT_EMOTICONS):
                extra = " take-face-poop" if index == 6 else ""
                faces.append(
                    f"<button type='button' class='take-face{extra}' "
                    f"data-face='{html.escape(emoticon, quote=True)}'>{html.escape(emoticon)}</button>"
                )
            st.html(
                f"<div class='take-faces' data-limit='{COMMENT_LIMIT}'>{''.join(faces)}</div>"
            )
            st.caption(
                f"Up to {COMMENT_LIMIT} characters. Tap one to add it. "
                "Posting again replaces yours. Each comment stays for 12 hours."
            )
            st.form_submit_button(
                "Post comment",
                key=f"{prefix}_comment_post",
                use_container_width=True,
                on_click=_post_comment,
            )


def _sentiment_alt_score(kind: str, asset_id: str, sentiment_at, mine_score, selected, prefix: str, on_vote) -> None:
    """Score controls under Disagree. A click saves, then only this box redraws."""
    del kind, asset_id, sentiment_at
    st.markdown("**Your score**")
    typed_key = f"{prefix}_alt_typed"

    def _pick(value: int, saver=on_vote, box=prefix, typed=typed_key) -> None:
        st.session_state[typed] = int(value)
        _take_result(box, bool(saver(-1, int(value))), "That thumb could not be saved. Please try again.")

    def _typed(saver=on_vote, box=prefix, typed=typed_key) -> None:
        raw = st.session_state.get(typed)
        if raw is None:
            return
        _take_result(box, bool(saver(-1, int(raw))), "That thumb could not be saved. Please try again.")

    for column, value in zip(st.columns(6, gap="xxsmall", wrap=False), (0, 20, 40, 60, 80, 100)):
        with column:
            st.button(
                str(value),
                key=f"{prefix}_alt_{value}",
                use_container_width=True,
                type="primary" if selected == value else "secondary",
                on_click=_pick,
                args=(value,),
            )
    if typed_key not in st.session_state and mine_score is not None:
        st.session_state[typed_key] = int(mine_score)
    number_kwargs = {
        "min_value": 0,
        "max_value": 100,
        "step": 1,
        "key": typed_key,
        "placeholder": "0–100",
        "on_change": _typed,
    }
    if typed_key not in st.session_state:
        number_kwargs["value"] = None
    st.number_input("Your score", label_visibility="collapsed", **number_kwargs)


def _published_label(value) -> str:
    """Turn an RSS pubDate into a calendar date. Empty when the feed omitted one."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    when = None
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError, OverflowError):
        when = None
    if when is None and len(raw) >= 10:
        try:
            when = datetime.strptime(raw[:10], "%Y-%m-%d")
        except ValueError:
            when = None
    if when is None:
        return ""
    return f"{when.strftime('%b')} {when.day}, {when.year}"


def headline_table(headlines: list, score_label: str = "Score") -> str:
    """Article, the date, a one-sentence AI summary, then the score. A dash until a summary exists."""
    sheet = " class='headline-ai'" if score_label != "Score" else ""
    rows = [
        "<div class='headline-head'>"
        "<div class='headline-title'>Article</div>"
        "<div class='headline-date'>Published</div>"
        "<div class='headline-note'>AI Summary</div>"
        f"<div class='headline-score'>{html.escape(score_label)}</div>"
        "</div>"
    ]
    for item in headlines:
        source = (
            f"<span class='headline-source'> — {html.escape(item['source'])}</span>"
            if item.get("source") else ""
        )
        published = _published_label(item.get("published"))
        published_html = html.escape(published) if published else "<span class='headline-empty'>—</span>"
        note = " ".join(str(item.get("note") or "").split())
        note_html = html.escape(note) if note else "<span class='headline-empty'>—</span>"
        rows.append(
            "<div class='headline-row'>"
            "<div class='headline-title'>"
            f"<a href='{html.escape(item['link'], quote=True)}' target='_blank' rel='noopener noreferrer'>"
            f"{html.escape(item['title'])}</a>{source}</div>"
            f"<div class='headline-date'>{published_html}</div>"
            f"<div class='headline-note'>{note_html}</div>"
            f"<div class='headline-score'>{sentiment_badge(item.get('score'))}</div></div>"
        )
    return f"<div{sheet} style='margin-top:10px;'>{''.join(rows)}</div>"


def _sentiment_story(report, coverage: str, score, color, background, arrow, note: str) -> str:
    """The score card shared by an asset and the two market sentiments."""

    def side_note(name, text, label_color):
        cleaned = " ".join(str(text or "").split())
        if not cleaned:
            return ""
        return (
            "<div class='sentiment-side'>"
            f"<div class='sentiment-side-label' style='color:{label_color};'>{name}</div>"
            f"<div class='sentiment-body'>{html.escape(cleaned)}</div>"
            "</div>"
        )

    drivers = "".join(
        f"<li>{html.escape(str(driver))}</li>"
        for driver in (report.get("drivers") or [])
    )
    drivers_html = f"<ul class='sentiment-drivers'>{drivers}</ul>" if drivers else ""
    sides = side_note("Positive", report.get("positive"), "#15803d") + side_note(
        "Negative", report.get("negative"), "#b91c1c"
    )
    summary = html.escape((report or {}).get("summary") or "")
    return (
        "<div class='sentiment-card'>"
        f"<div class='sentiment-kicker'>{html.escape(note)}</div>"
        f"<div class='sentiment-score' style='background:{background};color:{color};'>"
        f"{arrow} {score:.0f}/100</div>"
        f"<div class='sentiment-coverage' style='color:{color};'>{html.escape(coverage)}</div>"
        f"<div class='sentiment-body'>{summary}</div>"
        f"{drivers_html}{sides}</div>"
    )


def _mood_coverage(score: float) -> str:
    if score >= 60:
        return "Bullish coverage"
    if score >= 53:
        return "Mildly bullish coverage"
    if score >= 47:
        return "Mixed coverage"
    if score >= 40:
        return "Mildly bearish coverage"
    return "Bearish coverage"


def _reading_articles(group: dict) -> list[dict]:
    """One public reading in the same shape as a news headline row."""
    articles = []
    for item in group.get("items") or []:
        link = str(item.get("href") or "")
        if not link.startswith("https://"):
            continue
        name = str(item.get("name") or "Reading")
        value = str(item.get("value") or "").strip()
        source = str(item.get("source") or "")
        if name.startswith("Michigan"):
            source = "Michigan"
        elif name.startswith("CBOE"):
            source = "CBOE"
        articles.append({
            "title": f"{name}, {value}" if value else name,
            "source": source,
            "published": item.get("published") or "",
            "link": link,
            "note": item.get("note") or item.get("detail") or "",
            "score": item.get("score"),
        })
    return articles


def _article_box(box_key: str, body: str) -> None:
    """Articles, summaries, and scores in the same rounded frame as Your take."""
    if not str(body or "").strip():
        return
    with st.container(border=True, key=f"article_box_{box_key}"):
        st.html(f"<div class='article-sheet'>{body}</div>")


def _mood_reading_board(market_key: str, label: str, report: dict | None) -> str:
    """The three reading groups, as article rows, above the Google headlines."""
    groups = (report or {}).get("gauges") if isinstance(report, dict) else None
    if not groups:
        try:
            groups = market_gauge_groups(market_key)
        except Exception:
            groups = []
    blocks = []
    for group in groups or []:
        articles = _reading_articles(group)
        note = str(group.get("note") or "").strip()
        if not articles and not note:
            continue
        title = f"<div class='headline-group'>{html.escape(str(group.get('title') or ''))}</div>"
        table = headline_table(articles, "AI Score") if articles else ""
        aside = f"<div class='headline-aside'>{html.escape(note)}</div>" if note else ""
        blocks.append(title + table + aside)
    return "".join(blocks)


def _mood_card(spec: dict, row: dict | None) -> None:
    """One whole-market card. The background job replaces a saved score. A missing one is written once."""
    key = spec["key"]
    label = spec["label"]
    query = spec["query"]
    cache_key = f"mood:{key}"
    report, stored_at = sentiment_from_row(row)
    if not (report and report.get("ok")):
        flag = f"mood_fill_{key}"
        if not st.session_state.get(flag):
            with st.spinner(f"Reading the {label.lower()}..."):
                report = analyze_market_mood(key, label, query, sentiment_ready())
            if report.get("reason") != "model_busy":
                st.session_state[flag] = True
            if report.get("ok"):
                stored_at = time.time()
                if save_market_mood(supabase, key, query, report, stored_at):
                    row = dict(row or {})
                    row["sentiment_updated_at"] = datetime.fromtimestamp(
                        stored_at, timezone.utc
                    ).isoformat()
                    st.session_state["_shared_reread"] = True
    if report and stored_at is not None:
        remember_sentiment(cache_key, report, stored_at)
    head_col, top_col = st.columns([5.1, 0.85], vertical_alignment="center")
    with head_col:
        mood_icon = "🪙" if key == "crypto" else "📈"
        st.markdown(
            _section_mark(_emoji_mark(mood_icon), label),
            unsafe_allow_html=True,
        )
    with top_col:
        _back_to_top(key=f"mood_top_{key}")
    headlines = newest_first((report or {}).get("headlines") or [])
    score = (report or {}).get("score")
    _paint_section_score(f"mood_{key}", score, bool(report and report.get("ok") and score is not None))
    if report and report.get("ok") and score is not None:
        color, background, arrow, _bar = tone(score)
        note = (
            "Average of the news article scores below, from the last 7 days"
            if any(item.get("score") is not None for item in headlines)
            else "Score for these headlines, from the last 7 days"
        )
        score_card, vote_card = st.columns([3.5, 2.1], vertical_alignment="top")
        with score_card:
            st.markdown(
                _sentiment_story(report, _mood_coverage(score), score, color, background, arrow, note),
                unsafe_allow_html=True,
            )
        with vote_card:
            mood_key = spec["key"]
            _sentiment_thumbs(
                "Mood",
                mood_key,
                (row or {}).get("sentiment_updated_at") if isinstance(row, dict) else None,
                label,
                score,
                report.get("summary") or "",
                prefix=f"mood_{mood_key}",
                on_vote=lambda vote, alt_score=None, market=mood_key, at=(
                    (row or {}).get("sentiment_updated_at") if isinstance(row, dict) else None
                ): _store_mood_vote(market, at, vote, alt_score),
                on_comment=lambda text, market=mood_key, at=(
                    (row or {}).get("sentiment_updated_at") if isinstance(row, dict) else None
                ), answered=score, answered_summary=report.get("summary") or "": _store_sentiment_comment(
                    "Mood", market, at, text, answered, answered_summary,
                ),
            )
    elif (report or {}).get("reason") == "missing_key":
        st.info("Headlines are in. Add an xAI API key so Grok can score them.")
    elif (report or {}).get("reason") == "no_headlines":
        st.info("No recent headlines turned up for this market.")
    elif (report or {}).get("reason") == "model_busy":
        st.info("Grok is busy right now. The score will be tried again in about a minute.")
    elif (report or {}).get("reason") == "bad_key":
        st.warning("The xAI API key was rejected. Check the key in the Streamlit secrets.")
    else:
        st.info("The market score could not be built this time.")
    _article_box(f"mood_{key}_readings", _mood_reading_board(key, label, report if isinstance(report, dict) else None))
    if headlines:
        _article_box(f"mood_{key}_news", headline_table(headlines, "AI Score"))
    st.caption(
        "The rows above the Google headlines are public readings, each scored on its own. "
        "The score at the top is the average of the news article scores. "
        "This is not the technical score, and it is not advice."
    )


def show_market_moods(trade_crypto: bool = True, trade_equities: bool = True) -> None:
    """Crypto market, then the stock market. Each uses the asset sentiment layout."""
    stored = load_market_moods(supabase)
    if stored is None:
        with section_expander("🌤️ Market sentiment", "market_mood"):
            st.info("Market sentiment storage is not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor.")
        return
    for spec in MACRO_MOODS:
        if spec["key"] == "crypto" and not trade_crypto:
            continue
        if spec["key"] == "stock" and not trade_equities:
            continue
        mood_icon = "🪙" if spec["key"] == "crypto" else "📈"
        st.html(
            f"<div id='market-mood-{spec['key']}' style='scroll-margin-top:4.5rem;'></div>"
        )
        with section_expander(f"{mood_icon} Market sentiment - {spec['label']}", f"market_mood_{spec['key']}"):
            _mood_card(spec, stored.get(spec["key"]))


def _price_text(value: float) -> str:
    if value >= 1000:
        return f"{value:,.0f}"
    if value >= 1:
        return f"{value:,.2f}"
    return f"{value:.4f}"


def _liquidation_snapshots(asset_id, count: int = 2) -> list[dict]:
    """The latest saved liquidation snapshots for one coin, newest first."""
    try:
        return (
            supabase.table("liquidation_history")
            .select("recorded_at, price, longs, shorts")
            .eq("asset_key", asset_market_key("Crypto", asset_id))
            .order("recorded_at", desc=True)
            .limit(count)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def _level_change(side_rows_before, price: float, usd: float) -> str:
    """How a level's amount moved since the last update. A level within 1% counts as the same one."""
    best = None
    for row in side_rows_before or []:
        before = _number_or_none(row.get("price"))
        if before and abs(before - price) / price <= 0.01:
            if best is None or abs(before - price) < abs(best[0] - price):
                best = (before, _number_or_none(row.get("usd")) or 0.0)
    if best is None:
        return "new"
    change = usd - best[1]
    if abs(change) < 0.005 * max(usd, 1.0):
        return "same"
    return ("+" if change > 0 else "−") + _short_usd(abs(change))


def show_leverage(kind: str, asset_id: str, label: str) -> None:
    """Estimated liquidation levels and the leverage data behind them, for the coin on the chart."""
    heading = f"🔥 Leverage & liquidations - {label}" if label else "🔥 Leverage & liquidations"
    with section_expander(heading, "leverage"):
        if kind != "Crypto":
            st.caption("Leverage and liquidation data covers crypto futures. Pick a coin on the chart to see it.")
            return
        record = _liquidation_record(asset_id)
        if not record or record.get("status") != "ok":
            st.caption(_liquidation_caption(record))
            return
        series = record.get("series") or {}
        price = _number_or_none(record.get("price"))
        stamps = pd.to_datetime(series.get("t") or [], unit="s", utc=True)

        def latest(name):
            values = [v for v in series.get(name) or [] if v is not None]
            return values[-1] if values else None

        def day_ago(name):
            values = series.get(name) or []
            return values[-25] if len(values) >= 25 else None

        # The headline numbers.
        oi_now, oi_then = latest("oi"), day_ago("oi")
        funding_now = latest("funding")
        ratio_now = latest("ls")
        long_24 = sum(v or 0 for v in (series.get("liq_long") or [])[-24:])
        short_24 = sum(v or 0 for v in (series.get("liq_short") or [])[-24:])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Open interest", _short_usd(oi_now) if oi_now else "—",
            f"{(oi_now / oi_then - 1) * 100:+.1f}% in 24h" if oi_now and oi_then else None,
            help="The value of all open futures positions on Binance, Bybit and OKX. Rising means new money is betting.",
        )
        c2.metric(
            "Funding rate", f"{funding_now:+.4f}%" if funding_now is not None else "—",
            help=(
                "What one side pays the other to hold its position, each funding period. Positive: longs pay shorts, "
                "so traders lean long. Negative: shorts pay longs. Large either way is a sign of a crowded side."
            ),
        )
        c3.metric(
            "Long/short ratio", f"{ratio_now:.2f}" if ratio_now else "—",
            help="Accounts holding longs for each account holding shorts. Above 1 means more traders are long.",
        )
        c4.metric(
            "Liquidated, 24h", f"{_short_usd(long_24 + short_24)}",
            f"longs {_short_usd(long_24)} · shorts {_short_usd(short_24)}", delta_color="off",
            help="Positions actually force-closed in the last 24 hours, longs and shorts.",
        )

        # The ladder: estimated levels as bars either side of the price.
        snapshots = _liquidation_snapshots(asset_id, 2)
        before = snapshots[1] if len(snapshots) > 1 else {}
        rows = []
        for side, colour in (("shorts", "#22c55e"), ("longs", "#ef4444")):
            for level in record.get(side) or []:
                level_price, usd = _number_or_none(level.get("price")), _number_or_none(level.get("usd"))
                if not level_price or not usd:
                    continue
                rows.append({
                    "side": side, "colour": colour, "price": level_price, "usd": usd,
                    "gap": (level_price / price - 1) * 100 if price else None,
                    "change": _level_change(before.get(side), level_price, usd) if before else "—",
                })
        rows.sort(key=lambda row: row["price"], reverse=True)
        # Stacked, not side by side: in the narrow right-hand column a side-by-side table lost
        # its amount and change columns.
        ladder_col, table_col = st.container(), st.container()
        with ladder_col:
            st.markdown("**Estimated liquidation levels**")
            if rows:
                ladder = go.Figure(go.Bar(
                    x=[row["usd"] for row in rows],
                    y=[f"{row['price']:,.4g}" for row in rows],
                    orientation="h",
                    marker_color=[row["colour"] for row in rows],
                    hovertext=[
                        f"{'Shorts' if row['side'] == 'shorts' else 'Longs'} near {row['price']:,.4g}: "
                        f"about {_short_usd(row['usd'])}" for row in rows
                    ],
                    hoverinfo="text",
                ))
                ladder.update_layout(
                    height=320, margin=dict(t=10, b=10, l=10, r=10), showlegend=False,
                    yaxis=dict(type="category", autorange="reversed", title=None),
                    xaxis=dict(title="Estimated USD"),
                )
                _paint_chart(ladder)
                st.plotly_chart(ladder, width="stretch")
                st.caption(
                    f"Price now {price:,.4g}. Green bars above are shorts that would be force-closed if the price "
                    "rose there; red bars below are longs if it fell. The longer bar is the more crowded side."
                    if price else ""
                )
        with table_col:
            st.markdown("**Levels and changes**")
            table = pd.DataFrame([
                {
                    "Side": "▲ Shorts" if row["side"] == "shorts" else "▼ Longs",
                    "Price": f"{row['price']:,.4g}",
                    "From price": f"{row['gap']:+.1f}%" if row["gap"] is not None else "—",
                    "Amount": _short_usd(row["usd"]),
                    "Since last": row["change"],
                }
                for row in rows
            ])
            if not table.empty:
                st.table(table.set_index("Side"))
            st.caption("Since last: change since the previous update, about an hour ago. New is a level that was not there.")

        # Seven days of the inputs, hour by hour.
        if len(stamps):
            trend = make_subplots(
                rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                row_heights=[0.34, 0.22, 0.22, 0.22],
                subplot_titles=("Price and open interest", "Long/short ratio", "Funding rate (%)", "Liquidated per hour"),
                specs=[[{"secondary_y": True}], [{}], [{}], [{}]],
            )
            trend.add_trace(go.Scatter(x=stamps, y=series.get("price"), name="Price", line=dict(color="#f97316", width=1.6)), row=1, col=1)
            trend.add_trace(go.Scatter(x=stamps, y=series.get("oi"), name="Open interest", line=dict(color="#6366f1", width=1.4)), row=1, col=1, secondary_y=True)
            trend.add_trace(go.Scatter(x=stamps, y=series.get("ls"), name="Long/short", line=dict(color="#0ea5e9", width=1.4)), row=2, col=1)
            trend.add_hline(y=1, line_dash="dot", line_color="gray", opacity=0.5, row=2, col=1)
            trend.add_trace(go.Bar(
                x=stamps, y=series.get("funding"), name="Funding",
                marker_color=["#22c55e" if (v or 0) >= 0 else "#ef4444" for v in series.get("funding") or []],
            ), row=3, col=1)
            trend.add_trace(go.Bar(x=stamps, y=[-(v or 0) for v in series.get("liq_long") or []], name="Longs liquidated", marker_color="#ef4444"), row=4, col=1)
            trend.add_trace(go.Bar(x=stamps, y=series.get("liq_short"), name="Shorts liquidated", marker_color="#22c55e"), row=4, col=1)
            trend.update_layout(
                height=720, barmode="relative", showlegend=True,
                legend=dict(orientation="h", yref="container", y=0, yanchor="bottom", xref="paper", x=0, xanchor="left"),
                margin=dict(t=40, b=80, l=10, r=10),
            )
            trend.update_yaxes(title_text="Price", row=1, col=1)
            trend.update_yaxes(title_text="USD", row=1, col=1, secondary_y=True, showgrid=False)
            _paint_chart(trend)
            st.plotly_chart(trend, width="stretch")
            st.caption(
                "Rising open interest with a rising price means new money is buying in; rising open interest with a "
                "falling price means new shorts. A ratio far above 1, or funding far from zero, means one side is "
                "crowded, which is when liquidations can cascade. In the bottom panel, red bars below the line are "
                "longs force-closed that hour and green bars above are shorts."
            )
        st.caption(_liquidation_caption(record))


def show_max_pain(kind: str, asset_id: str, label: str, chart_price: float | None) -> None:
    """Options max pain for the open asset. A positioning chart, not part of the score."""
    force = bool(st.session_state.pop("max_pain_force", False))
    heading = f"🎯 Max pain - {label}" if label else "🎯 Max pain"
    with section_expander(heading, "max_pain"):
        market = options_market(kind, asset_id)
        if not market:
            st.caption(
                "This asset has no listed options chain here. "
                "Max pain is available for stocks, Bitcoin, and Ethereum."
            )
            return
        expiries, error = list_expiries(market, force=force)
        labels = dict(expiries)
        if labels:
            expiry_key = f"max_pain_expiry_{market}"
            if st.session_state.get(expiry_key) not in labels:
                # Start on the nearest expiry after today. On its last day a stock option
                # often shows no open interest at all, so today's makes a blank default.
                today_iso = datetime.now(timezone.utc).date().isoformat()
                later = [item for item in labels if str(item) > today_iso]
                st.session_state[expiry_key] = later[0] if later else next(iter(labels))
            expiry = st.selectbox(
                "Expiry",
                list(labels),
                format_func=lambda item: labels[item],
                key=f"max_pain_expiry_{market}",
            )
        else:
            expiry = None
        if error:
            st.warning(error)
            return
        if not expiry:
            st.caption("No listed expiries for this asset right now.")
            return
        calls, puts, underlying, chain_error = load_open_interest(
            market, expiry, force=force and market.startswith("stock:"),
        )
        if chain_error:
            st.warning(chain_error)
            return
        if not calls and not puts:
            st.caption(
                "This expiry shows no open interest. On an option's last day the data source often "
                "reports none, so pick a later expiry above."
            )
            return
        total_open = sum(calls.values()) + sum(puts.values())
        if market.startswith("stock:") and total_open < 100:
            # A handful of contracts (often on an option's last day) gives a meaningless answer.
            st.caption(
                f"This expiry has only {total_open:,.0f} open contracts, too few for a meaningful max pain. "
                "Pick a later expiry above."
            )
            return
        level = pain_strike(calls, puts)
        spot = underlying if underlying else chart_price
        spot_name = "Index" if underlying else "Latest price"
        price_col, pain_col, expiry_col = st.columns(3)
        price_col.metric(spot_name, _price_text(spot) if spot else "—")
        pain_col.metric("Max pain", _price_text(level) if level is not None else "—")
        expiry_col.metric("Expiry", labels.get(expiry, expiry))
        shown = window_strikes(list(calls) + list(puts), spot, level)
        full_count = len(set(calls) | set(puts))
        fig = go.Figure()
        fig.add_bar(
            x=shown,
            y=[calls.get(strike, 0.0) for strike in shown],
            name="Calls",
            marker_color="#15803d",
        )
        fig.add_bar(
            x=shown,
            y=[puts.get(strike, 0.0) for strike in shown],
            name="Puts",
            marker_color="#b91c1c",
        )
        if level is not None:
            fig.add_vline(x=level, line_dash="dash", line_color="#7c3aed", line_width=2)
        if spot:
            fig.add_vline(x=spot, line_dash="dot", line_color="#f59e0b", line_width=2)
        whole = all(float(strike).is_integer() for strike in shown)
        fig.update_layout(
            barmode="group",
            height=460,
            margin=dict(t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis_title="Open interest",
            xaxis_title="Strike",
        )
        fig.update_xaxes(tickformat="," if whole else ",.2f")
        _paint_chart(fig)
        st.plotly_chart(fig, width="stretch")
        if spot and level is not None and spot != 0:
            gap = (level - spot) / spot * 100
            side = "above" if gap > 0 else "below"
            st.caption(
                f"Max pain is {abs(gap):.1f}% {side} the {spot_name.lower()}. "
                "The violet line is that strike. The orange line is the price."
            )
        else:
            st.caption("The violet line is max pain. The orange line is the price.")
        if len(shown) < full_count:
            st.caption("The bars are the strikes nearest the price. Max pain is calculated from the full chain.")
        st.caption(
            "This is where open contracts would be worth the least at expiry. "
            "It is not a price target, and it is not part of the technical score. "
            "Open interest is contracts for stocks, and coin amount for Bitcoin and Ethereum."
        )


def _sentiment_points(subject_key: str) -> list[tuple[str, float]]:
    """Saved sentiment readings for one market or asset. Empty when history is not ready."""
    try:
        response = (
            supabase.table("sentiment_history")
            .select("score, recorded_at")
            .eq("subject_key", subject_key)
            .order("recorded_at")
            .execute()
        )
    except Exception:
        return []
    points = []
    for row in response.data or []:
        day = str(row.get("recorded_at") or "")[:10]
        try:
            score = float(row.get("score"))
        except (TypeError, ValueError):
            continue
        if day and score == score:
            points.append((day, score))
    return points


def _live_sentiment_point(row) -> tuple[str, float] | None:
    """The score already on screen, on the day it was saved."""
    report, stored_at = sentiment_from_row(row)
    if not report or stored_at is None:
        return None
    try:
        score = float(report.get("score"))
    except (TypeError, ValueError):
        return None
    if score != score:
        return None
    day = datetime.fromtimestamp(stored_at, timezone.utc).strftime("%Y-%m-%d")
    return day, score


def _sentiment_series(subject_key: str, row) -> list[tuple[str, float]]:
    """History plus the current saved score, so the latest reading still shows."""
    points = _sentiment_points(subject_key)
    live = _live_sentiment_point(row)
    if live is not None:
        points.append(live)
    return points


def _lead_label(value, reliable: bool | None = None) -> str:
    """Signed lead. A dagger marks a lead too thin to tell from chance."""
    if value is None:
        return "—"
    mark = "" if reliable is None or reliable else "†"
    return f"{value:+.2f}{mark}"


def show_signal_evidence(kind: str, asset_id: str, shown: str) -> None:
    """How the technical score has actually lined up with later price for this asset."""
    from evidence import load_evidence

    record = load_evidence(supabase, asset_market_key(kind, asset_id))
    if not record:
        st.info(
            f"The long-run test for {shown} has not been prepared yet. The background worker adds it "
            "within a few minutes of an asset being watched, then refreshes it daily. Check back soon."
        )
        return
    if record.get("too_short"):
        st.info(
            f"{shown} does not have enough price history to test yet. The test needs about two and a half "
            "years of daily prices."
        )
        return
    verdict = record.get("verdict") or {}
    level = verdict.get("level", "none")
    reverse = bool(verdict.get("reverse"))
    if level == "holds" and not reverse:
        st.success("Held up in this test. Still not a forecast: check it on similar assets.")
    elif level == "holds" and reverse:
        st.warning("Held up in reverse: high scores were followed by weaker prices.")
    elif level == "hint":
        st.warning("A faint hint at one time frame. Not enough to rely on.")
    else:
        st.info("No evidence the score has helped for this asset.")

    st.write(record.get("ai_text") or record.get("text") or "")

    rows = []
    for horizon, info in (record.get("horizons") or {}).items():
        high, low = info.get("high") or {}, info.get("low") or {}

        def move(bucket):
            if not bucket.get("n"):
                return "no cases"
            excess = bucket.get("excess")
            tail = "" if excess is None else f" ({excess:+.2f}% vs an average day)"
            thin = " - few cases" if (bucket.get("effective_n") or 0) < 10 else ""
            return f"{bucket['n']} days{tail}{thin}"

        ic, noise = info.get("ic"), info.get("noise")
        rows.append({
            "Next": f"{horizon} day" + ("" if str(horizon) == "1" else "s"),
            "Link to later price": "n/a" if ic is None else f"{ic:+.2f}",
            "Chance level": "n/a" if noise is None else f"±{noise:.2f}",
            "High scores": move(high),
            "Low scores": move(low),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(
        "Link to later price runs from -1 to +1. Anything inside the chance level cannot be told apart from luck. "
        "High and low scores are compared with an average day because most assets drift one way over time."
    )
    from evidence import volatility_text
    from funding import funding_text

    typical = volatility_text(record)
    if typical:
        st.write(typical)
    crowding = funding_text(record.get("funding"))
    if crowding:
        st.write(crowding)
    factors = verdict.get("factors") or []
    if factors:
        st.caption(
            "Parts of the score that cleared the chance level at two or more time frames: "
            + ", ".join(str(item) for item in factors)
            + ". With this many comparisons that is worth a closer look, not proof."
        )
    strategy = record.get("strategy") or {}
    if strategy.get("strategy_return_pct") is not None and strategy.get("buy_hold_return_pct") is not None:
        st.caption(
            f"Holding only while the score was high returned {strategy['strategy_return_pct']:+.0f}% "
            f"against {strategy['buy_hold_return_pct']:+.0f}% for buy and hold, after costs and with a one-day delay "
            f"(in the market {strategy.get('exposure_pct') or 0:.0f}% of days)."
        )
    st.caption(
        f"Daily prices from {record.get('first_scored', '?')} to {record.get('asof', '?')} "
        f"({record.get('scored_days', 0)} days). Tested without looking ahead. "
        "A description of the past, not advice and not a forecast."
    )


def show_signal_matrix(kind: str, asset_id: str, label: str, indicated, weights: dict) -> None:
    """Price across 30 days, with each signal set on those same dates."""
    from signal_matrix import LEAD_HORIZONS, MATRIX_DAYS, boundary_lines, build_matrix, weekend_edges

    shown = " ".join(str(label or "").split()) or "Selected asset"
    with section_expander(f"▦ Signal matrix - {shown}", "signal_matrix"):
        if indicated is None or getattr(indicated, "empty", True):
            st.caption("Price history is not ready for this asset yet.")
            return
        section = st.radio(
            "Signal view",
            ["Recent 30 days", "Evidence"],
            horizontal=True,
            label_visibility="collapsed",
            key="signal_matrix_section",
        )
        if section == "Evidence":
            show_signal_evidence(kind, asset_id, shown)
            return
        view = st.radio(
            "Matrix display",
            ["Lines", "Numbers"],
            horizontal=True,
            label_visibility="collapsed",
            key="signal_matrix_view",
        )
        horizon = st.radio(
            "Lead window",
            list(LEAD_HORIZONS),
            format_func=lambda days: f"Next {days} day" if days == 1 else f"Next {days} days",
            horizontal=True,
            key="signal_matrix_horizon",
        )
        sets = [("TA score", weights or {})]
        for stored_name, plain in (
            ("📊 Trend Following", "Trend Following"),
            ("📉 Mean Reversion", "Mean Reversion"),
            ("🚀 Momentum Heavy", "Momentum Heavy"),
        ):
            sets.append((plain, built_in_profiles.get(stored_name) or {}))
        for name, saved in (custom_profiles or {}).items():
            if name in built_in_profiles or not isinstance(saved, dict):
                continue
            sets.append((str(name), saved))
        market_key = "crypto" if kind == "Crypto" else "stock"
        asset_key = asset_market_key(kind, asset_id)
        moods = load_market_moods(supabase) or {}
        asset_row = (st.session_state.get("_shared_rows") or {}).get(asset_key)
        if not isinstance(asset_row, dict):
            asset_row = (load_shared_market(supabase, [asset_key]) or {}).get(asset_key)
        sentiment = {
            "Market sentiment": _sentiment_series(market_key, moods.get(market_key)),
            "Asset sentiment": _sentiment_series(asset_key, asset_row),
        }
        matrix = build_matrix(indicated, sets, sentiment, int(horizon), MATRIX_DAYS)
        dates = matrix["dates"]
        if len(dates) < 2:
            st.caption("Not enough daily prices yet to draw this matrix.")
            return
        st.caption(
            f"The last {len(dates)} daily closes, then each signal on those same dates. "
            f"Lead is how closely that signal lined up with the price change over the next {int(horizon)} "
            + ("day" if int(horizon) == 1 else "days")
            + ". Positive means a high score came before a rise. "
            + "A blank sentiment day is before the first saved reading. After that, the last saved score stays until the next one. "
            + "The 30-day record in the table below counts every signal the same way, using your bullish and bearish boundaries. "
            + "† marks a lead that is too thin to tell from chance. Price changes over the next few days overlap, "
            + "so 30 days holds far fewer independent observations than it looks."
        )
        rows = matrix["rows"]
        plot_rows = list(rows)
        if view == "Numbers":
            head = "".join(
                f"<th style='padding:4px 6px;font-weight:600;white-space:nowrap;'>{html.escape(day[5:])}</th>"
                for day in dates
            )
            body = []
            price_cells = "".join(
                f"<td style='padding:4px 6px;text-align:right;white-space:nowrap;'>{close:,.2f}</td>"
                for close in matrix["closes"]
            )
            body.append(
                "<tr><td style='padding:4px 8px;font-weight:600;white-space:nowrap;'>Price</td>"
                f"<td style='padding:4px 6px;text-align:right;'>—</td>{price_cells}</tr>"
            )
            for row in plot_rows:
                cells = []
                for value in row["values"]:
                    shown_value = "—" if value is None else f"{value:.0f}"
                    cells.append(
                        "<td style='padding:4px 6px;text-align:right;white-space:nowrap;'>"
                        f"{shown_value}</td>"
                    )
                body.append(
                    "<tr><td style='padding:4px 8px;font-weight:600;white-space:nowrap;'>"
                    f"{html.escape(row['name'])}</td>"
                    f"<td style='padding:4px 6px;text-align:right;white-space:nowrap;'>{_lead_label(row.get('lead'), row.get('reliable'))}</td>"
                    f"{''.join(cells)}</tr>"
                )
            st.markdown(
                "<div style='width:100%;overflow-x:auto;'><table style='border-collapse:collapse;font-size:0.8rem;'>"
                "<thead><tr><th style='padding:4px 8px;text-align:left;'>Signal</th>"
                "<th style='padding:4px 6px;text-align:right;'>Lead</th>"
                f"{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>",
                unsafe_allow_html=True,
            )
        else:
            count = 1 + len(plot_rows)
            fig = make_subplots(
                rows=count,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.012,
                row_heights=[0.22] + [0.78 / max(len(plot_rows), 1)] * len(plot_rows),
                subplot_titles=["Price"] + [row["name"] for row in plot_rows],
            )
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=matrix["closes"],
                    mode="lines",
                    name="Price",
                    line=dict(color="#2563eb", width=2),
                ),
                row=1,
                col=1,
            )
            palette = ["#15803d", "#d97706", "#7c3aed", "#0891b2", "#b45309", "#0f766e", "#be123c", "#4f46e5"]
            for index, row in enumerate(plot_rows):
                sentiment_row = row["name"] in ("Market sentiment", "Asset sentiment")
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=row["values"],
                        mode="lines+markers" if sentiment_row else "lines",
                        name=row["name"],
                        line=dict(color=palette[index % len(palette)], width=1.6),
                        marker=dict(size=6) if sentiment_row else None,
                        connectgaps=False,
                    ),
                    row=index + 2,
                    col=1,
                )
                fig.update_yaxes(range=[0, 100], row=index + 2, col=1)
            fig.update_layout(
                height=180 + 78 * len(plot_rows),
                showlegend=False,
                margin=dict(t=28, b=24, l=8, r=8),
            )
            fig.update_annotations(font_size=12)
            guide = "#6b7280" if _active_theme() == "dark" else "#9ca3af"
            for day in weekend_edges(dates):
                fig.add_shape(
                    type="line",
                    x0=day,
                    x1=day,
                    y0=0,
                    y1=1,
                    xref="x",
                    yref="paper",
                    line=dict(color=guide, width=1, dash="dot"),
                    layer="below",
                )
            fig.update_xaxes(showgrid=False)
            _paint_chart(fig)
            st.plotly_chart(fig, width="stretch")
        ranked = sorted(
            [row for row in rows if row.get("lead") is not None and row.get("reliable")],
            key=lambda row: abs(row["lead"]),
            reverse=True,
        )
        rank_of = {row["name"]: index + 1 for index, row in enumerate(ranked)}
        try:
            bull_line = float(alert_prefs.get("min_score_alert", 70))
        except (TypeError, ValueError):
            bull_line = 70.0
        try:
            bear_line = float(alert_prefs.get("max_score_alert", 30))
        except (TypeError, ValueError):
            bear_line = 30.0
        summary = []
        for row in rows:
            values = row.get("values") or []
            present = sum(value is not None for value in values)
            if present == 0:
                lines = ["No saved readings in this window yet."]
            else:
                lines = boundary_lines(values, matrix["closes"], bull_line, bear_line)
                quiet = all(" of " not in line for line in lines)
                if quiet and row["name"] in ("Market sentiment", "Asset sentiment"):
                    crossed = any(
                        value is not None and (value >= bull_line or value <= bear_line)
                        for value in values
                    )
                    if crossed:
                        lines.append(
                            "A saved score crossed your boundary, but no later price is in this window yet."
                        )
                    else:
                        day_word = "day" if present == 1 else "days"
                        lines.append(
                            f"The saved score covers {present} {day_word} in this window "
                            "and stayed between your bearish and bullish boundaries."
                        )
            record = "<br>".join(html.escape(line) for line in lines)
            summary.append(
                f"<tr><td style='padding:4px 8px;vertical-align:top;white-space:nowrap;'>{html.escape(row['name'])}</td>"
                f"<td style='padding:4px 8px;text-align:right;vertical-align:top;white-space:nowrap;'>{rank_of.get(row['name'], '—')}</td>"
                f"<td style='padding:4px 8px;text-align:right;vertical-align:top;white-space:nowrap;'>{_lead_label(row.get('lead'), row.get('reliable'))}</td>"
                f"<td style='padding:4px 8px;vertical-align:top;width:100%;'>{record}</td></tr>"
            )
        st.markdown(
            "<div style='width:100%;'><table style='width:100%;border-collapse:collapse;font-size:0.9rem;margin-top:8px;'>"
            "<thead><tr><th style='padding:4px 8px;text-align:left;white-space:nowrap;'>Signal</th>"
            "<th style='padding:4px 8px;text-align:right;white-space:nowrap;'>Rank</th>"
            "<th style='padding:4px 8px;text-align:right;white-space:nowrap;'>Lead</th>"
            "<th style='padding:4px 8px;text-align:left;width:100%;'>30-day record</th></tr></thead>"
            f"<tbody>{''.join(summary)}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        effective = [row.get("effective_n") for row in rows if row.get("effective_n")]
        if effective:
            st.caption(
                f"About {max(effective):.0f} independent observations per signal at this window. "
                "Only leads that clear the noise level for that count are ranked. "
                "Read the record beside the all-days figure: a rising asset is higher most days whatever the score says. "
                "This is a lookback. It does not change the technical score or alerts."
            )


def show_market_sentiment(kind: str, asset_id: str, label: str, ticker: str | None):
    """Headline sentiment for the asset on the chart. Shared for 12 hours."""
    query = sentiment_query(kind, label, ticker)
    stored = load_shared_market(supabase, [asset_market_key(kind, asset_id)]).get(
        asset_market_key(kind, asset_id)
    )
    report, stored_at = sentiment_from_row(stored)
    if report and stored_at is not None:
        remember_sentiment(query, report, stored_at)
    st.html("<div id='market-sentiment' style='scroll-margin-top:4.5rem;'></div>")
    shown_name = " ".join((label or "").split())
    if kind == "Stock" and ticker and ticker.upper() not in shown_name.upper():
        shown_name = f"{shown_name} ({ticker})" if shown_name else ticker
    sentiment_heading = (
        f"📰 Market sentiment - {shown_name}" if shown_name else "📰 Market sentiment"
    )
    sentiment_logo = (stored or {}).get("logo_url") if isinstance(stored, dict) else ""
    if not sentiment_logo:
        sentiment_logo = (st.session_state.get("asset_logos") or {}).get(asset_market_key(kind, asset_id))
    with section_expander(sentiment_heading, "market_sentiment_panel"):
        mark_col, sentiment_top = st.columns([5.2, 0.85], vertical_alignment="center")
        with mark_col:
            if shown_name:
                st.markdown(
                    _section_mark(
                        asset_logo(sentiment_logo, shown_name, size=32),
                        _ticker_label(kind, asset_id, shown_name),
                    ),
                    unsafe_allow_html=True,
                )
        with sentiment_top:
            _back_to_top(key="sentiment_back_to_top")
        if not (report and report.get("ok")):
            flag = f"sentiment_fill_{asset_market_key(kind, asset_id)}"
            if not st.session_state.get(flag):
                with st.spinner("Reading recent headlines..."):
                    report = analyze_market_sentiment(query, sentiment_ready())
                if report.get("reason") != "model_busy":
                    st.session_state[flag] = True
                if report.get("ok"):
                    stored_at = time.time()
                    save_sentiment(supabase, kind, asset_id, report, stored_at)
                    remember_sentiment(query, report, stored_at)
                    stored = dict(stored or {})
                    stored["sentiment_updated_at"] = datetime.fromtimestamp(
                        stored_at, timezone.utc
                    ).isoformat()
                    st.session_state["_shared_reread"] = True
        report = report or {}
        headlines = newest_first(report.get("headlines") or [])
        score = report.get("score")
        _paint_section_score("asset", score, bool(report.get("ok") and score is not None))
        if report.get("ok") and score is not None:
            color, background, arrow, _bar = tone(score)
            note = (
                "Average of the article scores below, from the last 7 days"
                if any(item.get("score") is not None for item in headlines)
                else "Score for these headlines, from the last 7 days"
            )
            sentiment_at = (stored or {}).get("sentiment_updated_at") if isinstance(stored, dict) else None
            score_card, vote_card = st.columns([3.5, 2.1], vertical_alignment="top")
            with score_card:
                st.markdown(
                    _sentiment_story(report, _mood_coverage(score), score, color, background, arrow, note),
                    unsafe_allow_html=True,
                )
            with vote_card:
                _sentiment_thumbs(
                    kind, asset_id, sentiment_at, shown_name or asset_id, score, report.get("summary") or "",
                )
        elif report.get("reason") == "missing_key":
            st.info("Headlines are in. Add an xAI API key so Grok can score them. See the README under Market sentiment.")
        elif report.get("reason") == "no_headlines":
            st.info("No recent headlines turned up for this asset.")
        elif report.get("reason") == "model_busy":
            st.info("Grok is busy right now. The articles are below, and the score will be tried again in about a minute.")
        elif report.get("reason") == "bad_key":
            st.warning("The xAI API key was rejected. Check the key in the Streamlit secrets.")
        else:
            st.info("The sentiment score could not be built this time. The articles are below.")

        if headlines:
            asset_key = "".join(ch if ch.isalnum() else "_" for ch in f"{kind}_{asset_id}").strip("_") or "asset"
            _article_box(f"asset_{asset_key}", headline_table(headlines))
        st.caption("This reads recent coverage. It is not the technical score, and it is not advice.")


_ASSET_PICK_JS = """
export default function(component) {
  const { setTriggerValue, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  window.__angstromPickAsset = setTriggerValue;
}
"""
_asset_pick = st.components.v2.component(
    "alert_asset_pick",
    js=_ASSET_PICK_JS,
    isolate_styles=False,
)


def _mark_clicked_alert_read(raw: str) -> str:
    """Record a clicked alert as read. Returns the asset pick that came with it, or ""."""
    note_id, pick = "", raw
    if raw.startswith("read|"):
        note_id, pick = raw.split("|", 1)[1], ""
    elif "|note:" in raw:
        pick, note_id = raw.rsplit("|note:", 1)
    if note_id.isdigit():
        try:
            (
                supabase.table("user_notifications")
                .update({"is_read": True})
                .eq("user_id", user_id)
                .eq("id", int(note_id))
                .execute()
            )
        except Exception:
            pass
    return pick


def _take_alert_pick() -> None:
    """An alert click names an asset. This pass draws that chart. It does not run again."""
    reported = _asset_pick(key="alert_asset_pick", on_picked_change=lambda: None)
    raw = str(getattr(reported, "picked", "") or "")
    if "|" not in raw or st.session_state.get("_alert_pick_seen") == raw:
        return
    raw_full, raw = raw, _mark_clicked_alert_read(raw)
    if not raw:
        st.session_state["_alert_pick_seen"] = raw_full
        return
    kind_name, asset_id = raw.split("|")[:2]
    quiet = raw.endswith("|quiet")
    if kind_name == "Crypto":
        chosen = CRYPTO_WATCHLIST
    elif kind_name == "Stock":
        chosen = STOCK_WATCHLIST
    else:
        return
    if asset_id not in chosen:
        return
    st.session_state["_alert_pick_seen"] = raw_full
    st.session_state.chart_pick = (kind_name, asset_id)
    st.session_state.chart_pick_from_row = True
    st.session_state.asset_type = kind_name
    if kind_name == "Crypto":
        st.session_state.asset_crypto = asset_id
    else:
        st.session_state.asset_stock = asset_id
    if quiet:
        return
    st.session_state.scroll_target = "interactive-chart"
    st.session_state.scroll_token = str(time.time_ns())
    _remember_section("interactive_chart", True)


@st.fragment(run_every="30s")
def render_social_popout(crypto_watchlist, stock_watchlist) -> None:
    """The social stream and chat on a page of their own, for a second window."""
    pairs = [("Crypto", asset_id) for asset_id in crypto_watchlist]
    pairs += [("Stock", asset_id) for asset_id in stock_watchlist]
    keys = [asset_market_key(kind, asset_id) for kind, asset_id in pairs]
    shared = load_shared_market(supabase, keys)
    logos = _asset_logos(crypto_watchlist, stock_watchlist, shared)
    feed = sentiment_comment_lists(supabase, keys, every=True)
    st.session_state["social_stream"] = _social_stream_json(
        crypto_watchlist, stock_watchlist, shared, logos, feed
    )
    saved_scope = (prefs.get("settings") or {}).get("stream_asset")
    scope = saved_scope if saved_scope in ("watchlist", "crypto", "stock") else ""
    try:
        stream_items = json.loads(st.session_state.get("social_stream") or "[]")
    except (TypeError, json.JSONDecodeError):
        stream_items = []
    if not isinstance(stream_items, list):
        stream_items = []
    stream_state = _draw_social_stream(stream_items, scope, popout=True)
    _handle_stream_events(stream_state)


def _keep_handoff_fresh() -> None:
    """The main tab hands over a new access token when it renews its own. Use it here too."""
    reported = _handoff_ask(
        key="handoff_ask",
        data={"current": str(st.session_state.get("access_token") or "")},
        on_token_change=lambda: None,
        on_none_change=lambda: None,
    )
    token = str(getattr(reported, "token", "") or "")
    if token and token != st.session_state.get("access_token"):
        try:
            member = supabase.auth.get_user(token).user
        except Exception:
            member = None
        if member is not None:
            # Same person: a renewed login. Someone else: this tab switches to them.
            st.session_state.user = member
            st.session_state.access_token = token
            st.rerun()


if _POPOUT_VIEW == "social":
    _keep_handoff_fresh()
    remember_favourites()
    render_social_popout(CRYPTO_WATCHLIST, STOCK_WATCHLIST)
    st.stop()

if _POPOUT_VIEW:
    _keep_handoff_fresh()
else:
    _handoff_host(key="handoff_host", data={"access": str(st.session_state.get("access_token") or "")})
    _popout_buttons(
        key="popout_buttons",
        data={
            "ids": list(_POPOUT_SECTION_IDS),
            "asWindow": bool(st.session_state.get("popouts_as_window", True)),
            "fold": bool(st.session_state.get("popouts_fold_section", True)),
        },
    )
remember_favourites()
_take_alert_pick()
if _POPOUT_VIEW:
    _asset_follow(key="asset_follow", data={"quiet": False})
else:
    # A pick made in a pop-out reaches the main page too.
    _asset_follow(key="asset_follow", data={"quiet": True})

render_dashboard(
    CRYPTO_WATCHLIST,
    STOCK_WATCHLIST,
    days_history,
    current_weights,
    show_reasons,
    show_extra_metrics,
    show_period_changes,
    trade_crypto,
    trade_equities,
)
if _POPOUT_VIEW:
    st.stop()
_record_run("whole page", _RUN_STARTED)
if str((load_profile() or {}).get("role") or "") == "admin":
    admin_panel()
_page_top(key="page_back_to_top")

st.markdown(
    "<div style='margin-top:2.5rem;padding-top:1rem;border-top:1px solid #e5e7eb;"
    "text-align:center;color:#6b7280;font-size:0.8rem;'>"
    "© 2026 Angstrom Signals. All rights reserved."
    "</div>",
    unsafe_allow_html=True,
)

st.sidebar.markdown("---")
st.sidebar.info("Prices are saved about every 5 minutes, and market sentiment about every 12 hours, for every account. This page reads those saved results. Alert checks use the same prices and continue after you leave.")
