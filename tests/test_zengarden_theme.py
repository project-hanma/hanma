# test_zengarden_theme.py — Tests for the Zen Garden theme.
# Copyright (C) 2026  Chris Hammer

import sys
from pathlib import Path
import pytest

from tests.helpers import run_hanma, write_file

# Add project root to sys.path and import app
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(_PROJECT_ROOT))
import app as hanma


def test_list_themes_contains_zengarden():
  # Test --list-themes includes zengarden
  result = run_hanma("--list-themes")
  assert "zengarden" in result.stdout.lower()


def test_zengarden_rendered_layout(tmp_path):
  # Test compilation using zengarden
  write_file(tmp_path / "index.md", "---\ntitle: Zen Garden Home\n---\nWelcome to the dry landscape!")
  
  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: zengarden\nname: Zen Test Site\n", encoding="utf-8")
  
  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))
  
  index_html = (out_dir / "index.html").read_text(encoding="utf-8")
  
  # Check for our zen garden classes and features
  assert 'class="zen-wrapper"' in index_html
  assert 'class="zen-header"' in index_html
  assert 'class="zen-logo"' in index_html
  assert 'class="zen-nav"' in index_html
  assert 'class="zen-main-container"' in index_html
  assert 'class="zen-footer"' in index_html
  assert 'class="shoji-accent left"' in index_html
  
  # Check scripts exist in output
  assert (out_dir / "assets" / "scripts" / "theme-init.js").exists()
  assert (out_dir / "assets" / "scripts" / "theme-toggle.js").exists()
  assert (out_dir / "assets" / "scripts" / "search.js").exists()
  assert (out_dir / "assets" / "css" / "style.css").exists()
  
  # Check script paths in output HTML
  assert 'assets/scripts/theme-init.js' in index_html
  assert 'assets/scripts/theme-toggle.js' in index_html
