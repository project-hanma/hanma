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
"""Site building and orchestration logic for Hanma."""
import sys
from datetime import datetime, date, timezone as dt_timezone
from pathlib import Path
from typing import Optional

from app.convert import convert_md_to_html
from app.files import find_markdown_files, copy_static_assets, clean_stale_html, POSTS_DIR_NAME
from app.manifest import (
  load_build_manifest, save_build_manifest, page_needs_rebuild,
  compute_nav_signature, compute_text_hash, compute_aux_signature,
  _MANIFEST_TEMPLATE_KEY, _MANIFEST_CONFIG_KEY, _MANIFEST_NAV_KEY,
  _MANIFEST_AUX_KEY, _MANIFEST_META_KEY,
)
from app.pages import _normalize_tag, build_tag_index_html, build_posts_listing_html
from app.parsing import (
  parse_front_matter, extract_title, extract_description,
  extract_date_dt,
  localize_datetime, _resolve_tz
)
from app.sidecar import build_sitemap_xml, build_search_json, build_rss_xml
from app.highlight import _build_highlight_css
from app.theme import copy_theme_assets, _load_theme_impl, _CSS_SUBDIR
from app.utils import BuildContext, write_text_if_changed


def _process_page_worker(md_path: Path, out_html: Path, nav_pages: list,
                         theme_name: str, themes_dir: Path, tags_out_dir: Path,
                         layout: str, front: Optional[dict], body: Optional[str],
                         ctx: BuildContext, source_mtime: Optional[float] = None) -> Path:
  """Worker function to convert one page (supports pre-loaded template or reloading)."""
  template = ctx.template
  if template is None:
    template, _ = _load_theme_impl(theme_name, themes_dir)
  return convert_md_to_html(
    md_path, out_html, ctx.site_name,
    nav_pages=nav_pages, template=template,
    tags_out_dir=tags_out_dir,
    base_url=ctx.base_url, output_root=ctx.output_dir,
    _layout=layout,
    posts_out=ctx.posts_out, posts_label=ctx.posts_label,
    sanitize=ctx.sanitize,
    timezone=ctx.timezone,
    recent_posts=ctx.recent_posts,
    front_matter=front,
    body=body,
    search_enabled=ctx.search_enabled,
    sidebar_side=ctx.sidebar_side,
    source_mtime=source_mtime,
    resolved_root_index=ctx.resolved_root_index,
  )


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


