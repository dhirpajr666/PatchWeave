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
_BIN = os.path.join(_ROOT, "core", "patch_metrics.bin")


@dataclass(frozen=True)
class DiffMetrics:
    files: int
    added: int
    removed: int
    hunks: int
    largest_file: str
    largest_churn: int

    def as_dict(self) -> Dict[str, object]:
        return {
            "files": self.files,
            "added": self.added,
            "removed": self.removed,
            "hunks": self.hunks,
            "largest_file": self.largest_file,
            "largest_churn": self.largest_churn,
        }


def _find_compiler() -> Optional[str]:
    for candidate in ("g++", "clang++", "c++"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def build_native(force: bool = False) -> str:
    """Compile the C++ metric engine; return the binary path.

    The binary is cached next to the source and only rebuilt when missing,
    stale, or ``force`` is set.
    """
    compiler = _find_compiler()
    if compiler is None:
        raise NativeUnavailable("no C++ compiler (g++/clang++/c++) on PATH")
    if not os.path.exists(_SRC):
        raise NativeUnavailable(f"metric source missing: {_SRC}")

    binary = _BIN + (".exe" if os.name == "nt" else "")
    fresh = (
        not force
        and os.path.exists(binary)
        and os.path.getmtime(binary) >= os.path.getmtime(_SRC)
    )
    if fresh:
        return binary

    cmd = [compiler, "-std=c++17", "-O2", "-o", binary, _SRC]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise NativeUnavailable(f"compile failed: {proc.stderr.strip()}")
    return binary


def native_metrics(diff_text: str) -> DiffMetrics:
    """Run the compiled engine over *diff_text* and parse its output.

    The engine emits ``key=value`` lines on stdout, one per metric.
    """
    binary = build_native()
    proc = subprocess.run(
        [binary], input=diff_text, capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise NativeUnavailable(f"engine error: {proc.stderr.strip()}")
    return _parse_kv(proc.stdout)


def _parse_kv(text: str) -> DiffMetrics:
    kv: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
