"""Ekstraksi PDF digital -> baris mentah + meta + bbox tabel.

Keluaran sama bentuknya dengan fixture tests/fixtures/<bank>_raw:
  rows : [{"TANGGAL","KETERANGAN","CBG","MUTASI","SALDO"}, ...]  (teks mentah, belum dinormalisasi)
  meta : periode, no_rekening, saldo_awal, saldo_akhir, mutasi_cr, n_cr, mutasi_db, n_db
  bbox : [{"halaman": 1, "bbox": (x0, top, x1, bottom)}, ...]  satuan poin PDF
"""
import re

import pdfplumber

# Batas kolom BCA (poin PDF) hasil pengamatan pada 6 sampel.
_BCA_KOLOM = {"ket_kiri": (85, 190), "ket_kanan": (190, 300), "cbg": (300, 337),
              "mutasi": (337, 465), "saldo": (465, 10**6)}


def _antara(x, lo_hi):
    return lo_hi[0] <= x < lo_hi[1]


def baca_header_halaman(path):
    """Teks halaman pertama (untuk identifikasi bank)."""
    with pdfplumber.open(path) as pdf:
        return pdf.pages[0].extract_text() or ""


def extract_bca(path):
    rows, meta, bbox = [], {}, []
    with pdfplumber.open(path) as pdf:
        for no, pg in enumerate(pdf.pages, start=1):
            ws = pg.extract_words()
            txt = pg.extract_text() or ""
            m = re.search(r"PERIODE\s*:\s*([A-Za-z]+\s+\d{4})", txt)
            if m:
                meta["periode"] = m.group(1)
            m = re.search(r"NO\.\s*REKENING\s*:\s*(\d+)", txt)
            if m:
                meta["no_rekening"] = m.group(1)
            hdr = [w for w in ws if w["text"] == "TANGGAL" and w["top"] > 200]
            if hdr:
                htop = hdr[0]["top"]
                stops = [w["top"] for w in ws if w["text"].startswith("Bersambung")]
                for i, w in enumerate(ws):
                    if (w["text"] == "SALDO" and i + 2 < len(ws) and ws[i + 1]["text"] == "AWAL"
                            and ws[i + 2]["text"] == ":" and w["top"] > htop):
                        stops.append(w["top"])
                bottom = min(stops) if stops else 10**6
                body = [w for w in ws if w["top"] > htop + 8 and w["top"] < bottom - 1]
                starts = sorted([w for w in body if w["x0"] < 85 and re.fullmatch(r"\d\d/\d\d", w["text"])],
                                key=lambda w: w["top"])
                for k, s in enumerate(starts):
                    end = starts[k + 1]["top"] if k + 1 < len(starts) else bottom
                    rw = [w for w in body if w["top"] >= s["top"] - 1 and w["top"] < end - 1]
                    srt = lambda c: sorted([w for w in rw if _antara(w["x0"], _BCA_KOLOM[c])],
                                           key=lambda w: (round(w["top"]), w["x0"]))
                    ket = " ".join(w["text"] for w in srt("ket_kiri") + srt("ket_kanan"))
                    cbg = " ".join(w["text"] for w in srt("cbg"))
                    mut = " ".join(w["text"] for w in sorted(
                        [w for w in rw if _antara(w["x0"], _BCA_KOLOM["mutasi"])], key=lambda w: w["x0"]))
                    sal = [w["text"] for w in rw if _antara(w["x0"], _BCA_KOLOM["saldo"])]
                    if "SALDO AWAL" in ket and not re.search(r"\d", mut):
                        meta["saldo_awal"] = sal[0] if sal else ""
                        continue
                    rows.append({"TANGGAL": s["text"], "KETERANGAN": ket, "CBG": cbg,
                                 "MUTASI": mut, "SALDO": sal[0] if sal else ""})
                if starts:
                    isi = [w for w in body if w["top"] >= starts[0]["top"] - 1]
                    bbox.append({"halaman": no, "bbox": (
                        min(w["x0"] for w in ws if w["top"] >= htop - 1 and w["top"] < bottom),
                        htop,
                        max(w["x1"] for w in isi),
                        max(w["bottom"] for w in isi))})
            if "MUTASI CR" in txt:
                for key, pat in [("saldo_awal_footer", r"SALDO AWAL\s*:\s*([\d,]+\.\d\d)"),
                                 ("saldo_akhir", r"SALDO AKHIR\s*:\s*([\d,]+\.\d\d)"),
                                 ("mutasi_cr", r"MUTASI CR\s*:\s*([\d,]+\.\d\d)\s+(\d+)"),
                                 ("mutasi_db", r"MUTASI DB\s*:\s*([\d,]+\.\d\d)\s+(\d+)")]:
                    mm = re.search(pat, txt)
                    if mm:
                        meta[key] = mm.group(1)
                        if mm.lastindex == 2:
                            meta["n_" + key[-2:]] = int(mm.group(2))
    meta.setdefault("saldo_awal", meta.get("saldo_awal_footer"))
    meta.pop("saldo_awal_footer", None)
    return rows, meta, bbox




