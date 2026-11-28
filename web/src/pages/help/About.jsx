import React from "react";
import { T } from "../../lib/i18n.js";
import Icon from "../../components/Icon.jsx";

// ℹ️ About: what MarketNavi is, how to reach us, the socials policy (the rules for comments and chat, kept here in
// every language), and the full terms and policies, which live on the website (in English) so there is one version.
const SITE = "https://marketnavi.ai/";
export const LEGAL = () => [
  ["terms.html", T("Terms of use"), "file-text"],
  ["privacy.html", T("Privacy"), "lock"],
  ["disclaimer.html", T("Not financial advice"), "triangle-exclamation-point"],
  ["refund.html", T("Refund policy"), "receipt"],
];

export default function About() {
  return (
    <div className="about">
      <div className="aboutbrand">
        <img src={`${import.meta.env.BASE_URL}icons/icon-192.png`} alt="" width="56" height="56" />
        <div><b>MarketNavi</b><span className="m">{T("Navigate the markets with AI-guided analysis and alerts, with a community alongside.")}</span></div>
      </div>
      <p>{T("MarketNavi is a platform for traders who want aggregated signals for whole markets and for individual assets. Technical scores and market sentiment sit together and update as conditions change. A real-time social stream lets the community react alongside those signals.")}</p>
      <div className="contacts">
        <span><Icon n="mail" size={15} /> {T("General")}: <a href="mailto:info@marketnavi.ai">info@marketnavi.ai</a></span>
        <span><Icon n="life-buoy" size={15} /> {T("Support")}: <a href="mailto:support@marketnavi.ai">support@marketnavi.ai</a></span>
      </div>

      <h3 className="rowtitle">{T("Socials policy")}</h3>
      <ul className="policy">
        <li>{T("The comments and the chat are for reacting to the markets and the readings in MarketNavi.")}</li>
        <li>{T("Nothing on this site is financial advice. A comment, a reply, a thumb, or a community score is one person's reaction. It is not a recommendation to buy, sell, or hold any asset.")}</li>
        <li>{T("Do not promote an asset. That includes telling people to buy or sell, posting a tip or a referral link, or pushing a coin or ticker the note is not answering.")}</li>
        <li>{T("Be civil. No harassment, threats, or personal attacks. No spam, and no posting the same note over and over.")}</li>
        <li>{T("Use the flag beside a comment that breaks these rules. Only the MarketNavi team sees reports. A comment that breaks the rules can be removed and its writer warned, and an account that keeps breaking them can be closed.")}</li>
      </ul>

      <h3 className="rowtitle">{T("Terms and policies")}</h3>
      <p className="sub">{T("Using MarketNavi means you accept the terms of use and the socials policy above. The full versions are on our website, in English.")}</p>
      <div className="legal">
        {LEGAL().map(([page, label, icon]) => (
          <a key={page} className="ghost bordered" href={SITE + page} target="_blank" rel="noopener noreferrer"><Icon n={icon} size={16} /> {label} <Icon n="external-link" size={13} tone={false} /></a>
        ))}
      </div>
    </div>
  );
}
