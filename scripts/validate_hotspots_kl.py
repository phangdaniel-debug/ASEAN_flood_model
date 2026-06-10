"""Back-compat shim — KL hotspot validation is now scripts/validate_hotspots.py --city kuala_lumpur.

Re-exports `cli` and `evaluate_gate` so existing imports keep working, and rewrites
argv to inject `--city kuala_lumpur` so the old invocation still prints the SAME numbers.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.validate_hotspots import cli, evaluate_gate  # noqa: F401  (back-compat re-export)

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--city", "kuala_lumpur", *sys.argv[1:]]
    cli()
