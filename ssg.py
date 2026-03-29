#!/usr/bin/env python3
"""
ssg.py — Static Site Generator
Converts Markdown files to HTML in-place, recursively.

Version: 0.3.0

Usage:
    python ssg.py [directory]

If no directory is given, the current working directory is used.
All .md files found in the directory tree are converted to .html
files written alongside the source .md file.

Dependencies:
    pip install markdown pymdown-extensions pyyaml
"""

__version__ = "0.3.0"

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
    print("Install it with:  pip install markdown pymdown-extensions")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("Error: 'pyyaml' package not found.")
    print("Install it with:  pip install pyyaml")
    sys.exit(1)


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

def parse_front_matter(md_text: str) -> tuple:
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
            except yaml.YAMLError:
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
            return meta, body
    return {}, md_text


# ─────────────────────────────────────────────────────────────────────────────
# THEME LOADER
# ─────────────────────────────────────────────────────────────────────────────

_THEMES_DIR = Path(__file__).parent / "themes"


def load_theme(name: str) -> tuple:
    """Load template.html from themes/<name>/ and return (Template, theme_dir).

    Exits with a clear error message if the theme or template.html is missing.
    """
    theme_dir = _THEMES_DIR / name
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
                   nav_pages: list[tuple]) -> str:
    """Build the <ul> content for the sticky nav bar.

    Each page appears as a top-level item.  The current page is marked active
    and, if it has headings, shows a dropdown with its TOC.  Other pages link
    directly to their HTML file via a path relative to the current page.

    nav_pages is a list of (out_html_path, title) tuples.
    """
    if not nav_pages:
        return toc_inner  # single-file mode: just the TOC

    items = []

    for page_html, page_title in nav_pages:
        is_current = page_html == current_out_html

        # Compute a relative URL from current page to target page
        try:
            rel_url = os.path.relpath(page_html, current_out_html.parent)
        except ValueError:
            rel_url = page_html.as_posix()  # different drive on Windows

        if is_current:
            # Active page — show TOC as dropdown if available
            dropdown = f"\n{toc_inner}" if toc_inner else ""
            items.append(
                f'  <li class="nav-current">\n'
                f'    <a href="{rel_url}" aria-current="page">{page_title}</a>'
                f'{dropdown}\n  </li>'
            )
        else:
            items.append(
                f'  <li>\n'
                f'    <a href="{rel_url}">{page_title}</a>\n'
                f'  </li>'
            )

    return "\n<ul>\n" + "\n".join(items) + "\n</ul>\n"


def collect_page_info(md_path: Path) -> tuple:
    """Return (title, description, front_matter) for a Markdown file without full conversion."""
    md_text = md_path.read_text(encoding="utf-8")
    front, body = parse_front_matter(md_text)
    fallback = md_path.stem.replace("-", " ").replace("_", " ").title()
    title = front.get("title") or extract_title(body, fallback)
    description = front.get("description") or extract_description(body)
    return title, description, front


