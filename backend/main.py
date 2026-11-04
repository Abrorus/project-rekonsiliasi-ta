"""
Backend Gateway / Launcher
Menyediakan akses terpadu ke Unified FastAPI Backend (src/api/main.py).
Mendukung eksekusi via:
  uvicorn backend.main:app --port 8000 --reload
  python backend/main.py
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Impor instance FastAPI yang sudah terunifikasi
from api.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
