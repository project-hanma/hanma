<p align="center">
  <img src="assets/hanma_logo_universal_dark_0402.svg" alt="hanma.py logo" width="400" />
</p>

A static site generator that does what it needs to and stops there. No roadmap,
no grand ambitions. The name is the honest answer to "when will it be finished?"

It builds your blog. That's mostly it.

> *はんま (hanma)* — something half-done, incomplete, not quite a whole unit.

## Features

- Converts `.md` / `.markdown` files to `.html` — written to `./output/` by default, or into
  a separate output directory with `--output`
- Recurses into sub-directories automatically, mirroring the source tree
- Defaults to `./site/` as the content root (falls back to current directory)
- `index.md` becomes the homepage — labelled **Home** and pinned first in the nav
- Folder-based navigation bar — "Home" pinned first; pages grouped by directory with dropdown menus; posts listing link ("Blog" by default) always last; optional `sort_index` front matter controls item order
- Responsive layout — 80% width centred, collapses cleanly on mobile
- Dark mode with OS preference detection and manual toggle (persisted via `localStorage`)
- Syntax-highlighted fenced code blocks (Pygments — themed per light/dark mode)
- Tables, footnotes, definition lists, abbreviations, blockquotes, linked images
- `Last updated` timestamp auto-generated from the file's modification time
- Built-in HTTP server (`--serve`) for local preview with correct theme persistence
- `--watch` mode — uses `watchdog` (inotify/FSEvents) for near-instant rebuilds; falls back to 1-second polling if not installed
- Stale output cleanup — HTML files with no corresponding source are removed automatically on every generation and in `--watch` mode when source files are deleted
- YAML front matter — optional `---` block at the top of any `.md` file for per-page metadata
- Theme system — swap the entire HTML/CSS/JS layout with `--theme NAME`; themes are self-contained directories
- Site config file (`hanma.yml`) — project-level defaults for name, output, theme, base URL, and more
- Tag index pages — `tags/<slug>.html` generated automatically from front matter tags
- Layout system — `layout: post` or `layout: page` front matter (files in `posts/` default to `post`; all others default to `page`); `posts/index.html` listing auto-generated from all `layout: post` pages sorted by date (using front matter `date` if available, falling back to file modification time; newest first), accessible at `/posts/`
- Client-side search — `search.json` generated and searchable inline via the default theme's header search box
- Sitemap — `sitemap.xml` generated when `--base-url` is set
- HTML sanitization (`--sanitize`) — optionally cleans generated HTML using `bleach` to prevent XSS from untrusted Markdown
- Static asset passthrough — `site/static/` copied verbatim to the output directory
- Incremental builds (`--incremental`) — only regenerates pages whose source, theme template, or config file has changed
- `--init` scaffold — creates a sample `site/` directory with starter content
- Skips dot-directories (e.g. `.venv`, `.git`) and `README.md` files automatically

## Requirements

Python 3.10+ and the following packages:

- `markdown`: Markdown to HTML conversion
- `pygments`: Syntax highlighting
- `pyyaml`: Front matter and config parsing
- `watchdog`: File system watching (optional, but recommended)
- `bleach`: HTML sanitization (optional, used with `--sanitize`)

### Setting up a virtual environment

It is recommended to install dependencies into a virtual environment rather
than your system Python:

```bash
# Create the virtual environment (once)
python -m venv .venv

# Activate it
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

# Install dependencies
pip install markdown pygments pyyaml watchdog bleach

# When you are done
deactivate
```

The virtual environment directory (`.venv`) is automatically skipped during Markdown discovery.

## Setup

Make the script executable so you can run it directly without typing `python`:

```bash
chmod +x hanma.py
```

The script already contains the appropriate shebang line (`#!/usr/bin/env python3`),
so after `chmod +x` you can invoke it as:

```bash
./hanma.py
./hanma.py --name "My Blog" --serve
```

## Project layout

The recommended structure places all Markdown content under `site/`:

```
project/
├── hanma.py              ← CLI entry point (thin launcher)
├── app/           ← all generator logic
├── conf/
│   └── hanma.yml         ← site config (optional)
└── site/
    ├── index.md          ← homepage (labelled "Home" in navigation)
    ├── about.md
    ├── static/           ← copied verbatim to output/static/
    │   └── logo.png
    └── posts/
        └── hello.md
```

Running `./hanma.py` from the project root will automatically discover and
process everything under `site/`, including sub-directories.

### Separate output directory

Use `--output` to write all generated HTML into a separate directory, keeping
source files untouched. The source tree is mirrored exactly:

```
project/
├── hanma.py
├── site/
│   ├── index.md
│   ├── about.md
│   └── posts/
│       └── hello.md
└── dist/               ← created by --output dist/
    ├── index.html
    ├── about.html
    └── posts/
        └── hello.html
```

## Usage