# ---------------------------------------------------------------- BRI
# Batas kolom BRI (poin PDF) hasil pengamatan pada 5 sampel. Tabel tanpa garis kolom.
_BRI_KOLOM = {"waktu": (0, 105), "uraian": (105, 298), "teller": (298, 372),
              "debet": (372, 470), "kredit": (470, 560), "saldo": (560, 10**6)}
_BRI_JEDA_BARIS = 14  # baris lanjutan uraian berjarak ~9 poin; antar transaksi ~21 poin
_BRI_HEADER = {"waktu": "Tanggal Transaksi", "uraian": "Uraian Transaksi", "teller": "Teller",
               "debet": "Debet", "kredit": "Kredit", "saldo": "Saldo"}


def extract_bri(path):
    rows, meta, bbox = [], {}, []
    with pdfplumber.open(path) as pdf:
        for no, pg in enumerate(pdf.pages, start=1):
            ws = pg.extract_words()
            txt = pg.extract_text() or ""
            m = re.search(r"No\.\s*Rekening\s*:\s*(\d+)", txt)
            if m:
                meta["no_rekening"] = m.group(1)
            m = re.search(r"Periode Transaksi\s*:\s*(\d\d/\d\d/\d\d\s*-\s*\d\d/\d\d/\d\d)", txt)
            if m:
                meta["periode"] = m.group(1)
            m = re.search(r"Closing Balance\s*\n([\d,]+\.\d\d) ([\d,]+\.\d\d) ([\d,]+\.\d\d) ([\d,]+\.\d\d)", txt)
            if m:
                meta["saldo_awal"], meta["mutasi_db"], meta["mutasi_cr"], meta["saldo_akhir"] = m.groups()
            # jangkar baris: tanggal dd/mm/yy di kolom paling kiri yang diikuti jam hh:mm:ss
            ws_s = sorted(ws, key=lambda w: (round(w["top"]), w["x0"]))
            anchors = []
            for i, w in enumerate(ws_s[:-1]):
                n2 = ws_s[i + 1]
                if (w["x0"] < 60 and re.fullmatch(r"\d\d/\d\d/\d\d", w["text"])
                        and re.fullmatch(r"\d\d:\d\d:\d\d", n2["text"]) and abs(n2["top"] - w["top"]) < 2):
                    anchors.append(w)
            if not anchors:
                continue
            tops_all = sorted({round(w["top"], 1) for w in ws})
            semua = []
            for k, a in enumerate(anchors):
                batas = anchors[k + 1]["top"] - 1 if k + 1 < len(anchors) else 10**6
                tops = [t for t in tops_all if a["top"] - 1 <= t < batas]
                ambil, prev = [], None
                for t in tops:
                    if prev is not None and t - prev > _BRI_JEDA_BARIS:
                        break
                    ambil.append(t)
                    prev = t
                rw = [w for w in ws if round(w["top"], 1) in ambil]
                semua.extend(rw)

                def kol(c):
                    return sorted([w for w in rw if _antara(w["x0"], _BRI_KOLOM[c])],
                                  key=lambda w: (round(w["top"]), w["x0"]))
                rows.append({
                    _BRI_HEADER["waktu"]: " ".join(w["text"] for w in kol("waktu")),
                    _BRI_HEADER["uraian"]: " ".join(w["text"] for w in kol("uraian")),
                    _BRI_HEADER["teller"]: " ".join(w["text"] for w in kol("teller")),
                    _BRI_HEADER["debet"]: " ".join(w["text"] for w in kol("debet")),
                    _BRI_HEADER["kredit"]: " ".join(w["text"] for w in kol("kredit")),
                    _BRI_HEADER["saldo"]: " ".join(w["text"] for w in kol("saldo")),
                })
            hdr = [w for w in ws_s[:-1] if w["text"] == "Tanggal" and w["x0"] < 60 and w["top"] < anchors[0]["top"]
                   and ws_s[ws_s.index(w) + 1]["text"] == "Transaksi"]
            top0 = hdr[-1]["top"] if hdr else anchors[0]["top"]
            hdr_words = [w for w in ws if top0 - 1 <= w["top"] < anchors[0]["top"]]
            bbox.append({"halaman": no, "bbox": (
                min(w["x0"] for w in hdr_words + semua), top0,
                max(w["x1"] for w in hdr_words + semua), max(w["bottom"] for w in semua))})
    return rows, meta, bbox


