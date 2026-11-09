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
"""Markdown to HTML conversion engine for Hanma."""
import html
import os
import sys
try:
  from markupsafe import Markup
except ImportError:
  # Fallback for older Jinja2 or if markupsafe isn't standalone
  try:
    from jinja2 import Markup
  except ImportError:
    Markup = str  # type: ignore
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
  import markdown
  from markdown.extensions.codehilite import CodeHiliteExtension
  from markdown.extensions.fenced_code import FencedCodeExtension
  from markdown.extensions.tables import TableExtension
  from markdown.extensions.toc import TocExtension
  from markdown.extensions.footnotes import FootnoteExtension
  from markdown.extensions.attr_list import AttrListExtension
  from markdown.extensions.def_list import DefListExtension
  from markdown.extensions.abbr import AbbrExtension
  from markdown.extensions.meta import MetaExtension
except ImportError as exc:
  raise RuntimeError(
    "Required package 'markdown' not found. "
    "Install it with:  pip install markdown pygments pyyaml watchdog"
  ) from exc

try:
  import bleach
  from bleach.css_sanitizer import CSSSanitizer as _CSSSanitizerCls
  _BLEACH_AVAILABLE = True
  _CSS_SANITIZER: Optional[Any] = _CSSSanitizerCls()
except ImportError:
  _BLEACH_AVAILABLE = False
  _CSS_SANITIZER = None

from app.nav import get_nav_data
from app.pages import _normalize_tag, _search_json_url, _sitemap_link
from app.parsing import (
  parse_front_matter, extract_title, extract_description,
  parse_date_field, localize_datetime
)
from app.utils import get_root_rel, _THEMES_DIR, atomic_write_text

_ALLOWED_TAGS = [
  'a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 'i', 'li', 'ol',
  'strong', 'ul', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'pre', 'div',
  'span', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'img', 'hr', 'br',
  'del', 'sup', 'sub', 'dl', 'dt', 'dd', 'details', 'summary'
]

_ALLOWED_CLASS_TAGS = {
  'a', 'abbr', 'b', 'blockquote', 'code', 'del', 'details', 'div', 'dl', 'dt', 'dd',
  'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'li', 'ol', 'p', 'pre',
  'span', 'strong', 'sub', 'summary', 'sup', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul'
}

_ALLOWED_ID_TAGS = {
  'a', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'ol', 'p', 'pre', 'span', 'sup', 'table'
}


