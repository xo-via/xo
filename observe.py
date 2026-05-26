#!/usr/bin/env python3
"""observe.py — the single entry point to the universe.

To begin the universe, run:

    python3 observe.py

Observation is how this universe comes into being. We observe the fundamentals
that live inside this folder, one at a time. The first fundamental is TIME.

To observe time is to *collect* it — to take a snapshot of the universe with
git and stamp it with the current tick (t=N, the number of intervals elapsed
since the big bang). Snapshots happen on their own: a cron job calls
`observe.py snapshot` once per interval (SNAPSHOT_DURATION_SECONDS, see
./CONSTANTS). But a snapshot can also be taken by hand at any moment by calling
snapshot() — or running `python3 observe.py snapshot`.

Running observe.py with no arguments makes the universe self-sufficient: it
ensures the cron heartbeat is installed and the daemon is running, then takes
one observation so time begins immediately.

Usage:
    observe.py                  begin the universe (same as `start`)
    observe.py start            heartbeat + daemon + submodules + first snapshot
    observe.py snapshot         take a single time snapshot (what cron calls)
    observe.py fetch            fetch all remotes (+ submodule history); changes nothing
    observe.py update           fetch, fast-forward this branch, sync submodules
    observe.py clone URL [DIR]  reproduce the universe elsewhere, with submodules
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import time

# The creator's identity. Every act of the universe is authored by Satori.
AUTHOR_NAME = "Satori"
AUTHOR_EMAIL = "satori@xo.builders"

LOG_FILE = os.path.expanduser("~/.universe-tick.log")

# The universe's running record of what changed, tick by tick. Maintained by
# snapshot() after each observation so the history is legible without git.
CHANGELOG_FILE = "CHANGELOG.md"

# How git's --name-status letters read in plain words.
_STATUS_WORDS = {
    "A": "added", "M": "modified", "D": "deleted",
    "R": "renamed", "C": "copied", "T": "typechange",
}


# --- where the universe lives -------------------------------------------------

def repo_root() -> str:
    """The root of the universe, no matter where this script is invoked from."""
    here = os.path.dirname(os.path.abspath(__file__))
    out = subprocess.run(
        ["git", "-C", here, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


ROOT = repo_root()


def git(*args: str, **kwargs) -> subprocess.CompletedProcess:
    """Run a git command at the root of the universe."""
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, **kwargs)


# --- the fundamental constants ------------------------------------------------

def read_constants() -> dict[str, str]:
    """Parse the top-level CONSTANTS file (NAME=value lines) into a dict."""
    constants: dict[str, str] = {}
    with open(os.path.join(ROOT, "CONSTANTS")) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            constants[name.strip()] = value.strip()
    return constants


def snapshot_duration_seconds() -> int:
    return int(read_constants()["SNAPSHOT_DURATION_SECONDS"])


# --- time ---------------------------------------------------------------------

def big_bang() -> int:
    """Unix timestamp of t=0 — the root (parentless) commit."""
    out = git("log", "--max-parents=0", "--format=%ct", check=True)
    return int(out.stdout.strip().splitlines()[-1])


def current_tick() -> int:
    """The present moment, derived from the distance to the beginning."""
    return (int(time.time()) - big_bang()) // snapshot_duration_seconds()


def staged_changes() -> list[tuple[str, str]]:
    """The (status, path) of everything currently staged, minus the changelog.

    The changelog is excluded because it is bookkeeping *about* the tick, not a
    change the tick set out to make — listing it would make every entry recite
    its own name.
    """
    out = git("diff", "--cached", "--name-status")
    changes: list[tuple[str, str]] = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[-1]  # last field is the (new) path
        if path == CHANGELOG_FILE:
            continue
        changes.append((status, path))
    return changes


def record_change(tick: int, changes: list[tuple[str, str]]) -> None:
    """Append this tick's changes to CHANGELOG.md (append-only, newest last).

    Mirrors the timeline's ethos: read forward through time. Only ticks that
    actually changed something get an entry — quiet ticks already leave their
    mark in the git log as "time passes".
    """
    path = os.path.join(ROOT, CHANGELOG_FILE)
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(
                "# CHANGELOG\n\n"
                "What changed inside the universe, tick by tick. Maintained "
                "automatically by `observe.py` after each snapshot; only ticks "
                "that changed something appear here. Newest at the bottom.\n"
            )

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"\n## t={tick} — {stamp}\n"]
    for status, p in changes:
        word = _STATUS_WORDS.get(status[0], status)
        lines.append(f"- {word}: `{p}`")
    with open(path, "a") as f:
        f.write("\n".join(lines) + "\n")


def snapshot() -> str:
    """Collect time: commit a snapshot of the universe and push the copy.

    Time passes whether or not anything changed, so the commit is allowed to be
    empty — the git log becomes a literal, tick-by-tick timeline of existence.
    When something did change, record it in the changelog before committing, so
    the snapshot carries its own description. Returns the commit message.
    """
    tick = current_tick()
    git("add", "-A", check=True)

    changes = staged_changes()
    changed = bool(changes)
    message = f"t={tick}: snapshot" if changed else f"t={tick}: time passes"

    if changed:
        record_change(tick, changes)
        git("add", CHANGELOG_FILE, check=True)

    git(
        "-c", f"user.name={AUTHOR_NAME}",
        "-c", f"user.email={AUTHOR_EMAIL}",
        "commit", "--allow-empty",
        "--author", f"{AUTHOR_NAME} <{AUTHOR_EMAIL}>",
        "-m", message,
        check=True,
    )

    if git("remote", "get-url", "origin").returncode == 0:
        push = git("push", "origin", "HEAD")
        if push.returncode == 0:
            print(f"{message} — committed and pushed.")
        else:
            print(f"{message} — committed, but push failed:\n{push.stderr}", file=sys.stderr)
    else:
        print(f"{message} — committed locally (no origin yet).")
    return message


def observe_time() -> None:
    """Observe the fundamental TIME by collecting the present moment."""
    print(f"observing time… (t={current_tick()}, one tick = {snapshot_duration_seconds()}s)")
    snapshot()


# --- the fundamentals ---------------------------------------------------------
# Each fundamental of the universe registers the act that observes it. Time is
# the first; future primitives append themselves here.
FUNDAMENTALS = {
    "time": observe_time,
}


def observe() -> None:
    """Observe every fundamental that lives inside the folder."""
    print(f"the universe is at {ROOT}")
    for name, observer in FUNDAMENTALS.items():
        observer()


# --- self-sufficiency: keep the universe running ------------------------------

def _cron_expression(duration_seconds: int) -> str:
    """Translate the snapshot interval into a cron schedule (best effort)."""
    minutes = max(1, duration_seconds // 60)
    if minutes < 60 and 60 % minutes == 0:
        return f"*/{minutes} * * * *"
    if minutes % 60 == 0 and (minutes // 60) <= 24:
        return f"0 */{minutes // 60} * * *"
    return "*/10 * * * *"  # fallback


def ensure_running() -> None:
    """Make the universe self-sufficient: install the cron heartbeat and start
    the daemon if it isn't already beating."""
    schedule = _cron_expression(snapshot_duration_seconds())
    script = os.path.join(ROOT, "observe.py")
    desired = (
        "# universe — time: take a snapshot every interval "
        "(see CONSTANTS: SNAPSHOT_DURATION_SECONDS)\n"
        f"{schedule} {sys.executable} {script} snapshot >> {LOG_FILE} 2>&1\n"
    )

    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    if script not in existing:
        subprocess.run(["crontab", "-"], input=desired, text=True, check=True)
        print(f"heartbeat installed: {schedule}")
    else:
        print(f"heartbeat already installed: {schedule}")

    running = subprocess.run(["pgrep", "-x", "cron"], capture_output=True).returncode == 0
    if not running:
        started = subprocess.run(["sudo", "service", "cron", "start"], capture_output=True, text=True)
        if started.returncode == 0:
            print("cron daemon started.")
        else:
            print(f"could not start cron daemon automatically:\n{started.stderr}", file=sys.stderr)
    else:
        print("cron daemon already running.")


