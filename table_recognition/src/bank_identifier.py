"""Kenali bank dari kombinasi nama kolom (penanda di profiles.id_markers).

Bank dipilih hanya bila TEPAT satu profil yang semua penandanya ada. Selain itu
mengembalikan None (abstain) -- tidak menebak.
"""
from .profiles import PROFILES


def _canon(s):
    return " ".join(str(s).lower().split())


def kenali_bank(teks_header):
    t = _canon(teks_header)
    cocok = [k for k, p in PROFILES.items()
             if p.get("id_markers") and all(m in t for m in p["id_markers"])]
    return cocok[0] if len(cocok) == 1 else None