def _collect_all_pages(files: list[Path], root: Path, output_dir: Path,
                       timezone: Optional[str],
                       manifest: Optional[dict] = None,
                       incremental: bool = False):
  """Pass 1: Collect titles, output paths, and derived data for all markdown files."""
  all_files = []
  drafts = 0
  tags_map: dict[str, list[tuple[Path, str, datetime]]] = {}
  slug_to_tag: dict[str, str] = {}
  dated_pages = []
  search_entries = []
  meta_cache = manifest.get(_MANIFEST_META_KEY, {}) if (incremental and isinstance(manifest, dict)) else {}
  new_meta_cache: dict[str, dict] = {}
  tz_key = timezone or ""

  for md_path in files:
    key = str(md_path)
    try:
      st = md_path.stat()
      md_size, md_mtime_ns, md_mtime = st.st_size, st.st_mtime_ns, st.st_mtime
    except OSError:
      md_size, md_mtime_ns, md_mtime = -1, -1, 0.0

    cached = meta_cache.get(key) if isinstance(meta_cache, dict) else None
    cache_hit = (
      isinstance(cached, dict)
      and md_size >= 0
      and cached.get("size") == md_size
      and cached.get("mtime_ns") == md_mtime_ns
      and cached.get("tz") == tz_key
    )

    loaded_from_cache = False
    if cache_hit and cached is not None:
      if cached.get("draft") is True:
        new_meta_cache[key] = cached
        print(f"  [draft] skipping {md_path.name}")
        drafts += 1
        continue
      try:
        cached_hash = cached["hash"]
        if not isinstance(cached_hash, str) or len(cached_hash) != 64:
          raise ValueError("Invalid cached hash")
        rel = md_path.relative_to(root)
        out_html = output_dir / rel.with_suffix(".html")
        title = str(cached["title"])
        description = str(cached["description"])
        layout = str(cached["layout"])
        sort_index = cached["sort_index"]
        if sort_index is not None and not isinstance(sort_index, int):
          raise ValueError("Invalid cached sort_index")
        link_cached = cached.get("link")
        front: Optional[dict] = {"link": link_cached} if isinstance(link_cached, dict) else {}
        body: Optional[str] = None
        md_hash = cached_hash
        raw_cached_tags = cached.get("tags", [])
        if not isinstance(raw_cached_tags, list):
          raise ValueError("Invalid cached tags")
        fm_tags = [str(t) for t in raw_cached_tags]
        date_dt = datetime.fromisoformat(cached["date_iso"])
        new_meta_cache[key] = cached
        loaded_from_cache = True
      except (KeyError, TypeError, ValueError):
        loaded_from_cache = False

    if not loaded_from_cache:
      md_text = md_path.read_text(encoding="utf-8")
      md_hash = compute_text_hash(md_text)
      front, body = parse_front_matter(md_text, source_path=md_path)

      if front.get("draft") is True:
        print(f"  [draft] skipping {md_path.name}")
        drafts += 1
        if md_size >= 0:
          new_meta_cache[key] = {
            "size": md_size, "mtime_ns": md_mtime_ns, "tz": tz_key, "draft": True,
          }
        continue

      fallback = md_path.stem.replace("-", " ").replace("_", " ").title()
      title = front.get("title") or extract_title(body, fallback)
      description = front.get("description") or extract_description(body)

      rel = md_path.relative_to(root)
      if md_path.stem.lower() == "index" and len(rel.parts) == 1:
        title = "Home"
      out_html = output_dir / rel.with_suffix(".html")

      rel_parts = rel.parts
      in_posts_dir = len(rel_parts) > 1 and rel_parts[0] == POSTS_DIR_NAME
      default_layout = "post" if in_posts_dir else "page"
      layout = str(front.get("layout", default_layout)).strip().lower()
      raw_si = front.get("sort_index")
      try:
        sort_index = int(raw_si) if raw_si is not None else None
      except (ValueError, TypeError):
        print(f"Warning: invalid sort_index '{raw_si}' in {md_path} — ignoring.", file=sys.stderr)
        sort_index = None

      extracted_dt = extract_date_dt(front.get("date"), tz_name=timezone, source_path=md_path)
      if extracted_dt is not None:
        date_dt = extracted_dt
      elif md_mtime > 0.0:
        mtime = datetime.fromtimestamp(md_mtime)
        date_dt = localize_datetime(mtime, tz_name=timezone)
      else:
        fallback_min = datetime(1970, 1, 1)
        date_dt = localize_datetime(fallback_min, tz_name=timezone)

      raw_tags = front.get("tags", [])
      fm_tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
      if md_size >= 0:
        link_val = front.get("link")
        new_meta_cache[key] = {
          "size": md_size,
          "mtime_ns": md_mtime_ns,
          "tz": tz_key,
          "draft": False,
          "hash": md_hash,
          "title": title,
          "description": description,
          "layout": layout,
          "sort_index": sort_index,
          "link": link_val if isinstance(link_val, dict) else None,
          "tags": fm_tags,
          "date_iso": date_dt.isoformat(),
        }

    all_files.append((md_path, out_html, title, layout, sort_index, front, body, md_hash, md_mtime))

    if fm_tags:
      seen_slugs: set[str] = set()
      for tag_str in fm_tags:
        slug = _normalize_tag(tag_str)
        if not slug or slug in seen_slugs:
          continue
        seen_slugs.add(slug)
        canonical_tag = slug_to_tag.setdefault(slug, tag_str)
        tags_map.setdefault(canonical_tag, []).append((out_html, title, date_dt))

    if layout == "post":
      dated_pages.append((out_html, title, date_dt, description))

    try:
      url_rel = out_html.relative_to(output_dir).as_posix()
    except ValueError:
      url_rel = out_html.name
    search_entries.append({
      "title": title,
      "description": description,
      "url": url_rel,
      "tags": fm_tags,
    })

  # Sort all_files: index.html first, then by name
  all_files.sort(key=lambda t: (0 if t[0].stem.lower() == "index" else 1, t[0].name))

  if incremental and isinstance(manifest, dict):
    manifest[_MANIFEST_META_KEY] = new_meta_cache

  return all_files, drafts, tags_map, dated_pages, search_entries


