"""PatchWeave — Coding-Agent Change Review Lab.

PatchWeave consumes a *change manifest* (the files an agent or human touched in a
work session) together with a *requirement catalog* (the intended scope of work)
and weaves them into an auditable review artifact. It maps each changed file to
the requirements that authorize it, flags unanchored edits (changes with no
governing requirement), surfaces unreviewed requirements (requirements with no
supporting change), quantifies the patch surface, and assembles focused review
queues that a reviewer can burn down deterministically.

The package is dependency-free and uses only the Python standard library. A
portable C++17 companion (``core/patch_metrics.cpp``) computes churn metrics over
raw diff bodies and is invoked through the ``metrics`` CLI verb.

Public surface
--------------
- :func:`patchweave.model.load_manifest`
- :func:`patchweave.model.load_catalog`
- :class:`patchweave.weave.Weaver`
- :class:`patchweave.queue.QueueBuilder`
- :func:`patchweave.brief.render_brief`
"""

from __future__ import annotations

__all__ = [
    "__version__",
    "PATCHWEAVE_SCHEMA",
]

__version__ = "1.0.1"

# Schema identifier embedded in every emitted artifact so downstream consumers
# can pin to a known shape. Bump the minor when fields are added, the major when
# fields are removed or repurposed.
PATCHWEAVE_SCHEMA = "patchweave/v1"

# draft note 1378
