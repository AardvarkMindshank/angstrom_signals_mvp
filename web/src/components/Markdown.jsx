import React from "react";
import { Glyphs } from "./Icon.jsx";

// A small Markdown reader for the help texts (the classic app's, written for Streamlit): paragraphs, "- " and "1. "
// lists whose wrapped lines are indented, # headings (two levels smaller, under the page's own), "| a | b |" tables, **bold**, *italic* and `code`. Emoji become the app's
// icons (Glyphs). No HTML is taken from the text.
function inline(s, key = 0) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)/g;
  let last = 0, m, k = key;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(<Glyphs key={k++} text={s.slice(last, m.index)} />);
    const t = m[0];
    out.push(t.startsWith("**") ? <b key={k++}>{inline(t.slice(2, -2), k * 100)}</b>
      : t.startsWith("`") ? <code key={k++}>{t.slice(1, -1)}</code> : <i key={k++}>{inline(t.slice(1, -1), k * 100)}</i>);
    last = m.index + t.length;
  }
  if (last < s.length) out.push(<Glyphs key={k++} text={s.slice(last)} />);
  return out;
}

export default function Markdown({ text }) {
  const lines = String(text || "").replace(/\r/g, "").split("\n");
  const blocks = [];
  let cur = null;
  const close = () => { if (cur) blocks.push(cur); cur = null; };
  for (const raw of lines) {
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) { close(); continue; }
    const bullet = /^\s{0,3}[-*•]\s+(.*)/.exec(line), num = /^\s{0,3}(\d+)[.)]\s+(.*)/.exec(line), row = /^\s*\|(.*)\|\s*$/.exec(line);
    const head = /^(#{1,6})\s+(.*)/.exec(line);
    if (head) { close(); blocks.push({ kind: "h", level: head[1].length, text: head[2] }); continue; }
    if (row) {
      if (/^[\s|:-]+$/.test(row[1])) continue;                       // the |---|---| line
      if (!cur || cur.kind !== "table") { close(); cur = { kind: "table", rows: [] }; }
      cur.rows.push(row[1].split("|").map((c) => c.trim()));
    } else if (bullet || num) {
      const kind = bullet ? "ul" : "ol";
      if (!cur || cur.kind !== kind) { close(); cur = { kind, items: [] }; }
      cur.items.push(bullet ? bullet[1] : num[2]);
    } else if (cur && (cur.kind === "ul" || cur.kind === "ol") && /^\s+\S/.test(line)) {
      cur.items[cur.items.length - 1] += " " + line.trim();       // a wrapped list line
    } else {
      if (!cur || cur.kind !== "p") { close(); cur = { kind: "p", text: line.trim() }; } else cur.text += " " + line.trim();
    }
  }
  close();
  return (
    <div className="md">
      {blocks.map((b, i) => b.kind === "ul" ? <ul key={i}>{b.items.map((x, j) => <li key={j}>{inline(x)}</li>)}</ul>
        : b.kind === "ol" ? <ol key={i}>{b.items.map((x, j) => <li key={j}>{inline(x)}</li>)}</ol>
        : b.kind === "table" ? (
          <div key={i} className="mdtable"><table>
            <thead><tr>{b.rows[0].map((c, j) => <th key={j}>{inline(c)}</th>)}</tr></thead>
            <tbody>{b.rows.slice(1).map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{inline(c)}</td>)}</tr>)}</tbody>
          </table></div>
        ) : b.kind === "h" ? React.createElement(`h${Math.min(6, b.level + 2)}`, { key: i, className: "mdh" }, inline(b.text))
        : <p key={i}>{inline(b.text)}</p>)}
    </div>
  );
}
