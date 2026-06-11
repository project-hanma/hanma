# Configuration File

A `conf/hanma.yml` file (next to `hanma.py`) sets project-level defaults. CLI flags always override config file values.

```yaml
name: My Site           # site name shown in header
base_url: https://...   # used for sitemap.xml, feed.xml, and canonical URLs
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
sidebar_side: right     # sidebar position for supported themes (left/right)
```

## Lookup Order

Hanma looks for a configuration file in the following order (first found wins):

1. `--config FILE` flag
2. `conf/hanma.yml` (next to `hanma.py`) — the default location
3. `hanma.yml` at the root of the source directory
4. `hanma.yaml` at the root of the source directory (legacy fallback)

## Reference Configuration Generator

To quickly generate a complete skeleton reference configuration file with all available configuration settings and explanatory comments, you can use the `--generate-default-config` CLI option:

```bash
# Writes to conf/hanma-defaults.yml by default
./hanma.py --generate-default-config

# Or write to a specific directory and file path
./hanma.py --generate-default-config path/to/my-config.yml
```

