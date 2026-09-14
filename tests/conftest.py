"""Test the standalone client without requiring Home Assistant to start."""

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "noise_explorer")
)
