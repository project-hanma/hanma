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
from dataclasses import dataclass
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any, Iterator, Optional

try:
  import yaml
except ImportError as exc:
  raise RuntimeError(
    "Required package 'pyyaml' not found. Install it with:  pip install pyyaml"
  ) from exc

YAMLError = yaml.YAMLError


def safe_load_yaml(text: str) -> Any:
  """Parse YAML text safely using PyYAML."""
  return yaml.safe_load(text)


@dataclass(frozen=True)
class BuildContext:
  """Shared site-wide configuration and template context for a build."""
  site_name: str
  base_url: str = ""
  output_dir: Optional[Path] = None
  posts_out: Optional[Path] = None
  posts_label: str = "Blog"
  recent_posts: Optional[list] = None
  sanitize: bool = False
  timezone: Optional[str] = None
  search_enabled: bool = True
  sidebar_side: str = "right"
  template: Any = None
  resolved_root_index: Optional[Path] = None


# ── Constants ─────────────────────────────────────────────────────────────────
# Anchor for themes/ — same directory as hanma.py since all files are siblings
_THEMES_DIR = Path(__file__).parent.parent / "themes"


def sync_file_if_changed(src: Path, dest: Path,
                         src_stat: Optional[os.stat_result] = None) -> bool:
  """Copy src to dest only if dest is missing or its size/mtime_ns differs."""
  try:
    st_src = src_stat if src_stat is not None else src.stat()
    try:
      dest_stat = dest.stat()
    except FileNotFoundError:
      dest_stat = None
    if (dest_stat is not None
        and stat.S_ISREG(dest_stat.st_mode)
        and st_src.st_size == dest_stat.st_size
        and st_src.st_mtime_ns == dest_stat.st_mtime_ns):
      return False
  except OSError:
    pass
  dest.parent.mkdir(parents=True, exist_ok=True)
  shutil.copy2(src, dest)
  return True


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8",
                      mode: int = 0o644) -> None:
  """Write content to a temporary file and atomically replace the target path."""
  try:
    fd, temp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", text=True)
  except FileNotFoundError:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", text=True)
  try:
    os.fchmod(fd, mode)
    with os.fdopen(fd, "w", encoding=encoding) as f:
      f.write(content)
    os.replace(temp_path, path)
  except Exception:
    if os.path.exists(temp_path):
      os.unlink(temp_path)
    raise


def write_text_if_changed(path: Path, content: str, encoding: str = "utf-8",
                          mode: int = 0o644) -> bool:
  """Write content atomically only when path is missing or its contents differ."""
  try:
    if path.is_file() and path.read_text(encoding=encoding) == content:
      return False
  except OSError:
    pass
  atomic_write_text(path, content, encoding=encoding, mode=mode)
  return True


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


def iter_safe_files(directory: Path,
                    resolved_root: Path) -> Iterator[tuple[Path, os.stat_result]]:
  """Yield (path, stat_result) for regular files under directory inside resolved_root."""
  try:
    entries = list(os.scandir(directory))
  except OSError:
    return
  for entry in entries:
    entry_path = Path(entry.path)
    try:
      if not entry_path.resolve().is_relative_to(resolved_root):
        continue
      st = entry.stat(follow_symlinks=True)
    except OSError:
      continue
    if stat.S_ISDIR(st.st_mode):
      yield from iter_safe_files(entry_path, resolved_root)
    elif stat.S_ISREG(st.st_mode):
      yield entry_path, st


def prune_stale_files(root_dir: Path, expected_files: set[Path]) -> None:
  """Delete files under root_dir not present in expected_files and prune empty dirs."""
  if not root_dir.is_dir():
    return
  for existing in sorted(root_dir.rglob("*")):
    if existing.is_file() and existing not in expected_files:
      try:
        existing.unlink()
        parent = existing.parent
        while parent != root_dir:
          try:
            parent.rmdir()
            parent = parent.parent
          except OSError:
            break
      except OSError:
        pass
