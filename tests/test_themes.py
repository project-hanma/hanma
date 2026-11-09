# test_themes.py — Built-in theme layout and configuration tests (Narwhal, Glassmorphic, Zen Garden).
# Copyright (C) 2026  Chris Hammer

import sys
from pathlib import Path

from tests.helpers import run_hanma, write_file

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(_PROJECT_ROOT))
import app as hanma


# ---------------------------------------------------------------------------
# 1. Narwhal Theme & sidebar_side Configuration
# ---------------------------------------------------------------------------

def test_sidebar_side_in_config(tmp_path):
  config_file = tmp_path / "hanma.yaml"

  config_file.write_text("theme: narwhal\n", encoding="utf-8")
  config = hanma.load_site_config(config_file)
  assert config.get("theme") == "narwhal"
  assert "sidebar_side" not in config

  config_file.write_text("theme: narwhal\nsidebar_side: left\n", encoding="utf-8")
  config = hanma.load_site_config(config_file)
  assert config.get("sidebar_side") == "left"

  config_file.write_text("theme: narwhal\nsidebar_side: right\n", encoding="utf-8")
  config = hanma.load_site_config(config_file)
  assert config.get("sidebar_side") == "right"


def test_list_themes_contains_narwhal():
  result = run_hanma("--list-themes")
  assert "narwhal" in result.stdout.lower()


def test_narwhal_rendered_layout_side_right(tmp_path):
  write_file(tmp_path / "index.md", "---\ntitle: Home Page\n---\nWelcome to Narwhal!")

  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: narwhal\nsidebar_side: right\nname: Narwhal Test Site\n", encoding="utf-8")

  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))

  index_html = (out_dir / "index.html").read_text(encoding="utf-8")

  assert 'class="narwhal-container sidebar-right"' in index_html
  assert 'class="narwhal-container sidebar-left"' not in index_html
  assert 'class="narwhal-sidebar"' in index_html
  assert 'class="sidebar-box search-box"' in index_html
  assert 'class="sidebar-box nav-box"' in index_html

  assert (out_dir / "assets" / "scripts" / "theme-init.js").exists()
  assert (out_dir / "assets" / "scripts" / "theme-toggle.js").exists()
  assert (out_dir / "assets" / "scripts" / "search.js").exists()
  assert (out_dir / "assets" / "css" / "style.css").exists()

  assert "scripts/theme-init.js" in index_html
  assert "scripts/theme-toggle.js" in index_html
  assert "scripts/search.js" in index_html


def test_narwhal_rendered_layout_side_left(tmp_path):
  write_file(tmp_path / "index.md", "---\ntitle: Home Page\n---\nWelcome to Narwhal!")

  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: narwhal\nsidebar_side: left\nname: Narwhal Test Site\n", encoding="utf-8")

  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))

  index_html = (out_dir / "index.html").read_text(encoding="utf-8")
  assert 'class="narwhal-container sidebar-left"' in index_html
  assert 'class="narwhal-container sidebar-right"' not in index_html


def test_narwhal_auxiliary_pages_contain_sidebar_side(tmp_path):
  write_file(tmp_path / "index.md", "---\ntitle: Home Page\n---\nWelcome.")
  write_file(tmp_path / "posts" / "hello.md", "---\ntitle: Hello World\nlayout: post\ntags:\n  - python\n  - web\n---\nHello.")

  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: narwhal\nsidebar_side: left\nname: Narwhal Test Site\n", encoding="utf-8")

  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))

  posts_index = (out_dir / "posts" / "index.html").read_text(encoding="utf-8")
  assert 'class="narwhal-container sidebar-left"' in posts_index

  tag_python = (out_dir / "tags" / "python.html").read_text(encoding="utf-8")
  assert 'class="narwhal-container sidebar-left"' in tag_python


# ---------------------------------------------------------------------------
# 2. Glassmorphic Theme
# ---------------------------------------------------------------------------

