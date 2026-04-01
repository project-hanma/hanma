import html
import json
from pathlib import Path
from typing import Optional


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
  out.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
      "tags": entry.get("tags", []),
    })
  out = output_root / "search.json"
  out.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
         encoding="utf-8")
  return out
