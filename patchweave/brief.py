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
