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
