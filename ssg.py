#!/usr/bin/env python3
"""
ssg.py — Static Site Generator
Converts Markdown files to HTML in-place, recursively.

Version: 0.1.0

Usage:
    python ssg.py [directory]

If no directory is given, the current working directory is used.
All .md files found in the directory tree are converted to .html
files written alongside the source .md file.

Dependencies:
    pip install markdown pymdown-extensions
"""

__version__ = "0.1.1"

import os
import sys
import re
import argparse
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler

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
# HTML TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <meta name="description" content="{description}" />
  <!-- Apply saved theme before first paint to avoid flash -->
  <script>
    (function(){{
      var t = localStorage.getItem("ssg-theme");
      if (t) {{ document.documentElement.setAttribute("data-theme", t); }}
      else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {{
        document.documentElement.setAttribute("data-theme", "dark");
      }}
    }})();
  </script>
  <style>
    /* ── Reset ────────────────────────────────────────────────────────────── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    /* ── Design Tokens ────────────────────────────────────────────────────── */
    :root {{
      --bg:          #f9f8f6;
      --surface:     #f0ede8;
      --border:      #c8c4bc;
      --text:        #1c1b18;
      --muted:       #78756e;
      --accent:      #5c7a18;
      --accent-soft: #f2f7e6;
      --code-bg:     #f3f2ef;
      --code-border: #dddbd6;
      --nav-bg:      #f0ede8;
      --nav-drop:    #f7f5f2;

      --font-body: "Georgia", "Times New Roman", serif;
      --font-mono: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
      --font-ui:   system-ui, -apple-system, sans-serif;

      --line:    1.75;
      --gap:     clamp(1.25rem, 4vw, 3rem);

      /* Toggle button */
      --btn-bg:      #dedad4;
      --btn-text:    #1c1b18;
      --btn-border:  #b0ada6;
    }}

    /* ── Dark mode tokens ─────────────────────────────────────────────────── */
    [data-theme="dark"] {{
      --bg:          #141412;
      --surface:     #1d1c19;
      --border:      #2e2c28;
      --text:        #e8e6e0;
      --muted:       #8a8680;
      --accent:      #c8e050;
      --accent-soft: #1e2608;
      --code-bg:     #1a1917;
      --code-border: #2e2c28;
      --nav-bg:      #1d1c19;
      --nav-drop:    #242320;
      --btn-bg:      #2a2926;
      --btn-text:    #e8e6e0;
      --btn-border:  #3a3835;
    }}

    /* Honour OS preference when no manual toggle has been set */
    @media (prefers-color-scheme: dark) {{
      :root:not([data-theme="light"]) {{
        --bg:          #141412;
        --surface:     #1d1c19;
        --border:      #2e2c28;
        --text:        #e8e6e0;
        --muted:       #8a8680;
        --accent:      #c8e050;
        --accent-soft: #1e2608;
        --code-bg:     #1a1917;
        --code-border: #2e2c28;
        --nav-bg:      #1d1c19;
        --nav-drop:    #242320;
        --btn-bg:      #2a2926;
        --btn-text:    #e8e6e0;
        --btn-border:  #3a3835;
      }}
    }}

    /* ── Base ─────────────────────────────────────────────────────────────── */
    html {{
      scroll-behavior: smooth;
      font-size: clamp(15px, 1.05vw, 17px);
      /* push content below sticky header + nav */
      scroll-padding-top: 7rem;
    }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-body);
      line-height: var(--line);
      min-height: 100dvh;
      display: flex;
      flex-direction: column;
    }}

    /* ── Sticky shell (header + nav grouped) ──────────────────────────────── */
    .sticky-shell {{
      position: sticky;
      top: 0;
      z-index: 200;
      display: flex;
      flex-direction: column;
    }}

    /* ── Site Header ──────────────────────────────────────────────────────── */
    .site-header {{
      width: 100%;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 0 10%;
    }}

    .site-header-inner {{
      display: flex;
      align-items: center;
      height: 3.25rem;
      gap: 1.5rem;
    }}

    .site-name {{
      font-family: var(--font-ui);
      font-size: 0.85rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--accent);
      text-decoration: none;
    }}
    .site-name:hover {{ opacity: 0.7; }}

    .header-sep {{ flex: 1; }}

    .site-meta {{
      font-size: 0.78rem;
      color: var(--muted);
      font-style: italic;
      font-family: var(--font-ui);
    }}

    /* ── Nav bar ──────────────────────────────────────────────────────────── */
    .site-nav {{
      width: 100%;
      background: var(--nav-bg);
      border-bottom: 1px solid var(--border);
      padding: 0 10%;
    }}

    .site-nav ul {{
      list-style: none;
      display: flex;
      flex-wrap: wrap;
      gap: 0;
      margin: 0;
      padding: 0;
    }}

    /* Top-level items (H2s) */
    .site-nav > ul > li {{
      position: relative;
    }}

    .site-nav > ul > li > a {{
      display: block;
      font-family: var(--font-ui);
      font-size: 0.78rem;
      font-weight: 500;
      letter-spacing: 0.03em;
      color: var(--text);
      text-decoration: none;
      padding: 0.65rem 1rem;
      border-bottom: 2px solid transparent;
      white-space: nowrap;
      transition: color 0.15s, border-color 0.15s;
    }}

    .site-nav > ul > li > a:hover,
    .site-nav > ul > li:focus-within > a {{
      color: var(--accent);
      border-bottom-color: var(--accent);
    }}

    /* Dropdown (H3s) */
    .site-nav > ul > li > ul {{
      display: none;
      position: absolute;
      top: 100%;
      left: 0;
      min-width: 220px;
      background: var(--nav-drop);
      border: 1px solid var(--border);
      border-top: 2px solid var(--accent);
      border-radius: 0 0 6px 6px;
      box-shadow: 0 6px 20px rgba(0,0,0,0.08);
      padding: 0.4rem 0;
      z-index: 300;
      list-style: none;
    }}

    .site-nav > ul > li:hover > ul,
    .site-nav > ul > li:focus-within > ul {{
      display: block;
    }}

    .site-nav > ul > li > ul > li > a {{
      display: block;
      font-family: var(--font-ui);
      font-size: 0.76rem;
      color: var(--muted);
      text-decoration: none;
      padding: 0.4rem 1.25rem;
      border-left: 2px solid transparent;
      transition: color 0.12s, border-color 0.12s, background 0.12s;
    }}

    .site-nav > ul > li > ul > li > a:hover {{
      color: var(--accent);
      border-left-color: var(--accent);
      background: var(--accent-soft);
    }}

    /* H4 level (third tier, if present) */
    .site-nav > ul > li > ul > li > ul {{
      list-style: none;
      padding: 0;
    }}
    .site-nav > ul > li > ul > li > ul > li > a {{
      display: block;
      font-family: var(--font-ui);
      font-size: 0.73rem;
      color: var(--muted);
      text-decoration: none;
      padding: 0.3rem 1.25rem 0.3rem 2.25rem;
      opacity: 0.8;
      transition: color 0.12s, opacity 0.12s;
    }}
    .site-nav > ul > li > ul > li > ul > li > a:hover {{
      color: var(--accent);
      opacity: 1;
    }}

    /* Current page indicator */
    .site-nav > ul > li.nav-current > a {{
      color: var(--accent);
      border-bottom-color: var(--accent);
      font-weight: 600;
    }}

    /* Divider between pages section and TOC section */
    .site-nav > ul > li.nav-divider {{
      display: flex;
      align-items: center;
      padding: 0 0.5rem;
      color: var(--border);
      font-size: 1rem;
      user-select: none;
      pointer-events: none;
    }}

    /* Hide nav if empty */
    .site-nav:empty {{ display: none; }}

    /* ── Page content wrapper — 80% centered ─────────────────────────────── */
    .page-wrap {{
      flex: 1;
      width: 80%;
      margin: 0 auto;
      padding: 1.5rem 0 calc(var(--gap) * 2);
    }}

    /* ── Article header ───────────────────────────────────────────────────── */
    /* ── Prose ────────────────────────────────────────────────────────────── */
    .prose > * + * {{ margin-top: 1.25em; }}

    .prose h1,
    .prose h2,
    .prose h3,
    .prose h4,
    .prose h5,
    .prose h6 {{
      line-height: 1.25;
      font-weight: normal;
      letter-spacing: -0.015em;
      margin-top: 2em;
      margin-bottom: 0.4em;
    }}

    .prose h1 {{ font-size: 2em; }}
    .prose h2 {{ font-size: 1.45em; border-bottom: 1px solid var(--border); padding-bottom: 0.3em; }}
    .prose h3 {{ font-size: 1.2em; }}
    .prose h4 {{ font-size: 1em; font-style: italic; }}

    .prose p {{ margin-top: 1em; }}

    .prose a {{
      color: var(--accent);
      text-decoration: underline;
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }}
    .prose a:hover {{ opacity: 0.7; }}

    .prose strong {{ font-weight: bold; }}
    .prose em {{ font-style: italic; }}

    .prose ul, .prose ol {{ padding-left: 1.5em; }}
    .prose ul {{ list-style: disc; }}
    .prose ol {{ list-style: decimal; }}
    .prose li + li {{ margin-top: 0.3em; }}
    .prose li > ul, .prose li > ol {{ margin-top: 0.3em; }}

    .prose blockquote {{
      border-left: 3px solid var(--accent);
      padding: 0.6em 1.2em;
      background: var(--accent-soft);
      border-radius: 0 4px 4px 0;
      font-style: italic;
      color: var(--muted);
    }}
    .prose blockquote p {{ margin-top: 0; }}

    .prose code {{
      font-family: var(--font-mono);
      font-size: 0.85em;
      background: var(--code-bg);
      border: 1px solid var(--code-border);
      padding: 0.1em 0.35em;
      border-radius: 3px;
    }}

    .prose pre {{
      background: #1c1b18;
      color: #e8e6e0;
      border-radius: 6px;
      padding: 1.25em 1.5em;
      overflow-x: auto;
      font-family: var(--font-mono);
      font-size: 0.82em;
      line-height: 1.6;
      border: 1px solid #2e2c27;
    }}
    .prose pre code {{
      background: transparent;
      border: none;
      padding: 0;
      font-size: inherit;
      color: inherit;
    }}

    .prose table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9em;
    }}
    .prose th {{
      text-align: left;
      font-weight: bold;
      background: var(--code-bg);
      border: 1px solid var(--border);
      padding: 0.5em 0.8em;
    }}
    .prose td {{
      border: 1px solid var(--border);
      padding: 0.45em 0.8em;
    }}
    .prose tr:nth-child(even) td {{ background: var(--accent-soft); }}

    .prose hr {{
      border: none;
      border-top: 1px solid var(--border);
      margin: 2.5em 0;
    }}

    .prose img {{
      max-width: 100%;
      height: auto;
      border-radius: 4px;
      display: block;
    }}

    .prose .footnote {{
      font-size: 0.82em;
      border-top: 1px solid var(--border);
      margin-top: 2.5em;
      padding-top: 1em;
      color: var(--muted);
    }}

    .prose dl dt {{ font-weight: bold; margin-top: 0.8em; }}
    .prose dl dd {{ margin-left: 1.5em; color: var(--muted); }}


    /* Permalink anchors from TocExtension */
    .prose .headerlink {{
      opacity: 0;
      margin-left: 0.4em;
      font-size: 0.7em;
      text-decoration: none;
      color: var(--muted);
      transition: opacity 0.15s;
    }}
    .prose :is(h2,h3,h4):hover .headerlink {{ opacity: 1; }}

    /* ── Footer ───────────────────────────────────────────────────────────── */
    .site-footer {{
      width: 100%;
      background: var(--surface);
      border-top: 1px solid var(--border);
      padding: 0.9rem 10%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 0.5rem;
    }}

    .site-footer p {{
      font-size: 0.75rem;
      color: var(--muted);
      font-family: var(--font-ui);
    }}

    /* ── Responsive ───────────────────────────────────────────────────────── */
    @media (max-width: 900px) {{
      .page-wrap {{ width: 92%; }}
      .site-header, .site-nav {{ padding-left: 4%; padding-right: 4%; }}
      .site-footer {{ padding-left: 4%; padding-right: 4%; }}

      /* Collapse nav to horizontal scroll on tablet */
      .site-nav > ul {{ flex-wrap: nowrap; overflow-x: auto; }}
      .site-nav > ul > li > ul {{ display: none !important; }}
    }}

    @media (max-width: 520px) {{
      .page-wrap {{ width: 96%; }}
      .site-nav {{ display: none; }}
    }}

    /* ── Dark mode toggle button ─────────────────────────────────────────── */
    .theme-toggle {{
      background: var(--btn-bg);
      color: var(--btn-text);
      border: 1px solid var(--btn-border);
      border-radius: 6px;
      padding: 0.25rem 0.65rem;
      font-family: var(--font-ui);
      font-size: 0.75rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      transition: background 0.15s, border-color 0.15s;
      white-space: nowrap;
      flex-shrink: 0;
    }}
    .theme-toggle:hover {{
      border-color: var(--accent);
      color: var(--accent);
    }}
    .theme-toggle .icon {{ font-size: 0.9rem; line-height: 1; }}


    {{HIGHLIGHT_CSS}}

    /* ── Print ────────────────────────────────────────────────────────────── */
    @media print {{
      .sticky-shell, .site-footer {{ display: none; }}
      .page-wrap {{ width: 100%; }}
      body {{ background: white; }}
    }}
  </style>
