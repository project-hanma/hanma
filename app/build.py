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
import string
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.convert import convert_md_to_html
from app.files import find_markdown_files, copy_static_assets, clean_stale_html, POSTS_DIR_NAME
from app.manifest import (
  load_build_manifest, save_build_manifest, page_needs_rebuild,
  compute_nav_signature, compute_text_hash,
  _MANIFEST_TEMPLATE_KEY, _MANIFEST_CONFIG_KEY, _MANIFEST_NAV_KEY,
)
from app.pages import _normalize_tag, build_tag_index_html, build_posts_listing_html
from app.parsing import (
  collect_page_info, parse_date_field, extract_date_dt,
  get_localized_now, localize_datetime
)
from app.sidecar import build_sitemap_xml, build_search_json
from app.highlight import HIGHLIGHT_CSS
from app.theme import copy_theme_assets, _load_theme_impl, _CSS_SUBDIR


def _load_mtimes(theme_dir: Path, config_path: Optional[Path]) -> tuple[float, float]:
  """Return (template_mtime, config_mtime)."""
  template_mtime = 0.0
  config_mtime = 0.0
  try:
    template_mtime = (theme_dir / "template.html").stat().st_mtime
  except OSError:
    pass
  if config_path:
    try:
      config_mtime = config_path.stat().st_mtime
    except OSError:
      pass
  return template_mtime, config_mtime


def _collect_all_pages(files: list[Path], root: Path, output_dir: Path, timezone: Optional[str]):
  """Pass 1: Collect titles, output paths, and derived data for all markdown files."""
  all_files = []
  drafts = 0
  tags_map = {}
  dated_pages = []
  search_entries = []

  for md_path in files:
    title, description, front, md_text = collect_page_info(md_path)
    md_hash = compute_text_hash(md_text)
    if front.get("draft") is True:
      print(f"  [draft] skipping {md_path.name}")
      drafts += 1
      continue
    
    rel = md_path.relative_to(root)
    if md_path.stem.lower() == "index" and len(rel.parts) == 1:
      title = "Home"
    out_html = output_dir / rel.with_suffix(".html")

    rel_parts = rel.parts
    in_posts_dir = len(rel_parts) > 1 and rel_parts[0] == POSTS_DIR_NAME
    default_layout = "post" if in_posts_dir else "page"
    layout = str(front.get("layout", default_layout)).strip().lower()
    raw_si = front.get("sort_index")
    sort_index = int(raw_si) if raw_si is not None else None

    all_files.append((md_path, out_html, title, layout, sort_index, md_text, md_hash))

    fm_tags = front.get("tags", [])
    if isinstance(fm_tags, list):
      for tag in fm_tags:
        tag_str = str(tag)
        date_str = parse_date_field(front.get("date"), tz_name=timezone)
        tags_map.setdefault(tag_str, []).append((out_html, title, date_str))

    if layout == "post":
      date_dt = extract_date_dt(front.get("date"), tz_name=timezone)
      if date_dt is None:
        try:
          mtime = datetime.fromtimestamp(md_path.stat().st_mtime)
          date_dt = localize_datetime(mtime, tz_name=timezone)
        except OSError:
          date_dt = datetime.min
      dated_pages.append((out_html, title, date_dt, description))

    try:
      url_rel = out_html.relative_to(output_dir).as_posix()
    except ValueError:
      url_rel = out_html.name
    search_entries.append({
      "title": title,
      "description": description,
      "url": url_rel,
      "tags": [str(t) for t in fm_tags] if isinstance(fm_tags, list) else [],
    })

  # Sort all_files: index.html first, then by name
  all_files.sort(key=lambda t: (0 if t[0].stem.lower() == "index" else 1, t[0].name))
  
  return all_files, drafts, tags_map, dated_pages, search_entries


