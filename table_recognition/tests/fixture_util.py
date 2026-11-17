import glob
import json
import os

HERE = os.path.dirname(__file__)
FIX = os.path.join(HERE, "fixtures")


def muat_fixture(bank, nama):
    with open(os.path.join(FIX, f"{bank}_raw", f"{nama}_raw.json"), encoding="utf-8") as f:
        return json.load(f)


def daftar_fixture(bank):
    return sorted(os.path.basename(p)[:-9] for p in glob.glob(os.path.join(FIX, f"{bank}_raw", "*_raw.json")))


def f(s):
    """'1,234.50' -> 1234.5 (untuk membaca angka meta fixture)."""
    return float(str(s).replace(",", ""))