def test_list_themes_contains_glassmorphic():
  result = run_hanma("--list-themes")
  assert "glassmorphic" in result.stdout.lower()


def test_glassmorphic_rendered_layout_side_right(tmp_path):
  write_file(tmp_path / "index.md", "---\ntitle: Glassmorphic Home\n---\nWelcome to Glassmorphic theme!")

  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: glassmorphic\nsidebar_side: right\nname: Glassmorphic Test Site\n", encoding="utf-8")

  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))

  index_html = (out_dir / "index.html").read_text(encoding="utf-8")

  assert 'class="glass-container sidebar-right"' in index_html
  assert 'class="ambient-orb orb-1"' in index_html
  assert 'class="glass-sidebar"' in index_html
  assert 'class="glass-main"' in index_html
  assert 'class="prose glass-card"' in index_html
  assert 'id="mobileMenuToggle"' in index_html

  assert (out_dir / "assets" / "scripts" / "theme-init.js").exists()
  assert (out_dir / "assets" / "scripts" / "theme-toggle.js").exists()
  assert (out_dir / "assets" / "scripts" / "search.js").exists()
  assert (out_dir / "assets" / "css" / "style.css").exists()

  assert "scripts/theme-init.js" in index_html
  assert "scripts/theme-toggle.js" in index_html


def test_glassmorphic_rendered_layout_side_left(tmp_path):
  write_file(tmp_path / "index.md", "---\ntitle: Left Sidebar Page\n---\nLeft sidebar testing.")

  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: glassmorphic\nsidebar_side: left\nname: Glassmorphic Test Site\n", encoding="utf-8")

  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))

  index_html = (out_dir / "index.html").read_text(encoding="utf-8")
  assert 'class="glass-container sidebar-left"' in index_html


def test_glassmorphic_auxiliary_pages(tmp_path):
  write_file(tmp_path / "index.md", "---\ntitle: Home\n---\nWelcome.")
  write_file(tmp_path / "posts" / "post1.md", "---\ntitle: Post One\nlayout: post\ntags:\n  - coding\n---\nBlog content.")

  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: glassmorphic\nsidebar_side: right\nname: Glassmorphic Test Site\n", encoding="utf-8")

  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))

  posts_index = (out_dir / "posts" / "index.html").read_text(encoding="utf-8")
  assert 'class="glass-container sidebar-right"' in posts_index

  tag_coding = (out_dir / "tags" / "coding.html").read_text(encoding="utf-8")
  assert 'class="glass-container sidebar-right"' in tag_coding


# ---------------------------------------------------------------------------
# 3. Zen Garden Theme
# ---------------------------------------------------------------------------

def test_list_themes_contains_zengarden():
  result = run_hanma("--list-themes")
  assert "zengarden" in result.stdout.lower()


def test_zengarden_rendered_layout(tmp_path):
  write_file(tmp_path / "index.md", "---\ntitle: Zen Garden Home\n---\nWelcome to the dry landscape!")

  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: zengarden\nname: Zen Test Site\n", encoding="utf-8")

  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))

  index_html = (out_dir / "index.html").read_text(encoding="utf-8")

  assert 'class="zen-wrapper"' in index_html
  assert 'class="zen-header"' in index_html
  assert 'class="zen-logo"' in index_html
  assert 'class="zen-nav"' in index_html
  assert 'class="zen-main-container"' in index_html
  assert 'class="zen-footer"' in index_html
  assert 'class="shoji-accent left"' in index_html

  assert (out_dir / "assets" / "scripts" / "theme-init.js").exists()
  assert (out_dir / "assets" / "scripts" / "theme-toggle.js").exists()
  assert (out_dir / "assets" / "scripts" / "search.js").exists()
  assert (out_dir / "assets" / "css" / "style.css").exists()

  assert "assets/scripts/theme-init.js" in index_html
  assert "assets/scripts/theme-toggle.js" in index_html
