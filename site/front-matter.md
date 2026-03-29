---
title: Front Matter Reference
description: A guide to using YAML front matter in ssg.py to control per-page metadata.
author: Chris
date: 2026-03-29
tags:
  - front-matter
  - yaml
  - metadata
---

# Front Matter Reference

Front matter is an optional YAML block placed at the very top of any Markdown
file, delimited by `---` lines. It lets you control per-page metadata without
touching the generator itself.

## Basic structure

```markdown
---
title: My Page Title
description: A short summary for search engines.
author: Jane Doe
date: 2025-06-01
tags:
  - example
  - guide
draft: false
---

Your Markdown content starts here.
```

The block must begin on the very first line of the file. Everything between the
opening and closing `---` is parsed as YAML.

## Supported fields

### `title`

Overrides the page title that would otherwise be extracted from the first `#`
heading in the file. Also used as the link label in the navigation bar.

```yaml
title: My Custom Title
```

### `description`

Overrides the auto-extracted description (normally the first paragraph of the
file). Appears as the `<meta name="description">` tag in the page `<head>`.

```yaml
description: A concise summary shown in search engine results.
```

### `author`

Displays an attribution line in the page footer and adds a
`<meta name="author">` tag to the page `<head>`.

```yaml
author: Jane Doe
```

### `date`

An ISO 8601 date (`YYYY-MM-DD`). Displayed in the footer alongside the author.
Has no effect on file ordering — discovery order is alphabetical with
`index.md` always first.

```yaml
date: 2025-06-01
```

### `tags`

A YAML list of tags. Rendered as a tag strip at the bottom of the page content
and added as `<meta name="keywords">`.

```yaml
tags:
  - python
  - web
  - tutorial
```

### `draft`

Set to `true` to exclude a page from generation entirely. Useful for
work-in-progress content. The file is skipped silently — no HTML is written
and the page does not appear in the navigation.

```yaml
draft: true
```

## Combining fields

All fields are optional and can be mixed freely:

```markdown
---
title: Release Notes — v2.0
author: Chris
date: 2026-01-15
tags:
  - release
  - changelog
---

## What changed

...
```

## Pages without front matter

Front matter is entirely optional. Pages with no `---` block behave exactly as
before — the title is extracted from the first `#` heading and the description
from the first paragraph.
