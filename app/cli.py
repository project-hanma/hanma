import argparse
import sys
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

from app.build import _run_build
from app.config import load_site_config
from app.convert import convert_md_to_html
from app.scaffold import init_scaffold
from app.theme import _load_theme_impl, copy_theme_assets
from app.watch import watch_and_rebuild
from app._version import __version__

# Anchor for themes/ and conf/ — same directory as hanma.py since all files are siblings
_PROJECT_ROOT = Path(__file__).parent.parent
_THEMES_DIR = _PROJECT_ROOT / "themes"
_CONF_DIR = _PROJECT_ROOT / "conf"


def main() -> None:
  if sys.version_info < (3, 10):
    sys.exit("Error: hanma.py requires Python 3.10 or later.")

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
  args = parser.parse_args()

  print(f"hanma {__version__} — It builds your blog. That's mostly it.\n")

  if args.list_themes:
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
    return

  if args.init:
    site_dir = Path("site").resolve()
    init_scaffold(site_dir, force=args.force)
    return

  # ── Resolve default path: prefer ./site/, fall back to cwd ──────────────
  if args.path is None:
    site_dir = Path("site").resolve()
    if site_dir.is_dir():
      raw_path = site_dir
    else:
      raw_path = Path(".").resolve()
  else:
    raw_path = Path(args.path).resolve()

  target = raw_path

  # ── Resolve the list of files and a display root ───────────────────────
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

  # ── Load site config (hanma.yml / hanma.yaml) ────────────────────────────
  # Lookup order: --config flag > conf/hanma.yml (next to hanma.py) > hanma.yml in source root
  #               > hanma.yaml in source root (legacy fallback)
  def _find_default_config(base: Path) -> Path:
    for name in ("hanma.yml", "hanma.yaml"):
      p = base / name
      if p.is_file():
        return p
    return base / "hanma.yml"  # non-existent sentinel; load_site_config returns {}

  if args.config is not None:
    config_path = Path(args.config).resolve()
  else:
    default_conf = _find_default_config(_CONF_DIR)
    config_path = default_conf if default_conf.is_file() else _find_default_config(root)
  site_config = load_site_config(config_path)

  # ── Merge CLI args with config (CLI always wins) ───────────────────────
  site_name   = args.name     if args.name     is not None else site_config.get("name",   "Blog")
  theme_name  = args.theme    if args.theme    is not None else site_config.get("theme",  "default")
  base_url    = args.base_url if args.base_url is not None else site_config.get("base_url", "")
  output_arg  = args.output   if args.output   is not None else site_config.get("output", None)
  posts_label = str(site_config.get("posts_label", "Blog"))

  # Boolean/int flags: CLI flag presence overrides config; config overrides built-in default
  # --serve is a nargs="?" int (None = not passed, 8000 = passed without value)
  cfg_serve       = site_config.get("serve",       False)
  cfg_port        = site_config.get("port",        8000)
  cfg_watch       = site_config.get("watch",       False)
  cfg_incremental = site_config.get("incremental", False)

  # Resolve effective serve port: explicit --serve N > --port N > config port > 8000
  if args.serve is not None:
    effective_serve = True
    effective_port  = args.serve if args.serve != 8000 else args.port
  elif cfg_serve:
    effective_serve = True
    effective_port  = cfg_port
  else:
    effective_serve = False
    effective_port  = args.port if args.port != 8000 else cfg_port

  effective_watch       = args.watch       or cfg_watch
  effective_incremental = args.incremental or cfg_incremental

  # ── Resolve output directory ───────────────────────────────────────────
  if output_arg:
    output_dir = Path(output_arg).resolve()
  else:
    output_dir = (_PROJECT_ROOT / "output").resolve()

  if target.is_dir() and output_dir.is_relative_to(root):
    print(f"Warning: output directory '{output_dir}' is inside the source directory '{root}'.")
    print("  This will mix generated HTML with Markdown sources.")

  # ── Handle single-file target: redirect to _run_build indirectly ──────
  # For a single file, rebuild only that file; set root to its parent.
  if target.is_file():
    # Single-file mode: convert directly
    theme_template, theme_dir = _load_theme_impl(theme_name, _THEMES_DIR)
    out_html = output_dir / target.name.replace(target.suffix, ".html")
    if args.dry_run:
      print(f"  [dry-run] {target.name}  →  {out_html}")
      return
    out_html.parent.mkdir(parents=True, exist_ok=True)
    copy_theme_assets(theme_dir, output_dir)
    convert_md_to_html(target, out_html, site_name, nav_pages=[], template=theme_template)
    print(f"  ✓  {target.name}  →  {out_html}")
    print(f"\nDone.  1 converted, 0 errors.")
    if effective_serve:
      _serve(output_dir, effective_port)
    return

  # ── Load theme ────────────────────────────────────────────────────────
  theme_template, theme_dir = _load_theme_impl(theme_name, _THEMES_DIR)

  # ── Manifest path for incremental builds ─────────────────────────────
  manifest_path = output_dir / ".hanma_manifest.json" if effective_incremental else None

  # ── Run the build ─────────────────────────────────────────────────────
  print(f"Building '{site_name}'  →  {output_dir}\n")
  ok, errors, skipped = _run_build(
    root, output_dir, site_name, theme_template, theme_dir,
    base_url=base_url,
    incremental=effective_incremental,
    manifest_path=manifest_path,
    dry_run=args.dry_run,
    posts_label=posts_label,
    config_path=config_path,
  )

  if args.dry_run:
    return

  if effective_watch:
    if effective_serve:
      watch_thread = threading.Thread(
        target=watch_and_rebuild,
        args=(root, output_dir, site_name, theme_template, theme_dir),
        kwargs={"base_url": base_url, "posts_label": posts_label,
            "config_path": config_path},
        daemon=True,
      )
      watch_thread.start()
    else:
      watch_and_rebuild(root, output_dir, site_name, theme_template, theme_dir,
               base_url=base_url, posts_label=posts_label,
               config_path=config_path)
      return

  if effective_serve:
    print("\nStarting server…")
    _serve(output_dir, effective_port)


def _serve(serve_dir: Path, port: int) -> None:
  """Start a local HTTP server serving serve_dir."""

  index_html = serve_dir / "index.html"
  if index_html.is_file():
    open_url = f"http://localhost:{port}/index.html"
  else:
    # Fall back to the first HTML file found, or bare root
    html_files = sorted(serve_dir.rglob("*.html"))
    if html_files:
      try:
        rel_html = html_files[0].relative_to(serve_dir)
      except ValueError:
        rel_html = html_files[0]
      open_url = f"http://localhost:{port}/{rel_html.as_posix()}"
    else:
      open_url = f"http://localhost:{port}/"

  class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
      super().__init__(*a, directory=str(serve_dir), **kw)
    def log_message(self, fmt, *a):
      pass

  try:
    server = HTTPServer(("127.0.0.1", port), QuietHandler)
  except OSError as exc:
    if exc.errno == 98 or "already in use" in str(exc).lower():
      print(f"Error: port {port} is already in use. Try --port <other>")
    else:
      print(f"Error starting server: {exc}")
    sys.exit(1)
  print(f"\nServing at http://localhost:{port}/")
  print(f"Opening  {open_url}")
  print("Press Ctrl+C to stop.\n")

  threading.Timer(0.5, lambda: webbrowser.open(open_url)).start()
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    print("\nServer stopped.")
