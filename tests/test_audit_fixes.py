import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from app.cli import main, QuietHandler
from app.convert import convert_md_to_html
from app.manifest import page_needs_rebuild

# ---------------------------------------------------------------------------
# 1. CLI & Server Fixes
# ---------------------------------------------------------------------------

@patch('app.cli._serve')
@patch('app.cli.load_site_config', return_value={})
@patch('app.cli._run_build', return_value=(1, 0, 0))
@patch('app.cli._load_theme_impl', return_value=(MagicMock(), Path(".")))
@patch('app.cli.Path.resolve', return_value=Path("."))
@patch('app.cli.Path.is_file', return_value=False)
@patch('app.cli.Path.is_dir', return_value=True)
def test_port_resolution_logic(mock_is_dir, mock_is_file, mock_resolve, 
                               mock_load_theme, mock_run_build, 
                               mock_config, mock_serve):
    """Test P0.3: --serve should win over --port when explicitly passed."""
    # We use decorators to avoid the "staircase of death" nested patch blocks.
    with patch('sys.argv', ['./hanma.py', '--serve', '9000', '--port', '7000']):
        try:
            main()
        except SystemExit:
            pass
            
    mock_serve.assert_called_once()
    # Verify that port 9000 (from --serve) was passed to _serve, ignoring --port 7000
    assert mock_serve.call_args[0][1] == 9000

