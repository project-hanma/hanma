#!/usr/bin/env python3
"""
hanma.py — Static Site Generator
Converts Markdown files to HTML in-place, recursively.

Version: 0.5.0

Usage:
    python hanma.py [directory]

If no directory is given, ./site/ is used (falling back to the current directory).
All .md files found in the directory tree are converted to .html
files written to ./output/ by default.

Dependencies:
    pip install markdown pygments pyyaml watchdog
"""

__version__ = "0.5.0"

import html
import json
import os
import sys
import re
import argparse
import shutil
import string
import time
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
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

try:
    import yaml
except ImportError:
    print("Error: 'pyyaml' package not found.")
    print("Install it with:  pip install pyyaml")
    sys.exit(1)

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler as _WatchdogHandler
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False
    _WatchdogHandler = object  # fallback base class


# ─────────────────────────────────────────────────────────────────────────────
# SYNTAX HIGHLIGHT CSS  (generated once at import time from Pygments)
# ─────────────────────────────────────────────────────────────────────────────

def _build_highlight_css() -> str:
    """Return scoped Pygments CSS for light and dark themes."""
    try:
        from pygments.formatters import HtmlFormatter
    except ImportError:
        return ""  # Pygments not installed — highlighting still works, just unstyled

    import re as _re

    def scoped(style: str, scope: str) -> str:
        raw = HtmlFormatter(style=style, cssclass="highlight").get_style_defs(".highlight")
        # Drop the bare `pre { ... }` rule Pygments adds — our template already styles pre
        raw = _re.sub(r"^pre\s*\{[^}]*\}\s*", "", raw, flags=_re.MULTILINE)
        out = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.endswith("{"):
                parts = [s.strip() for s in line.rstrip("{").split(",")]
                out.append(", ".join(f"{scope} {p}" for p in parts) + " {")
            else:
                out.append(line)
        return "\n".join(out)

    light   = scoped("friendly", ":root")
    dark    = scoped("monokai",  '[data-theme="dark"]')
    os_dark = scoped("monokai",  ':root:not([data-theme="light"])')

    return f"""
    /* Syntax highlighting — light (Pygments \'friendly\') */
    {light}

    /* Syntax highlighting — dark (Pygments \'monokai\') */
    {dark}

    @media (prefers-color-scheme: dark) {{
      {os_dark}
    }}"""


HIGHLIGHT_CSS = _build_highlight_css()


# ─────────────────────────────────────────────────────────────────────────────
# FRONT MATTER
# ─────────────────────────────────────────────────────────────────────────────

def parse_front_matter(md_text: str, source_path: Optional[Path] = None) -> tuple:
    """Strip and parse a YAML front matter block delimited by '---' lines.

    Returns (metadata_dict, body_text) where body_text has the front matter
    removed.  If no front matter is present returns ({}, md_text) unchanged.

    Supported fields:
      title       str   — overrides auto-extracted H1
      description str   — overrides auto-extracted first paragraph
      author      str   — displayed in the page footer
      date        str   — ISO 8601 (YYYY-MM-DD), displayed in the footer
      tags        list  — rendered as a tag strip below the content
      draft       bool  — if true, the page is skipped during generation
      refresh     int   — auto-refresh interval in seconds (omit or 0 to disable)
    """
    lines = md_text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, md_text
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() in ("---", "..."):
            yaml_block = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1:])
            try:
                meta = yaml.safe_load(yaml_block) or {}
            except yaml.YAMLError as exc:
                loc = f" in {source_path}" if source_path else ""
                print(f"Warning: malformed YAML front matter{loc} — metadata ignored", file=sys.stderr)
                print(f"  Hint: if a value contains a colon, wrap it in quotes — e.g. title: \"My Title: Subtitle\"", file=sys.stderr)
                print(f"  YAML error: {exc}", file=sys.stderr)
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
            return meta, body
    return {}, md_text


# ─────────────────────────────────────────────────────────────────────────────
# SITE CONFIG FILE (hanma.yml)
# ─────────────────────────────────────────────────────────────────────────────

def load_site_config(config_path: Path) -> dict:
    """Load hanma.yml (or hanma.yaml) from config_path. Returns {} if absent or invalid.

    Recognized fields: name, base_url, output, theme, serve, port, watch, incremental.
    """
    if not config_path.is_file():
        return {}
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"Warning: could not parse {config_path}: {exc}", file=sys.stderr)
        return {}
    if not isinstance(raw, dict):
        return {}
    allowed = {"name", "base_url", "output", "theme", "serve", "port", "watch", "incremental",
               "posts_label"}
    return {k: v for k, v in raw.items() if k in allowed}


# ─────────────────────────────────────────────────────────────────────────────
# THEME LOADER
# ─────────────────────────────────────────────────────────────────────────────

_THEMES_DIR = Path(__file__).parent / "themes"