def _generate_sidecar_files(all_files: list, output_dir: Path,
                            base_url: str, search_entries: list,
                            dated_pages: list,
                            site_name: str = "Blog",
                            search_enabled: bool = True) -> None:
  """Generate sitemap.xml, feed.xml, and search.json."""
  if base_url:
    # ── Generate sitemap.xml ──────────────────────────────────────────────
    sitemap_pages = []
    for entry in all_files:
      md_path, out_html = entry[0], entry[1]
      md_mtime = entry[8] if len(entry) > 8 else 0.0
      try:
        if md_mtime > 0.0:
          mtime = md_mtime
        elif md_path.exists():
          mtime = md_path.stat().st_mtime
        else:
          mtime = out_html.stat().st_mtime
        lastmod = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
      except OSError:
        lastmod = datetime.now().strftime("%Y-%m-%d")
      sitemap_pages.append((out_html, lastmod))
    sitemap_path = build_sitemap_xml(sitemap_pages, output_dir, base_url)
    if sitemap_path:
      print(f"  [sitemap] sitemap.xml  ({len(sitemap_pages)} URL(s))")

    # ── Generate feed.xml (RSS) ───────────────────────────────────────────
    rss_path = build_rss_xml(dated_pages, output_dir, base_url, site_name=site_name)
    if rss_path:
      print(f"  [rss]   feed.xml     ({len(dated_pages)} entry/entries)")

  # ── Generate search.json ──────────────────────────────────────────────
  if search_enabled:
    build_search_json(search_entries, output_dir, base_url)
    print(f"  [search] search.json  ({len(search_entries)} entry/entries)")
  else:
    print("  [search] skipped (disabled in config)")


