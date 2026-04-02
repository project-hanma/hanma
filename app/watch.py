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
import threading
import time
from pathlib import Path
from typing import Optional

from app.build import _run_build
from app.files import find_markdown_files

try:
  from watchdog.observers import Observer
  from watchdog.events import FileSystemEventHandler as _WatchdogHandler
  _WATCHDOG_AVAILABLE = True
except ImportError:
  _WATCHDOG_AVAILABLE = False
  _WatchdogHandler = object  # fallback base class


class _HanmaEventHandler(_WatchdogHandler):
  """Watchdog event handler: triggers a debounced rebuild on any relevant change."""

  _RELEVANT_SUFFIXES = {".md", ".markdown", ".yaml", ".css", ".js"}

  def __init__(self, rebuild_fn, theme_dir: Path, output_dir: Optional[Path] = None) -> None:
    super().__init__()
    self._rebuild = rebuild_fn
    self._theme_dir = theme_dir
    self._output_dir = output_dir
    self._lock = threading.Lock()
    self._debounce_timer: Optional[threading.Timer] = None

  def _is_relevant(self, path: str) -> bool:
    p = Path(path)
    if self._output_dir and p.is_relative_to(self._output_dir):
      return False
    return p.suffix.lower() in self._RELEVANT_SUFFIXES

  def _schedule_rebuild(self) -> None:
    with self._lock:
      if self._debounce_timer is not None:
        self._debounce_timer.cancel()
      self._debounce_timer = threading.Timer(0.3, self._rebuild)
      self._debounce_timer.start()

  _TRIGGER_TYPES = {"created", "deleted", "modified", "moved"}

  def on_any_event(self, event) -> None:
    if getattr(event, "is_directory", False):
      return
    if getattr(event, "event_type", None) not in self._TRIGGER_TYPES:
      return
    src = getattr(event, "src_path", "")
    if self._is_relevant(src):
      self._schedule_rebuild()


def _watch_polling(root: Path, output_dir: Path, site_name: str,
         template: string.Template, theme_dir: Path,
         base_url: str = "", poll_interval: float = 1.0,
         posts_label: str = "Blog",
         config_path: Optional[Path] = None) -> None:
  """Fallback polling-based watch (used when watchdog is not available)."""
  print(f"Watching {root} for changes (polling, Ctrl+C to stop)...\n")

  def get_mtimes(file_list: list) -> dict:
    mtimes = {}
    for p in file_list:
      try:
        mtimes[p] = p.stat().st_mtime
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
      deleted = set(files) - set(current_files)
      changed = [p for p in current_files
           if current_mtimes.get(p) != last_mtimes.get(p)]
      if changed or deleted:
        print(f"\n  [watch] change detected, rebuilding...")
        _run_build(root, output_dir, site_name, template, theme_dir,
             base_url=base_url, posts_label=posts_label,
             config_path=config_path)
      last_mtimes = current_mtimes
      files = current_files
  except KeyboardInterrupt:
    print("\nWatch stopped.")


def watch_and_rebuild(root: Path, output_dir: Path, site_name: str,
           template: string.Template, theme_dir: Path,
           base_url: str = "",
           poll_interval: float = 1.0,
           posts_label: str = "Blog",
           config_path: Optional[Path] = None) -> None:
  """Watch source files and regenerate on changes.

  Uses watchdog (inotify/FSEvents/kqueue) when available; falls back to
  polling when watchdog is not installed.
  """
  if not _WATCHDOG_AVAILABLE:
    _watch_polling(root, output_dir, site_name, template, theme_dir,
           base_url=base_url, poll_interval=poll_interval,
           posts_label=posts_label, config_path=config_path)
    return

  def rebuild():
    print(f"\n  [watch] change detected, rebuilding...")
    try:
      _run_build(root, output_dir, site_name, template, theme_dir,
           base_url=base_url, posts_label=posts_label,
           config_path=config_path)
    except Exception as exc:
      print(f"  [watch] build error: {exc}")

  handler = _HanmaEventHandler(rebuild, theme_dir, output_dir=output_dir)
  observer = Observer()
  observer.schedule(handler, str(root), recursive=True)
  # Only schedule theme_dir separately when it lives outside the source tree.
  # If theme_dir is nested under root the recursive watch above already covers it.
  if theme_dir != root and not theme_dir.is_relative_to(root):
    observer.schedule(handler, str(theme_dir), recursive=True)
  observer.start()
  print(f"Watching {root} for changes (Ctrl+C to stop)...\n")
  try:
    while observer.is_alive():
      observer.join(timeout=1.0)
  except KeyboardInterrupt:
    observer.stop()
  observer.join()
  print("\nWatch stopped.")
