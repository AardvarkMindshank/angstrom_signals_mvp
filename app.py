"""
Crypto & Equity Signals Dashboard
Run with: streamlit run app.py
"""

import base64
import html
import io
import json
import time
import traceback
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots
from streamlit.errors import StreamlitInvalidLayoutContextError
from supabase import create_client

st.set_page_config(
    page_title="angstrom signals - level 1",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
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
  host.querySelectorAll("button[data-pick]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      button.blur();
      setTriggerValue("picked", button.getAttribute("data-pick"));
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

_SOCIAL_STREAM_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  let items = [];
  let savedAsset = "";
  try {
    const parsed = typeof data === "string" ? JSON.parse(data || "[]") : data;
    if (Array.isArray(parsed)) {
      items = parsed;
    } else if (parsed && typeof parsed === "object") {
      items = Array.isArray(parsed.items) ? parsed.items : [];
      savedAsset = parsed.asset === "watchlist" ? "watchlist" : "";
    }
  } catch (error) {
    items = [];
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
    if (!document.getElementById("social-stream-style")) {
      const style = document.createElement("style");
      style.id = "social-stream-style";
      style.textContent = [
        "#social-stream-root{position:fixed;inset:0;z-index:10000000;pointer-events:none;}",
        "#social-stream-root.is-open{pointer-events:auto;}",
        "#social-stream-root .scrim{position:absolute;inset:0;background:rgba(17,24,39,0.35);opacity:0;transition:opacity .2s ease;}",
        "#social-stream-root.is-open .scrim{opacity:1;}",
        "#social-stream-root .panel{position:absolute;top:0;right:0;height:100%;width:min(420px,100vw);background:#fff;color:#111827;box-shadow:-12px 0 40px rgba(17,24,39,.18);transform:translateX(100%);transition:transform .22s ease;display:flex;flex-direction:column;pointer-events:auto;}",
        "#social-stream-root.is-open .panel{transform:none;}",
        "#social-stream-root .head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:18px 18px 4px;}",
        "#social-stream-root h2{margin:0;font-size:1.15rem;line-height:1.25;font-weight:650;}",
        "#social-stream-root .kicker{font-size:.72rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#6b7280;margin-bottom:2px;}",
        "#social-stream-root .hint{margin:6px 0 0;color:#6b7280;font-size:.8rem;line-height:1.35;}",
        "#social-stream-root .close{background:#f3f4f6;border:0;border-radius:999px;padding:6px 12px;font:inherit;font-weight:600;cursor:pointer;color:#111827;}",
        "#social-stream-root .edge{position:fixed;top:.75rem;right:0;z-index:2;pointer-events:auto;display:flex;align-items:center;justify-content:center;width:2rem;height:2rem;padding:0;border:1px solid rgba(49,51,63,.2);border-right:0;border-radius:.5rem 0 0 .5rem;background:#fff;color:#808495;cursor:pointer;box-shadow:-1px 1px 4px rgba(0,0,0,.08);transition:right .22s ease,background .15s ease,color .15s ease;}",
        "#social-stream-root .edge:hover{background:#f0f2f6;color:#ff4b4b;}",
        "#social-stream-root.is-open .edge{right:min(420px,calc(100vw - 2.25rem));}",
        "#social-stream-root.is-open .edge svg{transform:scaleX(-1);}",
        "#social-stream-root .filters{padding:10px 18px 0;}",
        "#social-stream-root .chips{display:flex;flex-wrap:wrap;gap:6px;}",
        "#social-stream-root .chips button{background:#fff;border:1px solid #d1d5db;border-radius:999px;padding:4px 10px;font:inherit;font-size:.82rem;cursor:pointer;color:#374151;}",
        "#social-stream-root .chips button.is-on{background:#111827;border-color:#111827;color:#fff;}",
        "#social-stream-root .picks{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;}",
        "#social-stream-root .picks label{display:flex;flex-direction:column;gap:4px;font-size:.75rem;font-weight:600;color:#6b7280;}",
        "#social-stream-root select{font:inherit;font-size:.85rem;color:#111827;border:1px solid #d1d5db;border-radius:8px;padding:6px 8px;background:#fff;}",
        "#social-stream-root .count{padding:10px 18px 0;font-size:.78rem;color:#6b7280;}",
        "#social-stream-root .list{overflow:auto;padding:8px 18px 28px;}",
        "#social-stream-root .card{padding:14px 0;border-top:1px solid #e5e7eb;}",
        "#social-stream-root .person{display:flex;gap:10px;align-items:center;}",
        "#social-stream-root .face{width:36px;height:36px;border-radius:50%;object-fit:cover;background:#dbeafe;color:#1d4ed8;display:flex;align-items:center;justify-content:center;font-weight:700;flex:none;}",
        "#social-stream-root .who{font-weight:600;font-size:.92rem;}",
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
        "#social-stream-root .empty{color:#6b7280;padding:18px 0;font-size:.9rem;line-height:1.4;}"
      ].join("");
      document.head.appendChild(style);
    }
    let root = document.getElementById("social-stream-root");
    if (!root) {
      root = document.createElement("div");
      root.id = "social-stream-root";
      root.innerHTML = [
        "<div class='scrim'></div>",
        "<aside class='panel' role='dialog' aria-label='Social signals stream'>",
        "<header class='head'><div>",
        "<div class='kicker'>Social signals</div>",
        "<h2>Social signals stream</h2>",
        "<p class='hint'>Newest first. Each note shows the sentiment it was answering, and stays for 12 hours. All assets or My watchlists is saved on your account.</p>",
        "</div><button type='button' class='close'>Close</button></header>",
        "<div class='filters'><div class='chips'>",
        "<button type='button' data-side=''>All</button>",
        "<button type='button' data-side='positive'>Positive</button>",
        "<button type='button' data-side='negative'>Negative</button>",
        "<button type='button' data-side='mixed'>Mixed</button>",
        "</div><div class='picks'>",
        "<label>Asset<select id='stream-asset'></select></label>",
        "<label>Person<select id='stream-person'></select></label>",
        "</div></div>",
        "<div class='count'></div><div class='list'></div></aside>",
        "<button type='button' class='edge' aria-label='Open the social signals stream' aria-expanded='false'>",
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
        if ((choice === "" || choice === "watchlist") && window.socialStreamReport) {
          window.socialStreamReport("asset", choice === "watchlist" ? "watchlist" : "all");
        }
      });
      root.querySelector("#stream-person").addEventListener("change", (event) => {
        window.socialStreamState.person = event.target.value;
        window.renderSocialStream();
      });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && window.socialStreamState.open) closeStream();
      });
    }
    window.openSocialStream = (assetKey) => {
      window.socialStreamState.open = true;
      window.socialStreamState.asset = assetKey || "";
      window.socialStreamState.side = "";
      window.socialStreamState.person = "";
      window.renderSocialStream();
      const closeButton = document.querySelector("#social-stream-root .close");
      if (closeButton) closeButton.focus();
    };
    window.renderSocialStream = () => {
      const panel = document.getElementById("social-stream-root");
      if (!panel) return;
      const state = window.socialStreamState;
      panel.classList.toggle("is-open", !!state.open);
      const edge = panel.querySelector(".edge");
      if (edge) {
        const edgeLabel = state.open ? "Close the social signals stream" : "Open the social signals stream";
        edge.setAttribute("aria-label", edgeLabel);
        edge.setAttribute("title", edgeLabel);
        edge.setAttribute("aria-expanded", state.open ? "true" : "false");
      }
      const items = window.socialStreamItems || [];
      const assets = [];
      const seenAssets = {};
      const people = [];
      const seenPeople = {};
      items.forEach((item) => {
        if (item.key && !seenAssets[item.key]) {
          seenAssets[item.key] = true;
          assets.push([item.key, item.asset || item.key]);
        }
        const person = item.name || "Member";
        if (!seenPeople[person]) {
          seenPeople[person] = true;
          people.push(person);
        }
      });
      assets.sort((a, b) => String(a[1]).localeCompare(String(b[1])));
      people.sort((a, b) => a.localeCompare(b));
      fillStreamSelect(
        panel.querySelector("#stream-asset"),
        "All assets",
        assets,
        state.asset,
        [["watchlist", "My watchlists"]]
      );
      fillStreamSelect(panel.querySelector("#stream-person"), "All people", people.map((name) => [name, name]), state.person);
      if (state.asset !== "watchlist" && !seenAssets[state.asset]) state.asset = "";
      if (!seenPeople[state.person]) state.person = "";
      panel.querySelector("#stream-asset").value = state.asset;
      panel.querySelector("#stream-person").value = state.person;
      panel.querySelectorAll("[data-side]").forEach((button) => {
        button.classList.toggle("is-on", (button.getAttribute("data-side") || "") === state.side);
      });
      const shown = items.filter((item) => {
        if (state.asset === "watchlist") {
          if (!item.watchlist) return false;
        } else if (state.asset && item.key !== state.asset) return false;
        if (state.person && (item.name || "Member") !== state.person) return false;
        if (state.side && item.side !== state.side) return false;
        return true;
      });
      const count = panel.querySelector(".count");
      count.textContent = shown.length === 1 ? "1 comment" : shown.length + " comments";
      const list = panel.querySelector(".list");
      list.replaceChildren();
      if (!shown.length) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = items.length
          ? "No comments match these filters."
          : "No comments yet. Each one stays for 12 hours after it is posted.";
        list.appendChild(empty);
        return;
      }
      shown.forEach((item) => list.appendChild(streamCard(item)));
    };
  }

  function fillStreamSelect(select, placeholder, pairs, selected, extras) {
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
    const person = document.createElement("div");
    person.className = "person";
    const name = String(item.name || "Member");
    person.appendChild(streamFace(name, item.avatar));
    const identity = document.createElement("div");
    const who = document.createElement("div");
    who.className = "who";
    who.textContent = name;
    const when = document.createElement("div");
    when.className = "when";
    const parsedAt = new Date(item.at);
    when.textContent = Number.isNaN(parsedAt.getTime()) ? "" : parsedAt.toLocaleString(undefined, {
      month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit"
    });
    identity.appendChild(who);
    identity.appendChild(when);
    person.appendChild(identity);
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
    card.appendChild(context);
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
  const alreadyOnScreen = () => {
    if (targetId !== "interactive-chart") return false;
    const target = document.getElementById(targetId);
    if (!target) return false;
    const scroller = target.closest('[data-testid="stMain"]') || target.closest("section.main");
    const viewTop = scroller ? scroller.getBoundingClientRect().top : 0;
    const viewBottom = scroller ? scroller.getBoundingClientRect().bottom : window.innerHeight;
    const rect = target.getBoundingClientRect();
    return rect.top >= viewTop - 16 && rect.top <= viewTop + (viewBottom - viewTop) * 0.55;
  };
  const go = () => {
    if (alreadyOnScreen()) return;
    const target = document.getElementById(targetId);
    if (!target) return;
    target.scrollIntoView({behavior: "auto", block: "start"});
    const scroller = target.closest('[data-testid="stMain"]') || target.closest("section.main");
    if (!scroller) return;
    const top = target.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 72;
    scroller.scrollTop = Math.max(0, top);
  };
  go();
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

_TECHNICAL_REFRESH_SECONDS = 300
_COUNTDOWN_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const timerKey = "cd_" + ((data && data.key) || "x");
  window.clearInterval(window[timerKey]);
  let host = parentElement.querySelector("[data-countdown]");
  if (!host) {
    host = document.createElement("div");
    host.setAttribute("data-countdown", "");
    parentElement.appendChild(host);
  }
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const end = Number(data && data.deadlineMs);
  const token = String((data && data.token) || "");
  function buttonLabel() {
    const column = parentElement.closest('[data-testid="column"]')
      || parentElement.closest('[data-testid="stColumn"]');
    const button = column && column.querySelector("button");
    if (!button) return null;
    button.style.whiteSpace = "nowrap";
    return button.querySelector("p") || button.querySelector('[data-testid="stMarkdownContainer"]') || button;
  }
  function render() {
    if (!Number.isFinite(end)) return;
    const left = Math.max(0, Math.round((end - Date.now()) / 1000));
    const hours = Math.floor(left / 3600);
    const minutes = Math.floor((left % 3600) / 60);
    const seconds = String(left % 60).padStart(2, "0");
    const clock = hours > 0
      ? hours + ":" + String(minutes).padStart(2, "0") + ":" + seconds
      : minutes + ":" + seconds;
    const label = buttonLabel();
    if (label) label.textContent = "🔄 Refresh " + clock;
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
    host.remove();
  };
}
"""
_countdown = st.components.v2.component(
    "refresh_countdown",
    js=_COUNTDOWN_JS,
    isolate_styles=False,
)


def _countdown_due(deadline: float, widget_key: str) -> bool:
    """Show the time left and report when this deadline has been reached."""
    token = str(int(deadline * 1000))
    result = _countdown(
        key=widget_key,
        data={"deadlineMs": int(deadline * 1000), "token": token, "key": widget_key},
        on_due_change=lambda: None,
    )
    return result.due == token


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


def section_expander(label: str, section_id: str):
    """A main-page section. Open all and Collapse all move every one of these together."""
    fold = st.session_state.setdefault("section_fold", {"open": True, "nonce": 0})
    return st.expander(label, expanded=bool(fold["open"]), key=f"{section_id}_{fold['nonce']}")


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
        load_shared_market,
        recent_closes,
        save_logos,
        save_price_paths,
        save_sentiment,
        sentiment_comment_lists,
        sentiment_crowd,
        social_stream_items,
        set_sentiment_comment,
        set_sentiment_vote,
        with_emoticon,
        sentiment_from_row,
        sparkline_svg,
        trend_tone,
    )
    from scoring import calculate_indicators, compute_score, find_column
    from sentiment import (
        analyze_market_sentiment,
        cached_sentiment_score,
        newest_first,
        remember_sentiment,
        sentiment_cached_at,
        sentiment_query,
        sentiment_ready,
        SENTIMENT_REFRESH_SECONDS,
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


if "user" not in st.session_state:
    st.session_state.user = None
if st.session_state.user is not None and not st.session_state.get("access_token"):
    st.session_state.user = None
if "data_nonce" not in st.session_state:
    st.session_state.data_nonce = 0

supabase = get_supabase()

if st.session_state.user is None:
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    _, col_center, _ = st.columns([1, 1.2, 1])

    with col_center:
        st.title("📈 angstrom signals")
        st.caption("Multi-factor technical scoring research platform • Please log in to continue")

        auth_tab1, auth_tab2 = st.tabs(["🔑 Log In", "📝 Sign Up"])

        with auth_tab1:
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

    st.stop()


user_id = st.session_state.user.id


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
    bio_html = (
        f"<div style='margin-top:8px;font-size:0.85rem;color:#374151;'>{html.escape(bio)}</div>"
        if bio else ""
    )
    return (
        "<div style='background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px;padding:12px;'>"
        "<div style='display:flex;gap:10px;align-items:center;'>"
        f"{face}<div><div style='font-weight:600;color:#111827;'>{safe_name}</div>"
        f"<div style='font-size:0.78rem;color:#6b7280;'>{safe_email}</div></div></div>"
        f"{bio_html}</div>"
    )


if "cloud_prefs" not in st.session_state:
    st.session_state.cloud_prefs = load_user_preferences()
if "profile" not in st.session_state:
    st.session_state.profile = load_profile()

prefs = st.session_state.cloud_prefs
alert_prefs = prefs.get("alerts", {})
profile = st.session_state.profile

with st.sidebar.expander("👤 Account", expanded=False):
    if profile is None:
        st.warning("Profile storage is not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor.")
        profile = {}
    st.markdown(profile_card(profile, st.session_state.user.email or ""), unsafe_allow_html=True)
    with st.expander("Edit profile", expanded=False):
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


notifications_list = fetch_user_notifications()
unread_count = sum(1 for note in notifications_list if not note.get("is_read", False))
notifications_label = "🔔 Notifications" + (f" ({unread_count})" if unread_count else "")

with st.sidebar.expander(notifications_label, expanded=False):
    with st.expander("Alert Feed", expanded=False):
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
                        st.rerun()
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
                st.caption("Click an alert to highlight that asset and open it on the chart.")
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

                for note in filtered_notifs:
                    color, background, arrow, _bar = tone(score_from_alert(note))
                    name = html.escape(str(note.get("asset_name") or "Asset"))
                    message = html.escape(str(note.get("message") or ""))
                    created = html.escape(str(note.get("created_at") or "")[:16].replace("T", " "))
                    weight = "700" if not note.get("is_read") else "500"
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
                            f"<button type='button' data-pick='{pick_value}' "
                            "style='display:block;width:100%;margin:0;padding:0;border:none;"
                            "background:transparent;text-align:left;cursor:pointer;font:inherit;color:inherit;'>"
                            f"{card}</button>"
                        )
                    picked = _score_table(
                        key=f"notif_{note_id}",
                        data=card,
                        on_picked_change=lambda: None,
                    ).picked
                    signature = f"{note_id}:{picked}"
                    if picked and target:
                        if st.session_state.get("notif_handled") != signature:
                            st.session_state.notif_handled = signature
                            st.session_state.chart_pick = target
                            st.session_state.chart_pick_from_row = True
                            st.session_state.scroll_target = "interactive-chart"
                            st.session_state.scroll_token = str(time.time_ns())
                            st.rerun()
                    elif str(st.session_state.get("notif_handled") or "").startswith(f"{note_id}:"):
                        st.session_state.notif_handled = None

                if st.button("🗑️ Clear Read Alerts", use_container_width=True, key="clear_read_btn"):
                    try:
                        supabase.table("user_notifications").delete().eq("user_id", user_id).eq("is_read", True).execute()
                        st.success("Cleared read alerts.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not clear alerts: {exc}")

    with st.expander("Configure Alert Rules", expanded=False):
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

if "section_fold" not in st.session_state:
    st.session_state.section_fold = {"open": True, "nonce": 0}

title_col, open_col, close_col = st.columns([6.2, 1, 1.25], vertical_alignment="center")
with title_col:
    st.title("angstrom signals - level 1")
with open_col:
    if st.button("Open all", key="open_all_sections", use_container_width=True):
        st.session_state.section_fold = {
            "open": True,
            "nonce": st.session_state.section_fold["nonce"] + 1,
        }
with close_col:
    if st.button("Collapse all", key="collapse_all_sections", use_container_width=True):
        st.session_state.section_fold = {
            "open": False,
            "nonce": st.session_state.section_fold["nonce"] + 1,
        }

with st.expander("Help and guides", expanded=False):
    st.markdown("""
