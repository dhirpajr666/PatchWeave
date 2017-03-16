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
