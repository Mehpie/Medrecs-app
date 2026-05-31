"""Jupyter notebook path bootstrap (works when cwd is project root or notebooks/)."""
import sys
from pathlib import Path


def setup_project_root() -> Path:
    root = Path.cwd().resolve()
    if root.name == "notebooks":
        root = root.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root