**Higher score = a more bullish setup.** Every score starts at 50 and each indicator adds or subtracts points. The result is kept between 0 and 100. This is a research tool, not financial advice.
""")
    bands = [
        ("Strong bullish", "70+", "#15803d", "#dcfce7"),
        ("Bullish", "60–69", "#15803d", "#dcfce7"),
        ("Neutral", "47–52", "#b45309", "#fef3c7"),
        ("Strong bearish", "below 30", "#b91c1c", "#fee2e2"),
    ]
    band_cols = st.columns(4)
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

1. Read the snapshot and the tables. The top row is the strongest technical score, the bottom is the weakest. Quick Snapshot, Crypto Scores, Equity Scores, Interactive Chart, Score Breakdown, and Market sentiment each sit in a section that starts open. Close a header to fold that section away. **Open all** and **Collapse all**, on the right of the page title, do that for every one of those sections. **Feedback**, at the bottom of the sidebar, sends an issue or an idea. It is stored as submitted.
2. Click a name in either table, a Quick Snapshot box, or an alert under Notifications. That asset stays highlighted, and the page moves down to the chart when the chart is off screen. Click a column title to sort that table. It starts with the strongest score at the top.
3. Extra metrics add **7d %**, **Market Cap**, **ATR %**, and **Vol**. A separate checkbox adds **1d %** before the seven-day change and **30d %** after it. For **1d %** and **7d %**, green means the price rose and red means it fell. **30d %** uses the same colors as the **30-day trend**: green for a rise of about 2% or more, red for a fall of about 2% or more, and orange when the move stays inside about 2%. For stocks, one day is the previous trading session. **Market Cap** is the latest size of the asset, from CoinGecko for crypto and Yahoo for stocks. **ATR %** is volatility. **Vol** is volume versus its 20-day average.
4. Alerts fire at 70 and 30 unless you move those sliders. One email goes to the address on your account when a technical score crosses a boundary. It is not sent again until the score leaves that boundary and crosses it later. Sentiment scores do not send alerts.

**Market sentiment**

This sits under the chart. The heading names the open asset, for example **Market sentiment - Bitcoin (BTC)**. Grok reads headlines from the last 7 days and gives each one a score from 0 to 100. The newest headline is listed first. The number at the top of the section is the average of those article scores. Under the short summary, **Positive** and **Negative** each add a paragraph drawn from those same headlines. Green, amber, and red use the same bands as the technical score. The two scores stay separate, and sentiment is not mixed into the technical score.

The **Sentiment** column shows that saved score in the same colored box. A dash means that asset has not been scored yet. Open it on the chart, and the score fills in once Grok finishes. The score is stored once and shown to every account that holds the asset. It stays for about 12 hours.

**30-day trend**, at the far right of each row, is a small line of that same 30-day move. Its color matches the **30d %** column: green for a rise of about 2% or more, red for a fall of about 2% or more, and orange when the move stays inside about 2%. The same line is shared by every account.

**Watching**, beside the name, is how many accounts have that asset on a watchlist. The people marks are a count, not the names of those accounts.

The picture on the left of each name is that asset's logo. The same logo appears at the top of the Interactive Chart and Market sentiment sections. Crypto logos come from CoinGecko. Stock logos come from Finnhub. A letter shows when a logo is not available. The address is saved once and reused for every account.

Beside the sentiment score you can press thumbs up if you agree, or thumbs down if you do not. Press the same thumb again to clear your take. Those buttons sit in an outlined box. After you disagree, scores appear in that same box, under the buttons: 0, 20, 40, 60, 80 and 100. The number you pick also fills the type box, and you can type any number from 0 to 100. It saves on its own when you click a score, press Enter, or leave the box. The thumbs and that same colored average sit at the bottom of Your take, and again under **Crowd** on each table row. The box is the average of the personal scores, in the same style as the Sentiment column. It updates when a score is clicked or typed. Hover the down thumb for the spread, which is how far those scores typically sit from the average. One score has no spread yet. A dash means nobody has given a personal score. Under the thumbs you can post one comment of up to 160 characters. A row of faces under the box adds an emoticon. A speech balloon appears beside the thumbs, and in the **Comments** column, once any comment exists. Click it, or the arrow on the right edge of the page, to slide in the **Social signals stream**. That stream lists comments newest first, with each person's picture, name, and the time, and the sentiment they were answering. Narrow it with All, Positive, Negative, or Mixed. Under Asset, All assets is every comment, and My watchlists is only the crypto and equity tables on your account. That choice is saved for you. You can also pick one asset or one person. Close it with Close, the shaded area, or Escape. A refresh of that sentiment clears every thumb and every personal score, because they belonged to the old score. A comment stays for 12 hours from when it was posted, and the stream keeps the sentiment it was answering even after a newer score arrives.

Click a sentiment score in the table to highlight that asset and jump to its headlines. **↑ Top** scrolls back to the top of the page. It sits at the top right of the Interactive Chart section, and at the top right of Market sentiment.

The Refresh button in Market sentiment pulls fresh headlines and a new score, then starts a 12-hour timer. It also runs on its own when that timer reaches zero. The Refresh button in Quick Snapshot still reloads prices and technical scores every 5 minutes. Pressing either button refreshes that section now and starts its timer again.

**Alerts keep running in the background**

Prices and technical scores on this page refresh every 5 minutes while it is open. Market sentiment refreshes about every 12 hours while it is open. The same 5-minute alert check keeps running after you close the page or log out.

- A crossing is saved on your account. It shows up under Notifications the next time you log in.
- The email goes only to you.
""")