def test_symlink_restriction_logic(tmp_path):
    """Test Item 2: Ensure symlinks pointing outside output dir are blocked."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("SECRET_DATA")
    
    # Create symlink pointing outside
    symlink_file = output_dir / "vuln.txt"
    symlink_file.symlink_to(secret_file)
    
    # Instantiate QuietHandler with a mock server that has the 'directory' attribute
    mock_server = MagicMock()
    mock_server.directory = str(output_dir)
    
    # We mock __init__ to avoid trying to setup the real socket/handler
    with patch.object(QuietHandler, '__init__', return_value=None):
        handler = QuietHandler()
        handler.server = mock_server
        handler.directory = str(output_dir)
        
        # translate_path returns a string path. 
        # For valid paths inside, it should return the absolute path.
        # For invalid paths outside, it returns "/dev/null/non-existent"
        
        # 1. Valid path
        valid_fs = handler.translate_path("/index.html")
        assert Path(valid_fs).is_relative_to(output_dir.resolve())
        
        # 2. Malicious symlink
        invalid_fs = handler.translate_path("/vuln.txt")
        assert "non-existent" in invalid_fs

def test_diagnostic_logging_logic():
    """Test Item 3: Verify only errors (>= 400) are logged."""
    with patch.object(QuietHandler, '__init__', return_value=None):
        handler = QuietHandler()
        
        with patch('app.cli.SimpleHTTPRequestHandler.log_message') as mock_log:
            # Should NOT log 200 OK
            handler.log_message("format", "GET /", "200", "-")
            assert not mock_log.called
            
            # Should NOT log 301 Redirect
            handler.log_message("format", "GET /", "301", "-")
            assert not mock_log.called
            
            # Should log 404 Not Found
            handler.log_message("format", "GET /", "404", "-")
            assert mock_log.called
            mock_log.reset_mock()
            
            # Should log 500 Server Error
            handler.log_message("format", "GET /", "500", "-")
            assert mock_log.called

# ---------------------------------------------------------------------------
# 2. Markdown & Build Fixes
# ---------------------------------------------------------------------------

def test_refresh_clamping(tmp_path):
    """Test P0.7: refresh values should be clamped to [1, 86400]."""
    from markupsafe import Markup
    
    md_file = tmp_path / "test.md"
    md_file.write_text("# Test", encoding="utf-8")
    out_file = tmp_path / "test.html"

    template = MagicMock()
    template.render.return_value = ""

    # Test high value -> clamped to 86400
    front = {"refresh": 999999}
    with patch('app.convert.Markup', side_effect=Markup) as mock_markup:
        convert_md_to_html(md_file, out_file, "Site", 
                          front_matter=front, body="# Test", template=template)
        args = [call.args[0] for call in mock_markup.call_args_list]
        assert any('content="86400"' in a for a in args)

    # Test negative value -> disabled
    front = {"refresh": -10}
    with patch('app.convert.Markup', side_effect=Markup) as mock_markup:
        convert_md_to_html(md_file, out_file, "Site", 
                          front_matter=front, body="# Test", template=template)
        args = [call.args[0] for call in mock_markup.call_args_list]
        assert not any('http-equiv="refresh"' in a for a in args)

def test_sanitization_warning(capsys, tmp_path):
    """Test P0.6: Warning should be printed if bleach is missing."""
    md_file = tmp_path / "test.md"
    md_file.write_text("# Test", encoding="utf-8")
    out_file = tmp_path / "test.html"

    with patch('app.convert._BLEACH_AVAILABLE', False):
        template = MagicMock()
        template.render.return_value = ""
        convert_md_to_html(md_file, out_file, "Site", 
                          sanitize=True, body="# Test", template=template)
        captured = capsys.readouterr()
        assert "Warning: sanitization requested but 'bleach' is not installed" in captured.err

def test_manifest_hash_robustness():
    """Test P0.4: Manifest should only trust 64-char strings as hashes."""
    manifest = {"test.md": "too-short"}
    # Should return True (needs rebuild) because hash is invalid length
    assert page_needs_rebuild(Path("test.md"), Path("test.html"), manifest, 
                             template_mtime=0, md_hash="a"*64) is True
    
    manifest = {"test.md": "a"*64}
    # Should return False (no rebuild) if hash matches
    with patch('app.manifest.Path.exists', return_value=True):
        assert page_needs_rebuild(Path("test.md"), Path("test.html"), manifest, 
                                 template_mtime=0, md_hash="a"*64) is False


def test_directory_indexing_blocked():
    """Test Item 5: Ensure directory indexing is blocked and returns a 404."""
    with patch.object(QuietHandler, '__init__', return_value=None):
        handler = QuietHandler()
        handler.send_error = MagicMock()
        
        res = handler.list_directory("/some/path")
        
        assert res is None
        handler.send_error.assert_called_once_with(404, "File not found")


def test_quiet_handler_directory_init():
    """Verify that QuietHandler correctly grabs directory from the server parameter during init."""
    with patch('app.cli.SimpleHTTPRequestHandler.__init__') as mock_super_init:
        mock_server = MagicMock()
        mock_server.directory = "/path/to/serve_dir"
        
        # Instantiate with mock request, address, and server
        QuietHandler(MagicMock(), ("127.0.0.1", 12345), mock_server)
        
        # Super init should be called with the correct keyword argument 'directory'
        mock_super_init.assert_called_once()
        _, kwargs = mock_super_init.call_args
        assert kwargs.get("directory") == "/path/to/serve_dir"


# ---------------------------------------------------------------------------
# 3. Datetime & Tag Sorting Fixes
# ---------------------------------------------------------------------------

def test_tag_sort_key_mixed_aware_naive_datetimes():
    """Verify _tag_sort_key safely sorts mixed aware, naive, string, and missing dates."""
    from datetime import datetime, date, timezone
    from zoneinfo import ZoneInfo
    from app.build import _tag_sort_key

    entries = [
        (Path("undated.html"), "Undated", None),
        (Path("aware_utc.html"), "Aware UTC 2026", datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)),
        (Path("naive_2025.html"), "Naive 2025", datetime(2025, 6, 1, 12, 0)),
        (Path("aware_ny.html"), "Aware NY 2026", datetime(2026, 7, 1, 12, 0, tzinfo=ZoneInfo("America/New_York"))),
        (Path("str_human.html"), "String Human", "March 15, 2025"),
        (Path("str_iso.html"), "String ISO", "2024-12-01"),
        (Path("date_obj.html"), "Date Obj", date(2024, 1, 1)),
        (Path("malformed.html"), "Malformed", "not-a-valid-date"),
    ]

    # Must sort without raising TypeError: can't compare offset-naive and offset-aware datetimes
    sorted_entries = sorted(entries, key=_tag_sort_key, reverse=True)
    sorted_titles = [t for _, t, _ in sorted_entries]

    # Newest to oldest:
    # 1. Aware NY 2026 (July 2026)
    # 2. Aware UTC 2026 (Jan 2026)
    # 3. Naive 2025 (June 2025)
    # 4. String Human (March 2025)
    # 5. String ISO (Dec 2024)
    # 6. Date Obj (Jan 2024)
    # 7 & 8: Undated / Malformed (sorted at the end)
    assert sorted_titles[:6] == [
        "Aware NY 2026",
        "Aware UTC 2026",
        "Naive 2025",
        "String Human",
        "String ISO",
        "Date Obj",
    ]
    assert set(sorted_titles[6:]) == {"Undated", "Malformed"}


def test_tag_sort_key_with_configured_timezone():
    """Verify _tag_sort_key honors tz_name when normalizing naive datetimes."""
    from datetime import datetime, timezone
    from app.build import _tag_sort_key

    # 2025-01-01 02:00:00 in Asia/Tokyo is 2024-12-31 17:00:00 UTC
    # 2025-01-01 00:00:00 in UTC is 2025-01-01 00:00:00 UTC
    # In UTC, 2025-01-01 00:00:00 UTC is NEWER than 2024-12-31 17:00:00 UTC.
    tokyo_naive = (Path("tokyo.html"), "Tokyo Naive", datetime(2025, 1, 1, 2, 0))
    utc_aware = (Path("utc.html"), "UTC Aware", datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc))

    key_tokyo = _tag_sort_key(tokyo_naive, tz_name="Asia/Tokyo")
    key_utc = _tag_sort_key(utc_aware, tz_name="Asia/Tokyo")

    assert key_utc[1] > key_tokyo[1]


def test_tag_index_site_generation_mixed_dates(tmp_path):
    """End-to-end integration test: generate tag index containing mixed dates and verify order."""
    from tests.helpers import run_hanma, write_file

    write_file(tmp_path / "page_new.md", "---\ntitle: Newest Post\ndate: 2026-03-01\ntags:\n  - tech\n---\n# New")
    write_file(tmp_path / "page_old.md", "---\ntitle: Oldest Post\ndate: 2024-01-01\ntags:\n  - tech\n---\n# Old")
    write_file(tmp_path / "page_undated.md", "---\ntitle: Undated Post\ntags:\n  - tech\n---\n# Undated")

    out_dir = tmp_path / "out"
    res = run_hanma(str(tmp_path), "--output", str(out_dir))
    assert res.returncode == 0, f"Build failed with: {res.stderr}\n{res.stdout}"

    tag_file = out_dir / "tags" / "tech.html"
    assert tag_file.exists()
    content = tag_file.read_text(encoding="utf-8")

    # Verify all posts are present
    assert "Newest Post" in content
    assert "Oldest Post" in content
    assert "Undated Post" in content

    # Verify descending date order (newest first, undated last)
    idx_new = content.index("Newest Post")
    idx_old = content.index("Oldest Post")
    idx_undated = content.index("Undated Post")
    assert idx_new < idx_old < idx_undated


# ---------------------------------------------------------------------------
# 4. Watch Mode Fixes (Stage 1)
# ---------------------------------------------------------------------------

def test_watch_event_handler_detects_theme_template_html(tmp_path):
    """Verify _HanmaEventHandler triggers on theme_dir/template.html but ignores output .html files."""
    from app.watch import _HanmaEventHandler

    src_dir = tmp_path / "site"
    theme_dir = tmp_path / "themes" / "custom"
    out_dir = tmp_path / "output"
    src_dir.mkdir()
    theme_dir.mkdir(parents=True)
    out_dir.mkdir()

    handler = _HanmaEventHandler(lambda: None, src_dir, theme_dir, output_dir=out_dir)

    # Regular .html in source or output must be ignored
    assert handler._is_relevant(str(src_dir / "page.html")) is False
    assert handler._is_relevant(str(out_dir / "index.html")) is False

    # template.html inside theme_dir must be relevant
    assert handler._is_relevant(str(theme_dir / "template.html")) is True


def test_watch_and_rebuild_forwards_sidebar_side(tmp_path):
    """Verify watch_and_rebuild and _watch_polling accept and forward sidebar_side."""
    import inspect
    from app.watch import watch_and_rebuild, _watch_polling

    sig_watch = inspect.signature(watch_and_rebuild)
    sig_poll = inspect.signature(_watch_polling)
    assert "sidebar_side" in sig_watch.parameters
    assert sig_watch.parameters["sidebar_side"].default == "right"
    assert "sidebar_side" in sig_poll.parameters
    assert sig_poll.parameters["sidebar_side"].default == "right"


# ---------------------------------------------------------------------------
# 5. Core Build & CLI Fixes (Stage 2)
# ---------------------------------------------------------------------------

def test_tag_slug_collision_merges_pages_and_skips_empty_slugs(tmp_path):
    """Issue 2.2: Tags normalizing to the same slug merge rather than overwrite; empty slugs skipped."""
    from tests.helpers import run_hanma, write_file

    write_file(tmp_path / "post_a.md", "---\ntitle: Post A\ntags:\n  - Python\n  - '+++'\n---\n# Post A")
    write_file(tmp_path / "post_b.md", "---\ntitle: Post B\ntags:\n  - python\n---\n# Post B")

    out_dir = tmp_path / "out"
    res = run_hanma(str(tmp_path), "--output", str(out_dir))
    assert res.returncode == 0

    tag_file = out_dir / "tags" / "python.html"
    assert tag_file.exists()
    tag_html = tag_file.read_text(encoding="utf-8")
    assert "Post A" in tag_html
    assert "Post B" in tag_html
    assert not (out_dir / "tags" / ".html").exists()


def test_non_integer_sort_index_warns_and_does_not_crash(tmp_path):
    """Issue 2.4: Non-integer sort_index logs a warning and falls back to None without crashing."""
    from tests.helpers import run_hanma, write_file

    write_file(tmp_path / "bad_sort.md", "---\ntitle: Bad Sort\nsort_index: invalid_int\n---\n# Hello")
    out_dir = tmp_path / "out"
    res = run_hanma(str(tmp_path), "--output", str(out_dir))
    assert res.returncode == 0
    assert "Warning: invalid sort_index" in res.stderr
    assert (out_dir / "bad_sort.html").exists()


def test_nested_page_sitemap_link_is_relative(tmp_path):
    """Issue 2.5: Subdirectory pages must link to ../sitemap.xml instead of bare sitemap.xml."""
    from tests.helpers import run_hanma, write_file

    write_file(tmp_path / "index.md", "# Home\n\nWelcome.")
    write_file(tmp_path / "posts" / "nested.md", "# Nested Post\n\nBody.")
    out_dir = tmp_path / "out"
    res = run_hanma(str(tmp_path), "--output", str(out_dir), "--base-url", "https://example.com")
    assert res.returncode == 0

    nested_html = (out_dir / "posts" / "nested.html").read_text(encoding="utf-8")
    assert 'href="../sitemap.xml"' in nested_html


def test_invalid_port_and_sidebar_side_validation(tmp_path):
    """Issue 2.7: Out-of-bounds ports exit cleanly; invalid sidebar_side defaults to right."""
    from tests.helpers import run_hanma, write_file

    write_file(tmp_path / "index.md", "# Home\n\nWelcome.")
    out_dir = tmp_path / "out"

    # Out-of-bounds CLI port must exit non-zero with clear error
    res_port = run_hanma(str(tmp_path), "--output", str(out_dir), "--port", "70000", expect_ok=False)
    assert res_port.returncode != 0
    assert "Port must be between 1 and 65535" in res_port.stderr

    # Invalid sidebar_side in config warns and falls back to right
    cfg = tmp_path / "hanma.yml"
    cfg.write_text("theme: narwhal\nsidebar_side: upside_down\n", encoding="utf-8")
    res_side = run_hanma(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))
    assert res_side.returncode == 0
    assert "Warning: invalid sidebar_side" in res_side.stderr
    html_out = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "sidebar-right" in html_out


def test_sitemap_lastmod_uses_source_mtime(tmp_path):
    """Issue 2.8: sitemap.xml <lastmod> reflects source file mtime rather than build time."""
    from tests.helpers import run_hanma, write_file

    md_file = write_file(tmp_path / "page.md", "# Historical Page\n\nContent.")
    # Set mtime to 2021-06-15 12:00:00 UTC (1623758400)
    os.utime(md_file, (1623758400, 1623758400))

    out_dir = tmp_path / "out"
    res = run_hanma(str(tmp_path), "--output", str(out_dir), "--base-url", "https://example.com")
    assert res.returncode == 0

    sitemap_xml = (out_dir / "sitemap.xml").read_text(encoding="utf-8")
    assert "<lastmod>2021-06-15</lastmod>" in sitemap_xml


# ---------------------------------------------------------------------------
# 6. Security Hardening Fixes (Stage 3)
# ---------------------------------------------------------------------------

def test_nav_link_url_blocks_unsafe_schemes(tmp_path):
    """Issue 3.1: Front matter link.url with javascript:, data:, or vbscript: must be ignored."""
    from app.nav import get_nav_data

    out_home = tmp_path / "index.html"
    out_evil = tmp_path / "evil.html"
    out_safe = tmp_path / "safe.html"

    nav_pages = [
        (out_home, "Home", tmp_path / "index.md", "page", 1, None),
        (out_evil, "Evil", tmp_path / "evil.md", "page", 2, {"url": "javascript:alert(1)"}),
        (out_safe, "Safe", tmp_path / "safe.md", "page", 3, {"url": "https://example.com/docs"}),
    ]
    nav_items = get_nav_data(out_home, nav_pages, output_root=tmp_path)
    urls = {item["title"]: item["url"] for item in nav_items}

    assert urls["Evil"] == "evil.html"
    assert "javascript:" not in urls["Evil"]
    assert urls["Safe"] == "https://example.com/docs"


def test_build_ignores_symlinks_pointing_outside_source_root(tmp_path):
    """Issue 3.2: Symlinks in site/ or site/static/ pointing outside root must not be read or copied."""
    from app.files import find_markdown_files, copy_static_assets
    from tests.helpers import write_file

    site_dir = tmp_path / "site"
    out_dir = tmp_path / "out"
    site_dir.mkdir()
    out_dir.mkdir()

    external_md = write_file(tmp_path / "outside_secret.md", "# Secret Outside\n\nDo not leak.")
    external_txt = write_file(tmp_path / "outside_static.txt", "SECRET_STATIC_CONTENT")

    write_file(site_dir / "legit.md", "# Legit\n\nInside site.")
    (site_dir / "leaked.md").symlink_to(external_md)

    static_dir = site_dir / "static"
    static_dir.mkdir()
    write_file(static_dir / "ok.txt", "OK")
    (static_dir / "leak.txt").symlink_to(external_txt)

    md_files = find_markdown_files(site_dir)
    assert [p.name for p in md_files] == ["legit.md"]

    copy_static_assets(site_dir, out_dir)
    assert (out_dir / "static" / "ok.txt").exists()
    assert not (out_dir / "static" / "leak.txt").exists()


def test_extract_description_strips_html_and_script_tags():
    """Issue 3.4: extract_description strips inline HTML and script/style blocks."""
    from app.parsing import extract_description

    md = "# Heading\n\n<script>alert('xss')</script>\n<div class=\"lead\">Clean <b>text</b> here.</div>"
    assert extract_description(md) == "Clean text here."


# ---------------------------------------------------------------------------
# 7. Performance Optimizations (Stage 4)
# ---------------------------------------------------------------------------

def test_differential_static_asset_sync_and_pruning(tmp_path):
    """Issue 4.2: Unchanged static files are not rewritten; deleted static files are pruned."""
    from app.files import copy_static_assets
    from tests.helpers import write_file

    site_dir = tmp_path / "site"
    out_dir = tmp_path / "out"
    static_src = site_dir / "static"
    static_src.mkdir(parents=True)
    out_dir.mkdir()

    f_keep = write_file(static_src / "keep.txt", "keep")
    f_del = write_file(static_src / "sub" / "delete_me.txt", "delete")

    # Initial sync
    copy_static_assets(site_dir, out_dir)
    dest_keep = out_dir / "static" / "keep.txt"
    dest_del = out_dir / "static" / "sub" / "delete_me.txt"
    assert dest_keep.exists()
    assert dest_del.exists()
    inode_before = dest_keep.stat().st_ino

    # Delete f_del in source and sync again
    f_del.unlink()
    copy_static_assets(site_dir, out_dir)

    assert dest_keep.exists()
    assert dest_keep.stat().st_ino == inode_before  # Not deleted & recreated
    assert not dest_del.exists()
    assert not (out_dir / "static" / "sub").exists()  # Empty parent dir pruned


def test_lazy_highlight_css_attribute_access():
    """Issue 4.6: HIGHLIGHT_CSS is lazily evaluated via module __getattr__ and cached."""
    import app
    import app.highlight

    css1 = app.HIGHLIGHT_CSS
    css2 = app.highlight.HIGHLIGHT_CSS
    assert css1 == css2
    assert ".highlight" in css1


# ---------------------------------------------------------------------------
# 8. HTML & CSS Sanitization (Bleach)
# ---------------------------------------------------------------------------

def test_sanitization_strips_script_tag(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Hello\n<script>alert('xss')</script>\nWorld", encoding="utf-8")
    out_file = tmp_path / "test.html"

    convert_md_to_html(md_file, out_file, "Test Site", sanitize=True)

    html_content = out_file.read_text(encoding="utf-8")
    assert "<script>" not in html_content
    assert "alert('xss')" in html_content
    assert '<h1 id="hello">Hello' in html_content
    assert "World" in html_content


def test_sanitization_preserves_safe_html(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Hello\n\n**Bold** and *Italic*\n\n[Link](https://example.com)", encoding="utf-8")
    out_file = tmp_path / "test.html"

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
    assert "<pre>" in html_content
    assert "<span class=" in html_content


def test_sanitization_disabled_by_default(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("<script>alert('xss')</script>", encoding="utf-8")
    out_file = tmp_path / "test.html"

    convert_md_to_html(md_file, out_file, "Test Site")

    html_content = out_file.read_text(encoding="utf-8")
    assert "<script>alert('xss')</script>" in html_content


def test_sanitization_strips_style_and_unpermitted_class_id(tmp_path):
    md_file = tmp_path / "test.md"
    md_text = (
        "---\n"
        "description: Safe Description\n"
        "---\n"
        '<span style="color: red; position: fixed;">Style Test</span>\n'
        '<img class="img-class" id="img-id" src="image.png" alt="img" />\n'
        '<div class="allowed-class" id="allowed-id">Allowed Div</div>'
    )
    md_file.write_text(md_text, encoding="utf-8")
    out_file = tmp_path / "test.html"

    convert_md_to_html(md_file, out_file, "Test Site", sanitize=True)

    html_content = out_file.read_text(encoding="utf-8")
    assert "<span>Style Test</span>" in html_content
    assert "color: red" not in html_content
    assert "image.png" in html_content
    assert "img-class" not in html_content
    assert "img-id" not in html_content
    assert 'class="allowed-class"' in html_content
    assert 'id="allowed-id"' in html_content

