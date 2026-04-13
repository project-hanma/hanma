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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
  from zoneinfo import ZoneInfo
except ImportError:
  # Fallback for systems without zoneinfo (e.g. very old Python 3.9 on Windows)
  # Hanma requires 3.10+, where zoneinfo is built-in.
  ZoneInfo = None

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


def get_localized_now(tz_name: Optional[str] = None) -> datetime:
  """Return current localized datetime based on the site's timezone."""
  tz = _resolve_tz(tz_name)
  return datetime.now(tz)


def localize_datetime(dt: datetime, tz_name: Optional[str] = None) -> datetime:
  """Ensure dt is localized to the site's configured timezone.

  If dt is naive, it's treated as local system time and then converted to tz_name.
  If dt is already aware, it's converted directly to tz_name.
  """
  tz = _resolve_tz(tz_name)
  if dt.tzinfo is None:
    # Treat as system local time, then localize
    return dt.replace(tzinfo=timezone.utc).astimezone(tz)
  return dt.astimezone(tz)


def _resolve_tz(tz_name: Optional[str]) -> timezone | ZoneInfo:
  """Resolve a timezone name string to a ZoneInfo or UTC fallback."""
  if not tz_name or not ZoneInfo:
    return timezone.utc
  try:
    return ZoneInfo(tz_name)
  except Exception:
    # Invalid timezone name; fallback to UTC
    print(f"Warning: timezone '{tz_name}' not found. Falling back to UTC.", file=sys.stderr)
    return timezone.utc


def parse_date_field(fm_date_raw, tz_name: Optional[str] = None, source_path: Optional[Path] = None) -> str:
  """Convert a front matter date value to a human-readable string.

  Accepts either a YYYY-MM-DD string or a datetime.date object (as parsed by
  PyYAML). Returns a formatted string like "January 01, 2025", or an empty
  string if the value is absent or malformed.
  """
  d = extract_date_dt(fm_date_raw, tz_name=tz_name, source_path=source_path)
  return d.strftime("%B %d, %Y") if d else ""


def extract_date_dt(fm_date_raw, tz_name: Optional[str] = None, source_path: Optional[Path] = None) -> datetime | None:
  """Extract a datetime object from a front matter date field.

  Accepts either a YYYY-MM-DD string or a datetime.date object (as parsed by
  PyYAML). Returns a datetime object localized to tz_name, or None if the value
  is absent or malformed.
  """
  if fm_date_raw is None:
    return None

  tz = _resolve_tz(tz_name)
  try:
    if isinstance(fm_date_raw, str):
      dt = datetime.strptime(fm_date_raw, "%Y-%m-%d")
      return dt.replace(tzinfo=tz)
    # PyYAML parses YYYY-MM-DD as datetime.date
    return datetime(fm_date_raw.year, fm_date_raw.month, fm_date_raw.day, tzinfo=tz)
  except (ValueError, AttributeError, TypeError) as exc:
    loc = f" in {source_path}" if source_path else ""
    print(f"Warning: invalid date '{fm_date_raw}'{loc} — using fallback.", file=sys.stderr)
    return None


def collect_page_info(md_path: Path) -> tuple[str, str, dict, str]:
  """Return (title, description, front_matter, md_text) for a Markdown file."""
  md_text = md_path.read_text(encoding="utf-8")
  front, body = parse_front_matter(md_text, source_path=md_path)
  fallback = md_path.stem.replace("-", " ").replace("_", " ").title()
  title = front.get("title") or extract_title(body, fallback)
  description = front.get("description") or extract_description(body)
  return title, description, front, md_text
