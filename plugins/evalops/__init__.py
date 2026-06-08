"""Hermes plugin entrypoint for local, non-installed demos."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hermes_evalops_plugin import register  # noqa: E402

__all__ = ["register"]