def load_theme(name: str) -> tuple:
    """Load template.html from themes/<name>/ and return (Template, theme_dir).

    Exits with a clear error message if the theme or template.html is missing.
    """
    theme_dir = (_THEMES_DIR / name).resolve()
    if not theme_dir.is_relative_to(_THEMES_DIR.resolve()):
        print(f"Error: theme name '{name}' is invalid (path traversal detected)")
        sys.exit(1)
    if not theme_dir.is_dir():
        available = sorted(d.name for d in _THEMES_DIR.iterdir() if d.is_dir()) \
            if _THEMES_DIR.is_dir() else []
        hint = f"  Available: {', '.join(available)}" if available else \
            "  (no themes/ directory found)"
        print(f"Error: theme '{name}' not found at {theme_dir}\n{hint}")
        sys.exit(1)
    template_path = theme_dir / "template.html"
    if not template_path.is_file():
        print(f"Error: theme '{name}' is missing template.html ({template_path})")
        sys.exit(1)
    return string.Template(template_path.read_text(encoding="utf-8")), theme_dir


def copy_theme_assets(theme_dir: Path, output_root: Path) -> None:
    """Copy all non-template files from theme_dir into output_root.

    Subdirectories are copied recursively. template.html is skipped.
    Does nothing if the theme contains only template.html.
    """
    for src in theme_dir.iterdir():
        if src.name == "template.html":
            continue
        dest = output_root / src.name
        if src.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        elif src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)


# ─────────────────────────────────────────────────────────────────────────────
# MARKDOWN → HTML
# ─────────────────────────────────────────────────────────────────────────────

def extract_title(md_text: str, fallback: str) -> str:
    """Return the first H1 heading found, or the filename as fallback."""
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def extract_description(md_text: str, max_chars: int = 160) -> str:
    """Return the first non-heading paragraph as a plain-text description."""
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("```"):
            # Strip inline markdown
            plain = re.sub(r"[*_`\[\]()!]", "", stripped)
            return plain[:max_chars]
    return ""


