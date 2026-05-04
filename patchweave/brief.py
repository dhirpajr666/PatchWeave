"""Render release review briefs from a weave report and review queue.

Three renderers are provided, all pure functions with no side effects:

- :func:`render_brief` — a human-readable ANSI/plain terminal report.
- :func:`render_markdown` — a portable Markdown brief for pasting into a PR.
- :func:`render_json` — a machine-readable artifact stamped with the schema id.

The terminal renderer degrades gracefully: when ``color=False`` (the default for
non-TTY output) it emits plain ASCII with box-drawing separators so logs stay
diff-friendly.
"""

from __future__ import annotations

import json
from typing import Dict, List, Sequence

from . import PATCHWEAVE_SCHEMA
from .queue import ReviewItem
from .weave import WeaveReport


# --- small ANSI helpers -----------------------------------------------------

_ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "orange": "\033[38;5;208m",
    "navy": "\033[38;5;24m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
}


def _c(text: str, *styles: str, enabled: bool) -> str:
    if not enabled:
        return text
    prefix = "".join(_ANSI[s] for s in styles if s in _ANSI)
    return f"{prefix}{text}{_ANSI['reset']}"


def _bar(fraction: float, width: int = 24) -> str:
    fraction = max(0.0, min(1.0, fraction))
    filled = int(round(fraction * width))
    return "#" * filled + "-" * (width - filled)


# --- terminal renderer ------------------------------------------------------

def render_brief(report: WeaveReport, queue: Sequence[ReviewItem], color: bool = False) -> str:
    lines: List[str] = []
    title = f" PATCHWEAVE REVIEW BRIEF :: {report.session} "
    lines.append(_c("=" * 60, "orange", enabled=color))
    lines.append(_c(title, "bold", "orange", enabled=color))
    lines.append(_c("=" * 60, "orange", enabled=color))
    lines.append("")
    lines.append(f"  branch   : {report.branch}")
    lines.append(f"  release  : {report.release}")
    lines.append(
        f"  surface  : +{report.total_added} / -{report.total_removed}"
        f"  (churn {report.total_churn})"
    )
    ratio = report.anchor_ratio
    lines.append(
        f"  anchored : {ratio * 100:5.1f}%  [{_bar(ratio)}]"
    )
    lines.append("")

    # Governance gaps
    lines.append(_c("-- GOVERNANCE GAPS " + "-" * 41, "navy", enabled=color))
    unmet = report.unmet()
    partial = report.partial()
    lines.append(f"  unanchored changes : {len(report.unanchored)}")
    lines.append(f"  unmet requirements : {len(unmet)}")
    lines.append(f"  partial (unreviewed): {len(partial)}")
    if report.unknown_refs:
        lines.append(
            f"  unknown references : {sum(len(v) for v in report.unknown_refs.values())}"
        )
    lines.append("")

    if unmet:
        lines.append(_c("  Unmet requirements:", "yellow", enabled=color))
        for status in unmet:
            lines.append(
                f"    - {status.requirement.id} [{status.requirement.risk}] "
                f"{status.requirement.title}"
            )
        lines.append("")

    # Risk histogram
    lines.append(_c("-- RISK DISTRIBUTION " + "-" * 39, "navy", enabled=color))
    hist = report.risk_histogram()
    peak = max(hist.values()) or 1
    for tier, count in hist.items():
        lines.append(f"  {tier:<9} {count:>3}  {_bar(count / peak, 20)}")
    lines.append("")

    # Review queue (top slice)
    lines.append(_c("-- REVIEW QUEUE (top 12) " + "-" * 35, "navy", enabled=color))
    if not queue:
        lines.append("  (queue empty — nothing to review)")
    for item in queue[:12]:
        flag = ",".join(item.flags) if item.flags else "-"
        lines.append(
            f"  {item.score:6.2f}  {item.path:<34.34} "
            f"[{item.risk:<10.10}] churn={item.churn:<4} {flag}"
        )
    lines.append("")
    lines.append(_c("=" * 60, "orange", enabled=color))
    return "\n".join(lines)


# --- markdown renderer ------------------------------------------------------

def render_markdown(report: WeaveReport, queue: Sequence[ReviewItem]) -> str:
    md: List[str] = []
    md.append(f"# Review Brief — {report.session}")
    md.append("")
    md.append(f"- **Branch:** `{report.branch}`")
    md.append(f"- **Release:** `{report.release}`")
    md.append(f"- **Patch surface:** +{report.total_added} / -{report.total_removed} "
              f"(churn {report.total_churn})")
    md.append(f"- **Anchor ratio:** {report.anchor_ratio * 100:.1f}%")
    md.append("")
    md.append("## Governance Gaps")
    md.append("")
    md.append("| Signal | Count |")
    md.append("| --- | --- |")
    md.append(f"| Unanchored changes | {len(report.unanchored)} |")
    md.append(f"| Unmet requirements | {len(report.unmet())} |")
    md.append(f"| Partial (unreviewed) | {len(report.partial())} |")
    md.append(f"| Unknown references | {sum(len(v) for v in report.unknown_refs.values())} |")
    md.append("")
    md.append("## Review Queue")
    md.append("")
    md.append("| # | Score | Path | Risk | Churn | Flags |")
    md.append("| --- | --- | --- | --- | --- | --- |")
    for i, item in enumerate(queue, start=1):
        flag = ", ".join(item.flags) if item.flags else "—"
        md.append(
            f"| {i} | {item.score:.2f} | `{item.path}` | {item.risk} | "
            f"{item.churn} | {flag} |"
        )
    md.append("")
    return "\n".join(md)


# --- json renderer ----------------------------------------------------------

def render_json(report: WeaveReport, queue: Sequence[ReviewItem]) -> str:
    payload: Dict[str, object] = {
        "schema": PATCHWEAVE_SCHEMA,
        "session": report.session,
        "branch": report.branch,
        "release": report.release,
        "surface": {
            "added": report.total_added,
            "removed": report.total_removed,
            "churn": report.total_churn,
            "anchor_ratio": round(report.anchor_ratio, 4),
        },
        "gaps": {
            "unanchored": [h.path for h in report.unanchored],
            "unmet_requirements": [s.requirement.id for s in report.unmet()],
            "partial_requirements": [s.requirement.id for s in report.partial()],
            "unknown_refs": report.unknown_refs,
        },
        "requirements": [
            {
                "id": s.requirement.id,
                "title": s.requirement.title,
                "risk": s.requirement.risk,
                "state": s.state,
                "supporting_paths": s.supporting_paths,
                "reviewed_paths": s.reviewed_paths,
            }
            for s in report.statuses.values()
        ],
        "queue": [item.as_dict() for item in queue],
    }
    return json.dumps(payload, indent=2, sort_keys=False)

# draft note 1421
