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

