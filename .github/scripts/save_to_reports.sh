#!/usr/bin/env bash
# Copy files into a folder on the "reports" branch and push it.
# Usage: save_to_reports.sh <folder on the branch> <file or folder>...
# The reports branch only holds results and saved price data, never app code.
# Works on a detached copy and pushes HEAD:reports, so it can run several times in one job.
set -euo pipefail
dest="$1"; shift
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
work="$(mktemp -d)"
cleanup() { git worktree remove --force "$work" >/dev/null 2>&1 || true; }
trap cleanup EXIT
if git fetch --depth=1 origin reports 2>/dev/null; then
  git worktree add --detach "$work" FETCH_HEAD
else
  git worktree add --detach "$work"
  (cd "$work" && git checkout -q --orphan "reports-new-$$" && git rm -rfq . && find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + \
     && echo "Backtest and research results. App code lives on main." > README.md)
fi
mkdir -p "$work/$dest"
for item in "$@"; do
  if [ -e "$item" ]; then cp -r "$item" "$work/$dest/"; fi
done
cd "$work"
git add -A
if git diff --cached --quiet; then echo "Nothing new to save."; exit 0; fi
git commit -qm "Results: $dest"
for attempt in 1 2 3; do
  if git push -q origin HEAD:reports; then echo "Saved to reports/$dest"; exit 0; fi
  git fetch -q origin reports && git rebase -q FETCH_HEAD || true
done
echo "Could not push the results." >&2
exit 1
