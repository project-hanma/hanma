import html
import os
import string
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

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
except ImportError:
  print("Error: 'markdown' package not found.")
  print("Install it with:  pip install markdown pygments pyyaml watchdog")
  sys.exit(1)

from hanma_core.highlight import HIGHLIGHT_CSS
from hanma_core.nav import build_nav_html
from hanma_core.pages import _normalize_tag, _search_json_url
from hanma_core.parsing import parse_front_matter, extract_title, extract_description

# Used only for the fallback when no template is passed to convert_md_to_html.
# Does not participate in test monkey-patching of _THEMES_DIR.
_THEMES_DIR = Path(__file__).parent.parent / "themes"


def convert_md_to_html(md_path: Path, out_path: Path, site_name: str,
           nav_pages: Optional[list] = None,
           template: Optional[string.Template] = None,
           tags_out_dir: Optional[Path] = None,
           base_url: str = "",
           output_root: Optional[Path] = None,
           layout: str = "page",
           posts_out: Optional[Path] = None,
           posts_label: str = "Blog") -> Path:
  """Read a .md file and write the HTML output to out_path.

  nav_pages is a list of (out_html_path, title, md_path, layout) tuples for
  every page being generated, used to build the cross-page navigation bar.
  template is a string.Template loaded from the active theme; defaults to
  the built-in default theme when not supplied.
  tags_out_dir is the output directory for tag index pages; when provided,
  tag names in the tag strip become clickable links.
  base_url and output_root are used to compute sitemap_link and
  search_json_url template variables.
  """
  if template is None:
    from hanma_core.theme import _load_theme_impl
    template, _ = _load_theme_impl("default", _THEMES_DIR)
  md_text = md_path.read_text(encoding="utf-8")
  front, body = parse_front_matter(md_text, source_path=md_path)

  fallback = md_path.stem.replace("-", " ").replace("_", " ").title()
  title = front.get("title") or extract_title(body, fallback)
  description = front.get("description") or extract_description(body)

  # ── Front matter: author / date / tags ───────────────────────────────────
  fm_author = str(front.get("author", "")).strip()
  fm_date_raw = front.get("date")
  fm_tags = front.get("tags", [])

  # Build a human-readable date string from front matter date field
  fm_date_str = ""
  if fm_date_raw is not None:
    try:
      if isinstance(fm_date_raw, str):
        fm_date_obj = datetime.strptime(fm_date_raw, "%Y-%m-%d")
      else:  # PyYAML parses YYYY-MM-DD as datetime.date
        fm_date_obj = datetime(fm_date_raw.year, fm_date_raw.month, fm_date_raw.day)
      fm_date_str = fm_date_obj.strftime("%B %d, %Y")
    except (ValueError, AttributeError):
      pass

  # Footer attribution line (author and/or date)
  fm_author_esc = html.escape(fm_author)
  if fm_author and fm_date_str:
    author_line = f"By <em>{fm_author_esc}</em>, {fm_date_str} &nbsp;&middot;&nbsp; "
  elif fm_author:
    author_line = f"By <em>{fm_author_esc}</em> &nbsp;&middot;&nbsp; "
  elif fm_date_str:
    author_line = f"{fm_date_str} &nbsp;&middot;&nbsp; "
  else:
    author_line = ""

  # Meta tags for head
  author_meta = f'<meta name="author" content="{html.escape(fm_author)}" />\n  ' if fm_author else ""
  if isinstance(fm_tags, list) and fm_tags:
    keywords_meta = f'<meta name="keywords" content="{html.escape(", ".join(str(t) for t in fm_tags))}" />\n  '
  else:
    keywords_meta = ""

  fm_refresh_raw = front.get("refresh")
  try:
    fm_refresh = int(fm_refresh_raw)
  except (TypeError, ValueError):
    fm_refresh = 0
  refresh_meta = f'<meta http-equiv="refresh" content="{fm_refresh}" />\n  ' if fm_refresh > 0 else ""

  extensions = [
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

  md = markdown.Markdown(extensions=extensions, output_format="html")
  content_html = md.convert(body)

  # Append tag strip to content if tags are present
  if isinstance(fm_tags, list) and fm_tags:
    tag_items_html = []
    for t in fm_tags:
      tag_text = html.escape(str(t))
      if tags_out_dir is not None:
        slug = _normalize_tag(str(t))
        tag_html_path = tags_out_dir / f"{slug}.html"
        try:
          rel_url = html.escape(
            os.path.relpath(tag_html_path, out_path.parent), quote=True
          )
        except ValueError:
          rel_url = f"tags/{slug}.html"
        tag_items_html.append(
          f'<a class="tag" href="{rel_url}">{tag_text}</a>'
        )
      else:
        tag_items_html.append(f'<span class="tag">{tag_text}</span>')
    content_html += f'\n<div class="page-tags">{"".join(tag_items_html)}</div>'

  nav_html = build_nav_html(out_path, nav_pages or [],
               output_root=output_root,
               posts_out=posts_out, posts_label=posts_label)

  now = datetime.now()
  date_str = now.strftime("%B %d, %Y")

  mtime = datetime.fromtimestamp(md_path.stat().st_mtime)
  last_updated = mtime.strftime("%H:%M %m/%d/%Y").replace(" ", " &mdash; ", 1)
  source_rel = md_path.name

  sitemap_link = '<a href="sitemap.xml">Sitemap</a>' if base_url else ""
  search_url = _search_json_url(out_path, output_root, base_url)

  # Logic for browser <title>:
  # 1. Homepage (root index.html) shows only site_name
  # 2. If page title matches site_name, show only site_name
  # 3. Otherwise, use "Site Name - Page Title"
  is_root_index = output_root and out_path.resolve() == (output_root / "index.html").resolve()
  titles_match = site_name and title.lower() == site_name.lower()

  if site_name:
    if is_root_index or titles_match:
      display_title = site_name
    else:
      display_title = f"{site_name} - {title}"
  else:
    display_title = title

  page_html = template.substitute(
    title=html.escape(display_title),
    description=html.escape(description),
    author_meta=author_meta,
    keywords_meta=keywords_meta,
    refresh_meta=refresh_meta,
    author_line=author_line,
    site_name=html.escape(site_name),
    date_str=date_str,
    content=content_html,
    nav=nav_html,
    source_file=source_rel,
    last_updated=last_updated,
    HIGHLIGHT_CSS=HIGHLIGHT_CSS,
    sitemap_link=sitemap_link,
    search_json_url=search_url,
  )

  out_path.parent.mkdir(parents=True, exist_ok=True)
  out_path.write_text(page_html, encoding="utf-8")
  return out_path
