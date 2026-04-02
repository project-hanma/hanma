# hanma.py — It builds your blog. That's mostly it.
# Copyright (C) 2026  Chris Hammer
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see
# <https://www.gnu.org/licenses/>.
import shutil
import sys
from datetime import datetime
from pathlib import Path


_SCAFFOLD_FILES: dict[str, str] = {
  "index.md": """\
---
title: Home
description: Welcome to my site.
---

# Welcome

This is the home page of your new site, built with **hanma.py**.

Edit the Markdown files in `site/` and run `./hanma.py` to regenerate.
""",
  "about.md": """\
---
title: About
description: A little about this site.
---

# About

Tell readers who you are and what this site is about.
""",
  "posts/hello-world.md": """\
---
title: Hello, World
description: My first post.
date: {today}
tags:
 - general
---

# Hello, World

Welcome to your first post!  Add more files to `site/posts/` and they will
appear in the auto-generated **Posts** listing.
""",
}


def init_scaffold(site_dir: Path, force: bool = False) -> None:
  """Create sample content in site_dir.

  Aborts (with a helpful message) if site_dir is non-empty and force is
  False.  With force=True, the entire site_dir is wiped before writing.
  """
  today = datetime.now().strftime("%Y-%m-%d")

  # Check whether the directory has any real contents (.gitkeep is ignored)
  real_contents = [
    p for p in site_dir.iterdir() if p.name != ".gitkeep"
  ] if site_dir.is_dir() else []
  if real_contents:
    if not force:
      print(f"Error: '{site_dir}' is not empty.")
      print("Re-run with --force to wipe it and create fresh sample content.")
      sys.exit(1)
    for item in real_contents:
      if item.is_dir():
        shutil.rmtree(item)
      else:
        item.unlink()

  site_dir.mkdir(parents=True, exist_ok=True)

  for rel, content in _SCAFFOLD_FILES.items():
    dest = site_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content.format(today=today), encoding="utf-8")
    print(f"  [create] {rel}")

  print(f"\nScaffold written to '{site_dir}'.  Run ./hanma.py to build.")