def _run_build(root: Path, output_dir: Path, site_name: str,
       template, theme_dir: Path,
       base_url: str = "", incremental: bool = False,
       manifest_path: Optional[Path] = None,
       dry_run: bool = False,
       posts_label: str = "Blog",
       config_path: Optional[Path] = None,
       sanitize: bool = False,
       timezone: Optional[str] = None) -> tuple[int, int, int]:
  """Run a full site build."""

  manifest = load_build_manifest(manifest_path) if (incremental and manifest_path) else {}
  template_mtime, config_mtime = _load_mtimes(theme_dir, config_path)

  files = find_markdown_files(root)
  if files:
    print(f"Found {len(files)} Markdown file(s)\n")

  all_files, drafts, tags_map, dated_pages, search_entries = _collect_all_pages(files, root, output_dir, timezone)

  def _in_posts_dir(md_path: Path) -> bool:
    try:
      rel_parts = md_path.relative_to(root).parts
      return len(rel_parts) > 1 and rel_parts[0] == POSTS_DIR_NAME
    except ValueError:
      return False

  nav_pages = [
    (out_html, title, md_path, layout, sort_index)
    for md_path, out_html, title, layout, sort_index, *rest in all_files
    if not _in_posts_dir(md_path)
  ] if len(all_files) > 1 else []

  tags_out_dir = output_dir / "tags"
  expected_html = {out_html for _, out_html, *rest in all_files}
  
  tag_out_paths = {}
  for tag in tags_map:
    slug = _normalize_tag(tag)
    tag_out_path = tags_out_dir / f"{slug}.html"
    tag_out_paths[tag] = tag_out_path
    expected_html.add(tag_out_path)

  posts_out_path = output_dir / "posts" / "index.html"
  posts_collision = any(out_html == posts_out_path for _, out_html, *rest in all_files)
  has_posts_listing = bool(dated_pages) and not posts_collision
  if has_posts_listing:
    expected_html.add(posts_out_path)

  nav_posts_out = posts_out_path if has_posts_listing else None

  if not dry_run:
    output_dir.mkdir(parents=True, exist_ok=True)
    copy_theme_assets(theme_dir, output_dir)
    pygments_path = output_dir / _CSS_SUBDIR / "pygments.css"
    pygments_path.parent.mkdir(parents=True, exist_ok=True)
    pygments_path.write_text(HIGHLIGHT_CSS, encoding="utf-8")
    copy_static_assets(root, output_dir)
    if output_dir.is_dir():
      stale = clean_stale_html(output_dir, expected_html)
      for path in stale:
        try:
          rel = path.relative_to(output_dir)
        except ValueError:
          rel = path
        print(f"  [clean] removed stale {rel}")

  ok, errors, skipped = 0, 0, 0
  recent_posts = [
    (out_path, title)
    for out_path, title, date_dt, desc in sorted(dated_pages, key=lambda t: t[2], reverse=True)[:5]
  ] if dated_pages else []

  nav_sig = compute_nav_signature(nav_pages, posts_out=nav_posts_out, recent_posts=recent_posts) if (nav_pages or nav_posts_out) else ""

  for entry in all_files:
    md_path, out_html, _title, layout, _si, md_text, md_hash = entry
    try:
      rel = md_path.relative_to(root)
    except ValueError:
      rel = md_path

    if dry_run:
      try:
        out_rel = out_html.relative_to(Path.cwd())
      except ValueError:
        out_rel = out_html
      print(f"  [dry-run] {rel}  →  {out_rel}")
      continue

    if incremental and not page_needs_rebuild(md_path, out_html, manifest, template_mtime, config_mtime, nav_sig, md_hash=md_hash):
      try:
        out_rel = out_html.relative_to(output_dir)
      except ValueError:
        out_rel = out_html
      print(f"  [skip]  {rel}  (unchanged)")
      skipped += 1
      ok += 1
      continue

    try:
      out = convert_md_to_html(
        md_path, out_html, site_name,
        nav_pages=nav_pages, template=template,
        tags_out_dir=tags_out_dir,
        base_url=base_url, output_root=output_dir,
        layout=layout,
        posts_out=nav_posts_out, posts_label=posts_label,
        sanitize=sanitize,
        timezone=timezone,
        recent_posts=recent_posts,
        md_text=md_text,
      )
      print(f"  ✓  {rel}  →  {out}")
      ok += 1
      if incremental and manifest_path is not None:
        manifest[str(md_path)] = md_hash
    except Exception as exc:
      print(f"  ✗  {rel}  →  ERROR: {exc}")
      errors += 1

  if dry_run:
    if tags_map:
      for tag, slug_path in tag_out_paths.items():
        try:
          out_rel = slug_path.relative_to(Path.cwd())
        except ValueError:
          out_rel = slug_path
        print(f"  [dry-run] (tag index) tags/{_normalize_tag(tag)}.html  →  {out_rel}")
    if has_posts_listing:
      try:
        pr = posts_out_path.relative_to(Path.cwd())
      except ValueError:
        pr = posts_out_path
      print(f"  [dry-run] (posts listing) posts/index.html  →  {pr}")
    return ok, errors, skipped

  # ── Generate tag index pages ──────────────────────────────────────────
  def _tag_sort_key(entry):
    _, _, date_str = entry
    if date_str:
      try:
        return (0, datetime.strptime(date_str, "%B %d, %Y"))
      except ValueError:
        pass
    return (1, datetime.min)

  for tag, tag_pages in tags_map.items():
    tag_out = tag_out_paths[tag]
    tag_pages_sorted = sorted(tag_pages, key=_tag_sort_key, reverse=True)
    try:
      build_tag_index_html(tag, tag_pages_sorted, tag_out, site_name, nav_pages, template,
              base_url=base_url, output_root=output_dir,
              posts_out=nav_posts_out, posts_label=posts_label,
              recent_posts=recent_posts)
      print(f"  [tag]   tags/{_normalize_tag(tag)}.html  ({len(tag_pages)} page(s))")
    except Exception as exc:
      print(f"  [tag]   ERROR generating tags/{_normalize_tag(tag)}.html: {exc}")
      errors += 1

  # ── Generate posts listing page ───────────────────────────────────────
  if has_posts_listing:
    try:
      build_posts_listing_html(dated_pages, posts_out_path, site_name, nav_pages, template,
                  base_url=base_url, output_root=output_dir,
                  posts_label=posts_label, posts_out=nav_posts_out,
                  recent_posts=recent_posts)
      print(f"  [posts] posts/index.html  ({len(dated_pages)} post(s))")
    except Exception as exc:
      print(f"  [posts] ERROR generating posts/index.html: {exc}")
      errors += 1
  elif posts_collision:
    print("  [posts] skipped: posts/index.md exists as source file")

  # ── Generate sitemap.xml ──────────────────────────────────────────────
  if base_url:
    sitemap_pages = []
    for _, out_html, *rest in all_files:
      try:
        mtime = out_html.stat().st_mtime
        lastmod = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
      except OSError:
        lastmod = datetime.now().strftime("%Y-%m-%d")
      sitemap_pages.append((out_html, lastmod))
    sitemap_path = build_sitemap_xml(sitemap_pages, output_dir, base_url)
    if sitemap_path:
      print(f"  [sitemap] sitemap.xml  ({len(sitemap_pages)} URL(s))")

  # ── Generate search.json ──────────────────────────────────────────────
  search_path = build_search_json(search_entries, output_dir, base_url)
  print(f"  [search] search.json  ({len(search_entries)} entry/entries)")

  if incremental and manifest_path is not None:
    manifest[_MANIFEST_TEMPLATE_KEY] = template_mtime
    manifest[_MANIFEST_CONFIG_KEY] = config_mtime
    manifest[_MANIFEST_NAV_KEY] = nav_sig
    save_build_manifest(manifest_path, manifest)

  if not dry_run:
    draft_note = f", {drafts} draft(s) skipped" if drafts else ""
    skip_note = f", {skipped} skipped (unchanged)" if skipped else ""
    print(f"\nDone.  {ok} converted{skip_note}{draft_note}, {errors} errors.")

  return ok, errors, skipped
