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
"""Command-line interface for the Hanma static site generator."""
import argparse
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

from app.build import _run_build
from app.config import load_site_config
from app.convert import convert_md_to_html
from app.scaffold import init_scaffold
from app.theme import ThemeError, _load_theme_impl, copy_theme_assets
from app.watch import watch_and_rebuild
from app._version import __version__
from app.utils import _THEMES_DIR

# Anchor for themes/ and conf/ — same directory as hanma.py since all files are siblings
_PROJECT_ROOT = Path(__file__).parent.parent
_CONF_DIR = _PROJECT_ROOT / "conf"

_NOT_SET = object()


def _create_parser() -> argparse.ArgumentParser:
  """Create and configure the argument parser."""
  parser = argparse.ArgumentParser(
    description="Convert Markdown files to HTML, recursively.",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
 ./hanma.py                                      # Process ./site/ (default, in-place)
 ./hanma.py site/sample.md                       # Convert a single file
 ./hanma.py site/                                # Explicit site directory (in-place)
 ./hanma.py site/ --output dist/                 # Write HTML to dist/, mirroring source tree
 ./hanma.py --name "My Blog" --serve             # Named site with local server
 ./hanma.py --output dist/ --serve               # Serve from output directory
 ./hanma.py --incremental                        # Only rebuild changed pages
    """,
  )
  parser.add_argument(
    "--version",
    action="version",
    version=f"hanma.py {__version__}",
  )
  parser.add_argument(
    "path",
    nargs="?",
    default=None,
    help="Markdown file or directory to convert (default: ./site/)",
  )
  parser.add_argument(
    "--name",
    default=None,
    metavar="SITE_NAME",
    help='Site name shown in the header (default: from hanma.yml or "Blog")',
  )
  parser.add_argument(
    "--base-url",
    default=None,
    metavar="URL",
    help="Base URL for sitemap.xml and search.json (e.g. https://example.com)",
  )
  parser.add_argument(
    "--dry-run",
    action="store_true",
    help="List files that would be converted without writing anything",
  )
  parser.add_argument(
    "--serve",
    nargs="?",
    const=8000,
    default=_NOT_SET,
    type=int,
    metavar="PORT",
    help="Start a local HTTP server after generating, optionally on PORT (default: 8000)",
  )
  parser.add_argument(
    "--output",
    default=None,
    metavar="DIR",
    help="Directory to write generated HTML files (default: output/ relative to hanma.py, not cwd)",
  )
  parser.add_argument(
    "--port",
    type=int,
    default=8000,
    metavar="PORT",
    help="Port for the local HTTP server (default: 8000)",
  )
  parser.add_argument(
    "--host",
    default=None,
    metavar="ADDR",
    help="Bind address for the local HTTP server (default: 127.0.0.1)",
  )
  parser.add_argument(
    "--watch",
    action="store_true",
    help="Watch source files and regenerate on changes after initial build",
  )
  parser.add_argument(
    "--theme",
    default=None,
    metavar="NAME",
    help='Theme to use from the themes/ directory (default: from hanma.yml or "default")',
  )
  parser.add_argument(
    "--list-themes",
    action="store_true",
    help="List available themes and exit",
  )
  parser.add_argument(
    "--incremental",
    action="store_true",
    help="Only regenerate pages whose source file has changed since last build",
  )
  parser.add_argument(
    "--sanitize",
    action="store_true",
    help="Sanitize the generated HTML using 'bleach' if available",
  )
  parser.add_argument(
    "--config",
    default=None,
    metavar="FILE",
    help="Path to config file (default: conf/hanma.yml next to hanma.py, then hanma.yml in source directory)",
  )
  parser.add_argument(
    "--init",
    action="store_true",
    help="Scaffold a new site with sample content in ./site/ and exit",
  )
  parser.add_argument(
    "--force",
    action="store_true",
    help="With --init: overwrite existing files in the target directory",
  )
  return parser


def _list_themes() -> None:
  """List available themes and exit."""
  if _THEMES_DIR.is_dir():
    themes = sorted(d.name for d in _THEMES_DIR.iterdir() if d.is_dir())
    if themes:
      print("Available themes:")
      for t in themes:
        print(f"  {t}")
    else:
      print("No themes found in themes/")
  else:
    print("No themes/ directory found")


def _init_scaffold_cmd(force: bool) -> None:
  """Scaffold a new site and exit."""
  site_dir = Path("site").resolve()
  try:
    init_scaffold(site_dir, force=force)
  except RuntimeError as exc:
    sys.exit(str(exc))


def _resolve_paths(args_path: Optional[str]) -> tuple[Path, Path]:
  """Resolve the source directory and target path."""
  if args_path is None:
    site_dir = Path("site").resolve()
    if site_dir.is_dir():
      raw_path = site_dir
    else:
      raw_path = Path(".").resolve()
  else:
    raw_path = Path(args_path).resolve()

  target = raw_path
  if target.is_file():
    if target.suffix.lower() not in {".md", ".markdown"}:
      print(f"Error: '{target}' is not a Markdown file (.md / .markdown).")
      sys.exit(1)
    root = target.parent
  elif target.is_dir():
    root = target
  else:
    print(f"Error: '{target}' is not a file or directory.")
    sys.exit(1)

  return root, target


def _get_config_path(args_config: Optional[str], root: Path) -> Path:
  """Determine the path to the configuration file."""
  def _find_default_config(base: Path) -> Path:
    for name in ("hanma.yml", "hanma.yaml"):
      p = base / name
      if p.is_file():
        return p
    return base / "hanma.yml"

  if args_config is not None:
    return Path(args_config).resolve()
  
  default_conf = _find_default_config(_CONF_DIR)
  if default_conf.is_file():
    return default_conf
  return _find_default_config(root)


def main() -> None:
  """Main entry point for the Hanma CLI tool."""
  if sys.version_info < (3, 10):
    sys.exit("Error: hanma.py requires Python 3.10 or later.")

  parser = _create_parser()
  args = parser.parse_args()

  print(f"hanma.py {__version__} — It builds your blog. That's mostly it.\n")

  if args.list_themes:
    _list_themes()
    return

  if args.init:
    _init_scaffold_cmd(args.force)
    return

  root, target = _resolve_paths(args.path)
  config_path = _get_config_path(args.config, root)
  site_config = load_site_config(config_path)
  settings = _get_effective_settings(args, site_config)

  if target.is_dir() and settings["output_dir"].is_relative_to(root):
    print(f"Warning: output directory '{settings['output_dir']}' is inside the source directory '{root}'.")
    print("  This will mix generated HTML with Markdown sources.")

  if target.is_file():
    _run_single_file_build(target, settings, args.dry_run)
    return

  _run_full_site_build(root, config_path, settings, args.dry_run)


def _get_effective_settings(args: argparse.Namespace, site_config: dict) -> dict:
  """Merge CLI args with config and return effective settings."""
  settings = {}
  settings["site_name"]   = args.name     if args.name     is not None else site_config.get("name",   "Blog")
  settings["theme_name"]  = args.theme    if args.theme    is not None else site_config.get("theme",  "default")
  settings["base_url"]    = args.base_url if args.base_url is not None else site_config.get("base_url", "")
  settings["output_arg"]  = args.output   if args.output   is not None else site_config.get("output", None)
  settings["posts_label"] = str(site_config.get("posts_label", "Blog"))
  settings["effective_timezone"] = site_config.get("timezone",    None)
  settings["sidebar_side"] = site_config.get("sidebar_side", "right")

  _apply_runtime_settings(settings, args, site_config)

  if settings["output_arg"]:
    settings["output_dir"] = Path(settings["output_arg"]).resolve()
  else:
    settings["output_dir"] = (_PROJECT_ROOT / "output").resolve()

  return settings


def _apply_runtime_settings(settings: dict, args: argparse.Namespace, site_config: dict) -> None:
  """Merge CLI args for serving, watching, and building."""
  cfg_serve       = site_config.get("serve",       False)
  cfg_port        = site_config.get("port",        8000)
  cfg_host        = site_config.get("host",        "127.0.0.1")
  cfg_watch       = site_config.get("watch",       False)
  cfg_incremental = site_config.get("incremental", False)
  cfg_search      = site_config.get("search",      True)
  cfg_sanitize    = site_config.get("sanitize",    False)

  if args.serve is not _NOT_SET:
    settings["effective_serve"] = True
    settings["effective_port"] = args.serve if args.serve is not None else 8000
  elif cfg_serve:
    settings["effective_serve"] = True
    settings["effective_port"]  = cfg_port
  else:
    settings["effective_serve"] = False
    settings["effective_port"]  = args.port if args.port != 8000 else cfg_port

  settings["effective_host"] = args.host if args.host is not None else cfg_host
  settings["effective_watch"]       = args.watch       or cfg_watch
  settings["effective_incremental"] = args.incremental or cfg_incremental
  settings["effective_search"]      = cfg_search
  settings["effective_sanitize"]    = args.sanitize    or cfg_sanitize


def _run_single_file_build(target: Path, settings: dict, dry_run: bool) -> None:
  """Convert a single Markdown file."""
  try:
    theme_template, theme_dir = _load_theme_impl(settings["theme_name"], _THEMES_DIR)
  except ThemeError as exc:
    print(f"Error: {exc}")
    sys.exit(1)
  
  out_html = settings["output_dir"] / target.name.replace(target.suffix, ".html")
  if dry_run:
    print(f"  [dry-run] {target.name}  →  {out_html}")
    return
  
  out_html.parent.mkdir(parents=True, exist_ok=True)
  copy_theme_assets(theme_dir, settings["output_dir"])
  convert_md_to_html(
    target, out_html, settings["site_name"], nav_pages=[], 
    template=theme_template, sanitize=settings["effective_sanitize"], 
    timezone=settings["effective_timezone"], search_enabled=settings["effective_search"],
    sidebar_side=settings["sidebar_side"]
  )
  print(f"  ✓  {target.name}  →  {out_html}")
  print("\nDone.  1 converted, 0 errors.")
  
  if settings["effective_serve"]:
    _serve(settings["output_dir"], settings["effective_port"], settings["effective_host"])


def _run_full_site_build(root: Path, config_path: Path, settings: dict, dry_run: bool) -> None:
  """Perform a full site build, potentially with watching and serving."""
  try:
    theme_template, theme_dir = _load_theme_impl(settings["theme_name"], _THEMES_DIR)
  except ThemeError as exc:
    print(f"Error: {exc}")
    sys.exit(1)

  manifest_path = settings["output_dir"] / ".hanma_manifest.json" if settings["effective_incremental"] else None

  print(f"Building '{settings['site_name']}'  →  {settings['output_dir']}\n")
  _run_build(
    root, settings["output_dir"], settings["site_name"], theme_template, theme_dir,
    base_url=settings["base_url"],
    incremental=settings["effective_incremental"],
    manifest_path=manifest_path,
    dry_run=dry_run,
    posts_label=settings["posts_label"],
    config_path=config_path,
    sanitize=settings["effective_sanitize"],
    timezone=settings["effective_timezone"],
    search_enabled=settings["effective_search"],
    sidebar_side=settings["sidebar_side"]
  )

  if dry_run:
    return

  if settings["effective_watch"]:
    watch_kwargs = {
      "base_url": settings["base_url"],
      "posts_label": settings["posts_label"],
      "config_path": config_path,
      "incremental": settings["effective_incremental"],
      "manifest_path": manifest_path,
      "sanitize": settings["effective_sanitize"],
      "timezone": settings["effective_timezone"],
      "search_enabled": settings["effective_search"],
    }
    if settings["effective_serve"]:
      watch_thread = threading.Thread(
        target=watch_and_rebuild,
        args=(root, settings["output_dir"], settings["site_name"], theme_template, theme_dir),
        kwargs=watch_kwargs,
        daemon=True,
      )
      watch_thread.start()
    else:
      watch_and_rebuild(root, settings["output_dir"], settings["site_name"], theme_template, theme_dir,
               **watch_kwargs)
      return

  if settings["effective_serve"]:
    print("\nStarting server…")
    _serve(settings["output_dir"], settings["effective_port"], settings["effective_host"])


class QuietHandler(SimpleHTTPRequestHandler):
  """Custom HTTP handler that validates paths and restricts logging."""
  def __init__(self, *a, **kw):
    # Retrieve directory from the server object (which is passed as the third positional argument)
    # to work around HTTPServer instantiating the handler without passing a directory kwarg.
    if len(a) > 2 and hasattr(a[2], 'directory'):
      kw['directory'] = a[2].directory
    super().__init__(*a, **kw)

  def list_directory(self, path):
    """Override list_directory to block directory indexing and return a clean 404."""
    self.send_error(404, "File not found")
    return None

  def translate_path(self, path):
    """Map URL to physical path and ensure it stays within serve_dir."""
    # Get the default translation
    fs_path = super().translate_path(path)
    
    # Resolve to absolute physical path (follows symlinks)
    try:
      resolved = Path(fs_path).resolve()
    except Exception:
      # If resolution fails, return an empty string to trigger 404
      return ""
        
    # Ensure the resolved path is strictly within the serving directory.
    # self.server.directory is set by SimpleHTTPRequestHandler
    serve_dir = Path(self.directory).resolve()
    if not resolved.is_relative_to(serve_dir):
      # Attempted directory traversal via symlink or other means
      return "/dev/null/non-existent"
        
    return str(resolved)

  def log_message(self, format, *args):  # pylint: disable=redefined-builtin
    """Only log errors (status code >= 400) to keep logs clean."""
    if len(args) > 1:
      try:
        code = int(args[1])
        if code >= 400:
          super().log_message(format, *args)
      except (ValueError, IndexError):
        pass


def _serve(serve_dir: Path, port: int, host: str = "127.0.0.1") -> None:
  """Start a local HTTP server serving serve_dir."""
  try:
    server = HTTPServer((host, port), QuietHandler)
    server.directory = str(serve_dir) # SimpleHTTPRequestHandler uses this
  except OSError as exc:
    if exc.errno == 98 or "already in use" in str(exc).lower():
      print(f"Error: port {port} is already in use. Try --port <other>")
    else:
      print(f"Error starting server: {exc}")
    sys.exit(1)
  print(f"\nServing at http://{host}:{port}/")
  print("Press Ctrl+C to stop.\n")

  try:
    server.serve_forever()
  except KeyboardInterrupt:
    print("\nServer stopped.")
