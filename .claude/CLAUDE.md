# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`hanma.py` is a minimal static site generator that converts Markdown files to self-contained HTML pages. `hanma.py` is a thin launcher (~25 lines); all logic lives in `app/` (16 modules); the HTML/CSS/JS template lives in `themes/default/template.html`.

**Version:** 0.1.92 (accessible as `app.__version__` and via `--version` flag)

**Dependencies** (install in `.venv/`): `markdown`, `pygments`, `pyyaml`, `watchdog`

## Setup & Running

```bash
# Install dependencies
source .venv/bin/activate
pip install markdown pygments pymdown-extensions pyyaml watchdog

# Generate HTML into ./output/ (default)
./hanma.py

# Generate into a separate output directory
./hanma.py --output dist/

# Generate with site name and serve locally (port inline or via --port)
./hanma.py --name "My Blog" --serve
./hanma.py --name "My Blog" --serve 9000
./hanma.py --name "My Blog" --serve --port 9000

# Watch for changes and regenerate automatically (uses watchdog/inotify)
./hanma.py --watch
./hanma.py --watch --serve

# Generate into dist/ and serve from there
./hanma.py --output dist/ --name "My Blog" --serve

# Use a custom theme
./hanma.py --theme mytheme

# Preview what would be generated (no writes)
./hanma.py --dry-run

# Target a specific file or directory
./hanma.py path/to/dir

# Use a config file (default: hanma.yaml in source directory)
./hanma.py --config path/to/hanma.yaml

# Scaffold a new site with sample content in ./site/
./hanma.py --init

# Scaffold into ./site/ even if it already contains files (wipes non-.gitkeep contents)
./hanma.py --init --force

# Generate sitemap.xml and absolute URLs in search.json
./hanma.py --base-url https://example.com

# Only rebuild pages that changed since last build
./hanma.py --incremental

# Show version
./hanma.py --version
```

There is no build step or linter configured. Tests are run with pytest:

```bash
pip install pytest   # one-time, into the same .venv
python -m pytest tests/ -v
```

CI runs automatically via Gitea Actions (`.gitea/workflows/ci.yml`) on every push and pull request to `develop`, using a single job on the `ansible-dev-fedora` runner (self-hosted Fedora Docker container). The `--serve` flag is excluded from tests as CI runs inside a container without a browser.

## Repository Layout

```
hanma.py              ← thin CLI launcher (~25 lines); adds app/ to sys.path and calls main()
app/           ← all logic; importable as a package
  __init__.py         ← re-exports every public symbol; defines _THEMES_DIR and load_theme()
  _version.py         ← single source of truth for __version__
  cli.py              ← main(), _serve(), argparse
  build.py            ← _run_build() orchestration
  convert.py          ← convert_md_to_html()
  parsing.py          ← parse_front_matter(), extract_title(), extract_description(), collect_page_info(), parse_date_field()
  nav.py              ← build_nav_html()
  pages.py            ← build_tag_index_html(), build_posts_listing_html(), _make_generated_page()
  sidecar.py          ← build_sitemap_xml(), build_search_json()
  files.py            ← find_markdown_files(), copy_static_assets(), clean_stale_html(), POSTS_DIR_NAME
  theme.py            ← _load_theme_impl(), copy_theme_assets()
  config.py           ← load_site_config()
  highlight.py        ← _build_highlight_css(), HIGHLIGHT_CSS
  manifest.py         ← load_build_manifest(), save_build_manifest(), page_needs_rebuild()
  watch.py            ← watch_and_rebuild(), _HanmaEventHandler, _watch_polling()
  scaffold.py         ← init_scaffold(), _SCAFFOLD_FILES
themes/               ← theme directories (themes/<name>/template.html + assets)
conf/                 ← default site config (conf/hanma.yml)
tests/                ← pytest suite (imports app as "hanma")
```

**Notes for contributors:**
- `__version__` is defined solely in `app/_version.py` and imported everywhere else. When bumping the version, only `app/_version.py` needs to change.
- `app/_THEMES_DIR` is defined in `__init__.py` (not `theme.py`) so tests can monkey-patch it and `load_theme()` picks up the change at call time.
- `app/convert.py` and `app/cli.py` each define their own local `_THEMES_DIR` for the internal `_load_theme_impl()` fallback — this does not participate in monkey-patching.
- `POSTS_DIR_NAME` is defined in `app/files.py` and imported by `build.py` and `nav.py`. Do not redefine it locally in other modules.
- `parse_date_field()` in `app/parsing.py` is the single implementation for converting front matter `date:` values to display strings. Use it anywhere date formatting is needed.
- All `Path(__file__).parent.parent` references in `app/` resolve to the project root (one level up from `app/`), equivalent to the old `Path(__file__).parent` in the monolith.

## Architecture

The pipeline runs in two passes over discovered Markdown files, orchestrated by `_run_build()` in `app/build.py`:

