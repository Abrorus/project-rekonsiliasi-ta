"""Normalisasi baris mentah hasil ekstraksi -> skema standar.

Murni stdlib. Semua perbedaan antar bank dibaca dari profiles.PROFILES.
"""
import re
from datetime import datetime

from .profiles import get_profile

BULAN = {
    "JANUARI": 1, "FEBRUARI": 2, "MARET": 3, "APRIL": 4, "MEI": 5, "JUNI": 6,
    "JULI": 7, "AGUSTUS": 8, "SEPTEMBER": 9, "OKTOBER": 10, "NOVEMBER": 11, "DESEMBER": 12,
}

_AMOUNT = {
    "us": re.compile(r"^(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}$"),
    "id": re.compile(r"^(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}$"),
}


def parse_amount(text, locale="us"):
    """Parse nominal secara ketat per locale. Mengembalikan float bertanda.

    Tanda: awalan '+'/'-' atau akhiran '-' (BSI). Format di luar pola -> ValueError
    (tidak ada tebakan, supaya salah baca tidak diam-diam jadi angka salah).
    """
    if locale not in _AMOUNT:
        raise ValueError(f"locale tidak dikenal: {locale!r}")
    s = "".join(str(text).split())
    sign = 1.0
    if s.startswith("+"):
        s = s[1:]
    elif s.startswith("-"):
        sign, s = -1.0, s[1:]
    elif s.endswith("-"):
        sign, s = -1.0, s[:-1]
    if not _AMOUNT[locale].match(s):
        raise ValueError(f"format nominal tidak valid untuk locale {locale}: {text!r}")
    if locale == "us":
        s = s.replace(",", "")
    else:
        s = s.replace(".", "").replace(",", ".")
    return sign * float(s)


def tahun_dari_periode(teks):
    """'PERIODE : JULI 2023' atau 'JULI 2023' -> (2023, 7)."""
    m = re.search(r"([A-Za-z]+)\s+(\d{4})", str(teks))
    if not m or m.group(1).upper() not in BULAN:
        raise ValueError(f"periode tidak dikenali: {teks!r}")
    return int(m.group(2)), BULAN[m.group(1).upper()]


def parse_waktu(text, profile, tahun=None):
    """Teks waktu -> ISO dengan presisi yang tersedia (tanggal / menit / detik)."""
    prof = get_profile(profile) if isinstance(profile, str) else profile
    s = " ".join(str(text).split())
    for pat in prof["waktu_patterns"]:
        m = re.match(pat, s)
        if not m:
            continue
        g = m.groupdict()
        if g.get("y"):
            y = int(g["y"])
            y = 2000 + y if y < 100 else y
        elif tahun is not None:
            y = int(tahun)
        else:
            raise ValueError(f"tahun tidak tersedia untuk {text!r}")
        d, mo = int(g["d"]), int(g["m"])
        if g.get("H") is None:
            datetime(y, mo, d)  # validasi tanggal
            return f"{y:04d}-{mo:02d}-{d:02d}"
        H, M = int(g["H"]), int(g["M"])
        if g.get("S") is None:
            datetime(y, mo, d, H, M)
            return f"{y:04d}-{mo:02d}-{d:02d}T{H:02d}:{M:02d}"
        S = int(g["S"])
        datetime(y, mo, d, H, M, S)
        return f"{y:04d}-{mo:02d}-{d:02d}T{H:02d}:{M:02d}:{S:02d}"
    raise ValueError(f"format waktu tidak dikenali: {text!r}")


def _canon(s):
    return " ".join(str(s).lower().split())


def standardize_headers(row, profile):
    """Ubah kunci baris mentah (nama kolom hasil ekstraksi) -> nama standar profil."""
    prof = get_profile(profile) if isinstance(profile, str) else profile
    lookup = {}
    for std, aliases in prof["headers"].items():
        for a in aliases:
            lookup[_canon(a)] = std
    out = {}
    for k, v in row.items():
        std = lookup.get(_canon(k))
        if std is None:
            raise ValueError(f"nama kolom tidak dikenali untuk profil ini: {k!r}")
        out[std] = v
    return out


