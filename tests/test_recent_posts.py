import pytest
from tests.helpers import run_hanma, write_file

def test_recent_posts_dropdown(tmp_path):
  # Set up a site with 7 posts
  write_file(tmp_path / "index.md", "# Home\n\nWelcome.")
  for i in range(1, 8):
    # Use dates to ensure order
    write_file(tmp_path / "posts" / f"post{i}.md", 
               f"---\ntitle: Post {i}\ndate: 2026-04-0{i}\n---\nPost content {i}.")
  
  out_dir = tmp_path / "out"
  run_hanma(str(tmp_path), "--output", str(out_dir))
  
  index_html = (out_dir / "index.html").read_text(encoding="utf-8")
  
  # Should find Post 7, 6, 5, 4, 3 (the 5 newest)
  # Should NOT find Post 2, 1 in the dropdown
  for i in range(3, 8):
      assert f"Post {i}" in index_html
  
  for i in range(1, 3):
      assert f"Post {i}" not in index_html
  
  # Should find the "More posts..." link and its styling
  assert 'href="posts/index.html"' in index_html
  assert "nav-more-posts" in index_html
  assert "nav-more-posts-sep" in index_html

if __name__ == "__main__":
  pytest.main([__file__])
