# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`ssg.py` is a minimal static site generator that converts Markdown files to self-contained HTML pages. Core logic lives in `ssg.py` (~690 lines); the HTML/CSS/JS template lives in `themes/default/template.html`.

**Version:** 0.3.0 (accessible as `__version__` and via `--version` flag)

**Dependencies** (install in `.venv/`): `markdown`, `pygments`, `pymdown-extensions`, `pyyaml`

## Setup & Running

```bash
# Install dependencies
source .venv/bin/activate
pip install markdown pygments pymdown-extensions pyyaml

# Generate HTML from ./site/ in-place (default)
./ssg.py

# Generate into a separate output directory
./ssg.py --output dist/

# Generate with site name and serve locally (port inline or via --port)
./ssg.py --name "My Blog" --serve
./ssg.py --name "My Blog" --serve 9000
./ssg.py --name "My Blog" --serve --port 9000

# Watch for changes and regenerate automatically
./ssg.py --watch
./ssg.py --watch --serve

# Generate into dist/ and serve from there
./ssg.py --output dist/ --name "My Blog" --serve

# Use a custom theme
./ssg.py --theme mytheme

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

CI runs automatically via Gitea Actions (`.gitea/workflows/ci.yml`) on every push and pull request to `develop`, using a single job on the `ansible-dev-fedora` runner (self-hosted Fedora Docker container). The `--serve` flag is excluded from tests as CI runs inside a container without a browser.

## Architecture

The pipeline runs in two passes over discovered Markdown files:

1. **Discovery** — `find_markdown_files(root)` walks the directory tree, skipping dotfiles/dotdirs (`.git`, `.venv`) and `README.md` files.
2. **Pass 1 (metadata)** — `collect_page_info()` extracts title and description from each file; output paths are computed here (in-place or under `--output` dir). Results are stored as `(md_path, out_html_path, title)` triples.
3. **Pass 2 (conversion)** — `convert_md_to_html(md_path, out_path, ...)` parses Markdown with extensions (tables, footnotes, definition lists, abbreviations, fenced code + Pygments highlighting, TOC, smart typography), substitutes into the theme template, and writes to `out_path` (creating parent directories as needed).

**Front matter fields** (YAML block delimited by `---` at the top of any `.md` file):

| Field | Type | Effect |
|---|---|---|
| `title` | string | Overrides auto-extracted H1 |
| `description` | string | Overrides auto-extracted first paragraph |
| `author` | string | Shown in page footer; added as `<meta name="author">` |
| `date` | YYYY-MM-DD | Shown in page footer alongside author |
| `tags` | list | Rendered as a tag strip below content; added as `<meta name="keywords">` |
| `draft` | bool | If `true`, page is skipped entirely during generation |

**Themes:**

Themes live in `themes/<name>/` alongside `ssg.py`. Each theme directory contains:

- `template.html` — required; uses `string.Template` `$variable` syntax
- Any other files (CSS, images, fonts, etc.) are copied to the output root at generation time

Available template variables: `$title`, `$description`, `$author_meta`, `$keywords_meta`, `$author_line`, `$site_name`, `$date_str`, `$nav`, `$content`, `$source_file`, `$last_updated`, `$HIGHLIGHT_CSS`

Select a theme with `--theme NAME` (default: `default`). The `themes/default/` theme is the canonical reference implementation.

**Key implementation details:**
- `load_theme(name)` reads `themes/<name>/template.html` and returns a `string.Template`. Exits cleanly if the theme or file is missing.
- `copy_theme_assets(theme_dir, output_root)` copies all non-`template.html` files from the theme directory into the output root.
- Syntax highlighting CSS is generated at startup via `_build_highlight_css()` using Pygments (`friendly` theme for light, `monokai` for dark) and injected as `$HIGHLIGHT_CSS`.
- Dark mode toggles a `data-theme` attribute on `<html>`, persisted via `localStorage`.
- Generated HTML is fully self-contained — no external resources after generation.
- `index.md` at the root of the target directory is treated as the site homepage and titled "Home" in navigation.
- `build_nav_html()` receives `(out_html_path, title)` pairs and computes relative URLs between output files — navigation links are always relative to the output location, not the source.
- When `--output DIR` is given, the source tree is mirrored under `DIR` (e.g. `site/posts/hello.md` → `DIR/posts/hello.html`).

## Design Philosophy

- **Minimal core, extensible themes** — `ssg.py` handles discovery, parsing, and orchestration; visual presentation is fully delegated to the active theme.
- **In-place output by default** — `.html` files are written next to their source `.md` files unless `--output` is specified, in which case the source tree is mirrored into that directory.
- **Self-contained output** — generated HTML embeds all CSS/JS inline; do not introduce CDN dependencies.
