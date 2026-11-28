"""The two emails a beta applicant can get: a seat, or a polite no. Used by the dashboard and the alert worker."""
from __future__ import annotations

import html

from email_brand import render_email


def _first_name(name: str) -> str:
    words = " ".join(str(name or "").split()).split(" ")
    return html.escape(words[0]) if words and words[0] else "there"


def welcome_email(name: str, app_url: str, nda: bool | None = None, link: str = "") -> tuple[str, str, str]:
    """(subject, html, plain text) for an applicant who got a seat. With link (their own one-time sign-in link from
    the worker), the button sets their password and takes them straight in; without it, the button opens the app.
    When the beta NDA is switched on, the email says it is signed at the first sign-in."""
    if nda is None:
        try:
            import nda as nda_module

            current = nda_module.current()
            nda = bool(current and current["enforce"])
        except Exception:
            nda = False
    if link:
        how = ("Press <strong>Set your password</strong> below: it opens MarketNavi, you choose a password, and you "
               "are in. The button works once, for 24 hours; after that, use <strong>Forgot password?</strong> on "
               "the sign-in page. Or simply choose <strong>Continue with Google</strong> there with this email address.")
    else:
        how = ("Open MarketNavi, then choose <strong>Continue with Google</strong> with this email address, or "
               "<strong>Forgot password?</strong> to set a password for it.")
    extra = (["When you first sign in, you will be asked to read and sign the beta non-disclosure agreement "
              "(a minute, once). You will get a signed copy by email."] if nda else [])
    page, plain = render_email(
        "You are in",
        [f"Hi {_first_name(name)}, thank you for applying. You have a seat in the MarketNavi closed beta.", how]
        + extra + [
            "It is free for accepted beta traders. Seats are limited, and we would love your honest "
            "feedback: use the Feedback box in the app. If we introduce paid tiers later, we will "
            "give at least 30 days' notice.",
        ],
        button=("Set your password", link) if link else ("Open MarketNavi", app_url),
        tone="up",
        preheader="Your seat in the MarketNavi closed beta is ready.",
    )
    return "You are in: MarketNavi closed beta", page, plain


def barred_email(inbox: str = "support@marketnavi.ai") -> tuple[str, str, str]:
    """(subject, html, plain text) for an address an admin has barred."""
    import html

    page, plain = render_email(
        "Your account is barred",
        ["Your MarketNavi account is barred at this time.",
         f'You can email <a href="mailto:{html.escape(inbox, quote=True)}" style="color:#1d5fd1;">{html.escape(inbox)}</a>.'],
        tone="down")
    return "Your MarketNavi account is barred", page, plain


def declined_email(name: str) -> tuple[str, str, str]:
    """(subject, html, plain text) for an applicant we cannot offer a seat to right now."""
    page, plain = render_email(
        "Thank you for applying",
        [
            f"Hi {_first_name(name)}, thank you for applying to the MarketNavi closed beta, and for "
            "taking the time to tell us about your trading.",
            "We have a small number of seats while we build with a handful of experienced traders, and we are "
            "not able to offer you one in this round. That is not a judgement on you or your trading.",
            "You are welcome to apply again later, and we will announce it on marketnavi.ai when more "
            "places open.",
        ],
        tone="info",
        preheader="An update on your MarketNavi beta request.",
    )
    return "Your MarketNavi beta request", page, plain
