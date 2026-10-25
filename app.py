"""
Crypto & Equity Signals Dashboard
Run with: streamlit run app.py
"""

import base64
from contextlib import nullcontext
import html
import io
import json
import re
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

st.set_page_config(
    page_title="angstrom signals",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
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
  const { parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  let style = document.getElementById("angstrom-brand-style");
  if (style && style.dataset.layout !== "jump") {
    style.remove();
    style = null;
  }
  if (!style) {
    style = document.createElement("style");
    style.id = "angstrom-brand-style";
    style.dataset.layout = "jump";
    style.textContent = [
      "html{--ang-surface:#ffffff;--ang-border:#e5e7eb;--ang-text:#111827;--ang-muted:#6b7280;--ang-soft:#374151;--ang-track:#e5e7eb;--ang-line:#f3f4f6;--ang-select:#e5e7eb;--ang-select-text:#111827;}",
      "html.angstrom-night{--ang-surface:#262730;--ang-border:#3f4654;--ang-text:#f3f4f6;--ang-muted:#9ca3af;--ang-soft:#d1d5db;--ang-track:#3f4654;--ang-line:#31333f;--ang-select:#3a4050;--ang-select-text:#f9fafb;}",
      ".ang-card{background:var(--ang-surface);color:var(--ang-text);border:1px solid var(--ang-border);border-radius:10px;padding:12px 16px;}",
      ".ang-kicker{font-size:.8rem;color:var(--ang-muted);margin-bottom:4px;}",
      ".ang-copy{color:var(--ang-text);font-size:.95rem;line-height:1.4;}",
      ".ang-title{color:var(--ang-text);font-weight:600;}",
      ".ang-track{flex:1;background:var(--ang-track);border-radius:6px;height:14px;overflow:hidden;}",
      ".ang-table{width:100%;border-collapse:collapse;font-size:.95rem;color:var(--ang-text);}",
      ".ang-table thead tr{border-bottom:2px solid var(--ang-border);}",
      ".ang-table tbody tr{border-bottom:1px solid var(--ang-line);}",
      ".ang-table tr.ang-row-on{background:var(--ang-select);color:var(--ang-select-text);}",
      "html:not(.angstrom-night) [data-testid='stAppViewContainer'],html:not(.angstrom-night) [data-testid='stHeader']{background:#eef0f4 !important;}",
      "html:not(.angstrom-night) [data-testid='stSidebar']{background:#ffffff !important;border-right:1px solid #e5e7eb;}",
      "html:not(.angstrom-night) [data-testid='stMain'] [data-testid='stExpander'] details,html:not(.angstrom-night) [data-testid='stMain'] [data-testid='stVerticalBlockBorderWrapper'],html:not(.angstrom-night) [data-testid='stMain'] [data-testid='stForm']{background:#ffffff !important;border-color:#e5e7eb !important;}",
      "html:not(.angstrom-night) [data-testid='stSidebar'] [data-testid='stExpander'] details{background:#f8fafc !important;border-color:#e5e7eb !important;}",
      "html.angstrom-night [data-testid='stAppViewContainer'],html.angstrom-night [data-testid='stHeader'],html.angstrom-night [data-testid='stBottom']{background:#0e1117 !important;}",
      "html.angstrom-night [data-testid='stSidebar']{background:#16181f !important;border-right:1px solid var(--ang-border);}",
      "html.angstrom-night [data-testid='stMain'] [data-testid='stExpander'] details,html.angstrom-night [data-testid='stMain'] [data-testid='stVerticalBlockBorderWrapper'],html.angstrom-night [data-testid='stMain'] [data-testid='stForm'],html.angstrom-night [data-testid='stMetric']{background:var(--ang-surface) !important;border-color:var(--ang-border) !important;}",
      "html.angstrom-night [data-testid='stSidebar'] [data-testid='stExpander'] details{background:#262730 !important;border-color:var(--ang-border) !important;}",
      "html.angstrom-night [data-testid='stExpander'] details > summary{background:transparent !important;}",
      "html.angstrom-night [data-baseweb='input'],html.angstrom-night [data-baseweb='textarea'],html.angstrom-night [data-baseweb='select'] > div,html.angstrom-night [data-testid='stFileUploaderDropzone']{background-color:#31333f !important;border-color:var(--ang-border) !important;color:var(--ang-text) !important;}",
      "html.angstrom-night [data-baseweb='input'] input,html.angstrom-night [data-baseweb='textarea'] textarea{background:transparent !important;color:var(--ang-text) !important;-webkit-text-fill-color:var(--ang-text);}",
      "html.angstrom-night [data-testid='stBaseButton-secondary']{background:#31333f !important;border-color:#4b5563 !important;color:var(--ang-text) !important;}",
      "html.angstrom-night [data-testid='stBaseButton-secondary']:hover{border-color:#e5e7eb !important;color:#ffffff !important;}",
      "button.angstrom-jump{display:block;width:100%;box-sizing:border-box;min-height:2.5rem;height:auto;padding:0.4rem 0.75rem;border-radius:0.5rem;border:1px solid rgba(49,51,63,0.2);background:#ffffff;color:#31333f;font:inherit;line-height:1.35;text-align:center;cursor:pointer;white-space:normal;}",
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
  let layoutStyle = document.getElementById("angstrom-layout-controls");
  if (layoutStyle && layoutStyle.dataset.layout !== "pill") {
    layoutStyle.remove();
    layoutStyle = null;
  }
  if (!layoutStyle) {
    layoutStyle = document.createElement("style");
    layoutStyle.id = "angstrom-layout-controls";
    layoutStyle.dataset.layout = "pill";
    const singleMark = "url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27%3E%3Crect x=%272.4%27 y=%272.4%27 width=%2719.2%27 height=%2719.2%27 fill=%27none%27 stroke=%27black%27 stroke-width=%272%27/%3E%3C/svg%3E')";
    const wideMark = "url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27%3E%3Crect x=%272.4%27 y=%272.4%27 width=%2719.2%27 height=%2719.2%27 fill=%27none%27 stroke=%27black%27 stroke-width=%272%27/%3E%3Cpath d=%27M2.4 9.1H21.6M12 9.1V21.6%27 fill=%27none%27 stroke=%27black%27 stroke-width=%272%27/%3E%3C/svg%3E')";
    layoutStyle.textContent = [
      "[class*='st-key-layout_single'],[class*='st-key-layout_wide'],[class*='st-key-open_all_sections'],[class*='st-key-collapse_all_sections']{width:fit-content !important;max-width:max-content !important;flex:0 0 auto !important;}",
      ".st-key-layout_single button,.st-key-layout_wide button{position:relative;width:2.05rem !important;height:2.05rem !important;min-height:2.05rem !important;padding:0 !important;border-radius:.4rem !important;display:inline-flex !important;align-items:center;justify-content:center;font-size:0 !important;line-height:0 !important;color:#111827 !important;background:#fff !important;border:1px solid rgba(49,51,63,.28) !important;box-shadow:none !important;}",
      ".st-key-layout_single button > *,.st-key-layout_wide button > *{position:absolute !important;width:1px !important;height:1px !important;overflow:hidden !important;clip:rect(0,0,0,0) !important;}",
      ".st-key-layout_single button::before,.st-key-layout_wide button::before{content:'';position:absolute;left:50%;top:50%;width:15px;height:15px;transform:translate(-50%,-50%);background:currentColor;-webkit-mask:var(--mark) center / contain no-repeat;mask:var(--mark) center / contain no-repeat;}",
      ".st-key-layout_single button{--mark:" + singleMark + ";}",
      ".st-key-layout_wide button{--mark:" + wideMark + ";}",
      ".st-key-layout_single button:hover,.st-key-layout_wide button:hover{border-color:#111827 !important;}",
      ".st-key-layout_single button[data-testid='stBaseButton-primary'],.st-key-layout_wide button[data-testid='stBaseButton-primary']{background:#111827 !important;color:#fff !important;border-color:#111827 !important;}",
      "html.angstrom-night .st-key-layout_single button,html.angstrom-night .st-key-layout_wide button{background:#262730 !important;color:#fafafa !important;border-color:#4b5563 !important;}",
      "html.angstrom-night .st-key-layout_single button:hover,html.angstrom-night .st-key-layout_wide button:hover{border-color:#e5e7eb !important;}",
      "html.angstrom-night .st-key-layout_single button[data-testid='stBaseButton-primary'],html.angstrom-night .st-key-layout_wide button[data-testid='stBaseButton-primary']{background:#f3f4f6 !important;color:#111827 !important;border-color:#f3f4f6 !important;}",
      ".st-key-open_all_sections button,.st-key-collapse_all_sections button{width:auto !important;min-width:0 !important;max-width:max-content !important;height:2.05rem !important;min-height:2.05rem !important;padding:0 .7rem !important;white-space:nowrap;font-size:.85rem !important;}",
      "[data-testid='stElementContainer']:not(:has([data-testid='stElementContainer'])):is(:has(#interactive-chart),:has(#market-mood-crypto),:has(#market-mood-stock),:has(#market-sentiment)),[class*='st-key-scroll_to_chart'],[class*='st-key-wide_column_split']{position:absolute !important;width:0 !important;height:0 !important;min-height:0 !important;margin:0 !important;padding:0 !important;overflow:visible !important;}",
      "#angstrom-wide-split{position:absolute;z-index:30;width:12px;margin-left:-6px;top:0;cursor:col-resize;touch-action:none;}",
      "#angstrom-wide-split .grip{position:absolute;top:50%;left:4px;width:4px;height:48px;margin-top:-24px;border-radius:999px;background:#9ca3af;}",
      "#angstrom-wide-split:hover .grip,#angstrom-wide-split.is-dragging .grip{background:#111827;}",
      "html.angstrom-night #angstrom-wide-split .grip{background:#6b7280;}",
      "html.angstrom-night #angstrom-wide-split:hover .grip,html.angstrom-night #angstrom-wide-split.is-dragging .grip{background:#e5e7eb;}",
      "#interactive-chart,#market-mood-crypto,#market-mood-stock,#market-sentiment{height:0;margin:0;padding:0;scroll-margin-top:4.5rem;}"
    ].join("");
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
  }
  return () => {};
}
"""
_brand_watch = st.components.v2.component(
    "brand_watch",
    js=_BRAND_JS,
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
  const openAndScroll = (targetId) => {
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
  host.querySelectorAll("button[data-pick]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      button.blur();
      const pick = button.getAttribute("data-pick") || "";
      if (pick.indexOf("mood|") === 0) {
        openAndScroll("market-mood-" + pick.split("|")[1]);
        return;
      }
      const parts = pick.split("|");
      const already = parts.length === 2 && Array.from(
        document.querySelectorAll("tr.ang-row-on button[data-pick]")
      ).some((el) => (el.getAttribute("data-pick") || "") === pick);
      if (already) {
        openAndScroll("interactive-chart");
        return;
      }
      if (button.hasAttribute("data-alert") && window.__angstromPickAsset) {
        window.__angstromPickAsset("picked", pick);
        return;
      }
      setTriggerValue("picked", pick);
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
      window.socialChatNotice = typeof parsed.notice === "string" ? parsed.notice : "";
      window.socialChatFaces = Array.isArray(parsed.faces) ? parsed.faces : [];
      window.socialChatLimit = Number(parsed.limit) || 160;
      account = String(parsed.account || "");
      panelPrefs = parsed.panel && typeof parsed.panel === "object" ? parsed.panel : {};
    }
  } catch (error) {
    items = [];
  }
  if (window.socialAccount !== account) {
    window.socialAccount = account;
    window.socialStreamState = null;
    const width = Number(panelPrefs.width);
    const split = Number(panelPrefs.split);
    window.socialPanelWidth = width >= 320 && width <= 900 ? Math.round(width) : 420;
    window.socialPanelSplit = split > 0.08 && split < 0.92 ? split : 0.5;
    window.socialPanelPinned = !!panelPrefs.pinned;
    const existing = document.getElementById("social-stream-root");
    if (existing) existing.remove();
  }
  window.socialStreamItems = items;
  window.socialStreamReport = setTriggerValue;
  installSocialStream(savedAsset);
  window.renderSocialStream();
  return () => {};

  function installSocialStream(savedAsset) {
    window.socialStreamState = window.socialStreamState || {
      open: false, side: "", asset: savedAsset || "", person: ""
    };
    if (typeof window.socialStreamState.pinned !== "boolean") {
      window.socialStreamState.pinned = !!window.socialPanelPinned;
    }
    let style = document.getElementById("social-stream-style");
    if (style && style.dataset.layout !== "score") {
      style.remove();
      style = null;
    }
    if (!style) {
      style = document.createElement("style");
      style.id = "social-stream-style";
      style.dataset.layout = "score";
      style.textContent = [
        "#social-stream-root{position:fixed;inset:0;z-index:10000000;pointer-events:none;}",
        "#social-stream-root.is-open{pointer-events:auto;}",
        "#social-stream-root.is-open.is-pinned{pointer-events:none;}",
        "#social-stream-root .scrim{position:absolute;inset:0;background:rgba(17,24,39,0.35);opacity:0;transition:opacity .2s ease;}",
        "#social-stream-root.is-open .scrim{opacity:1;}",
        "#social-stream-root.is-open.is-pinned .scrim{opacity:0;pointer-events:none;}",
        "#social-stream-root.is-open.is-pinned .panel,#social-stream-root.is-open.is-pinned .edge{pointer-events:auto;}",
        "#social-stream-root .panel{position:absolute;top:0;right:0;height:100%;width:min(var(--social-width,420px),100vw);background:#fff;color:#111827;box-shadow:-12px 0 40px rgba(17,24,39,.18);transform:translateX(100%);transition:transform .22s ease;display:flex;flex-direction:column;overflow:hidden;pointer-events:auto;}",
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
        "#social-stream-root .chat-notice{color:#b45309;font-size:.8rem;line-height:1.35;margin-bottom:6px;}",
        "#social-stream-root .card{padding:14px 0;border-top:1px solid #e5e7eb;}",
        "#social-stream-root .chat-filters{padding:8px 18px 0;}",
        "#social-stream-root .chat-filters .picks{grid-template-columns:1fr;margin-top:0;}",
        "#social-stream-root .person{display:flex;gap:10px;align-items:center;}",
        "#social-stream-root .person .identity{flex:1;min-width:0;}",
        "#social-stream-root .favourite{flex:none;margin-left:auto;background:none;border:0;padding:0 2px;cursor:pointer;font-size:1.2rem;line-height:1;color:#9ca3af;}",
        "#social-stream-root .favourite.is-on{color:#d97706;}",
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
        "#social-stream-root.is-dark .panel{background:#1c1f27;color:#fafafa;box-shadow:-12px 0 40px rgba(0,0,0,.45);}",
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
        "#social-stream-root.is-dark .chat-notice{color:#fbbf24;}"
      ].join("");
      document.head.appendChild(style);
    }
    let root = document.getElementById("social-stream-root");
    if (root && root.dataset.layout !== "titles") {
      root.remove();
      root = null;
    }
    if (!root) {
      if (window.socialStreamAbort) window.socialStreamAbort.abort();
      window.socialStreamAbort = new AbortController();
      const streamSignal = window.socialStreamAbort.signal;
      root = document.createElement("div");
      root.id = "social-stream-root";
      root.dataset.layout = "titles";
      root.innerHTML = [
        "<div class='scrim'></div>",
        "<aside class='panel' role='dialog' aria-label='Social signals and chat'>",
        "<div class='width-grip' role='separator' aria-orientation='vertical' title='Drag to resize the panel'></div>",
        "<div class='finder'><input id='panel-search' type='search' placeholder='Search the stream and the chat' aria-label='Search the stream and the chat'></div>",
        "<div class='stream-pane'>",
        "<header class='head'><div>",
        "<div class='kicker'>Social signals</div>",
        "<h2>Social signals stream</h2>",
        "</div><div class='head-actions'><button type='button' class='pin' title='Pin the panel'>Pin</button><button type='button' class='close'>Close</button></div></header>",
        "<div class='filters'><div class='chips'>",
        "<button type='button' data-side=''>All</button>",
        "<button type='button' data-side='positive'>Positive</button>",
        "<button type='button' data-side='negative'>Negative</button>",
        "<button type='button' data-side='mixed'>Mixed</button>",
        "</div><div class='picks'>",
        "<label>Asset<select id='stream-asset'></select></label>",
        "<label>Person<select id='stream-person'></select></label>",
        "</div></div>",
        "<div class='count'></div><div class='list'></div></div>",
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
          pinned: !!(window.socialStreamState && window.socialStreamState.pinned)
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
        const finderBox = root.querySelector(".finder");
        const chrome = (splitter ? splitter.offsetHeight : 0) + (finderBox ? finderBox.offsetHeight : 0);
        const height = panelBox ? panelBox.clientHeight - chrome : 0;
        applySplit(height ? heldRatio * height : 0);
      };
      fitSplit();
      window.addEventListener("resize", () => {
        applyWidth(Number(window.socialPanelWidth) >= 320 ? Number(window.socialPanelWidth) : 420);
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
      assets.sort((a, b) => String(a[1]).localeCompare(String(b[1])));
      people.sort((a, b) => a.localeCompare(b));
      fillStreamSelect(
        panel.querySelector("#stream-asset"),
        "All assets",
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
      const personChoices = [["me", "Me"], ["favourites", "Favourites"]];
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
      const list = panel.querySelector(".list");
      if (list) {
        const keptScroll = list.scrollTop;
        list.replaceChildren();
        if (!shown.length) {
          const empty = document.createElement("div");
          empty.className = "empty";
          empty.textContent = state.person === "me"
            ? "No comments from you yet."
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
    const total = document.createElement("span");
    total.textContent = String(Number(count) || 0);
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
    if (!window.socialStreamReport) return;
    window.socialStreamReport("favourite", JSON.stringify({ n: Date.now(), user: id, on: on }));
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

  function personRow(item) {
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
    const star = favouriteButton(item);
    if (star) person.appendChild(star);
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
    const person = personRow(item);
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
        : chatPerson === "favourites" && !favouriteSet().size && !String(query).trim()
        ? "No favourites yet. Press the star beside a name."
        : "No chat comments match.";
      list.appendChild(empty);
    } else {
      shownThreads.forEach((item) => list.appendChild(chatCard(item, item.id)));
    }
    const notice = panel.querySelector(".chat-notice");
    if (notice) {
      notice.hidden = !window.socialChatNotice;
      notice.textContent = window.socialChatNotice || "";
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
    const person = personRow(item);
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
    const person = personRow(item);
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
    "social_stream",
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
    if (details && details.hasAttribute("inert") && summary) summary.click();
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
  let style = document.getElementById("angstrom-page-top-style");
  if (!style) {
    style = document.createElement("style");
    style.id = "angstrom-page-top-style";
    style.textContent = [
      "#angstrom-page-top{position:fixed;right:1.25rem;bottom:1.25rem;z-index:1000;display:none;",
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
  const mainScroller = () => document.querySelector('[data-testid="stMain"]')
    || document.querySelector("section.main");
  const scrolled = () => {
    const main = mainScroller();
    const mainTop = main ? main.scrollTop : 0;
    return mainTop > 120 || window.scrollY > 120;
  };
  const sync = () => button.classList.toggle("is-on", scrolled());
  if (!button.dataset.bound) {
    button.dataset.bound = "1";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      const main = mainScroller();
      if (main) main.scrollTop = 0;
      window.scrollTo({top: 0, behavior: "auto"});
      sync();
    });
  }
  const watch = (target) => {
    if (!target || target.dataset.pageTopBound) return;
    target.dataset.pageTopBound = "1";
    target.addEventListener("scroll", sync, {passive: true});
  };
  watch(mainScroller());
  if (!window.angstromPageTopBound) {
    window.angstromPageTopBound = true;
    window.addEventListener("scroll", sync, {passive: true});
  }
  sync();
  return () => {
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
  const { parentElement, setTriggerValue } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const minSplit = 0.2;
  const maxSplit = 0.8;
  let handle = document.getElementById("angstrom-wide-split");
  if (!handle) {
    handle = document.createElement("div");
    handle.id = "angstrom-wide-split";
    handle.title = "Drag to resize these two columns";
    const grip = document.createElement("div");
    grip.className = "grip";
    handle.appendChild(grip);
  }
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
  if (!handle.dataset.bound) {
    handle.dataset.bound = "1";
    handle.addEventListener("pointerdown", (event) => {
      const found = pair();
      if (!found || stacked(found.columns) || event.button !== 0) return;
      event.preventDefault();
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
        place();
        setTriggerValue("split", ratio.toFixed(3));
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", stop);
      handle.addEventListener("pointercancel", stop);
    });
  }
  place();
  const retry = window.setInterval(place, 400);
  const stopRetry = window.setTimeout(() => window.clearInterval(retry), 8000);
  return () => {
    window.clearInterval(retry);
    window.clearTimeout(stopRetry);
    if (observer) observer.disconnect();
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
    if (left <= 0) button.textContent = title + " (update due)";
    else if (lead) button.textContent = title + " (" + lead + " " + clock + ")";
    else button.textContent = title + " (" + clock + ")";
    if (left <= 0 && token && window[timerKey + "_sent"] !== token) {
      window.clearInterval(window[timerKey]);
      window[timerKey + "_sent"] = token;
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

# Opening a section is only show and hide. This records that choice without
# asking Streamlit to rebuild the page.
_SECTION_TOGGLE_JS = """
export default function(component) {
  const { setTriggerValue, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  window.__angstromSetSection = setTriggerValue;
  if (window.__angstromSectionWatch) return;
  window.__angstromSectionWatch = true;
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!target || !target.closest) return;
    const summary = target.closest("summary");
    if (!summary) return;
    const expander = summary.closest('[data-testid="stExpander"]');
    if (!expander) return;
    let node = expander;
    let sectionId = "";
    while (node) {
      const names = typeof node.className === "string" ? node.className.split(" ") : [];
      const hit = names.find((name) => name.indexOf("st-key-sec_") === 0);
      if (hit) {
        sectionId = hit.slice("st-key-sec_".length);
        break;
      }
      node = node.parentElement;
    }
    if (!sectionId) return;
    window.setTimeout(() => {
      const details = expander.querySelector('[data-testid="stExpanderDetails"]');
      const opened = !!(details && !details.hasAttribute("inert"));
      const send = window.__angstromSetSection;
      if (send) send("toggle", sectionId + ":" + (opened ? "1" : "0"));
    }, 40);
  }, true);
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
  const search = new URLSearchParams(window.location.search);
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
    history.replaceState(null, "", window.location.pathname + (rest ? "?" + rest : "") + window.location.hash);
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

# Streamlit's own link button opens the address in a new tab, which drops the
# sign-in secret. This link stays in the same tab.
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
    link.target = "_self";
    shell.appendChild(link);
  }
  const url = data && data.url ? String(data.url) : "";
  const verifier = data && data.verifier ? String(data.verifier) : "";
  link.href = url || "#";
  link.onclick = () => {
    if (!verifier) return;
    try { sessionStorage.setItem("angstrom-pkce", verifier); } catch (err) {}
    try { localStorage.setItem("angstrom-pkce", verifier); } catch (err) {}
    const secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = "angstrom_pkce=" + encodeURIComponent(verifier) + "; Path=/; Max-Age=600; SameSite=Lax" + secure;
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
_MAIN_SECTION_IDS = (
    "quick_snapshot",
    "crypto_scores",
    "equity_scores",
    "interactive_chart",
    "score_breakdown",
    "market_mood",
    "market_mood_crypto",
    "market_mood_stock",
    "max_pain",
    "market_sentiment_panel",
)
_SECTION_IDS = _MAIN_SECTION_IDS + (
    "help_guides",
    "account",
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
    "feedback",
    "about",
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
        on_toggle_change=lambda: None,
    )
    raw = str(getattr(reported, "toggle", "") or "")
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


def section_expander(label: str, section_id: str):
    """A main-page section. Open all and Collapse all move every one of these together."""
    return tracked_expander(label, section_id, default=True)


def _reveal_section(section_id: str, anchor: str) -> None:
    """Open one section and scroll to it, without folding the others."""
    _remember_section(section_id, True)
    st.session_state.scroll_target = anchor
    st.session_state.scroll_token = str(time.time_ns())


try:
    from alerts import evaluate_alerts
    from data_fetchers import (
        crypto_logo_urls,
        crypto_market_caps,
        crypto_ticker,
        fetch_crypto_data,
        fetch_stock_data,
        find_crypto,
        format_market_cap,
        stock_logo_url,
        stock_market_caps,
        period_for_days,
        resolve_crypto_id,
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
        recent_closes,
        row_timestamp,
        save_logos,
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
            client.auth.set_session(access, refresh)
        except Exception:
            st.session_state.user = None
            st.session_state.access_token = None
            st.session_state.refresh_token = None
            client = create_client(url, key)
    return client


def clear_session():
    st.session_state.user = None
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.pop("cloud_prefs", None)
    st.session_state.pop("profile", None)
    st.session_state.pop("prefs_user", None)


# Widget values stay in the browser session after logout. The next person to
# sign in on that same page would otherwise see them and save them as their own.
_ACCOUNT_STATE_KEYS = (
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
    return "https://angstromsignalsmvp.streamlit.app"


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

if st.session_state.user is None:
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
            auth_tab1, auth_tab2 = st.tabs(["🔑 Log In", "📝 Sign Up"])

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
                    login_email = st.text_input("Email", key="login_email")
                    login_password = st.text_input("Password", type="password", key="login_password")
                    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                    if st.button("Log In", type="primary", use_container_width=True):
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
                                st.rerun()
                        except Exception:
                            st.error("Login failed. Check your email and password.")
                    if st.button("Forgot password?", use_container_width=True, key="forgot_password"):
                        st.session_state.recover_email = st.session_state.get("login_email", "")
                        st.session_state.show_recover = True
                        st.session_state.recover_sent = False
                        st.session_state.pop("recovery_error", None)
                        st.rerun()

            with auth_tab2:
                st.markdown("### Create New Account")
                signup_email = st.text_input("Email", key="signup_email")
                signup_password = st.text_input("Password", type="password", key="signup_password")
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                if st.button("Create Account", type="primary", use_container_width=True):
                    try:
                        supabase.auth.sign_up({
                            "email": signup_email,
                            "password": signup_password,
                        })
                        st.success("Account created. Confirm the email if required, then log in.")
                    except Exception:
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
            default_alerts = {
                "user_id": user_id,
                "enabled": True,
                "min_score_alert": 70,
                "max_score_alert": 30,
            }
            supabase.table("alert_preferences").insert(default_alerts).execute()
            prefs_dict["alerts"] = default_alerts

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
    }


def save_alert_preferences_to_cloud(updates: dict):
    try:
        supabase.table("alert_preferences").update(updates).eq("user_id", user_id).execute()
    except Exception as exc:
        st.error(f"Error saving alert preferences: {exc}")


def fetch_user_notifications():
    try:
        res = (
            supabase.table("user_notifications")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


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


def _clean_invite_email(value: str) -> str:
    """A lower-case email, or empty when the text is not an address."""
    text = " ".join(str(value or "").split()).lower()
    if text.count("@") != 1 or any(ch.isspace() for ch in text):
        return ""
    local, domain = text.split("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        return ""
    return text


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

_brand_watch(key="brand_watch")
st.sidebar.markdown(_brand_mark(150), unsafe_allow_html=True)

@st.fragment
def invite_someone() -> None:
    """Send one invite. This form redraws on its own."""
    st.caption("Invite your friends to join! Get 100 social points when they do!")
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


with tracked_expander("👤 Account", "account", sidebar=True):
    if profile is None:
        st.warning("Profile storage is not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor.")
        profile = {}
    st.markdown(profile_card(profile, st.session_state.user.email or ""), unsafe_allow_html=True)
    st.caption("A new post adds 5 to your social score. A reply adds 1.")
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
                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    feed_filter = st.radio(
                        "Filter",
                        ["Unread", "All"],
                        horizontal=True,
                        label_visibility="collapsed",
                        key="notif_filter_radio",
                    )
                with f_col2:
                    if st.button("Mark read", key="mark_read_btn", use_container_width=True):
                        try:
                            supabase.table("user_notifications").update({"is_read": True}).eq("user_id", user_id).execute()
                            _rerun_fragment()
                        except Exception:
                            st.error("Could not mark alerts as read.")

                filtered_notifs = (
                    [note for note in notifications_list if not note.get("is_read", False)]
                    if feed_filter == "Unread"
                    else notifications_list
                )

                if not filtered_notifs:
                    st.caption(f"No {feed_filter.lower()} notifications.")
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

                    asset_notes = [
                        note for note in filtered_notifs
                        if str(note.get("alert_type") or "") != "invite_joined"
                        and notification_target(note.get("asset_symbol"))
                    ]
                    if asset_notes:
                        st.caption("Click an alert to highlight that asset and open it on the chart.")
                    for note in filtered_notifs:
                        name = html.escape(str(note.get("asset_name") or "Asset"))
                        message = html.escape(str(note.get("message") or ""))
                        created = html.escape(str(note.get("created_at") or "")[:16].replace("T", " "))
                        weight = "700" if not note.get("is_read") else "500"
                        if str(note.get("alert_type") or "") == "invite_joined":
                            border = "#93c5fd" if not note.get("is_read") else "#e5e7eb"
                            card = (
                                "<div style='background:#f8fafc;border:1px solid "
                                f"{border};border-radius:8px;padding:8px 10px;margin-bottom:8px;'>"
                                f"<div style='font-weight:{weight};color:#1e3a8a;'>Invite accepted</div>"
                                f"<div style='font-size:0.8rem;color:#374151;margin-top:2px;'>{message}</div>"
                                f"<div style='font-size:0.75rem;color:#6b7280;margin-top:2px;'>{created}</div></div>"
                            )
                            _score_table(key=f"notif_{note.get('id') or name}", data=card)
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
                        if target:
                            kind_name, asset_id = target
                            pick_value = html.escape(f"{kind_name}|{asset_id}", quote=True)
                            card = (
                                f"<button type='button' data-alert='1' data-pick='{pick_value}' "
                                "style='display:block;width:100%;margin:0;padding:0;border:none;"
                                "background:transparent;text-align:left;cursor:pointer;font:inherit;color:inherit;'>"
                                f"{card}</button>"
                            )
                        _score_table(
                            key=f"notif_{note_id}",
                            data=card,
                        )

                    if st.button("🗑️ Clear Read Alerts", use_container_width=True, key="clear_read_btn"):
                        try:
                            supabase.table("user_notifications").delete().eq("user_id", user_id).eq("is_read", True).execute()
                            st.success("Cleared read alerts.")
                            _rerun_fragment()
                        except Exception as exc:
                            st.error(f"Could not clear alerts: {exc}")

        with tracked_expander("Configure Alert Rules", "alert_rules"):
            st.caption(
                "70 is a strong bullish setup. 30 is a strong bearish setup. "
                "An email is sent once when a score crosses a boundary, and again only after it leaves and crosses later."
            )
            alert_enabled = st.checkbox("Enable Alerts", value=alert_prefs.get("enabled", True), key="alert_enabled_cb")
            min_score = st.slider(
                "Bullish Alert Threshold (Score ≥)",
                50, 95, int(alert_prefs.get("min_score_alert", 70)),
                key="min_score_slider",
            )
            max_score = st.slider(
                "Bearish Alert Threshold (Score ≤)",
                5, 50, int(alert_prefs.get("max_score_alert", 30)),
                key="max_score_slider",
            )

            new_alert_settings = {
                "enabled": alert_enabled,
                "min_score_alert": min_score,
                "max_score_alert": max_score,
            }
            if new_alert_settings != {name: alert_prefs.get(name) for name in new_alert_settings}:
                alert_prefs.update(new_alert_settings)
                prefs["alerts"] = alert_prefs
                save_alert_preferences_to_cloud(new_alert_settings)


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
with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
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
        open_sections = st.button("Open all", key="open_all_sections", width="content")
        collapse_sections = st.button("Collapse all", key="collapse_all_sections", width="content")
        # A layout button on this same run must not win. Collapse all only folds
        # the sections, and the wide or single choice stays as it was.
        if open_sections or collapse_sections:
            closing = bool(collapse_sections)
            states = _section_map()
            for section_id in _MAIN_SECTION_IDS:
                states[section_id] = not closing
            if closing:
                states["help_guides"] = False
            save_account_settings({"sections": states})
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
remember_section_clicks()

with tracked_expander("📖 Help and guides", "help_guides", default=False):
    st.markdown("""
**Higher score = a more bullish setup.** Every score starts at 50 and each indicator adds or subtracts points. The result is kept between 0 and 100. This is a research tool, not financial advice.
""")
    bands = [
        ("Strong bullish", "70+", "#15803d", "#dcfce7"),
        ("Bullish", "60–69", "#15803d", "#dcfce7"),
        ("Neutral", "47–52", "#b45309", "#fef3c7"),
        ("Bearish", "30–39", "#b91c1c", "#fee2e2"),
        ("Strong bearish", "below 30", "#b91c1c", "#fee2e2"),
    ]
    band_cols = st.columns(len(bands))
    for column, (name, span, color, background) in zip(band_cols, bands):
        column.markdown(
            f"<div style='background:{background};color:{color};border-radius:8px;padding:12px 14px;'>"
            f"<div style='font-size:0.8rem;font-weight:600;'>{name}</div>"
            f"<div style='font-size:1.6rem;font-weight:700;line-height:1.2;'>{span}</div></div>",
            unsafe_allow_html=True,
        )
    st.caption("The same colors are used on the scores. Green is 53 and above. Amber is 47–52. Red is below 47.")

    left, right = st.columns(2)
    with left:
        st.markdown("""
**What moves the score** (at weight 1.0)

- **RSI** — oversold adds up to 8, overbought subtracts up to 8
- **Stochastic** — below 20 adds 5, above 80 subtracts 5
- **Moving averages** — 4 points for each of SMA 20, 50, and 200, added when price is above and subtracted when price is below
- **ADX** — a strong trend adds or subtracts 4, in the direction of the 50-day average
- **MACD** — up to 4 for the line versus zero, 3 for the signal cross, and 2 for the histogram
""")
    with right:
        st.markdown("""
**More factors**

- **Ichimoku** — 5 points for price versus the cloud, 3 for Tenkan versus Kijun
- **Bollinger Bands** — near the lower band adds 4, near the upper band subtracts 4
- **Volume** — a high-volume up bar adds 3, a high-volume down bar subtracts 3
- **OBV** — 3 points for whether volume flow is above or below its average
- **7-day move** — up to 4 points either way

Sidebar sliders scale each factor. Zero turns that factor off. Named sets save a slider mix to your account.
""")

    st.markdown("""
**How to use it**

1. Read the snapshot and the tables. The top row is the strongest technical score, the bottom is the weakest. Quick Snapshot, Market sentiment for crypto, Market sentiment for stocks, Crypto Scores, Equity Scores, Interactive Chart, Score Breakdown, Max pain, and Market sentiment each sit in a section that starts open. Close a header to fold that section away. **Open all** and **Collapse all**, on the right of the page title, do that for every one of those sections. The square beside them stacks every section in one column, with Quick Snapshot first. The mark with a wide top and two panes underneath puts Quick Snapshot and both score tables across the top, market sentiment on the left, and Interactive Chart, Score Breakdown, Max pain, and Market sentiment on the right. Those two bottom columns start at equal width. Drag the line between them to give either side more room. That line stays inside those two columns. The wide or single choice, that column split, the open asset, the social panel's width, split, and pin, and the open or collapsed state of each section are saved on your account and come back when you log in. On a narrow screen the wide layout stacks the left and right parts. **I trade cryptos**, **I trade equities**, and **I trade both**, in Settings, are saved on your account. A market you leave out is hidden, including its sentiment, its score table, and its Quick Snapshot boxes. The chart follows the markets you trade. Collapse all also closes this guide. Open all does not open it. **Feedback**, at the bottom of the sidebar, sends an issue or an idea. It is stored as submitted. The arrow on the left edge of the page closes the sidebar. It stays on that edge when the sidebar is closed, so the sidebar can be opened again. Hover the arrow to see which action it will take.
2. Click a name in either table, a Quick Snapshot box, or an alert under Notifications. That asset stays highlighted, and the page moves down to the chart when the chart is off screen. Click a column title to sort that table. It starts with the strongest score at the top.
3. Extra metrics add **7d %**, **Market Cap**, **ATR %**, and **Vol**. A separate checkbox adds **1d %** before the seven-day change and **30d %** after it. For **1d %** and **7d %**, green means the price rose and red means it fell. **30d %** uses the same colors as the **30-day trend**: green for a rise of about 2% or more, red for a fall of about 2% or more, and orange when the move stays inside about 2%. For stocks, one day is the previous trading session. **Market Cap** is the latest size of the asset, from CoinGecko for crypto and Yahoo for stocks. **ATR %** is volatility. **Vol** is volume versus its 20-day average.
4. Alerts fire at 70 and 30 unless you move those sliders. One email goes to the address on your account when a technical score crosses a boundary. It is not sent again until the score leaves that boundary and crosses it later. Sentiment scores do not send alerts.

**Market sentiment for crypto and stocks**

In the single column these two sections sit under Quick Snapshot, crypto first and then stocks. Quick Snapshot shows each one as the colored score box, the status, such as Mildly bullish coverage, and the short summary, for the markets you trade. The thumbs and the crowd's own score sit on the right. Click anywhere on that box to open that market's section. The public readings sit in a rounded box, in three groups, each with a one-sentence summary and its own score: liquidity and central banks, the dollar and yields, and crypto sentiment for crypto; policy and inflation, market breadth, and institutional feeds for stocks. The Google headlines follow in a second rounded box. On the selected asset, the articles sit in one box of the same kind. Each one uses the same layout as the asset sentiment under the chart: the score on the left, Your take on the right, then those reading rows, then the articles. Neither is an asset, and neither is added to the tables or the technical score. Each score is an average of recent headlines. The summary, the positive paragraph, and the negative paragraph can also use those public readings. Each article row also has a one-sentence AI Summary, after the date. A dash there means that score was saved before summaries. The next background update fills it in. It is stored once and shown to every account. A background update replaces it about every 12 hours. Until that update arrives, the last score stays on screen. Your take works the same way as on an asset: agree, disagree, a score from 0 to 100, and one short comment. A refresh of that market clears the thumbs and personal scores. A comment stays for 12 hours. The search wording can be tightened later.

**Max pain**

This sits under the chart, above Market sentiment, for the same open asset. It is the options strike where the open calls and puts would be worth the least at that expiry. Green bars are call open interest and red bars are put open interest. The violet line is that strike. The orange line is the price. It describes where contracts are parked. It is not a price target, it is not mixed into the technical score, and it does not send an alert. Stocks use the Yahoo options chain. Bitcoin and Ethereum use Deribit's public options book. Other coins have no chain here, so the section says so. The nearest expiry is selected, and another can be chosen. It keeps its own cache. The technical control in Quick Snapshot opens the chart and does not reload max pain.

**Market sentiment**

This sits under the chart. The heading names the open asset, for example **Market sentiment - Bitcoin (BTC)**. Grok reads headlines from the last 7 days and gives each one a score from 0 to 100. The newest headline is listed first. Beside each link is the date, then a one-sentence AI Summary, then the score. A dash in AI Summary means that score was saved before summaries. The next background update fills it in. The number at the top of the section is the average of those article scores. Under the short summary, **Positive** and **Negative** each add a paragraph drawn from those same headlines. Green, amber, and red use the same bands as the technical score. The two scores stay separate, and sentiment is not mixed into the technical score.

The **Sentiment** column shows that saved score in the same colored box. A dash means that asset has not been scored yet. Adding it to a watchlist writes the first score when nobody else has it stored, and the background update keeps it after that. The score is stored once and shown to every account. A background update replaces it about every 12 hours. Until that update arrives, the last score stays on screen.

**30-day trend**, at the far right of each row, is a small line of that same 30-day move. Its color matches the **30d %** column: green for a rise of about 2% or more, red for a fall of about 2% or more, and orange when the move stays inside about 2%. The same line is shared by every account.

**Watching**, beside the name, is how many accounts have that asset on a watchlist. The people marks are a count, not the names of those accounts.

The picture on the left of each name is that asset's logo. The same logo appears at the top of the Interactive Chart and the asset's Market sentiment, with the ticker in large type beside it, such as SUI. Crypto market and Stock market use a larger version of the icon on their section title, with Crypto market or Stock market beside it. Crypto logos come from CoinGecko. Stock logos come from Finnhub. A letter shows when a logo is not available. The address is saved once and reused for every account.

Beside the sentiment score you can press thumbs up if you agree, or thumbs down if you do not. Press the same thumb again to clear your take. Those buttons sit in an outlined box. After you disagree, scores appear in that same box, under the buttons: 0, 20, 40, 60, 80 and 100. The number you pick also fills the type box, and you can type any number from 0 to 100. It saves on its own when you click a score, press Enter, or leave the box. The thumbs and that same colored average sit at the bottom of Your take, and again under **Crowd** on each table row. The box is the average of the personal scores, in the same style as the Sentiment column. It updates when a score is clicked or typed. Hover the down thumb for the spread, which is how far those scores typically sit from the average. One score has no spread yet. A dash means nobody has given a personal score. Under the thumbs you can post one comment of up to 160 characters. A row of faces under the box can be added to the comment. A speech balloon appears beside the thumbs, and in the **Comments** column, once any comment exists. Click it, or the arrow on the right edge of the page, to open **Social signals and chat**, described below. A refresh of that sentiment clears every thumb and every personal score, because they belonged to the old score. A comment stays for 12 hours from when it was posted, and the stream keeps the sentiment it was answering even after a newer score arrives.

Click a sentiment score in the table to highlight that asset and jump to its headlines. **↑ Top** scrolls back to the top of the page. It sits at the top right of the Interactive Chart section, and at the top right of Market sentiment. Another **↑ Top** sits at the bottom right of the page once you have scrolled down.

The controls at the top of Quick Snapshot open a section. They do not start a refresh. Market Sentiment - Crypto opens the crypto market. Market Sentiment - Equities opens the stock market. A market you do not trade is left out. Market Sentiment - Selected Asset opens the sentiment for the asset on the chart. Technical Data - Selected Asset opens the chart. Each one shows the time until the next shared update, for example (update in 4:56:40). That clock is the same for every account. It counts from the last saved update. When it reaches zero the page reads the saved result again. It does not ask for a new one. If the background update is late, the last saved result stays on screen.

Prices for every asset on any watchlist are saved about every 5 minutes. This page turns those prices into a technical score with this account's own weights. Market sentiment for the crypto market, the stock market, and each of those assets is saved about every 12 hours. Both intervals are one shared setting. An asset that is not already stored is written when it is added, then the same schedule keeps it.

**Social signals and chat**

The arrow on the right edge of the page, or a speech balloon, opens a panel. The top half is the social signals stream. The bottom half is a general chat. Drag the gray bar between them to give either half more room. Drag the handle on the panel's left edge to make the panel wider or narrower. Close the panel with Close, the shaded area, or Escape. Pin, beside Close, keeps the panel open and leaves the rest of the page free to use. The shaded area and Escape no longer close it while it is pinned.

**Social signals stream**

Comments are newest first. Each one shows the person's picture, name, and the time, plus the sentiment they were answering. A note stays for 12 hours. A reply stays with that note for the same 12 hours.

All, Positive, Negative, and Mixed narrow the list by the coverage they were answering. Under Asset, All assets is every comment. My watchlists is the crypto and equity tables on your account. My Crypto Watchlist and My Equities Watchlist each show one of those lists. Crypto market and Stock market sit above the individual assets. All assets or a watchlist is saved on your account. You can also pick one asset.

Under Person, All people shows everyone. Me, just under that, shows notes you wrote, including a reply you wrote. Favourites shows notes from people you have starred, including a reply they wrote. A star beside another person's name adds them. Press the filled star to remove them. That list is saved on your account. You can also pick one person. A note stays in the list when that person wrote it or replied under it.

The green thumb and the red thumb each show a count. You can mark any note, including one you posted. Press the same thumb again to clear your mark. The curved arrow replies. The trash can deletes a note you posted, and deleting a comment also removes the replies under it.

**General chat**

This is a shared room, not tied to an asset. Notes are newest first, and they stay. The panel shows the newest 60 conversations, with the replies under each one. Older notes stay stored.

The Person list works the same way as on the stream, including Me and Favourites. Write a comment in the box at the bottom. Enter posts it. Shift and Enter starts a new line. The same row of faces sits under the box. The curved arrow replies. A reply to a reply is added under the original comment. Thumbs work the same way as on the stream, including on a note you posted, and the count sits beside each thumb. The trash can deletes a note you posted, and deleting a comment also removes the replies under it.

**Search**

One box at the top of the panel filters the stream and the chat together. It matches the words in a note or a reply, a person's name, or, on the stream, the asset. It searches the notes already on the panel, so it does not look through chat older than those 60 conversations.

**Alerts keep running in the background**

Prices are saved about every 5 minutes, and market sentiment about every 12 hours, whether or not this page is open. The page reads those saved results. Alert checks use the same prices and keep running after you close the page or log out.

- A crossing is saved on your account. It shows up under Notifications the next time you log in.
- The email goes only to you.
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
            st.caption("Add a ticker (XLM) or a name (Stellar).")
            new_crypto = st.text_input("Add crypto", key="new_crypto", placeholder="e.g. XLM or Stellar")
            if st.button("Add Crypto") and new_crypto:
                found = find_crypto(new_crypto)
                if not found:
                    st.warning(f"No coin found for '{new_crypto.strip()}'. Try the ticker, such as XLM, or the name, such as Stellar.")
                else:
                    cid, label = found
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
                        st.rerun()
            if CRYPTO_WATCHLIST:
                to_remove = st.selectbox("Remove crypto", [""] + list(CRYPTO_WATCHLIST.keys()), key="rm_crypto")
                if to_remove and st.button("Remove Crypto"):
                    CRYPTO_WATCHLIST.pop(to_remove, None)
                    prefs["crypto"] = CRYPTO_WATCHLIST
                    save_preferences_to_cloud({"crypto_watchlist": CRYPTO_WATCHLIST})
                    st.rerun()

    if trade_equities:
        with tracked_expander("Edit Stocks", "edit_stocks"):
            st.caption("Add by ticker (AAPL, MSFT, etc.)")
            new_stock = st.text_input("Add stock ticker", key="new_stock", placeholder="e.g. GOOGL")
            if st.button("Add Stock") and new_stock:
                tic = new_stock.strip().upper()
                if tic and tic not in STOCK_WATCHLIST:
                    STOCK_WATCHLIST[tic] = tic
                    prefs["stock"] = STOCK_WATCHLIST
                    save_preferences_to_cloud({"stock_watchlist": STOCK_WATCHLIST})
                    _ensure_added("Stock", tic, tic)
                    st.rerun()
            if STOCK_WATCHLIST:
                to_remove = st.selectbox("Remove stock", [""] + list(STOCK_WATCHLIST.keys()), key="rm_stock")
                if to_remove and st.button("Remove Stock"):
                    STOCK_WATCHLIST.pop(to_remove, None)
                    prefs["stock"] = STOCK_WATCHLIST
                    save_preferences_to_cloud({"stock_watchlist": STOCK_WATCHLIST})
                    st.rerun()

with tracked_expander("⚖️ Scoring Balance Weights", "weights", sidebar=True):
    st.caption("Adjust the relative importance of each indicator. Every slider changes the score.")

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
    st.radio("Markets you trade", _TRADE_CHOICES, key="trade_markets")
    days_history = st.slider("Days of history", 90, 365, key="days_history")
    show_reasons = st.checkbox("Show score breakdown", key="show_reasons")
    show_extra_metrics = st.checkbox(
        "Show extra metrics (7d, market cap, ATR, volume)",
        key="show_extra_metrics",
    )
    show_period_changes = st.checkbox(
        "Show 1-day and 30-day changes",
        key="show_period_changes",
    )

    save_account_settings({
        "days_history": int(days_history),
        "show_reasons": bool(show_reasons),
        "show_extra_metrics": bool(show_extra_metrics),
        "show_period_changes": bool(show_period_changes),
        "trade_crypto": bool(trade_crypto),
        "trade_equities": bool(trade_equities),
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
    payload = {
        "from": sender,
        "to": [address],
        "subject": "You are invited to Angstrom Signals",
        "html": (
            f"<p>{safe_name} invited you to Angstrom Signals.</p>"
            f"<p><a href=\"{link}\">Create an account</a> with this email address.</p>"
            "<p>Angstrom Signals is market sentiment and technical signals, with the crowd alongside. "
            "It is research, not financial advice.</p>"
        ),
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


@st.cache_data(ttl=300)
def load_crypto(coin_id, days, nonce):
    del nonce
    return fetch_crypto_data(coin_id, days)


@st.cache_data(ttl=300)
def load_stock(ticker, days, nonce):
    del nonce
    return fetch_stock_data(ticker, period=period_for_days(days))


@st.cache_data(ttl=300)
def load_market_caps(crypto_ids, stock_tickers, nonce):
    del nonce
    return {
        "crypto": crypto_market_caps(crypto_ids),
        "stock": stock_market_caps(stock_tickers),
    }


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


def _share_market_rows(crypto_watchlist, stock_watchlist, crypto_results, stock_results):
    """Save this refresh's closes and reuse any headline score already stored."""
    priced = []
    for kind, results in (("Crypto", crypto_results), ("Stock", stock_results)):
        for row in results:
            priced.append({"kind": kind, "asset_id": row.get("key"), "closes": row.get("closes")})
    save_price_paths(supabase, priced)

    pairs = [("Crypto", asset_id) for asset_id in crypto_watchlist]
    pairs += [("Stock", asset_id) for asset_id in stock_watchlist]
    shared = load_shared_market(supabase, [asset_market_key(kind, asset_id) for kind, asset_id in pairs])
    counts = holder_counts(supabase)
    logos = _asset_logos(crypto_watchlist, stock_watchlist, shared)
    crypto_keys = [asset_market_key("Crypto", asset_id) for asset_id in crypto_watchlist]
    stock_keys = [asset_market_key("Stock", asset_id) for asset_id in stock_watchlist]
    market_keys = crypto_keys + stock_keys
    crowd = sentiment_crowd(supabase, market_keys)
    comments = sentiment_comment_lists(supabase, market_keys)
    feed = sentiment_comment_lists(supabase, market_keys, every=True)
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
    st.session_state["social_stream"] = json.dumps(
        social_stream_items(
            feed, shared, stream_names, logos, market_keys,
            {"crypto": crypto_keys, "stock": stock_keys},
            sentiment_replies(supabase),
        ),
        ensure_ascii=False,
    )
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


def _asset_logos(crypto_watchlist, stock_watchlist, shared: dict) -> dict[str, str]:
    """Reuse a saved logo. Ask CoinGecko or Finnhub only when an asset has none yet."""
    logos = {}
    missing_crypto = []
    missing_stock = []
    fresh = []
    for kind, watchlist in (("Crypto", crypto_watchlist), ("Stock", stock_watchlist)):
        for asset_id in watchlist:
            key = asset_market_key(kind, asset_id)
            saved = _stored_logo(shared.get(key))
            if saved:
                logos[key] = saved
            elif kind == "Crypto":
                missing_crypto.append(asset_id)
            else:
                missing_stock.append(asset_id)
    for coin_id, url in crypto_logo_urls(missing_crypto).items():
        key = asset_market_key("Crypto", coin_id)
        logos[key] = url
        fresh.append({"kind": "Crypto", "asset_id": coin_id, "logo_url": url})
    for ticker in missing_stock:
        url = stock_logo_url(ticker)
        if not url:
            continue
        key = asset_market_key("Stock", ticker)
        logos[key] = url
        fresh.append({"kind": "Stock", "asset_id": ticker, "logo_url": url})
    save_logos(supabase, fresh)
    st.session_state["asset_logos"] = logos
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


@st.fragment
def render_dashboard(crypto_watchlist, stock_watchlist, history_days, weights, show_reasons_flag, show_extra_metrics_flag, show_period_changes_flag, trade_crypto, trade_equities):
    st.session_state["_bar_run"] = {}
    shared_keys = []
    if trade_crypto:
        shared_keys.extend(asset_market_key("Crypto", asset_id) for asset_id in crypto_watchlist)
    if trade_equities:
        shared_keys.extend(asset_market_key("Stock", asset_id) for asset_id in stock_watchlist)
    st.session_state["_shared_rows"] = load_shared_market(supabase, shared_keys)

    wide_layout = st.session_state.get("section_layout") == "Wide"
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
        moods = load_market_moods(supabase) or {}
        if trade_crypto:
            jumps.append((
                "Market Sentiment - Crypto",
                "jump_mood_crypto",
                "mood_countdown_crypto",
                next_update(row_timestamp(moods.get("crypto"), "sentiment_updated_at"), SENTIMENT_REFRESH_SECONDS),
                "market_mood_crypto",
                "market-mood-crypto",
                "Open crypto market sentiment. The time is the next shared update. Pressing this does not refresh it.",
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
            ))
            jumps.append((
                "Technical Data - Selected Asset",
                "jump_technical",
                "technical_countdown",
                next_update(row_timestamp(opened_row, "prices_updated_at"), TECHNICAL_REFRESH_SECONDS),
                "interactive_chart",
                "interactive-chart",
                "Open the chart. The time is the next shared price update. Pressing this does not refresh it.",
            ))
        if jumps:
            # One control per column, so each timer writes onto its own button.
            jump_columns = st.columns(len(jumps))
            honored = st.session_state.setdefault("countdown_seen", {})
            reread = False
            for column, (title, _button_key, timer_key, deadline, _section_id, anchor, jump_help) in zip(jump_columns, jumps):
                with column:
                    due = _countdown_due(deadline, timer_key, title, anchor, jump_help)
                    token = "" if deadline is None else str(int(deadline * 1000))
                    if due and token and honored.get(timer_key) != token:
                        honored[timer_key] = token
                        reread = True
            if reread:
                _rerun_fragment()

        # Market cap still uses a short cache. Prices and sentiment come from the shared rows.
        nonce = (st.session_state.data_nonce, int(time.time() // TECHNICAL_REFRESH_SECONDS))

        def process_watchlist(watchlist, is_crypto=True):
            results = []
            for key, name in watchlist.items():
                if is_crypto:
                    ticker = crypto_ticker(key)
                    if ticker and str(key).strip().upper() == ticker:
                        name = ticker
                kind = "Crypto" if is_crypto else "Stock"
                df, err = _stored_bars(kind, key, history_days)

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
                        df = calculate_indicators(df)
                        scored = compute_score(df, weights=weights)
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

        crypto_results = process_watchlist(crypto_watchlist, is_crypto=True) if trade_crypto else []
        stock_results = process_watchlist(stock_watchlist, is_crypto=False) if trade_equities else []
        if show_extra_metrics_flag:
            caps = load_market_caps(
                tuple(crypto_watchlist) if trade_crypto else (),
                tuple(stock_watchlist) if trade_equities else (),
                nonce,
            )
            for row in crypto_results:
                row["market_cap"] = (caps.get("crypto") or {}).get(str(row.get("key") or "").lower())
            for row in stock_results:
                row["market_cap"] = (caps.get("stock") or {}).get(str(row.get("key") or "").upper())
        _share_market_rows(crypto_watchlist, stock_watchlist, crypto_results, stock_results)
        saved_scope = (prefs.get("settings") or {}).get("stream_asset")
        scope = saved_scope if saved_scope in ("watchlist", "crypto", "stock") else ""
        try:
            stream_items = json.loads(st.session_state.get("social_stream") or "[]")
        except (TypeError, json.JSONDecodeError):
            stream_items = []
        if not isinstance(stream_items, list):
            stream_items = []
        chat_notice = st.session_state.pop("chat_notice", "")
        stream_state = _social_stream(
            key="social_stream_host",
            data=json.dumps(
                {
                    "items": stream_items,
                    "asset": scope,
                    "chat": load_chat(supabase),
                    "me": _chat_viewer(),
                    "favourites": _favourite_ids((prefs.get("settings") or {}).get("favourites")),
                    "notice": chat_notice,
                    "faces": list(COMMENT_EMOTICONS),
                    "limit": COMMENT_LIMIT,
                    "account": str(user_id),
                    "panel": account_panel(),
                },
                ensure_ascii=False,
            ),
            on_asset_change=lambda: None,
            on_chat_change=lambda: None,
            on_signal_change=lambda: None,
            on_favourite_change=lambda: None,
            on_panel_change=lambda: None,
        )
        chosen_scope = stream_state.asset
        chat_event = _chat_action(getattr(stream_state, "chat", None))
        signal_event = _chat_action(getattr(stream_state, "signal", None))
        favourite_event = _favourite_event(getattr(stream_state, "favourite", None))
        if chat_event and chat_event.get("n") != st.session_state.get("chat_done"):
            st.session_state["chat_done"] = chat_event.get("n")
            st.session_state["chat_notice"] = _apply_chat_action(chat_event)
            _rerun_fragment()
        if signal_event and signal_event.get("n") != st.session_state.get("signal_done"):
            st.session_state["signal_done"] = signal_event.get("n")
            st.session_state["chat_notice"] = _apply_signal_action(signal_event)
            _rerun_fragment()
        if favourite_event and favourite_event.get("n") != st.session_state.get("favourite_done"):
            st.session_state["favourite_done"] = favourite_event.get("n")
            st.session_state["chat_notice"] = _apply_favourite(favourite_event)
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
                if panel_updates:
                    save_account_settings(panel_updates)

        try:
            evaluate_alerts(supabase, user_id, crypto_results + stock_results, alert_prefs)
        except Exception:
            st.warning("Alerts were not updated on this refresh.")

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
            else:
                st.session_state.scroll_target = "interactive-chart"
                section_id = "interactive_chart"
            st.session_state.scroll_token = str(time.time_ns())
            st.session_state.chart_pick = (kind_name, asset_id)
            st.session_state.chart_pick_from_row = True
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
        st.caption("Click a box to open that asset on the chart.")

    if not wide_layout:
        show_market_moods(trade_crypto, trade_equities)

    def render_score_bar(score):
        if score is None or pd.isna(score):
            pct, color, label = 0, "#6b7280", "—"
        else:
            pct = max(0, min(100, float(score)))
            color = tone(score)[3]
            label = f"{score:.0f}"
        return (
            '<div style="display:flex;align-items:center;gap:8px;width:100%;min-width:100px;">'
            '<div class="ang-track">'
            f'<div style="width:{pct}%;background:{color};height:100%;border-radius:6px;"></div></div>'
            f'<span style="min-width:28px;font-weight:600;font-size:0.9em;">{label}</span></div>'
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
            st.caption("Click a column title to sort. The table starts with the strongest score at the top. Click a name to show that asset on the chart. Click a sentiment score to open its headlines. Watching is how many accounts hold that asset. The Crowd box is the average of personal scores. Hover the down thumb for the spread. A comment balloon, or the arrow on the right edge, opens the social signals and chat. The 30-day trend uses the same colors as 30d %.")

            headers = ["Asset", "Watching", "Score", "Signal", "Price", "RSI"]
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
            sort_at = {"Asset": 0, "Watching": 1, "Score": 2, "Signal": 3, "Price": 4, "RSI": 5}
            column = 6
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
                mark = " ↓" if name == "Score" else ""
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
                rows_html += (
                    f"<tr class='{row_class}'>"
                    f"<td data-sort='{sort_token(row.get('symbol'))}' style='padding:10px;white-space:nowrap;'>"
                    "<span style='display:inline-flex;align-items:center;gap:8px;'>"
                    f"{asset_logo(row.get('logo_url'), row.get('symbol'))}{name_button}</span></td>"
                    f"<td data-sort='{sort_token(row.get('holders'), numeric=True)}' "
                    f"style='padding:8px 10px;white-space:nowrap;'>{holders_mark(row.get('holders'))}</td>"
                    f"<td data-sort='{sort_token(row.get('score'), numeric=True)}' "
                    f"style='padding:10px;min-width:130px;'>{render_score_bar(row['score'])}</td>"
                    f"{cell(row.get('label') or '—', row.get('label') or '')}"
                    f"{cell(price_str, price, numeric=True)}{cell(rsi_str, rsi, numeric=True)}"
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
                rows_html += (
                    f"<td data-sort='{sort_token(headline_score, numeric=True)}' "
                    f"style='padding:10px;text-align:right;white-space:nowrap;'>"
                    f"{sentiment_badge(headline_score, sentiment_pick)}</td>"
                    f"<td data-crowd-mark='{pick_value}' "
                    f"data-sort='{sort_token((row.get('thumbs_up') or 0) - (row.get('thumbs_down') or 0), numeric=True)}' "
                    f"style='padding:10px 4px 10px 10px;text-align:right;white-space:nowrap;'>"
                    f"{crowd_mark(row.get('thumbs_up'), row.get('thumbs_down'), headline_score is not None, row.get('alt_count'), row.get('alt_avg'), row.get('alt_spread'))}</td>"
                    f"<td data-crowd-avg='{pick_value}' "
                    f"data-sort='{sort_token(row.get('alt_avg'), numeric=True)}' "
                    f"style='padding:10px 10px 10px 4px;text-align:left;white-space:nowrap;'>"
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
                    _rerun_fragment()
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

            if asset_key and st.session_state.get("chart_pick") != (asset_type, asset_key):
                st.session_state.chart_pick = (asset_type, asset_key)
                _rerun_fragment()

            if not asset_key:
                st.info("Add an asset to this watchlist to see a chart.")
                return

            df_chart, chart_err = _stored_bars(asset_type, asset_key, history_days)
            if asset_type == "Crypto":
                title = crypto_watchlist[asset_key]
            else:
                title = f"{stock_watchlist[asset_key]} ({asset_key})"

            if chart_err or df_chart.empty:
                st.warning(chart_err or "Could not load chart data. Check your internet connection.")
                return

            df_chart = calculate_indicators(df_chart)
            fig = make_subplots(
                rows=3, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                row_heights=[0.55, 0.2, 0.25],
                subplot_titles=(f"{title} Price", "Volume", "RSI (14)"),
            )
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

            colors = [
                "green" if df_chart["close"].iloc[i] >= df_chart["open"].iloc[i] else "red"
                for i in range(len(df_chart))
            ]
            fig.add_trace(
                go.Bar(x=df_chart.index, y=df_chart["volume"], name="Volume", marker_color=colors, opacity=0.6),
                row=2, col=1,
            )
            if "rsi" in df_chart.columns:
                fig.add_trace(
                    go.Scatter(x=df_chart.index, y=df_chart["rsi"], name="RSI", line=dict(color="purple", width=1.5)),
                    row=3, col=1,
                )
                fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)
                fig.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.3, row=3, col=1)

            fig.update_layout(
                height=750,
                xaxis_rangeslider_visible=False,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=60, b=20),
            )
            fig.update_yaxes(title_text="Price", row=1, col=1)
            fig.update_yaxes(title_text="Volume", row=2, col=1)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
            _paint_chart(fig)
            st.plotly_chart(fig, width="stretch")

            result = compute_score(df_chart, weights=weights)
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
                col_c.metric("Volatility (ATR%)", f"{result['atr_pct']:.2f}%")

        if show_reasons_flag and result.get("reasons") and result.get("score") is not None:
            with section_expander(f"🔍 Score Breakdown — {title}", "score_breakdown"):
                st.markdown(
                    f"<span style='color:{color};font-weight:bold;font-size:1.1em'>"
                    f"{result['score']}/100 ({html.escape(str(result['label']))})</span>",
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
        show_max_pain(asset_type, asset_key, title, float(df_chart["close"].iloc[-1]))
        show_market_sentiment(
            asset_type,
            asset_key,
            sentiment_label,
            crypto_ticker(asset_key) if asset_type == "Crypto" else asset_key,
        )
    # Outside both wide columns, so it cannot push the chart header down.
    _scroll_chart(
        key="scroll_to_chart",
        data={
            "token": st.session_state.get("scroll_token") or "",
            "target": st.session_state.get("scroll_target") or "interactive-chart",
        },
    )
    if st.session_state.pop("_shared_reread", False):
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


def headline_table(headlines: list) -> str:
    """Article, the date, a one-sentence AI summary, then the score. A dash until a summary exists."""
    rows = [
        "<div class='headline-head'>"
        "<div class='headline-title'>Article</div>"
        "<div class='headline-date'>Published</div>"
        "<div class='headline-note'>AI Summary</div>"
        "<div class='headline-score'>Score</div>"
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
    return f"<div style='margin-top:10px;'>{''.join(rows)}</div>"


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
        articles.append({
            "title": f"{name}, {value}" if value else name,
            "source": item.get("source") or "",
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
        table = headline_table(articles) if articles else ""
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
        _article_box(f"mood_{key}_news", headline_table(headlines))
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
                st.session_state[expiry_key] = next(iter(labels))
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
            st.caption("This expiry has no open interest yet.")
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


def _take_alert_pick() -> None:
    """An alert click names an asset. This pass draws that chart. It does not run again."""
    reported = _asset_pick(key="alert_asset_pick", on_picked_change=lambda: None)
    raw = str(getattr(reported, "picked", "") or "")
    if "|" not in raw or st.session_state.get("_alert_pick_seen") == raw:
        return
    kind_name, asset_id = raw.split("|", 1)
    if kind_name == "Crypto":
        chosen = CRYPTO_WATCHLIST
    elif kind_name == "Stock":
        chosen = STOCK_WATCHLIST
    else:
        return
    if asset_id not in chosen:
        return
    st.session_state["_alert_pick_seen"] = raw
    st.session_state.chart_pick = (kind_name, asset_id)
    st.session_state.chart_pick_from_row = True
    st.session_state.asset_type = kind_name
    if kind_name == "Crypto":
        st.session_state.asset_crypto = asset_id
    else:
        st.session_state.asset_stock = asset_id
    st.session_state.scroll_target = "interactive-chart"
    st.session_state.scroll_token = str(time.time_ns())
    _remember_section("interactive_chart", True)


_take_alert_pick()

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
