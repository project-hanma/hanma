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
"""File watching and auto-rebuild functionality for Hanma."""
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

from app.build import _run_build
from app.config import load_site_config, validate_base_url
from app.files import find_markdown_files
from app.theme import ThemeError, _load_theme_impl

try:
  from watchdog.observers import Observer
  from watchdog.events import FileSystemEventHandler as _WatchdogHandler
  _WATCHDOG_AVAILABLE = True
except ImportError:
  _WATCHDOG_AVAILABLE = False
  _WatchdogHandler = object  # type: ignore # fallback base class


class _HanmaEventHandler(_WatchdogHandler):
  """Watchdog event handler: triggers a debounced rebuild on any relevant change."""

  _RELEVANT_SUFFIXES = {".md", ".markdown", ".yaml", ".yml", ".css", ".js"}
  _TRIGGER_TYPES = {"created", "deleted", "modified", "moved"}

  def __init__(self, rebuild_fn, source_root: Path, theme_dir: Path,
               output_dir: Optional[Path] = None,
               config_path: Optional[Path] = None) -> None:
    super().__init__()
    self._rebuild = rebuild_fn
    self._source_root = source_root.resolve()
    self._theme_dir = theme_dir.resolve()
    self._output_dir = output_dir.resolve() if output_dir else None
    self._config_path = config_path.resolve() if config_path else None
    self._lock = threading.Lock()
    self._debounce_timer: Optional[threading.Timer] = None

  def set_theme_dir(self, theme_dir: Path) -> None:
    """Update the active theme directory tracked by this handler."""
    self._theme_dir = theme_dir.resolve()

  def _is_hidden(self, path: Path) -> bool:
    """Check if the path or any of its parents (relative to roots) is hidden."""
    try:
      p = path.resolve()
      if p.is_relative_to(self._source_root):
        rel = p.relative_to(self._source_root)
        return any(part.startswith(".") for part in rel.parts)
      if p.is_relative_to(self._theme_dir):
        rel = p.relative_to(self._theme_dir)
        return any(part.startswith(".") for part in rel.parts)
    except (ValueError, OSError):
      pass
    return False

  def _is_relevant(self, path: str) -> bool:
    p = Path(path)
    is_template = p.name == "template.html"
    is_config_name = bool(self._config_path and p.name == self._config_path.name)
    if not is_template and not is_config_name and p.suffix.lower() not in self._RELEVANT_SUFFIXES:
      return False
    try:
      resolved = p.resolve()
    except OSError:
      return False
    if self._output_dir and resolved.is_relative_to(self._output_dir):
      return False
    if self._config_path and resolved == self._config_path:
      return True
    if self._is_hidden(resolved):
      return False
    if is_template:
      return resolved.is_relative_to(self._theme_dir)
    return True

  def _schedule_rebuild(self) -> None:
    with self._lock:
      if self._debounce_timer is not None:
        self._debounce_timer.cancel()
      self._debounce_timer = threading.Timer(0.3, self._rebuild)
      self._debounce_timer.start()

  def _is_empty_file(self, path: Path) -> bool:
    try:
      return path.stat().st_size == 0
    except OSError:
      return True

  def on_any_event(self, event) -> None:
    if getattr(event, "event_type", None) not in self._TRIGGER_TYPES:
      return

    src = getattr(event, "src_path", "")
    
    # Always ignore output directory
    try:
      src_path = Path(src)
      if self._output_dir and src_path.resolve().is_relative_to(self._output_dir):
        return
    except (ValueError, OSError):
      pass

    # For directories: trigger on deletion, or move
    if getattr(event, "is_directory", False):
      if event.event_type in {"deleted", "moved"} and not self._is_hidden(src_path):
        self._schedule_rebuild()
      # Skip "created" for directories to avoid building empty folders
      return

    # For files
    if self._is_relevant(src):
      if event.event_type in {"created", "modified"} and self._is_empty_file(src_path):
        return
      self._schedule_rebuild()
    elif event.event_type == "moved":
      dest = getattr(event, "dest_path", "")
      if dest and self._is_relevant(dest) and not self._is_empty_file(Path(dest)):
        self._schedule_rebuild()