def build_nav_html(current_out_html: Path, toc_inner: str,
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
    from collections import OrderedDict
    groups: dict = OrderedDict()

    POSTS_DIR_NAME = "posts"

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
                # Directory with an index: top-level item = index, dropdown = children
                idx_html, idx_title, _, _ = idx
                dropdown = []
                for child_html, child_title, _, _ in children:
                    safe_u = html.escape(_rel_url(child_html), quote=True)
                    safe_t = html.escape(child_title)
                    is_cur = child_html == current_out_html
                    cur_cls = ' style="font-weight:600;color:var(--accent)"' if is_cur else ""
                    dropdown.append((safe_u, f'<span{cur_cls}>{safe_t}</span>'))
                other_items.append(_li(idx_html, idx_title, dropdown if dropdown else None))
            else:
                # No index — render each child as its own top-level item
                for entry in children:
                    page_html, page_title, md_path, layout = entry
                    other_items.append(_li(page_html, page_title))

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


def collect_page_info(md_path: Path) -> tuple:
    """Return (title, description, front_matter) for a Markdown file without full conversion."""
    md_text = md_path.read_text(encoding="utf-8")
    front, body = parse_front_matter(md_text, source_path=md_path)
    fallback = md_path.stem.replace("-", " ").replace("_", " ").title()
    title = front.get("title") or extract_title(body, fallback)
    description = front.get("description") or extract_description(body)
    return title, description, front


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

    nav_pages is a list of (out_html_path, title) tuples for every page being
    generated, used to build the cross-page navigation bar.
    template is a string.Template loaded from the active theme; defaults to
    the built-in default theme when not supplied.
    tags_out_dir is the output directory for tag index pages; when provided,
    tag names in the tag strip become clickable links.
    base_url and output_root are used to compute sitemap_link and
    search_json_url template variables.
    """
    if template is None:
        template, _ = load_theme("default")
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

    # Extract TOC inner HTML (strip the outer <div class="toc"> wrapper)
    toc_html = getattr(md, "toc", "")
    empty_toc = ('<div class="toc">\n<ul>\n</ul>\n</div>', "")
    if toc_html.strip() in empty_toc:
        toc_inner = ""
    else:
        toc_inner = re.sub(r'</?div[^>]*>', '', toc_html).strip()

    nav_html = build_nav_html(out_path, toc_inner, nav_pages or [],
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


# ─────────────────────────────────────────────────────────────────────────────
# STALE OUTPUT CLEANUP
# ─────────────────────────────────────────────────────────────────────────────

def clean_stale_html(output_dir: Path, expected_html: set[Path]) -> list[Path]:
    """Remove .html files in output_dir that have no corresponding source page.

    expected_html is the set of output paths that should exist after generation.
    Returns the list of paths that were removed.
    """
    removed = []
    for html_file in sorted(output_dir.rglob("*.html")):
        if html_file not in expected_html:
            try:
                html_file.unlink()
                removed.append(html_file)
                # Remove empty parent directories up to output_dir
                parent = html_file.parent
                while parent != output_dir:
                    try:
                        parent.rmdir()  # only removes if empty
                        parent = parent.parent
                    except OSError:
                        break
            except OSError as exc:
                print(f"  [clean] warning: could not remove {html_file}: {exc}", file=sys.stderr)
    return removed


# ─────────────────────────────────────────────────────────────────────────────
# DIRECTORY WALKER
# ─────────────────────────────────────────────────────────────────────────────

def find_markdown_files(root: Path) -> list[Path]:
    """Recursively find all .md and .markdown files under root.

    Skips any path whose components include a dotfile/dotdir (e.g. .venv).
    """
    IGNORE_NAMES = {"README.md", "README.markdown", "readme.md", "readme.markdown"}

    def has_dotpart(p: Path) -> bool:
        return any(part.startswith(".") for part in p.relative_to(root).parts)

    return sorted(
        p for p in root.rglob("*")
        if p.suffix.lower() in {".md", ".markdown"}
        and p.is_file()
        and not has_dotpart(p)
        and p.name not in IGNORE_NAMES
    )


# ─────────────────────────────────────────────────────────────────────────────
# STATIC ASSET PASSTHROUGH
# ─────────────────────────────────────────────────────────────────────────────

def copy_static_assets(source_root: Path, output_root: Path) -> None:
    """Copy <source_root>/static/ to <output_root>/static/ unchanged.

    Does nothing if no static/ directory exists in source_root.
    """
    static_src = source_root / "static"
    if not static_src.is_dir():
        return
    static_dest = output_root / "static"
    if static_dest.exists():
        shutil.rmtree(static_dest)
    shutil.copytree(static_src, static_dest)
    count = sum(1 for _ in static_dest.rglob("*") if _.is_file())
    print(f"  [static] copied {count} file(s) from static/")


# ─────────────────────────────────────────────────────────────────────────────
# GENERATED PAGES (tag indexes, post listing)
# ─────────────────────────────────────────────────────────────────────────────

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
    nav_html = build_nav_html(out_path, "", nav_pages, output_root=output_root,
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


# ─────────────────────────────────────────────────────────────────────────────
# SIDECAR FILES (sitemap.xml, search.json)
# ─────────────────────────────────────────────────────────────────────────────

def build_sitemap_xml(pages: list[tuple], output_root: Path, base_url: str) -> Optional[Path]:
    """Write sitemap.xml to output_root. Returns None if base_url is empty.

    pages is a list of (out_html_path, lastmod_date_str) tuples.
    base_url must be an absolute URL, e.g. https://example.com
    """
    if not base_url:
        return None
    base = base_url.rstrip("/")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page_path, lastmod in pages:
        try:
            rel = page_path.relative_to(output_root).as_posix()
        except ValueError:
            rel = page_path.name
        loc = html.escape(f"{base}/{rel}")
        lastmod_esc = html.escape(lastmod)
        lines.append(f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod_esc}</lastmod>\n  </url>")
    lines.append("</urlset>")
    out = output_root / "sitemap.xml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def build_search_json(entries: list[dict], output_root: Path,
                      base_url: str = "") -> Path:
    """Write search.json to output_root.

    Each entry: {title, description, url, tags}
    url is relative from output_root when base_url is empty,
    or an absolute URL when base_url is provided.
    """
    base = base_url.rstrip("/") if base_url else ""
    normalized = []
    for entry in entries:
        url = entry.get("url", "")
        if base and url:
            url = f"{base}/{url}"
        normalized.append({
            "title": entry.get("title", ""),
            "description": entry.get("description", ""),
            "url": url,
            "tags": entry.get("tags", []),
        })
    out = output_root / "search.json"
    out.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# BUILD MANIFEST (incremental builds)
# ─────────────────────────────────────────────────────────────────────────────

_MANIFEST_TEMPLATE_KEY = "_template_mtime"
_MANIFEST_CONFIG_KEY   = "_config_mtime"


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
                        template_mtime: float, config_mtime: float = 0.0) -> bool:
    """Return True if md_path should be regenerated.

    Triggers rebuild if:
    - out_html does not exist
    - md_path mtime differs from manifest entry
    - template_mtime is newer than the manifest's recorded template_mtime
    - config_mtime is newer than the manifest's recorded config_mtime
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
    return False


# ─────────────────────────────────────────────────────────────────────────────
# CORE BUILD LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def _run_build(root: Path, output_dir: Path, site_name: str,
               template: string.Template, theme_dir: Path,
               base_url: str = "", incremental: bool = False,
               manifest_path: Optional[Path] = None,
               dry_run: bool = False,
               posts_label: str = "Blog",
               config_path: Optional[Path] = None) -> tuple[int, int, int]:
    """Run a full site build. Returns (ok, errors, skipped)."""

    files = find_markdown_files(root)
    if not files:
        print(f"No Markdown files found under: {root}")
        return 0, 0, 0

    print(f"Found {len(files)} Markdown file(s)\n")

    # ── Load build manifest for incremental builds ────────────────────────
    manifest: dict = {}
    template_mtime = 0.0
    config_mtime = 0.0
    if incremental and manifest_path is not None:
        manifest = load_build_manifest(manifest_path)
        template_html = theme_dir / "template.html"
        try:
            template_mtime = template_html.stat().st_mtime
        except OSError:
            pass
        if config_path is not None:
            try:
                config_mtime = config_path.stat().st_mtime
            except OSError:
                pass

    # ── Pass 1: collect titles, output paths, and derived data ───────────
    all_files: list[tuple] = []  # (md_path, out_html, title, layout)
    drafts = 0
    tags_map: dict[str, list] = {}      # tag -> [(out_html, title, date_str)]
    dated_pages: list[tuple] = []       # [(out_html, title, date_obj, description)]
    search_entries: list[dict] = []

    POSTS_DIR_NAME = "posts"

    for md_path in files:
        title, description, front = collect_page_info(md_path)
        if front.get("draft") is True:
            print(f"  [draft] skipping {md_path.name}")
            drafts += 1
            continue
        rel = md_path.relative_to(root)
        # Only the root-level index.md is titled "Home"; subdir index.md keeps its own title.
        if md_path.stem.lower() == "index" and len(rel.parts) == 1:
            title = "Home"
        out_html = output_dir / rel.with_suffix(".html")

        # Determine layout: front matter overrides directory-based default.
        # Files under posts/ default to 'post'; everything else defaults to 'page'.
        rel_parts = rel.parts
        in_posts_dir = len(rel_parts) > 1 and rel_parts[0] == POSTS_DIR_NAME
        default_layout = "post" if in_posts_dir else "page"
        layout = str(front.get("layout", default_layout)).strip().lower()

        all_files.append((md_path, out_html, title, layout))

        # Collect tags
        fm_tags = front.get("tags", [])
        if isinstance(fm_tags, list):
            for tag in fm_tags:
                tag_str = str(tag)
                # Parse date for sorted tag listing
                date_str = ""
                fm_date_raw = front.get("date")
                if fm_date_raw is not None:
                    try:
                        if isinstance(fm_date_raw, str):
                            d = datetime.strptime(fm_date_raw, "%Y-%m-%d")
                        else:
                            d = datetime(fm_date_raw.year, fm_date_raw.month, fm_date_raw.day)
                        date_str = d.strftime("%B %d, %Y")
                    except (ValueError, AttributeError):
                        pass
                tags_map.setdefault(tag_str, []).append((out_html, title, date_str))

        # Collect pages for posts listing: all layout='post' pages go here.
        # dated_pages entries: (out_html, title, mtime_dt, description)
        # mtime_dt is the file's modification time, used for both sorting and display.
        if layout == "post":
            try:
                mtime_dt = datetime.fromtimestamp(md_path.stat().st_mtime)
            except OSError:
                mtime_dt = datetime.min
            dated_pages.append((out_html, title, mtime_dt, description))

        # Collect search entry
        try:
            url_rel = out_html.relative_to(output_dir).as_posix()
        except ValueError:
            url_rel = out_html.name
        search_entries.append({
            "title": title,
            "description": description,
            "url": url_rel,
            "tags": [str(t) for t in fm_tags] if isinstance(fm_tags, list) else [],
        })

    # index.html always listed first, everything else in discovery order
    all_files.sort(key=lambda t: (0 if t[0].stem.lower() == "index" else 1, t[0].name))

    # Single-file invocations get no cross-page nav (nothing to link to).
    # nav_pages entries: (out_html, title, md_path, layout)
    # Posts with layout='post' from OUTSIDE the posts/ dir are included in nav.
    # Pages inside posts/ are excluded from nav (they appear in posts listing).
    def _in_posts_dir(md_path: Path) -> bool:
        try:
            rel_parts = md_path.relative_to(root).parts
            return len(rel_parts) > 1 and rel_parts[0] == POSTS_DIR_NAME
        except ValueError:
            return False

    nav_pages = (
        [
            (out_html, title, md_path, layout)
            for md_path, out_html, title, layout in all_files
            if not _in_posts_dir(md_path)
        ]
        if len(all_files) > 1 else []
    )

    # Compute tags output directory
    tags_out_dir = output_dir / "tags"

    # ── Compute expected HTML (includes generated pages) ─────────────────
    expected_html: set[Path] = {out_html for _, out_html, _, _ in all_files}

    # Tag index pages
    tag_out_paths: dict[str, Path] = {}
    for tag in tags_map:
        slug = _normalize_tag(tag)
        tag_out_path = tags_out_dir / f"{slug}.html"
        tag_out_paths[tag] = tag_out_path
        expected_html.add(tag_out_path)

    # Posts listing page — written to output/posts/index.html so that the
    # /posts/ URL serves the listing directly (no directory listing fallback).
    # Skipped if posts/index.md already exists as a source file.
    posts_out_path = output_dir / "posts" / "index.html"
    posts_collision = any(out_html == posts_out_path for _, out_html, _, _ in all_files)
    has_posts_listing = bool(dated_pages) and not posts_collision
    if has_posts_listing:
        expected_html.add(posts_out_path)

    # nav_posts_out: path passed to build_nav_html so every page links to the listing.
    # None when there are no posts or posts/index.md exists as a source file.
    nav_posts_out = posts_out_path if has_posts_listing else None

    # Search index and sitemap are not HTML so not added to expected_html

    # ── Copy theme assets to output root ─────────────────────────────────
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        copy_theme_assets(theme_dir, output_dir)

    # ── Copy static assets ────────────────────────────────────────────────
    if not dry_run:
        copy_static_assets(root, output_dir)

    # ── Remove stale HTML files with no corresponding source ──────────────
    if not dry_run and output_dir.is_dir():
        stale = clean_stale_html(output_dir, expected_html)
        for path in stale:
            try:
                rel = path.relative_to(output_dir)
            except ValueError:
                rel = path
            print(f"  [clean] removed stale {rel}")

    ok = 0
    errors = 0
    skipped = 0

    # ── Pass 2: generate HTML with full nav ───────────────────────────────
    for md_path, out_html, _title, layout in all_files:
        try:
            rel = md_path.relative_to(root)
        except ValueError:
            rel = md_path

        if dry_run:
            try:
                out_rel = out_html.relative_to(Path.cwd())
            except ValueError:
                out_rel = out_html
            print(f"  [dry-run] {rel}  →  {out_rel}")
            continue

        # Incremental skip check
        if incremental and not page_needs_rebuild(md_path, out_html, manifest, template_mtime, config_mtime):
            try:
                out_rel = out_html.relative_to(output_dir)
            except ValueError:
                out_rel = out_html
            print(f"  [skip]  {rel}  (unchanged)")
            skipped += 1
            ok += 1
            continue

        try:
            out = convert_md_to_html(
                md_path, out_html, site_name,
                nav_pages=nav_pages, template=template,
                tags_out_dir=tags_out_dir,
                base_url=base_url, output_root=output_dir,
                layout=layout,
                posts_out=nav_posts_out, posts_label=posts_label,
            )
            print(f"  ✓  {rel}  →  {out}")
            ok += 1
            if incremental and manifest_path is not None:
                try:
                    manifest[str(md_path)] = md_path.stat().st_mtime
                except OSError:
                    pass
        except Exception as exc:
            print(f"  ✗  {rel}  →  ERROR: {exc}")
            errors += 1

    if dry_run:
        # Show what generated pages would be created
        if tags_map:
            for tag, slug_path in tag_out_paths.items():
                try:
                    out_rel = slug_path.relative_to(Path.cwd())
                except ValueError:
                    out_rel = slug_path
                print(f"  [dry-run] (tag index) tags/{_normalize_tag(tag)}.html  →  {out_rel}")
        if has_posts_listing:
            try:
                pr = posts_out_path.relative_to(Path.cwd())
            except ValueError:
                pr = posts_out_path
            print(f"  [dry-run] (posts listing) posts/index.html  →  {pr}")
        return ok, errors, skipped

    # ── Generate tag index pages ──────────────────────────────────────────
    for tag, tag_pages in tags_map.items():
        tag_out = tag_out_paths[tag]
        # Sort tag pages: dated entries first (by date desc), then undated alphabetically
        def _sort_key(entry):
            _, _, date_str = entry
            if date_str:
                try:
                    return (0, datetime.strptime(date_str, "%B %d, %Y"))
                except ValueError:
                    pass
            return (1, datetime.min)
        tag_pages_sorted = sorted(tag_pages, key=_sort_key, reverse=True)
        try:
            build_tag_index_html(tag, tag_pages_sorted, tag_out, site_name, nav_pages, template,
                             base_url=base_url, output_root=output_dir,
                             posts_out=nav_posts_out, posts_label=posts_label)
            print(f"  [tag]   tags/{_normalize_tag(tag)}.html  ({len(tag_pages)} page(s))")
        except Exception as exc:
            print(f"  [tag]   ERROR generating tags/{_normalize_tag(tag)}.html: {exc}")
            errors += 1

    # ── Generate posts listing page ───────────────────────────────────────
    if has_posts_listing:
        try:
            build_posts_listing_html(dated_pages, posts_out_path, site_name, nav_pages, template,
                                     base_url=base_url, output_root=output_dir,
                                     posts_label=posts_label, posts_out=nav_posts_out)
            print(f"  [posts] posts/index.html  ({len(dated_pages)} post(s))")
        except Exception as exc:
            print(f"  [posts] ERROR generating posts/index.html: {exc}")
            errors += 1
    elif posts_collision:
        print("  [posts] skipped: posts/index.md exists as source file")

    # ── Generate sitemap.xml ──────────────────────────────────────────────
    if base_url:
        sitemap_pages = []
        for _, out_html, _, _ in all_files:
            try:
                mtime = out_html.stat().st_mtime
                lastmod = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            except OSError:
                lastmod = datetime.now().strftime("%Y-%m-%d")
            sitemap_pages.append((out_html, lastmod))
        sitemap_path = build_sitemap_xml(sitemap_pages, output_dir, base_url)
        if sitemap_path:
            print(f"  [sitemap] sitemap.xml  ({len(sitemap_pages)} URL(s))")

    # ── Generate search.json ──────────────────────────────────────────────
    search_path = build_search_json(search_entries, output_dir, base_url)
    print(f"  [search] search.json  ({len(search_entries)} entry/entries)")

    # ── Save build manifest ───────────────────────────────────────────────
    if incremental and manifest_path is not None:
        manifest[_MANIFEST_TEMPLATE_KEY] = template_mtime
        manifest[_MANIFEST_CONFIG_KEY] = config_mtime
        save_build_manifest(manifest_path, manifest)

    if not dry_run:
        draft_note = f", {drafts} draft(s) skipped" if drafts else ""
        skip_note = f", {skipped} skipped (unchanged)" if skipped else ""
        print(f"\nDone.  {ok} converted{skip_note}{draft_note}, {errors} errors.")

    return ok, errors, skipped