# ---------------------------------------------------------------- BSI
_BSI_KOLOM = 12


def _sel(c):
    return "" if c is None else str(c)


def extract_bsi(path):
    rows, meta, bbox, header = [], {}, [], None
    with pdfplumber.open(path) as pdf:
        for no, pg in enumerate(pdf.pages, start=1):
            txt = pg.extract_text() or ""
            m = re.search(r"REKENING\s*:\s*[A-Z]{3}\s+(\d+)", txt)
            if m:
                meta["no_rekening"] = m.group(1)
            m = re.search(r"Periode\s*:\s*(\d\d/\d\d/\d{4}\s*s/d\s*\d\d/\d\d/\d{4})", txt)
            if m:
                meta["periode"] = m.group(1)
            m = re.search(r"Total Debet[^:]*:\s*([\d,]+\.\d\d)", txt)
            if m:
                meta["mutasi_db"] = m.group(1)
            m = re.search(r"Total Kredit[^:]*:\s*([\d,]+\.\d\d)", txt)
            if m:
                meta["mutasi_cr"] = m.group(1)
            # Label "awal"/"akhir" tidak dipercaya (bsi_02-05 salah ketik): urutan dipakai.
            sal = re.findall(r"Saldo riil (?:awal|akhir) per\s*[\d/]+\s*:\s*([\d,]+\.\d\d)", txt)
            if len(sal) >= 2 and "saldo_awal" not in meta:
                meta["saldo_awal"], meta["saldo_akhir"] = sal[0], sal[1]
            for t in pg.find_tables():
                data = t.extract()
                if not data or len(data[0]) != _BSI_KOLOM:
                    continue  # kotak info (2 kolom) dan lainnya diabaikan
                bbox.append({"halaman": no, "bbox": tuple(t.bbox)})
                for r in data:
                    r = [_sel(c) for c in r]
                    if r[0].strip() == "No" and "saldo riil" in " ".join(" ".join(r).lower().split()):
                        header = header or r
                        continue
                    rows.append(r)
    if header is None:
        raise ValueError("header tabel BSI tidak ditemukan di halaman mana pun")
    return [dict(zip(header, r)) for r in rows], meta, bbox


EXTRACTORS = {"bca": extract_bca, "bri": extract_bri, "bsi": extract_bsi}