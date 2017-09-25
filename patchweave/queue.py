"""Assemble focused, deterministic review queues from a weave report.

A raw list of changes is a poor review artifact: reviewers want the *riskiest,
least-covered* work first, and they want a stable order so two runs over the same
inputs produce the same queue. :class:`QueueBuilder` turns a
:class:`~patchweave.weave.WeaveReport` into ordered :class:`ReviewItem` records.

Scoring model
-------------
Each review item receives a priority score in ``[0, 100]``. The score is a
weighted blend of four normalized signals:

- ``risk``    — the requirement risk tier (critical > elevated > notable > routine)
- ``surface`` — churn contributed by the change relative to the largest hunk
- ``gap``     — whether the change is unanchored or its requirement is unreviewed
- ``blast``   — number of distinct requirements the change touches

The default weights favor governance gaps and risk over raw size, because a tiny
unanchored edit to a critical path is more dangerous than a large, well-anchored,
already-reviewed refactor. Weights are overridable via :class:`QueueWeights`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .model import RISK_ORDER
from .weave import WeaveReport, anchor_index


@dataclass(frozen=True)
class QueueWeights:
    risk: float = 0.35
    surface: float = 0.20
    gap: float = 0.30
    blast: float = 0.15

    def normalized(self) -> "QueueWeights":
        total = self.risk + self.surface + self.gap + self.blast
        if total <= 0:
            return QueueWeights()
        return QueueWeights(
            risk=self.risk / total,
            surface=self.surface / total,
            gap=self.gap / total,
            blast=self.blast / total,
        )


@dataclass(frozen=True)
class ReviewItem:
    path: str
    score: float
    risk: str
    churn: int
    requirement_ids: List[str]
    flags: List[str]  # e.g. ["unanchored"], ["unreviewed-req"], ["unknown-ref"]

    def as_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "score": round(self.score, 2),
            "risk": self.risk,
            "churn": self.churn,
            "requirements": list(self.requirement_ids),
            "flags": list(self.flags),
        }


class QueueBuilder:
    """Build a ranked review queue from a weave report."""

    def __init__(self, report: WeaveReport, weights: QueueWeights | None = None) -> None:
        self.report = report
        self.weights = (weights or QueueWeights()).normalized()
        self._index = anchor_index(report)
        # Map path -> churn for surface normalization.
        self._churn: Dict[str, int] = {}
        for hunk in report.unanchored:
            self._churn[hunk.path] = hunk.churn
        # supporting hunks are not directly available; reconstruct churn via anchors
        # requires the original manifest, so we accept churn only for what we know.

    def _peak_churn(self) -> int:
        return max((c for c in self._churn.values()), default=1) or 1

    def _risk_component(self, risk: str) -> float:
        idx = RISK_ORDER.index(risk) if risk in RISK_ORDER else 0
        return idx / (len(RISK_ORDER) - 1)

    def build(self, manifest_churn: Dict[str, int] | None = None) -> List[ReviewItem]:
        """Produce a stably-ordered review queue.

        *manifest_churn* optionally supplies path -> churn for anchored hunks so
        the surface component is accurate for every item, not only unanchored
        ones. The CLI passes this in from the loaded manifest.
        """
        churn_map = dict(self._churn)
        if manifest_churn:
            churn_map.update(manifest_churn)
        peak = max((c for c in churn_map.values()), default=1) or 1

        w = self.weights
        items: List[ReviewItem] = []

        # Unanchored hunks: maximum governance gap.
        for hunk in self.report.unanchored:
            flags = ["unanchored"]
            if hunk.path in self.report.unknown_refs:
                flags.append("unknown-ref")
            surface = hunk.churn / peak
            score = 100.0 * (
                w.risk * self._risk_component("elevated")
                + w.surface * surface
                + w.gap * 1.0
                + w.blast * 0.0
            )
            items.append(
                ReviewItem(
                    path=hunk.path,
                    score=score,
                    risk="unanchored",
                    churn=hunk.churn,
                    requirement_ids=[],
                    flags=flags,
