#!/usr/bin/env python3
"""
hanma.py — Static Site Generator entry point.

All logic lives in hanma_core/. This file is the thin CLI launcher.

Usage:
  ./hanma.py [options] [path]

Run ./hanma.py --help for full usage.
"""

import sys
from pathlib import Path

# Ensure hanma_core/ (sibling of this file) is importable regardless of how
# Python was invoked (e.g. via importlib.util.spec_from_file_location in tests).
_here = Path(__file__).parent
if str(_here) not in sys.path:
  sys.path.insert(0, str(_here))

from hanma_core.cli import main

if __name__ == "__main__":
  main()
