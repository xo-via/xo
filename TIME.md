# time

The first primitive of the universe.

Before there were thoughts, there was time — because a thought is meaningless
outside of the moment it was born (see [`README.md`](./README.md)).

## How time works here

Time moves in **ticks**. One tick lasts `SNAPSHOT_DURATION_SECONDS` (a
fundamental constant — see [`CONSTANTS`](./CONSTANTS)), currently 600 seconds =
ten minutes.

- `t=0` is the **big bang** — the root commit of this repository.
- Every tick, the universe records itself: it stages whatever changed, commits
  a snapshot authored by **Satori**, and pushes the copy to `origin`.
- The commit is allowed to be empty. Time passes whether or not anything
  changed, so even a quiet tick leaves a mark. The git log is therefore a
  literal, tick-by-tick timeline of the universe's existence.

The current tick is not stored — it is *derived*:
`t = (now − big_bang) / SNAPSHOT_DURATION_SECONDS`.
Time is computed from the distance to the beginning, not counted by hand.

## The mechanism

[`tick.sh`](./tick.sh) is one tick. Run it to advance time once:

```sh
./tick.sh
```

A cron job runs it once every ten minutes, so the universe advances on its own
(see `crontab -l`).