# ─────────────────────────────────────────────────────────────────────────────
# WATCH MODE (watchdog-based)
# ─────────────────────────────────────────────────────────────────────────────

class _HanmaEventHandler(_WatchdogHandler):
    """Watchdog event handler: triggers a debounced rebuild on any relevant change."""

    _RELEVANT_SUFFIXES = {".md", ".markdown", ".yaml", ".css", ".js"}

    def __init__(self, rebuild_fn, root: Path, theme_dir: Path, output_dir: Optional[Path] = None) -> None:
        super().__init__()
        self._rebuild = rebuild_fn
        self._root = root
        self._theme_dir = theme_dir
        self._output_dir = output_dir
        self._lock = threading.Lock()
        self._debounce_timer: Optional[threading.Timer] = None

    def _is_relevant(self, path: str) -> bool:
        p = Path(path)
        if self._output_dir and p.is_relative_to(self._output_dir):
            return False
        return p.suffix.lower() in self._RELEVANT_SUFFIXES

    def _schedule_rebuild(self) -> None:
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(0.3, self._rebuild)
            self._debounce_timer.start()

    _TRIGGER_TYPES = {"created", "deleted", "modified", "moved"}

    def on_any_event(self, event) -> None:
        if getattr(event, "is_directory", False):
            return
        if getattr(event, "event_type", None) not in self._TRIGGER_TYPES:
            return
        src = getattr(event, "src_path", "")
        if self._is_relevant(src):
            self._schedule_rebuild()


