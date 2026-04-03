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
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
  import yaml
except ImportError:
  print("Error: 'pyyaml' package not found.")
  print("Install it with:  pip install pyyaml")
  sys.exit(1)


def parse_front_matter(md_text: str, source_path: Optional[Path] = None) -> tuple:
  """Strip and parse a YAML front matter block delimited by '---' lines.

  Returns (metadata_dict, body_text) where body_text has the front matter
  removed.  If no front matter is present returns ({}, md_text) unchanged.

  Supported fields:
   title       str   — overrides auto-extracted H1
   description str   — overrides auto-extracted first paragraph
   author      str   — displayed in the page footer
   date        str   — ISO 8601 (YYYY-MM-DD), displayed in the footer
   tags        list  — rendered as a tag strip below the content
   draft       bool  — if true, the page is skipped during generation
   refresh     int   — auto-refresh interval in seconds (omit or 0 to disable)
   layout      str   — 'page' (default) or 'post'; overrides directory-based default
  """
  lines = md_text.split("\n")
  if not lines or lines[0].strip() != "---":
    return {}, md_text
  for i, line in enumerate(lines[1:], start=1):
    if line.strip() in ("---", "..."):
      yaml_block = "\n".join(lines[1:i])
      body = "\n".join(lines[i + 1:])
      try:
        meta = yaml.safe_load(yaml_block) or {}
      except yaml.YAMLError as exc:
        loc = f" in {source_path}" if source_path else ""
        print(f"Warning: malformed YAML front matter{loc} — metadata ignored", file=sys.stderr)
        print(f"  Hint: if a value contains a colon, wrap it in quotes — e.g. title: \"My Title: Subtitle\"", file=sys.stderr)
        print(f"  YAML error: {exc}", file=sys.stderr)
        meta = {}
      if not isinstance(meta, dict):
        meta = {}
      return meta, body
  return {}, md_text


def extract_title(md_text: str, fallback: str) -> str:
  """Return the first H1 heading found, or the filename as fallback."""
  for line in md_text.splitlines():
    stripped = line.strip()
    if stripped.startswith("# "):
      return stripped[2:].strip()
  return fallback


def extract_description(md_text: str, max_chars: int = 160) -> str:
  """Return the first non-heading paragraph as a plain-text description."""
  for line in md_text.splitlines():
    stripped = line.strip()
    if stripped and not stripped.startswith("#") and not stripped.startswith("```"):
      # Strip inline markdown
      plain = re.sub(r"[*_`\[\]()!]", "", stripped)
      return plain[:max_chars]
  return ""


def parse_date_field(fm_date_raw) -> str:
  """Convert a front matter date value to a human-readable string.

  Accepts either a YYYY-MM-DD string or a datetime.date object (as parsed by
  PyYAML). Returns a formatted string like "January 01, 2025", or an empty
  string if the value is absent or malformed. Malformed values are silently
  ignored — callers should warn the user separately if needed.
  """
  d = extract_date_dt(fm_date_raw)
  return d.strftime("%B %d, %Y") if d else ""


def extract_date_dt(fm_date_raw) -> datetime | None:
  """Extract a datetime object from a front matter date field.

  Accepts either a YYYY-MM-DD string or a datetime.date object (as parsed by
  PyYAML). Returns a datetime object or None if the value is absent or malformed.
  """
  if fm_date_raw is None:
    return None
  try:
    if isinstance(fm_date_raw, str):
      return datetime.strptime(fm_date_raw, "%Y-%m-%d")
    # PyYAML parses YYYY-MM-DD as datetime.date
    return datetime(fm_date_raw.year, fm_date_raw.month, fm_date_raw.day)
  except (ValueError, AttributeError, TypeError):
    return None


def collect_page_info(md_path: Path) -> tuple:
  """Return (title, description, front_matter) for a Markdown file without full conversion."""
  md_text = md_path.read_text(encoding="utf-8")
  front, body = parse_front_matter(md_text, source_path=md_path)
  fallback = md_path.stem.replace("-", " ").replace("_", " ").title()
  title = front.get("title") or extract_title(body, fallback)
  description = front.get("description") or extract_description(body)
  return title, description, front
