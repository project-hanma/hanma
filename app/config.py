# hanma.py — It builds your blog. That's mostly it.
# Copyright (C) 2026  Chris Hammer
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see
# <https://www.gnu.org/licenses/>.
"""Configuration loading and validation for Hanma."""
import sys
from pathlib import Path

try:
  import yaml
except ImportError as exc:
  raise RuntimeError(
    "Required package 'pyyaml' not found. Install it with:  pip install pyyaml"
  ) from exc


def load_site_config(config_path: Path) -> dict:
  """Load hanma.yml (or hanma.yaml) from config_path. Returns {} if absent or invalid.

  Recognized fields: name, base_url, output, theme, serve, port, watch, incremental.
  """
  if not config_path.is_file():
    return {}
  try:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
  except yaml.YAMLError as exc:
    print(f"Warning: could not parse {config_path}: {exc}", file=sys.stderr)
    return {}
  if not isinstance(raw, dict):
    return {}
  allowed = {"name", "base_url", "output", "theme", "serve", "port", "host", "watch", "incremental",
       "posts_label", "sanitize", "timezone", "search", "sidebar_side"}
  return {k: v for k, v in raw.items() if k in allowed}


DEFAULT_CONFIG_CONTENT = """# hanma.yml — default site configuration
# All values here can be overridden by CLI flags.
# Comment out any line to revert to the built-in default for that setting.

# Site name shown in the page header
name: Hanma

# Base URL for sitemap.xml and absolute URLs in search.json.
# Leave empty to use relative URLs (sitemap.xml will not be generated).
# Example: https://example.com
base_url: ""

# Output directory for generated HTML (relative to hanma.py, or absolute).
# Default when unset: output/ relative to hanma.py
output: output/

# Theme to use from the themes/ directory.
theme: default

# Sidebar position for themes that support it (e.g., 'narwhal').
# Options: right, left
# sidebar_side: right

# Start the local HTTP server after generating.
# serve: false

# Port for the local HTTP server (only used when serve is true).
# port: 8000

# Address the HTTP server binds to (127.0.0.1 = loopback only, 0.0.0.0 = all interfaces).
# host: 127.0.0.1

# Watch source files and regenerate on changes after the initial build.
# watch: false

# Only regenerate pages whose source file has changed since the last build.
# incremental: false

# Enable search functionality and show the search box.
search: true

# Sanitize the generated HTML using 'bleach' if available.
# sanitize: false

# Label for the posts listing link in the navigation bar.
# posts_label: Blog

# Timezone for post dates and "last updated" timestamps (e.g., UTC, America/New_York).
# Default: UTC
# timezone: UTC
"""

