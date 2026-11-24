"""Paket SIREKON (Pool 2 NLP & Pool 3 KB / API)."""
from pathlib import Path
import sys

_SRC_DIR = str(Path(__file__).resolve().parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