CRYPTO_WATCHLIST = prefs["crypto"]
STOCK_WATCHLIST = prefs["stock"]
current_weights = prefs["weights"]
custom_profiles = prefs["profiles"]
settings = prefs["settings"]


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

with st.sidebar.expander("⭐ Watchlists", expanded=False):
    with st.expander("Edit Crypto", expanded=False):
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
                changed = False
                if alias and alias != cid and alias in CRYPTO_WATCHLIST:
                    CRYPTO_WATCHLIST.pop(alias, None)
                    changed = True
                if cid and cid not in CRYPTO_WATCHLIST:
                    CRYPTO_WATCHLIST[cid] = label
                    changed = True
                if changed:
                    prefs["crypto"] = CRYPTO_WATCHLIST
                    save_preferences_to_cloud({"crypto_watchlist": CRYPTO_WATCHLIST})
                    st.rerun()
        if CRYPTO_WATCHLIST:
            to_remove = st.selectbox("Remove crypto", [""] + list(CRYPTO_WATCHLIST.keys()), key="rm_crypto")
            if to_remove and st.button("Remove Crypto"):
                CRYPTO_WATCHLIST.pop(to_remove, None)
                prefs["crypto"] = CRYPTO_WATCHLIST
                save_preferences_to_cloud({"crypto_watchlist": CRYPTO_WATCHLIST})
                st.rerun()

    with st.expander("Edit Stocks", expanded=False):
        st.caption("Add by ticker (AAPL, MSFT, etc.)")
        new_stock = st.text_input("Add stock ticker", key="new_stock", placeholder="e.g. GOOGL")
        if st.button("Add Stock") and new_stock:
            tic = new_stock.strip().upper()
            if tic and tic not in STOCK_WATCHLIST:
                STOCK_WATCHLIST[tic] = tic
                prefs["stock"] = STOCK_WATCHLIST
                save_preferences_to_cloud({"stock_watchlist": STOCK_WATCHLIST})
                st.rerun()
        if STOCK_WATCHLIST:
            to_remove = st.selectbox("Remove stock", [""] + list(STOCK_WATCHLIST.keys()), key="rm_stock")
            if to_remove and st.button("Remove Stock"):
                STOCK_WATCHLIST.pop(to_remove, None)
                prefs["stock"] = STOCK_WATCHLIST
                save_preferences_to_cloud({"stock_watchlist": STOCK_WATCHLIST})
                st.rerun()

