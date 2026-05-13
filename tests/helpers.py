import sys
import subprocess
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SSG = Path(__file__).parent.parent / "hanma.py"

def run_hanma(*args, cwd=None, expect_ok=True):
    """Run hanma.py with the given arguments and return CompletedProcess."""
    # Prioritize .venv if it exists (use absolute path)
    project_root = Path(__file__).parent.parent
    venv_python = project_root / ".venv" / "bin" / "python3"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable

    result = subprocess.run(
        [python_exe, str(SSG), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    if expect_ok and result.returncode != 0:
        import pytest
        pytest.fail(
            f"hanma.py exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result

def write_file(path: Path, content: str) -> Path:
    """Write content to a file, ensuring parent directories exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path
