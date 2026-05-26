# time

The first primitive of the universe.

Before there were thoughts, there was time — because a thought is meaningless
outside of the moment it was born (see the root [`README.md`](../README.md)).

## How time works here

Time moves in **ticks**. One tick is one hour.

- `t=0` is the **big bang** — the root commit of this repository.
- Every tick, the universe records itself: it stages whatever changed, commits
  a snapshot authored by **Satori**, and pushes the copy to `origin`.
- The commit is allowed to be empty. Time passes whether or not anything
  changed, so even a quiet hour leaves a mark. The git log is therefore a
  literal, hour-by-hour timeline of the universe's existence.

The current tick is not stored — it is *derived*: `t = (now − big_bang) / 1h`.
Time is computed from the distance to the beginning, not counted by hand.

## The mechanism

[`tick.sh`](./tick.sh) is one tick. Run it to advance time once:

```sh
time/tick.sh
```

A scheduled routine runs it once per hour, so the universe advances on its own.
