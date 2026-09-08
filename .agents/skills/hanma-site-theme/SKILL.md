---
name: hanma-site-theme
description: Guidelines for authoring content, managing site configuration, and building or customizing themes for Hanma.
---

# Hanma Site and Theme Customization

Use this skill when creating or editing Markdown content, managing the `hanma.yml` configuration, or designing and modifying HTML/CSS templates in the `themes/` directory.

## Site Structure
- **Navigation**: Folder-based.
  - Pinned: The root `index.md` is always pinned as "Home".
  - Dropdowns: Subdirectories containing an `index.md` become dropdowns in the navigation.
  - Headers: Subdirectories without an `index.md` become non-clickable headers.
  - Exclusions: The `posts/` directory is excluded from the main navigation.
- **Content Files**: Typically reside in `site/`.

## Front Matter (YAML)
Supported fields at the top of Markdown files:
- `title`, `description`: Overrides auto-extracted H1/first paragraph.
- `author`, `date`: Shown in footer and meta tags.
- `tags`: Generates tag pages under `tags/<slug>.html`.
- `draft: true`: Skips the page entirely.
- `layout`: `page` (default) or `post` (default for `posts/`).
- `sort_index`: Controls ordering in navigation (lower = first).
- `refresh`: Auto-refresh interval (meta tag).

## Site Configuration (`hanma.yml`)
Priority: `--config` flag > `conf/hanma.yml` > root `hanma.yml`.
Common fields: `name`, `base_url`, `output`, `theme`, `posts_label`, `serve`, `port`, `host`, `watch`, `incremental`, `sanitize`, `timezone`.

## Theme Development
- Located in `themes/<theme_name>/`.
- Must contain Jinja2 templates (e.g., `page.html`, `post.html`).
- Supported template variables:
  - `$title`, `$description`, `$site_name`, `$content`, `$nav`, `$date_str`, `$author_meta`, `$keywords_meta`, `$author_line`, `$source_file`, `$last_updated`, `$sitemap_link`, `$search_json_url`.
- Assets in the theme's `assets/` directory are copied and merged into the output `assets/` directory.
