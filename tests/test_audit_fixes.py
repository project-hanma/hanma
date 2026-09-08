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


