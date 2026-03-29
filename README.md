# ssg.py

A minimal static site generator written in Python. Drop it into any directory,
run it, and every Markdown file is converted to a self-contained HTML page —
no configuration file required.

## Features

- Converts `.md` / `.markdown` files to `.html` — in-place by default, or into
  a separate output directory with `--output`
- Recurses into sub-directories automatically, mirroring the source tree
- Defaults to `./site/` as the content root (falls back to current directory)
- `index.md` becomes the homepage — labelled **Home** and pinned first in the nav
- Cross-page navigation bar — all generated pages linked from every page
- Per-page table of contents rendered as a dropdown on the active nav item
- Responsive layout — 80% width centred, collapses cleanly on mobile
- Dark mode with OS preference detection and manual toggle (persisted via `localStorage`)
- Syntax-highlighted fenced code blocks (Pygments — themed per light/dark mode)
- Tables, footnotes, definition lists, abbreviations, blockquotes, linked images
- `Last updated` timestamp auto-generated from the file's modification time
- Built-in HTTP server (`--serve`) for local preview with correct theme persistence
- `--watch` mode — polls source files and regenerates on change (works with or without `--serve`)
- YAML front matter — optional `---` block at the top of any `.md` file for per-page metadata
- Skips dot-directories (e.g. `.venv`, `.git`) and `README.md` files automatically

## Requirements

Python 3.10+ and the following packages:

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
pip install markdown pygments pymdown-extensions pyyaml

# When you are done
deactivate
```

The virtual environment directory (`.venv`) is automatically skipped by
`ssg.py` during Markdown discovery.

## Setup

Make the script executable so you can run it directly without typing `python`:

```bash
chmod +x ssg.py
```

The script already contains the appropriate shebang line (`#!/usr/bin/env python3`),
so after `chmod +x` you can invoke it as:

```bash
./ssg.py
./ssg.py --name "My Blog" --serve
```

## Project layout

The recommended structure places all Markdown content under `site/`:

```
project/
├── ssg.py
└── site/
    ├── index.md        ← homepage (labelled "Home" in navigation)
    ├── about.md
    ├── code.md
    └── posts/
        └── hello.md
```

Running `./ssg.py` from the project root will automatically discover and
process everything under `site/`, including sub-directories.

### Separate output directory

Use `--output` to write all generated HTML into a separate directory, keeping
source files untouched. The source tree is mirrored exactly:

```
project/
├── ssg.py
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
# Convert ./site/ in-place (default)
./ssg.py

# Write output to a separate directory
./ssg.py --output dist/

# Generate and serve locally (recommended for development)
./ssg.py --name "My Blog" --serve

# Generate into dist/ and serve from there
./ssg.py --output dist/ --name "My Blog" --serve

# Serve on a custom port (two equivalent forms)
./ssg.py --serve 9000
./ssg.py --serve --port 9000

# Convert a single file
./ssg.py site/post.md

# Target a specific directory explicitly
./ssg.py ~/my-blog

# Watch for changes and regenerate automatically
./ssg.py site/ --output output/ --watch

# Watch and serve simultaneously
./ssg.py site/ --output output/ --watch --serve

# Preview what would be converted without writing anything
./ssg.py --dry-run

# Show version
./ssg.py --version
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
| `--name` | `Blog` | Site name displayed in the page header |
| `--output DIR` | — | Directory to write generated HTML files (default: alongside source) |
| `--dry-run` | — | List matched files without writing HTML |
| `--serve [PORT]` | — | Start a local HTTP server after generating; optional inline port |
| `--port PORT` | `8000` | Port for the local HTTP server (alternative to `--serve PORT`) |
| `--watch` | — | Watch source files and regenerate on changes after initial build |
| `--version` | — | Print version and exit |

## Homepage

If `site/index.md` exists it is treated as the homepage:

- Converted to `index.html` (in-place or in `--output` dir)
- Labelled **Home** in the navigation bar regardless of the H1 in the file
- Always listed as the first navigation item
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
---

# Content starts here
```

All fields are optional. When present they take effect as follows:

| Field | Type | Effect |
|---|---|---|
| `title` | string | Overrides the auto-extracted H1 heading |
| `description` | string | Overrides the auto-extracted first paragraph |
| `author` | string | Shown in the page footer; added as `<meta name="author">` |
| `date` | YYYY-MM-DD | Shown in the page footer alongside the author |
| `tags` | list | Rendered as a tag strip below the content; added as `<meta name="keywords">` |
| `draft` | bool | If `true`, the page is silently skipped during generation |

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

## Testing

A pytest suite lives in `tests/test_ssg.py` and covers syntax checking, file
discovery, conversion, CLI flags, navigation, and edge cases.

```bash
# Install pytest into your virtual environment (one-time)
pip install pytest

# Run all tests
python -m pytest tests/ -v
```

CI runs automatically via Gitea Actions on every push and pull request to
`main`, running on a self-hosted Fedora Docker container (`ansible-dev-fedora`).

## Customisation

All visual styling lives inside the `HTML_TEMPLATE` string at the top of
`ssg.py`. CSS custom properties (variables) control the colour scheme,
typography, and spacing — edit the `:root` block to retheme the entire site
in one place.

## License

MIT
