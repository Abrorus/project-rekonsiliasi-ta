"""Pipeline PDF scan (BNI, Mandiri): render -> OCR sel -> parsing -> koreksi saldo -> validasi.

Keluaran `process_scan_pdf` sama bentuknya dengan pipeline digital, ditambah:
  transaksi_ocr_murni : transaksi hasil OCR+parsing TANPA koreksi saldo (angka 1 pada evaluasi)
  transaksi           : transaksi setelah koreksi saldo (angka 2 pada evaluasi)
  koreksi             : daftar koreksi yang diterapkan (indeks baris, jenis, dari, ke, pasti)
"""
import os
import re

from src.balance import koreksi_dp, validasi_ringkasan
from src.ocr_scan import baca_halaman, cari_header, teks_atas, _kata
from src.scan_parse import (bersihkan_keterangan, meta_bni, meta_mandiri, parse_jam, parse_nominal,
                            parse_tanggal)
from src.scan_preprocess import render_pages, siapkan_halaman

DESIMAL = {"bni": 0, "mandiri": 2}
META = {"bni": meta_bni, "mandiri": meta_mandiri}


def kenali_bank_scan(gray):
    """BNI memuat 'Rincian' (tanpa 'Keterangan'); Mandiri memuat 'Keterangan' (tanpa 'Rincian')."""
    kata = {x["t"] for x in _kata(gray, 6)}
    ada_rincian, ada_ket = "Rincian" in kata, "Keterangan" in kata
    if ada_rincian and not ada_ket:
        return "bni"
    if ada_ket and not ada_rincian:
        return "mandiri"
    return None


def _obs(teks_list, desimal):
    """Daftar hipotesis OCR -> [(nilai, suara)] (nilai identik digabung, urutan = prioritas)."""
    hit, urut = {}, []
    for t in teks_list:
        v = parse_nominal(t, desimal)
        if v is None:
            continue
        if v not in hit:
            hit[v] = 0
            urut.append(v)
        hit[v] += 1
    return [(v, hit[v]) for v in urut]


def _baris_ke_nilai(r, bank, tahun, bulan_default):
    """Teks mentah satu baris -> dict nilai (waktu ISO, keterangan, nominal bertanda, saldo)."""
    d = DESIMAL[bank]
    hari, bln, thn = parse_tanggal(r["tanggal"], tahun)
    jam = parse_jam(r["waktu"])
    return dict(hari=hari, bulan=bln or bulan_default, tahun=thn or tahun, jam=jam,
                jam_kandidat=[j for j in (parse_jam(t) for t in (r.get("waktu_obs") or [r["waktu"]])) if j],
                keterangan=bersihkan_keterangan(r["keterangan"]),
                nominal=parse_nominal(r["nominal"], d), saldo=parse_nominal(r["saldo"], d),
                nominal_obs=_obs(r.get("nominal_obs") or [r["nominal"]], d),
                saldo_obs=_obs(r.get("saldo_obs") or [r["saldo"]], d))


def _pilih_jam(v, prev):
    """Pilih jam dari kandidat: utamakan yang tidak mundur terhadap baris sebelumnya pada tanggal yang
    sama (mutasi kronologis). prev = (tanggal_tuple, jam) atau None."""
    kand = v["jam_kandidat"]
    if not kand:
        return None
    if prev and prev[0] == (v["tahun"], v["bulan"], v["hari"]):
        for j in kand:
            if j >= prev[1]:
                return j
    return kand[0]


def _waktu_iso(v, hari_prev):
    hari = v["hari"] if v["hari"] is not None else hari_prev
    if hari is None or v["bulan"] is None or v["tahun"] is None:
        return None
    s = f"{v['tahun']:04d}-{v['bulan']:02d}-{hari:02d}"
    if v["jam"]:
        s += "T{:02d}:{:02d}:{:02d}".format(*v["jam"])
    return s


def _ke_record(v, nominal, saldo, waktu, bank, norek, nama):
    nominal = 0.0 if nominal is None else nominal
    return {"bank": bank.upper(), "no_rekening": norek, "source_file": nama,
            "waktu_transaksi": waktu, "keterangan": v["keterangan"],
            "debit": round(-nominal, 2) if nominal < 0 else 0.0,
            "kredit": round(nominal, 2) if nominal > 0 else 0.0,
            "saldo": None if saldo is None else round(saldo, 2)}


