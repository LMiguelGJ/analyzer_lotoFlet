"""Individual entry points for frozen historical Quiniela scenarios."""

import sys
from pathlib import Path

# The engine lives in main/ and imports repo_ref from the repository root.
_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "main"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
