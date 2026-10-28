"""The two emails a beta applicant can get: a seat, or a polite no. Used by the dashboard and the alert worker."""
from __future__ import annotations

import html

from email_brand import render_email


def _first_name(name: str) -> str:
    words = " ".join(str(name or "").split()).split(" ")
    return html.escape(words[0]) if words and words[0] else "there"


def welcome_email(name: str, app_url: str) -> tuple[str, str, str]:
    """(subject, html, plain text) for an applicant who got a seat."""
    page, plain = render_email(
        "You are in",
        [
            f"Hi {_first_name(name)}, thank you for applying. You have a seat in the Angstrom Signals closed beta.",
            "Open the dashboard, then either choose <strong>Continue with Google</strong> with this email "
            "address, or open the <strong>Beta Access Accepted?</strong> tab and create a password for this "
            "email address.",
            "It is free for accepted beta traders. Seats are limited, and we would love your honest "
            "feedback: use the Feedback box in the sidebar. If we introduce paid tiers later, we will "
            "give at least 30 days' notice.",
        ],
        button=("Open the dashboard", app_url),
        tone="up",
        preheader="Your seat in the Angstrom Signals closed beta is ready.",
    )
    return "You are in: Angstrom Signals closed beta", page, plain


def declined_email(name: str) -> tuple[str, str, str]:
    """(subject, html, plain text) for an applicant we cannot offer a seat to right now."""
    page, plain = render_email(
        "Thank you for applying",
        [
            f"Hi {_first_name(name)}, thank you for applying to the Angstrom Signals closed beta, and for "
            "taking the time to tell us about your trading.",
            "We have a small number of seats while we build with a handful of experienced traders, and we are "
            "not able to offer you one in this round. That is not a judgement on you or your trading.",
            "You are welcome to apply again later, and we will announce it on angstromsignals.com when more "
            "places open.",
        ],
        tone="info",
        preheader="An update on your Angstrom Signals beta request.",
    )
    return "Your Angstrom Signals beta request", page, plain
