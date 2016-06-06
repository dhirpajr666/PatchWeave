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
