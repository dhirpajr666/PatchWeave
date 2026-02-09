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
          f"anchor_ratio={report.anchor_ratio * 100:.1f}%")
    for h in report.unanchored:
        print(f"  UNANCHORED  {h.path}  churn={h.churn}")
    for s in report.unmet():
        print(f"  UNMET       {s.requirement.id}  [{s.requirement.risk}]  {s.requirement.title}")
    for path, ids in report.unknown_refs.items():
        print(f"  UNKNOWN-REF {path}  -> {', '.join(ids)}")

    total_gaps = unanchored + unmet + unknown
    if args.max_gaps is not None and total_gaps > args.max_gaps:
        print(f"gate: {total_gaps} gaps exceed threshold {args.max_gaps}", file=sys.stderr)
        return 2
    return 0


def cmd_metrics(args) -> int:
    with open(args.diff, "r", encoding="utf-8") as fh:
        diff_text = fh.read()
    m: DiffMetrics = run_metrics(diff_text, prefer_native=not args.pure)
    if args.format == "json":
        import json

        print(json.dumps(m.as_dict(), indent=2))
    else:
        print(f"files         : {m.files}")
        print(f"hunks         : {m.hunks}")
        print(f"added         : {m.added}")
        print(f"removed       : {m.removed}")
        print(f"largest_file  : {m.largest_file}")
        print(f"largest_churn : {m.largest_churn}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="patchweave",
        description="PatchWeave — Coding-Agent Change Review Lab",
    )
    p.add_argument("--version", action="version", version=f"patchweave {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add_pair(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--manifest", required=True, help="path to change manifest JSON")
        sp.add_argument("--catalog", required=True, help="path to requirement catalog JSON")

    sp = sub.add_parser("weave", help="print a terminal review brief")
    add_pair(sp)
    sp.add_argument("--color", action="store_true", help="enable ANSI colour")
    sp.add_argument("--weights", help="queue weights as r,s,g,b floats")
    sp.set_defaults(func=cmd_weave)

    sp = sub.add_parser("queue", help="print the ranked review queue")
    add_pair(sp)
    sp.add_argument("--format", choices=["text", "json"], default="text")
    sp.add_argument("--weights", help="queue weights as r,s,g,b floats")
    sp.set_defaults(func=cmd_queue)

    sp = sub.add_parser("brief", help="render a full brief")
    add_pair(sp)
    sp.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    sp.add_argument("--color", action="store_true")
    sp.add_argument("--weights", help="queue weights as r,s,g,b floats")
    sp.set_defaults(func=cmd_brief)

    sp = sub.add_parser("gaps", help="print governance gaps (CI gate)")
    add_pair(sp)
    sp.add_argument("--max-gaps", type=int, default=None,
                    help="exit non-zero when total gaps exceed this")
    sp.set_defaults(func=cmd_gaps)

    sp = sub.add_parser("metrics", help="run the native diff metric engine")
    sp.add_argument("--diff", required=True, help="path to a unified diff file")
    sp.add_argument("--format", choices=["text", "json"], default="text")
    sp.add_argument("--pure", action="store_true", help="force pure-Python engine")
    sp.set_defaults(func=cmd_metrics)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except NativeUnavailable as exc:
        print(f"native engine unavailable: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# draft note 1395
