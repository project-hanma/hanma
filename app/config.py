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
from typing import Any, Optional
from urllib.parse import urlsplit

from app.utils import YAMLError, safe_load_yaml

_BOOL_KEYS = {"serve", "watch", "incremental", "search", "sanitize"}
_STR_KEYS = {
  "name", "base_url", "output", "theme", "posts_label",
  "host", "timezone", "sidebar_side",
}


def validate_base_url(base_url: str) -> str:
  """Validate that base_url is empty or a well-formed http/https URL."""
  cleaned = str(base_url).strip() if base_url is not None else ""
  if not cleaned:
    return ""
  if any(ord(c) < 0x20 or ord(c) == 0x7f or c.isspace() for c in cleaned):
    raise ValueError(f"Invalid base_url '{base_url}': must not contain whitespace or control chars.")
  parsed = urlsplit(cleaned)
  if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
    raise ValueError(f"Invalid base_url '{base_url}': must be an http:// or https:// URL.")
  return cleaned


def _coerce_bool(key: str, val: Any) -> Optional[bool]:
  """Coerce YAML config values to bool cleanly, avoiding truthy 'false' strings."""
  if isinstance(val, bool):
    return val
  if isinstance(val, str):
    low = val.strip().lower()
    if low in {"true", "yes", "1", "on"}:
      return True
    if low in {"false", "no", "0", "off"}:
      return False
  print(f"Warning: invalid boolean value for '{key}' ({val!r}) — ignoring.", file=sys.stderr)
  return None


def load_site_config(config_path: Path) -> dict:
  """Load hanma.yml (or hanma.yaml) from config_path. Returns {} if absent or invalid.

  Recognized fields: name, base_url, output, theme, serve, port, host, watch,
  incremental, posts_label, sanitize, timezone, search, sidebar_side.
  """
  if not config_path.is_file():
    return {}
  try:
    raw = safe_load_yaml(config_path.read_text(encoding="utf-8")) or {}
  except YAMLError as exc:
    print(f"Warning: could not parse {config_path}: {exc}", file=sys.stderr)
    return {}
  if not isinstance(raw, dict):
    return {}
  allowed = _BOOL_KEYS | _STR_KEYS | {"port"}
  cleaned: dict[str, Any] = {}
  for k, v in raw.items():
    if k not in allowed:
      continue
    if k in _BOOL_KEYS:
      coerced = _coerce_bool(k, v)
      if coerced is not None:
        cleaned[k] = coerced
    elif k in _STR_KEYS:
      if v is None:
        cleaned[k] = None
      elif isinstance(v, (str, int, float)):
        cleaned[k] = str(v)
      else:
        print(f"Warning: invalid string value for '{k}' — ignoring.", file=sys.stderr)
    else:
      cleaned[k] = v
  return cleaned


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

# Sidebar position for themes that support it (e.g., 'narwhal', 'glassmorphic').
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

# Sanitize the generated HTML using 'nh3' if available.
# sanitize: false

# Label for the posts listing link in the navigation bar.
# posts_label: Blog

# Timezone for post dates and "last updated" timestamps (e.g., UTC, America/New_York).
# Default: UTC
# timezone: UTC
"""