def convert_md_to_html(md_path: Path, out_path: Path, site_name: str,
                       nav_pages: Optional[list] = None,
                       template: Optional[string.Template] = None) -> Path:
    """Read a .md file and write the HTML output to out_path.

    nav_pages is a list of (out_html_path, title) tuples for every page being
    generated, used to build the cross-page navigation bar.
    template is a string.Template loaded from the active theme; defaults to
    the built-in default theme when not supplied.
    """
    if template is None:
        template, _ = load_theme("default")
    md_text = md_path.read_text(encoding="utf-8")
    front, body = parse_front_matter(md_text)

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
    if fm_author and fm_date_str:
        author_line = f"By <em>{fm_author}</em>, {fm_date_str} &nbsp;&middot;&nbsp; "
    elif fm_author:
        author_line = f"By <em>{fm_author}</em> &nbsp;&middot;&nbsp; "
    elif fm_date_str:
        author_line = f"{fm_date_str} &nbsp;&middot;&nbsp; "
    else:
        author_line = ""

    # Meta tags for head
    author_meta = f'<meta name="author" content="{fm_author}" />\n  ' if fm_author else ""
    if isinstance(fm_tags, list) and fm_tags:
        keywords_meta = f'<meta name="keywords" content="{", ".join(str(t) for t in fm_tags)}" />\n  '
    else:
        keywords_meta = ""

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
        tag_items = "".join(f'<span class="tag">{t}</span>' for t in fm_tags)
        content_html += f'\n<div class="page-tags">{tag_items}</div>'

    # Extract TOC inner HTML (strip the outer <div class="toc"> wrapper)
    toc_html = getattr(md, "toc", "")
    empty_toc = ('<div class="toc">\n<ul>\n</ul>\n</div>', "")
    if toc_html.strip() in empty_toc:
        toc_inner = ""
    else:
        toc_inner = re.sub(r'</?div[^>]*>', '', toc_html).strip()

    nav_html = build_nav_html(out_path, toc_inner, nav_pages or [])

    now = datetime.now()
    date_str = now.strftime("%B %d, %Y")
    generated_at = now.strftime("%H:%M %m/%d/%Y")

    mtime = datetime.fromtimestamp(md_path.stat().st_mtime)
    last_updated = mtime.strftime("%H:%M %m/%d/%Y").replace(" ", " &mdash; ", 1)
    source_rel = md_path.name

    html = template.substitute(
        title=title,
        description=description,
        author_meta=author_meta,
        keywords_meta=keywords_meta,
        author_line=author_line,
        site_name=site_name,
        date_str=date_str,
        content=content_html,
        nav=nav_html,
        source_file=source_rel,
        last_updated=last_updated,
        HIGHLIGHT_CSS=HIGHLIGHT_CSS,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


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
# WATCH MODE
# ─────────────────────────────────────────────────────────────────────────────

def watch_and_rebuild(root: Path, output_dir: Optional[Path], site_name: str,
                      template: string.Template,
                      poll_interval: float = 1.0) -> None:
    """Poll source .md files for changes and regenerate on modifications.

    Runs until KeyboardInterrupt.  On any change the affected file is
    regenerated and the full nav is rebuilt (nav is global across all pages).
    """
    print(f"Watching {root} for changes (Ctrl+C to stop)...\n")

    def get_mtimes(file_list: list) -> dict:
        mtimes = {}
        for p in file_list:
            try:
                mtimes[p] = p.stat().st_mtime
            except OSError:
                pass
        return mtimes

    def build_all_files(file_list: list) -> list:
        result = []
        for md_path in file_list:
            title, _, front = collect_page_info(md_path)
            if front.get("draft") is True:
                continue
            if md_path.stem.lower() == "index":
                title = "Home"
            if output_dir is not None:
                rel = md_path.relative_to(root)
                out_html = output_dir / rel.with_suffix(".html")
            else:
                out_html = md_path.with_suffix(".html")
            result.append((md_path, out_html, title))
        result.sort(key=lambda t: (0 if t[0].stem.lower() == "index" else 1, t[0].name))
        return result

    files = find_markdown_files(root)
    last_mtimes = get_mtimes(files)

    try:
        while True:
            time.sleep(poll_interval)
            current_files = find_markdown_files(root)
            current_mtimes = get_mtimes(current_files)

            changed = [p for p in current_files
                       if current_mtimes.get(p) != last_mtimes.get(p)]

            if changed:
                all_files = build_all_files(current_files)
                nav_pages = ([(out_html, title) for _, out_html, title in all_files]
                             if len(all_files) > 1 else [])

                for md_path in changed:
                    entry = next((e for e in all_files if e[0] == md_path), None)
                    if entry is None:
                        continue
                    _, out_html, _ = entry
                    try:
                        convert_md_to_html(md_path, out_html, site_name, nav_pages=nav_pages, template=template)
                        print(f"  [watch] regenerated {md_path.name}")
                    except Exception as exc:
                        print(f"  [watch] ERROR {md_path.name}: {exc}")

                last_mtimes = current_mtimes
                files = current_files

    except KeyboardInterrupt:
        print("\nWatch stopped.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Markdown files to HTML, recursively.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./ssg.py                                      # Process ./site/ (default, in-place)
  ./ssg.py site/sample.md                       # Convert a single file
  ./ssg.py site/                                # Explicit site directory (in-place)
  ./ssg.py site/ --output dist/                 # Write HTML to dist/, mirroring source tree
  ./ssg.py --name "My Blog" --serve             # Named site with local server
  ./ssg.py --output dist/ --serve               # Serve from output directory
        """,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ssg.py {__version__}",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Markdown file or directory to convert (default: ./site/)",
    )
    parser.add_argument(
        "--name",
        default="Blog",
        metavar="SITE_NAME",
        help='Site name shown in the header (default: "Blog")',
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
        help="Directory to write generated HTML files (default: alongside source files)",
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
        default="default",
        metavar="NAME",
        help='Theme to use from the themes/ directory (default: "default")',
    )
    args = parser.parse_args()

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
        files = [target]
        root = target.parent
    elif target.is_dir():
        root = target
        files = find_markdown_files(root)
        if not files:
            print(f"No Markdown files found under: {root}")
            return
    else:
        print(f"Error: '{target}' is not a file or directory.")
        sys.exit(1)

    print(f"Found {len(files)} Markdown file(s)\n")

    # ── Resolve output directory ───────────────────────────────────────────
    output_dir = Path(args.output).resolve() if args.output else None

    # ── Load theme ────────────────────────────────────────────────────────
    theme_template, theme_dir = load_theme(args.theme)

    # ── Pass 1: collect titles and compute output paths ───────────────────
    # all_files: list of (md_path, out_html_path, title)
    all_files: list[tuple] = []
    for md_path in files:
        title, _, front = collect_page_info(md_path)
        if front.get("draft") is True:
            print(f"  [draft] skipping {md_path.name}")
            continue
        # index.md is always labelled "Home" in the nav
        if md_path.stem.lower() == "index":
            title = "Home"
        if output_dir is not None:
            rel = md_path.relative_to(root)
            out_html = output_dir / rel.with_suffix(".html")
        else:
            out_html = md_path.with_suffix(".html")
        all_files.append((md_path, out_html, title))

    # index.html always listed first, everything else in discovery order
    all_files.sort(key=lambda t: (0 if t[0].stem.lower() == "index" else 1, t[0].name))

    # Single-file invocations get no cross-page nav (nothing to link to)
    nav_pages = [(out_html, title) for _, out_html, title in all_files] if len(all_files) > 1 else []

    # ── Copy theme assets to output root ─────────────────────────────────
    if not args.dry_run:
        assets_root = output_dir if output_dir is not None else root
        assets_root.mkdir(parents=True, exist_ok=True)
        copy_theme_assets(theme_dir, assets_root)

    ok = 0
    errors = 0

    # ── Pass 2: generate HTML with full nav ───────────────────────────────
    for md_path, out_html, _title in all_files:
        try:
            rel = md_path.relative_to(root)
        except ValueError:
            rel = md_path

        if args.dry_run:
            print(f"  [dry-run] {rel}  →  {out_html}")
            continue
        try:
            out = convert_md_to_html(md_path, out_html, args.name, nav_pages=nav_pages, template=theme_template)
            print(f"  ✓  {rel}  →  {out}")
            ok += 1
        except Exception as exc:
            print(f"  ✗  {rel}  →  ERROR: {exc}")
            errors += 1

    if not args.dry_run:
        print(f"\nDone.  {ok} converted, {errors} errors.")

    if not args.dry_run and args.watch:
        if args.serve is not None:
            # Server takes the main thread; watch runs as a background daemon
            watch_thread = threading.Thread(
                target=watch_and_rebuild,
                args=(root, output_dir, args.name, theme_template),
                daemon=True,
            )
            watch_thread.start()
        else:
            watch_and_rebuild(root, output_dir, args.name, theme_template)
            return

    if not args.dry_run and args.serve is not None:
        serve_dir = output_dir if output_dir is not None else root
        port = args.serve if isinstance(args.serve, int) else args.port

        # Find the first generated HTML file to open in the browser
        # Prefer index.html as the landing page
        index_html = serve_dir / "index.html"
        if index_html.is_file():
            open_url = f"http://localhost:{port}/index.html"
        elif all_files:
            first_html = all_files[0][1]  # out_html from first entry
            rel_html = first_html.relative_to(serve_dir)
            open_url = f"http://localhost:{port}/{rel_html.as_posix()}"
        else:
            open_url = f"http://localhost:{port}/"

        class QuietHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(serve_dir), **kwargs)
            def log_message(self, fmt, *args):
                pass  # suppress per-request noise

        server = HTTPServer(("", port), QuietHandler)
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