def _watch_polling(root: Path, output_dir: Path, site_name: str,
                   template: string.Template, theme_dir: Path,
                   base_url: str = "", poll_interval: float = 1.0,
                   posts_label: str = "Blog",
                   config_path: Optional[Path] = None) -> None:
    """Fallback polling-based watch (used when watchdog is not available)."""
    print(f"Watching {root} for changes (polling, Ctrl+C to stop)...\n")

    def get_mtimes(file_list: list) -> dict:
        mtimes = {}
        for p in file_list:
            try:
                mtimes[p] = p.stat().st_mtime
            except OSError:
                pass
        return mtimes

    files = find_markdown_files(root)
    last_mtimes = get_mtimes(files)

    try:
        while True:
            time.sleep(poll_interval)
            current_files = find_markdown_files(root)
            current_mtimes = get_mtimes(current_files)
            deleted = set(files) - set(current_files)
            changed = [p for p in current_files
                       if current_mtimes.get(p) != last_mtimes.get(p)]
            if changed or deleted:
                print(f"\n  [watch] change detected, rebuilding...")
                _run_build(root, output_dir, site_name, template, theme_dir,
                           base_url=base_url, posts_label=posts_label,
                           config_path=config_path)
            last_mtimes = current_mtimes
            files = current_files
    except KeyboardInterrupt:
        print("\nWatch stopped.")


