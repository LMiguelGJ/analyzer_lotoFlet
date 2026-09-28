"""Reproduce fríos / 1 número / apuesta audaz."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SYSTEM, K, STYLE = "cold", 1, "bold"

if __name__ == "__main__":
    from simuladores.runner import main

    raise SystemExit(main(SYSTEM, K, STYLE))
