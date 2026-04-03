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
"""app — internal package for hanma.py.

Re-exports every public symbol so that tests can do:
  import app as hanma
  hanma.extract_title(...)
  hanma._THEMES_DIR = tmp_path / "themes"   # monkey-patch supported
"""

from pathlib import Path

# ── Version ───────────────────────────────────────────────────────────────────
from app._version import __version__

# ── _THEMES_DIR: defined here so tests can monkey-patch app._THEMES_DIR
# and load_theme() (defined below) picks it up at call time. ──────────────────
_THEMES_DIR = Path(__file__).parent.parent / "themes"

# ── Re-exports ────────────────────────────────────────────────────────────────
from app.config import load_site_config
from app.highlight import HIGHLIGHT_CSS, _build_highlight_css
from app.parsing import (
  parse_front_matter, extract_title, extract_description, collect_page_info,
  parse_date_field,
)
from app.nav import build_nav_html
from app.theme import ThemeError, _load_theme_impl, copy_theme_assets
from app.files import find_markdown_files, copy_static_assets, clean_stale_html, POSTS_DIR_NAME
from app.pages import (
  _normalize_tag, _sitemap_link, _search_json_url,
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
