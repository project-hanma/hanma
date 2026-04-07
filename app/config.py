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
import sys
from pathlib import Path

try:
  import yaml
except ImportError as exc:
  raise RuntimeError(
    "Required package 'pyyaml' not found. Install it with:  pip install pyyaml"
  ) from exc


def load_site_config(config_path: Path) -> dict:
  """Load hanma.yml (or hanma.yaml) from config_path. Returns {} if absent or invalid.

  Recognized fields: name, base_url, output, theme, serve, port, watch, incremental.
  """
  if not config_path.is_file():
    return {}
  try:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
  except yaml.YAMLError as exc:
    print(f"Warning: could not parse {config_path}: {exc}", file=sys.stderr)
    return {}
  if not isinstance(raw, dict):
    return {}
  allowed = {"name", "base_url", "output", "theme", "serve", "port", "host", "watch", "incremental",
       "posts_label", "sanitize"}
  return {k: v for k, v in raw.items() if k in allowed}