def _tag_sort_key(entry: tuple, tz_name: Optional[str] = None) -> tuple[int, datetime]:
  """Sort key for tag listing: dated entries first (by date desc), then undated.

  Normalizes all datetimes (aware, naive, date objects, or string representations)
  to offset-aware UTC datetimes to prevent TypeError on mixed aware/naive comparison.
  """
  _, _, date_val = entry
  dt: Optional[datetime] = None
  tz = _resolve_tz(tz_name)

  if isinstance(date_val, datetime):
    if date_val.tzinfo is not None:
      dt = date_val.astimezone(dt_timezone.utc)
    else:
      dt = date_val.replace(tzinfo=tz).astimezone(dt_timezone.utc)
  elif isinstance(date_val, date):
    d = datetime(date_val.year, date_val.month, date_val.day, tzinfo=tz)
    dt = d.astimezone(dt_timezone.utc)
  elif isinstance(date_val, str) and date_val.strip():
    raw = date_val.strip()
    for fmt in ("%B %d, %Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
      try:
        parsed = datetime.strptime(raw, fmt)
        dt = parsed.replace(tzinfo=tz).astimezone(dt_timezone.utc)
        break
      except ValueError:
        pass
    if dt is None:
      try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is not None:
          dt = parsed.astimezone(dt_timezone.utc)
        else:
          dt = parsed.replace(tzinfo=tz).astimezone(dt_timezone.utc)
      except (ValueError, TypeError):
        print(f"Warning: malformed internal date '{date_val}' in tag sort", file=sys.stderr)

  if dt is not None:
    return (1, dt)
  return (0, datetime.min.replace(tzinfo=dt_timezone.utc))


def _generate_tag_indices(tags_map: dict, tag_out_paths: dict,
                          nav_pages: list, ctx: BuildContext) -> int:
  """Generate tag index pages and return error count."""
  errors = 0
  assert ctx.output_dir is not None

  for tag, tag_pages in tags_map.items():
    tag_out = tag_out_paths[tag]
    tag_pages_sorted = sorted(
      tag_pages,
      key=lambda e: _tag_sort_key(e, tz_name=ctx.timezone),
      reverse=True,
    )
    try:
      build_tag_index_html(
        tag, tag_pages_sorted, tag_out, ctx.site_name, nav_pages, ctx.template,
        base_url=ctx.base_url, output_root=ctx.output_dir,
        posts_out=ctx.posts_out, posts_label=ctx.posts_label,
        recent_posts=ctx.recent_posts, search_enabled=ctx.search_enabled,
        sidebar_side=ctx.sidebar_side, timezone=ctx.timezone,
      )
      print(f"  [tag]   tags/{_normalize_tag(tag)}.html  ({len(tag_pages)} page(s))")
    except Exception as exc:  # pylint: disable=broad-exception-caught
      print(f"  [tag]   ERROR generating tags/{_normalize_tag(tag)}.html: {exc}")
      errors += 1
  return errors


def _prepare_output(output_dir: Path, theme_dir: Path, root: Path,
                    expected_html: set[Path],
                    base_url: str = "",
                    search_enabled: bool = True) -> list[Path]:
  """Prepare output directory: create, copy assets, and clean stale files."""
  output_dir.mkdir(parents=True, exist_ok=True)
  copy_theme_assets(theme_dir, output_dir)
  pygments_path = output_dir / _CSS_SUBDIR / "pygments.css"
  write_text_if_changed(pygments_path, _build_highlight_css(), encoding="utf-8")
  copy_static_assets(root, output_dir)
  stale: list[Path] = []
  if output_dir.is_dir():
    stale = clean_stale_html(output_dir, expected_html)
    for path in stale:
      try:
        rel = path.relative_to(output_dir)
      except ValueError:
        rel = path
      print(f"  [clean] removed stale {rel}")
    stale_sidecars: list[Path] = []
    if not base_url:
      stale_sidecars.extend([output_dir / "sitemap.xml", output_dir / "feed.xml"])
    if not search_enabled:
      stale_sidecars.append(output_dir / "search.json")
    for sidecar_path in stale_sidecars:
      if sidecar_path.is_file():
        try:
          sidecar_path.unlink()
          stale.append(sidecar_path)
          print(f"  [clean] removed stale {sidecar_path.name}")
        except OSError as exc:
          print(f"  [clean] warning: could not remove {sidecar_path}: {exc}", file=sys.stderr)
  return stale


def _print_dry_run_auxiliary(tags_map: dict, tag_out_paths: dict, has_posts_listing: bool, posts_out_path: Path) -> None:
  """Print dry-run info for tags and posts indices."""
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


def _generate_auxiliary_pages(tags_map: dict, tag_out_paths: dict, nav_pages: list,
                              has_posts_listing: bool, posts_out_path: Path,
                              dated_pages: list, posts_collision: bool,
                              all_files: list, search_entries: list,
                              ctx: BuildContext) -> int:
  """Generate tag indices, posts listing, and sidecar files."""
  errors = 0
  assert ctx.output_dir is not None
  errors += _generate_tag_indices(tags_map, tag_out_paths, nav_pages, ctx)

  # ── Generate posts listing page ───────────────────────────────────────
  if has_posts_listing:
    try:
      build_posts_listing_html(
        dated_pages, posts_out_path, ctx.site_name, nav_pages, ctx.template,
        base_url=ctx.base_url, output_root=ctx.output_dir,
        posts_label=ctx.posts_label, posts_out=ctx.posts_out,
        recent_posts=ctx.recent_posts, search_enabled=ctx.search_enabled,
        sidebar_side=ctx.sidebar_side, timezone=ctx.timezone,
      )
      print(f"  [posts] posts/index.html  ({len(dated_pages)} post(s))")
    except Exception as exc:  # pylint: disable=broad-exception-caught
      print(f"  [posts] ERROR generating posts/index.html: {exc}")
      errors += 1
  elif posts_collision:
    print("  [posts] skipped: posts/index.md exists as source file")

  # ── Generate sidecar files ────────────────────────────────────────────
  _generate_sidecar_files(
    all_files, ctx.output_dir, ctx.base_url, search_entries, dated_pages,
    site_name=ctx.site_name, search_enabled=ctx.search_enabled,
  )

  return errors


def _prepare_tasks(all_files: list, root: Path, theme_dir: Path,
                   ctx: BuildContext, nav_pages: list,
                   incremental: bool, manifest: dict,
                   manifest_path: Optional[Path], template_mtime: float,
                   config_mtime: float, nav_sig: str, dry_run: bool) -> tuple:
  """Determine which pages need rebuilding and plan worker tasks."""
  tasks, ok, skipped = [], 0, 0
  assert ctx.output_dir is not None
  theme_name = theme_dir.name
  themes_dir = theme_dir.parent
  tags_out_dir = ctx.output_dir / "tags"

  for entry in all_files:
    md_path, out_html, _title, layout, _si, front, body, md_hash, md_mtime = entry
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

    if incremental and not page_needs_rebuild(
      md_path, out_html, manifest, template_mtime, config_mtime, nav_sig, md_hash=md_hash
    ):
      print(f"  [skip]  {rel}  (unchanged)")
      skipped += 1
      ok += 1
      if manifest_path is not None:
        manifest[str(md_path)] = md_hash
      continue

    tasks.append((
      _process_page_worker,
      (
        md_path, out_html, nav_pages, theme_name, themes_dir,
        tags_out_dir, layout, front, body, ctx, md_mtime
      ),
      rel, md_hash, md_path
    ))
  return tasks, ok, skipped


def _plan_outputs(all_files: list, root: Path, output_dir: Path, tags_map: dict, dated_pages: list, base_url: str, search_enabled: bool) -> tuple:
  """Determine which HTML files will be generated and identify nav pages."""
  def _in_posts_dir(md_path: Path) -> bool:
    try:
      rel_parts = md_path.relative_to(root).parts
      return len(rel_parts) > 1 and rel_parts[0] == POSTS_DIR_NAME
    except ValueError:
      return False

  nav_pages = [
    (out_html, title, md_path, layout, sort_index, front.get("link"))
    for md_path, out_html, title, layout, sort_index, front, *rest in all_files
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

  if base_url:
    expected_html.add(output_dir / "sitemap.xml")
    expected_html.add(output_dir / "feed.xml")
  if search_enabled:
    expected_html.add(output_dir / "search.json")

  return nav_pages, tag_out_paths, posts_out_path, has_posts_listing, expected_html, posts_collision


def _init_manifest(incremental: bool, manifest_path: Optional[Path], theme_dir: Path, config_path: Optional[Path]) -> tuple[dict, float, float]:
  """Load manifest and mtimes for rebuild detection."""
  manifest = load_build_manifest(manifest_path) if (incremental and manifest_path) else {}
  template_mtime, config_mtime = _load_mtimes(theme_dir, config_path)
  return manifest, template_mtime, config_mtime


def _run_build(root: Path, output_dir: Path, site_name: str,
       template, theme_dir: Path,
       base_url: str = "", incremental: bool = False,
       manifest_path: Optional[Path] = None,
       dry_run: bool = False,
       posts_label: str = "Blog",
       config_path: Optional[Path] = None,
       sanitize: bool = False,
       timezone: Optional[str] = None,
       search_enabled: bool = True,
       sidebar_side: str = "right") -> tuple[int, int, int]:
  """Run a full site build."""

  output_dir = output_dir.resolve()
  manifest, template_mtime, config_mtime = _init_manifest(incremental, manifest_path, theme_dir, config_path)

  files = find_markdown_files(root)
  if files:
    print(f"Found {len(files)} Markdown file(s)\n")

  all_files, drafts, tags_map, dated_pages, search_entries = _collect_all_pages(
    files, root, output_dir, timezone, manifest=manifest, incremental=incremental
  )

  nav_pages, tag_out_paths, posts_out_path, has_posts_listing, expected_html, posts_collision = _plan_outputs(
    all_files, root, output_dir, tags_map, dated_pages, base_url, search_enabled
  )

  nav_posts_out = posts_out_path if has_posts_listing else None

  stale_removed: list[Path] = []
  if not dry_run:
    stale_removed = _prepare_output(
      output_dir, theme_dir, root, expected_html,
      base_url=base_url, search_enabled=search_enabled,
    )

  errors = 0
  recent_posts = [
    (out_path, title)
    for out_path, title, date_dt, desc in sorted(dated_pages, key=lambda t: t[2], reverse=True)[:5]
  ] if dated_pages else []

  nav_sig = compute_nav_signature(
    nav_pages, posts_out=nav_posts_out, recent_posts=recent_posts,
    posts_label=posts_label,
  ) if (nav_pages or nav_posts_out) else ""

  ctx = BuildContext(
    site_name=site_name,
    base_url=base_url,
    output_dir=output_dir,
    posts_out=nav_posts_out,
    posts_label=posts_label,
    recent_posts=recent_posts,
    sanitize=sanitize,
    timezone=timezone,
    search_enabled=search_enabled,
    sidebar_side=sidebar_side,
    template=template,
    resolved_root_index=output_dir / "index.html",
  )

  tasks, ok, skipped = _prepare_tasks(
    all_files, root, theme_dir, ctx, nav_pages,
    incremental, manifest, manifest_path, template_mtime,
    config_mtime, nav_sig, dry_run,
  )

  if tasks:
    for fn, args, rel, md_hash, md_path in tasks:
      try:
        out = fn(*args)
        print(f"  ✓  {rel}  →  {out}")
        ok += 1
        if incremental and manifest_path is not None:
          manifest[str(md_path)] = md_hash
      except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"  ✗  {rel}  →  ERROR: {exc}")
        errors += 1

  if dry_run:
    _print_dry_run_auxiliary(tags_map, tag_out_paths, has_posts_listing, posts_out_path)
    return ok, errors, skipped

  # ── Generate tag indices, posts listing, and sidecar files ─────────────
  lastmod_dates: Optional[list[tuple[str, str]]] = None
  if base_url:
    lastmod_dates = []
    for entry in all_files:
      md_path, out_html = entry[0], entry[1]
      md_mtime = entry[8] if len(entry) > 8 else 0.0
      if md_mtime > 0.0:
        d_str = datetime.fromtimestamp(md_mtime).strftime("%Y-%m-%d")
      else:
        d_str = datetime.now().strftime("%Y-%m-%d")
      lastmod_dates.append((str(out_html), d_str))

  aux_sig = compute_aux_signature(
    tags_map, dated_pages, search_entries, base_url,
    posts_label, search_enabled, site_name, sidebar_side,
    nav_sig=nav_sig, timezone=timezone, lastmod_dates=lastmod_dates,
  )
  aux_up_to_date = (
    incremental
    and not stale_removed
    and template_mtime <= manifest.get(_MANIFEST_TEMPLATE_KEY, 0.0)
    and config_mtime <= manifest.get(_MANIFEST_CONFIG_KEY, 0.0)
    and (not nav_sig or manifest.get(_MANIFEST_NAV_KEY) == nav_sig)
    and manifest.get(_MANIFEST_AUX_KEY) == aux_sig
    and all(p.exists() for p in expected_html)
  )
  if not aux_up_to_date:
    errors += _generate_auxiliary_pages(
      tags_map, tag_out_paths, nav_pages, has_posts_listing,
      posts_out_path, dated_pages, posts_collision, all_files,
      search_entries, ctx,
    )

  if incremental and manifest_path is not None:
    active_keys = {str(entry[0]) for entry in all_files}
    pruned_manifest: dict = {
      k: v for k, v in manifest.items()
      if k in active_keys or k.startswith("_")
    }
    pruned_manifest[_MANIFEST_TEMPLATE_KEY] = template_mtime
    pruned_manifest[_MANIFEST_CONFIG_KEY] = config_mtime
    pruned_manifest[_MANIFEST_NAV_KEY] = nav_sig
    pruned_manifest[_MANIFEST_AUX_KEY] = aux_sig
    save_build_manifest(manifest_path, pruned_manifest)

  if not dry_run:
    draft_note = f", {drafts} draft(s) skipped" if drafts else ""
    skip_note = f", {skipped} skipped (unchanged)" if skipped else ""
    print(f"\nDone.  {ok} converted{skip_note}{draft_note}, {errors} errors.")

  return ok, errors, skipped
