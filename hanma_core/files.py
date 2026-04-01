import shutil
import sys
from pathlib import Path


def find_markdown_files(root: Path) -> list[Path]:
  """Recursively find all .md and .markdown files under root.

  Skips any path whose components include a dotfile/dotdir (e.g. .venv).
  """
  IGNORE_NAMES = {"README.md", "README.markdown", "readme.md", "readme.markdown"}

  def has_dotpart(p: Path) -> bool:
    return any(part.startswith(".") for part in p.relative_to(root).parts)

  return sorted(
    p for p in root.rglob("*")
    if p.suffix.lower() in {".md", ".markdown"}
    and p.is_file()
    and not has_dotpart(p)
    and p.name not in IGNORE_NAMES
  )


def copy_static_assets(source_root: Path, output_root: Path) -> None:
  """Copy <source_root>/static/ to <output_root>/static/ unchanged.

  Does nothing if no static/ directory exists in source_root.
  """
  static_src = source_root / "static"
  if not static_src.is_dir():
    return
  static_dest = output_root / "static"
  if static_dest.exists():
    shutil.rmtree(static_dest)
  shutil.copytree(static_src, static_dest)
  count = sum(1 for _ in static_dest.rglob("*") if _.is_file())
  print(f"  [static] copied {count} file(s) from static/")


def clean_stale_html(output_dir: Path, expected_html: set[Path]) -> list[Path]:
  """Remove .html files in output_dir that have no corresponding source page.

  expected_html is the set of output paths that should exist after generation.
  Returns the list of paths that were removed.
  """
  removed = []
  for html_file in sorted(output_dir.rglob("*.html")):
    if html_file not in expected_html:
      try:
        html_file.unlink()
        removed.append(html_file)
        # Remove empty parent directories up to output_dir
        parent = html_file.parent
        while parent != output_dir:
          try:
            parent.rmdir()  # only removes if empty
            parent = parent.parent
          except OSError:
            break
      except OSError as exc:
        print(f"  [clean] warning: could not remove {html_file}: {exc}", file=sys.stderr)
  return removed