def watch_and_rebuild(root: Path, output_dir: Path, site_name: str,
                      template: string.Template, theme_dir: Path,
                      base_url: str = "",
                      poll_interval: float = 1.0,
                      posts_label: str = "Blog",
                      config_path: Optional[Path] = None) -> None:
    """Watch source files and regenerate on changes.

    Uses watchdog (inotify/FSEvents/kqueue) when available; falls back to
    polling when watchdog is not installed.
    """
    if not _WATCHDOG_AVAILABLE:
        _watch_polling(root, output_dir, site_name, template, theme_dir,
                       base_url=base_url, poll_interval=poll_interval,
                       posts_label=posts_label, config_path=config_path)
        return

    def rebuild():
        print(f"\n  [watch] change detected, rebuilding...")
        try:
            _run_build(root, output_dir, site_name, template, theme_dir,
                       base_url=base_url, posts_label=posts_label,
                       config_path=config_path)
        except Exception as exc:
            print(f"  [watch] build error: {exc}")

    handler = _HanmaEventHandler(rebuild, root, theme_dir, output_dir=output_dir)
    observer = Observer()
    observer.schedule(handler, str(root), recursive=True)
    if theme_dir != root and not theme_dir.is_relative_to(root):
        observer.schedule(handler, str(theme_dir), recursive=True)
    observer.start()
    print(f"Watching {root} for changes (Ctrl+C to stop)...\n")
    try:
        while observer.is_alive():
            observer.join(timeout=1.0)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    print("\nWatch stopped.")


# ─────────────────────────────────────────────────────────────────────────────
# INIT SCAFFOLD
# ─────────────────────────────────────────────────────────────────────────────

_SCAFFOLD_FILES: dict[str, str] = {
    "index.md": """\
---
title: Home
description: Welcome to my site.
---

# Welcome

This is the home page of your new site, built with **hanma.py**.

Edit the Markdown files in `site/` and run `./hanma.py` to regenerate.
""",
    "about.md": """\
---
title: About
description: A little about this site.
---

# About

Tell readers who you are and what this site is about.
""",
    "posts/hello-world.md": """\
---
title: Hello, World
description: My first post.
date: {today}
tags:
  - general
---

# Hello, World

Welcome to your first post!  Add more files to `site/posts/` and they will
appear in the auto-generated **Posts** listing.
""",
}


