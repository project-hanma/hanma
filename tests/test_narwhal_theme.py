# test_narwhal_theme.py — Tests for the classic old-reddit-inspired Narwhal theme and configuration.
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

def test_sidebar_side_in_config(tmp_path):
  # 1. Test sidebar_side configuration is parsed
  config_file = tmp_path / "hanma.yaml"
  
  # Default case: no sidebar_side specified
  config_file.write_text("theme: narwhal\n", encoding="utf-8")
  config = hanma.load_site_config(config_file)
  assert config.get("theme") == "narwhal"
  assert "sidebar_side" not in config

  # Case: sidebar_side left
  config_file.write_text("theme: narwhal\nsidebar_side: left\n", encoding="utf-8")
  config = hanma.load_site_config(config_file)
  assert config.get("sidebar_side") == "left"

  # Case: sidebar_side right
  config_file.write_text("theme: narwhal\nsidebar_side: right\n", encoding="utf-8")
  config = hanma.load_site_config(config_file)
  assert config.get("sidebar_side") == "right"


def test_list_themes_contains_narwhal():
  # 2. Test --list-themes includes narwhal
  result = run_hanma("--list-themes")
  assert "narwhal" in result.stdout.lower()


def test_narwhal_rendered_layout_side_right(tmp_path):
  # 3. Test compilation using narwhal with sidebar_side: right
  write_file(tmp_path / "index.md", "---\ntitle: Home Page\n---\nWelcome to Narwhal!")
  
  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: narwhal\nsidebar_side: right\nname: Narwhal Test Site\n", encoding="utf-8")
  
  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))
  
  index_html = (out_dir / "index.html").read_text(encoding="utf-8")
  
  # The output html should render with "sidebar-right" class
  assert 'class="narwhal-container sidebar-right"' in index_html
  assert 'class="narwhal-container sidebar-left"' not in index_html
  
  # Check layout elements
  assert 'class="narwhal-sidebar"' in index_html
  assert 'class="sidebar-box search-box"' in index_html
  assert 'class="sidebar-box nav-box"' in index_html
  
  # Check scripts exist in output
  assert (out_dir / "assets" / "scripts" / "theme-init.js").exists()
  assert (out_dir / "assets" / "scripts" / "theme-toggle.js").exists()
  assert (out_dir / "assets" / "scripts" / "search.js").exists()
  assert (out_dir / "assets" / "css" / "style.css").exists()
  
  # Check theme-init.js is in <head> and other scripts are at bottom
  assert 'scripts/theme-init.js' in index_html
  assert 'scripts/theme-toggle.js' in index_html
  assert 'scripts/search.js' in index_html


def test_narwhal_rendered_layout_side_left(tmp_path):
  # 4. Test compilation using narwhal with sidebar_side: left
  write_file(tmp_path / "index.md", "---\ntitle: Home Page\n---\nWelcome to Narwhal!")
  
  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: narwhal\nsidebar_side: left\nname: Narwhal Test Site\n", encoding="utf-8")
  
  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))
  
  index_html = (out_dir / "index.html").read_text(encoding="utf-8")
  
  # The output html should render with "sidebar-left" class
  assert 'class="narwhal-container sidebar-left"' in index_html
  assert 'class="narwhal-container sidebar-right"' not in index_html


def test_narwhal_auxiliary_pages_contain_sidebar_side(tmp_path):
  # 5. Test generated auxiliary pages (tags, blog lists) also contain the configured sidebar layout class.
  write_file(tmp_path / "index.md", "---\ntitle: Home Page\n---\nWelcome.")
  
  # Add some posts with tags
  write_file(tmp_path / "posts" / "hello.md", "---\ntitle: Hello World\nlayout: post\ntags:\n  - python\n  - web\n---\nHello.")
  
  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: narwhal\nsidebar_side: left\nname: Narwhal Test Site\n", encoding="utf-8")
  
  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))
  
  # Check posts index/listing page
  posts_index = (out_dir / "posts" / "index.html").read_text(encoding="utf-8")
  assert 'class="narwhal-container sidebar-left"' in posts_index
  
  # Check tag page
  tag_python = (out_dir / "tags" / "python.html").read_text(encoding="utf-8")
  assert 'class="narwhal-container sidebar-left"' in tag_python
