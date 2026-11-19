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
"""Site scaffold initialization logic."""
import shutil
from datetime import datetime
from pathlib import Path

from app.utils import atomic_write_text


_SCAFFOLD_FILES: dict[str, str] = {
  "index.md": """\
---
title: Home
description: Welcome to my site.
---

# Welcome

This is the home page of your new site, built with **hanma.py**.

Edit the Markdown files in `site/` and run `./hanma.py` to regenerate.

### What's in this scaffold?
- **[About](about.html)**: A simple secondary page.
- **[Markdown Elements](elements.html)**: A demonstration of supported Markdown extensions (TOC, Code, Tables, etc).
- **[Formatting & Meta](formatting.html)**: How to use front matter for sorting and metadata.
- **[Posts](posts/)**: An example blog directory.
""",
  "about.md": """\
---
title: About
description: A little about this site.
---

# About

Tell readers who you are and what this site is about. This page is automatically added to your navigation bar.
""",
  "elements.md": """\
---
title: Markdown Elements
description: A demonstration of Hanma's Markdown capabilities.
---

# Markdown Elements

Hanma supports a wide variety of Markdown extensions out of the box.

[TOC]

## Syntax Highlighting

Fenced code blocks are automatically highlighted using Pygments.

```python
def hello_hanma():
    print("It builds your blog. That's mostly it.")
```

## Tables

Standard GFM tables are supported.

| Feature | Support |
| --- | --- |
| TOC | Yes |
| Code Hilite | Yes |
| Tables | Yes |
| Footnotes | Yes |

## Lists

### Task Lists
- [x] Write code
- [ ] Write docs
- [ ] Profit

### Definition Lists
Hanma
: A lightweight Python SSG.

Markdown
: A lightweight markup language.

## Footnotes & Abbreviations

You can use footnotes[^1] to provide extra context. 
Also, ABBR tags work!

[^1]: This is the footnote content.

*[ABBR]: Abbreviation
""",
  "formatting.md": """\
---
title: Formatting & Meta
description: Demonstrating sort_index and metadata.
sort_index: 10
author: Chris Hammer
date: {today}
---

# Formatting & Meta

This page demonstrates how Hanma handles front matter metadata.

### Manual Sorting
The `sort_index: 10` in this page's front matter ensures it appears *after* the Home and About pages in the navigation bar (which have default lower indexes).

### Metadata
This page specifies an `author` and a `date`. Depending on your theme, these might appear in the page footer or as meta tags in the HTML head.

### Dates
The date for this page was set to `{today}` when the scaffold was created.
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

Welcome to your first post! Add more files to `site/posts/` and they will
appear in the auto-generated **Posts** listing.
""",
  "posts/second-post.md": """\
---
title: Another Post
description: Showing off multiple posts.
date: {today}
tags:
 - demo
---

# Another Post

This second post demonstrates how Hanma automatically creates a "Posts" index page and sorts entries by date (newest first).
""",
  "static/README.md": """\
# Static Directory

Files placed in the `site/static/` directory are copied **unchanged** to the `output/static/` directory during the build process.

Use this for:
- Custom CSS
- JavaScript files
- Images and downloads
- Any other assets you want to link to directly.
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
      raise RuntimeError(
        f"Error: '{site_dir}' is not empty. "
        "Re-run with --force to wipe it and create fresh sample content."
      )
    for item in real_contents:
      if item.is_dir() and not item.is_symlink():
        shutil.rmtree(item)
      else:
        item.unlink()

  site_dir.mkdir(parents=True, exist_ok=True)

  for rel, content in _SCAFFOLD_FILES.items():
    dest = site_dir / rel
    atomic_write_text(dest, content.format(today=today), encoding="utf-8")
    print(f"  [create] {rel}")

  print(f"\nScaffold written to '{site_dir}'.  Run ./hanma.py to build.")
