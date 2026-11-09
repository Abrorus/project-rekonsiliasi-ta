"""Parsing teks mentah hasil OCR (BNI/Mandiri) menjadi nilai: nominal, saldo, waktu, meta header.

Prinsip: parser TOLERAN (hasil OCR bisa salah satu karakter) dan tidak melempar error; nilai yang
tidak terbaca menjadi None. Perbaikan nilai dilakukan di balance.koreksi_rantai (berdasar aritmetika
saldo), bukan di sini.
"""
import re

BULAN = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "may": 5, "jun": 6, "jul": 7,
    "agu": 8, "aug": 8, "ags": 8, "sep": 9, "okt": 10, "oct": 10, "nov": 11, "des": 12, "dec": 12,
}
BULAN_PANJANG = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7,
    "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7, "august": 8,
    "october": 10, "december": 12,
}
_HURUF_ANGKA = str.maketrans({"O": "0", "o": "0", "S": "5", "I": "1", "l": "1", "|": "1", "B": "8", "Z": "2"})


def bulan_dari_teks(t):
    t = t.strip().lower().rstrip(".")
    if t in BULAN_PANJANG:
        return BULAN_PANJANG[t]
    return BULAN.get(t[:3])


def parse_nominal(teks, desimal):
    """'+4,000.000,00' -> (+400000000? tidak) ; kembalikan float bertanda atau None.

    Hanya digit yang dipakai; pemisah (titik/koma) diabaikan karena sering tertukar saat OCR.
    desimal=0 (BNI): semua digit = bilangan bulat.
    desimal=2 (Mandiri): angka setelah pemisah terakhir = sen; bila panjangnya bukan 2, dipotong/dilengkapi
    ke 2 digit (selisih akan terdeteksi dan diperbaiki oleh koreksi saldo)."""
    if not teks:
        return None
    t = teks.strip()
    if not re.search(r"\d", t):
        return None
    tanda = -1.0 if t.lstrip().startswith("-") else 1.0
    if desimal == 0:
        d = re.sub(r"\D", "", t)
        return tanda * float(int(d)) if d else None
    m = re.search(r"[.,](\d+)\s*$", t)
    if m and len(m.group(1)) <= 3:
        sen = m.group(1)[:2].ljust(2, "0")
        depan = re.sub(r"\D", "", t[: m.start()])
    else:
        sen, depan = "00", re.sub(r"\D", "", t)
    if not depan:
        depan = "0"
    return tanda * (int(depan) + int(sen) / 100.0)


def parse_tanggal(teks, tahun_default=None):
    """'01 May 2026' / 'OS Jan 2026' -> (hari|None, bulan|None, tahun|None)."""
    m = re.search(r"(\S{1,3})\s*([A-Za-z]{3,9})\.?\s*(\d{4})\b", teks or "")
    if not m:
        return None, None, tahun_default
    hari_s = m.group(1).translate(_HURUF_ANGKA)
    hari = int(hari_s) if hari_s.isdigit() and 1 <= int(hari_s) <= 31 else None
    return hari, bulan_dari_teks(m.group(2)), int(m.group(3))


def parse_jam(teks):
    """'11:09:51WIB' -> (11, 9, 51); 6 digit tanpa titik dua juga diterima; selain itu None."""
    t = teks or ""
    m = re.search(r"(\d{2}):(\d{2}):(\d{2})", t)
    if not m:
        d = re.sub(r"\D", "", t)
        if len(d) != 6:
            return None
        m = re.match(r"(\d{2})(\d{2})(\d{2})", d)
    h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return (h, mi, s) if h < 24 and mi < 60 and s < 60 else None


def bersihkan_keterangan(t):
    """Buang token noise (hanya simbol) dari hasil OCR; lipat spasi."""
    toks = [x for x in (t or "").split() if re.search(r"[A-Za-z0-9]", x) or x in ("-", "&", "/")]
    return " ".join(toks)


# ---------- meta dari kotak ringkasan ----------

def _angka_us(s):
    d = re.sub(r"\D", "", s)
    return float(int(d)) if d else None


def meta_bni(teks):
    """norek, periode (tahun, bulan), saldo_awal, total_kredit, total_debit, saldo_akhir (bila terbaca)."""
    meta = {}
    m = re.search(r"TAPLUS[^\n]*?[-–]\s*(\d{8,})", teks, re.I) or re.search(r"[-–]\s*(\d{9,})", teks)
    if m:
        meta["no_rekening"] = m.group(1)
    m = re.search(r"Periode\s*:?\s*(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", teks)
    if m and bulan_dari_teks(m.group(3)):
        meta["periode"] = (int(m.group(4)), bulan_dari_teks(m.group(3)))
    baris = teks.splitlines()
    for i, b in enumerate(baris):
        if re.search(r"Saldo\s*Awal", b, re.I) and re.search(r"Saldo\s*Akhir", b, re.I) and i + 1 < len(baris):
            angka = re.findall(r"[+-]?\d{1,3}(?:[.,]\d{3})+|[+-]?\d+", baris[i + 1])
            if len(angka) >= 3:
                meta["saldo_awal"] = _angka_us(angka[0])
                meta["total_kredit"] = _angka_us(angka[1])
                meta["total_debit"] = _angka_us(angka[2])
            if len(angka) >= 4:
                meta["saldo_akhir"] = _angka_us(angka[3])
            break
    return meta


def meta_mandiri(teks):
    meta = {}
    m = re.search(r"Account\s*Number\s*[:\s]*\W*(\d{10,})", teks, re.I) or re.search(r"\b(\d{13})\b", teks)
    if m:
        meta["no_rekening"] = m.group(1)
    m = re.search(r"(\d{1,2})\s*([A-Za-z]{3,9})\s+(\d{4})\s*[-–]\s*(\d{1,2})\s*([A-Za-z]{3,9})\s+(\d{4})", teks)
    if m and bulan_dari_teks(m.group(2)):
        meta["periode"] = (int(m.group(3)), bulan_dari_teks(m.group(2)))

    def uang(pola):
        mm = re.search(pola + r"[^\d\n]{0,12}([\d.,]+)", teks, re.I)
        return parse_nominal(mm.group(1), 2) if mm and re.search(r",\d{2}\s*$", mm.group(1)) else None
    meta["saldo_awal"] = uang(r"Initial\s*Balance")
    meta["total_kredit"] = uang(r"Incoming\s*Transactions")
    meta["total_debit"] = uang(r"Outgoing\s*Transactions")
    meta["saldo_akhir"] = uang(r"Closing\s*Balance")
    return {k: v for k, v in meta.items() if v is not None}