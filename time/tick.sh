#!/usr/bin/env bash
#
# time/tick.sh — advance the universe by one tick.
#
# Time is the first primitive of this universe. It moves in ticks.
# One tick = ten minutes since the big bang (t=0, the root commit).
#
# Each tick the universe records itself: it stages whatever has changed,
# commits a snapshot authored by Satori, and pushes the copy to origin.
# Time passes whether or not anything changed, so the commit is allowed
# to be empty — the git log becomes a literal, hour-by-hour timeline of
# the universe's existence.
#
set -euo pipefail

# Root of the universe, regardless of where this script is called from.
REPO_ROOT="$(git -C "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# The creator's identity. Every act of the universe is authored by Satori.
AUTHOR_NAME="Satori"
AUTHOR_EMAIL="satori@xo.builders"

# A tick's length is a fundamental constant of the universe (see CONSTANTS/).
SNAPSHOT_DURATION_SECONDS="$(cat "$REPO_ROOT/CONSTANTS/SNAPSHOT_DURATION_SECONDS")"

# The big bang: the timestamp of the root (parentless) commit.
BIG_BANG="$(git log --max-parents=0 --format=%ct | tail -1)"
NOW="$(date +%s)"
TICK=$(( (NOW - BIG_BANG) / SNAPSHOT_DURATION_SECONDS ))   # ticks elapsed since t=0

git add -A

if git diff --cached --quiet; then
  MSG="t=${TICK}: time passes"
else
  MSG="t=${TICK}: snapshot"
fi

git -c user.name="$AUTHOR_NAME" -c user.email="$AUTHOR_EMAIL" \
    commit --allow-empty \
    --author="${AUTHOR_NAME} <${AUTHOR_EMAIL}>" \
    -m "$MSG"

# Push the copy, if the universe has somewhere to be copied to.
if git remote get-url origin >/dev/null 2>&1; then
  git push origin HEAD
  echo "${MSG} — committed and pushed."
else
  echo "${MSG} — committed locally (no origin yet)."
fi
