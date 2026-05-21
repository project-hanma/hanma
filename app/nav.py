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
"""Navigation generation and management for Hanma."""
import os
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from app.files import POSTS_DIR_NAME


def get_nav_data(current_out_html: Path,
               nav_pages: list[tuple],
               output_root: Optional[Path] = None,
               posts_out: Optional[Path] = None,
               posts_label: str = "Blog",
               recent_posts: Optional[list[tuple]] = None) -> list[dict]:
  """Return a structured list of navigation items."""
  if not nav_pages and posts_out is None:
    return []

  def _rel_url(target: Path) -> str:
    try:
      return os.path.relpath(target, current_out_html.parent).replace(os.sep, "/")
    except ValueError:
      return target.as_posix()

  groups = _group_nav_pages(nav_pages, output_root)
  home_item, pending = _process_groups(groups, current_out_html, output_root, _rel_url)
  
  # Final assembly
  def _si_key(item_tuple) -> tuple:
    si = item_tuple[0]
    return (1 if si is None else 0, si if si is not None else 0)

  final_nav = [item for _, item in sorted(pending, key=_si_key)]
  
  if posts_out:
    final_nav.append(_create_posts_nav(posts_out, posts_label, current_out_html, recent_posts, _rel_url))

  return [home_item] + final_nav if home_item else final_nav


def _group_nav_pages(nav_pages: list[tuple], output_root: Optional[Path]) -> dict:
  """Group pages by their top-level directory."""
  groups: dict = OrderedDict()
  for entry in nav_pages:
    page_html = entry[0]
    depth = _get_depth(page_html, output_root)
    rel_parts = _get_rel_parts(page_html, output_root)
    dir_key = "" if depth == 0 else rel_parts[0]
    if dir_key == POSTS_DIR_NAME:
      continue
    if dir_key not in groups:
      groups[dir_key] = {"index": None, "children": []}
    if depth > 0 and page_html.stem.lower() == "index":
      groups[dir_key]["index"] = entry
    else:
      groups[dir_key]["children"].append(entry)
  return groups


def _process_groups(groups: dict, current_out_html: Path, output_root: Optional[Path], rel_url_fn) -> tuple:
  """Process grouped pages into navigation items."""
  home_item = None
  pending = []
  for dir_key, group in groups.items():
    if dir_key == "":
      for entry in group["children"]:
        item = _create_item(entry, current_out_html, rel_url_fn)
        page_html = entry[0]
        if page_html.stem.lower() == "index" and (output_root is None or page_html.parent == output_root):
          home_item = item
        else:
          pending.append((entry[4], item))
    else:
      folder_item = _create_folder_item(dir_key, group, current_out_html, rel_url_fn)
      if folder_item:
        pending.append((group["index"][4] if group["index"] else None, folder_item))
  return home_item, pending


def _create_item(entry: tuple, current_out_html: Path, rel_url_fn) -> dict:
  """Create a single page navigation item."""
  page_html, page_title = entry[0], entry[1]
  link_data = entry[5] if len(entry) > 5 else None
  item = {"title": page_title, "is_current": page_html == current_out_html, "is_folder": False}
  _apply_link_logic(item, link_data, rel_url_fn(page_html))
  return item


def _create_folder_item(dir_key: str, group: dict, current_out_html: Path, rel_url_fn) -> Optional[dict]:
  """Create a folder (dropdown) navigation item."""
  idx = group["index"]
  if idx is None:
    # Handle folder without index.md (header-only)
    if not group["children"]:
      return None
    folder_title = dir_key.replace("-", " ").replace("_", " ").title()
    item = {"title": folder_title, "url": None, "is_current": False, "is_folder": True, "children": []}
    group_si = next((e[4] for e in group["children"] if e[4] is not None), None)
    # We'll use the first child's sort index as a proxy
    for child_entry in sorted(group["children"], key=lambda e: (1 if e[4] is None else 0, e[4] if e[4] is not None else 0)):
      item["children"].append(_create_item(child_entry, current_out_html, rel_url_fn))
      if child_entry[0] == current_out_html:
        item["is_current"] = True
    # Attach a mock sort_index for the group
    group["index"] = (None, None, None, None, group_si)
    return item

  folder_title = dir_key.replace("-", " ").replace("_", " ").title()
  item = {"title": folder_title, "is_current": idx[0] == current_out_html, "is_folder": True, "children": []}
  _apply_link_logic(item, idx[5] if len(idx) > 5 else None, rel_url_fn(idx[0]))
  
  def _si_key(e):
    return (1 if e[4] is None else 0, e[4] if e[4] is not None else 0)

  for child_entry in sorted(group["children"], key=_si_key):
    item["children"].append(_create_item(child_entry, current_out_html, rel_url_fn))
  return item


def _create_posts_nav(posts_out: Path, posts_label: str, current_out_html: Path, recent_posts: Optional[list], rel_url_fn) -> dict:
  """Create the 'Blog' (posts) navigation item with recent posts as children."""
  item = {"title": posts_label, "is_current": posts_out == current_out_html, "is_folder": bool(recent_posts), "children": []}
  item["url"] = rel_url_fn(posts_out)
  if recent_posts:
    for out_path, title in recent_posts:
      item["children"].append({"title": title, "url": rel_url_fn(out_path), "is_current": out_path == current_out_html, "is_folder": False})
    item["children"].append({
      "title": "More posts...",
      "url": rel_url_fn(posts_out),
      "is_current": False,
      "is_folder": False,
      "is_more_link": True
    })
  return item


def _get_depth(page_html: Path, output_root: Optional[Path]) -> int:
  if output_root is None:
    return 0
  try:
    return len(page_html.relative_to(output_root).parts) - 1
  except ValueError:
    return 0


def _get_rel_parts(page_html: Path, output_root: Optional[Path]) -> tuple:
  if output_root is not None:
    try:
      return page_html.relative_to(output_root).parts
    except ValueError:
      pass
  return (page_html.name,)


def _apply_link_logic(item: dict, link_data, default_url: str):
  """Apply external link overrides to a nav item."""
  item["url"] = default_url
  if not isinstance(link_data, dict):
    return

  override_url = link_data.get("url")
  if not override_url:
    return

  item["url"] = override_url
  target = str(link_data.get("target", "")).lower().strip()

  target_map = {
    "tab": "_blank",
    "window": "_blank",
    "same": "_self"
  }

  if target:
    item["target"] = target_map.get(target, target)