def _reload_watch_settings(config_path: Optional[Path], state: dict[str, Any],
                           themes_dir: Path, cli_overrides: dict) -> dict[str, Any]:
  """Reload hanma.yml and active theme safely, preserving CLI overrides and path boundaries."""
  updated = dict(state)
  theme_reloaded = False

  if config_path and config_path.is_file():
    cfg = load_site_config(config_path)
    if cfg:
      if not cli_overrides.get("name") and "name" in cfg and cfg["name"] is not None:
        updated["site_name"] = cfg["name"]
      if not cli_overrides.get("base_url") and "base_url" in cfg:
        try:
          updated["base_url"] = validate_base_url(cfg["base_url"] or "")
        except ValueError as exc:
          print(f"Warning: {exc} Keeping previous base_url.", file=sys.stderr)
      if "posts_label" in cfg and cfg["posts_label"] is not None:
        updated["posts_label"] = str(cfg["posts_label"])
      updated["incremental"] = bool(cli_overrides.get("incremental") or cfg.get("incremental", updated["incremental"]))
      updated["sanitize"] = bool(cli_overrides.get("sanitize") or cfg.get("sanitize", updated["sanitize"]))
      if "timezone" in cfg:
        updated["timezone"] = cfg["timezone"]
      if "search" in cfg:
        updated["search_enabled"] = bool(cfg["search"])
      if "sidebar_side" in cfg and cfg["sidebar_side"] is not None:
        raw_side = str(cfg["sidebar_side"]).strip().lower()
        if raw_side in {"left", "right"}:
          updated["sidebar_side"] = raw_side
      cfg_theme = cfg.get("theme")
      if not cli_overrides.get("theme") and isinstance(cfg_theme, str) and cfg_theme.strip():
        try:
          new_tpl, new_dir = _load_theme_impl(cfg_theme.strip(), themes_dir)
          updated["template"] = new_tpl
          updated["theme_dir"] = new_dir
          theme_reloaded = True
        except ThemeError as exc:
          print(f"Warning: invalid theme in config during watch reload: {exc}", file=sys.stderr)

  if not theme_reloaded:
    active_theme_dir: Path = updated["theme_dir"]
    if (active_theme_dir / "template.html").is_file():
      try:
        updated["template"], _ = _load_theme_impl(active_theme_dir.name, themes_dir)
      except (ThemeError, OSError):
        pass

  return updated


def _watch_polling(root: Path, output_dir: Path, site_name: str,
         template, theme_dir: Path,
         base_url: str = "", poll_interval: float = 1.0,
         posts_label: str = "Blog",
         config_path: Optional[Path] = None,
         incremental: bool = False,
         manifest_path: Optional[Path] = None,
         sanitize: bool = False,
         timezone: Optional[str] = None,
         search_enabled: bool = True,
         sidebar_side: str = "right",
         cli_overrides: Optional[dict] = None) -> None:
  """Fallback polling-based watch (used when watchdog is not available)."""
  print(f"Watching {root} for changes (polling, Ctrl+C to stop)...\n")
  themes_dir = theme_dir.parent.resolve()
  overrides = cli_overrides or {}
  state: dict[str, Any] = {
    "site_name": site_name,
    "base_url": base_url,
    "posts_label": posts_label,
    "incremental": incremental,
    "sanitize": sanitize,
    "timezone": timezone,
    "search_enabled": search_enabled,
    "sidebar_side": sidebar_side,
    "theme_dir": theme_dir,
    "template": template,
  }

  def get_mtimes(file_list: list[Path]) -> dict[Path, float]:
    mtimes: dict[Path, float] = {}
    for p in file_list:
      try:
        mtimes[p] = p.stat().st_mtime
      except OSError:
        pass
    tpl_path = state["theme_dir"] / "template.html"
    try:
      if tpl_path.is_file():
        mtimes[tpl_path] = tpl_path.stat().st_mtime
    except OSError:
      pass
    if config_path:
      try:
        if config_path.is_file():
          mtimes[config_path] = config_path.stat().st_mtime
      except OSError:
        pass
    return mtimes

  files = find_markdown_files(root)
  last_mtimes = get_mtimes(files)

  try:
    while True:
      time.sleep(poll_interval)
      current_files = find_markdown_files(root)
      current_mtimes = get_mtimes(current_files)
      deleted = set(last_mtimes.keys()) - set(current_mtimes.keys())
      changed = [p for p in current_mtimes if current_mtimes.get(p) != last_mtimes.get(p)]
      if changed or deleted:
        print("\n  [watch] change detected, rebuilding...")
        state = _reload_watch_settings(config_path, state, themes_dir, overrides)
        _run_build(
          root, output_dir, state["site_name"], state["template"], state["theme_dir"],
          base_url=state["base_url"], posts_label=state["posts_label"],
          config_path=config_path,
          incremental=state["incremental"],
          manifest_path=manifest_path,
          sanitize=state["sanitize"],
          timezone=state["timezone"],
          search_enabled=state["search_enabled"],
          sidebar_side=state["sidebar_side"],
        )
        current_mtimes = get_mtimes(current_files)
      last_mtimes = current_mtimes
      files = current_files
  except KeyboardInterrupt:
    print("\nWatch stopped.")


