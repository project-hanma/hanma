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
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from app.files import POSTS_DIR_NAME

_CACHE_LOCK = threading.Lock()
_GROUP_CACHE: dict[tuple, dict] = {}


def _fast_rel_url(target: Path, current_dir: Path,
                  target_parts: Optional[tuple[str, ...]],
                  current_dir_parts: Optional[tuple[str, ...]]) -> str:
  """Compute relative URL from current_dir to target without repeated posixpath.relpath."""
  if current_dir_parts is not None and target_parts is not None:
    limit = min(len(current_dir_parts), len(target_parts) - 1)
    common = 0
    while common < limit and current_dir_parts[common] == target_parts[common]:
      common += 1
    ups = ("..",) * (len(current_dir_parts) - common)
    return "/".join(ups + target_parts[common:])
  try:
    return os.path.relpath(target, current_dir).replace(os.sep, "/")
  except ValueError:
    return target.as_posix()


def get_nav_data(current_out_html: Path,
               nav_pages: list[tuple],
               output_root: Optional[Path] = None,
               posts_out: Optional[Path] = None,
               posts_label: str = "Blog",
               recent_posts: Optional[list[tuple]] = None) -> list[dict]:
  """Return a structured list of navigation items."""
  if not nav_pages and posts_out is None:
    return []

  cache_entry = _get_nav_cache_entry(nav_pages, output_root)
  current_dir = current_out_html.parent
  posts_key = tuple((p, t) for p, t in recent_posts) if recent_posts else ()
  base_key = (current_dir, posts_out, posts_label, posts_key)

  with _CACHE_LOCK:
    base_items = cache_entry["base_cache"].get(base_key)

  if base_items is None:
    current_dir_parts: Optional[tuple[str, ...]] = None
    if output_root is not None:
      try:
        current_dir_parts = current_dir.relative_to(output_root).parts
      except ValueError:
        current_dir_parts = None

    rel_parts_map: dict[Path, Optional[tuple[str, ...]]] = cache_entry["rel_parts"]

    def _rel_url(target: Path) -> str:
      t_parts = rel_parts_map.get(target)
      if t_parts is None and output_root is not None:
        try:
          t_parts = target.relative_to(output_root).parts
        except ValueError:
          t_parts = None
      return _fast_rel_url(target, current_dir, t_parts, current_dir_parts)

    built_base = _build_base_nav_items(
      cache_entry["ordered_specs"], posts_out, posts_label, recent_posts, _rel_url
    )
    with _CACHE_LOCK:
      cache_entry["base_cache"][base_key] = built_base
    base_items = built_base

  return _materialize_nav_items(base_items, current_out_html)


def _si_sort_key(entry: tuple) -> tuple:
  si = entry[4]
  return (1 if si is None else 0, si if si is not None else 0)


def _get_nav_cache_entry(nav_pages: list[tuple], output_root: Optional[Path]) -> dict:
  """Return cached grouped/sorted nav specs for nav_pages, thread-safely."""
  cache_key = (id(nav_pages), len(nav_pages), output_root)
  with _CACHE_LOCK:
    cached = _GROUP_CACHE.get(cache_key)
    if cached is not None and cached.get("_ref") is nav_pages:
      return cached

  groups: dict = OrderedDict()
  rel_parts_map: dict[Path, Optional[tuple[str, ...]]] = {}
  for entry in nav_pages:
    page_html = entry[0]
    if output_root is not None:
      try:
        rel_parts = page_html.relative_to(output_root).parts
      except ValueError:
        rel_parts = None
    else:
      rel_parts = None
    rel_parts_map[page_html] = rel_parts
    depth = (len(rel_parts) - 1) if rel_parts is not None else 0
    dir_key = "" if depth == 0 else rel_parts[0]  # type: ignore[index]
    if dir_key == POSTS_DIR_NAME:
      continue
    if dir_key not in groups:
      groups[dir_key] = {"index": None, "children": [], "sort_index": None}
    if depth > 0 and page_html.stem.lower() == "index":
      groups[dir_key]["index"] = entry
    else:
      groups[dir_key]["children"].append(entry)

  home_entry = None
  pending_specs: list[tuple[Optional[int], str, object]] = []
  for dir_key, grp in groups.items():
    if dir_key == "":
      for entry in grp["children"]:
        page_html = entry[0]
        if page_html.stem.lower() == "index" and (output_root is None or page_html.parent == output_root):
          home_entry = entry
        else:
          pending_specs.append((entry[4], "page", entry))
    else:
      grp["children"].sort(key=_si_sort_key)
      if grp["index"] is not None:
        grp["sort_index"] = grp["index"][4]
      else:
        grp["sort_index"] = next((e[4] for e in grp["children"] if e[4] is not None), None)
      if grp["index"] is not None or grp["children"]:
        pending_specs.append((grp["sort_index"], "folder", (dir_key, grp)))

  pending_specs.sort(key=lambda t: (1 if t[0] is None else 0, t[0] if t[0] is not None else 0))

  new_entry = {
    "_ref": nav_pages,
    "rel_parts": rel_parts_map,
    "ordered_specs": (home_entry, pending_specs),
    "base_cache": {},
  }
  with _CACHE_LOCK:
    _GROUP_CACHE.clear()
    _GROUP_CACHE[cache_key] = new_entry
  return new_entry


