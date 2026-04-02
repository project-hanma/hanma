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
import hashlib
import json
import sys
from pathlib import Path


_MANIFEST_TEMPLATE_KEY = "_template_mtime"
_MANIFEST_CONFIG_KEY   = "_config_mtime"
_MANIFEST_NAV_KEY      = "_nav_signature"


def compute_nav_signature(nav_pages: list) -> str:
  """Return a stable hash of the current nav page set.

  nav_pages is a list of (out_html, title, md_path, layout) tuples.
  The signature covers the output paths and titles so that any addition,
  removal, or rename forces a full nav rebuild.
  """
  entries = sorted(str(out_html) for out_html, *_ in nav_pages)
  return hashlib.md5("\n".join(entries).encode()).hexdigest()


def load_build_manifest(manifest_path: Path) -> dict:
  """Load JSON manifest mapping str(md_path) -> mtime float. Returns {} on miss."""
  if not manifest_path.is_file():
    return {}
  try:
    return json.loads(manifest_path.read_text(encoding="utf-8"))
  except (json.JSONDecodeError, OSError):
    return {}


def save_build_manifest(manifest_path: Path, manifest: dict) -> None:
  """Persist the manifest dict as JSON to manifest_path."""
  try:
    manifest_path.write_text(
      json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
  except OSError as exc:
    print(f"  [manifest] warning: could not save {manifest_path}: {exc}", file=sys.stderr)


def page_needs_rebuild(md_path: Path, out_html: Path, manifest: dict,
            template_mtime: float, config_mtime: float = 0.0,
            nav_signature: str = "") -> bool:
  """Return True if md_path should be regenerated.

  Triggers rebuild if:
  - out_html does not exist
  - md_path mtime differs from manifest entry
  - template_mtime is newer than the manifest's recorded template_mtime
  - config_mtime is newer than the manifest's recorded config_mtime
  - nav_signature differs from the manifest's recorded nav_signature
  """
  if not out_html.exists():
    return True
  if str(md_path) not in manifest:
    return True
  try:
    if md_path.stat().st_mtime != manifest[str(md_path)]:
      return True
  except OSError:
    return True
  if template_mtime > manifest.get(_MANIFEST_TEMPLATE_KEY, 0.0):
    return True
  if config_mtime > manifest.get(_MANIFEST_CONFIG_KEY, 0.0):
    return True
  if nav_signature and nav_signature != manifest.get(_MANIFEST_NAV_KEY, ""):
    return True
  return False
