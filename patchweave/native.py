"""Bridge to the portable C++17 metric engine ``core/patch_metrics.cpp``.

The heavy per-line churn accounting is delegated to a small native tool for
speed and to demonstrate PatchWeave's mixed-language seam. This module locates a
C++ toolchain, compiles the source on demand into a cached binary, and streams
diff bodies through it.

The bridge is *optional*: :func:`native_metrics` raises
:class:`NativeUnavailable` when no compiler is found, and callers fall back to a
pure-Python implementation (:func:`python_metrics`) so the CLI always works.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional


class NativeUnavailable(RuntimeError):
    """Raised when no C++ toolchain is available to build the metric engine."""


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "core", "patch_metrics.cpp")