with st.sidebar.expander("⚖️ Scoring Balance Weights", expanded=False):
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

with st.sidebar.expander("⚙️ Settings", expanded=False):
    days_history = st.slider("Days of history", 90, 365, int(settings.get("days_history", 200)))
    show_reasons = st.checkbox("Show score breakdown", value=settings.get("show_reasons", True))
    show_extra_metrics = st.checkbox(
        "Show extra metrics (7d, market cap, ATR, volume)",
        value=settings.get("show_extra_metrics", True),
    )
    show_period_changes = st.checkbox(
        "Show 1-day and 30-day changes",
        value=settings.get("show_period_changes", True),
    )

    new_settings = {
        "days_history": days_history,
        "show_reasons": show_reasons,
        "show_extra_metrics": show_extra_metrics,
        "show_period_changes": show_period_changes,
    }
    if settings.get("stream_asset") in ("all", "watchlist"):
        new_settings["stream_asset"] = settings["stream_asset"]
    if new_settings != settings:
        settings = new_settings
        prefs["settings"] = settings
        save_preferences_to_cloud({"settings": settings})


def _feedback_mail_settings() -> tuple[str, str, str]:
    """Resend key, sender, and the inbox that receives feedback. Empty pieces stay empty."""
    import os

    api_key = (os.getenv("RESEND_API_KEY") or "").strip() or _optional_secret("resend", "api_key")
    sender = (os.getenv("RESEND_FROM") or "").strip() or _optional_secret("resend", "from_email")
    inbox = (os.getenv("FEEDBACK_TO") or "").strip() or _optional_secret("resend", "feedback_to")
    return api_key, sender or "Angstrom Signals <onboarding@resend.dev>", inbox


