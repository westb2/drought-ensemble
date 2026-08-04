"""Bootstrap imports for notebooks and scripts run outside an editable install."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def find_project_root() -> Path:
    """Find the drought-ensemble project root from the current working directory."""
    for candidate in [Path.cwd(), *Path.cwd().resolve().parents]:
        if (candidate / "classes" / "Domain.py").is_file():
            return candidate
        nested = candidate / "drought-ensemble"
        if (nested / "classes" / "Domain.py").is_file():
            return nested
    return ROOT


def setup_imports() -> Path:
    """Add the project root to ``sys.path`` for flat imports (``classes``, ``analysis``)."""
    root = find_project_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root
