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
import html
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
  """Return a structured list of navigation items.
  
  Each item is a dict:
    title: str
    url: str (optional)
    is_current: bool
    is_folder: bool
    children: list[dict] (optional)
  """
  if not nav_pages and posts_out is None:
    return []

  def _rel_url(target: Path) -> str:
    try:
      return os.path.relpath(target, current_out_html.parent)
    except ValueError:
      return target.as_posix()

  def _depth(page_html: Path) -> int:
    if output_root is None:
      return 0
    try:
      return len(page_html.relative_to(output_root).parts) - 1
    except ValueError:
      return 0

  groups: dict = OrderedDict()
  for entry in nav_pages:
    page_html, page_title, md_path, layout, sort_index = entry
    depth = _depth(page_html)

    if output_root is not None:
      try:
        rel_parts = page_html.relative_to(output_root).parts
      except ValueError:
        rel_parts = (page_html.name,)
    else:
      rel_parts = (page_html.name,)

    dir_key = "" if depth == 0 else rel_parts[0]
    if dir_key == POSTS_DIR_NAME:
      continue

    if dir_key not in groups:
      groups[dir_key] = {"index": None, "children": []}

    if depth > 0 and page_html.stem.lower() == "index":
      groups[dir_key]["index"] = entry
    else:
      groups[dir_key]["children"].append(entry)

  home_item: Optional[dict] = None
  
  def _si_key(si) -> tuple:
    return (1 if si is None else 0, si if si is not None else 0)

  pending: list[tuple] = []  # (sort_index, item_dict)

  for dir_key, group in groups.items():
    if dir_key == "":
      for entry in group["children"]:
        page_html, page_title, md_path, layout, sort_index = entry
        is_current = page_html == current_out_html
        item = {
          "title": page_title,
          "url": _rel_url(page_html),
          "is_current": is_current,
          "is_folder": False
        }
        if page_html.stem.lower() == "index" and (
          output_root is None or page_html.parent == output_root
        ):
          home_item = item
        else:
          pending.append((sort_index, item))
    else:
      idx = group["index"]
      children = group["children"]
      if idx is not None:
        idx_html, _, _, _, idx_si = idx
        idx_title = dir_key.replace("-", " ").replace("_", " ").title()
        item = {
          "title": idx_title,
          "url": _rel_url(idx_html),
          "is_current": idx_html == current_out_html,
          "is_folder": True,
          "children": []
        }
        for child_html, child_title, _, _, _ in sorted(children, key=lambda e: _si_key(e[4])):
          item["children"].append({
            "title": child_title,
            "url": _rel_url(child_html),
            "is_current": child_html == current_out_html,
            "is_folder": False
          })
        pending.append((idx_si, item))
      else:
        if children:
          group_si = next((e[4] for e in children if e[4] is not None), None)
          item = {
            "title": dir_key.replace("-", " ").replace("_", " ").title(),
            "url": None,
            "is_current": any(ch == current_out_html for ch, *_ in children),
            "is_folder": True,
            "children": []
          }
          for child_html, child_title, _, _, _ in sorted(children, key=lambda e: _si_key(e[4])):
            item["children"].append({
              "title": child_title,
              "url": _rel_url(child_html),
              "is_current": child_html == current_out_html,
              "is_folder": False
            })
          pending.append((group_si, item))

  pending.sort(key=lambda t: _si_key(t[0]))
  items = ([home_item] if home_item else []) + [t[1] for t in pending]

  if posts_out is not None:
    item = {
      "title": posts_label,
      "url": _rel_url(posts_out),
      "is_current": posts_out == current_out_html,
      "is_folder": bool(recent_posts),
      "children": []
    }
    if recent_posts:
      for post_html, post_title in recent_posts:
        item["children"].append({
          "title": post_title,
          "url": _rel_url(post_html),
          "is_current": post_html == current_out_html,
          "is_folder": False
        })
      item["children"].append({
        "title": "More posts...",
        "url": _rel_url(posts_out),
        "is_current": False,
        "is_folder": False,
        "is_more_link": True
      })
    items.append(item)

  return items


def build_nav_html(current_out_html: Path,
         nav_pages: list[tuple],
         output_root: Optional[Path] = None,
         posts_out: Optional[Path] = None,
         posts_label: str = "Blog",
         recent_posts: Optional[list[tuple]] = None) -> str:
  """Build the <ul> content for the sticky nav bar. (Legacy string-builder)"""
  items = get_nav_data(current_out_html, nav_pages, output_root, posts_out, posts_label, recent_posts)
  if not items:
    return ""

  def _render_item(item: dict) -> str:
    css = ' class="nav-current"' if item["is_current"] else ""
    aria = ' aria-current="page"' if item["is_current"] else ""
    title = html.escape(item["title"])
    url = html.escape(item["url"], quote=True) if item["url"] else None

    if item.get("children"):
      drop_html = "\n    <ul>\n"
      for child in item["children"]:
        child_url = html.escape(child["url"], quote=True)
        child_title = html.escape(child["title"])
        if child.get("is_more_link"):
          drop_html += f'      <li><span class="nav-more-posts-sep"></span><a href="{child_url}"><span class="nav-more-posts">{child_title}</span></a></li>\n'
        else:
          cur_style = ' style="font-weight:600;color:var(--accent)"' if child["is_current"] else ""
          drop_html += f'      <li><a href="{child_url}"><span{cur_style}>{child_title}</span></a></li>\n'
      drop_html += "    </ul>"
      
      if url:
        return f'  <li{css}>\n    <a href="{url}"{aria}>{title}</a>{drop_html}\n  </li>'
      else:
        return f'  <li{css}>\n    <span class="nav-folder">{title}</span>{drop_html}\n  </li>'
    
    return f'  <li{css}>\n    <a href="{url}"{aria}>{title}</a>\n  </li>'

  html_parts = ["\n<ul>"]
  for item in items:
    html_parts.append(_render_item(item))
  html_parts.append("</ul>\n")
  return "\n".join(html_parts)