1. **Discovery** — `find_markdown_files(root)` walks the directory tree, skipping dotfiles/dotdirs (`.git`, `.venv`) and `README.md` files.
2. **Pass 1 (metadata)** — `collect_page_info()` extracts title and description from each file; output paths are computed here (in-place or under `--output` dir). Also builds `tags_map`, `dated_pages`, and `search_entries` for generated pages. Results are stored as `(md_path, out_html_path, title)` triples.
3. **Pass 2 (conversion)** — `convert_md_to_html(md_path, out_path, ...)` parses Markdown with extensions (tables, footnotes, definition lists, abbreviations, fenced code + Pygments highlighting, TOC, smart typography), substitutes into the theme template, and writes to `out_path` (creating parent directories as needed).
4. **Generated pages** — After pass 2, `_run_build()` generates tag index pages (`tags/<slug>.html`), the posts listing page (`posts.html`), `sitemap.xml` (when `--base-url` is set), and `search.json`.

**Front matter fields** (YAML block delimited by `---` at the top of any `.md` file):

| Field | Type | Effect |
|---|---|---|
| `title` | string | Overrides auto-extracted H1 |
| `description` | string | Overrides auto-extracted first paragraph |
| `author` | string | Shown in page footer; added as `<meta name="author">` |
| `date` | YYYY-MM-DD | Shown in page footer alongside author (has no effect on post listing order or display — posts always use file mtime) |
| `tags` | list | Rendered as clickable tag links below content; generates `tags/<slug>.html` index pages |
| `draft` | bool | If `true`, page is skipped entirely during generation |
| `refresh` | int | Auto-refresh interval in seconds; omit or set to 0 to disable |
| `layout` | string | `page` (default) or `post`; overrides directory-based default |

**Site config file (`hanma.yml`):**

The default config is `conf/hanma.yml` (next to `hanma.py`). Lookup order:
1. `--config FILE` flag
2. `conf/hanma.yml` (relative to `hanma.py`) — the shipped default
3. `hanma.yml` at the root of the source directory
4. `hanma.yaml` at the root of the source directory (legacy fallback)

CLI flags always override config file values. Comment out any line in the config to revert that setting to its built-in default.

```yaml
name: My Site           # site name shown in header
base_url: https://...   # used for sitemap.xml and absolute URLs in search.json
output: dist/           # output directory
theme: default          # theme name
serve: false            # start HTTP server after build (true/false)
port: 8000              # HTTP server port (used when serve: true)
watch: false            # watch for changes and rebuild (true/false)
incremental: false      # only rebuild changed pages (true/false)
posts_label: Blog       # label for the posts listing nav link (default: "Blog")
```

**Themes:**

Themes live in `themes/<name>/` alongside `hanma.py`. Each theme directory contains:

- `template.html` — required; uses `string.Template` `$variable` syntax
- Any other files (CSS, images, fonts, etc.) are copied to the output root at generation time

Available template variables: `$title`, `$description`, `$author_meta`, `$keywords_meta`, `$refresh_meta`, `$author_line`, `$site_name`, `$date_str`, `$nav`, `$content`, `$source_file`, `$last_updated`, `$HIGHLIGHT_CSS`, `$sitemap_link`, `$search_json_url`

Select a theme with `--theme NAME` (default: `default`). The `themes/default/` theme is the canonical reference implementation.

**Static asset passthrough:**

Any `static/` directory at the root of the source directory is copied verbatim to `output/static/`. This is the mechanism for images, fonts, and other non-Markdown files.