def _email_feedback(kind: str, body: str, user_email: str, user_id: str) -> bool:
    """Mail one saved note. False when Resend is not configured or the send fails."""
    api_key, sender, inbox = _feedback_mail_settings()
    if not api_key or not inbox:
        return False
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
        return response.status_code < 300
    except Exception:
        return False


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
    if _email_feedback(kind, text[:4000], user_email, user_id):
        return "Saved and emailed. Thank you."
    return "Saved. Thank you."


if st.session_state.pop("feedback_clear", False):
    st.session_state["feedback_body"] = ""

with st.sidebar.expander("📝 Feedback", expanded=False):
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
        if st.session_state.feedback_notice.startswith("Saved"):
            st.session_state.feedback_clear = True
        st.rerun()
    feedback_notice = st.session_state.pop("feedback_notice", "")
    if feedback_notice.startswith("Saved"):
        st.success(feedback_notice)
    elif feedback_notice:
        st.warning(feedback_notice)


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
    market_keys = [asset_market_key(kind, asset_id) for kind, asset_id in pairs]
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
    st.session_state["social_stream"] = json.dumps(
        social_stream_items(feed, shared, stream_names, logos, market_keys),
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


@st.fragment
def render_dashboard(crypto_watchlist, stock_watchlist, history_days, weights, show_reasons_flag, show_extra_metrics_flag, show_period_changes_flag):
    if "technical_due" not in st.session_state:
        st.session_state.technical_due = time.time() + _TECHNICAL_REFRESH_SECONDS

    with section_expander("Quick Snapshot", "quick_snapshot"):
        _, snap_refresh = st.columns([4, 1.45], vertical_alignment="center")
        with snap_refresh:
            technical_now = st.button(
                "🔄 Refresh",
                key="refresh_technical",
                use_container_width=True,
                help="Pull fresh prices and technical scores. This also runs on its own when the timer reaches zero.",
            )
            technical_due = _countdown_due(st.session_state.technical_due, "technical_countdown")
            if technical_now or technical_due:
                st.session_state.data_nonce += 1
                st.session_state.technical_due = time.time() + _TECHNICAL_REFRESH_SECONDS
                _rerun_fragment()

        # Wall-clock window so a scheduled rerun fetches new prices instead of the 5-minute cache.
        nonce = (st.session_state.data_nonce, int(time.time() // 300))

        def process_watchlist(watchlist, is_crypto=True):
            results = []
            for key, name in watchlist.items():
                if is_crypto:
                    ticker = crypto_ticker(key)
                    if ticker and str(key).strip().upper() == ticker:
                        name = ticker
                with st.spinner(f"Loading {name}..."):
                    if is_crypto:
                        df, err = load_crypto(key, history_days, nonce)
                    else:
                        df, err = load_stock(key, history_days, nonce)

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

                    if not df.empty and len(df) >= 15:
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

        crypto_results = process_watchlist(crypto_watchlist, is_crypto=True)
        stock_results = process_watchlist(stock_watchlist, is_crypto=False)
        if show_extra_metrics_flag:
            caps = load_market_caps(tuple(crypto_watchlist), tuple(stock_watchlist), nonce)
            for row in crypto_results:
                row["market_cap"] = (caps.get("crypto") or {}).get(str(row.get("key") or "").lower())
            for row in stock_results:
                row["market_cap"] = (caps.get("stock") or {}).get(str(row.get("key") or "").upper())
        _share_market_rows(crypto_watchlist, stock_watchlist, crypto_results, stock_results)
        saved_scope = (prefs.get("settings") or {}).get("stream_asset")
        scope = "watchlist" if saved_scope == "watchlist" else ""
        try:
            stream_items = json.loads(st.session_state.get("social_stream") or "[]")
        except (TypeError, json.JSONDecodeError):
            stream_items = []
        if not isinstance(stream_items, list):
            stream_items = []
        chosen_scope = _social_stream(
            key="social_stream_host",
            data=json.dumps({"items": stream_items, "asset": scope}, ensure_ascii=False),
            on_asset_change=lambda: None,
        ).asset
        if chosen_scope in ("all", "watchlist"):
            stored = prefs.setdefault("settings", {})
            if stored.get("stream_asset") != chosen_scope:
                stored["stream_asset"] = chosen_scope
                save_preferences_to_cloud({"settings": stored})

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
            parts = str(raw).split("|")
            if len(parts) < 2:
                return
            kind_name, asset_id = parts[0], parts[1]
            destination = parts[2] if len(parts) > 2 else "chart"
            chosen = crypto_watchlist if kind_name == "Crypto" else stock_watchlist if kind_name == "Stock" else None
            if not chosen or asset_id not in chosen:
                return
            st.session_state.scroll_target = "market-sentiment" if destination == "sentiment" else "interactive-chart"
            st.session_state.scroll_token = str(time.time_ns())
            if st.session_state.get("chart_pick") != (kind_name, asset_id):
                st.session_state.chart_pick = (kind_name, asset_id)
                st.session_state.chart_pick_from_row = True
            _rerun_fragment()

        c1, c2, c3, c4 = st.columns(4)

        def render_snapshot_card(title, name, score, pick, logo_url=None):
            color, bg, arrow, _bar = tone(score)
            score_str = f"{score:.1f}/100" if score is not None and not pd.isna(score) else "—"
            safe_title = html.escape(str(title))
            safe_name = html.escape(str(name))
            logo = asset_logo(logo_url, name) if name and name != "—" else ""
            body = (
                "<div style='background: white; padding: 12px 16px; border-radius: 8px; border: 1px solid #e5e7eb;'>"
                f"<div style='font-size: 0.8rem; color: #6b7280; margin-bottom: 4px;'>{safe_title}</div>"
                "<div style='display:flex;align-items:center;gap:8px;font-size:1.1rem;font-weight:600;"
                "color:#111827;margin-bottom:8px;white-space:nowrap;overflow:hidden;'>"
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

        show_snapshot(c1, "Top Crypto", crypto_top, "Crypto", "snapshot_crypto_top")
        show_snapshot(c2, "Weakest Crypto", crypto_bot, "Crypto", "snapshot_crypto_weak")
        show_snapshot(c3, "Top Stock", stock_top, "Stock", "snapshot_stock_top")
        show_snapshot(c4, "Weakest Stock", stock_bot, "Stock", "snapshot_stock_weak")
        st.caption("Click a box to open that asset on the chart.")

    def render_score_bar(score):
        if score is None or pd.isna(score):
            pct, color, label = 0, "#6b7280", "—"
        else:
            pct = max(0, min(100, float(score)))
            color = tone(score)[3]
            label = f"{score:.0f}"
        return (
            '<div style="display:flex;align-items:center;gap:8px;width:100%;min-width:100px;">'
            '<div style="flex:1;background:#e5e7eb;border-radius:6px;height:14px;overflow:hidden;">'
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
            st.caption("Click a column title to sort. The table starts with the strongest score at the top. Click a name to show that asset on the chart. Click a sentiment score to open its headlines. Watching is how many accounts hold that asset. The Crowd box is the average of personal scores. Hover the down thumb for the spread. A comment balloon, or the arrow on the right edge, opens the social signals stream. The 30-day trend uses the same colors as 30d %.")

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
                row_style = "background:#e5e7eb;color:#111827;" if selected else ""
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
                    f"<tr style='border-bottom:1px solid #f0f0f0;{row_style}'>"
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
                    f"<td data-sort='{sort_token((row.get('thumbs_up') or 0) - (row.get('thumbs_down') or 0), numeric=True)}' "
                    f"style='padding:10px 4px 10px 10px;text-align:right;white-space:nowrap;'>"
                    f"{crowd_mark(row.get('thumbs_up'), row.get('thumbs_down'), headline_score is not None, row.get('alt_count'), row.get('alt_avg'), row.get('alt_spread'))}</td>"
                    f"<td data-sort='{sort_token(row.get('alt_avg'), numeric=True)}' "
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
                "<table data-table='"
                f"{table_key}' style='width:100%;border-collapse:collapse;font-size:0.95rem;'>"
                f"<thead><tr style='border-bottom:2px solid #e5e7eb;'>{header_html}</tr></thead>"
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
        if chosen_asset in chosen_list:
            st.session_state.chart_pick = (chosen_kind, chosen_asset)
            st.session_state.chart_pick_from_row = True
        del st.query_params["chart_kind"]
        del st.query_params["chart_asset"]

    if "chart_pick" not in st.session_state:
        if crypto_watchlist:
            st.session_state.chart_pick = ("Crypto", next(iter(crypto_watchlist)))
        elif stock_watchlist:
            st.session_state.chart_pick = ("Stock", next(iter(stock_watchlist)))

    style_and_show_table(crypto_results, "Crypto Scores", "Crypto", "crypto_scores")
    style_and_show_table(stock_results, "Equity Scores", "Stock", "equity_scores")

    pick = st.session_state.get("chart_pick")
    if pick and (
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
        if kind not in ("Crypto", "Stock"):
            kind = "Crypto" if crypto_watchlist else "Stock"
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
    chart_logo = (st.session_state.get("asset_logos") or {}).get(asset_market_key(chart_kind, chart_asset))
    chart_label = f"Interactive Chart - {chart_name}" if chart_name else "Interactive Chart"
    st.html(
        "<div id='interactive-chart' style='scroll-margin-top:4.5rem;'></div>"
    )
    with section_expander(chart_label, "interactive_chart"):
        logo_col, _, chart_top = st.columns([0.35, 4.85, 0.9], vertical_alignment="center")
        with logo_col:
            if chart_name:
                st.markdown(asset_logo(chart_logo, chart_name, size=32), unsafe_allow_html=True)
        with chart_top:
            _back_to_top(key="chart_back_to_top")
        _scroll_chart(
            key="scroll_to_chart",
            data={
                "token": st.session_state.get("scroll_token") or "",
                "target": st.session_state.get("scroll_target") or "interactive-chart",
            },
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            asset_type = st.selectbox("Type", ["Crypto", "Stock"], key="asset_type")
        with col2:
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

        if asset_type == "Crypto":
            df_chart, chart_err = load_crypto(asset_key, history_days, nonce)
            title = crypto_watchlist[asset_key]
        else:
            df_chart, chart_err = load_stock(asset_key, history_days, nonce)
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
        with section_expander(f"Score Breakdown — {title}", "score_breakdown"):
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
                    st.plotly_chart(fig_contrib, width="stretch")
            with breakdown_col2:
                st.markdown("**Detailed Reasons**")
                for reason in result["reasons"]:
                    st.caption(f"• {reason}")

    sentiment_label = crypto_watchlist[asset_key] if asset_type == "Crypto" else stock_watchlist[asset_key]
    show_market_sentiment(
        asset_type,
        asset_key,
        sentiment_label,
        crypto_ticker(asset_key) if asset_type == "Crypto" else asset_key,
    )


def _store_sentiment_vote(kind: str, asset_id: str, sentiment_at, vote, alt_score=None) -> None:
    try:
        set_sentiment_vote(supabase, user_id, kind, asset_id, sentiment_at, vote, alt_score)
    except Exception:
        st.warning("That thumb could not be saved. Please try again.")
        return
    st.rerun()


def _store_sentiment_comment(
    kind: str, asset_id: str, sentiment_at, body: str, responded_score=None, responded_summary: str = "",
) -> None:
    try:
        set_sentiment_comment(
            supabase, user_id, kind, asset_id, sentiment_at, body, responded_score, responded_summary,
        )
    except Exception:
        st.warning("That comment could not be saved. Please try again.")
        return
    st.rerun()


def _sentiment_thumbs(
    kind: str, asset_id: str, sentiment_at, title: str, responded_score=None, responded_summary: str = "",
) -> None:
    """Agree or disagree, then one short comment. Disagree opens a score in the same box."""
    if not sentiment_at:
        st.caption("Thumbs and comments open once this sentiment is saved.")
        return
    key = asset_market_key(kind, asset_id)
    voice = sentiment_crowd(supabase, [key]).get(key) or {}
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
        .st-key-sentiment_alt_{selected} [data-testid="stBaseButton-primary"],
        .st-key-sentiment_alt_{selected} [data-testid="stBaseButton-primary"]:hover,
        .st-key-sentiment_alt_{selected} [data-testid="stBaseButton-primary"]:focus,
        .st-key-sentiment_alt_{selected} [data-testid="stBaseButton-primary"]:active {{
            background-color: {color};
            border-color: {color};
            color: #ffffff;
        }}
        .st-key-sentiment_alt_{selected} [data-testid="stBaseButton-primary"] p {{
            color: #ffffff;
        }}
        """
    st.html(
        f"""
        <style>
        [class*="st-key-market_sentiment_panel"] details[open] {{
            overflow: visible !important;
        }}
        .st-key-sentiment_take_box {{
            background: #ffffff;
            border: 1px solid #e5e7eb !important;
            border-radius: 10px !important;
            overflow: visible !important;
        }}
        .st-key-sentiment_agree,
        .st-key-sentiment_disagree {{
            position: relative;
            overflow: visible !important;
        }}
        .st-key-sentiment_agree:hover::after,
        .st-key-sentiment_disagree:hover::after {{
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
        .st-key-sentiment_agree:hover::after {{
            content: "You agree with this sentiment. Press again to clear it.";
        }}
        .st-key-sentiment_disagree:hover::after {{
            content: "You disagree with this sentiment. Press again to clear it.";
        }}
        .st-key-sentiment_agree [data-testid="stBaseButton-primary"],
        .st-key-sentiment_agree [data-testid="stBaseButton-primary"]:hover,
        .st-key-sentiment_agree [data-testid="stBaseButton-primary"]:focus,
        .st-key-sentiment_agree [data-testid="stBaseButton-primary"]:active {{
            background-color: #15803d;
            border-color: #15803d;
            color: #ffffff;
        }}
        .st-key-sentiment_agree [data-testid="stBaseButton-primary"] p {{
            color: #ffffff;
        }}
        .st-key-sentiment_take_box .stColumn {{
            min-width: 0 !important;
        }}
        .st-key-sentiment_comment_row {{
            margin-top: 6px;
        }}
        [class*="st-key-sentiment_face_"] button {{
            min-width: 0;
            padding: 0.15rem 0;
        }}
        [class*="st-key-sentiment_face_"] button p {{
            font-size: 1rem;
            line-height: 1.1;
        }}
        .st-key-sentiment_alt_0 button,
        .st-key-sentiment_alt_20 button,
        .st-key-sentiment_alt_40 button,
        .st-key-sentiment_alt_60 button,
        .st-key-sentiment_alt_80 button,
        .st-key-sentiment_alt_100 button {{
            min-width: 0;
            padding: 0.3rem 0;
        }}
        .st-key-sentiment_alt_0 button p,
        .st-key-sentiment_alt_20 button p,
        .st-key-sentiment_alt_40 button p,
        .st-key-sentiment_alt_60 button p,
        .st-key-sentiment_alt_80 button p,
        .st-key-sentiment_alt_100 button p {{
            font-size: 0.8rem;
        }}
        {selected_color}
        </style>
        """
    )
    with st.container(border=True, key="sentiment_take_box"):
        st.markdown("**Your take**")
        agree = st.button(
            "👍 Agree",
            key="sentiment_agree",
            use_container_width=True,
            type="primary" if mine == 1 else "secondary",
        )
        disagree = st.button(
            "👎 Disagree",
            key="sentiment_disagree",
            use_container_width=True,
            type="primary" if mine == -1 else "secondary",
        )
        if agree:
            _store_sentiment_vote(kind, asset_id, sentiment_at, None if mine == 1 else 1)
        elif disagree:
            _store_sentiment_vote(kind, asset_id, sentiment_at, None if mine == -1 else -1)
        if mine == -1:
            _sentiment_alt_score(kind, asset_id, sentiment_at, mine_score, selected)
        notes = sentiment_comment_lists(supabase, [key]).get(key) or []
        mine_text = next((item["text"] for item in notes if item.get("mine")), "")
        _comment_row(
            key="sentiment_comment_row",
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
        box_key = f"sentiment_comment_box_{key}"
        if box_key not in st.session_state:
            st.session_state[box_key] = mine_text
        pending_face = st.session_state.pop(f"{box_key}_face", None)
        if pending_face:
            st.session_state[box_key] = with_emoticon(st.session_state.get(box_key), pending_face)
        st.text_input(
            "Comment",
            max_chars=COMMENT_LIMIT,
            key=box_key,
            label_visibility="collapsed",
            placeholder="Add a short comment",
        )
        picked_face = None
        for index, (column, emoticon) in enumerate(
            zip(st.columns(len(COMMENT_EMOTICONS), gap="xxsmall", wrap=False), COMMENT_EMOTICONS)
        ):
            with column:
                if st.button(emoticon, key=f"sentiment_face_{index}", use_container_width=True):
                    picked_face = emoticon
        if picked_face:
            st.session_state[f"{box_key}_face"] = picked_face
            _rerun_fragment()
        st.caption(
            f"Up to {COMMENT_LIMIT} characters. Tap a face to add it. "
            "Posting again replaces yours. Each comment stays for 12 hours."
        )
        if st.button("Post comment", key="sentiment_comment_post", use_container_width=True):
            text = " ".join(str(st.session_state.get(box_key) or "").split())
            if text or mine_text:
                _store_sentiment_comment(
                    kind, asset_id, sentiment_at, text, responded_score, responded_summary,
                )


def _sentiment_alt_score(kind: str, asset_id: str, sentiment_at, mine_score, selected) -> None:
    """Score controls under Disagree. A clicked or typed number saves on its own."""
    st.markdown("**Your score**")
    picked = None
    for column, value in zip(st.columns(6, gap="xxsmall", wrap=False), (0, 20, 40, 60, 80, 100)):
        with column:
            if st.button(
                str(value),
                key=f"sentiment_alt_{value}",
                use_container_width=True,
                type="primary" if selected == value else "secondary",
            ):
                picked = value
    typed_key = f"sentiment_alt_typed_{asset_market_key(kind, asset_id)}"
    if picked is not None:
        st.session_state[typed_key] = int(picked)
    elif typed_key not in st.session_state and mine_score is not None:
        st.session_state[typed_key] = int(mine_score)
    number_kwargs = {
        "min_value": 0,
        "max_value": 100,
        "step": 1,
        "key": typed_key,
        "placeholder": "0–100",
    }
    if typed_key not in st.session_state:
        number_kwargs["value"] = None
    typed = st.number_input("Your score", label_visibility="collapsed", **number_kwargs)
    stored = None if mine_score is None else int(mine_score)
    if typed is not None and int(typed) != stored:
        _store_sentiment_vote(kind, asset_id, sentiment_at, -1, int(typed))


def _published_label(value) -> str:
    """Turn an RSS pubDate into a calendar date. Empty when the feed omitted one."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError, OverflowError):
        return ""
    return f"{when.strftime('%b')} {when.day}, {when.year}"


@st.fragment
def show_market_sentiment(kind: str, asset_id: str, label: str, ticker: str | None):
    """Headline sentiment for the asset on the chart. Shared for 12 hours."""
    query = sentiment_query(kind, label, ticker)
    stored = load_shared_market(supabase, [asset_market_key(kind, asset_id)]).get(
        asset_market_key(kind, asset_id)
    )
    if st.session_state.get("sentiment_force") != query:
        report, stored_at = sentiment_from_row(stored)
        if report and stored_at is not None:
            remember_sentiment(query, report, stored_at)
    st.html("<div id='market-sentiment' style='scroll-margin-top:4.5rem;'></div>")
    shown_name = " ".join((label or "").split())
    if kind == "Stock" and ticker and ticker.upper() not in shown_name.upper():
        shown_name = f"{shown_name} ({ticker})" if shown_name else ticker
    sentiment_heading = f"Market sentiment - {shown_name}" if shown_name else "Market sentiment"
    sentiment_logo = (stored or {}).get("logo_url") if isinstance(stored, dict) else ""
    if not sentiment_logo:
        sentiment_logo = (st.session_state.get("asset_logos") or {}).get(asset_market_key(kind, asset_id))
    with section_expander(sentiment_heading, "market_sentiment_panel"):
        logo_col, _, sentiment_refresh, sentiment_top = st.columns([0.35, 2.8, 1.45, 0.85], vertical_alignment="center")
        with logo_col:
            if shown_name:
                st.markdown(asset_logo(sentiment_logo, shown_name, size=32), unsafe_allow_html=True)
        sentiment_deadlines = st.session_state.setdefault("sentiment_due", {})
        if query not in sentiment_deadlines:
            cached_at = sentiment_cached_at(query)
            sentiment_deadlines[query] = (
                cached_at + SENTIMENT_REFRESH_SECONDS
                if cached_at
                else time.time() + SENTIMENT_REFRESH_SECONDS
            )
        with sentiment_refresh:
            sentiment_now = st.button(
                "🔄 Refresh",
                key="refresh_sentiment",
                use_container_width=True,
                help="Pull fresh headlines and a new sentiment score for this asset. This also runs on its own when the timer reaches zero.",
            )
            sentiment_due = _countdown_due(sentiment_deadlines[query], "sentiment_countdown")
            if sentiment_now or sentiment_due:
                sentiment_deadlines[query] = time.time() + SENTIMENT_REFRESH_SECONDS
                st.session_state.sentiment_force = query
                _rerun_fragment()
        with sentiment_top:
            _back_to_top(key="sentiment_back_to_top")
        force_sentiment = st.session_state.get("sentiment_force") == query
        if force_sentiment:
            st.session_state.sentiment_force = None
        cached_before = sentiment_cached_at(query)
        with st.spinner("Reading recent headlines..."):
            report = load_market_sentiment(query, sentiment_ready(), force=force_sentiment)
        cached_after = sentiment_cached_at(query)
        if report.get("ok") and cached_after and cached_after != cached_before:
            save_sentiment(supabase, kind, asset_id, report, cached_after)
            st.rerun(scope="app")

        headlines = newest_first(report.get("headlines") or [])
        score = report.get("score")
        if report.get("ok") and score is not None:
            color, background, arrow, _bar = tone(score)
            if score >= 60:
                coverage = "Bullish coverage"
            elif score >= 53:
                coverage = "Mildly bullish coverage"
            elif score >= 47:
                coverage = "Mixed coverage"
            elif score >= 40:
                coverage = "Mildly bearish coverage"
            else:
                coverage = "Bearish coverage"
            summary = html.escape(report.get("summary") or "")

            def side_note(label, text, label_color):
                cleaned = " ".join(str(text or "").split())
                if not cleaned:
                    return ""
                return (
                    "<div style='margin-top:12px;'>"
                    f"<div style='font-size:0.75rem;font-weight:700;color:{label_color};'>{label}</div>"
                    f"<div style='margin-top:4px;color:#111827;'>{html.escape(cleaned)}</div>"
                    "</div>"
                )

            sides_html = side_note("Positive", report.get("positive"), "#15803d") + side_note(
                "Negative", report.get("negative"), "#b91c1c"
            )
            driver_items = "".join(
                f"<li style='margin:4px 0;color:#374151;'>{html.escape(str(driver))}</li>"
                for driver in (report.get("drivers") or [])
            )
            drivers_html = (
                f"<ul style='margin:10px 0 0;padding-left:1.15rem;'>{driver_items}</ul>"
                if driver_items else ""
            )
            sentiment_at = (stored or {}).get("sentiment_updated_at") if isinstance(stored, dict) else None
            score_card, vote_card = st.columns([3.5, 2.1], vertical_alignment="top")
            with score_card:
                st.markdown(
                    "<div style='background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px;'>"
                    "<div style='font-size:0.8rem;color:#6b7280;margin-bottom:4px;'>"
                    + (
                        "Average of the article scores below, from the last 7 days"
                        if any(item.get("score") is not None for item in headlines)
                        else "Score for these headlines, from the last 7 days"
                    )
                    + "</div>"
                    f"<div style='display:inline-flex;align-items:center;gap:6px;background:{background};color:{color};"
                    f"padding:2px 8px;border-radius:4px;font-weight:600;'>{arrow} {score:.0f}/100</div>"
                    f"<div style='margin-top:8px;font-weight:600;color:{color};'>{html.escape(coverage)}</div>"
                    f"<div style='margin-top:8px;color:#111827;'>{summary}</div>"
                    f"{drivers_html}{sides_html}</div>",
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
            rows = [
                "<div style='display:flex;align-items:center;gap:16px;padding:4px 0 8px;'>"
                "<div style='flex:1;font-size:0.8rem;font-weight:600;color:#6b7280;'>Article</div>"
                "<div style='width:112px;flex:none;text-align:right;font-size:0.8rem;font-weight:600;color:#6b7280;'>Published</div>"
                "<div style='width:76px;flex:none;text-align:right;font-size:0.8rem;font-weight:600;color:#6b7280;'>Score</div>"
                "</div>"
            ]
            for item in headlines:
                source = f" — {html.escape(item['source'])}" if item.get("source") else ""
                published = _published_label(item.get("published"))
                published_html = (
                    html.escape(published)
                    if published
                    else "<span style='color:#6b7280;'>—</span>"
                )
                badge = sentiment_badge(item.get("score"))
                rows.append(
                    "<div style='display:flex;align-items:center;gap:16px;padding:8px 0;border-top:1px solid #f3f4f6;'>"
                    "<div style='flex:1;min-width:0;'>"
                    f"<a href='{html.escape(item['link'], quote=True)}' target='_blank' rel='noopener noreferrer'>"
                    f"{html.escape(item['title'])}</a>{source}</div>"
                    f"<div style='width:112px;flex:none;text-align:right;white-space:nowrap;color:#4b5563;'>{published_html}</div>"
                    f"<div style='width:76px;flex:none;text-align:right;'>{badge}</div></div>"
                )
            st.html(f"<div style='margin-top:10px;'>{''.join(rows)}</div>")
        st.caption("This reads recent coverage. It is not the technical score, and it is not advice.")


render_dashboard(
    CRYPTO_WATCHLIST,
    STOCK_WATCHLIST,
    days_history,
    current_weights,
    show_reasons,
    show_extra_metrics,
    show_period_changes,
)

st.sidebar.markdown("---")
st.sidebar.info("Prices and technical scores refresh every 5 minutes while this page is open. Market sentiment refreshes about every 12 hours. Alert checks continue every 5 minutes after you leave.")
st.sidebar.caption("Watchlists, settings, and alerts are stored on your account.")