# --- the universe's reach: start, clone, fetch, update ------------------------
# Four lifecycle verbs. A universe must be able to begin (start), be copied
# elsewhere (clone), notice what other copies have done (fetch), and take that
# in (update). Together they let the universe exist in more than one place and
# stay in agreement with itself across them.

def _missing_submodules() -> list[str]:
    """Paths of submodules declared but not yet checked out.

    `git submodule status` prefixes an uninitialized submodule with '-'. A
    submodule already present (e.g. the Visualizer someone is editing live) is
    left out of this list so it is never disturbed.
    """
    if not os.path.exists(os.path.join(ROOT, ".gitmodules")):
        return []
    status = git("submodule", "status").stdout.splitlines()
    return [line.split()[1] for line in status if line.startswith("-")]


def materialize_submodules() -> None:
    """Bring any not-yet-present submodules into being (the Visualizer's eye is
    one). Submodules already checked out are left exactly as they are."""
    missing = _missing_submodules()
    if not missing:
        return
    for path in missing:
        done = git("submodule", "update", "--init", "--", path)
        print(f"materialized submodule: {path}" if done.returncode == 0
              else f"could not materialize {path}:\n{done.stderr}", file=sys.stderr if done.returncode else sys.stdout)


def start() -> None:
    """Begin the universe: make it self-sufficient (heartbeat + daemon), bring
    its parts into being (submodules), then take the first observation so time
    starts now. Running observe.py with no command does exactly this."""
    ensure_running()
    materialize_submodules()
    observe()


