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
| `page_tags` | list | Structured list of tags for the current page: `[{"name": "...", "url": "..."}]` |
| `author_line` | string | **(HTML)** Author/date attribution (use `{{ author_line | safe }}`) |
| `author_meta` | string | **(HTML)** `<meta name="author">` tag |
| `keywords_meta` | string | **(HTML)** `<meta name="keywords">` tag |
| `refresh_meta` | string | **(HTML)** `<meta http-equiv="refresh">` tag |
| `source_file` | string | Source `.md` filename |
| `last_updated` | string | File modification timestamp |
| `sitemap_link` | string | **(HTML)** Link to `sitemap.xml` |
| `search_json_url` | string | URL to `search.json` (relative or absolute) |

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
