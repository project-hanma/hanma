# Feature Requests

Consolidated from two separate analysis documents (feat_req1.md: brainstorm list; feat_req2.md: competitive gap analysis against Pelican, MkDocs, Hugo, Jekyll, Eleventy, Lektor).

---

## Priority 1 — High Impact, Agreed Across Both Sources

**RSS/Atom Feed**
Both documents independently flag this as top priority. `collect_page_info()` already returns `date`, `title`, and `description` for all pages. Estimated ~40–50 line addition at the end of `main()`.

~~**Tag Index Pages**~~
~~Tags are currently decorative (visual strip + meta keywords) but not navigational. No `tags/python.html` listing exists. Both sources identify this as high-value since the tags are already parsed from front matter — rendering index pages is the only missing step.~~

~~**Sitemap (`sitemap.xml`)**~~
~~Mentioned in both documents. Hugo, Jekyll, and Pelican all auto-generate this. Same pass-1 data already available, pure SEO upside with minimal code.~~

---

## Priority 2 — Medium Impact

~~**Site Config File (`ssg.yaml`)**~~
~~All configuration is currently CLI flags only. A `ssg.yaml` at the project root (site name, base URL, output dir, theme) that the CLI can override would make the tool usable without shell scripting. Pelican, MkDocs, Hugo, and Jekyll all treat this as mandatory.~~

**Base URL / Canonical URLs**
No `base_url` concept means no `<link rel="canonical">`, no absolute URLs in RSS feeds, and no `og:url`. One config variable unlocks all of these and is a prerequisite for a correct RSS feed. *(Note: `base_url` is now supported in `ssg.yaml` and via `--base-url`; canonical/og tags not yet added.)*

~~**Static Asset Passthrough**~~
~~No mechanism to copy `site/images/`, `site/fonts/`, etc. to output unchanged. Nearly every real site needs images; this is a practical blocker for non-trivial content.~~

**Live Reload**
Would make `--watch --serve` significantly more pleasant. Requires injecting a small JS snippet in dev mode and a WebSocket or SSE endpoint from the server.

---

## Priority 3 — Lower Priority / Nice to Have

~~**Search Index**~~
~~Generate a `search.json` (title, description, URL per page) to let the theme inject client-side search. Critical for docs sites; lower value for small blogs.~~

~~**inotify-based Watch (`watchdog`)**~~
~~Current watch mode polls every 1 second (`time.sleep(1.0)`). `watchdog` would give near-instant rebuilds at the cost of one new dependency.~~

~~**Post Listing Page**~~
~~An auto-generated page listing all posts sorted by date from front matter. Complements tag index pages.~~

**Previous/Next Post Links**
"← older" / "newer →" navigation at the bottom of posts, sorted by front matter date.

**Multiple Layouts**
Front matter `layout: post` vs `layout: page` selects a different template within the theme.

~~**Incremental Builds**~~
~~Only regenerate pages whose source or dependencies have changed.~~

**Pagination**
Split long post lists into pages (e.g. `posts/page/2/`). Depends on post listing page existing first.

**Breadcrumbs**
Useful for deeply nested content structures.

**Related Pages**
Suggest pages sharing the same tags. Depends on tag index pages being implemented first.

~~**Front Matter `refresh` Field**~~
~~Add a `refresh: <seconds>` front matter field that injects `<meta http-equiv="refresh" content="<seconds>" />` into the page `<head>`, causing the browser to auto-reload after the specified interval. Useful for live dashboards or status pages. Accepts a positive integer; absent or zero means no refresh.~~

**Word Count / Reading Time**
Inject "5 min read" into the template via a new template variable.

**Shortcodes**
Custom inline macros like `{{youtube id="abc123"}}`.

~~**`--init` Scaffold**~~
~~Scaffold a new site with sample content and a `site/` directory.~~

---

## What We're Already Ahead On (No Action Needed)

- **Self-contained HTML output** — No external CSS/JS after generation. No other mainstream SSG does this by default.
- **Dark mode** — Correct `data-theme` approach with pre-paint preference application; dual Pygments themes. Most SSGs leave this entirely to themes.
- **Two-pass architecture** — Global nav is consistent across all pages without a second write pass.
- **Stale output cleanup** — Hugo does this with `--cleanDestinationDir`; Pelican and Jekyll do not.
- **`--dry-run`** — Absent from most SSGs.
- **Single-file distribution** — Only Hugo (compiled binary) competes here.
