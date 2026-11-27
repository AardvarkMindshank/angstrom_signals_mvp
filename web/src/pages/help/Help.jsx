import React, { useEffect, useState } from "react";
import { T, lang, noEmoji } from "../../lib/i18n.js";
import Icon from "../../components/Icon.jsx";
import Markdown from "../../components/Markdown.jsx";
import { showAgain } from "../../components/GettingStarted.jsx";

// 📖 Help and guides: the topics down the left (as Settings), each the same explanation the classic app gives, in
// the member's language (web/scripts/help.py writes them at build time), and the training videos.
// The topics' icons (named in web/scripts/help.py), listed so web/scripts/icons.py copies them.
export const HELP_ICONS = ["rocket", "trending-up", "chart-column", "newspaper", "waves-horizontal", "puzzle", "funnel", "bell", "message-circle", "clapperboard"];
let cache = null;
const load = () => (cache = cache || fetch(`${import.meta.env.BASE_URL}help/${lang}.json`).then((r) => (r.ok ? r.json() : fetch(`${import.meta.env.BASE_URL}help/en.json`).then((x) => x.json())))
  .catch(() => { cache = null; return null; }));

export default function Help({ topic, account }) {
  const [d, setD] = useState(null);
  const [video, setVideo] = useState(null);
  useEffect(() => { load().then(setD); }, []);
  if (!d) return <div className="page"><div className="empty" style={{ height: 300 }}>{T("Loading…")}</div></div>;
  const all = [...d.topics, { key: "videos", title: T("Training videos"), icon: "clapperboard" }];
  const on = all.some((x) => x.key === topic) ? topic : "start";
  const cur = all.find((x) => x.key === on);
  return (
    <div className="settings help">
      <nav className="snav" aria-label={T("Help and guides")}>
        <h1>{T("Help and guides")}</h1>
        {all.map((x) => (
          <a key={x.key} href={`#help/${x.key}`} className={on === x.key ? "on" : ""} aria-current={on === x.key ? "page" : undefined}>
            <Icon n={x.icon} /> {noEmoji(x.title)}
          </a>
        ))}
      </nav>
      <div className="sbody">
        <h2 className="helph"><Icon n={cur.icon} /> {noEmoji(cur.title)}</h2>
        {on === "videos" ? <Videos series={d.videos} play={setVideo} />
          : cur.blocks.map((b, i) => <Markdown key={i} text={b} />)}
        {on === "start" && (
          <button type="button" className="ghost bordered" onClick={async () => { await showAgain(account); window.location.hash = "snapshot"; window.location.reload(); }}
            title={T("Brings back the checklist at the top of the page.")}><Icon n="rocket" size={16} /> {T("🚀 Show the getting-started checklist")}</button>
        )}
        <p className="sub">{T("Descriptive readings, not financial advice.")}</p>
      </div>
      {video && <Player video={video} series={d.videos} onClose={() => setVideo(null)} onPick={setVideo} />}
    </div>
  );
}

function Videos({ series, play }) {
  return (
    <>
      <p className="sub">{T("Short videos with captions, about a minute or two each. Recorded in the classic app, so some screens look different, but the ideas are the same.")}</p>
      <div className="vgrid">
        {series.map((s) => (
          <section key={s.key} className="vseries">
            <div className="rowtitle">{s.name}</div>
            {s.videos.map((v) => (
              <button key={v.slug} type="button" className="vlink" onClick={() => play({ ...v, series: s.key })}>
                <Icon n="play" size={15} /> <span>{v.title}</span> <span className="m">{v.length}</span>
              </button>
            ))}
          </section>
        ))}
      </div>
    </>
  );
}

function Player({ video, series, onClose, onPick }) {
  const list = (series.find((s) => s.key === video.series) || { videos: [] }).videos;
  const i = list.findIndex((v) => v.slug === video.slug);
  const go = (n) => list[n] && onPick({ ...list[n], series: video.series });
  useEffect(() => { const k = (e) => e.key === "Escape" && onClose(); window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, []);
  return (
    <div className="dvpop" onClick={onClose}>
      <div className="dvbox" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="ghost icon dvclose" onClick={onClose} aria-label={T("Close")}><Icon n="x" /></button>
        <video key={video.slug} src={video.url} controls autoPlay playsInline />
        <div className="bar" style={{ marginTop: 10, color: "#fff" }}>
          <button type="button" className="ghost" disabled={i <= 0} onClick={() => go(i - 1)} style={{ color: "#fff" }}><Icon n="chevron-left" /> {T("Back")}</button>
          <b style={{ flex: 1, textAlign: "center" }}>{video.title} · {i + 1}/{list.length}</b>
          <button type="button" className="ghost" disabled={i >= list.length - 1} onClick={() => go(i + 1)} style={{ color: "#fff" }}>{T("Next")} <Icon n="chevron-right" /></button>
        </div>
      </div>
    </div>
  );
}
