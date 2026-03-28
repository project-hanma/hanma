# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`ssg.py` is a minimal, zero-configuration static site generator that converts Markdown files to self-contained HTML pages. The entire implementation lives in a single file (`ssg.py`, ~980 lines) with no build system or config files.

**Version:** 0.1.1 (accessible as `__version__` and via `--version` flag)

**Dependencies** (install in `.venv/`): `markdown`, `pygments`, `pymdown-extensions`

## Setup & Running

```bash
# Install dependencies
source .venv/bin/activate
pip install markdown pygments pymdown-extensions

# Generate HTML from ./site/ in-place (default)
./ssg.py

# Generate into a separate output directory
./ssg.py --output dist/

# Generate with site name and serve locally (port inline or via --port)
./ssg.py --name "My Blog" --serve
./ssg.py --name "My Blog" --serve 9000
./ssg.py --name "My Blog" --serve --port 9000

# Generate into dist/ and serve from there
./ssg.py --output dist/ --name "My Blog" --serve

# Preview what would be generated (no writes)
./ssg.py --dry-run

# Target a specific file or directory
./ssg.py path/to/dir

# Show version
./ssg.py --version
```

There is no build step or linter configured. Tests are run with pytest:

```bash
pip install pytest   # one-time, into the same .venv
python -m pytest tests/ -v
```

CI runs automatically via Gitea Actions (`.gitea/workflows/ci.yml`) on every push and pull request to `main`, across Python 3.10, 3.11, and 3.12. The `--serve` flag is excluded from tests as CI runs inside a container without a browser.

## Architecture

All logic is in `ssg.py`. The pipeline runs in two passes over discovered Markdown files:

1. **Discovery** — `find_markdown_files(root)` walks the directory tree, skipping dotfiles/dotdirs (`.git`, `.venv`) and `README.md` files.
2. **Pass 1 (metadata)** — `collect_page_info()` extracts title and description from each file; output paths are computed here (in-place or under `--output` dir). Results are stored as `(md_path, out_html_path, title)` triples.
3. **Pass 2 (conversion)** — `convert_md_to_html(md_path, out_path, ...)` parses Markdown with extensions (tables, footnotes, definition lists, abbreviations, fenced code + Pygments highlighting, TOC, smart typography), injects the result into the large `HTML_TEMPLATE` constant, and writes to `out_path` (creating parent directories as needed).

**Key implementation details:**
- `HTML_TEMPLATE` (lines ~95–645) is a single string containing all CSS, JavaScript, and the HTML skeleton. CSS custom properties and responsive breakpoints (900px, 520px) are defined here.
- Syntax highlighting CSS is generated at startup via `_build_highlight_css()` using Pygments (`friendly` theme for light, `monokai` for dark).
- Dark mode toggles a `data-theme` attribute on `<html>`, persisted via `localStorage`.
- Generated HTML is fully self-contained — no external resources after generation.
- `index.md` at the root of the target directory is treated as the site homepage and titled "Home" in navigation.
- `build_nav_html()` receives `(out_html_path, title)` pairs and computes relative URLs between output files — navigation links are always relative to the output location, not the source.
- When `--output DIR` is given, the source tree is mirrored under `DIR` (e.g. `site/posts/hello.md` → `DIR/posts/hello.html`).

## Design Philosophy

- **Single file, no config** — avoid splitting into modules or adding YAML/JSON config unless functionality genuinely requires it.
- **In-place output by default** — `.html` files are written next to their source `.md` files unless `--output` is specified, in which case the source tree is mirrored into that directory.
- **Self-contained output** — generated HTML embeds all CSS/JS inline; do not introduce CDN dependencies.
