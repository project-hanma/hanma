# test_security.py — Security boundary tests for Hanma.
# Copyright (C) 2026  Chris Hammer

from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
import stat
import sys
from unittest.mock import MagicMock, patch

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(_PROJECT_ROOT))

from app.cli import QuietHandler, _HanmaHTTPServer, _create_parser, _get_effective_settings
from app.config import validate_base_url
from app.convert import convert_md_to_html
from app.files import copy_static_assets, find_markdown_files
from app.manifest import save_build_manifest
from app.nav import _is_safe_url, get_nav_data
from app.scaffold import init_scaffold
from app.theme import _load_theme_impl
from app.utils import _THEMES_DIR, atomic_write_text
from app.watch import _reload_watch_settings
from tests.helpers import write_file


@contextmanager
def _make_quiet_handler(serve_dir: Path):
  """Instantiate QuietHandler with mocked socket init pointing at serve_dir."""
  mock_server = MagicMock()
  mock_server.directory = str(serve_dir)
  mock_server.resolved_directory = None
  with patch.object(QuietHandler, "__init__", return_value=None):
    handler = QuietHandler()
    handler.server = mock_server
    handler.directory = str(serve_dir)
    yield handler


class TestPreviewServerSecurity:
  def test_server_is_threaded_and_handler_reads_directory_from_server(self):
    assert issubclass(_HanmaHTTPServer, ThreadingHTTPServer)
    with patch("app.cli.SimpleHTTPRequestHandler.__init__") as mock_super_init:
      mock_server = MagicMock()
      mock_server.directory = "/path/to/serve_dir"
      QuietHandler(MagicMock(), ("127.0.0.1", 12345), mock_server)
      mock_super_init.assert_called_once()
      _, kwargs = mock_super_init.call_args
      assert kwargs.get("directory") == "/path/to/serve_dir"

  def test_translate_path_blocks_external_symlinks_and_dotfiles(self, tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "index.html").write_text("<h1>OK</h1>", encoding="utf-8")
    (output_dir / ".hanma_manifest.json").write_text('{"secret": true}', encoding="utf-8")
    hidden_dir = output_dir / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "leak.html").write_text("secret", encoding="utf-8")

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("SECRET_DATA", encoding="utf-8")
    (output_dir / "vuln.txt").symlink_to(secret_file)

    with _make_quiet_handler(output_dir) as handler:
      assert Path(handler.translate_path("/index.html")) == (output_dir / "index.html").resolve()
      assert "non-existent" in handler.translate_path("/vuln.txt")
      assert "non-existent" in handler.translate_path("/.hanma_manifest.json")
      assert "non-existent" in handler.translate_path("/.hidden/leak.html")

  def test_security_headers_version_timeout_and_directory_listing(self, tmp_path):
    with _make_quiet_handler(tmp_path) as handler:
      assert handler.version_string() == "hanma"
      assert handler.timeout == 10

      headers = []
      handler.send_header = lambda k, v: headers.append((k, v))
      with patch("app.cli.SimpleHTTPRequestHandler.end_headers"):
        handler.end_headers()
      header_dict = dict(headers)
      assert header_dict.get("X-Content-Type-Options") == "nosniff"
      assert header_dict.get("X-Frame-Options") == "SAMEORIGIN"
      assert header_dict.get("Referrer-Policy") == "strict-origin-when-cross-origin"

      handler.send_error = MagicMock()
      assert handler.list_directory("/some/path") is None
      handler.send_error.assert_called_once_with(404, "File not found")

  def test_logs_only_http_errors(self, tmp_path):
    with _make_quiet_handler(tmp_path) as handler:
      with patch("app.cli.SimpleHTTPRequestHandler.log_message") as mock_log:
        handler.log_message("format", "GET /", "200", "-")
        handler.log_message("format", "GET /", "301", "-")
        assert not mock_log.called

        handler.log_message("format", "GET /", "404", "-")
        assert mock_log.called
        mock_log.reset_mock()

        handler.log_message("format", "GET /", "500", "-")
        assert mock_log.called


