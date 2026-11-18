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
"""Sidecar file generation (RSS, Search index) for Hanma."""
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.utils import atomic_write_text, write_text_if_changed


def build_rss_xml(posts: list[tuple], output_root: Path, base_url: str,
          site_name: str = "Blog", site_description: str = "") -> Optional[Path]:
  """Write feed.xml (RSS 2.0) to output_root. Returns None if base_url is empty.

  posts is a list of (out_html_path, title, date_dt, description) tuples.
  date_dt should be an aware datetime object.
  """
  if not base_url:
    return None

  base = base_url.rstrip("/")
  pub_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

  lines = [
    '<?xml version="1.0" encoding="UTF-8" ?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    '  <channel>',
    f'    <title>{html.escape(site_name)}</title>',
    f'    <link>{html.escape(base)}/</link>',
    f'    <description>{html.escape(site_description or site_name)}</description>',
    f'    <lastBuildDate>{pub_date}</lastBuildDate>',
    f'    <atom:link href="{html.escape(base)}/feed.xml" rel="self" type="application/rss+xml" />',
    '    <generator>Hanma SSG</generator>'
  ]

  for out_path, title, date_dt, description in posts:
    try:
      rel = out_path.relative_to(output_root).as_posix()
    except ValueError:
      rel = out_path.name
    
    link = f"{base}/{rel}"
    guid = link # Use URL as GUID
    
    # RFC 822 format for RSS: "Mon, 02 Jan 2006 15:04:05 MST"
    if date_dt.tzinfo == timezone.utc:
      date_rfc = date_dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
    else:
      date_rfc = date_dt.strftime("%a, %d %b %Y %H:%M:%S %z")

    lines.append('    <item>')
    lines.append(f'      <title>{html.escape(title)}</title>')
    lines.append(f'      <link>{html.escape(link)}</link>')
    lines.append(f'      <guid isPermaLink="true">{html.escape(guid)}</guid>')
    lines.append(f'      <pubDate>{date_rfc}</pubDate>')
    if description:
      lines.append(f'      <description>{html.escape(description)}</description>')
    lines.append('    </item>')

  lines.append('  </channel>')
  lines.append('</rss>')

  out = output_root / "feed.xml"
  atomic_write_text(out, "\n".join(lines) + "\n", encoding="utf-8")
  return out


def build_sitemap_xml(pages: list[tuple], output_root: Path, base_url: str) -> Optional[Path]:
  """Write sitemap.xml to output_root. Returns None if base_url is empty.

  pages is a list of (out_html_path, lastmod_date_str) tuples.
  base_url must be an absolute URL, e.g. https://example.com
  """
  if not base_url:
    return None
  base = base_url.rstrip("/")
  lines = ['<?xml version="1.0" encoding="UTF-8"?>',
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
  for page_path, lastmod in pages:
    try:
      rel = page_path.relative_to(output_root).as_posix()
    except ValueError:
      rel = page_path.name
    loc = html.escape(f"{base}/{rel}")
    lastmod_esc = html.escape(lastmod)
    lines.append(f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod_esc}</lastmod>\n  </url>")
  lines.append("</urlset>")
  out = output_root / "sitemap.xml"
  write_text_if_changed(out, "\n".join(lines) + "\n", encoding="utf-8")
  return out


def build_search_json(entries: list[dict], output_root: Path,
           base_url: str = "") -> Path:
  """Write search.json to output_root.

  Each entry: {title, description, url, tags}
  url is relative from output_root when base_url is empty,
  or an absolute URL when base_url is provided.
  """
  base = base_url.rstrip("/") if base_url else ""
  normalized = []
  for entry in entries:
    url = entry.get("url", "")
    if base and url:
      url = f"{base}/{url}"
    normalized.append({
      "title": entry.get("title", ""),
      "description": entry.get("description", ""),
      "url": url,
      "tags": [str(t) for t in entry.get("tags", [])],
    })
  out = output_root / "search.json"
  write_text_if_changed(out, json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
  return out
