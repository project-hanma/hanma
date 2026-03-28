"""
Tests for ssg.py — syntax, file discovery, conversion, CLI behaviour.
Run with: python -m pytest tests/
"""

import importlib
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SSG = Path(__file__).parent.parent / "ssg.py"


def run(*args, cwd=None, expect_ok=True):
    """Run ssg.py with the given arguments and return CompletedProcess."""
    result = subprocess.run(
        [sys.executable, str(SSG), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    if expect_ok and result.returncode != 0:
        pytest.fail(
            f"ssg.py exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))
    return path


# ---------------------------------------------------------------------------
# Import the module under test so we can call functions directly
# ---------------------------------------------------------------------------

spec = importlib.util.spec_from_file_location("ssg", SSG)
ssg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssg)


# ===========================================================================
# 1. Syntax / import
# ===========================================================================


class TestSyntax:
    def test_module_imports_cleanly(self):
        assert ssg is not None

    def test_version_string_present(self):
        assert hasattr(ssg, "__version__")
        assert ssg.__version__

    def test_py_compile(self):
        import py_compile
        py_compile.compile(str(SSG), doraise=True)


# ===========================================================================
# 2. --version flag
# ===========================================================================


class TestVersionFlag:
    def test_version_flag_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(SSG), "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_version_output_contains_version(self):
        result = subprocess.run(
            [sys.executable, str(SSG), "--version"],
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        assert ssg.__version__ in combined


# ===========================================================================
# 3. Title & description extraction
# ===========================================================================


class TestExtractTitle:
    def test_h1_extracted(self):
        assert ssg.extract_title("# Hello World\n\nParagraph.", "fallback") == "Hello World"

    def test_fallback_used_when_no_h1(self):
        assert ssg.extract_title("Just a paragraph.", "my-file") == "my-file"

    def test_fallback_is_not_used_when_h1_present(self):
        result = ssg.extract_title("# Real Title\nText.", "should-not-appear")
        assert result == "Real Title"

    def test_h1_with_extra_whitespace(self):
        assert ssg.extract_title("#   Spaced Title  \n", "fb") == "Spaced Title"

    def test_h2_not_treated_as_title(self):
        result = ssg.extract_title("## Section\nText.", "fallback")
        assert result == "fallback"


class TestExtractDescription:
    def test_first_paragraph_used(self):
        md = "# Title\n\nThis is the intro paragraph.\n\n## Section\n"
        desc = ssg.extract_description(md)
        assert "intro paragraph" in desc

    def test_heading_lines_skipped(self):
        md = "# Title\n## Sub\nThis is text."
        desc = ssg.extract_description(md)
        assert desc == "This is text."

    def test_truncated_to_160_chars(self):
        md = "# T\n\n" + ("word " * 50)
        desc = ssg.extract_description(md, max_chars=160)
        assert len(desc) <= 160

    def test_empty_file_returns_empty(self):
        assert ssg.extract_description("") == ""


# ===========================================================================
# 4. File discovery
# ===========================================================================


class TestFindMarkdownFiles:
    def test_discovers_md_files(self, tmp_path):
        write(tmp_path / "a.md", "# A")
        write(tmp_path / "b.md", "# B")
        found = ssg.find_markdown_files(tmp_path)
        names = {p.name for p in found}
        assert names == {"a.md", "b.md"}

    def test_recurses_into_subdirectories(self, tmp_path):
        write(tmp_path / "sub" / "deep.md", "# Deep")
        found = ssg.find_markdown_files(tmp_path)
        assert any(p.name == "deep.md" for p in found)

    def test_skips_dotdirs(self, tmp_path):
        write(tmp_path / ".hidden" / "secret.md", "# Secret")
        write(tmp_path / "visible.md", "# Visible")
        found = ssg.find_markdown_files(tmp_path)
        assert all(p.name != "secret.md" for p in found)

    def test_skips_readme(self, tmp_path):
        write(tmp_path / "README.md", "# Readme")
        write(tmp_path / "page.md", "# Page")
        found = ssg.find_markdown_files(tmp_path)
        assert all(p.name.lower() != "readme.md" for p in found)

    def test_index_included_in_results(self, tmp_path):
        write(tmp_path / "alpha.md", "# Alpha")
        write(tmp_path / "index.md", "# Home")
        write(tmp_path / "zebra.md", "# Zebra")
        found = ssg.find_markdown_files(tmp_path)
        stems = [p.stem.lower() for p in found]
        assert "index" in stems

    def test_accepts_markdown_extension(self, tmp_path):
        write(tmp_path / "page.markdown", "# Page")
        found = ssg.find_markdown_files(tmp_path)
        assert any(p.suffix == ".markdown" for p in found)

    def test_ignores_non_markdown_files(self, tmp_path):
        write(tmp_path / "data.json", '{"key": "value"}')
        write(tmp_path / "page.md", "# Page")
        found = ssg.find_markdown_files(tmp_path)
        assert all(p.suffix in {".md", ".markdown"} for p in found)


# ===========================================================================
# 5. convert_md_to_html
# ===========================================================================


class TestConvertMdToHtml:
    def test_produces_html_file(self, tmp_path):
        src = write(tmp_path / "page.md", "# Hello\n\nWorld.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "Test Site", nav_pages=[])
        assert out.exists()

    def test_output_contains_title(self, tmp_path):
        src = write(tmp_path / "page.md", "# My Page\n\nContent.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "Test Site", nav_pages=[])
        html = out.read_text()
        assert "My Page" in html

    def test_output_contains_site_name(self, tmp_path):
        src = write(tmp_path / "page.md", "# Page\n\nContent.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "MySite", nav_pages=[])
        html = out.read_text()
        assert "MySite" in html

    def test_markdown_rendered_to_html_tags(self, tmp_path):
        src = write(tmp_path / "page.md", "# Title\n\n**bold** and *italic*.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html = out.read_text()
        assert "<strong>" in html
        assert "<em>" in html

    def test_fenced_code_block_highlighted(self, tmp_path):
        src = write(tmp_path / "code.md", "# Code\n\n```python\nprint('hi')\n```\n")
        out = tmp_path / "code.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html = out.read_text()
        assert "<code" in html.lower()

    def test_table_rendered(self, tmp_path):
        src = write(
            tmp_path / "table.md",
            """\
            # Table

            | A | B |
            |---|---|
            | 1 | 2 |
            """,
        )
        out = tmp_path / "table.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html = out.read_text()
        assert "<table" in html

    def test_creates_parent_directories(self, tmp_path):
        src = write(tmp_path / "src" / "sub" / "page.md", "# Deep\n\nContent.")
        out = tmp_path / "dist" / "sub" / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        assert out.exists()

    def test_self_contained_no_external_links(self, tmp_path):
        src = write(tmp_path / "page.md", "# Page\n\nContent.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html = out.read_text()
        # Should not reference CDN or external resources
        for external in ["cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com"]:
            assert external not in html


# ===========================================================================
# 6. CLI — in-place conversion
# ===========================================================================


class TestCLIInPlace:
    def test_converts_single_file(self, tmp_path):
        src = write(tmp_path / "page.md", "# Page\n\nContent.")
        run(str(src))
        assert (tmp_path / "page.html").exists()

    def test_converts_directory(self, tmp_path):
        write(tmp_path / "a.md", "# A\n\nContent.")
        write(tmp_path / "b.md", "# B\n\nContent.")
        run(str(tmp_path))
        assert (tmp_path / "a.html").exists()
        assert (tmp_path / "b.html").exists()

    def test_recurses_into_subdirs(self, tmp_path):
        write(tmp_path / "sub" / "page.md", "# Sub\n\nContent.")
        run(str(tmp_path))
        assert (tmp_path / "sub" / "page.html").exists()

    def test_nonexistent_path_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(SSG), "/nonexistent/path/that/does/not/exist"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_error_message_on_bad_path(self):
        result = subprocess.run(
            [sys.executable, str(SSG), "/no/such/path"],
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        assert "not a file or directory" in combined.lower() or "error" in combined.lower()


# ===========================================================================
# 7. CLI — --output flag
# ===========================================================================


class TestCLIOutput:
    def test_html_written_to_output_dir(self, tmp_path):
        src_dir = tmp_path / "src"
        out_dir = tmp_path / "dist"
        write(src_dir / "page.md", "# Page\n\nContent.")
        run(str(src_dir), "--output", str(out_dir))
        assert (out_dir / "page.html").exists()

    def test_source_files_untouched(self, tmp_path):
        src_dir = tmp_path / "src"
        out_dir = tmp_path / "dist"
        write(src_dir / "page.md", "# Page\n\nContent.")
        run(str(src_dir), "--output", str(out_dir))
        assert not (src_dir / "page.html").exists()

    def test_mirrors_subdirectory_structure(self, tmp_path):
        src_dir = tmp_path / "src"
        out_dir = tmp_path / "dist"
        write(src_dir / "posts" / "hello.md", "# Hello\n\nContent.")
        run(str(src_dir), "--output", str(out_dir))
        assert (out_dir / "posts" / "hello.html").exists()

    def test_output_dir_created_if_missing(self, tmp_path):
        src_dir = tmp_path / "src"
        out_dir = tmp_path / "new_dist"
        write(src_dir / "page.md", "# Page\n\nContent.")
        run(str(src_dir), "--output", str(out_dir))
        assert out_dir.is_dir()


# ===========================================================================
# 8. CLI — --dry-run
# ===========================================================================


class TestCLIDryRun:
    def test_no_files_written(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        run(str(tmp_path), "--dry-run")
        assert not (tmp_path / "page.html").exists()

    def test_lists_files_in_output(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        result = run(str(tmp_path), "--dry-run")
        assert "page.md" in result.stdout

    def test_dry_run_with_output_dir_no_files_written(self, tmp_path):
        src_dir = tmp_path / "src"
        out_dir = tmp_path / "dist"
        write(src_dir / "page.md", "# Page\n\nContent.")
        run(str(src_dir), "--output", str(out_dir), "--dry-run")
        assert not out_dir.exists() or not (out_dir / "page.html").exists()


# ===========================================================================
# 9. CLI — --name
# ===========================================================================


class TestCLIName:
    def test_site_name_appears_in_output(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        run(str(tmp_path), "--name", "MyAwesomeSite")
        html = (tmp_path / "page.html").read_text()
        assert "MyAwesomeSite" in html


# ===========================================================================
# 10. Navigation
# ===========================================================================


class TestNavigation:
    def test_nav_links_present_for_multiple_pages(self, tmp_path):
        write(tmp_path / "index.md", "# Home\n\nWelcome.")
        write(tmp_path / "about.md", "# About\n\nInfo.")
        run(str(tmp_path))
        html = (tmp_path / "index.html").read_text()
        assert "about.html" in html

    def test_current_page_marked(self, tmp_path):
        write(tmp_path / "index.md", "# Home\n\nWelcome.")
        write(tmp_path / "about.md", "# About\n\nInfo.")
        run(str(tmp_path))
        html = (tmp_path / "about.html").read_text()
        assert 'aria-current="page"' in html

    def test_index_labelled_home(self, tmp_path):
        write(tmp_path / "index.md", "# Welcome\n\nContent.")
        write(tmp_path / "other.md", "# Other\n\nContent.")
        run(str(tmp_path))
        html = (tmp_path / "other.html").read_text()
        assert "Home" in html

    def test_index_link_appears_before_other_pages(self, tmp_path):
        write(tmp_path / "index.md", "# Home\n\nContent.")
        write(tmp_path / "about.md", "# About\n\nContent.")
        run(str(tmp_path))
        html = (tmp_path / "about.html").read_text()
        assert html.index("index.html") < html.index("about.html")


# ===========================================================================
# 11. Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_empty_file_does_not_crash(self, tmp_path):
        write(tmp_path / "empty.md", "")
        run(str(tmp_path))
        assert (tmp_path / "empty.html").exists()

    def test_file_with_no_headings(self, tmp_path):
        write(tmp_path / "plain.md", "Just some text with no headings.")
        run(str(tmp_path))
        assert (tmp_path / "plain.html").exists()

    def test_unicode_content(self, tmp_path):
        write(tmp_path / "unicode.md", "# Ünïcödé\n\nCafé naïve résumé.")
        run(str(tmp_path))
        html = (tmp_path / "unicode.html").read_text(encoding="utf-8")
        assert "Ünïcödé" in html

    def test_deeply_nested_subdirectory(self, tmp_path):
        write(tmp_path / "a" / "b" / "c" / "deep.md", "# Deep\n\nContent.")
        run(str(tmp_path))
        assert (tmp_path / "a" / "b" / "c" / "deep.html").exists()