def watch_and_rebuild(root: Path, output_dir: Path, site_name: str,
           template, theme_dir: Path,
           base_url: str = "",
           poll_interval: float = 1.0,
           posts_label: str = "Blog",
           config_path: Optional[Path] = None,
           incremental: bool = False,
           manifest_path: Optional[Path] = None,
           sanitize: bool = False,
           timezone: Optional[str] = None,
           search_enabled: bool = True,
           sidebar_side: str = "right",
           cli_overrides: Optional[dict] = None) -> None:
  """Watch source files and regenerate on changes.

  Uses watchdog (inotify/FSEvents/kqueue) when available; falls back to
  polling when watchdog is not installed.
  """
  if not _WATCHDOG_AVAILABLE:
    _watch_polling(
      root, output_dir, site_name, template, theme_dir,
      base_url=base_url, poll_interval=poll_interval,
      posts_label=posts_label, config_path=config_path,
      incremental=incremental, manifest_path=manifest_path,
      sanitize=sanitize, timezone=timezone,
      search_enabled=search_enabled,
      sidebar_side=sidebar_side,
      cli_overrides=cli_overrides,
    )
    return

  build_lock = threading.Lock()
  themes_dir = theme_dir.parent.resolve()
  overrides = cli_overrides or {}
  state: dict[str, Any] = {
    "site_name": site_name,
    "base_url": base_url,
    "posts_label": posts_label,
    "incremental": incremental,
    "sanitize": sanitize,
    "timezone": timezone,
    "search_enabled": search_enabled,
    "sidebar_side": sidebar_side,
    "theme_dir": theme_dir.resolve(),
    "template": template,
  }
  watched_dirs: set[Path] = set()
  observer = Observer()

  def _ensure_watched(directory: Path) -> None:
    resolved_dir = directory.resolve()
    if not resolved_dir.is_dir():
      return
    if any(resolved_dir == w or resolved_dir.is_relative_to(w) for w in watched_dirs):
      return
    observer.schedule(handler, str(resolved_dir), recursive=True)
    watched_dirs.add(resolved_dir)

  def rebuild():
    nonlocal state
    with build_lock:
      print("\n  [watch] change detected, rebuilding...")
      try:
        state = _reload_watch_settings(config_path, state, themes_dir, overrides)
        active_theme_dir: Path = state["theme_dir"]
        handler.set_theme_dir(active_theme_dir)
        _ensure_watched(active_theme_dir)
        _run_build(
          root, output_dir, state["site_name"], state["template"], active_theme_dir,
          base_url=state["base_url"], posts_label=state["posts_label"],
          config_path=config_path,
          incremental=state["incremental"],
          manifest_path=manifest_path,
          sanitize=state["sanitize"],
          timezone=state["timezone"],
          search_enabled=state["search_enabled"],
          sidebar_side=state["sidebar_side"],
        )
      except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"  [watch] build error: {exc}")

  handler = _HanmaEventHandler(
    rebuild, root, theme_dir, output_dir=output_dir, config_path=config_path
  )
  _ensure_watched(root)
  _ensure_watched(theme_dir)
  if config_path and config_path.parent.is_dir():
    _ensure_watched(config_path.parent)
  observer.start()
  print(f"Watching {root} for changes (Ctrl+C to stop)...\n")
  try:
    while observer.is_alive():
      observer.join(timeout=1.0)
  except KeyboardInterrupt:
    observer.stop()
  observer.join()
  print("\nWatch stopped.")
