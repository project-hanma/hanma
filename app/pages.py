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
import re
import string
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.nav import get_nav_data


def _normalize_tag(tag: str) -> str:
  """Produce a filesystem-safe slug from a tag name."""
  return re.sub(r"[^\w-]", "-", str(tag).lower()).strip("-")


def _rel_url(target: Path, base: Path) -> str:
  """Return a relative URL string from base directory to target file."""
  try:
    return os.path.relpath(target, base).replace(os.sep, "/")
  except ValueError:
    return target.as_posix()


def _sitemap_link(out_path: Path, output_root: Optional[Path], base_url: str) -> str:
  """Return an HTML anchor to sitemap.xml as seen from out_path, or '' if no base_url."""
  if not base_url:
    return ""
  if output_root is None:
    return '<a href="sitemap.xml">Sitemap</a>'
  rel = _rel_url(output_root / "sitemap.xml", out_path.parent)
  return f'<a href="{rel}">Sitemap</a>'


def _search_json_url(out_path: Path, output_root: Optional[Path], base_url: str) -> str:
  """Return the URL to search.json as seen from out_path.

  Uses an absolute URL when base_url is set, otherwise computes a relative
  path from out_path back to output_root/search.json.
  """
  if base_url:
    return base_url.rstrip("/") + "/search.json"
  if output_root is None:
    return "search.json"
  return _rel_url(output_root / "search.json", out_path.parent)


def _make_generated_page(content_html: str, title: str, description: str,
             out_path: Path, site_name: str,
             nav_pages: list[tuple],
             template,
             sitemap_link: str = "",
             search_json_url: str = "search.json",
             output_root: Optional[Path] = None,
             posts_out: Optional[Path] = None,
             posts_label: str = "Blog",
             recent_posts: Optional[list] = None) -> Path:
  """Render a generated (non-markdown) page using the active theme template."""
  nav_items = get_nav_data(out_path, nav_pages, output_root=output_root,
               posts_out=posts_out, posts_label=posts_label,
               recent_posts=recent_posts)
  now = datetime.now()
  titles_match = site_name and title.lower() == site_name.lower()
  if site_name and not titles_match:
    display_title = f"{site_name} - {title}"
  else:
    display_title = site_name or title

  page_html = template.render(
    title=display_title,
    description=description,
    author_meta="",
    keywords_meta="",
    refresh_meta="",
    author_line="",
    site_name=site_name,
    date_str=now.strftime("%B %d, %Y"),
    content=content_html,
    nav_items=nav_items,
    source_file="(generated)",
    last_updated=now.strftime("%H:%M %m/%d/%Y").replace(" ", " &mdash; ", 1),
    sitemap_link=sitemap_link,
    search_json_url=search_json_url,
  )
  out_path.parent.mkdir(parents=True, exist_ok=True)
  out_path.write_text(page_html, encoding="utf-8")
  return out_path


def build_tag_index_html(tag: str, pages: list[tuple], out_path: Path,
             site_name: str, nav_pages: list[tuple],
             template,
             base_url: str = "",
             output_root: Optional[Path] = None,
             posts_out: Optional[Path] = None,
             posts_label: str = "Blog",
             recent_posts: Optional[list] = None) -> Path:
  """Generate a tag index page listing all pages tagged with tag.

  pages is a list of (out_html_path, title, date_str) tuples, sorted by date.
  """
  safe_tag = html.escape(tag)
  items = []
  for page_html_path, page_title, date_str in pages:
    rel_url = html.escape(_rel_url(page_html_path, out_path.parent), quote=True)
    safe_title = html.escape(page_title)
    date_span = f' <span class="post-date">{html.escape(date_str)}</span>' if date_str else ""
    items.append(f'  <li><a href="{rel_url}">{safe_title}</a>{date_span}</li>')

  items_html = "\n".join(items) if items else "  <li><em>No pages found.</em></li>"
  content_html = (
    f'<h1>Pages tagged &#8220;<em>{safe_tag}</em>&#8221;</h1>\n'
    f'<ul class="tag-index">\n{items_html}\n</ul>'
  )
  return _make_generated_page(
    content_html, f'Tag: {tag}', f'Pages tagged {tag}',
    out_path, site_name, nav_pages, template,
    sitemap_link=_sitemap_link(out_path, output_root, base_url),
    search_json_url=_search_json_url(out_path, output_root, base_url),
    output_root=output_root,
    posts_out=posts_out, posts_label=posts_label,
    recent_posts=recent_posts,
  )


def build_posts_listing_html(dated_pages: list[tuple], out_path: Path,
               site_name: str, nav_pages: list[tuple],
               template,
               base_url: str = "",
               output_root: Optional[Path] = None,
               posts_label: str = "Blog",
               posts_out: Optional[Path] = None,
               recent_posts: Optional[list] = None) -> Path:
  """Generate posts.html listing all layout='post' pages, newest first.

  dated_pages is a list of (out_html_path, title, date_dt, description) tuples.
  date_dt is used for both sorting and display.
  """
  # Sort newest-first by date.
  sorted_pages = sorted(dated_pages, key=lambda t: t[2], reverse=True)

  items = []
  for page_html_path, page_title, date_dt, description in sorted_pages:
    rel_url = html.escape(_rel_url(page_html_path, out_path.parent), quote=True)
    safe_title = html.escape(page_title)

    # Use a simpler format if it's exactly midnight (likely from YYYY-MM-DD front matter).
    if date_dt.hour == 0 and date_dt.minute == 0 and date_dt.second == 0:
      fmt = "%-m/%-d/%Y"
    else:
      fmt = "%-m/%-d/%Y @ %I:%M %p"

    date_str = html.escape(date_dt.strftime(fmt))
    date_span = f' <span class="post-date">{date_str}</span>'
    desc_html = f'\n    <p class="post-desc">{html.escape(description)}</p>' if description else ""
    items.append(
      f'  <li>\n'
      f'    <a href="{rel_url}">{safe_title}</a>'
      f'{date_span}'
      f'{desc_html}\n  </li>'
    )

  items_html = "\n".join(items) if items else "  <li><em>No posts found.</em></li>"
  safe_label = html.escape(posts_label)
  content_html = f'<h1>{safe_label}</h1>\n<ul class="post-list">\n{items_html}\n</ul>'
  return _make_generated_page(
    content_html, posts_label, f"A listing of all {posts_label.lower()} posts.",
    out_path, site_name, nav_pages, template,
    sitemap_link=_sitemap_link(out_path, output_root, base_url),
    search_json_url=_search_json_url(out_path, output_root, base_url),
    output_root=output_root,
    posts_out=posts_out, posts_label=posts_label,
    recent_posts=recent_posts,
  )
