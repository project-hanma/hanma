---
name: hanma-engine-dev
description: Guidelines for modifying, testing, versioning, and maintaining the Hanma Static Site Generator core engine.
---

# Hanma Engine Development

Use this skill when modifying the core Python code of the Hanma SSG (located in the `app/` directory), writing or running tests (in the `tests/` directory), or preparing a release.

## Core Architecture
- **Two-Pass Build System**:
  1. **Discovery / Metadata (`collect_page_info`)**: Scan the site directory, parse front matter, and build the navigation tree.
  2. **Conversion / Templating (`convert_md_to_html`)**: Convert Markdown to HTML and inject variables into the theme templates.
- **Incrementality**: Incremental builds track file modification times, theme/config changes, and navigation signature changes via `.hanma_manifest.json`.
- **Theme System**: Merges theme assets into `output/assets/` and auto-generates `pygments.css`.

## Development Workflow
1. **Branching**:
   - NEVER modify `develop`, `main`, or `master`.
   - Always work on a feature branch (e.g., `feature/your-feature`).
2. **Testing**:
   - Run the test suite: `python -m pytest tests/ -v`
   - Always use the project's `.venv/bin/python3` if `mcp-tools-py` is not available.
3. **Versioning**:
   - The source of truth for versioning is [app/_version.py](file:///home/chris/Development/ProjectHanma/Hanma/app/_version.py).
   - Bump the version **exactly once** before the final commit of a task.
   - Increment:
     - `+0.0.10` for new features.
     - `+0.0.1` for bug fixes.
4. **Release Notes**:
   - Provide release notes in the `Hanma v[version] — [The "Name" Update]` format.
   - Use emojis (e.g., 🏯, 🏗️, 🛠️, ✅) for section headers ONLY. Do NOT place emojis at the end of individual bullet points.
5. **Security**:
   - Validate file paths to prevent traversal/symlink attacks.
   - Sanitize all HTML inputs (using `bleach` if enabled).