</head>
<body>

<div class="sticky-shell">
  <header class="site-header">
    <div class="site-header-inner">
      <a class="site-name" href="/">{site_name}</a>
      <span class="header-sep"></span>
      <span class="site-meta">{date_str}</span>
      <button class="theme-toggle" id="themeToggle" aria-label="Toggle dark mode">
        <span class="icon" id="themeIcon">&#9790;</span>
        <span id="themeLabel">Dark</span>
      </button>
    </div>
  </header>
  <nav class="site-nav" aria-label="Site navigation">
    {nav}
  </nav>
</div>

<div class="page-wrap">
  <article class="prose">
    {content}
  </article>
</div>

<footer class="site-footer">
  <p>{source_file}</p>
  <p>Last updated: {last_updated} &nbsp;&middot;&nbsp; Generated by <strong>ssg.py</strong></p>
</footer>

<script>
(function () {{
  var STORAGE_KEY = "ssg-theme";
  var root = document.documentElement;
  var btn  = document.getElementById("themeToggle");
  var icon = document.getElementById("themeIcon");
  var lbl  = document.getElementById("themeLabel");

  function currentTheme() {{
    return root.getAttribute("data-theme") || "light";
  }}

  function syncButton(theme) {{
    if (theme === "dark") {{
      icon.innerHTML = "&#9728;";
      lbl.textContent = "Light";
    }} else {{
      icon.innerHTML = "&#9790;";
      lbl.textContent = "Dark";
    }}
  }}

  // Sync button label to whatever the <head> script already applied
  syncButton(currentTheme());

  btn.addEventListener("click", function () {{
    var next = currentTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem(STORAGE_KEY, next);
    syncButton(next);
  }});
}})();
</script>