**Key implementation details:**
- `load_site_config(config_path)` in `app/config.py` reads `hanma.yml` (or `hanma.yaml`) and returns a dict with recognized keys (`name`, `base_url`, `output`, `theme`, `serve`, `port`, `watch`, `incremental`, `posts_label`). CLI flags always override.
- `load_theme(name)` in `app/__init__.py` reads `themes/<name>/template.html` and returns a `string.Template`. Exits cleanly if the theme or file is missing. Wraps `_load_theme_impl(name, themes_dir)` from `app/theme.py` so `_THEMES_DIR` is read at call time.
- `copy_theme_assets(theme_dir, output_root)` copies all non-`template.html` files from the theme directory into the output root.
- `copy_static_assets(source_root, output_root)` copies `source_root/static/` → `output_root/static/` using `shutil.copytree`. Does nothing if `static/` is absent.
- Syntax highlighting CSS is generated at startup via `_build_highlight_css()` using Pygments (`friendly` theme for light, `monokai` for dark) and injected as `$HIGHLIGHT_CSS`.
- Dark mode toggles a `data-theme` attribute on `<html>`, persisted via `localStorage`.
- Generated HTML is fully self-contained — no external resources after generation.
- `index.md` at the root of the target directory is treated as the site homepage and titled "Home" in navigation. Subdirectory `index.md` files use their own title.
- **Navigation is folder-based, not heading-based.** `build_nav_html()` receives `(out_html_path, title, md_path, layout)` tuples and builds a two-level nav:
  - "Home" (root `index.md`) is always pinned as the first nav item.
  - Other root-level pages appear next as top-level items.
  - A subdirectory with an `index.md` becomes a top-level nav item (using that index's title); other pages in that directory appear as dropdown items under it.
  - Pages in `posts/` are excluded from the page-based nav.
  - If a posts listing exists (`posts.html`), a link to it is appended as the **last** nav item, labelled by `posts_label` (default `"Blog"`, configurable via `posts_label` in `hanma.yml`).
  - Headings are no longer used to generate dropdown items.
  - Navigation links are always relative to the output location, not the source. Generated pages (tag indexes, posts listing) are excluded from the page-based nav.
- **Layout defaults:** Files under `posts/` default to `layout: post`; all other files default to `layout: page`. Front matter `layout` field overrides the directory-based default.
- **Posts listing (`posts/index.html`):** All pages with `layout: post` (including those outside `posts/` with explicit `layout: post`) are included in the posts listing, sorted by file modification time (newest first). The `date` front matter field is ignored for post ordering and display — each post shows its file mtime formatted as `M/D/YYYY @ HH:MM AM/PM`. Written to `output/posts/index.html` so that the `/posts/` URL serves the listing directly. Skipped if `posts/index.md` exists as a source file. Pages outside `posts/` with `layout: post` also appear in the nav.
- When `--output DIR` is given, the source tree is mirrored under `DIR` (e.g. `site/posts/hello.md` → `DIR/posts/hello.html`).
- `clean_stale_html(output_dir, expected_html)` removes `.html` files in the output directory that have no corresponding source page. `expected_html` includes generated tag/posts pages. Called at the start of `_run_build()`.
- `_normalize_tag(tag)` converts a tag string to a filesystem-safe slug (e.g. `"my tag"` → `"my-tag"`).
- `build_tag_index_html(tag, pages, ...)` generates `tags/<slug>.html` listing all pages with that tag.
- `build_posts_listing_html(dated_pages, ...)` generates `posts/index.html` for all `layout: post` pages. `dated_pages` entries are `(out_html, title, mtime_dt, description)` tuples; sorted by `mtime_dt` newest-first. Each post displays its mtime as `M/D/YYYY @ HH:MM AM/PM`. Skipped if `posts/index.md` exists as a source file.
- `build_sitemap_xml(pages, output_root, base_url)` writes `sitemap.xml`; returns `None` and does nothing when `base_url` is empty. A "Sitemap" link is also injected into the footer of every generated page via `$sitemap_link` (empty string when `base_url` is unset).
- `build_search_json(entries, output_root, base_url)` writes `search.json` with `{title, description, url, tags}` per page. The default theme includes a client-side search box in the header that lazily fetches `search.json` on first keystroke and filters results inline — no server required. The URL is injected per-page as `$search_json_url` (relative path accounting for subdirectory depth, or absolute when `base_url` is set).
- `_search_json_url(out_path, output_root, base_url)` computes the correct URL to `search.json` as seen from a given output page.
- `init_scaffold(site_dir, force)` creates `index.md`, `about.md`, and `posts/hello-world.md` sample files in `site_dir`. `.gitkeep` is ignored when checking emptiness, so a directory containing only `.gitkeep` is treated as empty. Aborts with a non-zero exit if `site_dir` contains any real files unless `force=True`, in which case all non-`.gitkeep` contents are deleted before writing (preserving `.gitkeep`). Called by `--init`; `--force` maps to `force=True`.
- `page_needs_rebuild(md_path, out_html, manifest, template_mtime, config_mtime)` returns `True` if the page must be regenerated. Triggers on: missing output, changed source mtime, newer template, or newer config file. Used by `--incremental` mode.
- Build manifests are stored as `output_dir/.hanma_manifest.json`. Format: `{str(md_path): mtime, "_template_mtime": float, "_config_mtime": float}`.
- `watch_and_rebuild()` uses `watchdog` (inotify/FSEvents/kqueue) when available, with a 300ms debounce timer. Falls back to 1-second polling if `watchdog` is not installed. The event handler ignores events from within `output_dir` and only reacts to source suffixes (`.md`, `.markdown`, `.yaml`, `.css`, `.js`) to prevent build output from triggering a rebuild loop.
- The entire build pipeline is encapsulated in `_run_build()`, which is called both from `main()` and from the watch rebuild callback.

## Design Philosophy

- **Minimal core, extensible themes** — `app/` handles discovery, parsing, and orchestration; visual presentation is fully delegated to the active theme.
- **Output directory by default** — `.html` files are written to `./output/` (relative to `hanma.py`) unless `--output DIR` is specified, in which case the source tree is mirrored into that directory. Source `.md` files are never modified.
- **Self-contained output** — generated HTML embeds all CSS/JS inline; do not introduce CDN dependencies.
- **Config file first, CLI override** — `hanma.yaml` provides project defaults; CLI flags always take precedence.
