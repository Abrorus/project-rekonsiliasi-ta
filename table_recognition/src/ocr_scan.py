"""OCR halaman scan BNI/Mandiri: header tabel -> pita baris -> sel -> teks mentah per sel.

Keluaran `baca_halaman` adalah baris MENTAH (string hasil OCR per sel). Parsing angka/waktu dan
koreksi saldo dilakukan di normalizer/balance, bukan di sini.
"""
import re

import cv2
import numpy as np
import pytesseract

from src.scan_preprocess import siapkan_halaman

LANG = "ind+eng"
WL_ANGKA = "0123456789.,"
WL_NOMINAL = "0123456789+-.,"
WL_WAKTU = "0123456789: WIB"

# nama kolom kunci per bank: (kata penanda kolom keterangan, ada kolom No)
KONFIG = {
    "bni": {"ket": "Rincian", "no": False},
    "mandiri": {"ket": "Keterangan", "no": True},
}


def _kata(gray, psm=6, lang=LANG):
    d = pytesseract.image_to_data(gray, lang=lang, config=f"--psm {psm}",
                                  output_type=pytesseract.Output.DICT)
    out = []
    for i, t in enumerate(d["text"]):
        if t.strip():
            out.append(dict(t=t, x=d["left"][i], y=d["top"][i], w=d["width"][i],
                            h=d["height"][i], c=float(d["conf"][i])))
    return out


def cari_header(gray, bank):
    """Posisi kata header tabel. Mencoba beberapa psm. Mengembalikan dict atau None."""
    ket_kata = KONFIG[bank]["ket"]
    for psm in (6, 4, 11, 12):
        w = _kata(gray, psm)
        ket = [x for x in w if x["t"] == ket_kata]
        nom = [x for x in w if x["t"] == "Nominal"]
        if not ket or not nom:
            continue
        # pasangan Keterangan/Nominal pada garis yang sama
        pasangan = [(k, n) for k in ket for n in nom if abs(k["y"] - n["y"]) < 25]
        if not pasangan:
            continue
        k, n = pasangan[0]
        sd = [x for x in w if x["t"] == "Saldo" and abs(x["y"] - n["y"]) < 25 and x["x"] > n["x"]]
        if sd:
            sd = sd[0]
        else:   # kata 'Saldo' header tidak terbaca: perkirakan dari jarak baku kolom Nominal-Saldo
            sd = dict(t="Saldo", x=n["x"] + 366, y=n["y"], w=56, h=n["h"], c=0.0)
        tg = [x for x in w if x["t"] == "Tanggal" and abs(x["y"] - n["y"]) < 25 and x["x"] < k["x"]]
        h = dict(ket=k, nom=n, sd=sd)
        h["tg"] = tg[0] if tg else None
        if KONFIG[bank]["no"]:
            no = [x for x in w if x["t"] == "No" and abs(x["y"] - n["y"]) < 25 and x["x"] < k["x"]]
            h["no"] = no[0] if no else None
        return h
    return None


