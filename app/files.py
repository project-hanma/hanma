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
"""File and directory utilities for Hanma."""
import errno
import sys
from pathlib import Path

from app.utils import sync_file_if_changed

POSTS_DIR_NAME = "posts"


def find_markdown_files(root: Path) -> list[Path]:
  """Recursively find all .md and .markdown files under root.

  Skips any path whose components include a dotfile/dotdir (e.g. .venv)
  or symlinks that resolve outside root.
  """
  IGNORE_NAMES = {"README.md", "README.markdown", "readme.md", "readme.markdown"}
  resolved_root = root.resolve()

  def has_dotpart(p: Path) -> bool:
    return any(part.startswith(".") for part in p.relative_to(root).parts)

  def is_within_root(p: Path) -> bool:
    try:
      return p.resolve().is_relative_to(resolved_root)
    except OSError:
      return False

  return sorted(
    p for p in root.rglob("*")
    if p.suffix.lower() in {".md", ".markdown"}
    and is_within_root(p)
    and p.is_file()
    and p.stat().st_size > 0
    and not has_dotpart(p)
    and p.name not in IGNORE_NAMES
  )


def copy_static_assets(source_root: Path, output_root: Path) -> None:
  """Synchronize <source_root>/static/ to <output_root>/static/ differentially.

  Does nothing if no static/ directory exists in source_root.
  Skips symlinks resolving outside source_root and prunes deleted destination files.
  """
  static_src = source_root / "static"
  if not static_src.is_dir():
    return
  resolved_root = source_root.resolve()
  if not static_src.resolve().is_relative_to(resolved_root):
    return
  static_dest = output_root / "static"
  static_dest.mkdir(parents=True, exist_ok=True)

  expected_dest_files: set[Path] = set()
  for src_file in static_src.rglob("*"):
    try:
      if not src_file.resolve().is_relative_to(resolved_root):
        continue
    except OSError:
      continue
    if not src_file.is_file():
      continue
    rel = src_file.relative_to(static_src)
    dest_file = static_dest / rel
    expected_dest_files.add(dest_file)
    sync_file_if_changed(src_file, dest_file)

  # Prune stale files in static_dest that no longer exist in static_src
  for dest_file in sorted(static_dest.rglob("*")):
    if dest_file.is_file() and dest_file not in expected_dest_files:
      try:
        dest_file.unlink()
        parent = dest_file.parent
        while parent != static_dest:
          try:
            parent.rmdir()
            parent = parent.parent
          except OSError:
            break
      except OSError:
        pass

  print(f"  [static] copied {len(expected_dest_files)} file(s) from static/")


def clean_stale_html(output_dir: Path, expected_html: set[Path]) -> list[Path]:
  """Remove .html files in output_dir that have no corresponding source page.

  expected_html is the set of output paths that should exist after generation.
  Returns the list of paths that were removed.
  """
  removed = []
  for html_file in sorted(output_dir.rglob("*.html")):
    if html_file not in expected_html:
      try:
        html_file.unlink()
        removed.append(html_file)
        # Remove empty parent directories up to output_dir
        parent = html_file.parent
        while parent != output_dir:
          try:
            parent.rmdir()  # only removes if empty
            parent = parent.parent
          except OSError as exc:
            # Narrow to 'directory not empty' or 'directory exists'
            if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST):
              raise
            break
      except OSError as exc:
        print(f"  [clean] warning: could not remove {html_file}: {exc}", file=sys.stderr)
  return removed
