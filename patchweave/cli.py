"""PatchWeave command-line interface.

Verbs
-----
``weave``    Map changes to requirements and print a terminal review brief.
``queue``    Emit only the ranked review queue (text or json).
``brief``    Emit a full brief in text, markdown, or json.
``gaps``     Print governance gaps (unanchored / unmet / unknown) and exit
             non-zero when any gap crosses the configured threshold — ideal for
             CI gating.
``metrics``  Run the native (or fallback) diff metric engine over a diff file.

Every verb accepts ``--manifest`` and ``--catalog`` except ``metrics`` which
takes ``--diff``. Run ``patchweave <verb> --help`` for details.
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Optional

from . import __version__
from .brief import render_brief, render_json, render_markdown
from .model import ManifestError, load_catalog, load_manifest
from .native import DiffMetrics, NativeUnavailable, metrics as run_metrics
from .queue import QueueBuilder, QueueWeights
from .weave import Weaver


def _churn_map(manifest) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for h in manifest.hunks:
        out[h.path] = out.get(h.path, 0) + h.churn
    return out


def _load_pair(args) -> tuple:
    manifest = load_manifest(args.manifest)
    catalog = load_catalog(args.catalog)
    return manifest, catalog

