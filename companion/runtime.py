"""Separate bundled, read-only resources from persistent portable data."""
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
PROJECT = Path(sys._MEIPASS) if FROZEN else Path(__file__).resolve().parent.parent
HOME = Path(sys.executable).resolve().parent if FROZEN else PROJECT
DATA = HOME / "data"
MANIFEST = HOME / "Manifest.lua" if FROZEN else PROJECT / "addon" / "Manifest.lua"
