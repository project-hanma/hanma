import html
import os
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from app.files import POSTS_DIR_NAME


def build_nav_html(current_out_html: Path,
         nav_pages: list[tuple],
         output_root: Optional[Path] = None,
         posts_out: Optional[Path] = None,
         posts_label: str = "Blog") -> str:
  """Build the <ul> content for the sticky nav bar.

  Navigation is structured by folder hierarchy, not by headings:
  - "Home" (root index.md) is always the first item.
  - Root-level non-index pages appear next as top-level items.
  - A subdirectory with an index.md becomes a top-level item (using that index's
   title) with a dropdown listing the other pages in that directory.
  - Pages with layout='post' outside posts/ are treated as root-level items.
  - The posts/ directory is excluded from the page-based nav.
  - If posts_out is provided, a link to it is appended as the last nav item
   (labelled posts_label, default "Blog").
  - Headings are no longer used to generate dropdown menu items.

  nav_pages is a list of (out_html_path, title, md_path, layout) tuples.
  output_root is the output directory root (used to compute relative depth).
  posts_out is the Path to the generated posts.html (or None if no posts exist).
  posts_label is the display label for the posts link.
  """
  if not nav_pages and posts_out is None:
    return ""  # single-file mode: no cross-page nav

  def _rel_url(target: Path) -> str:
    try:
      return os.path.relpath(target, current_out_html.parent)
    except ValueError:
      return target.as_posix()

  def _li(page_html: Path, page_title: str, dropdown_items: list[str] = None) -> str:
    is_current = page_html == current_out_html
    safe_url = html.escape(_rel_url(page_html), quote=True)
    safe_title = html.escape(page_title)
    css = ' class="nav-current"' if is_current else ""
    aria = ' aria-current="page"' if is_current else ""
    if dropdown_items:
      drop_html = "\n    <ul>\n" + "".join(
        f'      <li><a href="{u}">{t}</a></li>\n'
        for u, t in dropdown_items
      ) + "    </ul>"
      return (
        f'  <li{css}>\n'
        f'    <a href="{safe_url}"{aria}>{safe_title}</a>'
        f'{drop_html}\n  </li>'
      )
    return f'  <li{css}>\n    <a href="{safe_url}"{aria}>{safe_title}</a>\n  </li>'

  # Determine the depth of each page relative to output_root so we can
  # classify pages as root-level vs inside a subdirectory.
  def _depth(page_html: Path) -> int:
    if output_root is None:
      return 0
    try:
      return len(page_html.relative_to(output_root).parts) - 1
    except ValueError:
      return 0

  # Group pages by their parent directory (relative to output_root).
  # Structure: {dir_key: {"index": entry|None, "children": [entry, ...]}}
  # dir_key = "" for root, else the relative dir string.
  # entry = (out_html_path, title, md_path, layout)
  groups: dict = OrderedDict()

  for entry in nav_pages:
    page_html, page_title, md_path, layout = entry
    depth = _depth(page_html)

    # Determine the group key (the directory relative to output_root)
    if output_root is not None:
      try:
        rel_parts = page_html.relative_to(output_root).parts
      except ValueError:
        rel_parts = (page_html.name,)
    else:
      rel_parts = (page_html.name,)

    if depth == 0:
      dir_key = ""
    else:
      dir_key = rel_parts[0]  # top-level subdirectory name

    # Skip the posts/ directory — it's represented by the posts listing page
    if dir_key == POSTS_DIR_NAME:
      continue

    if dir_key not in groups:
      groups[dir_key] = {"index": None, "children": []}

    is_dir_index = depth > 0 and page_html.stem.lower() == "index"
    if is_dir_index:
      groups[dir_key]["index"] = entry
    else:
      groups[dir_key]["children"].append(entry)

  # Separate root-level home (index.html) from other root pages so we can
  # guarantee Home is always the first nav item.
  home_item: Optional[str] = None
  other_items: list[str] = []

  for dir_key, group in groups.items():
    if dir_key == "":
      # Root-level pages: home first, rest in discovery order
      for entry in group["children"]:
        page_html, page_title, md_path, layout = entry
        li = _li(page_html, page_title)
        if page_html.stem.lower() == "index" and (
          output_root is None or page_html.parent == output_root
        ):
          home_item = li
        else:
          other_items.append(li)
    else:
      idx = group["index"]
      children = group["children"]
      if idx is not None:
        # Directory with an index: top-level item links to index using folder name, dropdown = children
        idx_html, _, _, _ = idx
        idx_title = dir_key.replace("-", " ").replace("_", " ").title()
        dropdown = []
        for child_html, child_title, _, _ in children:
          safe_u = html.escape(_rel_url(child_html), quote=True)
          safe_t = html.escape(child_title)
          is_cur = child_html == current_out_html
          cur_cls = ' style="font-weight:600;color:var(--accent)"' if is_cur else ""
          dropdown.append((safe_u, f'<span{cur_cls}>{safe_t}</span>'))
        other_items.append(_li(idx_html, idx_title, dropdown if dropdown else None))
      else:
        # No index — use the folder name as a non-linking dropdown header
        if children:
          folder_label = html.escape(dir_key.replace("-", " ").replace("_", " ").title())
          dropdown = []
          for child_html, child_title, _, _ in children:
            safe_u = html.escape(_rel_url(child_html), quote=True)
            safe_t = html.escape(child_title)
            is_cur = child_html == current_out_html
            cur_cls = ' style="font-weight:600;color:var(--accent)"' if is_cur else ""
            dropdown.append((safe_u, f'<span{cur_cls}>{safe_t}</span>'))
          is_current_group = any(ch == current_out_html for ch, _, _, _ in children)
          css = ' class="nav-current"' if is_current_group else ""
          drop_html = "\n    <ul>\n" + "".join(
            f'      <li><a href="{u}">{t}</a></li>\n'
            for u, t in dropdown
          ) + "    </ul>"
          other_items.append(
            f'  <li{css}>\n'
            f'    <span class="nav-folder">{folder_label}</span>'
            f'{drop_html}\n  </li>'
          )

  items = ([home_item] if home_item else []) + other_items

  # Append posts listing link last (if posts exist)
  if posts_out is not None:
    is_cur = posts_out == current_out_html
    safe_url = html.escape(_rel_url(posts_out), quote=True)
    safe_label = html.escape(posts_label)
    css = ' class="nav-current"' if is_cur else ""
    aria = ' aria-current="page"' if is_cur else ""
    items.append(f'  <li{css}>\n    <a href="{safe_url}"{aria}>{safe_label}</a>\n  </li>')

  if not items:
    return ""

  return "\n<ul>\n" + "\n".join(items) + "\n</ul>\n"
