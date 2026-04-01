import html
import os
import re
import string
from datetime import datetime
from pathlib import Path
from typing import Optional

from hanma_core.highlight import HIGHLIGHT_CSS
from hanma_core.nav import build_nav_html


def _normalize_tag(tag: str) -> str:
    """Produce a filesystem-safe slug from a tag name."""
    return re.sub(r"[^\w-]", "-", str(tag).lower()).strip("-")


def _search_json_url(out_path: Path, output_root: Optional[Path], base_url: str) -> str:
    """Return the URL to search.json as seen from out_path.

    Uses an absolute URL when base_url is set, otherwise computes a relative
    path from out_path back to output_root/search.json.
    """
    if base_url:
        return base_url.rstrip("/") + "/search.json"
    if output_root is None:
        return "search.json"
    try:
        depth = len(out_path.relative_to(output_root).parts) - 1
    except ValueError:
        depth = 0
    return ("../" * depth) + "search.json"


def _make_generated_page(content_html: str, title: str, description: str,
                          out_path: Path, site_name: str,
                          nav_pages: list[tuple],
                          template: string.Template,
                          sitemap_link: str = "",
                          search_json_url: str = "search.json",
                          output_root: Optional[Path] = None,
                          posts_out: Optional[Path] = None,
                          posts_label: str = "Blog") -> Path:
    """Render a generated (non-markdown) page using the active theme template."""
    nav_html = build_nav_html(out_path, nav_pages, output_root=output_root,
                              posts_out=posts_out, posts_label=posts_label)
    now = datetime.now()
    titles_match = site_name and title.lower() == site_name.lower()
    if site_name and not titles_match:
        display_title = f"{site_name} - {title}"
    else:
        display_title = site_name or title

    page_html = template.substitute(
        title=html.escape(display_title),
        description=html.escape(description),
        author_meta="",
        keywords_meta="",
        refresh_meta="",
        author_line="",
        site_name=html.escape(site_name),
        date_str=now.strftime("%B %d, %Y"),
        content=content_html,
        nav=nav_html,
        source_file="(generated)",
        last_updated=now.strftime("%H:%M %m/%d/%Y").replace(" ", " &mdash; ", 1),
        HIGHLIGHT_CSS=HIGHLIGHT_CSS,
        sitemap_link=sitemap_link,
        search_json_url=search_json_url,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page_html, encoding="utf-8")
    return out_path


def build_tag_index_html(tag: str, pages: list[tuple], out_path: Path,
                          site_name: str, nav_pages: list[tuple],
                          template: string.Template,
                          base_url: str = "",
                          output_root: Optional[Path] = None,
                          posts_out: Optional[Path] = None,
                          posts_label: str = "Blog") -> Path:
    """Generate a tag index page listing all pages tagged with tag.

    pages is a list of (out_html_path, title, date_str) tuples, sorted by date.
    """
    safe_tag = html.escape(tag)
    items = []
    for page_html_path, page_title, date_str in pages:
        try:
            rel_url = html.escape(
                os.path.relpath(page_html_path, out_path.parent), quote=True
            )
        except ValueError:
            rel_url = page_html_path.as_posix()
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
        sitemap_link='<a href="../sitemap.xml">Sitemap</a>' if base_url else "",
        search_json_url=_search_json_url(out_path, output_root, base_url),
        output_root=output_root,
        posts_out=posts_out, posts_label=posts_label,
    )


def build_posts_listing_html(dated_pages: list[tuple], out_path: Path,
                              site_name: str, nav_pages: list[tuple],
                              template: string.Template,
                              base_url: str = "",
                              output_root: Optional[Path] = None,
                              posts_label: str = "Blog",
                              posts_out: Optional[Path] = None) -> Path:
    """Generate posts.html listing all layout='post' pages, newest first.

    dated_pages is a list of (out_html_path, title, mtime_dt, description) tuples.
    mtime_dt is the file's modification time; used for both sorting and display.
    """
    # Sort newest-first by mtime.
    sorted_pages = sorted(dated_pages, key=lambda t: t[2], reverse=True)

    items = []
    for page_html_path, page_title, mtime_dt, description in sorted_pages:
        try:
            rel_url = html.escape(
                os.path.relpath(page_html_path, out_path.parent), quote=True
            )
        except ValueError:
            rel_url = page_html_path.as_posix()
        safe_title = html.escape(page_title)
        date_str = html.escape(mtime_dt.strftime("%-m/%-d/%Y @ %I:%M %p"))
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
    # Compute depth-aware sitemap link (posts/index.html is one level deep)
    if base_url:
        sitemap_link = '<a href="../sitemap.xml">Sitemap</a>'
    else:
        sitemap_link = ""
    return _make_generated_page(
        content_html, posts_label, f"A listing of all {posts_label.lower()} posts.",
        out_path, site_name, nav_pages, template,
        sitemap_link=sitemap_link,
        search_json_url=_search_json_url(out_path, output_root, base_url),
        output_root=output_root,
        posts_out=posts_out, posts_label=posts_label,
    )
