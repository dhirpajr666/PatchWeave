# PatchWeave

**Coding-Agent Change Review Lab** — weave a change manifest and a requirement
catalog into an auditable review artifact. PatchWeave answers the question every
reviewer of AI-generated (or human) diffs eventually asks out loud: *"Which of
these edits was actually authorized, and which requirements did nobody touch?"*

![PatchWeave loom banner](docs/assets/loom-banner.svg)

PatchWeave treats a review the way a loom treats cloth. Your **requirements** are
the *warp* — the fixed vertical threads that give the fabric its structure. Your
**changes** are the *weft* — the horizontal threads a coding session lays across
the warp. A healthy change set is tightly woven: every weft thread crosses a warp
thread (every change is *anchored* to a requirement), and every warp thread is
crossed at least once (every requirement is *met*). PatchWeave finds the loose
threads — unanchored edits, unmet requirements, dangling references — and hands
you a ranked queue so you review the dangerous parts first.

---

## Table of contents

- [Why PatchWeave exists](#why-patchweave-exists)
- [The two input documents](#the-two-input-documents)
- [Core concepts and vocabulary](#core-concepts-and-vocabulary)
- [Architecture](#architecture)
- [Installation](#installation)
- [Command-line reference](#command-line-reference)
- [Workflows and CLI recipes](#workflows-and-cli-recipes)
- [The anchoring algorithm](#the-anchoring-algorithm)
- [The review-queue scoring model](#the-review-queue-scoring-model)
- [The native metric engine](#the-native-metric-engine)
- [Output schemas](#output-schemas)
- [Operations and CI gating](#operations-and-ci-gating)
- [Extension seams](#extension-seams)
- [Design identity](#design-identity)
- [Glossary](#glossary)

---

## Why PatchWeave exists

Coding agents produce diffs at a rate no human review process was designed for.
A single agent session might touch thirty files across five subsystems, cite a
handful of ticket ids in its commit body, and leave the rest unattributed. The
traditional review tools — a side-by-side diff and a mental checklist — collapse
under that volume. Two failure modes dominate:

1. **Unanchored drift.** The agent edited a file that no requirement asked it to
   touch. Sometimes that is legitimate collateral (a shared helper had to change);
   often it is scope creep, a stray refactor, or an outright mistake. Either way
   it deserves a *conscious* review decision rather than being buried in the pile.

2. **Silent gaps.** A requirement was on the list, the session claimed success,
   and yet no change in the manifest supports it. The work looks done because the
   loud, easy requirements got attention while the quiet, risky one slipped.

PatchWeave makes both visible and *ranks* them, so a reviewer's scarce attention
flows to the riskiest, least-covered work first. It is deliberately small,
dependency-free, and deterministic: the same inputs always produce the same
brief, which makes it safe to wire into a gate.

---

## The two input documents

PatchWeave consumes exactly two JSON documents. Both are plain, hand-editable,
and version-control-friendly.

### Change manifest

Describes what a work session touched. Each entry is a *hunk* — one file, with
line-delta counts, the requirement ids it claims to satisfy, and an optional
reviewer sign-off.

```json
{
  "session": "agent-2026-09-01-checkout-refactor",
  "branch": "feat/checkout-idempotency",
  "changes": [
    {
      "path": "src/checkout/idempotency.py",
      "kind": "add",
      "added": 141,
      "removed": 0,
      "requirements": ["REQ-CHK-1", "REQ-CHK-2"],
      "reviewer": "dana"
    }
  ]
}
```

| Field          | Type      | Meaning                                              |
| -------------- | --------- | ---------------------------------------------------- |
| `path`         | string    | File touched (required, non-empty).                  |
| `kind`         | string    | `add` \| `modify` \| `delete` \| `rename`.           |
| `added`        | int ≥ 0   | Lines added.                                         |
| `removed`      | int ≥ 0   | Lines removed.                                       |
| `requirements` | string[]  | Requirement ids this change claims to satisfy.       |
| `reviewer`     | string?   | Who signed off; absence means *unreviewed*.          |

### Requirement catalog

Describes the intended scope of work — the warp threads.

```json
{
  "release": "2026.09-checkout",
  "requirements": [
    {
      "id": "REQ-CHK-1",
      "title": "Checkout sessions must be idempotent under client retries",
      "risk": "critical",
      "owner": "dana",
      "globs": ["src/checkout/*.py"]
    }
  ]
}
```

| Field   | Type     | Meaning                                                        |
| ------- | -------- | -------------------------------------------------------------- |
| `id`    | string   | Stable identifier (required, unique across the catalog).       |
| `title` | string   | Human-readable statement of intent.                            |
| `risk`  | string   | `routine` \| `notable` \| `elevated` \| `critical`.            |
| `globs` | string[] | Path globs this requirement is expected to touch.              |
| `owner` | string?  | Accountable person or team.                                    |

Both loaders are strict about *structure* and lenient about *forward
compatibility*: unknown top-level keys are ignored, but a malformed entry raises
`ManifestError` rather than silently producing a misleading brief.

---

## Core concepts and vocabulary

- **Anchor** — a resolved link between a changed path and a requirement id. An
  anchor is *explicit* (the change listed the id) or *implicit* (the change's
  path matched a requirement glob).
- **Unanchored change** — a hunk with no resolved anchor at all. The loudest
  governance signal PatchWeave emits.
- **Unknown reference** — a hunk that cited a requirement id which does not exist
  in the catalog (a stale or fat-fingered ticket).
- **Requirement state** — `unmet` (no supporting change), `partial` (has changes
  but at least one is unreviewed), or `reviewed` (met and fully signed off).
- **Patch surface** — the total added + removed lines across the manifest; the
  raw size of what a reviewer must comprehend.
- **Review item** — one entry in the ranked queue, carrying a priority score,
  risk tier, churn, its requirement ids, and any flags.

---

## Architecture

PatchWeave is a linear pipeline with one native side-branch. Each stage is a pure
transformation over immutable dataclasses, which is what makes runs reproducible.

![PatchWeave pipeline](docs/assets/pipeline.svg)

```
                +-----------+     +-----------+     +-----------+     +-----------+
  manifest ---> |   load    | --> |   weave   | --> |   score   | --> |   brief   | ---> report
  catalog  ---> | (model.py)|     | (weave.py)|     | (queue.py)|     | (brief.py)|      queue
                +-----------+     +-----------+     +-----------+     +-----------+
                                        |                                   ^
                                        v                                   |
                                   anchor map / gaps                        |
                                                                            |
  diff ------------------------------> [ metrics ] --- C++17 patch_metrics.cpp
                                        (native.py bridge, pure-Python fallback)
```

Module responsibilities:

| Module              | Responsibility                                                             |
| ------------------- | -------------------------------------------------------------------------- |
| `patchweave/model.py`  | Dataclasses (`Hunk`, `Requirement`, `Manifest`, `Catalog`), loaders, validation. |
| `patchweave/weave.py`  | `Weaver` resolves anchors, computes `RequirementStatus`, produces `WeaveReport`. |
| `patchweave/queue.py`  | `QueueBuilder` scores and orders `ReviewItem`s.                            |
| `patchweave/brief.py`  | Terminal, Markdown, and JSON renderers.                                    |
| `patchweave/native.py` | Compiles and drives the C++ engine; pure-Python fallback.                  |
| `patchweave/cli.py`    | Argument parsing and verb dispatch.                                        |
| `core/patch_metrics.cpp` | Portable C++17 diff churn accumulator.                                   |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the data-flow contract and
[DESIGN.md](DESIGN.md) for the reasoning behind the scoring model.

---

## Installation

PatchWeave requires only Python 3.11+. There are no third-party dependencies.

```bash
# from the repository root
python -m patchweave --version
```

The native metric engine additionally uses a C++17 compiler (`g++`, `clang++`,
or `c++`) if one is on `PATH`. It is compiled on demand and cached; when absent,
the `metrics` verb transparently falls back to an identical pure-Python
implementation.

---

## Command-line reference

```
patchweave <verb> [options]

  weave    --manifest FILE --catalog FILE [--color] [--weights r,s,g,b]
  queue    --manifest FILE --catalog FILE [--format text|json] [--weights ...]
  brief    --manifest FILE --catalog FILE [--format text|markdown|json] [--color]
  gaps     --manifest FILE --catalog FILE [--max-gaps N]
  metrics  --diff FILE [--format text|json] [--pure]
```

- `weave` — the everyday view: a terminal brief with surface totals, anchor
  ratio, governance gaps, a risk histogram, and the top of the review queue.
- `queue` — just the ranked list, for feeding into other tooling.
- `brief` — the full artifact in your chosen format; `markdown` is designed to
  paste directly into a pull request description.
- `gaps` — a gate. Prints every unanchored change, unmet requirement, and
  unknown reference, and exits non-zero when the total exceeds `--max-gaps`.
- `metrics` — runs the native churn engine over a raw unified diff.

---

## Workflows and CLI recipes

### 1. Everyday review brief

```bash
python -m patchweave weave \
  --manifest examples/manifest.json \
  --catalog  examples/catalog.json --color
```

You get the anchor ratio, the risk histogram, and the top of the queue in one
screen. Start at the top of the queue and work down; the ordering guarantees the
riskiest, least-covered work is first.

### 2. Paste-ready PR summary

```bash
python -m patchweave brief \
  --manifest examples/manifest.json \
  --catalog  examples/catalog.json \
  --format markdown > review-brief.md
```

The Markdown brief renders a governance-gaps table and a numbered review queue —
drop it into the PR body so reviewers share a single prioritized worklist.

### 3. Gate a merge on governance health

```bash
python -m patchweave gaps \
  --manifest examples/manifest.json \
  --catalog  examples/catalog.json \
  --max-gaps 0
echo "exit: $?"   # non-zero when any gap remains
```

### 4. Re-weight the queue for a security review

Emphasize governance gaps and risk, de-emphasize raw size:

```bash
python -m patchweave queue \
  --manifest examples/manifest.json \
  --catalog  examples/catalog.json \
  --weights 0.45,0.05,0.40,0.10 --format json
```

The four weights are `risk,surface,gap,blast`; they are normalized internally so
they need not sum to one.

### 5. Machine-readable artifact for a dashboard

```bash
python -m patchweave brief \
  --manifest examples/manifest.json \
  --catalog  examples/catalog.json \
  --format json > brief.json
```

Every JSON artifact is stamped with `"schema": "patchweave/v1"`.

### 6. Native churn metrics over a diff

```bash
python -m patchweave metrics --diff examples/sample.diff
python -m patchweave metrics --diff examples/sample.diff --pure --format json
```

---

## The anchoring algorithm

Anchoring is the core resolution step. For each hunk:

1. **Explicit pass.** For every requirement id the hunk cites, if the id exists
   in the catalog, emit an `Anchor(via="explicit")`. If it does not exist, record
   it under `unknown_refs` for that path.
2. **Implicit pass.** *Only if the explicit pass produced no anchors*, test the
   hunk's path against every requirement's globs. Each match emits an
   `Anchor(via="glob")`.
3. **Unanchored.** If neither pass produced an anchor, the hunk lands in
   `unanchored`.

Explicit anchors deliberately suppress implicit ones: once an author has stated
intent, PatchWeave trusts that statement rather than second-guessing it with glob
heuristics. This keeps the model predictable — an author can always override glob
inference by naming a requirement explicitly.

```
for hunk in manifest:
    anchors, unknown = [], []
    for rid in hunk.requirements:
        (anchors if rid in catalog else unknown).append(rid)
    if not anchors:
        for req in catalog:
            if req.matches(hunk.path):
                anchors.append(glob_anchor(hunk.path, req.id))
    classify(hunk, anchors, unknown)
```

Coverage then rolls up per requirement: a requirement is `met` when at least one
supporting path anchored to it, and `reviewed` only when *every* supporting path
carries a reviewer.

---

## The review-queue scoring model

Each review item receives a priority score in `[0, 100]`, a weighted blend of
four normalized signals:

| Signal    | Source                                                     | Intuition                                    |
| --------- | ---------------------------------------------------------- | -------------------------------------------- |
| `risk`    | requirement risk tier (or `elevated` for unanchored)       | critical paths demand attention              |
| `surface` | hunk churn ÷ largest churn in the set                      | bigger changes carry more places to hide bugs |
| `gap`     | 1.0 when unanchored or unreviewed, else 0.0                | governance gaps are the whole point          |
| `blast`   | distinct requirements touched, capped at 3                 | cross-cutting edits ripple further           |

Default weights are `risk=0.35, surface=0.20, gap=0.30, blast=0.15`, normalized
before use. The bias toward `gap` and `risk` over `surface` is intentional: a
tiny unanchored edit to a critical file outranks a large, well-anchored,
already-reviewed refactor.

Ties break on **path ascending**, so the queue is fully deterministic. See
[DESIGN.md](DESIGN.md) for the rationale and worked numeric examples.

---

## The native metric engine

`core/patch_metrics.cpp` is a portable C++17 filter that reads a unified diff on
stdin and prints `key=value` metric lines on stdout:

```
files=3
added=17
removed=2
hunks=4
largest_file=b/src/checkout/session.py
largest_churn=10
```

The Python bridge (`patchweave/native.py`) locates a compiler, builds a cached
binary next to the source, streams the diff through it, and parses the output. If
no compiler exists it uses `python_metrics`, which is behaviorally identical, so
the CLI never breaks on a machine without a toolchain. Force the pure path with
`--pure` to compare, or to keep a build sandboxed.

---

## Output schemas

### JSON brief (`patchweave/v1`)

```json
{
  "schema": "patchweave/v1",
  "session": "...",
  "branch": "...",
  "release": "...",
  "surface": { "added": 357, "removed": 57, "churn": 414, "anchor_ratio": 0.7143 },
  "gaps": {
    "unanchored": ["src/util/hashing.py"],
    "unmet_requirements": ["REQ-OBS-7"],
    "partial_requirements": ["REQ-CHK-2"],
    "unknown_refs": { "scripts/dev-seed.py": ["REQ-GONE-1"] }
  },
  "requirements": [ { "id": "...", "state": "reviewed", "supporting_paths": ["..."] } ],
  "queue": [ { "path": "...", "score": 76.52, "risk": "critical", "flags": [] } ]
}
```

### Metric object

```json
{ "files": 3, "added": 17, "removed": 2, "hunks": 4,
  "largest_file": "b/src/checkout/session.py", "largest_churn": 10 }
```

---

## Operations and CI gating

Wire `gaps` into your pipeline to block merges that leave governance debt:

```yaml
- name: PatchWeave gate
  run: |
    python -m patchweave gaps \
