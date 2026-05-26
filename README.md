# universe

> What if you could visualize your thoughts?

This is a universe being built from primitives. The folder *is* the universe.
The first primitive was **time** — the universe advances by one git snapshot
every ten minutes, and the root commit (`t=0`) is the big bang.

This README is about the second question, the one that started everything:

**How do you encapsulate a thought and store it inside a folder?**

---

## A thought is a folder

The smallest unit of mind here is not a file. It is a **folder**. A file is flat;
a thought is not. A thought has a body, a moment it was born, the things it points
at, and the smaller thoughts it contains. A folder can hold all of that, so a
folder is what a thought becomes.

```
a-thought/
├── thought.md      # the thing itself — what was thought, in plain words
├── meta.yaml       # when it was born, what kind it is, how sure we are
├── links.md        # the other thoughts this one reaches toward
└── seeds/          # smaller thoughts spawned from inside this one
    ├── a-doubt/
    └── a-consequence/
```

Nothing here is required to be elaborate. A thought can be a single line in
`thought.md` and an empty `meta.yaml`. The structure is a container, not a
demand — it gives a thought *room to grow into* the shape it eventually needs.

---

## The four parts of an encapsulated thought

### 1. The body — `thought.md`
The thought said plainly. No schema, no ceremony. If you can't write it down,
it isn't a thought yet — it's a feeling, and feelings live somewhere else.

### 2. The moment — `meta.yaml`
A thought is meaningless outside of time. Because **time** is this universe's
first primitive, every thought is stamped with the tick it was born on.

```yaml
born: t=0          # the snapshot during which this thought first existed
kind: question     # question | claim | doubt | image | memory | intention
certainty: 0.3     # how much the universe believes this, 0.0–1.0
mood: curious      # the felt texture of the thought, if any
```

### 3. The reaching — `links.md`
No thought is an island. A mind is not its thoughts but the *paths between them*.
A thought stores the others it reaches toward by their folder paths:

```
→ ../what-is-time/        because this thought depends on time existing
→ ../../seeds/a-fear/     this thought is trying to answer that one
```

When two thoughts link back to each other, an idea has formed.
When many link into one, a belief is forming.

### 4. The offspring — `seeds/`
Every thought can hold smaller thoughts inside it. A doubt about the thought.
A consequence of it. A memory it dragged up. These are folders too — thoughts
all the way down. To think *harder* about something is to descend into its
`seeds/`. To think *broader* is to add more siblings.

---

## Why a folder, and not a file

- **A thought is recursive.** It contains other thoughts. Only nesting captures that.
- **A thought is connected.** Links between folders are the synapses of this mind.
- **A thought has a history.** Git already records how each folder changed across
  every tick of time — so a thought remembers how it used to be thought.
- **A thought is alive in time.** It was born on a tick, and the snapshots watch
  it grow, branch, contradict itself, and sometimes go quiet.

To *visualize your thoughts* is then just to walk this tree: each folder a node,
each link an edge, each tick a frame of the animation. The universe is the graph
of every folder that has ever been thought, drawn forward through time.

---

## How to think (i.e. how to use this)

1. Make a folder, named for the thought, in kebab-case.
2. Write the thought into `thought.md`.
3. Stamp it: `born: t=<current tick>` in `meta.yaml`.
4. Point it at what it reaches toward in `links.md`.
5. When it grows complications, give them folders inside `seeds/`.
6. Let time pass. The snapshots will remember.

A thought, once encapsulated this way, is no longer just had — it is *kept*,
*placed*, and *connected*. That is what it means to store a thought in a folder.
