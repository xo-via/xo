# CONSTANTS

The fundamental constants of the universe.

Every universe is fixed by a handful of numbers it cannot change about itself.
This folder holds ours. Each constant is a single file whose entire contents
are its value — nothing else — so any part of the universe can read it with a
plain `cat` and so its history is legible in the timeline.

These are the dials of reality. Change one and the universe behaves differently
from that tick onward.

## The constants

| File                        | Value | Meaning                                                        |
|-----------------------------|-------|----------------------------------------------------------------|
| `SNAPSHOT_DURATION_SECONDS` | `600` | How long one tick lasts, in seconds. 600s = 10 minutes.        |

`SNAPSHOT_DURATION_SECONDS` is the heartbeat of [time](../time/README.md):
`time/tick.sh` reads it to decide both how often a snapshot is taken and how
the current tick `t=N` is derived (`t = (now − big_bang) / SNAPSHOT_DURATION_SECONDS`).
It is the single source of truth — the scheduler and the math both bend to it.
