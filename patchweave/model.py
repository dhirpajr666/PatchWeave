"""Data model and loaders for PatchWeave inputs.

Two documents drive the whole system:

``manifest``
    A JSON object describing a review-worthy change set. Each entry is a *hunk*:
    a single file touched in the session, annotated with the requirement ids it
    claims to satisfy, the reviewer (if any) who signed off, and raw line-delta
    counts.

``catalog``
    A JSON object describing the requirements the session was meant to fulfil.
    Each requirement carries a stable id, a human title, a risk tier, and an
    optional list of path globs it is expected to touch.

Both loaders are intentionally strict: unknown top-level keys are tolerated
(forward-compatibility) but malformed entries raise :class:`ManifestError` so a
broken input never silently produces a misleading review brief.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any, Dict, Iterable, List, Optional, Sequence


class ManifestError(ValueError):
    """Raised when a manifest or catalog document is structurally invalid."""


# Risk tiers, ordered from least to most severe. Used to rank review queues.
RISK_ORDER = ("routine", "notable", "elevated", "critical")


def _risk_rank(tier: str) -> int:
    try:
        return RISK_ORDER.index(tier)
    except ValueError:
        return -1


@dataclass(frozen=True)
class Hunk:
    """A single file touched in a change set."""

    path: str
    added: int
    removed: int
    requirements: Sequence[str] = field(default_factory=tuple)
    reviewer: Optional[str] = None
    kind: str = "modify"  # one of: add, modify, delete, rename

    @property
    def churn(self) -> int:
        """Total lines touched (added + removed)."""
        return self.added + self.removed

    @property
    def net(self) -> int:
        """Net line delta (added - removed)."""
        return self.added - self.removed

    @property
    def anchored(self) -> bool:
        """True when the hunk cites at least one requirement id."""
        return len(self.requirements) > 0

    @property
    def reviewed(self) -> bool:
        """True when a reviewer has been recorded for the hunk."""
        return bool(self.reviewer)


@dataclass(frozen=True)
class Requirement:
    """A unit of intended work the change set is meant to satisfy."""

    id: str
    title: str
    risk: str = "routine"
    globs: Sequence[str] = field(default_factory=tuple)
    owner: Optional[str] = None

    @property
    def risk_rank(self) -> int:
        return _risk_rank(self.risk)

    def matches(self, path: str) -> bool:
        """True when *path* satisfies one of this requirement's path globs."""
        return any(fnmatch(path, g) for g in self.globs)


@dataclass(frozen=True)
class Manifest:
    """A loaded, validated change manifest."""

    session: str
    branch: str
    hunks: List[Hunk]

    @property
    def total_churn(self) -> int:
        return sum(h.churn for h in self.hunks)

    def requirement_ids(self) -> set:
        seen: set = set()
        for h in self.hunks:
            seen.update(h.requirements)
        return seen


@dataclass(frozen=True)
class Catalog:
    """A loaded, validated requirement catalog."""

    release: str
    requirements: List[Requirement]

    def by_id(self) -> Dict[str, Requirement]:
        return {r.id: r for r in self.requirements}


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise ManifestError(message)


def _as_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError(f"{label} must be an integer, got {value!r}")
    if value < 0:
        raise ManifestError(f"{label} must be non-negative, got {value}")
    return value


def parse_manifest(doc: Dict[str, Any]) -> Manifest:
    """Validate and convert a raw manifest dict into a :class:`Manifest`."""

    _require(isinstance(doc, dict), "manifest root must be an object")
    session = str(doc.get("session", "unnamed-session"))
    branch = str(doc.get("branch", "HEAD"))
    raw_hunks = doc.get("changes", doc.get("hunks", []))
    _require(isinstance(raw_hunks, list), "'changes' must be a list")

    hunks: List[Hunk] = []
    for i, entry in enumerate(raw_hunks):
        _require(isinstance(entry, dict), f"change[{i}] must be an object")
        path = entry.get("path")
        _require(isinstance(path, str) and path, f"change[{i}].path is required")
        kind = str(entry.get("kind", "modify"))
        _require(
            kind in ("add", "modify", "delete", "rename"),
            f"change[{i}].kind '{kind}' is invalid",
        )
        reqs = entry.get("requirements", [])
        _require(isinstance(reqs, list), f"change[{i}].requirements must be a list")
        reviewer = entry.get("reviewer")
        if reviewer is not None:
            reviewer = str(reviewer)
        hunks.append(
            Hunk(
                path=path,
                added=_as_int(entry.get("added", 0), f"change[{i}].added"),
                removed=_as_int(entry.get("removed", 0), f"change[{i}].removed"),
                requirements=tuple(str(r) for r in reqs),
                reviewer=reviewer,
                kind=kind,
            )
        )
    return Manifest(session=session, branch=branch, hunks=hunks)


def parse_catalog(doc: Dict[str, Any]) -> Catalog:
    """Validate and convert a raw catalog dict into a :class:`Catalog`."""

    _require(isinstance(doc, dict), "catalog root must be an object")
    release = str(doc.get("release", "unversioned"))
    raw_reqs = doc.get("requirements", [])
    _require(isinstance(raw_reqs, list), "'requirements' must be a list")

    reqs: List[Requirement] = []
    seen_ids: set = set()
    for i, entry in enumerate(raw_reqs):
        _require(isinstance(entry, dict), f"requirement[{i}] must be an object")
        rid = entry.get("id")
        _require(isinstance(rid, str) and rid, f"requirement[{i}].id is required")
        _require(rid not in seen_ids, f"duplicate requirement id '{rid}'")
        seen_ids.add(rid)
        risk = str(entry.get("risk", "routine"))
        _require(
            _risk_rank(risk) >= 0,
            f"requirement[{i}].risk '{risk}' is not a known tier",
        )
        globs = entry.get("globs", [])
        _require(isinstance(globs, list), f"requirement[{i}].globs must be a list")
        owner = entry.get("owner")
        if owner is not None:
            owner = str(owner)
        reqs.append(
            Requirement(
                id=rid,
                title=str(entry.get("title", rid)),
                risk=risk,
                globs=tuple(str(g) for g in globs),
                owner=owner,
            )
        )
    return Catalog(release=release, requirements=reqs)


def _load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise ManifestError(f"file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:  # pragma: no cover - message passthrough
            raise ManifestError(f"invalid JSON in {path}: {exc}") from exc


def load_manifest(path: str) -> Manifest:
    """Load and validate a manifest document from *path*."""
    return parse_manifest(_load_json(path))


def load_catalog(path: str) -> Catalog:
    """Load and validate a catalog document from *path*."""
    return parse_catalog(_load_json(path))


def iter_paths(hunks: Iterable[Hunk]) -> Iterable[str]:
    for h in hunks:
        yield h.path

# draft note 1385
