import re


def _build_highlight_css() -> str:
  """Return scoped Pygments CSS for light and dark themes."""
  try:
    from pygments.formatters import HtmlFormatter
  except ImportError:
    return ""  # Pygments not installed — highlighting still works, just unstyled

  def scoped(style: str, scope: str) -> str:
    raw = HtmlFormatter(style=style, cssclass="highlight").get_style_defs(".highlight")
    # Drop the bare `pre { ... }` rule Pygments adds — our template already styles pre
    raw = re.sub(r"^pre\s*\{[^}]*\}\s*", "", raw, flags=re.MULTILINE)
    out = []
    for line in raw.splitlines():
      line = line.strip()
      if not line:
        continue
      if line.endswith("{"):
        parts = [s.strip() for s in line.rstrip("{").split(",")]
        out.append(", ".join(f"{scope} {p}" for p in parts) + " {")
      else:
        out.append(line)
    return "\n".join(out)

  light   = scoped("friendly", ":root")
  dark    = scoped("monokai",  '[data-theme="dark"]')
  os_dark = scoped("monokai",  ':root:not([data-theme="light"])')

  return f"""
  /* Syntax highlighting — light (Pygments 'friendly') */
  {light}

  /* Syntax highlighting — dark (Pygments 'monokai') */
  {dark}

  @media (prefers-color-scheme: dark) {{
   {os_dark}
  }}"""


HIGHLIGHT_CSS = _build_highlight_css()
