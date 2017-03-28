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


def _build_queue(report, manifest, args) -> List:
    weights = QueueWeights()
    if getattr(args, "weights", None):
        try:
            parts = [float(x) for x in args.weights.split(",")]
            if len(parts) == 4:
                weights = QueueWeights(*parts)
        except ValueError:
            print("warning: --weights ignored (expected r,s,g,b floats)", file=sys.stderr)
    return QueueBuilder(report, weights).build(_churn_map(manifest))


def cmd_weave(args) -> int:
    manifest, catalog = _load_pair(args)
    report = Weaver(manifest, catalog).weave()
    queue = _build_queue(report, manifest, args)
    print(render_brief(report, queue, color=args.color))
    return 0


def cmd_queue(args) -> int:
    manifest, catalog = _load_pair(args)
    report = Weaver(manifest, catalog).weave()
    queue = _build_queue(report, manifest, args)
    if args.format == "json":
        import json

        print(json.dumps([i.as_dict() for i in queue], indent=2))
    else:
        for i, item in enumerate(queue, start=1):
            flag = ",".join(item.flags) if item.flags else "-"
            print(f"{i:>3}. {item.score:6.2f}  {item.path}  "
                  f"[{item.risk}] churn={item.churn} {flag}")
    return 0


def cmd_brief(args) -> int:
    manifest, catalog = _load_pair(args)
    report = Weaver(manifest, catalog).weave()
    queue = _build_queue(report, manifest, args)
    if args.format == "json":
        print(render_json(report, queue))
    elif args.format == "markdown":
        print(render_markdown(report, queue))
    else:
        print(render_brief(report, queue, color=args.color))
    return 0


def cmd_gaps(args) -> int:
    manifest, catalog = _load_pair(args)
    report = Weaver(manifest, catalog).weave()
    unanchored = len(report.unanchored)
    unmet = len(report.unmet())
    unknown = sum(len(v) for v in report.unknown_refs.values())
    print(f"unanchored={unanchored} unmet={unmet} unknown_refs={unknown} "