def pita_baris(gray, x0, x1, ytop):
    """Pita baris dari proyeksi horizontal kolom saldo. Daftar (y_awal, y_akhir)."""
    reg = gray[int(ytop):, int(x0):int(x1)]
    if reg.size == 0:
        return []
    b = cv2.threshold(reg, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    ink = (b > 0).sum(axis=1) > max(3, 0.01 * (x1 - x0))
    return _runs(ink, int(ytop), gabung=6, minimal=10)


def _runs(ink, offset, gabung, minimal):
    runs, s = [], None
    for i, v in enumerate(ink):
        if v and s is None:
            s = i
        if not v and s is not None:
            runs.append((s, i))
            s = None
    if s is not None:
        runs.append((s, len(ink)))
    m = []
    for r in runs:
        if m and r[0] - m[-1][1] < gabung:
            m[-1] = (m[-1][0], r[1])
        else:
            m.append(r)
    return [(a + offset, b + offset) for a, b in m if b - a >= minimal]


def garis_teks(gray, x0, x1, y0, y1):
    """Garis teks di dalam sel (proyeksi horizontal)."""
    reg = gray[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)]
    if reg.size == 0:
        return []
    b = cv2.threshold(reg, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    ink = (b > 0).sum(axis=1) > max(2, 0.012 * (x1 - x0))
    return _pecah_ganda(_runs(ink, max(0, int(y0)), gabung=5, minimal=12))


def _pecah_ganda(runs, tinggi_satu=18):
    """Dua garis teks yang menempel terbaca sebagai satu pita; pecah di tengah bila tingginya ~2x."""
    out = []
    for a, b in runs:
        if b - a >= 1.7 * tinggi_satu:
            mid = (a + b) // 2
            out += [(a, mid), (mid, b)]
        else:
            out.append((a, b))
    return out


def ocr_potong(gray, x0, x1, y0, y1, psm=6, wl=None, skala=3.0, lang=LANG):
    c = gray[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)]
    if c.size == 0:
        return ""
    c = cv2.resize(c, None, fx=skala, fy=skala, interpolation=cv2.INTER_CUBIC)
    c = cv2.copyMakeBorder(c, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
    cfg = f"--psm {psm}"
    if wl:
        cfg += f' -c tessedit_char_whitelist="{wl}"'
    return " ".join(pytesseract.image_to_string(c, lang=lang, config=cfg).split())


def _kolom(h, bank, lebar):
    sd, nom, ket = h["sd"]["x"], h["nom"]["x"], h["ket"]["x"]
    if bank == "bni":
        tg_x = h["tg"]["x"] if h["tg"] else ket - 421
        batas = tg_x + 0.143 * (sd + 57 - tg_x)
        x = dict(tg=(tg_x - 40, batas), ket=(batas, nom - 45))
    else:
        tg_x = h["tg"]["x"] if h["tg"] else ket - 182
        x = dict(tg=(tg_x - 30, ket - 25), ket=(ket - 25, nom - 80))
        no_x = h["no"]["x"] if h.get("no") else tg_x - 85
        x["no"] = (no_x - 30, tg_x - 30)
    x["nom"] = (x["ket"][1], sd - 110)
    x["sd"] = (sd - 110, lebar - 5)
    return x


RE_TGL = re.compile(r"[A-Za-z]{3,9}\.?\s*\d{4}\b")
RE_JAM = re.compile(r"\d{1,2}\s*:?\s*\d{2}\s*:?\s*\d{2}|WIB|WI8")
def _jam_valid(t):
    m = re.search(r"(\d{2}):(\d{2}):(\d{2})", t)
    return bool(m) and int(m.group(1)) < 24 and int(m.group(2)) < 60 and int(m.group(3)) < 60


RE_NOMINAL_OK = re.compile(r"^[+-]?\d{1,3}([.,]\d{3})*([.,]\d{2})?$")


def _ocr_satu_garis(gray, x0, x1, y0, y1, wl, ok=None):
    """OCR satu garis angka; bila hasil tidak lolos regex `ok`, coba varian lain."""
    varian = [(2.0, "bin"), (3.0, "g"), (3.0, "bin"), (2.0, "g"), (4.0, "g")]
    terbaik = ""
    for sk, mode in varian:
        c = gray[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)]
        if c.size == 0:
            return ""
        c = cv2.resize(c, None, fx=sk, fy=sk, interpolation=cv2.INTER_CUBIC)
        if mode == "bin":
            c = cv2.threshold(c, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        c = cv2.copyMakeBorder(c, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
        t = " ".join(pytesseract.image_to_string(
            c, lang="eng", config=f'--psm 7 -c tessedit_char_whitelist="{wl}"').split())
        t = t.replace(" ", "")
        if not terbaik:
            terbaik = t
        if ok is None or (ok(t) if callable(ok) else ok.match(t)):
            return t
    return terbaik


VARIAN_ANGKA = [(2.0, "bin"), (3.0, "bin"), (2.0, "g")]


def _ocr_angka_multi(gray, x0, x1, y0, y1, wl):
    """OCR satu garis angka dengan beberapa varian (skala/binarisasi). Mengembalikan daftar string
    berurutan menurut prioritas; hasil kosong dibuang. Hasil tiap varian berkorelasi, jadi ini
    bukan 'voting' melainkan daftar hipotesis untuk koreksi saldo."""
    c0 = gray[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)]
    out = []
    if c0.size == 0:
        return out
    for sk, mode in VARIAN_ANGKA:
        c = cv2.resize(c0, None, fx=sk, fy=sk, interpolation=cv2.INTER_CUBIC)
        if mode == "bin":
            c = cv2.threshold(c, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        c = cv2.copyMakeBorder(c, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
        try:
            t = "".join(pytesseract.image_to_string(
                c, lang="eng", config=f'--psm 7 -c tessedit_char_whitelist="{wl}"').split())
        except pytesseract.TesseractError:
            t = ""
        if t:
            out.append(t)
    return out


def _ocr_waktu_multi(gray, x0, x1, y0, y1):
    """Hipotesis jam dari beberapa varian OCR; yang lolos validasi HH:MM:SS didahulukan."""
    c0 = gray[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)]
    sah, lain = [], []
    for sk, mode in ((2.0, "bin"), (3.0, "g"), (3.0, "bin")):
        c = cv2.resize(c0, None, fx=sk, fy=sk, interpolation=cv2.INTER_CUBIC)
        if mode == "bin":
            c = cv2.threshold(c, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        c = cv2.copyMakeBorder(c, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
        try:
            t = "".join(pytesseract.image_to_string(
                c, lang="eng", config=f'--psm 7 -c tessedit_char_whitelist="{WL_WAKTU}"').split())
        except pytesseract.TesseractError:
            t = ""
        if t:
            (sah if _jam_valid(t) else lain).append(t)
    out = []
    for t in sah + lain:
        if t not in out:
            out.append(t)
    return out


def _garis_utama(gray, x0, x1, y0, y1):
    """Garis teks paling tebal (ink terbanyak) di sel; dipakai sel satu-baris (nominal, saldo)."""
    L = garis_teks(gray, x0, x1, y0, y1)
    if not L:
        return None
    reg = gray[:, int(x0):int(x1)]
    def ink(l):
        return int((cv2.threshold(reg[l[0]:l[1]], 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1] > 0).sum())
    return max(L, key=ink)


def baca_halaman(img_bgr, bank):
    """Satu halaman -> (daftar baris mentah, info). Baris mentah:
    {tanggal, waktu, keterangan, nominal, saldo, no (mandiri), y}

    Jangkar baris = garis tanggal ('DD Mon YYYY') di kolom tanggal; setiap baris terdiri atas
    garis tanggal + garis jam. Garis lain (catatan kaki, disclaimer) diabaikan."""
    gray, _, sudut = siapkan_halaman(img_bgr)
    h = cari_header(gray, bank)
    if h is None:
        return [], dict(header=False, sudut=sudut, gray=gray)
    W = gray.shape[1]
    x = _kolom(h, bank, W)
    ytop = h["sd"]["y"] + 30
    garis = garis_teks(gray, *x["tg"], ytop, gray.shape[0])
    kls = []
    for (a, b) in garis:
        t = ocr_potong(gray, *x["tg"], a - 4, b + 4, psm=7, lang="eng", skala=2.0)
        kls.append((a, b, t))
    awal = []   # indeks garis awal baris: garis tanggal, atau garis tak terbaca yang diikuti garis jam
    for i, (a, b, t) in enumerate(kls):
        diikuti_jam = (i + 1 < len(kls) and kls[i + 1][0] - b < 25 and RE_JAM.search(kls[i + 1][2])
                       and not RE_JAM.search(t))
        if RE_TGL.search(t) or diikuti_jam:
            awal.append(i)
    if not awal:
        return [], dict(header=True, sudut=sudut, h=h, gray=gray, y_header=h["sd"]["y"])
    pusat = []
    for i in awal:
        a, b, _ = kls[i]
        if i + 1 < len(kls) and RE_JAM.search(kls[i + 1][2]) and kls[i + 1][0] - b < 25:
            b = kls[i + 1][1]
        pusat.append((a + b) / 2)
    pitch = float(np.median(np.diff(pusat))) if len(pusat) > 1 else 100.0
    baris = []
    for k, i in enumerate(awal):
        top = pusat[k] - pitch / 2 if k == 0 else (pusat[k - 1] + pusat[k]) / 2
        bot = pusat[k] + pitch / 2 if k + 1 == len(pusat) else (pusat[k] + pusat[k + 1]) / 2
        top = max(top, h["sd"]["y"] + 30)
        a, b, t_tgl = kls[i]
        tanggal = ocr_potong(gray, *x["tg"], a - 4, b + 4, psm=7, lang="eng")
        waktu, waktu_obs = "", []
        if i + 1 < len(kls) and kls[i + 1][0] < bot and RE_JAM.search(kls[i + 1][2]):
            a2, b2, _ = kls[i + 1]
            waktu_obs = _ocr_waktu_multi(gray, *x["tg"], a2 - 4, b2 + 4)
            waktu = waktu_obs[0] if waktu_obs else ""
        r = dict(tanggal=tanggal, waktu=waktu, waktu_obs=waktu_obs,
                 keterangan=ocr_potong(gray, *x["ket"], top, bot, psm=6), y=(int(top), int(bot)))
        for kunci, kol, wl in (("nominal", "nom", WL_NOMINAL), ("saldo", "sd", WL_ANGKA)):
            g = _garis_utama(gray, *x[kol], top, bot)
            obs = _ocr_angka_multi(gray, *x[kol], g[0] - 4, g[1] + 4, wl) if g else []
            r[kunci] = obs[0] if obs else ""
            r[kunci + "_obs"] = obs
        if "no" in x:
            g = _garis_utama(gray, *x["no"], top, bot)
            r["no"] = _ocr_satu_garis(gray, *x["no"], g[0] - 4, g[1] + 4, "0123456789") if g else ""
        baris.append(r)
    return baris, dict(header=True, sudut=sudut, h=h, gray=gray, y_header=h["sd"]["y"])


def teks_atas(gray, y_header):
    """OCR kotak ringkasan di atas tabel (norek, periode, saldo awal/akhir, total)."""
    reg = gray[: int(y_header)]
    reg = cv2.resize(reg, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    return pytesseract.image_to_string(reg, lang=LANG, config="--psm 6")