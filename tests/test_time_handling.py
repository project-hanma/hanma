
import os
import time
from tests.helpers import run_hanma, write_file

class TestTimeHandling:
  def test_front_matter_date_overrides_mtime_for_sorting(self, tmp_path):
    # Create two posts where the one with the older mtime has a newer front-matter date.
    old_post = tmp_path / "posts" / "old_mtime.md"
    new_post = tmp_path / "posts" / "new_mtime.md"
    
    # 2025-05-01 is newer than 2025-04-01
    write_file(old_post, "---\ndate: 2025-05-01\n---\n# Newer Date Old Mtime\n\nContent.")
    write_file(new_post, "---\ndate: 2025-04-01\n---\n# Older Date New Mtime\n\nContent.")
    
    # Set mtime of old_post to be much older than new_post
    t1 = time.time() - 10000
    t2 = time.time()
    os.utime(old_post, (t1, t1))
    os.utime(new_post, (t2, t2))
    
    out_dir = tmp_path / "out"
    run_hanma(str(tmp_path), "--output", str(out_dir))
    
    posts_html = (out_dir / "posts" / "index.html").read_text(encoding="utf-8")
    
    # "Newer Date Old Mtime" (2025-05-01) should appear BEFORE "Older Date New Mtime" (2025-04-01)
    # despite having an older filesystem mtime.
    assert posts_html.index("Newer Date Old Mtime") < posts_html.index("Older Date New Mtime")
    
    # Verify display date format for front-matter dates (midnight)
    assert "5/1/2025" in posts_html
    assert "4/1/2025" in posts_html
    # It should NOT have the time part if it's midnight
    assert "5/1/2025 @" not in posts_html

  def test_fallback_to_mtime_when_date_missing(self, tmp_path):
    # One post has front-matter date, another doesn't.
    dated_post = tmp_path / "posts" / "dated.md"
    undated_post = tmp_path / "posts" / "undated.md"
    
    write_file(dated_post, "---\ndate: 2025-01-01\n---\n# Dated\n\nContent.")
    write_file(undated_post, "# Undated\n\nContent.")
    
    # Set undated_post to be newer than dated_post's front matter date.
    t_new = time.mktime(time.strptime("2025-02-01", "%Y-%m-%d"))
    os.utime(undated_post, (t_new, t_new))
    
    out_dir = tmp_path / "out"
    run_hanma(str(tmp_path), "--output", str(out_dir))
    
    posts_html = (out_dir / "posts" / "index.html").read_text(encoding="utf-8")
    
    # "Undated" (2025-02-01 mtime) should appear BEFORE "Dated" (2025-01-01 FM date)
    assert posts_html.index("Undated") < posts_html.index("Dated")
