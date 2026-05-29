# test_glassmorphic_theme.py — Tests for the high-fidelity premium Glassmorphic theme.
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


def test_list_themes_contains_glassmorphic():
  # Test --list-themes includes glassmorphic
  result = run_hanma("--list-themes")
  assert "glassmorphic" in result.stdout.lower()


def test_glassmorphic_rendered_layout_side_right(tmp_path):
  # Test compilation using glassmorphic with default/right sidebar
  write_file(tmp_path / "index.md", "---\ntitle: Glassmorphic Home\n---\nWelcome to Glassmorphic theme!")
  
  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: glassmorphic\nsidebar_side: right\nname: Glassmorphic Test Site\n", encoding="utf-8")
  
  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))
  
  index_html = (out_dir / "index.html").read_text(encoding="utf-8")
  
  # Check for our glassmorphic classes and features
  assert 'class="glass-container sidebar-right"' in index_html
  assert 'class="ambient-orb orb-1"' in index_html
  assert 'class="glass-sidebar"' in index_html
  assert 'class="glass-main"' in index_html
  assert 'class="prose glass-card"' in index_html
  assert 'id="mobileMenuToggle"' in index_html
  
  # Check scripts exist in output
  assert (out_dir / "assets" / "scripts" / "theme-init.js").exists()
  assert (out_dir / "assets" / "scripts" / "theme-toggle.js").exists()
  assert (out_dir / "assets" / "scripts" / "search.js").exists()
  assert (out_dir / "assets" / "css" / "style.css").exists()
  
  # Check theme-init.js and toggle scripts are present
  assert 'scripts/theme-init.js' in index_html
  assert 'scripts/theme-toggle.js' in index_html


def test_glassmorphic_rendered_layout_side_left(tmp_path):
  # Test compilation using glassmorphic with sidebar_side: left
  write_file(tmp_path / "index.md", "---\ntitle: Left Sidebar Page\n---\nLeft sidebar testing.")
  
  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: glassmorphic\nsidebar_side: left\nname: Glassmorphic Test Site\n", encoding="utf-8")
  
  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))
  
  index_html = (out_dir / "index.html").read_text(encoding="utf-8")
  assert 'class="glass-container sidebar-left"' in index_html


def test_glassmorphic_auxiliary_pages(tmp_path):
  # Test that generated auxiliary pages (tags, blog lists) also contain the glassmorphic layout.
  write_file(tmp_path / "index.md", "---\ntitle: Home\n---\nWelcome.")
  write_file(tmp_path / "posts" / "post1.md", "---\ntitle: Post One\nlayout: post\ntags:\n  - coding\n---\nBlog content.")
  
  cfg = tmp_path / "hanma.yml"
  cfg.write_text("theme: glassmorphic\nsidebar_side: right\nname: Glassmorphic Test Site\n", encoding="utf-8")
  
  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))
  
  # Check posts index/listing page
  posts_index = (out_dir / "posts" / "index.html").read_text(encoding="utf-8")
  assert 'class="glass-container sidebar-right"' in posts_index
  
  # Check tag page
  tag_coding = (out_dir / "tags" / "coding.html").read_text(encoding="utf-8")
  assert 'class="glass-container sidebar-right"' in tag_coding
