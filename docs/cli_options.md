# CLI Usage & Options

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

# Generate sitemap.xml, feed.xml, and canonical links
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

# Generate a default configuration file (conf/hanma-defaults.yml)
./hanma.py --generate-default-config

# Generate a default configuration file at a custom path
./hanma.py --generate-default-config my-config.yml

# Show version
./hanma.py --version
```

> **Note:** The `--serve` flag is recommended for local development. Browsers
> restrict `localStorage` access when opening HTML files directly via
> `file://`, which prevents the theme preference from persisting across pages.
> Serving over `http://localhost` resolves this. When `index.html` is present,
> `--serve` will open it automatically as the landing page.
> 
> For security, directory indexing is strictly blocked on the local development server.
> If a directory is requested and does not contain an `index.html` file, a
> `404 Not Found` response is returned instead of listing the directory's files.

## Options

| Flag | Default | Description |
|---|---|---|
| `path` | `./site/` | Markdown file or directory to convert |
| `--name NAME` | `Blog` | Site name displayed in the page header |
| `--output DIR` | `./output/` | Directory to write generated HTML files |
| `--base-url URL` | — | Absolute base URL; enables `sitemap.xml`, `feed.xml`, and absolute URLs for canonical links |
| `--config FILE` | `conf/hanma.yml` | Path to a config file; overrides default lookup order |
| `--theme NAME` | `default` | Theme to use from the `themes/` directory |
| `--dry-run` | — | List matched files without writing HTML |
| `incremental` | — | Only rebuild pages whose source, theme template, or config file has changed since the last build |
| `sanitize` | — | Sanitize the generated HTML using `bleach` to prevent XSS (requires `bleach` package) |
| `timezone` | `UTC` | Timezone name for post dates and "last updated" timestamps (e.g., `America/New_York`) |
| `--serve [PORT]` | — | Start a local HTTP server after generating; optional inline port |
| `--port PORT` | `8000` | Port for the local HTTP server (alternative to `--serve PORT`) |
| `--host ADDR` | `127.0.0.1` | Bind address for the local HTTP server |
| `--watch` | — | Watch source files and regenerate on changes after initial build |
| `--init` | — | Scaffold a new `site/` directory with sample content |
| `--force` | — | Used with `--init`; wipes `site/` before scaffolding |
| `--list-themes` | — | List available themes and exit |
| `--generate-default-config [FILE]` | — | Generate a default configuration file and exit (default: `conf/hanma-defaults.yml`) |
| `--version` | — | Print version and exit |
