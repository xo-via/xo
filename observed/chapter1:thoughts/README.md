# observe.py

**The single entry point to a universe.** A self-contained Python script that
turns a folder (a git repository) into a small, living "universe": it gives the
folder *time*, keeps itself running, can copy and re-sync itself, travel through
its own history, host a confined AI session inside itself, exchange *signals*
with other copies of itself, and — if given a lifespan — be born, tick down,
choose a fate, and seal an encrypted record of its life before it stops.

It is a clone of the universe's root engine `xo.py`; same code, different name.

```sh
python3 observe.py            # begin the universe (install heartbeat + first tick + a session)
python3 observe.py snapshot   # take a single time-snapshot (what cron calls)
python3 observe.py life        # show this instance's lifespan / seal status
```

---

## Core idea

A **universe** is the git repository this script lives at the root of. Its first
and founding primitive is **time**, and time here is *derived*, not stored:

- The repository's **root commit** (the parentless commit) is `t=0` — the **big
  bang**. Its commit timestamp is the origin of time.
- One **tick** lasts `SNAPSHOT_DURATION_SECONDS` (read from the `CONSTANTS`
  file). The current tick is computed as
  `t = (now − big_bang) / SNAPSHOT_DURATION_SECONDS`.
- To **observe** time is to *collect* it: stage everything, write a commit, and
  push it. The git log becomes a literal, tick-by-tick timeline of existence —
  even an unchanged tick leaves a mark (commits are allowed to be empty).

