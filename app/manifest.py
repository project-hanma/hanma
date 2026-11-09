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
"""Incremental build manifest management for Hanma."""
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional

from app.utils import atomic_write_text


_MANIFEST_TEMPLATE_KEY = "_template_mtime"
_MANIFEST_CONFIG_KEY   = "_config_mtime"
_MANIFEST_NAV_KEY      = "_nav_signature"


def compute_nav_signature(nav_pages: list, posts_out: Optional[Path] = None,
             recent_posts: Optional[list] = None) -> str:
  """Return a stable hash of the current nav page set.

  nav_pages is a list of (out_html, title, md_path, layout, sort_index, link_data) tuples.
  The signature covers the output paths and titles so that any addition,
  removal, or rename forces a full nav rebuild.
  Also includes posts_out so that adding/removing the first post triggers
  a rebuild of all pages to update the nav link.
  Includes recent_posts titles and paths so changes in the blog dropdown
  trigger a rebuild of the nav on all pages.
  """
  entries = []
  for entry in nav_pages:
    page_html, page_title = entry[0], entry[1]
    link_data = entry[5] if len(entry) > 5 else None
    entries.append(f"PAGE:{page_html}:{page_title}")
    if isinstance(link_data, dict) and link_data.get("url"):
      entries.append(f"LINK:{link_data.get('url')}:{link_data.get('target', '')}")

  if posts_out:
    entries.append(f"POSTS:{posts_out}")
  if recent_posts:
    for out_html, title in recent_posts:
      entries.append(f"RECENT:{out_html}:{title}")
  
  # Stable sort for a consistent hash
  entries.sort()
  return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def compute_text_hash(text: str) -> str:
  """Return SHA256 hash of the given text."""
  return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_build_manifest(manifest_path: Path) -> dict:
  """Load JSON manifest mapping str(md_path) -> sha256 hash. Returns {} on miss."""
  if not manifest_path.is_file():
    return {}
  try:
    return json.loads(manifest_path.read_text(encoding="utf-8"))
  except (json.JSONDecodeError, OSError):
    return {}


def save_build_manifest(manifest_path: Path, manifest: dict) -> None:
  """Persist the manifest dict as JSON to manifest_path."""
  try:
    atomic_write_text(
      manifest_path,
      json.dumps(manifest, indent=2) + "\n",
      encoding="utf-8"
    )
  except OSError as exc:
    print(f"  [manifest] warning: could not save {manifest_path}: {exc}", file=sys.stderr)


def page_needs_rebuild(md_path: Path, out_html: Path, manifest: dict,
            template_mtime: float, config_mtime: float = 0.0,
            nav_signature: str = "",
            md_hash: str = "") -> bool:
  """Return True if md_path should be regenerated.

  Triggers rebuild if:
  - out_html does not exist
  - md_path content hash differs from manifest entry
  - template_mtime is newer than the manifest's recorded template_mtime
  - config_mtime is newer than the manifest's recorded config_mtime
  - nav_signature differs from the manifest's recorded nav_signature
  """
  if not out_html.exists():
    return True
  if str(md_path) not in manifest:
    return True

  # Fallback to mtime check if we don't have a hash or if manifest entry looks like a float (legacy)
  entry = manifest[str(md_path)]
  if not md_hash or isinstance(entry, (float, int)):
    try:
      if md_path.stat().st_mtime != entry:
        return True
    except (OSError, TypeError):
      return True
  else:
    # entry must be a string and length must match SHA-256 (64 hex chars)
    if not isinstance(entry, str) or len(entry) != 64:
      return True
    if md_hash != entry:
      return True

  if template_mtime > manifest.get(_MANIFEST_TEMPLATE_KEY, 0.0):
    return True
  if config_mtime > manifest.get(_MANIFEST_CONFIG_KEY, 0.0):
    return True
  if nav_signature and nav_signature != manifest.get(_MANIFEST_NAV_KEY, ""):
    return True
  return False