def _kosong(v):
    return v is None or str(v).strip() == ""


def _debit_kredit(row, prof):
    loc = prof["locale"]
    mode = prof["amount_mode"]
    if mode == "mutasi_label":
        s = " ".join(str(row.get("mutasi", "")).split())
        lab = prof["debit_label"]
        is_db = s.endswith(" " + lab)
        body = s[: -len(lab)].strip() if is_db else s
        if body == "":
            raise ValueError("kolom mutasi kosong")
        val = abs(parse_amount(body, loc))
        return (val, 0.0) if is_db else (0.0, val)
    if mode == "debit_kredit":
        d = 0.0 if _kosong(row.get("debit")) else abs(parse_amount(row["debit"], loc))
        k = 0.0 if _kosong(row.get("kredit")) else abs(parse_amount(row["kredit"], loc))
        if d and k:
            raise ValueError("debit dan kredit sama-sama terisi")
        if not d and not k and _kosong(row.get("debit")) and _kosong(row.get("kredit")):
            raise ValueError("debit dan kredit sama-sama kosong")
        return d, k
    raise NotImplementedError(f"amount_mode {mode!r} belum diimplementasi")


def normalize_data(raw_rows, profile, meta=None, strict=True):
    """Baris mentah -> daftar record standar.

    Record: bank, no_rekening, source_file, waktu_transaksi, keterangan, debit, kredit, saldo.
    `saldo` = nilai tercetak (float) atau None bila tidak tercetak (BCA) -> diisi balance.hitung_saldo.
    strict=True : baris yang tidak valid -> ValueError (menyebut nomor baris).
    strict=False: baris tetap dikeluarkan, field bermasalah None, record['flag']='PERIKSA'.
    """
    meta = meta or {}
    key = profile if isinstance(profile, str) else profile.get("bank")
    prof = get_profile(profile) if isinstance(profile, str) else profile
    if not prof.get("ready", False):
        raise NotImplementedError(f"Profil {key!r} belum siap (ditunda ke langkah OCR).")
    bank = key if isinstance(profile, str) else prof.get("bank", "")

    tahun = None
    if prof.get("year_source") == "periode":
        if "periode" not in meta:
            raise ValueError("meta['periode'] wajib untuk profil ini")
        tahun, _ = tahun_dari_periode(meta["periode"])

    drops = [re.compile(p) for p in prof.get("drop_patterns", [])]
    records = []
    for i, raw in enumerate(raw_rows, start=1):
        try:
            r = standardize_headers(raw, prof)
            ket = " ".join(str(r.get("keterangan", "")).split())
            if any(p.match(ket) for p in drops):
                continue
            waktu = parse_waktu(r["waktu"], prof, tahun)
            debit, kredit = _debit_kredit(r, prof)
            saldo = None if _kosong(r.get("saldo")) else parse_amount(r["saldo"], prof["locale"])
            if prof["saldo_per_row"] and saldo is None:
                raise ValueError("saldo kosong padahal profil mewajibkan saldo per baris")
            rec = {
                "bank": bank,
                "no_rekening": meta.get("no_rekening"),
                "source_file": meta.get("source_file"),
                "waktu_transaksi": waktu,
                "keterangan": ket,
                "debit": debit,
                "kredit": kredit,
                "saldo": saldo,
            }
        except (ValueError, KeyError) as e:
            if strict:
                raise ValueError(f"baris {i}: {e}") from e
            rec = {"bank": bank, "no_rekening": meta.get("no_rekening"),
                   "source_file": meta.get("source_file"), "waktu_transaksi": None,
                   "keterangan": " ".join(str(raw.get("KETERANGAN", raw.get("keterangan", ""))).split()),
                   "debit": None, "kredit": None, "saldo": None, "flag": "PERIKSA"}
        records.append(rec)
    return records