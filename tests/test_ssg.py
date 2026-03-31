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
        out_dir = tmp_path / "out"
        run(str(src), "--output", str(out_dir))
        assert (out_dir / "page.html").exists()

    def test_converts_directory(self, tmp_path):
        write(tmp_path / "a.md", "# A\n\nContent.")
        write(tmp_path / "b.md", "# B\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert (out_dir / "a.html").exists()
        assert (out_dir / "b.html").exists()

    def test_recurses_into_subdirs(self, tmp_path):
        write(tmp_path / "sub" / "page.md", "# Sub\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert (out_dir / "sub" / "page.html").exists()

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
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--name", "MyAwesomeSite")
        html = (out_dir / "page.html").read_text()
        assert "MyAwesomeSite" in html


# ===========================================================================
# 10. Navigation
# ===========================================================================


class TestNavigation:
    def test_nav_links_present_for_multiple_pages(self, tmp_path):
        write(tmp_path / "index.md", "# Home\n\nWelcome.")
        write(tmp_path / "about.md", "# About\n\nInfo.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        html = (out_dir / "index.html").read_text()
        assert "about.html" in html

    def test_current_page_marked(self, tmp_path):
        write(tmp_path / "index.md", "# Home\n\nWelcome.")
        write(tmp_path / "about.md", "# About\n\nInfo.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        html = (out_dir / "about.html").read_text()
        assert 'aria-current="page"' in html

    def test_index_labelled_home(self, tmp_path):
        write(tmp_path / "index.md", "# Welcome\n\nContent.")
        write(tmp_path / "other.md", "# Other\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        html = (out_dir / "other.html").read_text()
        assert "Home" in html

    def test_index_link_appears_before_other_pages(self, tmp_path):
        write(tmp_path / "index.md", "# Home\n\nContent.")
        write(tmp_path / "about.md", "# About\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        html = (out_dir / "about.html").read_text()
        assert html.index("index.html") < html.index("about.html")


# ===========================================================================
# 11. Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_empty_file_does_not_crash(self, tmp_path):
        write(tmp_path / "empty.md", "")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert (out_dir / "empty.html").exists()

    def test_file_with_no_headings(self, tmp_path):
        write(tmp_path / "plain.md", "Just some text with no headings.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert (out_dir / "plain.html").exists()

    def test_unicode_content(self, tmp_path):
        write(tmp_path / "unicode.md", "# Ünïcödé\n\nCafé naïve résumé.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        html = (out_dir / "unicode.html").read_text(encoding="utf-8")
        assert "Ünïcödé" in html

    def test_deeply_nested_subdirectory(self, tmp_path):
        write(tmp_path / "a" / "b" / "c" / "deep.md", "# Deep\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert (out_dir / "a" / "b" / "c" / "deep.html").exists()


# ===========================================================================
# 12. Front matter — parse_front_matter()
# ===========================================================================


class TestParseFrontMatter:
    def test_no_front_matter_returns_empty_dict(self):
        meta, body = ssg.parse_front_matter("# Hello\n\nContent.")
        assert meta == {}
        assert "Hello" in body

    def test_front_matter_stripped_from_body(self):
        md = "---\ntitle: My Title\n---\n# Hello\n\nContent."
        meta, body = ssg.parse_front_matter(md)
        assert "title:" not in body
        assert "---" not in body

    def test_title_field_parsed(self):
        md = "---\ntitle: My Title\n---\nContent."
        meta, _ = ssg.parse_front_matter(md)
        assert meta["title"] == "My Title"

    def test_author_field_parsed(self):
        md = "---\nauthor: Jane Doe\n---\nContent."
        meta, _ = ssg.parse_front_matter(md)
        assert meta["author"] == "Jane Doe"

    def test_date_field_parsed(self):
        md = "---\ndate: 2025-06-01\n---\nContent."
        meta, _ = ssg.parse_front_matter(md)
        assert meta["date"] is not None

    def test_tags_field_parsed_as_list(self):
        md = "---\ntags:\n  - python\n  - web\n---\nContent."
        meta, _ = ssg.parse_front_matter(md)
        assert isinstance(meta["tags"], list)
        assert "python" in meta["tags"]

    def test_draft_field_parsed(self):
        md = "---\ndraft: true\n---\nContent."
        meta, _ = ssg.parse_front_matter(md)
        assert meta["draft"] is True

    def test_malformed_yaml_returns_empty_dict(self):
        md = "---\n: bad: yaml: {\n---\nContent."
        meta, body = ssg.parse_front_matter(md)
        assert meta == {}

    def test_unclosed_front_matter_ignored(self):
        md = "---\ntitle: Oops\nContent with no closing delimiter."
        meta, body = ssg.parse_front_matter(md)
        assert meta == {}
        assert body == md


# ===========================================================================
# 13. Front matter — integration with convert_md_to_html
# ===========================================================================


class TestFrontMatterIntegration:
    def test_title_from_front_matter_overrides_h1(self, tmp_path):
        src = write(tmp_path / "page.md",
                    "---\ntitle: FM Title\n---\n# H1 Title\n\nContent.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html = out.read_text()
        assert "FM Title" in html

    def test_description_from_front_matter(self, tmp_path):
        src = write(tmp_path / "page.md",
                    "---\ndescription: Custom desc.\n---\n# Title\n\nOther text.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html = out.read_text()
        assert "Custom desc." in html

    def test_author_appears_in_output(self, tmp_path):
        src = write(tmp_path / "page.md",
                    "---\nauthor: Jane Doe\n---\n# Title\n\nContent.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html = out.read_text()
        assert "Jane Doe" in html

    def test_date_appears_in_output(self, tmp_path):
        src = write(tmp_path / "page.md",
                    "---\ndate: 2025-06-01\n---\n# Title\n\nContent.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html = out.read_text()
        assert "2025" in html

    def test_tags_rendered_in_output(self, tmp_path):
        src = write(tmp_path / "page.md",
                    "---\ntags:\n  - python\n  - web\n---\n# Title\n\nContent.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html = out.read_text()
        assert "python" in html
        assert "web" in html

    def test_keywords_meta_tag_present(self, tmp_path):
        src = write(tmp_path / "page.md",
                    "---\ntags:\n  - python\n---\n# Title\n\nContent.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html = out.read_text()
        assert 'name="keywords"' in html

    def test_author_meta_tag_present(self, tmp_path):
        src = write(tmp_path / "page.md",
                    "---\nauthor: Jane\n---\n# Title\n\nContent.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html = out.read_text()
        assert 'name="author"' in html

    def test_draft_page_skipped_by_cli(self, tmp_path):
        write(tmp_path / "draft.md", "---\ndraft: true\n---\n# Draft\n\nContent.")
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert not (out_dir / "draft.html").exists()
        assert (out_dir / "page.html").exists()

    def test_no_front_matter_still_works(self, tmp_path):
        src = write(tmp_path / "plain.md", "# Plain\n\nNo front matter.")
        out = tmp_path / "plain.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        assert out.exists()
        html = out.read_text()
        assert "Plain" in html


# ===========================================================================
# 14. Themes
# ===========================================================================


class TestThemes:
    def test_default_theme_loads(self):
        template, theme_dir = ssg.load_theme("default")
        import string
        assert isinstance(template, string.Template)
        assert "$title" in template.template
        assert theme_dir.name == "default"

    def test_missing_theme_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(SSG), "--theme", "nonexistent", str(SSG.parent / "site")],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "not found" in result.stdout + result.stderr

    def test_theme_flag_accepted(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--theme", "default")
        assert (out_dir / "page.html").exists()

    def test_theme_assets_copied_to_output(self, tmp_path):
        import string
        # Create a minimal custom theme with an extra asset
        theme_dir = tmp_path / "themes" / "custom"
        theme_dir.mkdir(parents=True)
        # Write a minimal template with all required placeholders
        default_template = (ssg._THEMES_DIR / "default" / "template.html").read_text()
        (theme_dir / "template.html").write_text(default_template)
        (theme_dir / "custom.css").write_text("body { color: red; }")

        out_dir = tmp_path / "dist"
        out_dir.mkdir()

        original_themes_dir = ssg._THEMES_DIR
        ssg._THEMES_DIR = tmp_path / "themes"
        try:
            ssg.copy_theme_assets(theme_dir, out_dir)
        finally:
            ssg._THEMES_DIR = original_themes_dir

        assert (out_dir / "custom.css").exists()
        assert not (out_dir / "template.html").exists()

    def test_template_html_not_copied_as_asset(self, tmp_path):
        out_dir = tmp_path / "dist"
        out_dir.mkdir()
        theme_dir = ssg._THEMES_DIR / "default"
        ssg.copy_theme_assets(theme_dir, out_dir)
        assert not (out_dir / "template.html").exists()


# ===========================================================================
# 15. Security — XSS escaping in front-matter fields
# ===========================================================================


class TestXSSEscaping:
    def test_title_xss_escaped(self, tmp_path):
        src = write(tmp_path / "page.md",
                    '---\ntitle: "</title><script>alert(1)</script>"\n---\nContent.')
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html_text = out.read_text()
        assert "<script>alert(1)</script>" not in html_text
        assert "&lt;script&gt;" in html_text

    def test_author_xss_escaped_in_author_line(self, tmp_path):
        src = write(tmp_path / "page.md",
                    '---\nauthor: "</em><script>xss</script>"\n---\n# T\n\nContent.')
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html_text = out.read_text()
        assert "<script>xss</script>" not in html_text

    def test_site_name_xss_escaped(self, tmp_path):
        src = write(tmp_path / "page.md", "# T\n\nContent.")
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, '<script>evil</script>', nav_pages=[])
        html_text = out.read_text()
        assert "<script>evil</script>" not in html_text

    def test_nav_title_xss_escaped(self, tmp_path):
        src = write(tmp_path / "page.md", "# T\n\nContent.")
        out = tmp_path / "page.html"
        nav_pages = [(out, '<script>nav</script>')]
        ssg.convert_md_to_html(src, out, "S", nav_pages=nav_pages)
        html_text = out.read_text()
        assert "<script>nav</script>" not in html_text

    def test_description_xss_escaped(self, tmp_path):
        src = write(tmp_path / "page.md",
                    '---\ndescription: "<script>desc</script>"\n---\n# T\n\nContent.')
        out = tmp_path / "page.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        html_text = out.read_text()
        assert "<script>desc</script>" not in html_text


# ===========================================================================
# 16. Port handling — B1 (--serve --port N)
# ===========================================================================


class TestPortHandling:
    def test_serve_port_flag_accepted(self):
        # --serve --port N should not crash at argument parsing level
        result = subprocess.run(
            [sys.executable, str(SSG), "--help"],
            capture_output=True,
            text=True,
        )
        assert "--port" in result.stdout
        assert "--serve" in result.stdout


# ===========================================================================
# 17. YAML warning — S5/U2 (malformed front matter emits warning)
# ===========================================================================


class TestMalformedYAMLWarning:
    def test_malformed_yaml_prints_warning(self, capsys):
        md = "---\n: bad: yaml: {\n---\nContent."
        meta, _ = ssg.parse_front_matter(md, source_path=Path("test.md"))
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower() or "malformed" in captured.err.lower()

    def test_malformed_yaml_integration_generates_html(self, tmp_path):
        src = write(tmp_path / "bad.md", "---\n: bad: yaml: {\n---\n# Title\n\nContent.")
        out = tmp_path / "bad.html"
        ssg.convert_md_to_html(src, out, "S", nav_pages=[])
        assert out.exists()
        assert "Title" in out.read_text()


# ===========================================================================
# 18. Navigation relative URLs — T2
# ===========================================================================


class TestNavRelativeURLs:
    def test_nav_link_from_subdir_to_index_is_relative(self, tmp_path):
        write(tmp_path / "index.md", "# Home\n\nWelcome.")
        write(tmp_path / "posts" / "hello.md", "# Hello\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        html = (out_dir / "posts" / "hello.html").read_text()
        # Link from posts/hello.html to index.html must go up one level
        assert "../index.html" in html

    def test_nav_link_from_index_to_subdir_page(self, tmp_path):
        write(tmp_path / "index.md", "# Home\n\nWelcome.")
        write(tmp_path / "posts" / "hello.md", "# Hello\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        html = (out_dir / "index.html").read_text()
        assert "posts/hello.html" in html


# ===========================================================================
# 19. Draft count in summary — U4
# ===========================================================================


class TestDraftSummary:
    def test_draft_count_in_summary(self, tmp_path):
        write(tmp_path / "draft.md", "---\ndraft: true\n---\n# Draft\n\nContent.")
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        result = run(str(tmp_path), "--output", str(out_dir))
        assert "draft" in result.stdout.lower()
        assert "1" in result.stdout


# ===========================================================================
# 20. --list-themes flag — U7
# ===========================================================================


class TestListThemes:
    def test_list_themes_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(SSG), "--list-themes"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_list_themes_shows_default(self):
        result = subprocess.run(
            [sys.executable, str(SSG), "--list-themes"],
            capture_output=True,
            text=True,
        )
        assert "default" in result.stdout


# ===========================================================================
# 21. Tag index pages
# ===========================================================================


class TestTagIndexPages:
    def test_tag_index_pages_generated(self, tmp_path):
        write(tmp_path / "page.md",
              "---\ntags:\n  - python\n  - web\n---\n# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert (out_dir / "tags" / "python.html").exists()
        assert (out_dir / "tags" / "web.html").exists()

    def test_tag_index_lists_tagged_page(self, tmp_path):
        write(tmp_path / "page.md",
              "---\ntags:\n  - python\n---\n# My Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        tag_html = (out_dir / "tags" / "python.html").read_text()
        assert "My Page" in tag_html

    def test_tag_index_title_contains_tag_name(self, tmp_path):
        write(tmp_path / "page.md",
              "---\ntags:\n  - python\n---\n# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        tag_html = (out_dir / "tags" / "python.html").read_text()
        assert "python" in tag_html

    def test_tag_links_in_page_content(self, tmp_path):
        write(tmp_path / "page.md",
              "---\ntags:\n  - python\n---\n# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        page_html = (out_dir / "page.html").read_text()
        # Tag should be a link pointing into tags/
        assert "tags/python.html" in page_html or "../tags/python.html" in page_html

    def test_tag_slug_normalizes_special_chars(self, tmp_path):
        write(tmp_path / "page.md",
              "---\ntags:\n  - 'my tag'\n---\n# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        # "my tag" → "my-tag"
        assert (out_dir / "tags" / "my-tag.html").exists()

    def test_multiple_pages_same_tag(self, tmp_path):
        write(tmp_path / "a.md", "---\ntags:\n  - python\n---\n# A\n\nContent.")
        write(tmp_path / "b.md", "---\ntags:\n  - python\n---\n# B\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        tag_html = (out_dir / "tags" / "python.html").read_text()
        assert "A" in tag_html
        assert "B" in tag_html

    def test_no_tag_pages_when_no_tags(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert not (out_dir / "tags").exists()

    def test_build_tag_index_html_function(self, tmp_path):
        out_path = tmp_path / "tags" / "python.html"
        pages = [(tmp_path / "page.html", "My Page", "March 01, 2025")]
        (tmp_path / "page.html").write_text("<html></html>")
        template, _ = ssg.load_theme("default")
        ssg.build_tag_index_html("python", pages, out_path, "Test", [], template)
        assert out_path.exists()
        html_text = out_path.read_text()
        assert "python" in html_text
        assert "My Page" in html_text


# ===========================================================================
# 22. Sitemap generation
# ===========================================================================


class TestSitemap:
    def test_sitemap_generated_with_base_url(self, tmp_path):
        write(tmp_path / "index.md", "# Home\n\nWelcome.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--base-url", "https://example.com")
        assert (out_dir / "sitemap.xml").exists()

    def test_sitemap_contains_page_urls(self, tmp_path):
        write(tmp_path / "index.md", "# Home\n\nWelcome.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--base-url", "https://example.com")
        sitemap = (out_dir / "sitemap.xml").read_text()
        assert "https://example.com" in sitemap
        assert "index.html" in sitemap

    def test_sitemap_not_generated_without_base_url(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert not (out_dir / "sitemap.xml").exists()

    def test_sitemap_is_valid_xml(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--base-url", "https://example.com")
        import xml.etree.ElementTree as ET
        tree = ET.parse(out_dir / "sitemap.xml")
        root_elem = tree.getroot()
        assert "urlset" in root_elem.tag

    def test_build_sitemap_xml_function_no_base_url(self, tmp_path):
        result = ssg.build_sitemap_xml([], tmp_path, "")
        assert result is None
        assert not (tmp_path / "sitemap.xml").exists()


# ===========================================================================
# 23. Site config file (ssg.yaml)
# ===========================================================================


class TestSiteConfig:
    def test_load_site_config_reads_name(self, tmp_path):
        (tmp_path / "ssg.yaml").write_text("name: My Config Site\n")
        config = ssg.load_site_config(tmp_path / "ssg.yaml")
        assert config.get("name") == "My Config Site"

    def test_load_site_config_returns_empty_when_missing(self, tmp_path):
        config = ssg.load_site_config(tmp_path / "ssg.yaml")
        assert config == {}

    def test_load_site_config_reads_base_url(self, tmp_path):
        (tmp_path / "ssg.yaml").write_text("base_url: https://example.com\n")
        config = ssg.load_site_config(tmp_path / "ssg.yaml")
        assert config.get("base_url") == "https://example.com"

    def test_load_site_config_reads_theme(self, tmp_path):
        (tmp_path / "ssg.yaml").write_text("theme: default\n")
        config = ssg.load_site_config(tmp_path / "ssg.yaml")
        assert config.get("theme") == "default"

    def test_site_config_name_used_in_output(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        cfg = tmp_path / "ssg.yaml"
        cfg.write_text("name: ConfigSiteName\n")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--config", str(cfg))
        page_html = (out_dir / "page.html").read_text()
        assert "ConfigSiteName" in page_html

    def test_cli_name_overrides_config(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        (tmp_path / "ssg.yaml").write_text("name: ConfigName\n")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--name", "CLIName")
        page_html = (out_dir / "page.html").read_text()
        assert "CLIName" in page_html
        assert "ConfigName" not in page_html

    def test_malformed_config_returns_empty(self, tmp_path):
        (tmp_path / "ssg.yaml").write_text(": bad: yaml: {\n")
        config = ssg.load_site_config(tmp_path / "ssg.yaml")
        assert config == {}

    def test_custom_config_path_flag(self, tmp_path):
        cfg_path = tmp_path / "custom.yaml"
        cfg_path.write_text("name: CustomPathSite\n")
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--config", str(cfg_path))
        page_html = (out_dir / "page.html").read_text()
        assert "CustomPathSite" in page_html

    def test_load_site_config_reads_serve(self, tmp_path):
        (tmp_path / "ssg.yml").write_text("serve: true\nport: 9000\n")
        config = ssg.load_site_config(tmp_path / "ssg.yml")
        assert config.get("serve") is True
        assert config.get("port") == 9000

    def test_load_site_config_reads_watch(self, tmp_path):
        (tmp_path / "ssg.yml").write_text("watch: true\n")
        config = ssg.load_site_config(tmp_path / "ssg.yml")
        assert config.get("watch") is True

    def test_load_site_config_reads_incremental(self, tmp_path):
        (tmp_path / "ssg.yml").write_text("incremental: true\n")
        config = ssg.load_site_config(tmp_path / "ssg.yml")
        assert config.get("incremental") is True

    def test_load_site_config_prefers_ssg_yml_over_ssg_yaml(self, tmp_path):
        (tmp_path / "ssg.yml").write_text("name: FromYml\n")
        (tmp_path / "ssg.yaml").write_text("name: FromYaml\n")
        # load_site_config takes an explicit path; the lookup preference is in main()
        config = ssg.load_site_config(tmp_path / "ssg.yml")
        assert config.get("name") == "FromYml"

    def test_default_conf_dir_ssg_yml_loaded(self):
        """conf/ssg.yml next to ssg.py is loaded without any --config flag."""
        conf_yml = SSG.parent / "conf" / "ssg.yml"
        assert conf_yml.is_file(), "conf/ssg.yml must exist"
        config = ssg.load_site_config(conf_yml)
        # The shipped default must at minimum define 'name'
        assert "name" in config


# ===========================================================================
# 24. Static asset passthrough
# ===========================================================================


class TestStaticAssets:
    def test_static_dir_copied_to_output(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        (tmp_path / "static").mkdir()
        (tmp_path / "static" / "logo.png").write_bytes(b"\x89PNG\r\n")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert (out_dir / "static" / "logo.png").exists()

    def test_static_subdirs_copied(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        (tmp_path / "static" / "images").mkdir(parents=True)
        (tmp_path / "static" / "images" / "photo.jpg").write_bytes(b"JFIF")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert (out_dir / "static" / "images" / "photo.jpg").exists()

    def test_no_static_dir_no_error(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))  # must not raise

    def test_copy_static_assets_function(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        dst.mkdir()
        (src / "static").mkdir(parents=True)
        (src / "static" / "style.css").write_text("body {}")
        ssg.copy_static_assets(src, dst)
        assert (dst / "static" / "style.css").exists()

    def test_copy_static_assets_no_static_dir(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        dst = tmp_path / "dst"
        dst.mkdir()
        ssg.copy_static_assets(src, dst)  # should not raise


# ===========================================================================
# 25. Search index (search.json)
# ===========================================================================


class TestSearchIndex:
    def test_search_json_generated(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert (out_dir / "search.json").exists()

    def test_search_json_contains_page_title(self, tmp_path):
        write(tmp_path / "page.md", "# My Title\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        import json as _json
        entries = _json.loads((out_dir / "search.json").read_text())
        titles = [e["title"] for e in entries]
        assert "My Title" in titles

    def test_search_json_contains_description(self, tmp_path):
        write(tmp_path / "page.md",
              "---\ndescription: A custom description.\n---\n# Title\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        import json as _json
        entries = _json.loads((out_dir / "search.json").read_text())
        descs = [e["description"] for e in entries]
        assert "A custom description." in descs

    def test_search_json_contains_tags(self, tmp_path):
        write(tmp_path / "page.md",
              "---\ntags:\n  - python\n---\n# Title\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        import json as _json
        entries = _json.loads((out_dir / "search.json").read_text())
        all_tags = [t for e in entries for t in e.get("tags", [])]
        assert "python" in all_tags

    def test_search_json_url_is_relative(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        import json as _json
        entries = _json.loads((out_dir / "search.json").read_text())
        for e in entries:
            assert not e["url"].startswith("http")

    def test_search_json_url_absolute_with_base_url(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--base-url", "https://example.com")
        import json as _json
        entries = _json.loads((out_dir / "search.json").read_text())
        for e in entries:
            assert e["url"].startswith("https://example.com")

    def test_build_search_json_function(self, tmp_path):
        import json as _json
        entries = [{"title": "T", "description": "D", "url": "t.html", "tags": []}]
        ssg.build_search_json(entries, tmp_path)
        result = _json.loads((tmp_path / "search.json").read_text())
        assert result[0]["title"] == "T"


# ===========================================================================
# 26. Post listing page
# ===========================================================================


class TestPostListingPage:
    def test_posts_html_generated_when_dated_pages_exist(self, tmp_path):
        write(tmp_path / "post.md",
              "---\ndate: 2025-01-01\n---\n# My Post\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert (out_dir / "posts.html").exists()

    def test_posts_html_not_generated_when_no_dated_pages(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        assert not (out_dir / "posts.html").exists()

    def test_posts_html_lists_dated_pages(self, tmp_path):
        write(tmp_path / "post.md",
              "---\ndate: 2025-03-01\n---\n# My Dated Post\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        posts_html = (out_dir / "posts.html").read_text()
        assert "My Dated Post" in posts_html

    def test_posts_html_sorted_newest_first(self, tmp_path):
        write(tmp_path / "old.md",
              "---\ndate: 2024-01-01\n---\n# Old Post\n\nContent.")
        write(tmp_path / "new.md",
              "---\ndate: 2025-06-01\n---\n# New Post\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        posts_html = (out_dir / "posts.html").read_text()
        assert posts_html.index("New Post") < posts_html.index("Old Post")

    def test_posts_html_skipped_when_posts_md_exists(self, tmp_path):
        write(tmp_path / "post.md",
              "---\ndate: 2025-01-01\n---\n# A Post\n\nContent.")
        write(tmp_path / "posts.md", "# My Posts\n\nManual listing.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir))
        # posts.html should exist but be the rendered posts.md, not auto-generated
        posts_html = (out_dir / "posts.html").read_text()
        assert "My Posts" in posts_html

    def test_build_posts_listing_html_function(self, tmp_path):
        from datetime import datetime
        out_path = tmp_path / "posts.html"
        template, _ = ssg.load_theme("default")
        dated = [(tmp_path / "post.html", "My Post", datetime(2025, 3, 1), "A description")]
        ssg.build_posts_listing_html(dated, out_path, "Test", [], template)
        assert out_path.exists()
        html_text = out_path.read_text()
        assert "My Post" in html_text
        assert "All Posts" in html_text


# ===========================================================================
# 27. Incremental builds
# ===========================================================================


class TestIncrementalBuilds:
    def test_incremental_flag_accepted(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--incremental")
        assert (out_dir / "page.html").exists()

    def test_manifest_file_created(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--incremental")
        assert (out_dir / ".ssg_manifest.json").exists()

    def test_unchanged_page_skipped_on_second_build(self, tmp_path):
        write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--incremental")
        result = run(str(tmp_path), "--output", str(out_dir), "--incremental")
        assert "skip" in result.stdout.lower() or "unchanged" in result.stdout.lower()

    def test_changed_page_rebuilt(self, tmp_path):
        md = write(tmp_path / "page.md", "# Page\n\nContent.")
        out_dir = tmp_path / "out"
        run(str(tmp_path), "--output", str(out_dir), "--incremental")
        # Modify the file and bump its mtime
        md.write_text("# Page\n\nUpdated content.")
        import os as _os
        _os.utime(md, None)
        result = run(str(tmp_path), "--output", str(out_dir), "--incremental")
        assert "skip" not in result.stdout.lower() or "Updated" in (out_dir / "page.html").read_text()

    def test_page_needs_rebuild_missing_output(self, tmp_path):
        md = write(tmp_path / "page.md", "# Page\n\nContent.")
        out_html = tmp_path / "page.html"
        assert ssg.page_needs_rebuild(md, out_html, {}, 0.0) is True

    def test_page_needs_rebuild_unchanged(self, tmp_path):
        md = write(tmp_path / "page.md", "# Page\n\nContent.")
        out_html = tmp_path / "page.html"
        out_html.write_text("<html></html>")
        mtime = md.stat().st_mtime
        manifest = {str(md): mtime, "_template_mtime": 0.0}
        assert ssg.page_needs_rebuild(md, out_html, manifest, 0.0) is False

    def test_page_needs_rebuild_template_changed(self, tmp_path):
        md = write(tmp_path / "page.md", "# Page\n\nContent.")
        out_html = tmp_path / "page.html"
        out_html.write_text("<html></html>")
        mtime = md.stat().st_mtime
        manifest = {str(md): mtime, "_template_mtime": 0.0}
        # Template mtime is newer than manifest records
        assert ssg.page_needs_rebuild(md, out_html, manifest, mtime + 1.0) is True

    def test_load_save_manifest_roundtrip(self, tmp_path):
        manifest_path = tmp_path / ".ssg_manifest.json"
        data = {"/some/path.md": 1234567890.0, "_template_mtime": 9876543.0}
        ssg.save_build_manifest(manifest_path, data)
        loaded = ssg.load_build_manifest(manifest_path)
        assert loaded == data

    def test_load_manifest_missing_file(self, tmp_path):
        result = ssg.load_build_manifest(tmp_path / ".ssg_manifest.json")
        assert result == {}


# ===========================================================================
# 28. inotify/watchdog-based watch (unit-level checks)
# ===========================================================================


class TestWatchdogWatch:
    def test_watchdog_available(self):
        assert ssg._WATCHDOG_AVAILABLE is True

    def test_ssg_event_handler_relevance(self, tmp_path):
        handler = ssg._SsgEventHandler(lambda: None, tmp_path, tmp_path)
        assert handler._is_relevant("file.md") is True
        assert handler._is_relevant("file.html") is False  # output files must not trigger rebuild
        assert handler._is_relevant("file.yaml") is True
        assert handler._is_relevant("file.png") is False
        assert handler._is_relevant("file.txt") is False

    def test_ssg_event_handler_ignores_open_close_events(self, tmp_path):
        from watchdog.events import FileOpenedEvent, FileClosedEvent, FileModifiedEvent
        triggered = []
        handler = ssg._SsgEventHandler(lambda: triggered.append(1), tmp_path, tmp_path)
        handler.on_any_event(FileOpenedEvent(str(tmp_path / "file.md")))
        handler.on_any_event(FileClosedEvent(str(tmp_path / "file.md")))
        assert triggered == [], "open/close events must not trigger rebuild"
        handler.on_any_event(FileModifiedEvent(str(tmp_path / "file.md")))
        import time; time.sleep(0.4)
        assert triggered == [1], "modify event must trigger rebuild"

    def test_watch_and_rebuild_signature_accepts_base_url(self, tmp_path):
        import inspect
        sig = inspect.signature(ssg.watch_and_rebuild)
        assert "base_url" in sig.parameters


# ---------------------------------------------------------------------------
# --init scaffold
# ---------------------------------------------------------------------------

class TestInitScaffold:

    def test_init_creates_scaffold_files(self, tmp_path):
        site_dir = tmp_path / "site"
        ssg.init_scaffold(site_dir)
        assert (site_dir / "index.md").is_file()
        assert (site_dir / "about.md").is_file()
        assert (site_dir / "posts" / "hello-world.md").is_file()

    def test_init_index_contains_expected_content(self, tmp_path):
        site_dir = tmp_path / "site"
        ssg.init_scaffold(site_dir)
        content = (site_dir / "index.md").read_text()
        assert "title: Home" in content
        assert "# Welcome" in content

    def test_init_post_has_today_date(self, tmp_path):
        from datetime import datetime
        site_dir = tmp_path / "site"
        ssg.init_scaffold(site_dir)
        content = (site_dir / "posts" / "hello-world.md").read_text()
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in content

    def test_init_aborts_if_dir_non_empty_without_force(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.md").write_text("existing")
        with pytest.raises(SystemExit):
            ssg.init_scaffold(site_dir, force=False)
        # existing file must survive untouched
        assert (site_dir / "index.md").read_text() == "existing"

    def test_init_aborts_on_any_file_not_just_scaffold_names(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "unrelated.txt").write_text("keep me")
        with pytest.raises(SystemExit):
            ssg.init_scaffold(site_dir, force=False)
        assert (site_dir / "unrelated.txt").exists()

    def test_init_force_wipes_dir_and_creates_scaffold(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        extra = site_dir / "extra.md"
        extra.write_text("should be gone")
        ssg.init_scaffold(site_dir, force=True)
        # extra file wiped
        assert not extra.exists()
        # scaffold files present
        assert "# Welcome" in (site_dir / "index.md").read_text()

    def test_init_cli_flag(self, tmp_path):
        run("--init", cwd=tmp_path)
        assert (tmp_path / "site" / "index.md").is_file()
        assert (tmp_path / "site" / "about.md").is_file()
        assert (tmp_path / "site" / "posts" / "hello-world.md").is_file()

    def test_init_cli_exits_on_non_empty_dir_without_force(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.md").write_text("existing")
        result = run("--init", cwd=tmp_path, expect_ok=False)
        assert result.returncode != 0
        assert (site_dir / "index.md").read_text() == "existing"

    def test_init_cli_force_wipes_and_rescaffolds(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        extra = site_dir / "extra.md"
        extra.write_text("gone")
        run("--init", "--force", cwd=tmp_path)
        assert not extra.exists()
        assert "# Welcome" in (site_dir / "index.md").read_text()
