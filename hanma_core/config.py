import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: 'pyyaml' package not found.")
    print("Install it with:  pip install pyyaml")
    sys.exit(1)


def load_site_config(config_path: Path) -> dict:
    """Load hanma.yml (or hanma.yaml) from config_path. Returns {} if absent or invalid.

    Recognized fields: name, base_url, output, theme, serve, port, watch, incremental.
    """
    if not config_path.is_file():
        return {}
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"Warning: could not parse {config_path}: {exc}", file=sys.stderr)
        return {}
    if not isinstance(raw, dict):
        return {}
    allowed = {"name", "base_url", "output", "theme", "serve", "port", "watch", "incremental",
               "posts_label"}
    return {k: v for k, v in raw.items() if k in allowed}
