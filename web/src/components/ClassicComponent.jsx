import React, { useEffect, useRef } from "react";
import { allWords } from "../lib/i18n.js";
import { watchIcons } from "./Icon.jsx";

// Hosts one of the classic app's interactive editors (web/src/generated/, copied from the classic app's Python files
// by web/scripts/components.py) inside the new app. The editor is the same JavaScript the classic app runs: it draws
// itself into the element it is given, reads its words from data.tr, and reports changes through setTriggerValue,
// exactly as Streamlit's components do. A change to `data` draws it again in place (its own state, such as a drag
// in progress or the search box, is kept by the editor on the same component object).
const styled = new Set();

export default function ClassicComponent({ fn, css, data, onTrigger, className }) {
  const box = useRef(null);
  const comp = useRef(null);
  const trig = useRef(onTrigger);
  trig.current = onTrigger;
  useEffect(() => {
    if (css && !styled.has(css)) {
      styled.add(css);
      const st = document.createElement("style");
      // The classic night mode is html.angstrom-night; the new app's is html.night.
      st.textContent = css.replace(/html\.angstrom-night/g, "html.night");
      document.head.appendChild(st);
    }
  }, [css]);
  useEffect(() => watchIcons(box.current), []);   // its emoji become the app's icons, as it draws
  useEffect(() => {
    if (!box.current || !data) return;
    if (!comp.current) comp.current = { parentElement: box.current, setTriggerValue: (name, value) => trig.current && trig.current(name, value) };
    comp.current.data = { ...data, tr: allWords() };
    try { fn(comp.current); } catch (e) { console.error("editor", e); }
  }, [data, fn]);
  return <div ref={box} className={"classic " + (className || "")} />;
}
