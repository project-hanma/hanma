import os
import shutil
import subprocess
from pathlib import Path
import pytest

def write(path, content):
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(content, encoding="utf-8")

def run(src, *args):
  cmd = ["python3", str(Path(__file__).parent.parent / "hanma.py"), src] + list(args)
  return subprocess.run(cmd, capture_output=True, text=True)

def test_recent_posts_dropdown(tmp_path):
  # Set up a site with 7 posts
  write(tmp_path / "index.md", "# Home\n\nWelcome.")
  for i in range(1, 8):
    # Use dates to ensure order
    write(tmp_path / "posts" / f"post{i}.md", f"---\ntitle: Post {i}\ndate: 2026-04-0{i}\n---\nPost content {i}.")
  
  out_dir = tmp_path / "out"
  run(str(tmp_path), "--output", str(out_dir))
  
  index_html = (out_dir / "index.html").read_text()
  
  # Should find Post 7, 6, 5, 4, 3 (the 5 newest)
  # Should NOT find Post 2, 1 in the dropdown
  assert "Post 7" in index_html
  assert "Post 6" in index_html
  assert "Post 5" in index_html
  assert "Post 4" in index_html
  assert "Post 3" in index_html
  assert "Post 2" not in index_html
  assert "Post 1" not in index_html
  
  # Should find the "More posts..." link
  assert 'href="posts/index.html"><span class="nav-more-posts-sep"></span><span class="nav-more-posts">More posts...</span></a>' in index_html
  # Should find the separator
  assert "nav-more-posts-sep" in index_html
  # Should find the special class
  assert "nav-more-posts" in index_html

if __name__ == "__main__":
  pytest.main([__file__])
