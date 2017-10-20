"""The weaving engine: map changes to requirements and score coverage.

The :class:`Weaver` is the analytical heart of PatchWeave. Given a
:class:`~patchweave.model.Manifest` and :class:`~patchweave.model.Catalog`, it
produces a :class:`WeaveReport` that answers four questions a reviewer always
asks:

1. **Which requirement authorizes each change?** — the *anchor map*.
2. **Which changes are unanchored?** — edits that cite no requirement, or cite a
   requirement that does not exist in the catalog.
3. **Which requirements are unreviewed / unmet?** — requirements with no
   supporting change, or with changes but no reviewer sign-off.
4. **How large is the patch surface, and where is the risk concentrated?**

Anchoring resolution
--------------------
A change is anchored to a requirement when *either* of these holds:

- The change explicitly lists the requirement id in ``requirements`` (an
  *explicit* anchor), or
- The change's path matches one of the requirement's ``globs`` (an *implicit*
  anchor).

Explicit anchors always win and are reported with ``via="explicit"``. Implicit
anchors are reported with ``via="glob"`` and only apply when no explicit anchor
was declared. A change that satisfies neither is *unanchored*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .model import Catalog, Hunk, Manifest, Requirement, RISK_ORDER


@dataclass(frozen=True)
class Anchor:
    """A resolved link between a change (path) and a requirement id."""

    path: str
    requirement_id: str
    via: str  # "explicit" or "glob"


@dataclass
class RequirementStatus:
    """Coverage roll-up for a single requirement."""

    requirement: Requirement
    supporting_paths: List[str] = field(default_factory=list)
    reviewed_paths: List[str] = field(default_factory=list)

    @property
    def met(self) -> bool:
        return len(self.supporting_paths) > 0

    @property
    def fully_reviewed(self) -> bool:
        return self.met and len(self.reviewed_paths) == len(self.supporting_paths)

    @property
    def state(self) -> str:
        if not self.met:
            return "unmet"
        if self.fully_reviewed:
            return "reviewed"
        return "partial"


@dataclass
class WeaveReport:
    """The full analysis produced by :meth:`Weaver.weave`."""

    session: str
    branch: str
    release: str
    anchors: List[Anchor]
    unanchored: List[Hunk]
    unknown_refs: Dict[str, List[str]]  # path -> unknown requirement ids
    statuses: Dict[str, RequirementStatus]
    total_added: int
    total_removed: int

    @property
    def total_churn(self) -> int:
        return self.total_added + self.total_removed

    @property
    def anchor_ratio(self) -> float:
        anchored_paths = {a.path for a in self.anchors}
        touched = anchored_paths | {h.path for h in self.unanchored}
        if not touched:
            return 1.0
        return len(anchored_paths) / len(touched)

    def unmet(self) -> List[RequirementStatus]:
        return [s for s in self.statuses.values() if not s.met]

    def partial(self) -> List[RequirementStatus]:
        return [s for s in self.statuses.values() if s.state == "partial"]

    def risk_histogram(self) -> Dict[str, int]:
        hist = {tier: 0 for tier in RISK_ORDER}
        for status in self.statuses.values():
            hist[status.requirement.risk] += 1
        return hist


class Weaver:
    """Resolve anchors and compute requirement coverage."""

    def __init__(self, manifest: Manifest, catalog: Catalog) -> None:
        self.manifest = manifest
        self.catalog = catalog
        self._by_id = catalog.by_id()

    def _resolve_hunk(self, hunk: Hunk) -> Tuple[List[Anchor], List[str]]:
        """Return (anchors, unknown_ids) for a single hunk."""
        anchors: List[Anchor] = []
        unknown: List[str] = []

        # Explicit anchors take priority.
        for rid in hunk.requirements:
            if rid in self._by_id:
                anchors.append(Anchor(hunk.path, rid, "explicit"))
            else:
                unknown.append(rid)

        # Implicit (glob) anchors only when no explicit anchor resolved.
        if not anchors:
            for req in self.catalog.requirements:
                if req.matches(hunk.path):
                    anchors.append(Anchor(hunk.path, req.id, "glob"))

        return anchors, unknown

    def weave(self) -> WeaveReport:
        anchors: List[Anchor] = []
        unanchored: List[Hunk] = []
        unknown_refs: Dict[str, List[str]] = {}
        statuses: Dict[str, RequirementStatus] = {
            r.id: RequirementStatus(requirement=r) for r in self.catalog.requirements
        }

        total_added = 0
        total_removed = 0

        for hunk in self.manifest.hunks:
            total_added += hunk.added
