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