</body>
</html>
"""


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


def collect_page_info(md_path: Path) -> tuple[str, str]:
    """Return (title, description) for a Markdown file without full conversion."""
    md_text = md_path.read_text(encoding="utf-8")
    title = extract_title(md_text, md_path.stem.replace("-", " ").replace("_", " ").title())
    description = extract_description(md_text)
    return title, description


def convert_md_to_html(md_path: Path, out_path: Path, site_name: str,
                       nav_pages: list[tuple] | None = None) -> Path:
    """Read a .md file and write the HTML output to out_path.

    nav_pages is a list of (out_html_path, title) tuples for every page being
    generated, used to build the cross-page navigation bar.
    """
    md_text = md_path.read_text(encoding="utf-8")

    title = extract_title(md_text, md_path.stem.replace("-", " ").replace("_", " ").title())
    description = extract_description(md_text)

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
    content_html = md.convert(md_text)

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

    html = HTML_TEMPLATE.format(
        title=title,
        description=description,
        site_name=site_name,
        date_str=date_str,
        content=content_html,
        nav=nav_html,
        source_file=source_rel,
        generated_at=generated_at,
        last_updated=last_updated,
    ).replace("{HIGHLIGHT_CSS}", HIGHLIGHT_CSS, 1)

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

    # ── Pass 1: collect titles and compute output paths ───────────────────
    # all_files: list of (md_path, out_html_path, title)
    all_files: list[tuple] = []
    for md_path in files:
        title, _ = collect_page_info(md_path)
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
            out = convert_md_to_html(md_path, out_html, args.name, nav_pages=nav_pages)
            print(f"  ✓  {rel}  →  {out}")
            ok += 1
        except Exception as exc:
            print(f"  ✗  {rel}  →  ERROR: {exc}")
            errors += 1

    if not args.dry_run:
        print(f"\nDone.  {ok} converted, {errors} errors.")

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
