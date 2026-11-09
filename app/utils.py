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
"""Common utilities and constants for Hanma."""
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional


# ── Constants ─────────────────────────────────────────────────────────────────
# Anchor for themes/ — same directory as hanma.py since all files are siblings
_THEMES_DIR = Path(__file__).parent.parent / "themes"


def sync_file_if_changed(src: Path, dest: Path) -> bool:
  """Copy src to dest only if dest is missing or its size/mtime_ns differs."""
  try:
    src_stat = src.stat()
    if dest.is_file():
      dest_stat = dest.stat()
      if src_stat.st_size == dest_stat.st_size and src_stat.st_mtime_ns == dest_stat.st_mtime_ns:
        return False
  except OSError:
    pass
  dest.parent.mkdir(parents=True, exist_ok=True)
  shutil.copy2(src, dest)
  return True


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
  """Write content to a temporary file and atomically replace the target path."""
  path.parent.mkdir(parents=True, exist_ok=True)
  fd, temp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", text=True)
  try:
    with os.fdopen(fd, "w", encoding=encoding) as f:
      f.write(content)
    os.replace(temp_path, path)
  except Exception:
    if os.path.exists(temp_path):
      os.unlink(temp_path)
    raise


def get_root_rel(output_root: Optional[Path], out_path: Path) -> str:
  """Calculate the relative path from the output file's directory back to root.

  Returns a string like "../../" or "" (if at root).
  """
  if not output_root:
    return ""
  
  root_rel = os.path.relpath(output_root, out_path.parent).replace(os.sep, "/")
  if root_rel == ".":
    return ""
  
  return root_rel.rstrip("/") + "/"
