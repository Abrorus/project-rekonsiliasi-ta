"""
routing.py
==========
Inferensi Pool 2: klasifikasi sub-kategori CoA + confidence routing ke Pool 3.

Memakai models/model_coa_final.pkl (hasil latih_model_coa.py) dan
models/threshold_coa.json (hasil threshold_coa.py).

Jalankan (dari folder src):  python routing.py
"""
import json
from pathlib import Path

import joblib

from kamus_istilah import normalisasi_teks
from kategori_keuangan import LABEL_COA

MODELS = Path(__file__).resolve().parent.parent / "models"


def load_model():
    paket = joblib.load(MODELS / "model_coa_final.pkl")
    f = MODELS / "threshold_coa.json"
    threshold = json.loads(f.read_text())["threshold"] if f.exists() else 0.66
    return paket["model"], threshold


def klasifikasi_transaksi(keterangan, jenis, model, threshold):
    """
    keterangan: teks mutasi mentah; jenis: 'CR' (kredit/cash in) atau 'DB' (debit/cash out).
    confidence >= threshold -> OTOMATIS; di bawahnya -> RUJUK_POOL3 (knowledge base).
    """
    teks = f"arah{jenis.lower()} " + normalisasi_teks(keterangan)
    proba = model.predict_proba([teks])[0]
    i = proba.argmax()
    label = model.classes_[i]
    return {
        "keterangan": keterangan,
        "jenis": jenis,
        "label": label,
        "nama_akun": LABEL_COA[label]["nama"],
        "confidence": round(float(proba[i]), 4),
        "status": "OTOMATIS" if proba[i] >= threshold else "RUJUK_POOL3",
    }


def main():
    model, threshold = load_model()
    contoh = [
        ("TRSF E-BANKING PANCA BERSAUDARA", "CR"),
        ("BPJS KS Jakarta Feb25", "DB"),
        ("BIAYA ADM", "DB"),
        ("beli kopi untuk tamu", "DB"),
        ("pulsa kantor jan", "DB"),
    ]
    print(f"=== Simulasi Routing (threshold={threshold}) ===\n")
    for teks, jenis in contoh:
        h = klasifikasi_transaksi(teks, jenis, model, threshold)
        print(f"[{h['jenis']}] {h['keterangan']:<34} -> {h['label']:<20} "
              f"conf={h['confidence']:.2f}  {h['status']}")


if __name__ == "__main__":
    main()