def _build_allowed_attrs() -> dict[str, list[str]]:
  attrs: dict[str, list[str]] = {
    'a': ['href', 'title', 'rel', 'aria-current'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
  }
  for tag in _ALLOWED_CLASS_TAGS:
    attrs.setdefault(tag, []).append('class')
  for tag in _ALLOWED_ID_TAGS:
    attrs.setdefault(tag, []).append('id')
  return attrs


_ALLOWED_ATTRS = _build_allowed_attrs()
_MD_INSTANCE: Optional[markdown.Markdown] = None


def _get_markdown_instance() -> markdown.Markdown:
  """Return a reusable Markdown instance, resetting state before each conversion."""
  global _MD_INSTANCE  # pylint: disable=global-statement
  if _MD_INSTANCE is None:
    extensions: list[str | markdown.extensions.Extension] = [
      MetaExtension(),
      TocExtension(permalink=True, toc_depth="2-4"),
      FencedCodeExtension(),
      CodeHiliteExtension(css_class="highlight", guess_lang=True, noclasses=False),
      TableExtension(),
      FootnoteExtension(),
      AttrListExtension(),
      DefListExtension(),
      AbbrExtension(),
      "markdown.extensions.nl2br",
      "markdown.extensions.sane_lists",
      "markdown.extensions.smarty",
    ]
    _MD_INSTANCE = markdown.Markdown(extensions=extensions, output_format="html")
  else:
    _MD_INSTANCE.reset()
  return _MD_INSTANCE

def convert_md_to_html(md_path: Path, out_path: Path, site_name: str,
            nav_pages: Optional[list] = None,
            template=None,
            tags_out_dir: Optional[Path] = None,
            base_url: str = "",
            output_root: Optional[Path] = None,
            _layout: str = "page",
            posts_out: Optional[Path] = None,
            posts_label: str = "Blog",
            sanitize: bool = False,
            timezone: Optional[str] = None,
            recent_posts: Optional[list] = None,
            front_matter: Optional[dict] = None,
            body: Optional[str] = None,
            search_enabled: bool = True,
            sidebar_side: str = "right") -> Path:

  """Read a .md file and write the HTML output to out_path.

  nav_pages is a list of (out_html_path, title, md_path, layout, sort_index) tuples for
  every page being generated, used to build the cross-page navigation bar.
  template is a jinja2.Template loaded from the active theme; defaults to
  the built-in default theme when not supplied.
  tags_out_dir is the output directory for tag index pages; when provided,
  tag names in the tag strip become clickable links.
  base_url and output_root are used to compute sitemap_link and
  search_json_url template variables.
  sanitize=True will clean the generated HTML using bleach if available.
  recent_posts is an optional list of (out_html, title) tuples for the nav.
  front_matter and body, if provided, avoids reading/parsing md_path again.
  """
  if template is None:
    from app.theme import _load_theme_impl
    template, _ = _load_theme_impl("default", _THEMES_DIR)
  
  if front_matter is None or body is None:
    md_text = md_path.read_text(encoding="utf-8")
    front_matter, body = parse_front_matter(md_text, source_path=md_path)

  fallback = md_path.stem.replace("-", " ").replace("_", " ").title()
  title = front_matter.get("title") or extract_title(body, fallback)
  description = front_matter.get("description") or extract_description(body)

  # ── Front matter: author / date / tags ───────────────────────────────────
  fm_author = str(front_matter.get("author", "")).strip()
  fm_date_raw = front_matter.get("date")
  fm_tags = front_matter.get("tags", [])

  # Build a human-readable date string from front matter date field
  fm_date_str = parse_date_field(fm_date_raw, tz_name=timezone, source_path=md_path)

  # Meta tags for head
  author_meta = Markup(f'<meta name="author" content="{html.escape(fm_author)}" />\n  ') if fm_author else "" # type: ignore
  if isinstance(fm_tags, list) and fm_tags:
    keywords_meta = Markup(f'<meta name="keywords" content="{html.escape(", ".join(str(t) for t in fm_tags))}" />\n  ')
  else:
    keywords_meta = "" # type: ignore

  fm_refresh_raw = front_matter.get("refresh")
  try:
    if fm_refresh_raw is not None:
      fm_refresh = int(fm_refresh_raw)
      if fm_refresh > 0:
        # Clamp to [1, 86400] (1 second to 24 hours)
        fm_refresh = max(1, min(86400, fm_refresh))
    else:
      fm_refresh = 0
  except (TypeError, ValueError):
    fm_refresh = 0
  refresh_meta = Markup(f'<meta http-equiv="refresh" content="{fm_refresh}" />\n  ') if fm_refresh > 0 else "" # type: ignore

  if sanitize and not _BLEACH_AVAILABLE:
    print("Warning: sanitization requested but 'bleach' is not installed. HTML will NOT be sanitized.", file=sys.stderr)
    print("To fix, run: pip install bleach tinycss2", file=sys.stderr)

  md = _get_markdown_instance()
  content_html = md.convert(body)

  # ── Sanitization ────────────────────────────────────────────────────────
  def _clean_if_needed(html_str: str) -> str:
    if sanitize and _BLEACH_AVAILABLE:
      return bleach.clean(
        html_str,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        css_sanitizer=_CSS_SANITIZER,
      )
    return html_str

  content_html = _clean_if_needed(content_html)

  # Build structured tags for templates
  page_tags = []
  if isinstance(fm_tags, list) and fm_tags:
    for t in fm_tags:
      tag_name = str(t)
      slug = _normalize_tag(tag_name)
      tag_url = None
      if tags_out_dir is not None and slug:
        tag_url = f"tags/{slug}.html"
      page_tags.append({"name": tag_name, "slug": slug, "url": tag_url})

  nav_items = get_nav_data(out_path, nav_pages or [],
               output_root=output_root,
               posts_out=posts_out, posts_label=posts_label,
               recent_posts=recent_posts)

  mtime_naive = datetime.fromtimestamp(md_path.stat().st_mtime)
  mtime = localize_datetime(mtime_naive, tz_name=timezone)
  last_updated = mtime.strftime("%H:%M %m/%d/%Y").replace(" ", " &mdash; ", 1)
  source_rel = md_path.name

  sitemap_link = _clean_if_needed(_sitemap_link(out_path, output_root, base_url))
  
  if search_enabled:
    search_url = _clean_if_needed(_search_json_url(out_path, output_root, base_url))
  else:
    search_url = ""

  # Logic for browser <title>:
  # 1. Homepage (root index.html) shows only site_name
  # 2. If page title matches site_name, show only site_name
  # 3. Otherwise, use "Site Name - Page Title"
  is_root_index = output_root and out_path.resolve() == (output_root / "index.html").resolve()
  titles_match = site_name and title.lower() == site_name.lower()

  root_rel = get_root_rel(output_root, out_path)

  if site_name:
    if is_root_index or titles_match:
      display_title = site_name
    else:
      display_title = f"{site_name} - {title}"
  else:
    display_title = title

  page_html = template.render(
    title=display_title,
    description=description,
    author_meta=author_meta,
    keywords_meta=keywords_meta,
    refresh_meta=refresh_meta,
    site_name=site_name,
    content=content_html,
    nav_items=nav_items,
    root_rel=root_rel,
    page_tags=page_tags,
    base_url=base_url,
    page_url=os.path.relpath(out_path, output_root).replace(os.sep, "/") if output_root else out_path.name,
    author=fm_author,
    page_date=fm_date_str,
    source_file=source_rel,
    last_updated=last_updated,
    sitemap_link=sitemap_link,
    search_json_url=search_url,
    sidebar_side=sidebar_side,
  )

  atomic_write_text(out_path, page_html, encoding="utf-8")
  return out_path