def init_scaffold(site_dir: Path, force: bool = False) -> None:
    """Create sample content in site_dir.

    Aborts (with a helpful message) if site_dir is non-empty and force is
    False.  With force=True, the entire site_dir is wiped before writing.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # Check whether the directory has any real contents (.gitkeep is ignored)
    real_contents = [
        p for p in site_dir.iterdir() if p.name != ".gitkeep"
    ] if site_dir.is_dir() else []
    if real_contents:
        if not force:
            print(f"Error: '{site_dir}' is not empty.")
            print("Re-run with --force to wipe it and create fresh sample content.")
            sys.exit(1)
        for item in real_contents:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    site_dir.mkdir(parents=True, exist_ok=True)

    for rel, content in _SCAFFOLD_FILES.items():
        dest = site_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content.format(today=today), encoding="utf-8")
        print(f"  [create] {rel}")

    print(f"\nScaffold written to '{site_dir}'.  Run ./hanma.py to build.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    if sys.version_info < (3, 10):
        sys.exit("Error: hanma.py requires Python 3.10 or later.")

    parser = argparse.ArgumentParser(
        description="Convert Markdown files to HTML, recursively.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./hanma.py                                      # Process ./site/ (default, in-place)
  ./hanma.py site/sample.md                       # Convert a single file
  ./hanma.py site/                                # Explicit site directory (in-place)
  ./hanma.py site/ --output dist/                 # Write HTML to dist/, mirroring source tree
  ./hanma.py --name "My Blog" --serve             # Named site with local server
  ./hanma.py --output dist/ --serve               # Serve from output directory
  ./hanma.py --incremental                        # Only rebuild changed pages
        """,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"hanma.py {__version__}",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Markdown file or directory to convert (default: ./site/)",
    )
    parser.add_argument(
        "--name",
        default=None,
        metavar="SITE_NAME",
        help='Site name shown in the header (default: from hanma.yml or "Blog")',
    )
    parser.add_argument(
        "--base-url",
        default=None,
        metavar="URL",
        help="Base URL for sitemap.xml and search.json (e.g. https://example.com)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be converted without writing anything",
    )
    parser.add_argument(
        "--serve",
        nargs="?",
        const=8000,
        type=int,
        metavar="PORT",
        help="Start a local HTTP server after generating, optionally on PORT (default: 8000)",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="DIR",
        help="Directory to write generated HTML files (default: output/ relative to hanma.py, not cwd)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        metavar="PORT",
        help="Port for the local HTTP server (default: 8000)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch source files and regenerate on changes after initial build",
    )
    parser.add_argument(
        "--theme",
        default=None,
        metavar="NAME",
        help='Theme to use from the themes/ directory (default: from hanma.yml or "default")',
    )
    parser.add_argument(
        "--list-themes",
        action="store_true",
        help="List available themes and exit",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only regenerate pages whose source file has changed since last build",
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="FILE",
        help="Path to config file (default: conf/hanma.yml next to hanma.py, then hanma.yml in source directory)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Scaffold a new site with sample content in ./site/ and exit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --init: overwrite existing files in the target directory",
    )
    args = parser.parse_args()

    if args.list_themes:
        if _THEMES_DIR.is_dir():
            themes = sorted(d.name for d in _THEMES_DIR.iterdir() if d.is_dir())
            if themes:
                print("Available themes:")
                for t in themes:
                    print(f"  {t}")
            else:
                print("No themes found in themes/")
        else:
            print("No themes/ directory found")
        return

    if args.init:
        site_dir = Path("site").resolve()
        init_scaffold(site_dir, force=args.force)
        return

    # ── Resolve default path: prefer ./site/, fall back to cwd ──────────────
    if args.path is None:
        site_dir = Path("site").resolve()
        if site_dir.is_dir():
            raw_path = site_dir
        else:
            raw_path = Path(".").resolve()
    else:
        raw_path = Path(args.path).resolve()

    target = raw_path

    # ── Resolve the list of files and a display root ───────────────────────
    if target.is_file():
        if target.suffix.lower() not in {".md", ".markdown"}:
            print(f"Error: '{target}' is not a Markdown file (.md / .markdown).")
            sys.exit(1)
        root = target.parent
    elif target.is_dir():
        root = target
    else:
        print(f"Error: '{target}' is not a file or directory.")
        sys.exit(1)

    # ── Load site config (hanma.yml / hanma.yaml) ────────────────────────────
    # Lookup order: --config flag > conf/hanma.yml (next to hanma.py) > hanma.yml in source root
    #               > hanma.yaml in source root (legacy fallback)
    def _find_default_config(base: Path) -> Path:
        for name in ("hanma.yml", "hanma.yaml"):
            p = base / name
            if p.is_file():
                return p
        return base / "hanma.yml"  # non-existent sentinel; load_site_config returns {}

    if args.config is not None:
        config_path = Path(args.config).resolve()
    else:
        default_conf = _find_default_config(Path(__file__).parent / "conf")
        config_path = default_conf if default_conf.is_file() else _find_default_config(root)
    site_config = load_site_config(config_path)

    # ── Merge CLI args with config (CLI always wins) ───────────────────────
    site_name   = args.name     if args.name     is not None else site_config.get("name",   "Blog")
    theme_name  = args.theme    if args.theme    is not None else site_config.get("theme",  "default")
    base_url    = args.base_url if args.base_url is not None else site_config.get("base_url", "")
    output_arg  = args.output   if args.output   is not None else site_config.get("output", None)
    posts_label = str(site_config.get("posts_label", "Blog"))

    # Boolean/int flags: CLI flag presence overrides config; config overrides built-in default
    # --serve is a nargs="?" int (None = not passed, 8000 = passed without value)
    cfg_serve       = site_config.get("serve",       False)
    cfg_port        = site_config.get("port",        8000)
    cfg_watch       = site_config.get("watch",       False)
    cfg_incremental = site_config.get("incremental", False)

    # Resolve effective serve port: explicit --serve N > --port N > config port > 8000
    if args.serve is not None:
        effective_serve = True
        effective_port  = args.serve if args.serve != 8000 else args.port
    elif cfg_serve:
        effective_serve = True
        effective_port  = cfg_port
    else:
        effective_serve = False
        effective_port  = args.port if args.port != 8000 else cfg_port

    effective_watch       = args.watch       or cfg_watch
    effective_incremental = args.incremental or cfg_incremental

    # ── Resolve output directory ───────────────────────────────────────────
    if output_arg:
        output_dir = Path(output_arg).resolve()
    else:
        output_dir = (Path(__file__).parent / "output").resolve()

    if target.is_dir() and output_dir.is_relative_to(root):
        print(f"Warning: output directory '{output_dir}' is inside the source directory '{root}'.")
        print("  This will mix generated HTML with Markdown sources.")

    # ── Handle single-file target: redirect to _run_build indirectly ──────
    # For a single file, rebuild only that file; set root to its parent.
    if target.is_file():
        # Single-file mode: convert directly
        theme_template, theme_dir = load_theme(theme_name)
        out_html = output_dir / target.name.replace(target.suffix, ".html")
        if args.dry_run:
            print(f"  [dry-run] {target.name}  →  {out_html}")
            return
        out_html.parent.mkdir(parents=True, exist_ok=True)
        copy_theme_assets(theme_dir, output_dir)
        convert_md_to_html(target, out_html, site_name, nav_pages=[], template=theme_template)
        print(f"  ✓  {target.name}  →  {out_html}")
        print(f"\nDone.  1 converted, 0 errors.")
        if effective_serve:
            _serve(output_dir, effective_port, [(out_html, "Page")])
        return

    # ── Load theme ────────────────────────────────────────────────────────
    theme_template, theme_dir = load_theme(theme_name)

    # ── Manifest path for incremental builds ─────────────────────────────
    manifest_path = output_dir / ".hanma_manifest.json" if effective_incremental else None

    # ── Run the build ─────────────────────────────────────────────────────
    print(f"Building '{site_name}'  →  {output_dir}\n")
    # Collect all_files for post-build serve logic
    _files = find_markdown_files(root)
    # Build a quick list for serve URL resolution
    _all_files_preview: list[tuple] = []
    for md_path in _files:
        title, _, front = collect_page_info(md_path)
        if front.get("draft") is True:
            continue
        if md_path.stem.lower() == "index":
            title = "Home"
        rel = md_path.relative_to(root)
        out_html = output_dir / rel.with_suffix(".html")
        _all_files_preview.append((md_path, out_html, title))
    _all_files_preview.sort(key=lambda t: (0 if t[0].stem.lower() == "index" else 1, t[0].name))

    ok, errors, skipped = _run_build(
        root, output_dir, site_name, theme_template, theme_dir,
        base_url=base_url,
        incremental=effective_incremental,
        manifest_path=manifest_path,
        dry_run=args.dry_run,
        posts_label=posts_label,
        config_path=config_path,
    )

    if args.dry_run:
        return

    if effective_watch:
        if effective_serve:
            watch_thread = threading.Thread(
                target=watch_and_rebuild,
                args=(root, output_dir, site_name, theme_template, theme_dir),
                kwargs={"base_url": base_url, "posts_label": posts_label,
                        "config_path": config_path},
                daemon=True,
            )
            watch_thread.start()
        else:
            watch_and_rebuild(root, output_dir, site_name, theme_template, theme_dir,
                              base_url=base_url, posts_label=posts_label,
                              config_path=config_path)
            return

    if effective_serve:
        print("\nStarting server…")
        _serve(output_dir, effective_port, _all_files_preview)


def _serve(serve_dir: Path, port: int, all_files: list) -> None:
    """Start a local HTTP server serving serve_dir."""

    index_html = serve_dir / "index.html"
    if index_html.is_file():
        open_url = f"http://localhost:{port}/index.html"
    elif all_files:
        first_html = all_files[0][1]
        try:
            rel_html = first_html.relative_to(serve_dir)
        except ValueError:
            rel_html = first_html
        open_url = f"http://localhost:{port}/{rel_html.as_posix()}"
    else:
        open_url = f"http://localhost:{port}/"

    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(serve_dir), **kw)
        def log_message(self, fmt, *a):
            pass

    try:
        server = HTTPServer(("127.0.0.1", port), QuietHandler)
    except OSError as exc:
        if exc.errno == 98 or "already in use" in str(exc).lower():
            print(f"Error: port {port} is already in use. Try --port <other>")
        else:
            print(f"Error starting server: {exc}")
        sys.exit(1)
    print(f"\nServing at http://localhost:{port}/")
    print(f"Opening  {open_url}")
    print("Press Ctrl+C to stop.\n")

    threading.Timer(0.5, lambda: webbrowser.open(open_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