def process_scan_pdf(path, dpi=200):
    nama = os.path.basename(path)
    hasil = {"file": nama, "bank": None, "no_rekening": None, "status": "PERLU_REVIEW", "masalah": [],
             "tabel_bbox": [], "transaksi": [], "transaksi_ocr_murni": [], "koreksi": [], "sel_mentah": []}
    try:
        halaman = render_pages(path, dpi=dpi)
    except Exception as e:  # Poppler tidak terpasang, PDF rusak, dll.
        hasil["status"] = "GAGAL"
        hasil["masalah"].append(f"render PDF gagal: {e}")
        return hasil
    if not halaman:
        hasil["status"] = "GAGAL"
        hasil["masalah"].append("PDF tanpa halaman")
        return hasil
    gray0, _, _ = siapkan_halaman(halaman[0])
    bank = kenali_bank_scan(gray0)
    if bank is None:
        hasil["masalah"].append("bank scan tidak dikenali (header 'Rincian'/'Keterangan' tidak terbaca)")
        return hasil
    hasil["bank"] = bank.upper()

    mentah, meta = [], {}
    for i, img in enumerate(halaman):
        rows, info = baca_halaman(img, bank)
        if not info["header"]:
            hasil["masalah"].append(f"halaman {i + 1}: header tabel tidak ditemukan")
            continue
        h = info["h"]
        hasil["tabel_bbox"].append({"page": i + 1, "bbox": None, "y_header": int(h["nom"]["y"])})
        if i == 0:
            meta = META[bank](teks_atas(info["gray"], h["nom"]["y"] - 5))
        mentah += rows
    hasil["no_rekening"] = meta.get("no_rekening")
    tahun, bulan = meta.get("periode", (None, None))
    if hasil["no_rekening"] is None:
        hasil["masalah"].append("nomor rekening tidak terbaca dari header")
    if "periode" not in meta:
        hasil["masalah"].append("periode tidak terbaca dari header")

    semua = [(r, _baris_ke_nilai(r, bank, tahun, bulan)) for r in mentah]
    semua = [(r, v) for r, v in semua if v["nominal"] is not None or v["saldo"] is not None]
    vals = [v for _, v in semua]
    hasil["sel_mentah"] = [{k: r.get(k, "") for k in ("tanggal", "waktu", "keterangan", "nominal", "saldo")}
                           for r, _ in semua]
    if not vals:
        hasil["masalah"].append("tidak ada baris transaksi terbaca")
        return hasil

    # ---- angka 1: OCR murni ----
    def bangun(nom_saldo):
        recs, hari_prev, prev = [], None, None
        for v, (nom, sal) in zip(vals, nom_saldo):
            v["jam"] = _pilih_jam(v, prev)
            if v["jam"]:
                prev = ((v["tahun"], v["bulan"], v["hari"]), v["jam"])
            w = _waktu_iso(v, hari_prev)
            if v["hari"] is not None:
                hari_prev = v["hari"]
            recs.append(_ke_record(v, nom, sal, w, bank, hasil["no_rekening"], nama))
        return recs
    hasil["transaksi_ocr_murni"] = bangun([(v["nominal"], v["saldo"]) for v in vals])

    # ---- angka 2: setelah koreksi saldo ----
    koreksi_in = [dict(nominal=v["nominal_obs"], saldo=v["saldo_obs"]) for v in vals]
    koreksi_out, koreksi = koreksi_dp(koreksi_in, meta.get("saldo_awal"), meta.get("saldo_akhir"),
                                       desimal=DESIMAL[bank])
    hasil["transaksi"] = bangun([(r["nominal"], r["saldo"]) for r in koreksi_out])
    hasil["koreksi"] = koreksi

    # ---- validasi ----
    recs = hasil["transaksi"]
    tidak_pasti = [k for k in koreksi if not k["pasti"]]
    if tidak_pasti:
        hasil["masalah"].append(f"{len(tidak_pasti)} koreksi saldo tidak pasti (baris "
                                + ", ".join(str(k['indeks'] + 1) for k in tidak_pasti) + ")")
    if any(r["saldo"] is None for r in recs):
        hasil["masalah"].append("ada baris tanpa saldo yang bisa dihitung")
    else:
        hasil["masalah"] += validasi_ringkasan(recs, meta.get("saldo_akhir"), meta.get("total_debit"),
                                               meta.get("total_kredit"))
    if any(r["waktu_transaksi"] is None or "T" not in r["waktu_transaksi"] for r in recs):
        hasil["masalah"].append("ada baris dengan tanggal/jam tidak terbaca penuh")
    if hasil["koreksi"]:
        hasil.setdefault("catatan", []).append(f"{len(koreksi)} koreksi saldo diterapkan")
    hasil["status"] = "OK" if not hasil["masalah"] else "PERLU_REVIEW"
    return hasil