def _build_base_nav_items(ordered_specs: tuple,
                          posts_out: Optional[Path],
                          posts_label: str,
                          recent_posts: Optional[list[tuple]],
                          rel_url_fn) -> list[tuple]:
  """Build per-directory cached nav specs with precomputed relative URLs."""
  home_entry, pending_specs = ordered_specs
  base_items: list[tuple] = []

  if home_entry is not None:
    base_items.append(_make_item_spec(home_entry, rel_url_fn))

  for _, kind, payload in pending_specs:
    if kind == "page":
      base_items.append(_make_item_spec(payload, rel_url_fn))
    else:
      dir_key, group = payload
      base_items.append(_make_folder_spec(dir_key, group, rel_url_fn))

  if posts_out:
    base_items.append(_make_posts_spec(posts_out, posts_label, recent_posts, rel_url_fn))

  return base_items


def _materialize_nav_items(base_items: list[tuple], current_out_html: Path) -> list[dict]:
  """Clone cached base nav specs and set is_current for current_out_html."""
  result: list[dict] = []
  for base_dict, target_path, is_header_folder, child_specs in base_items:
    item = base_dict.copy()
    if child_specs is not None:
      children: list[dict] = []
      any_child_current = False
      for child_base, child_path in child_specs:
        child = child_base.copy()
        is_curr = (child_path == current_out_html) if child_path is not None else False
        child["is_current"] = is_curr
        if is_curr:
          any_child_current = True
        children.append(child)
      item["children"] = children
      item["is_current"] = any_child_current if is_header_folder else (target_path == current_out_html)
    else:
      item["is_current"] = (target_path == current_out_html)
    result.append(item)
  return result


def _make_item_spec(entry: tuple, rel_url_fn) -> tuple:
  """Create a cached base spec for a single page navigation item."""
  page_html, page_title = entry[0], entry[1]
  link_data = entry[5] if len(entry) > 5 else None
  item: dict = {"title": page_title, "is_folder": False}
  _apply_link_logic(item, link_data, rel_url_fn(page_html))
  return (item, page_html, False, None)


def _make_folder_spec(dir_key: str, group: dict, rel_url_fn) -> tuple:
  """Create a cached base spec for a folder (dropdown) navigation item."""
  idx = group["index"]
  folder_title = dir_key.replace("-", " ").replace("_", " ").title()
  child_specs = [
    (_make_item_spec(child_entry, rel_url_fn)[0], child_entry[0])
    for child_entry in group["children"]
  ]
  if idx is None:
    item: dict = {"title": folder_title, "url": None, "is_folder": True}
    return (item, None, True, child_specs)

  item = {"title": folder_title, "is_folder": True}
  _apply_link_logic(item, idx[5] if len(idx) > 5 else None, rel_url_fn(idx[0]))
  return (item, idx[0], False, child_specs)


def _make_posts_spec(posts_out: Path, posts_label: str,
                     recent_posts: Optional[list], rel_url_fn) -> tuple:
  """Create a cached base spec for the 'Blog' (posts) navigation item."""
  item: dict = {
    "title": posts_label,
    "is_folder": bool(recent_posts),
    "url": rel_url_fn(posts_out),
  }
  child_specs: list[tuple[dict, Optional[Path]]] = []
  if recent_posts:
    for out_path, title in recent_posts:
      child_specs.append((
        {"title": title, "url": rel_url_fn(out_path), "is_folder": False},
        out_path,
      ))
    child_specs.append((
      {
        "title": "More posts...",
        "url": rel_url_fn(posts_out),
        "is_folder": False,
        "is_more_link": True,
      },
      None,
    ))
  return (item, posts_out, False, child_specs)


def _is_safe_url(url: str) -> bool:
  """Return True if url uses a safe scheme (http, https, mailto) or is a relative path."""
  cleaned = url.strip()
  if not cleaned:
    return False
  if any(ord(c) < 0x20 or ord(c) == 0x7f for c in cleaned):
    return False
  if cleaned.startswith(("//", "\\")):
    return False
  parsed = urlsplit(cleaned)
  if parsed.scheme:
    scheme = parsed.scheme.lower()
    if scheme in {"http", "https"}:
      return bool(parsed.netloc)
    if scheme == "mailto":
      return bool(parsed.path)
    return False
  if parsed.netloc:
    return False
  return True


def _apply_link_logic(item: dict, link_data, default_url: str):
  """Apply external link overrides to a nav item."""
  item["url"] = default_url
  if not isinstance(link_data, dict):
    return

  override_url = link_data.get("url")
  if not override_url or not _is_safe_url(str(override_url)):
    return

  item["url"] = str(override_url).strip()
  target = str(link_data.get("target", "")).lower().strip()

  target_map = {
    "tab": "_blank",
    "window": "_blank",
    "same": "_self",
    "_blank": "_blank",
    "_self": "_self",
  }

  if target in target_map:
    item["target"] = target_map[target]