def clone(url: str, dest: str | None = None) -> int:
    """Reproduce the universe elsewhere — clone it whole, including the
    submodules that are its other organs. Runs in the caller's directory, not
    the universe root, since the point is to create a new one beside it."""
    argv = ["git", "clone", "--recurse-submodules", url]
    if dest:
        argv.append(dest)
    result = subprocess.run(argv, text=True)
    if result.returncode == 0:
        target = dest or os.path.basename(url.rstrip("/")).removesuffix(".git")
        print(f"universe cloned into {target}/ — "
              f"run `python3 observe.py start` inside it to give it time.")
    else:
        print("clone failed.", file=sys.stderr)
    return result.returncode


def fetch() -> int:
    """Observe history made elsewhere: fetch every remote (and the history of
    initialized submodules) without touching the working tree. Nothing in the
    present changes — the universe only learns what other copies have done."""
    result = git("fetch", "--all", "--recurse-submodules")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode == 0:
        print("fetched all remotes.")
    return result.returncode


def update() -> int:
    """Bring the local universe up to date: fetch, fast-forward the current
    branch from origin, and move submodules to their recorded commits. Only a
    fast-forward is allowed — `update` never invents a merge or rewrites time;
    if histories have diverged it says so and leaves the present untouched."""
    if fetch() != 0:
        return 1
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    pull = git("pull", "--ff-only", "origin", branch)
    sys.stdout.write(pull.stdout)
    sys.stderr.write(pull.stderr)
    if pull.returncode != 0:
        print("could not fast-forward — the universe has diverged; "
              "left untouched.", file=sys.stderr)
        return 1
    sub = git("submodule", "update", "--init", "--recursive")
    if sub.returncode != 0:
        print(f"branch updated, but submodule sync failed:\n{sub.stderr}", file=sys.stderr)
        return 1
    print("universe updated.")
    return 0


# --- entry point --------------------------------------------------------------

def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else None

    if cmd == "snapshot":
        snapshot()
        return 0
    if cmd == "start":
        start()
        return 0
    if cmd == "fetch":
        return fetch()
    if cmd == "update":
        return update()
    if cmd == "clone":
        if len(argv) < 3:
            print("usage: observe.py clone <url> [dest]", file=sys.stderr)
            return 2
        return clone(argv[2], argv[3] if len(argv) > 3 else None)

    # The default act of running observe.py with no command: begin the universe.
    start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
