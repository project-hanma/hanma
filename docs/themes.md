# Themes & Customization

Hanma delegates all visual layout and styling to its theme system. Themes are self-contained directories in the `themes/` folder.

## Theme Structure

A theme directory typically looks like this:

```
themes/default/
├── template.html      ← Jinja2 HTML skeleton
└── assets/
    ├── css/
    │   └── style.css  ← layout and component styles
    └── scripts/
        ├── theme-init.js    ← applies saved theme before first paint
        ├── theme-toggle.js  ← dark/light toggle button logic
        └── search.js        ← inline search dropdown
```

The `assets/` directory is merged into `output/assets/` during the build process.

## Built-in Themes

Hanma comes with four built-in themes:

- **default**: A clean, centered layout with a sticky header.
- **narwhal**: A professional sidebar-centric layout with a premium navy and slate blue color scheme. It supports the `sidebar_side` configuration option.
- **glassmorphic**: A modern layout featuring a frosted glass aesthetic (glassmorphism) with vibrant ambient background blobs and high-fidelity micro-interactions. It uses the Outfit and Inter typography and supports the `sidebar_side` configuration option.
- **zengarden**: A serene, minimalist layout inspired by traditional Japanese Zen gardens and paper shoji screens. It features Lora, Noto Serif JP, and Plus Jakarta Sans typography, custom stones-and-ripples SVG iconography, and a tranquil design.

## Customization

To create a custom theme:
1. Copy an existing theme (e.g., `themes/default/`) to a new folder (e.g., `themes/mytheme/`).
2. Edit `template.html` using [Jinja2](https://jinja.palletsprojects.com/) syntax.
3. Update the `assets/` to your liking.

### Available Template Variables

| Variable | Type | Content |
|---|---|---|
| `title` | string | Browser title |
| `description` | string | Page description (meta) |
| `site_name` | string | Site name from `--name` or config |
| `content` | string | **(HTML)** Rendered page content (use `{{ content | safe }}`) |
| `nav_items` | list | Structured navigation data for custom loops |
| `root_rel` | string | Relative path prefix to the output root (e.g., `""` or `"../"`) |
| `page_tags` | list | Structured list of tags for the current page: `[{"name": "...", "slug": "...", "url": "..."}]` |
| `author` | string | Author name from front matter |
| `page_date` | string | Formatted front matter date (e.g., `"November 09, 2026"`) |
| `author_meta` | string | **(HTML)** `<meta name="author">` tag (use `{{ author_meta | safe }}`) |
| `keywords_meta` | string | **(HTML)** `<meta name="keywords">` tag (use `{{ keywords_meta | safe }}`) |
| `refresh_meta` | string | **(HTML)** `<meta http-equiv="refresh">` tag (use `{{ refresh_meta | safe }}`) |
| `source_file` | string | Source `.md` filename |
| `last_updated` | string | **(HTML)** Localized modification/generation timestamp (use `{{ last_updated | safe }}`) |
| `sitemap_link` | string | **(HTML)** Relative or absolute link to `sitemap.xml` (use `{{ sitemap_link | safe }}`) |
| `search_json_url` | string | URL to `search.json` (relative or absolute; empty string when `search: false`) |
| `base_url` | string | Absolute base URL from config |
| `page_url` | string | URL of the current page relative to output root |
| `sidebar_side` | string | Sidebar position (`left` or `right`) for supported themes |

### Custom Navigation Loop

You can build your menu using `nav_items`:

```html
<ul>
  {% for item in nav_items %}
    <li{% if item.is_current %} class="active"{% endif %}>
      <a href="{{ item.url }}">{{ item.title }}</a>
      {% if item.children %}
        <ul class="dropdown">
          {% for child in item.children %}
            <li><a href="{{ child.url }}">{{ child.title }}</a></li>
          {% endfor %}
        </ul>
      {% endif %}
    </li>
  {% endfor %}
</ul>
```

## Syntax Highlighting

Fenced code blocks are highlighted using [Pygments](https://pygments.org/). The default theme switches between a `friendly` light theme and a `monokai` dark theme based on the user's preference or OS settings.

````markdown
```bash
echo "hello world"
```
````

Pygments CSS is automatically generated at build time and written to `output/assets/css/pygments.css`.
