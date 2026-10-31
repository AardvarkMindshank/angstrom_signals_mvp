"""Durable record of hold-out attempts, kept on the reports branch at holdout/attempts.json.

An attempt is CLAIMED (written and pushed) before any price is read. A claim is atomic: the push is a normal
fast-forward, so if two runs race, one push is rejected; the loser re-reads the record, now sees the winner's
attempt, and is refused. When a run ends (however it ends), FINISH records the last stage it reached.

Policy (validation spec, section 12.8):
- No attempt yet: a first attempt is allowed.
- Any attempt that reached outputs_written: refused for ever. The hold-out has been run.
- The latest attempt did not reach outputs_written (crash, cancelled runner, failed check): another attempt is
  allowed only as an explicit RECOVERY naming that attempt's run id, typed by a person, and only from the same
  signed-off tag and spec hash. At most MAX_ATTEMPTS attempts in total. Every attempt and its last stage is
  printed in the final report.
- Recovery cannot change the result: code (tag), configuration (spec hash), prices (checksums), packages (lock)
  and random seeds are all fixed, so a re-run computes the same numbers.

Usage:
    holdout_attempts.py claim  --run-id ID --run-attempt N --commit SHA --spec-hash H [--recovery-of ID]
    holdout_attempts.py finish --run-id ID --stage-log out/stage.log
    holdout_attempts.py show   [--out file]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

RECORD = "holdout/attempts.json"
BRANCH = "reports"
MAX_ATTEMPTS = 3
COMPLETE = "outputs_written"


def decide(attempts: list[dict], recovery_of: str | None) -> tuple[bool, str]:
    if any(a.get("final_stage") == COMPLETE for a in attempts):
        return False, "The hold-out has already produced results. It runs once."
    if not attempts:
        if recovery_of:
            return False, "There is no earlier attempt to recover."
        return True, "first attempt"
    latest = attempts[-1]
    if not recovery_of:
        return False, (f"Attempt {latest['run_id']} exists (last stage: {latest.get('final_stage') or 'unknown, '
                       'still running or the runner died'}). A new run must be an explicit recovery of it.")
    if recovery_of != latest["run_id"]:
        return False, f"Recovery must name the latest attempt, {latest['run_id']}."
    if len(attempts) >= MAX_ATTEMPTS:
        return False, f"{MAX_ATTEMPTS} attempts already; no further recovery without a new signed-off spec."
    return True, f"recovery of {recovery_of}"


def _git(*args, cwd=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)


def _read(worktree: Path) -> list[dict]:
    path = worktree / RECORD
    return json.loads(path.read_text()) if path.exists() else []


def _update(repo: str, change, message: str, remote: str = "origin", before_push=None, tries: int = 6):
    """Fetch the branch, apply change(attempts) -> (attempts or None, info), commit and push. Retries on a
    rejected push by starting again from the new branch head."""
    for _ in range(tries):
        _git("fetch", "-q", remote, BRANCH, cwd=repo)
        with tempfile.TemporaryDirectory() as tmp:
            wt = Path(tmp) / "wt"
            _git("worktree", "add", "-q", "--detach", str(wt), "FETCH_HEAD", cwd=repo)
            try:
                attempts = _read(wt)
                new, info = change(attempts)
                if new is None:
                    return False, info
                (wt / RECORD).parent.mkdir(parents=True, exist_ok=True)
                (wt / RECORD).write_text(json.dumps(new, indent=1) + "\n")
                _git("add", RECORD, cwd=wt)
                _git("-c", "user.name=github-actions", "-c", "user.email=actions@github.com",
                     "commit", "-q", "-m", message, cwd=wt)
                if before_push:
                    before_push()
                pushed = _git("push", "-q", remote, f"HEAD:{BRANCH}", cwd=wt, check=False)
                if pushed.returncode == 0:
                    return True, info
            finally:
                _git("worktree", "remove", "--force", str(wt), cwd=repo, check=False)
    return False, "Could not record the attempt (the branch kept moving). Nothing was run."


def claim(repo: str, run_id: str, run_attempt: str, commit: str, spec_hash: str, recovery_of: str | None,
          remote: str = "origin", before_push=None) -> tuple[bool, str]:
    def change(attempts):
        ok, reason = decide(attempts, recovery_of)
        if not ok:
            return None, reason
        record = {"run_id": run_id, "run_attempt": run_attempt, "commit": commit, "spec_hash": spec_hash,
                  "kind": "recovery" if recovery_of else "first", "recovery_of": recovery_of or None,
                  "claimed_at": datetime.now(timezone.utc).isoformat(), "final_stage": None, "finished_at": None}
        return attempts + [record], reason

    return _update(repo, change, f"Hold-out attempt claimed: run {run_id}", remote, before_push)


def finish(repo: str, run_id: str, stage_log: str, remote: str = "origin") -> tuple[bool, str]:
    path = Path(stage_log)
    stages = [line.split()[-1] for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    last = stages[-1] if stages else "none (stopped before the guards passed or before any data was read)"

    def change(attempts):
        for a in attempts:
            if a["run_id"] == run_id and not a.get("finished_at"):
                a["final_stage"], a["stages"] = last, stages
                a["finished_at"] = datetime.now(timezone.utc).isoformat()
                return attempts, last
        return None, f"no open attempt {run_id}"

    return _update(repo, change, f"Hold-out attempt finished: run {run_id} at {last}", remote)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("claim")
    for name in ("--run-id", "--run-attempt", "--commit", "--spec-hash"):
        c.add_argument(name, required=True)
    c.add_argument("--recovery-of", default="")
    f = sub.add_parser("finish")
    f.add_argument("--run-id", required=True)
    f.add_argument("--stage-log", required=True)
    s = sub.add_parser("show")
    s.add_argument("--out", default="")
    args = parser.parse_args(argv)
    repo = "."
    if args.cmd == "claim":
        ok, info = claim(repo, args.run_id, args.run_attempt, args.commit, args.spec_hash, args.recovery_of or None)
        print(("Claimed: " if ok else "Refused: ") + info)
        return 0 if ok else 1
    if args.cmd == "finish":
        ok, info = finish(repo, args.run_id, args.stage_log)
        print(("Recorded last stage: " if ok else "Not recorded: ") + info)
        return 0 if ok else 1
    _git("fetch", "-q", "origin", BRANCH, cwd=repo)
    shown = _git("show", f"FETCH_HEAD:{RECORD}", cwd=repo, check=False).stdout or "[]"
    if args.out:
        Path(args.out).write_text(shown)
    print(shown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
