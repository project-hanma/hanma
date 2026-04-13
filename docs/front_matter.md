# Front Matter & Metadata

Any `.md` file can include an optional YAML front matter block at the very top, delimited by `---` lines. This allows you to override defaults or add specific metadata to a page.

```markdown
---
title: My Post Title
description: A short summary shown in search results.
author: Jane Doe
date: 2025-06-01
tags:
  - python
  - web
draft: false
refresh: 60
layout: post
sort_index: 2
---

# Content starts here
```

## Available Fields

All fields are optional.

| Field | Type | Effect |
|---|---|---|
| `title` | string | Overrides the auto-extracted H1 heading; prepended with the site name in the browser title |
| `description` | string | Overrides the auto-extracted first paragraph |
| `author` | string | Shown in the page footer; added as `<meta name="author">` |
| `date` | YYYY-MM-DD | Shown in the page footer alongside the author; primary sorting and display key for the posts listing (falls back to file modification time if missing) |
| `layout` | string | `page` or `post` — overrides directory-based default (`posts/` files default to `post`) |
| `tags` | list | Rendered as a tag strip below the content; generates `tags/<slug>.html` index pages; added as `<meta name="keywords">` |
| `draft` | bool | If `true`, the page is silently skipped during generation |
| `refresh` | int | Auto-refresh interval in seconds — injects `<meta http-equiv="refresh">` into the page head; omit or set to `0` to disable |
| `sort_index` | int | Navigation sort priority (starting at `1`); lower values appear earlier; pages without `sort_index` retain their default alphabetical order but appear after all pages that have one. |

## Generated Pages

Hanma automatically generates several functional pages based on your content and configuration:

| Page | Description |
|---|---|
| `tags/<slug>.html` | Created if any page uses the `tags` front matter field. Lists all pages with that tag. |
| `posts/index.html` | Lists all pages with `layout: post` (automatic for files in `posts/`). Sorted newest-first by date. |
| `sitemap.xml` | Generated if `--base-url` is set. |
| `search.json` | Always generated; contains the search index used by the theme's search box. |
