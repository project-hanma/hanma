import json
import sys
from pathlib import Path


_MANIFEST_TEMPLATE_KEY = "_template_mtime"
_MANIFEST_CONFIG_KEY   = "_config_mtime"


def load_build_manifest(manifest_path: Path) -> dict:
    """Load JSON manifest mapping str(md_path) -> mtime float. Returns {} on miss."""
    if not manifest_path.is_file():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_build_manifest(manifest_path: Path, manifest: dict) -> None:
    """Persist the manifest dict as JSON to manifest_path."""
    try:
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        print(f"  [manifest] warning: could not save {manifest_path}: {exc}", file=sys.stderr)


def page_needs_rebuild(md_path: Path, out_html: Path, manifest: dict,
                        template_mtime: float, config_mtime: float = 0.0) -> bool:
    """Return True if md_path should be regenerated.

    Triggers rebuild if:
    - out_html does not exist
    - md_path mtime differs from manifest entry
    - template_mtime is newer than the manifest's recorded template_mtime
    - config_mtime is newer than the manifest's recorded config_mtime
    """
    if not out_html.exists():
        return True
    if str(md_path) not in manifest:
        return True
    try:
        if md_path.stat().st_mtime != manifest[str(md_path)]:
            return True
    except OSError:
        return True
    if template_mtime > manifest.get(_MANIFEST_TEMPLATE_KEY, 0.0):
        return True
    if config_mtime > manifest.get(_MANIFEST_CONFIG_KEY, 0.0):
        return True
    return False
