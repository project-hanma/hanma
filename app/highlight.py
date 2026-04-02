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