`observe.py` finds its universe with `git rev-parse --show-toplevel` from the
script's own directory, so it works no matter where you invoke it from — **as
long as it sits inside a git repository** (see [Running as its own
universe](#running-as-its-own-universe)).

---

## Commands

| Command | What it does |
|---|---|
| `observe.py` *(no args)* | Same as `start`. |
| `observe.py start` | Make the universe self-sufficient: install the cron **heartbeat**, start the cron daemon, materialize any missing submodules, take the first snapshot, then spin up a confined Claude session. |
| `observe.py snapshot` | Take one time-snapshot (commit + push). This is what cron calls every tick. Refuses while time-traveling (see below). |
| `observe.py fetch` | `git fetch --all --recurse-submodules`. Learns what other copies have done; changes nothing in the working tree. |
| `observe.py update` | `fetch`, then **fast-forward only** the current branch from `origin`, then sync submodules. Never invents a merge or rewrites history; if branches diverged, it says so and stops. |
| `observe.py clone URL [DIR]` | `git clone --recurse-submodules` — reproduce the whole universe (with its submodules) elsewhere. |
| `observe.py travel MOMENT` | **Time-travel** to any commit. `MOMENT` is a tick (`t=42` or `42`), a SHA/branch/tag, or `present`/`now`/`head` to return. |
| `observe.py session [TASK]` | Spin up a headless Claude Code session confined to this folder (see below). |
| `observe.py id` | Print this instance's identity. |
| `observe.py emit KIND [BODY]` | Emit one **signal** to the shared substrate (commit + push). |
| `observe.py receive` | Pull and print new signals from other instances. |
| `observe.py run [INTERVAL] [LIFESPAN] [FATE]` | Run as a **live instance**: emit presence + receive on an interval, until interrupted or until a programmed lifespan ends. |
| `observe.py life` | Show lifespan remaining / fate, or whether this instance has been sealed. |

---

## Time, snapshots, and the changelog

`snapshot()` is the heart:

1. If `HEAD` is **detached** (the universe is time-traveling), **time freezes** —
   no snapshot is taken, so the heartbeat can never commit onto a visited past.
2. Otherwise it stages everything (`git add -A`), computes the tick, and writes a
   commit authored by **Satori `<satori@xo.builders>`**:
   - `t=N: snapshot` when something changed,
   - `t=N: time passes` when nothing did (empty commit).
3. On a substantive change it first appends a tick-stamped entry to
   [`CHANGELOG.md`](./CHANGELOG.md) (added/modified/deleted per file), so each
   snapshot carries its own description. The changelog excludes itself and skips
   quiet ticks.
4. If an `origin` remote exists, it pushes `HEAD`.

### The heartbeat (`start` / `ensure_running`)
`start` installs a **cron** line that runs `observe.py snapshot` every interval,
logging to `~/.universe-tick.log`, and starts the cron daemon if needed. The
schedule is derived from `SNAPSHOT_DURATION_SECONDS` as a best effort
(`*/m * * * *` for sub-hour minute intervals that divide 60, `0 */h * * *` for
whole-hour intervals, else a `*/10` fallback). Installing is idempotent and
removes any stale heartbeat line first. Cron only ticks while the host is awake.

---

## Time travel

`travel` fetches first (so even commits that live only on a remote are
reachable), then **detaches** the working tree to the target commit. While away,
`snapshot()` refuses, so the heartbeat can't overwrite the past. `travel present`
checks out the home branch (`origin`'s default, else `main`) and time resumes.

> Caveat: traveling to a commit replaces *every* file, **including `observe.py`
> itself**. If you visit a commit older than a given feature, the on-disk script
> won't have it — so the safe way back is always `travel present` (or a plain
> `git checkout <home-branch>`).

---

## The confined session

`session [TASK]` launches a **headless** Claude Code run (`claude -p`) whose
entire world is this folder. Confinement is two-layered:

1. **File tools are hard-confined.** The session runs with its working directory
   at the root and *no* extra directories, and file tools are not pre-approved,
   so Claude Code's workspace boundary blocks any read/write *above* the root
   (in-folder edits auto-apply under `acceptEdits`).
2. **Shell is cooperatively confined.** `Bash` is pre-approved so the session can
   run any command top-down from the root; a system prompt holds it to the
   folder ("there is nothing above the big bang"). There is no OS sandbox here,
   so shell confinement is by instruction.

`start` ends by spinning one up with a default "look around and report" task; the
cron `snapshot` never does — a session is born only on a deliberate run. Set
`UNIVERSE_SESSION_BUDGET` to cap spend (`--max-budget-usd`). Requires the
`claude` CLI on `PATH`; if absent, the session is skipped.

---

## Signals — one universe among many

Once cloned, each copy is an **instance** that can speak to the others through the
shared git remote (the same medium that carries time).

- **Identity**: a stable name in `.xo-id` (e.g. `host-9f3a1c`), generated once
  and kept local to the clone — so even two instances on one machine are distinct
  voices.
- **Emit**: appends a JSON line to this instance's *own* log
  `signals/<id>.jsonl`, commits it, and pushes (with rebase-retry). Because each
  instance only ever writes its own file, instances never conflict.
- **Receive**: pulls, then reads every *other* instance's log, returning lines it
  hasn't seen (read positions tracked in `.xo-seen.json`).
- **`run`**: announces `hello`, then each `XO_SIGNAL_INTERVAL` seconds emits an
  `alive` presence signal and receives others', emitting `bye` when stopped.

A signal is `{ "from", "t" (tick), "kind", "body", "ts" }`.

---

## Lifespan, fate, and the sealed `xo.json`

A `run` can be given a **programmed lifespan**. It then lives for that many
seconds — emitting and receiving — and at the end **seals an encrypted record of
its life** and stops immediately.

- **Begin**: `begin_life` writes `.xo-life.json` (birth time, expiry, fate,
  generation = previous + 1, tick born).
- **Fate**: one of `evolve`, `decay`, `restart`, or `random` (which deterministically
  resolves to one of the first three at birth). Set via the `run` argument,
  `XO_FATE`, or `DEFAULT_FATE` in `CONSTANTS`.
- **Death**: when the clock hits zero, the run appends a terminal fate marker to
  its **footprint** (the in-memory list of everything it emitted), then writes
  **`xo.json`**:
  ```json
  { "dna": "<encrypted>", "footprint": "<encrypted>" }
  ```
  - **dna** — the genome at death: id, generation, fate, lifespan, born/expires/
    died timestamps, tick born/died.
  - **footprint** — every signal it emitted during the run, plus the fate marker.
  - Both blobs are encrypted with **Fernet** (key from `XO_KEY`, else `.xo-key`,
    auto-generated on first seal; a non-Fernet key is stretched with PBKDF2-HMAC-
    SHA256). The seal is committed as `xo: <id> gen=N sealed` and pushed, then
    `.xo-life.json` is removed.

`observe.py life` reports time remaining and fate, or — once `xo.json` exists —
that the instance is sealed.

---

## Files & state

**Tracked (part of the universe, shared):**

| Path | Meaning |
|---|---|
| `observe.py` | this engine |
| `CONSTANTS` | the fundamental constants (see below) |
| `CHANGELOG.md` | auto-maintained, tick-by-tick record of changes |
| `signals/<id>.jsonl` | each instance's append-only signal log |
| `xo.json` | the sealed, encrypted life record (after a lifespan ends) |

**Local to each clone (gitignored — never shared):**

| Path | Meaning |
|---|---|
| `.xo-id` | this instance's identity |
| `.xo-seen.json` | how far this instance has read each peer |
| `.xo-life.json` | the active run's life clock |
| `.xo-key` | the Fernet encryption key |

---

## Configuration

**`CONSTANTS`** (top-level `NAME=value` file, the single source of truth):

| Key | Meaning |
|---|---|
| `SNAPSHOT_DURATION_SECONDS` | length of one tick (drives both the tick math and the cron cadence) |
| `LIFESPAN_SECONDS` | default programmed life for `run` (`0` = live until interrupted) |
| `DEFAULT_FATE` | default fate at death (`evolve`/`decay`/`restart`/`random`) |

**Environment variables** (override `CONSTANTS` where applicable):

| Var | Effect |
|---|---|
| `XO_SIGNAL_INTERVAL` | seconds between `run` emissions (default 60) |
| `XO_LIFESPAN_SECONDS` | overrides the lifespan for `run` |
| `XO_FATE` | overrides the fate |
| `XO_KEY` | encryption key for `xo.json` |
| `UNIVERSE_SESSION_BUDGET` | dollar cap for the Claude session |

---

## Identity

Every act of the universe (snapshots, signal commits, the seal commit) is
authored as **Satori `<satori@xo.builders>`** — the universe's own hand,
independent of whoever's git is configured on the host.

---

## Requirements

- `git` and `python3`
- `cron` (for the self-running heartbeat; the daemon must be allowed to run)
- the `cryptography` package (for `xo.json` sealing)
- the `claude` CLI (only for `session` / the `start` session step; optional)

---

## Running as its own universe

`observe.py` resolves its root with git, so it operates on whatever repository
**encloses** it. Placed inside an existing universe (as this copy is, under
`observed/chapter1:thoughts/`), it would act on that *outer* universe — a
reflection, not a separate world. To make this folder a genuinely independent
universe:

```sh
cd observed/chapter1:thoughts
git init                                  # give it its own history…
printf 'SNAPSHOT_DURATION_SECONDS=600\n' > CONSTANTS   # …and its own physics
git add -A && git commit -m "t=0: a universe begins"   # its big bang
python3 observe.py                        # start it ticking
```

From then on this folder has its own time, its own snapshots, and its own
signals — a child universe, observed from outside by the one that contains it.
