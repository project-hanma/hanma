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
import shutil
import string
import sys
from pathlib import Path


def _load_theme_impl(name: str, themes_dir: Path) -> tuple:
  """Load template.html from themes_dir/<name>/ and return (Template, theme_dir).

  Exits with a clear error message if the theme or template.html is missing.
  themes_dir is passed explicitly so callers can control the lookup path
  (and tests can monkey-patch it via app._THEMES_DIR).
  """
  theme_dir = (themes_dir / name).resolve()
  if not theme_dir.is_relative_to(themes_dir.resolve()):
    print(f"Error: theme name '{name}' is invalid (path traversal detected)")
    sys.exit(1)
  if not theme_dir.is_dir():
    available = sorted(d.name for d in themes_dir.iterdir() if d.is_dir()) \
      if themes_dir.is_dir() else []
    hint = f"  Available: {', '.join(available)}" if available else \
      "  (no themes/ directory found)"
    print(f"Error: theme '{name}' not found at {theme_dir}\n{hint}")
    sys.exit(1)
  template_path = theme_dir / "template.html"
  if not template_path.is_file():
    print(f"Error: theme '{name}' is missing template.html ({template_path})")
    sys.exit(1)
  return string.Template(template_path.read_text(encoding="utf-8")), theme_dir


def copy_theme_assets(theme_dir: Path, output_root: Path) -> None:
  """Copy all non-template files from theme_dir into output_root.

  Subdirectories are copied recursively. template.html is skipped.
  Does nothing if the theme contains only template.html.
  """
  for src in theme_dir.iterdir():
    if src.name == "template.html":
      continue
    dest = output_root / src.name
    if src.is_file():
      dest.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(src, dest)
    elif src.is_dir():
      if dest.exists():
        shutil.rmtree(dest)
      shutil.copytree(src, dest)
