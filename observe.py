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
    observe.py            observe the fundamentals + ensure the universe keeps running
    observe.py snapshot   take a single time snapshot (what cron calls)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

# The creator's identity. Every act of the universe is authored by Satori.
AUTHOR_NAME = "Satori"
AUTHOR_EMAIL = "satori@xo.builders"

LOG_FILE = os.path.expanduser("~/.universe-tick.log")


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


def snapshot() -> str:
    """Collect time: commit a snapshot of the universe and push the copy.

    Time passes whether or not anything changed, so the commit is allowed to be
    empty — the git log becomes a literal, tick-by-tick timeline of existence.
    Returns the commit message.
    """
    tick = current_tick()
    git("add", "-A", check=True)

    changed = git("diff", "--cached", "--quiet").returncode != 0
    message = f"t={tick}: snapshot" if changed else f"t={tick}: time passes"

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


# --- entry point --------------------------------------------------------------

def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "snapshot":
        snapshot()
        return 0
    # The default act of running observe.py: keep the universe alive, then look.
    ensure_running()
    observe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
