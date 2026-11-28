import React, { useEffect, useState } from "react";
import Icon, { Tile } from "../../components/Icon.jsx";
import { T } from "../../lib/i18n.js";
import { supabase } from "../../lib/supabase.js";
import News from "../asset/News.jsx";
import Community from "../asset/Community.jsx";

// 🌤️ Market sentiment: the crypto market's and the stock market's news mood, read like an asset's news (the same
// report shape), with the members' take and comments. Shared by everyone, updated about every 12 hours.
const shown = (s) => (s == null ? null : Math.round((Number(s) - 50) * 2));     // stored 0..100, shown -100..+100

export default function Mood({ market: wanted, account }) {
  const settings = (account && account.settings) || {};
  const trades = { crypto: settings.trade_crypto !== false, stock: settings.trade_equities !== false };
  const market = wanted === "stock" ? "stock" : "crypto";
  const [row, setRow] = useState(undefined);
  useEffect(() => {
    let live = true; setRow(undefined);
    supabase.from("market_mood").select("market_key, sentiment_report, sentiment_updated_at").eq("market_key", market).limit(1)
      .then(({ data }) => live && setRow((data || [])[0] || null), () => live && setRow(null));
    return () => { live = false; };
  }, [market]);
  const rep = row && row.sentiment_report && typeof row.sentiment_report === "object" ? row.sentiment_report : null;
  const score = rep && rep.ok ? shown(rep.score) : null;
  const votes = {
    crowd: async () => {
      try { const { data } = await supabase.rpc("market_mood_crowd", { market_keys: [market] }); const r = (data || [])[0] || {};
        return { up: +r.thumbs_up || 0, down: +r.thumbs_down || 0, mine: r.my_vote == null ? null : +r.my_vote };
      } catch (e) { return { up: 0, down: 0, mine: null }; }
    },
    vote: async (v) => {
      const { data: u } = await supabase.auth.getUser();
      if (v !== 1 && v !== -1) { const { error } = await supabase.from("market_mood_votes").delete().eq("user_id", u.user.id).eq("market_key", market); if (error) throw error; return; }
      const { error } = await supabase.from("market_mood_votes").upsert({ user_id: u.user.id, market_key: market, sentiment_at: row.sentiment_updated_at, vote: v, alt_score: null }, { onConflict: "user_id,market_key" });
      if (error) throw error;
    },
  };
  return (
    <div className="page">
      <div className="bar">
        <h1 className="ptitle" style={{ marginRight: "auto" }}><Tile n={market === "crypto" ? "coins" : "trending-up"} size={22} /> {T("Market sentiment")}</h1>
        {trades.crypto && trades.stock && (
          <div className="seg" role="tablist" aria-label={T("Market")}>
            <a role="tab" aria-selected={market === "crypto"} className={"segl" + (market === "crypto" ? " on" : "")} href="#mood/crypto">{T("Crypto market")}</a>
            <a role="tab" aria-selected={market === "stock"} className={"segl" + (market === "stock" ? " on" : "")} href="#mood/stock">{T("Stock market")}</a>
          </div>
        )}
      </div>
      <p className="sub">{T("Market sentiment is shared by everyone and updated about every 12 hours.")}</p>
      {row === undefined ? <div className="empty" style={{ height: 240 }}>{T("Loading…")}</div> : (
        <>
          <News rep={rep} score={score} at={row && row.sentiment_updated_at} />
          {row && <Community key={market} row={{ asset_key: market === "crypto" ? "Mood|crypto" : "Mood|stock", sentiment_updated_at: row.sentiment_updated_at, sentiment_report: rep || {} }}
            score={score} votes={votes} about={T("This market's news hasn't been scored yet.")} />}
        </>
      )}
    </div>
  );
}
