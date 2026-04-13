# Configuration File

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
timezone: UTC           # timezone name (e.g. America/New_York)
posts_label: Blog       # label for the posts listing link in the nav (default: "Blog")
```

## Lookup Order

Hanma looks for a configuration file in the following order (first found wins):

1. `--config FILE` flag
2. `conf/hanma.yml` (next to `hanma.py`) — the default location
3. `hanma.yml` at the root of the source directory
4. `hanma.yaml` at the root of the source directory (legacy fallback)