class TestHtmlSanitization:
  def test_disabled_by_default(self, tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("<script>alert('xss')</script>", encoding="utf-8")
    out_file = tmp_path / "test.html"

    convert_md_to_html(md_file, out_file, "Test Site")

    assert "<script>alert('xss')</script>" in out_file.read_text(encoding="utf-8")

  def test_preserves_safe_markdown_tables_and_code_highlighting(self, tmp_path):
    md_file = tmp_path / "safe.md"
    md_file.write_text(
      "# Hello\n\n"
      "**Bold** and *Italic*\n\n"
      "[Link](https://example.com)\n\n"
      "| Col 1 | Col 2 |\n|---|---|\n| Val 1 | Val 2 |\n\n"
      "```python\nprint('hello')\n```\n",
      encoding="utf-8",
    )
    out_file = tmp_path / "safe.html"

    convert_md_to_html(md_file, out_file, "Test Site", sanitize=True)

    html = out_file.read_text(encoding="utf-8")
    assert '<h1 id="hello">Hello' in html
    assert "<strong>Bold</strong>" in html
    assert "<em>Italic</em>" in html
    assert 'href="https://example.com"' in html
    assert "<table>" in html
    assert "<thead>" in html
    assert "<tbody>" in html
    assert "<th>Col 1</th>" in html
    assert "<td>Val 1</td>" in html
    assert '<div class="highlight">' in html
    assert "<pre>" in html
    assert "<span class=" in html

  def test_strips_scripts_styles_and_unpermitted_attrs(self, tmp_path):
    md_file = tmp_path / "unsafe.md"
    md_file.write_text(
      "---\n"
      "description: Safe Description\n"
      "---\n"
      "# Hello\n"
      "<script>alert('xss')</script>\n"
      "World\n\n"
      '<span style="color: red; position: fixed;">Style Test</span>\n'
      '<img class="img-class" id="img-id" src="image.png" alt="img" />\n'
      '<div class="allowed-class" id="allowed-id">Allowed Div</div>\n',
      encoding="utf-8",
    )
    out_file = tmp_path / "unsafe.html"

    convert_md_to_html(md_file, out_file, "Test Site", sanitize=True)

    html = out_file.read_text(encoding="utf-8")
    assert "<script>" not in html
    assert "alert('xss')" not in html
    assert "World" in html
    assert "<span>Style Test</span>" in html
    assert "color: red" not in html
    assert "image.png" in html
    assert "img-class" not in html
    assert "img-id" not in html
    assert 'class="allowed-class"' in html
    assert 'id="allowed-id"' in html

  def test_warns_when_nh3_unavailable(self, capsys, tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Test", encoding="utf-8")
    out_file = tmp_path / "test.html"

    with patch("app.convert._NH3_AVAILABLE", False):
      template = MagicMock()
      template.render.return_value = ""
      convert_md_to_html(
        md_file, out_file, "Site",
        sanitize=True, body="# Test", template=template,
      )
    assert "Warning: sanitization requested but 'nh3' is not installed" in capsys.readouterr().err


class TestUrlSecurity:
  def test_base_url_rejects_unsafe_schemes(self, capsys):
    assert validate_base_url("https://example.com") == "https://example.com"
    assert validate_base_url("") == ""
    with pytest.raises(ValueError):
      validate_base_url("javascript:alert(1)")
    with pytest.raises(ValueError):
      validate_base_url("ftp://example.com")

    args = _create_parser().parse_args(["--base-url", "javascript:alert(1)"])
    with pytest.raises(SystemExit) as exc:
      _get_effective_settings(args, {})
    assert exc.value.code == 1
    assert "Invalid base_url" in capsys.readouterr().err

  def test_nav_blocks_unsafe_urls_and_targets(self, tmp_path):
    assert _is_safe_url("//evil.com/phish") is False
    assert _is_safe_url("\\\\evil.com\\share") is False
    assert _is_safe_url("https://evil.com/\x00bad") is False
    assert _is_safe_url("https://example.com\n") is True

    out_home = tmp_path / "index.html"
    out_evil = tmp_path / "evil.html"
    out_p1 = tmp_path / "p1.html"
    out_safe = tmp_path / "safe.html"
    nav_pages = [
      (out_home, "Home", tmp_path / "index.md", "page", 1, None),
      (out_evil, "Evil", tmp_path / "evil.md", "page", 2, {"url": "javascript:alert(1)"}),
      (out_p1, "ProtoRel", tmp_path / "p1.md", "page", 3, {"url": "//evil.com", "target": "custom_win"}),
      (out_safe, "Safe", tmp_path / "safe.md", "page", 4, {"url": "https://example.com/docs", "target": "custom_win"}),
    ]
    items = {item["title"]: item for item in get_nav_data(out_home, nav_pages, output_root=tmp_path)}
    assert items["Evil"]["url"] == "evil.html"
    assert "javascript:" not in items["Evil"]["url"]
    assert items["ProtoRel"]["url"] == "p1.html"
    assert items["Safe"]["url"] == "https://example.com/docs"
    assert "target" not in items["Safe"]


class TestFilesystemSecurity:
  def test_build_ignores_external_symlinks(self, tmp_path):
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

    assert [p.name for p in find_markdown_files(site_dir)] == ["legit.md"]

    copy_static_assets(site_dir, out_dir)
    assert (out_dir / "static" / "ok.txt").exists()
    assert not (out_dir / "static" / "leak.txt").exists()

  def test_watch_reload_blocks_theme_path_traversal(self, tmp_path, capsys):
    evil_dir = tmp_path / "evil_theme"
    evil_dir.mkdir()
    (evil_dir / "template.html").write_text("<html>{{ content }}</html>", encoding="utf-8")

    cfg_path = tmp_path / "hanma.yml"
    cfg_path.write_text(f"theme: ../../..{evil_dir}\n", encoding="utf-8")

    default_tpl, default_dir = _load_theme_impl("default", _THEMES_DIR)
    state = {
      "site_name": "Site",
      "base_url": "",
      "posts_label": "Blog",
      "incremental": False,
      "sanitize": False,
      "timezone": None,
      "search_enabled": True,
      "sidebar_side": "right",
      "theme_dir": default_dir,
      "template": default_tpl,
    }
    updated = _reload_watch_settings(cfg_path, state, _THEMES_DIR, {})
    err = capsys.readouterr().err.lower()
    assert updated["theme_dir"] == default_dir
    assert "path traversal" in err or "invalid theme" in err

  def test_scaffold_force_unlinks_symlinked_dir_without_touching_target(self, tmp_path):
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    keep_file = outside_dir / "keep.txt"
    keep_file.write_text("safe", encoding="utf-8")

    site_target = tmp_path / "site_scaffold"
    site_target.mkdir()
    linked_dir = site_target / "linked_dir"
    linked_dir.symlink_to(outside_dir)

    init_scaffold(site_target, force=True)
    assert keep_file.exists()
    assert not linked_dir.exists()

  def test_atomic_write_and_manifest_file_permissions(self, tmp_path):
    pub = tmp_path / "pub.html"
    atomic_write_text(pub, "<html/>")
    assert stat.S_IMODE(pub.stat().st_mode) == 0o644

    man = tmp_path / ".hanma_manifest.json"
    save_build_manifest(man, {"k": "v"})
    assert stat.S_IMODE(man.stat().st_mode) == 0o600
