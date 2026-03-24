# ssg.py

A minimal static site generator written in Python. Drop it into any directory,
run it, and every Markdown file is converted to a self-contained HTML page
in-place — no build output folder, no configuration file required.

## Features

- Converts `.md` / `.markdown` files to `.html` alongside the source file
- Recurses into sub-directories automatically
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
pip install markdown pygments

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

## Usage

```bash
# Convert ./site/ (default — recommended)
./ssg.py

# Generate and serve locally (recommended for development)
./ssg.py --name "My Blog" --serve

# Serve on a custom port
./ssg.py --name "My Blog" --serve --port 9000

# Convert a single file
./ssg.py site/post.md

# Target a specific directory explicitly
./ssg.py ~/my-blog

# Preview what would be converted without writing anything
./ssg.py --dry-run
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
| `--dry-run` | — | List matched files without writing HTML |
| `--serve` | — | Start a local HTTP server after generating |
| `--port` | `8000` | Port for the local HTTP server |

## Homepage

If `site/index.md` exists it is treated as the homepage:

- Converted to `site/index.html`
- Labelled **Home** in the navigation bar regardless of the H1 in the file
- Always listed as the first navigation item
- Opened automatically in the browser when using `--serve`

## Ignored Files

The following are silently skipped during directory traversal:

- Any file or directory whose name begins with `.` (e.g. `.venv`, `.git`)
- `README.md` and `README.markdown` (case-insensitive) in any directory

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

## Customisation

All visual styling lives inside the `HTML_TEMPLATE` string at the top of
`ssg.py`. CSS custom properties (variables) control the colour scheme,
typography, and spacing — edit the `:root` block to retheme the entire site
in one place.

## License

MIT
