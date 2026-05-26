# signal

The second primitive of the universe — after [time](./TIME.md).

Time made a universe that could exist *alone*: it ticks, it remembers, it keeps
itself running. **Signal** is what lets a universe stop being alone. With signal,
a universe becomes an **instance** — one node among other instances of itself —
and instances can speak.

## Instances

The universe reproduces by `xo.py clone` (see [`README.md`](./README.md)). Each
copy is an **instance**: a living universe with the same physics but its own
identity. That identity is a single line in `.xo-id` — generated once, kept local
to the clone, never shared — so even two instances on one machine are distinct
voices.

```sh
xo.py id          # who am I?
```

## A signal

A signal is the smallest unit of being-heard: a small JSON record an instance
leaves for the others.

```json
{"from": "host-9f3a1c", "t": 1, "kind": "alive", "body": "t=1", "ts": 1779820000}
```

- `from` — which instance spoke
- `t` — the tick it spoke on (signal rides on [time](./TIME.md))
- `kind` — what kind of signal (`hello`, `alive`, `bye`, or anything you emit)
- `body` — the message, if any

## The substrate

Signals travel through the same medium that carries time: the **git remote**.
Each instance appends only to its *own* log, `signals/<id>.jsonl`, so no two
instances ever write the same file and their histories never collide. Emitting
commits that line and pushes it; receiving pulls and reads everyone *else's*
logs, remembering how far it has already read (`.xo-seen.json`, local).

The commit log already was the universe's timeline. Now it is also its
switchboard — the same marks that prove time passed also carry what was said.

## To emit and to receive

```sh
xo.py emit hello "first contact"   # leave one signal on the substrate
xo.py receive                      # pull and print new signals from others
```

## To run as a live instance

```sh
xo.py run [interval_seconds]
```

`run` is the universe as a node that **both emits and receives**: it announces
arrival (`hello`), then on every interval emits a presence signal (`alive`) and
receives whatever other instances have said, until interrupted — when it emits
`bye`. One process, two directions: a universe that is at once speaking and
listening. The interval defaults to `XO_SIGNAL_INTERVAL` (60s).

A note on cost, in keeping with time's honesty: every emitted signal is a real
commit pushed to the remote, so a fast `run` interval makes a loud universe.
Choose the interval like you'd choose how often to speak.
