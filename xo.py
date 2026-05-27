#!/usr/bin/env python3
"""xo.py — the single entry point to the universe.

To begin the universe, run:

    python3 xo.py

Observation is how this universe comes into being. We observe the fundamentals
that live inside this folder, one at a time. The first fundamental is TIME.

To observe time is to *collect* it — to take a snapshot of the universe with
git and stamp it with the current tick (t=N, the number of intervals elapsed
since the big bang). Snapshots happen on their own: a cron job calls
`xo.py snapshot` once per interval (SNAPSHOT_DURATION_SECONDS, see
./CONSTANTS). But a snapshot can also be taken by hand at any moment by calling
snapshot() — or running `python3 xo.py snapshot`.

Running xo.py with no arguments makes the universe self-sufficient: it
ensures the cron heartbeat is installed and the daemon is running, then takes
one observation so time begins immediately.

Usage:
    xo.py                  begin the universe (same as `start`)
    xo.py start            heartbeat + daemon + submodules + first snapshot
    xo.py snapshot         take a single time snapshot (what cron calls)
    xo.py fetch            fetch all remotes (+ submodule history); changes nothing
    xo.py update           fetch, fast-forward this branch, sync submodules
    xo.py clone URL [DIR]  reproduce the universe elsewhere, with submodules
    xo.py travel MOMENT    time-travel to any commit (t=N, a SHA, or 'present')
    xo.py session [TASK]   spin up a Claude Code session confined to this folder

Signal — this universe as a node among universes (see SIGNAL.md):
    xo.py id               print this instance's identity
    xo.py emit KIND [BODY] emit one signal to the shared substrate (commit + push)
    xo.py receive          pull and print new signals from other instances
    xo.py run [INTERVAL] [LIFESPAN] [FATE]
                           run as a live instance: emit + receive until lifespan ends
    xo.py life             show lifespan or whether xo.json is sealed
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import re
import shutil
import signal as signals_module
import socket
import subprocess
import sys
import time
import uuid

from cryptography.fernet import Fernet

# The creator's identity. Every act of the universe is authored by Satori.
AUTHOR_NAME = "Satori"
AUTHOR_EMAIL = "satori@xo.builders"

LOG_FILE = os.path.expanduser("~/.universe-tick.log")

# --- signal: this universe as a node among universes --------------------------
# Each running instance has a stable identity (.xo-id, local & gitignored) and
# emits/receives small JSON signals through the shared git substrate. An
# instance writes only its own append-only log under signals/<id>.jsonl, so many
# instances never conflict; everyone reads everyone else's. See SIGNAL.md.
SIGNALS_DIR = "signals"
ID_FILE = ".xo-id"          # this instance's name (per-clone, gitignored)
SEEN_FILE = ".xo-seen.json"  # how far we've read each peer (local, gitignored)
SIGNAL_INTERVAL_SECONDS = int(os.environ.get("XO_SIGNAL_INTERVAL", "60"))

# --- lifespan: a bounded life for a live instance -----------------------------
# A `run` with a programmed lifespan keeps emitting signals until time is up.
# At lifespan=0 the process seals every emission into xo.json (encrypted dna +
# footprint) and stops immediately — no extra work after death.
LIFE_FILE = ".xo-life.json"  # active run clock — local, gitignored
XO_JSON = "xo.json"          # sealed record: { "dna": "…", "footprint": "…" }
KEY_FILE = ".xo-key"           # encryption key — local, gitignored
KDF_SALT = b"xo-universe-v1"
FATES = ("evolve", "decay", "restart", "random")

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


def lifespan_seconds() -> int:
    """Programmed life for `run`, in seconds. 0 means live until interrupted."""
    if os.environ.get("XO_LIFESPAN_SECONDS", "").strip().isdigit():
        return int(os.environ["XO_LIFESPAN_SECONDS"])
    return int(read_constants().get("LIFESPAN_SECONDS", "0"))


def default_fate() -> str:
    """What happens when lifespan ends."""
    env = os.environ.get("XO_FATE", "").strip().lower()
    if env in FATES:
        return env
    fate = read_constants().get("DEFAULT_FATE", "random").strip().lower()
    return fate if fate in FATES else "random"


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
                "automatically by `xo.py` after each snapshot; only ticks "
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

    While the universe is time-traveling (HEAD detached at some past commit),
    time *freezes*: no snapshot is taken, so the heartbeat can never commit onto
    a detached HEAD or overwrite a visited past. Return with `travel present`.
    """
    if is_detached():
        head = git("rev-parse", "--short", "HEAD").stdout.strip()
        message = (f"time is frozen — the universe is visiting {tick_of('HEAD')} "
                   f"({head}); no snapshot taken. run `xo.py travel present` "
                   f"to return to the present.")
        print(message)
        return message

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
    script = os.path.join(ROOT, "xo.py")
    desired = (
        "# universe — time: take a snapshot every interval "
        "(see CONSTANTS: SNAPSHOT_DURATION_SECONDS)\n"
        f"{schedule} {sys.executable} {script} snapshot >> {LOG_FILE} 2>&1\n"
    )

    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    # Drop any prior heartbeat line (incl. the pre-rename observe.py one) and our
    # own comment, keep everything else, then install the current xo.py line.
    kept = [
        ln for ln in existing.splitlines()
        if ln.strip()
        and "xo.py" not in ln
        and "observe.py" not in ln
        and not ln.startswith("# universe — time")
    ]
    if existing.strip() != "\n".join(kept).strip() or script not in existing:
        body = ("\n".join(kept) + "\n" if kept else "") + desired
        subprocess.run(["crontab", "-"], input=body, text=True, check=True)
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
    its parts into being (submodules), take the first observation so time starts
    now, and then spin up a confined Claude Code session inside it. Running
    xo.py with no command does exactly this.

    The cron heartbeat calls `snapshot`, not `start`, so a session is spun up
    only on a deliberate run — never on every tick.
    """
    ensure_running()
    materialize_submodules()
    observe()
    session()


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
              f"run `python3 xo.py start` inside it to give it time.")
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


# --- time travel: visit any commit --------------------------------------------
# The git log is the universe's literal timeline, so to time-travel is simply to
# check out another commit. Travel fetches first (so even moments that exist
# only on a remote are reachable), then moves the working tree there. While away
# from the present, time freezes (snapshot() refuses) so the heartbeat cannot
# write over history. `travel present` returns to the tip of the home branch.

_PRESENT = {"present", "now", "head", "tip", "today"}


def is_detached() -> bool:
    """True when HEAD points at a commit directly — i.e. we are time-traveling,
    not sitting on a branch in the present."""
    return git("symbolic-ref", "-q", "HEAD").returncode != 0


def home_branch() -> str:
    """The branch the present lives on (origin's default, else 'main')."""
    out = git("rev-parse", "--abbrev-ref", "origin/HEAD")
    if out.returncode == 0 and "/" in out.stdout:
        return out.stdout.strip().split("/", 1)[1]
    return "main"


def tick_of(rev: str) -> str:
    """The tick a commit belongs to, read from its 't=N: …' message; falls back
    to a short SHA when the message has no tick stamp."""
    out = git("log", "-1", "--format=%s", rev)
    m = re.match(r"t=(\d+):", out.stdout.strip())
    if m:
        return f"t={m.group(1)}"
    sha = git("rev-parse", "--short", rev)
    return sha.stdout.strip() or rev


def resolve_moment(ref: str) -> str | None:
    """Turn a user's idea of a moment into a commit SHA.

    Accepts a tick (`t=42` or just `42`), the present (`present`/`now`/`head`),
    or any git revision (SHA, tag, branch). Returns None if it names no commit.
    """
    ref = ref.strip()
    if ref.lower() in _PRESENT:
        return home_branch()
    m = re.fullmatch(r"t=?(\d+)", ref, re.IGNORECASE)
    if m:
        # A tick may have several commits (snapshot + time passes); the latest
        # one is that tick's final state.
        out = git("log", "-1", "--format=%H", f"--grep=^t={m.group(1)}:")
        return out.stdout.strip() or None
    out = git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return out.stdout.strip() or None


def travel(ref: str) -> int:
    """Time-travel: move the universe to any commit. `travel present` (or
    now/head) returns to the tip of the home branch, where time resumes."""
    if fetch() != 0:
        print("(fetch failed — traveling within local history only)", file=sys.stderr)

    going_home = ref.strip().lower() in _PRESENT
    target = resolve_moment(ref)
    if not target:
        print(f"no such moment: {ref!r} — give a tick (t=42), a SHA, or 'present'.",
              file=sys.stderr)
        return 1

    if going_home:
        branch = home_branch()
        back = git("checkout", branch)
        if back.returncode != 0:
            print(f"could not return to the present:\n{back.stderr}", file=sys.stderr)
            return 1
        git("pull", "--ff-only", "origin", branch)  # best effort
        print(f"returned to the present — {branch} at {tick_of('HEAD')}. time resumes.")
        return 0

    go = git("checkout", "--detach", target)
    if go.returncode != 0:
        print(f"could not travel (uncommitted changes in the present?):\n{go.stderr}",
              file=sys.stderr)
        return 1
    print(f"traveled to {tick_of(target)} ({target[:8]}). time is frozen here — "
          f"run `xo.py travel present` to return.")
    return 0


# --- a mind inside the universe: a confined Claude Code session ---------------
# Running xo.py spins up a headless Claude Code session whose entire world
# is this folder. Its working directory is the universe root, and it is given no
# additional directories — so Claude Code's file tools are scoped to the
# universe and cannot reach above it. A confinement system prompt holds the same
# line for shell commands. It can do anything at or below the root; nothing above
# it exists, as far as the session is concerned.

# How the session is confined to the universe (two layers):
#   1. File tools (Read/Edit/Write/Glob/Grep) are NOT pre-approved here, so they
#      fall under Claude Code's workspace boundary: with cwd at the root and no
#      --add-dir, they work at/below the root but are HARD-BLOCKED above it
#      (acceptEdits auto-applies in-workspace edits; an outside path is denied).
#   2. Bash is pre-approved so the session can run any command top-down from the
#      root — but bash is not path-scoped, so its confinement is the working
#      directory plus the system prompt below (cooperative; there is no OS
#      sandbox available in this environment to jail shell commands).
# So: file access above the root is genuinely prevented; shell commands are held
# to the root by instruction. Only pre-approve non-file tools here.
SESSION_TOOLS = ["Bash", "WebSearch", "WebFetch", "TodoWrite"]

SESSION_DEFAULT_PROMPT = (
    "You have just come into being inside a universe whose entire world is this "
    "folder. Look around — start with README.md and OBSERVATIONS.md — then say, "
    "briefly, what this universe is and what changed most recently. Act only if "
    "something clearly warrants it; otherwise just report."
)


def session(task: str | None = None) -> int:
    """Spin up a headless Claude Code session confined to the universe root.

    cwd is the root and no extra directories are granted, so Claude Code's file
    tools are scoped to the universe; a confinement system prompt extends the
    same boundary to shell commands. With no task, a default observation prompt
    is used. Returns the claude process's exit code.
    """
    if shutil.which("claude") is None:
        print("the `claude` CLI is not installed — skipping the session.",
              file=sys.stderr)
        return 1

    prompt = (task or "").strip() or SESSION_DEFAULT_PROMPT
    confine = (
        f"You are a Claude Code session living inside a universe whose entire "
        f"world is the directory {ROOT}. Everything you do happens at or below "
        f"it, using paths relative to it. You may run any command and read, "
        f"create, or edit any file here — but you must never read, write, cd "
        f"into, or otherwise touch any path ABOVE this directory. There is "
        f"nothing above the big bang; treat {ROOT} as the root of all existence."
    )

    cmd = [
        "claude", "-p", prompt,
        "--permission-mode", "acceptEdits",  # act unattended, file tools stay in-workspace
        "--allowedTools", *SESSION_TOOLS,
        "--append-system-prompt", confine,
    ]
    budget = os.environ.get("UNIVERSE_SESSION_BUDGET", "").strip()
    if budget:
        cmd += ["--max-budget-usd", budget]

    print(f"spinning up a Claude session, confined to {ROOT} …")
    # Run from the root: this is what scopes the session to the universe.
    return subprocess.run(cmd, cwd=ROOT).returncode


# --- signal: emit and receive among instances ---------------------------------
# A universe is no longer alone. Each clone is an instance with its own identity;
# instances speak by leaving signals in the shared substrate (the git remote).
# Emitting writes a line to this instance's own log and pushes it; receiving
# pulls and reads the logs of every *other* instance. The same medium that
# carries time (commits) now also carries messages.

def instance_id() -> str:
    """This instance's stable name. Generated once and kept in .xo-id (local to
    the clone, gitignored) so every instance — even on the same machine — is a
    distinct voice."""
    path = os.path.join(ROOT, ID_FILE)
    if os.path.exists(path):
        name = open(path).read().strip()
        if name:
            return name
    name = f"{socket.gethostname().split('.')[0]}-{uuid.uuid4().hex[:6]}"
    with open(path, "w") as f:
        f.write(name + "\n")
    return name


def _push_with_retry(tries: int = 3) -> bool:
    """Push HEAD, integrating concurrent history if the push is rejected. Since
    each instance only ever writes its own signal log, rebases never conflict."""
    branch = home_branch()
    for _ in range(tries):
        if git("push", "origin", "HEAD").returncode == 0:
            return True
        git("pull", "--rebase", "--autostash", "origin", branch)
    return git("push", "origin", "HEAD").returncode == 0


def emit(kind: str, body: str = "", *, footprint: list[dict] | None = None) -> int:
    """Emit one signal: append it to this instance's log, commit, and push it to
    the shared substrate so other instances can receive it.

    When `footprint` is passed (during `run`), the emission is also kept in
    memory to be sealed into xo.json at lifespan end.
    """
    iid = instance_id()
    os.makedirs(os.path.join(ROOT, SIGNALS_DIR), exist_ok=True)
    rel = f"{SIGNALS_DIR}/{iid}.jsonl"
    record = {
        "from": iid,
        "t": current_tick(),
        "kind": kind,
        "body": body,
        "ts": int(time.time()),
    }
    if footprint is not None:
        footprint.append(dict(record))
    with open(os.path.join(ROOT, rel), "a") as f:
        f.write(json.dumps(record) + "\n")

    git("add", "--", rel, check=True)
    git(
        "-c", f"user.name={AUTHOR_NAME}",
        "-c", f"user.email={AUTHOR_EMAIL}",
        "commit", "--author", f"{AUTHOR_NAME} <{AUTHOR_EMAIL}>",
        "-m", f"signal: {iid} → {kind}",
        check=True,
    )
    pushed = git("remote", "get-url", "origin").returncode == 0 and _push_with_retry()
    print(f"⇢ emitted [{kind}] as {iid}" + ("" if pushed else " (local only)"))
    return 0


def _load_seen() -> dict[str, int]:
    path = os.path.join(ROOT, SEEN_FILE)
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:
            return {}
    return {}


def _save_seen(seen: dict[str, int]) -> None:
    with open(os.path.join(ROOT, SEEN_FILE), "w") as f:
        json.dump(seen, f)


def receive(announce: bool = True) -> list[dict]:
    """Pull the shared substrate and return signals from other instances that we
    have not read yet (advancing our per-peer read position)."""
    if git("remote", "get-url", "origin").returncode == 0:
        git("pull", "--rebase", "--autostash", "origin", home_branch())

    iid = instance_id()
    sigdir = os.path.join(ROOT, SIGNALS_DIR)
    seen = _load_seen()
    fresh: list[dict] = []
    if os.path.isdir(sigdir):
        for fname in sorted(os.listdir(sigdir)):
            if not fname.endswith(".jsonl"):
                continue
            peer = fname[: -len(".jsonl")]
            if peer == iid:
                continue  # never receive our own voice
            lines = open(os.path.join(sigdir, fname)).read().splitlines()
            start = seen.get(peer, 0)
            for line in lines[start:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    fresh.append(json.loads(line))
                except Exception:
                    continue
            seen[peer] = len(lines)
    _save_seen(seen)

    if announce:
        for s in fresh:
            print(f"⇠ from {s.get('from')} [{s.get('kind')}] "
                  f"t={s.get('t')}: {s.get('body', '')}")
        if not fresh:
            print("(no new signals)")
    return fresh


# --- lifespan: birth, ticking down, seal into xo.json -------------------------

def _fernet() -> Fernet:
    """Key from XO_KEY env, else .xo-key (created on first seal if missing)."""
    raw = os.environ.get("XO_KEY", "").strip()
    path = os.path.join(ROOT, KEY_FILE)
    if not raw and os.path.exists(path):
        raw = open(path).read().strip()
    if not raw:
        raw = Fernet.generate_key().decode()
        with open(path, "w") as f:
            f.write(raw + "\n")
    if len(raw) == 44 and raw.endswith("="):
        return Fernet(raw.encode())
    derived = hashlib.pbkdf2_hmac("sha256", raw.encode(), KDF_SALT, 480_000, dklen=32)
    return Fernet(base64.urlsafe_b64encode(derived))


def _encrypt_blob(data: dict | list) -> str:
    return _fernet().encrypt(
        json.dumps(data, separators=(",", ":")).encode()
    ).decode()


def seal_xo_json(dna: dict, footprint: list[dict]) -> None:
    """Write the encrypted life record. Only `dna` and `footprint` are stored."""
    out = {"dna": _encrypt_blob(dna), "footprint": _encrypt_blob(footprint)}
    with open(os.path.join(ROOT, XO_JSON), "w") as f:
        json.dump(out, f, indent=2)
        f.write("\n")


def _commit_xo_json(iid: str, generation: int) -> None:
    """Best-effort: put the sealed xo.json on the substrate before we stop."""
    git("add", XO_JSON, check=True)
    git(
        "-c", f"user.name={AUTHOR_NAME}",
        "-c", f"user.email={AUTHOR_EMAIL}",
        "commit", "--author", f"{AUTHOR_NAME} <{AUTHOR_EMAIL}>",
        "-m", f"xo: {iid} gen={generation} sealed",
        check=True,
    )
    if git("remote", "get-url", "origin").returncode == 0:
        _push_with_retry()


def is_sealed() -> bool:
    path = os.path.join(ROOT, XO_JSON)
    if not os.path.exists(path):
        return False
    try:
        data = json.load(open(path))
        return "dna" in data and "footprint" in data
    except Exception:
        return False

def _resolve_fate(choice: str, iid: str) -> str:
    """Turn 'random' into a stable pick for this birth."""
    if choice != "random":
        return choice
    h = hashlib.sha256(f"{iid}:{time.time()}".encode()).hexdigest()
    return ("evolve", "decay", "restart")[int(h[:8], 16) % 3]


def _load_life() -> dict | None:
    path = os.path.join(ROOT, LIFE_FILE)
    if not os.path.exists(path):
        return None
    try:
        return json.load(open(path))
    except Exception:
        return None


def _save_life(record: dict) -> None:
    with open(os.path.join(ROOT, LIFE_FILE), "w") as f:
        json.dump(record, f, indent=2)
        f.write("\n")


def begin_life(iid: str, seconds: int, fate: str) -> dict:
    """Record this run's birth and when it must end."""
    now = int(time.time())
    resolved = _resolve_fate(fate, iid)
    prev = _load_life() or {}
    generation = int(prev.get("generation", 0)) + 1
    record = {
        "id": iid,
        "born_ts": now,
        "expires_ts": now + seconds if seconds > 0 else None,
        "lifespan_seconds": seconds,
        "fate": resolved,
        "generation": generation,
        "tick_born": current_tick(),
    }
    _save_life(record)
    return record


def finish_life(record: dict) -> dict:
    """Return dna for sealing — the instance's genome at death."""
    return {
        "id": record["id"],
        "generation": record["generation"],
        "fate": record["fate"],
        "lifespan_seconds": record["lifespan_seconds"],
        "born_ts": record["born_ts"],
        "expires_ts": record["expires_ts"],
        "tick_born": record["tick_born"],
        "tick_died": current_tick(),
        "died_ts": int(time.time()),
    }


def life_remaining(record: dict | None) -> int | None:
    """Seconds until programmed death, or None if unbounded."""
    if not record or not record.get("expires_ts"):
        return None
    return max(0, int(record["expires_ts"]) - int(time.time()))


def _fate_body(fate: str, record: dict) -> str:
    """What the terminal signal carries — enough for a successor to act."""
    rem = life_remaining(record)
    parts = [
        f"fate={fate}",
        f"gen={record.get('generation', 1)}",
        f"t={current_tick()}",
    ]
    if rem is not None:
        parts.append(f"remaining={rem}s")
    return " ".join(parts)


def show_life() -> int:
    """Print the programmed lifespan for this instance, if any."""
    record = _load_life()
    iid = instance_id()
    if not record:
        secs = lifespan_seconds()
        if secs > 0:
            print(f"instance {iid} has no active life record; "
                  f"CONSTANTS lifespan is {secs}s (fate={default_fate()}).")
        else:
            print(f"instance {iid} has no programmed lifespan "
                  f"(LIFESPAN_SECONDS=0 — lives until interrupted).")
        return 0
    rem = life_remaining(record)
    fate = record.get("fate", "?")
    gen = record.get("generation", "?")
    if record.get("died_ts"):
        print(f"instance {iid} gen={gen} died at t={record.get('tick_died')} "
              f"(fate was {fate}).")
        return 0
    if rem is None:
        print(f"instance {iid} gen={gen} is alive with no expiry.")
        return 0
    if rem == 0:
        print(f"instance {iid} gen={gen} lifespan has elapsed (fate={fate}).")
        return 0
    print(f"instance {iid} gen={gen} — {rem}s remaining, fate={fate} at death.")
    return 0


def run(lifespan_override: int | None = None, fate_override: str | None = None) -> int:
    """Run this universe as a live instance: announce arrival, then on every
    interval emit a presence signal and receive everyone else's, until lifespan
    ends or the process is interrupted.

    When a lifespan is programmed (CONSTANTS, env, or CLI), the loop keeps
    emitting until expiry, then emits the chosen fate (evolve / decay /
    restart), says bye, and stops — it does not run past death.
    """
    iid = instance_id()
    seconds = lifespan_override if lifespan_override is not None else lifespan_seconds()
    fate = (fate_override or default_fate()).lower()
    if fate not in FATES:
        print(f"unknown fate {fate!r} — choose one of: {', '.join(FATES)}",
              file=sys.stderr)
        return 2

    life = begin_life(iid, seconds, fate) if seconds > 0 else None
    resolved_fate = life["fate"] if life else None

    if seconds > 0:
        print(f"instance {iid} is alive — emitting + receiving every "
              f"{SIGNAL_INTERVAL_SECONDS}s for {seconds}s, then {resolved_fate}. "
              f"Ctrl-C to stop early.")
    else:
        print(f"instance {iid} is alive — emitting + receiving every "
              f"{SIGNAL_INTERVAL_SECONDS}s. Ctrl-C to stop.")

    stop = {"now": False}
    def _halt(*_a):
        stop["now"] = True
    signals_module.signal(signals_module.SIGINT, _halt)
    signals_module.signal(signals_module.SIGTERM, _halt)

    emit("hello", f"{iid} online gen={life['generation'] if life else 1}")
    expired = False
    try:
        while not stop["now"]:
            receive(announce=True)
            rem = life_remaining(life)
            if life and rem is not None and rem <= 0:
                expired = True
                break
            wait = SIGNAL_INTERVAL_SECONDS
            if rem is not None:
                wait = min(wait, rem)
            for _ in range(max(1, wait)):
                if stop["now"]:
                    break
                if life and life_remaining(life) == 0:
                    expired = True
                    break
                time.sleep(1)
            if stop["now"] or expired:
                break
            body = f"t={current_tick()}"
            rem = life_remaining(life)
            if rem is not None:
                body += f" remaining={rem}s"
            emit("alive", body)
    finally:
        if expired and life:
            emit(resolved_fate, _fate_body(resolved_fate, life))
            finish_life(life)
            emit("bye", f"{iid} {resolved_fate}")
            print(f"instance {iid} lifespan ended — fate={resolved_fate}, stopped.")
        else:
            emit("bye", f"{iid} offline")
            print(f"instance {iid} stopped.")
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
            print("usage: xo.py clone <url> [dest]", file=sys.stderr)
            return 2
        return clone(argv[2], argv[3] if len(argv) > 3 else None)
    if cmd == "travel":
        if len(argv) < 3:
            print("usage: xo.py travel <commit|t=N|present>", file=sys.stderr)
            return 2
        return travel(argv[2])
    if cmd == "session":
        task = " ".join(argv[2:]) if len(argv) > 2 else None
        return session(task)
    if cmd == "id":
        print(instance_id())
        return 0
    if cmd == "emit":
        if len(argv) < 3:
            print("usage: xo.py emit <kind> [body]", file=sys.stderr)
            return 2
        return emit(argv[2], " ".join(argv[3:]))
    if cmd == "receive":
        receive(announce=True)
        return 0
    if cmd == "run":
        global SIGNAL_INTERVAL_SECONDS
        interval: int | None = None
        life_secs: int | None = None
        fate: str | None = None
        args = argv[2:]
        i = 0
        while i < len(args):
            a = args[i]
            if a.isdigit() and interval is None:
                interval = int(a)
            elif a.isdigit() and life_secs is None:
                life_secs = int(a)
            elif a.lower() in FATES and fate is None:
                fate = a.lower()
            else:
                print("usage: xo.py run [interval] [lifespan_seconds] [fate]",
                      file=sys.stderr)
                print(f"       fate is one of: {', '.join(FATES)}", file=sys.stderr)
                return 2
            i += 1
        if interval is not None:
            SIGNAL_INTERVAL_SECONDS = interval
        return run(lifespan_override=life_secs, fate_override=fate)
    if cmd == "life":
        return show_life()

    # The default act of running xo.py with no command: begin the universe.
    start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
