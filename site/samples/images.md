# Images in Markdown

`ssg.py` passes standard Markdown image syntax straight through to HTML.
No special configuration is needed.

---

## Basic Syntax

```markdown
![Alt text](path/to/image.png)
```

The `alt text` is used by screen readers and displayed if the image fails
to load — always include a meaningful description.

---

## Remote Images

Remote URLs work just as well as local paths:

```markdown
![A scenic mountain landscape](https://picsum.photos/seed/mountain/900/400)
```

![A scenic mountain landscape](https://picsum.photos/seed/mountain/900/400)

---

## Local Images

Place the image file alongside (or relative to) your Markdown file and
reference it by relative path:

```markdown
![Project architecture diagram](./diagrams/architecture.png)
```

Sub-directories work too:

```markdown
![Logo](../assets/logo.png)
```

---

## Images with Captions

Markdown has no native caption element. The common pattern is an italicised
paragraph immediately below the image:

```markdown
![Aerial photograph of a forest](https://picsum.photos/seed/forest/900/400)

*Figure 1 — Aerial view of a temperate rainforest, Pacific Northwest.*
```

![Aerial photograph of a forest](https://picsum.photos/seed/forest/900/400)

*Figure 1 — Aerial view of a temperate rainforest, Pacific Northwest.*

---

## Linked Images

Wrap the image syntax in a link to make it clickable:

```markdown
[![A coastal cliff](https://picsum.photos/seed/coast/900/400)](https://picsum.photos)
```

[![A coastal cliff](https://picsum.photos/seed/coast/900/400)](https://picsum.photos)

---

## Tips

- **Local paths are relative to the Markdown file**, not to where you run
  `ssg.py` from. So `./images/photo.jpg` means a folder called `images`
  sitting next to your `.md` file.
- Images are styled to be `max-width: 100%` so they never overflow the
  content column on any screen size.
- Prefer descriptive alt text — it improves accessibility and SEO.
- For diagrams and screenshots, PNG is preferred; for photographs, JPEG or
  WebP keeps file sizes smaller.