```bash
# Convert ./site/ (default)
./hanma.py

# Write output to a separate directory
./hanma.py --output dist/

# Generate and serve locally (recommended for development)
./hanma.py --name "My Blog" --serve

# Generate into dist/ and serve from there
./hanma.py --output dist/ --name "My Blog" --serve

# Serve on a custom port (two equivalent forms)
./hanma.py --serve 9000
./hanma.py --serve --port 9000

# Convert a single file
./hanma.py site/post.md

# Target a specific directory explicitly
./hanma.py ~/my-blog

# Use a custom theme
./hanma.py site/ --output output/ --theme mytheme

# Watch for changes and regenerate automatically
./hanma.py site/ --output output/ --watch

# Watch and serve simultaneously
./hanma.py site/ --output output/ --watch --serve

# Only rebuild pages that changed since last build
./hanma.py --incremental

# Sanitize generated HTML using bleach (optional)
./hanma.py --sanitize

# Generate sitemap.xml and absolute URLs in search.json
./hanma.py --base-url https://example.com

# Use a config file explicitly
./hanma.py --config path/to/hanma.yml

# Preview what would be converted without writing anything
./hanma.py --dry-run

# Scaffold a new site with sample content in ./site/
./hanma.py --init

# Scaffold into ./site/ even if it already contains files (wipes it first)
./hanma.py --init --force

# List available themes
./hanma.py --list-themes

# Show version
./hanma.py --version
```

> **Note:** The `--serve` flag is recommended for local development. Browsers
> restrict `localStorage` access when opening HTML files directly via
> `file://`, which prevents the theme preference from persisting across pages.
> Serving over `http://localhost` resolves this. When `index.html` is present,
> `--serve` will open it automatically as the landing page.

## Options

| Flag | Default | Description |
|---|---|---|
| `path` | `./site/` | Markdown file or directory to convert |
| `--name NAME` | `Blog` | Site name displayed in the page header |
| `--output DIR` | `./output/` | Directory to write generated HTML files |
| `--base-url URL` | — | Absolute base URL; enables `sitemap.xml` and absolute URLs in `search.json` |
| `--config FILE` | `conf/hanma.yml` | Path to a config file; overrides default lookup order |
| `--theme NAME` | `default` | Theme to use from the `themes/` directory |
| `--dry-run` | — | List matched files without writing HTML |
| `--incremental` | — | Only rebuild pages whose source, theme template, or config file has changed since the last build |
| `--sanitize` | — | Sanitize the generated HTML using `bleach` to prevent XSS (requires `bleach` package) |
| `--serve [PORT]` | — | Start a local HTTP server after generating; optional inline port |
| `--port PORT` | `8000` | Port for the local HTTP server (alternative to `--serve PORT`) |
| `--host ADDR` | `127.0.0.1` | Bind address for the local HTTP server |
| `--watch` | — | Watch source files and regenerate on changes after initial build |
| `--init` | — | Scaffold a new `site/` directory with sample content |
| `--force` | — | Used with `--init`; wipes `site/` before scaffolding |
| `--list-themes` | — | List available themes and exit |
| `--version` | — | Print version and exit |

## Site Config File

A `conf/hanma.yml` file (next to `hanma.py`) sets project-level defaults. CLI flags always override config file values.

```yaml
name: My Site           # site name shown in header
base_url: https://...   # used for sitemap.xml and absolute URLs in search.json
output: dist/           # output directory
theme: default          # theme name
serve: false            # start HTTP server after build (true/false)
port: 8000              # HTTP server port
host: 127.0.0.1         # HTTP server bind address
watch: false            # watch for changes and rebuild (true/false)
incremental: false      # only rebuild changed pages (true/false)
sanitize: false         # sanitize generated HTML using bleach (true/false)
posts_label: Blog       # label for the posts listing link in the nav (default: "Blog")
```

Config file lookup order (first found wins):
1. `--config FILE` flag
2. `conf/hanma.yml` (next to `hanma.py`) — the shipped default
3. `hanma.yml` at the root of the source directory
4. `hanma.yaml` at the root of the source directory (legacy fallback)

## Homepage

If `site/index.md` exists it is treated as the homepage:

- Converted to `index.html` (in-place or in `--output` dir)
- Labelled **Home** in the navigation bar regardless of the H1 in the file
- Always pinned as the first navigation item
- Opened automatically in the browser when using `--serve`

## Ignored Files

The following are silently skipped during directory traversal:

- Any file or directory whose name begins with `.` (e.g. `.venv`, `.git`)
- `README.md` and `README.markdown` (case-insensitive) in any directory

## Front Matter

Any `.md` file can include an optional YAML front matter block at the very top,
delimited by `---` lines:

```markdown
---
title: My Post Title
description: A short summary shown in search results.
author: Jane Doe
date: 2025-06-01
tags:
  - python
  - web
draft: false
refresh: 60
layout: post
sort_index: 2
---

# Content starts here
```

All fields are optional. When present they take effect as follows:

| Field | Type | Effect |
|---|---|---|
| `title` | string | Overrides the auto-extracted H1 heading; prepended with the site name in the browser title |
| `description` | string | Overrides the auto-extracted first paragraph |
| `author` | string | Shown in the page footer; added as `<meta name="author">` |
| `date` | YYYY-MM-DD | Shown in the page footer alongside the author; primary sorting and display key for the posts listing (falls back to file modification time if missing) |
| `layout` | string | `page` or `post` — overrides directory-based default (`posts/` files default to `post`) |
| `tags` | list | Rendered as a tag strip below the content; generates `tags/<slug>.html` index pages; added as `<meta name="keywords">` |
| `draft` | bool | If `true`, the page is silently skipped during generation |
| `refresh` | int | Auto-refresh interval in seconds — injects `<meta http-equiv="refresh">` into the page head; omit or set to `0` to disable |
| `sort_index` | int | Navigation sort priority (starting at `1`); lower values appear earlier; pages without `sort_index` retain their default alphabetical order but appear after all pages that have one. For subdirectory groups the `sort_index` of `index.md` controls the group's position; for index-less folders the lowest `sort_index` among the folder's children is used. Home and Blog are always pinned first and last regardless. |

## Generated Pages

Several pages are generated automatically alongside converted Markdown:

| Page | Generated when |
|---|---|
| `tags/<slug>.html` | Any source page has a `tags` front matter field |
| `posts/index.html` | Any source page has `layout: post` (files in `posts/` default to this; skipped if `posts/index.md` exists); sorted by date (newest-first); dates displayed as `M/D/YYYY` (for front matter dates) or `M/D/YYYY @ HH:MM AM/PM` (for fallback mtimes); served at `/posts/` URL |
| `sitemap.xml` | `--base-url` is set |
| `search.json` | Always — used by the default theme's inline search box |

## Static Assets

A `static/` directory at the root of the source directory is copied verbatim to `output/static/`. Use it for images, fonts, downloads, and any other non-Markdown files:

```
site/
├── index.md
└── static/
    ├── logo.png
    └── fonts/
        └── custom.woff2
```

## Syntax Highlighting

Fenced code blocks are highlighted using [Pygments](https://pygments.org/).
The light mode uses the `friendly` theme and dark mode uses `monokai` —
both switch automatically with the page theme, including OS-level dark mode
preference.

````markdown
```bash
echo "hello world"
```
````

Pygments attempts to auto-detect the language if none is specified. For best
results, always declare the language after the opening fence.

## Themes

The visual layout is controlled by a theme. Themes live in `themes/<name>/`
alongside `hanma.py` and are fully self-contained directories:

```
themes/
└── default/               ← built-in theme
    ├── template.html      ← HTML skeleton
    └── assets/
        ├── css/
        │   └── style.css  ← layout and component styles
        └── scripts/
            ├── theme-init.js    ← applies saved theme before first paint
            ├── theme-toggle.js  ← dark/light toggle button logic
            └── search.js        ← inline search dropdown
```

The `assets/` subdirectory is merged into `output/assets/` at build time,
preserving its internal structure. Pygments syntax-highlighting CSS is
generated at build time and written to `output/assets/css/pygments.css`.

Select a theme with `--theme`:

```bash
./hanma.py site/ --output output/ --theme mytheme
```

List available themes:

```bash
./hanma.py --list-themes
```

### Creating a custom theme

1. Copy `themes/default/` to `themes/mytheme/`
2. Edit `template.html` — it uses Python's `string.Template` `$variable` syntax
3. Place static assets inside an `assets/` subdirectory — they will be merged into `output/assets/` at build time (e.g. `assets/css/style.css` → `output/assets/css/style.css`)

Available variables in `template.html`:

| Variable | Content |
|---|---|
| `$title` | Browser title (automatically prepended with site name) |
| `$description` | Page description (meta) |
| `$site_name` | Site name from `--name` or config |
| `$date_str` | Today's date |
| `$nav` | Navigation bar HTML |
| `$content` | Rendered page content |
| `$author_line` | Author/date attribution (empty if not set) |
| `$author_meta` | `<meta name="author">` tag (empty if not set) |
| `$keywords_meta` | `<meta name="keywords">` tag (empty if not set) |
| `$refresh_meta` | `<meta http-equiv="refresh">` tag (empty if `refresh` not set) |
| `$source_file` | Source `.md` filename |
| `$last_updated` | File modification timestamp |
| `$sitemap_link` | Link to `sitemap.xml` (empty if `--base-url` not set) |
| `$search_json_url` | URL to `search.json` (relative or absolute) |

## Testing

A pytest suite lives in `tests/test_hanma.py` and covers syntax checking, file
discovery, conversion, CLI flags, navigation, and edge cases. It imports
`app` directly for unit tests and invokes `hanma.py` via subprocess for
CLI integration tests.

```bash
# Install pytest into your virtual environment (one-time)
pip install pytest

# Run all tests
python -m pytest tests/ -v
```

## Customisation

Visual styling is fully delegated to the active theme. See the **Themes** section above for details on creating or modifying themes under `themes/`.

## License

GPLv2 — see [LICENSE](LICENSE) for the full text.
