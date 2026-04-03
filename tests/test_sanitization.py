import pytest
from pathlib import Path
from app.convert import convert_md_to_html

def test_sanitization_strips_script_tag(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Hello\n<script>alert('xss')</script>\nWorld", encoding="utf-8")
    out_file = tmp_path / "test.html"
    
    # Run with sanitization enabled
    convert_md_to_html(md_file, out_file, "Test Site", sanitize=True)
    
    html_content = out_file.read_text(encoding="utf-8")
    assert "<script>" not in html_content
    # By default, bleach strips tags but leaves the content.
    # If we want to strip the content too, we'd need to configure bleach differently.
    # But for now, ensuring <script> is gone is the main goal.
    assert "alert('xss')" in html_content
    assert '<h1 id="hello">Hello' in html_content
    assert "World" in html_content

def test_sanitization_preserves_safe_html(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Hello\n\n**Bold** and *Italic*\n\n[Link](https://example.com)", encoding="utf-8")
    out_file = tmp_path / "test.html"
    
    # Run with sanitization enabled
    convert_md_to_html(md_file, out_file, "Test Site", sanitize=True)
    
    html_content = out_file.read_text(encoding="utf-8")
    assert '<h1 id="hello">Hello' in html_content
    assert "<strong>Bold</strong>" in html_content
    assert "<em>Italic</em>" in html_content
    assert 'href="https://example.com"' in html_content

def test_sanitization_preserves_tables(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("| Col 1 | Col 2 |\n|---|---|\n| Val 1 | Val 2 |", encoding="utf-8")
    out_file = tmp_path / "test.html"
    
    convert_md_to_html(md_file, out_file, "Test Site", sanitize=True)
    
    html_content = out_file.read_text(encoding="utf-8")
    assert "<table>" in html_content
    assert "<thead>" in html_content
    assert "<tbody>" in html_content
    assert "<th>Col 1</th>" in html_content
    assert "<td>Val 1</td>" in html_content

def test_sanitization_preserves_code_highlighting(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("```python\nprint('hello')\n```", encoding="utf-8")
    out_file = tmp_path / "test.html"
    
    convert_md_to_html(md_file, out_file, "Test Site", sanitize=True)
    
    html_content = out_file.read_text(encoding="utf-8")
    assert '<div class="highlight">' in html_content
    assert '<pre>' in html_content
    # Pygments uses many spans with classes
    assert '<span class=' in html_content

def test_sanitization_disabled_by_default(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("<script>alert('xss')</script>", encoding="utf-8")
    out_file = tmp_path / "test.html"
    
    # Run with default settings (sanitize=False)
    convert_md_to_html(md_file, out_file, "Test Site")
    
    html_content = out_file.read_text(encoding="utf-8")
    assert "<script>alert('xss')</script>" in html_content
