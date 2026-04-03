#!/usr/bin/env python3
# hanma.py — It builds your blog. That's mostly it.
# Copyright (C) 2026  Chris Hammer
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see
# <https://www.gnu.org/licenses/>.
"""
hanma.py — Static Site Generator entry point.

All logic lives in app/. This file is the thin CLI launcher.

Usage:
  ./hanma.py [options] [path]

Run ./hanma.py --help for full usage.
"""

import sys
from pathlib import Path

# Ensure app/ (sibling of this file) is importable regardless of how
# Python was invoked (e.g. via importlib.util.spec_from_file_location in tests).
_here = Path(__file__).parent
if str(_here) not in sys.path:
  sys.path.insert(0, str(_here))

try:
  from app.cli import main
except RuntimeError as _exc:
  print(f"Error: {_exc}")
  sys.exit(1)

if __name__ == "__main__":
  main()
