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
