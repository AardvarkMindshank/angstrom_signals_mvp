"""Start the "Study this Set" job on GitHub now, instead of waiting for GitHub's timer (which is best-effort and
often hours late on the free plan).

The app asks GitHub to run .github/workflows/set-studies.yml when a study is queued, and again (at most every 10
minutes) while a queued study is on screen. It needs GITHUB_DISPATCH_TOKEN in the app's environment: a fine-grained
GitHub token for this repository with only "Actions: read and write". Without it nothing happens and the timer still
picks the study up, as before. Extra nudges are harmless: the workflow runs one at a time and an empty queue stops at
its first step.
"""

from __future__ import annotations

import os
import time

import requests

REPO = "AardvarkMindshank/angstrom_signals_mvp"
WORKFLOW = "set-studies.yml"
QUIET = 600                      # seconds between nudges from a page that shows a queued study
_last = [0.0]


def token() -> str:
    return (os.getenv("GITHUB_DISPATCH_TOKEN") or "").strip().strip('"').strip("'")


def run_workflow(workflow: str, inputs: dict | None = None, post=requests.post) -> bool:
    """Ask GitHub to run one of this repository's workflows now (it must allow workflow_dispatch). True when GitHub
    accepted; False without GITHUB_DISPATCH_TOKEN or on any error. Never raises."""
    key = token()
    if not key:
        return False
    body = {"ref": "main"}
    if inputs:
        body["inputs"] = {k: str(v) for k, v in inputs.items()}
    try:
        r = post(f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow}/dispatches", timeout=10,
                 headers={"Authorization": f"Bearer {key}", "Accept": "application/vnd.github+json",
                          "X-GitHub-Api-Version": "2022-11-28"},
                 json=body)
        return r.status_code == 204
    except Exception:
        return False


def run_funnel_now(funnel_id: str, post=requests.post) -> bool:
    """Check one funnel straight away (after a save, restart or resume) instead of at the next hourly run."""
    return bool(funnel_id) and run_workflow("funnel.yml", {"funnel_id": funnel_id}, post=post)


def nudge(force: bool = True, post=requests.post, now=time.time) -> bool:
    """Ask GitHub to run the studies now. True when GitHub accepted. Never raises."""
    key = token()
    if not key or (not force and now() - _last[0] < QUIET):
        return False
    _last[0] = now()
    try:
        r = post(f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches", timeout=10,
                 headers={"Authorization": f"Bearer {key}", "Accept": "application/vnd.github+json",
                          "X-GitHub-Api-Version": "2022-11-28"},
                 json={"ref": "main"})
        return r.status_code == 204
    except Exception:
        return False
