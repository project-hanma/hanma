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
"""Theme loading and asset management for Hanma."""
import os
import stat
from pathlib import Path

try:
  import jinja2
except ImportError as exc:
  raise RuntimeError(
    "Required package 'Jinja2' not found. "
    "Install it with:  pip install Jinja2"
  ) from exc

from app.utils import iter_safe_files, prune_stale_files, sync_file_if_changed


class ThemeError(ValueError):
  """Raised when a theme cannot be loaded."""


def _load_theme_impl(name: str, themes_dir: Path) -> tuple:
  """Load template.html from themes_dir/<name>/ and return (Template, theme_dir).

  Raises ThemeError with a clear message if the theme or template.html is missing.
  themes_dir is passed explicitly so callers can control the lookup path
  (and tests can monkey-patch it via app._THEMES_DIR).
  """
  theme_dir = (themes_dir / name).resolve()
  if not theme_dir.is_relative_to(themes_dir.resolve()):
    raise ThemeError(f"theme name '{name}' is invalid (path traversal detected)")
  if not theme_dir.is_dir():
    available = sorted(d.name for d in themes_dir.iterdir() if d.is_dir()) \
      if themes_dir.is_dir() else []
    hint = f"  Available: {', '.join(available)}" if available else \
      "  (no themes/ directory found)"
    raise ThemeError(f"theme '{name}' not found at {theme_dir}\n{hint}")
  
  loader = jinja2.FileSystemLoader(str(theme_dir))
  env = jinja2.Environment(loader=loader, autoescape=True)
  try:
    return env.get_template("template.html"), theme_dir
  except jinja2.TemplateNotFound as exc:
    raise ThemeError(f"theme '{name}' is missing template.html ({theme_dir / 'template.html'})") from exc


_CSS_SUBDIR = Path("assets") / "css"


def _copy_assets_dir(src_assets_dir: Path, output_root: Path,
                     resolved_theme_dir: Path, expected_assets: set[Path]) -> None:
  for child, st in iter_safe_files(src_assets_dir, resolved_theme_dir):
    rel = child.relative_to(src_assets_dir)
    dest = output_root / "assets" / rel
    expected_assets.add(dest)
    sync_file_if_changed(child, dest, src_stat=st)


def copy_theme_assets(theme_dir: Path, output_root: Path) -> None:
  """Copy all non-template files from theme_dir into output_root/assets/.

  A theme subdirectory named 'assets' is merged into output_root/assets/
  directly (preserving its internal structure), so that paths like
  assets/css/style.css and assets/scripts/foo.js resolve correctly.
  Loose files (not inside assets/) fall back to output_root/assets/css/.
  template.html is always skipped. Stale theme assets are pruned (preserving pygments.css).
  """
  resolved_theme_dir = theme_dir.resolve()
  css_dir = output_root / _CSS_SUBDIR
  assets_root = output_root / "assets"
  expected_assets: set[Path] = {css_dir / "pygments.css"}

  for entry in os.scandir(theme_dir):
    if entry.name == "template.html":
      continue
    src = Path(entry.path)
    try:
      if not src.resolve().is_relative_to(resolved_theme_dir):
        continue
      st = entry.stat(follow_symlinks=True)
    except OSError:
      continue
    if stat.S_ISDIR(st.st_mode) and entry.name == "assets":
      _copy_assets_dir(src, output_root, resolved_theme_dir, expected_assets)
      continue
    dest = css_dir / entry.name
    if stat.S_ISREG(st.st_mode):
      expected_assets.add(dest)
      sync_file_if_changed(src, dest, src_stat=st)
    elif stat.S_ISDIR(st.st_mode):
      for child, child_st in iter_safe_files(src, resolved_theme_dir):
        child_dest = dest / child.relative_to(src)
        expected_assets.add(child_dest)
        sync_file_if_changed(child, child_dest, src_stat=child_st)

  prune_stale_files(assets_root, expected_assets)
