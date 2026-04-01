"""app — internal package for hanma.py.

Re-exports every public symbol so that tests can do:
  import app as hanma
  hanma.extract_title(...)
  hanma._THEMES_DIR = tmp_path / "themes"   # monkey-patch supported
"""

from pathlib import Path

# ── Version ───────────────────────────────────────────────────────────────────
__version__ = "0.6.0"

# ── _THEMES_DIR: defined here so tests can monkey-patch app._THEMES_DIR
# and load_theme() (defined below) picks it up at call time. ──────────────────
_THEMES_DIR = Path(__file__).parent.parent / "themes"

# ── Re-exports ────────────────────────────────────────────────────────────────
from app.config import load_site_config
from app.highlight import HIGHLIGHT_CSS, _build_highlight_css
from app.parsing import (
  parse_front_matter, extract_title, extract_description, collect_page_info,
)
from app.nav import build_nav_html
from app.theme import _load_theme_impl, copy_theme_assets
from app.files import find_markdown_files, copy_static_assets, clean_stale_html
from app.pages import (
  _normalize_tag, _search_json_url,
  _make_generated_page, build_tag_index_html, build_posts_listing_html,
)
from app.sidecar import build_sitemap_xml, build_search_json
from app.manifest import (
  load_build_manifest, save_build_manifest, page_needs_rebuild,
  _MANIFEST_TEMPLATE_KEY, _MANIFEST_CONFIG_KEY,
)
from app.convert import convert_md_to_html
from app.build import _run_build
from app.watch import (
  _HanmaEventHandler, _watch_polling, watch_and_rebuild, _WATCHDOG_AVAILABLE,
)
from app.scaffold import _SCAFFOLD_FILES, init_scaffold
from app.cli import main, _serve


def load_theme(name: str) -> tuple:
  """Load theme by name, reading _THEMES_DIR at call time.

  Defined here (not in theme.py) so that tests can monkey-patch
  app._THEMES_DIR and have load_theme() honour the patched value.
  """
  return _load_theme_impl(name, _THEMES_DIR)
