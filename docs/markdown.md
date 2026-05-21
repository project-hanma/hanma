# Markdown Features & Extensions

Hanma uses [Python-Markdown](https://python-markdown.github.io/) to convert your content into HTML. In addition to standard Markdown, several extensions are enabled by default to provide a rich feature set.

## Standard Features

- **TOC:** Use `[TOC]` to generate a Table of Contents (levels 2-4).
- **Tables:** Standard GFM-style table support.
- **Fenced Code:** Code blocks with triple backticks (```) and optional language hints.
- **Footnotes:** Standard Markdown footnotes using `[^1]` and `[^1]: My note`.
- **Definition Lists:** Support for terms and definitions.
- **Abbreviations:** Define abbreviations like `*[HTML]: HyperText Markup Language`.

## SmartyPants & Formatting

- **SmartyPants:** Automatically converts ASCII quotes, dashes, and ellipses into their typographically correct counterparts (e.g., `---` becomes &mdash;).
- **Newlines:** The `nl2br` extension is enabled, meaning single line breaks in Markdown will be preserved as `<br>` tags in HTML.
- **Sane Lists:** Improved list handling to prevent accidental list nesting.

## Image Readability & Attributes

Hanma includes the `attr_list` extension, which allows you to add CSS classes and other attributes directly to Markdown elements using the `{.class}` syntax.

### Dark Mode Image Inversion

For transparent images like graphs, icons, or charts that use dark text/lines, you can "opt-in" to color inversion for dark mode. This ensures they remain readable when the theme switches to a dark background.

Add the `invert-dark` class to your image syntax:

```markdown
![Network Graph](pi-traffic.png){.invert-dark}
```

- **Light Mode:** The image appears exactly as it is.
- **Dark Mode:** The colors are inverted (black text becomes white), making it clear against the dark background.

Note: This is recommended for graphs and icons only. For photos, the inversion is usually not desired.

## Syntax Highlighting

Code blocks are highlighted using [Pygments](https://pygments.org/). The theme automatically manages the color scheme based on the active light/dark mode.

````markdown
```python
def hello_world():
    print("Hello, Hanma!")
```
````

For a full list of supported languages, refer to the [Pygments documentation](https://pygments.org/languages/).

## Security & HTML Sanitization

When the `--sanitize` flag is enabled (or `sanitize: true` is configured in `hanma.yml`), Hanma filters generated HTML using `bleach` to secure the output:

- **Style Attribute Removal:** All inline `style="..."` attributes are stripped completely to prevent malicious inline CSS injection or clickjacking.
- **Restricted Class & ID Attributes:** To prevent style/layout spoofing, class and ID attributes (commonly added via the `attr_list` extension, e.g. `{.invert-dark}`) are strictly whitelisted. They are permitted on structural and text formatting tags (such as headings, paragraphs, divs, spans, tables, lists, and code blocks) but are stripped from unpermitted elements (like `<img>`).
