"""
hitung_kappa.py
===============
LANGKAH 3 (dijalankan SETELAH validator mengisi kolom label_validator).

Membandingkan label otomatis (kunci_label_sampel.csv) dengan label dari staf keuangan
(sampel_validasi_20persen.xlsx -> kolom label_validator) memakai Cohen's Kappa.
Target proposal: kappa >= 0.61 (substantial agreement).

Validator mengisi kolom label_validator dengan KODE label dari sheet 'Daftar Label'
(contoh: SALARY, PAYABLE_VENDOR). Baris yang dikosongkan dilewati.

Cara jalan (dari folder src):
    python hitung_kappa.py
"""
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from kategori_keuangan import LABEL_COA

DATA = Path(__file__).resolve().parent.parent / "data"
TARGET_KAPPA = 0.61


def tafsir(k):
    # skala Landis & Koch (1977)
    for batas, teks in [(0.81, "hampir sempurna"), (0.61, "substansial"), (0.41, "sedang"),
                        (0.21, "lemah"), (0.0, "sangat lemah")]:
        if k >= batas:
            return teks
    return "di bawah kebetulan"


def main():
    sampel = pd.read_excel(DATA / "sampel_validasi_20persen.xlsx", sheet_name="Sampel", dtype=str)
    kunci = pd.read_csv(DATA / "kunci_label_sampel.csv", dtype=str)
    df = sampel.merge(kunci, on="id", how="left")

    df["label_validator"] = df["label_validator"].fillna("").str.strip().str.upper()
    kosong = (df["label_validator"] == "").sum()
    df = df[df["label_validator"] != ""].copy()
    print(f"Baris sampel: {len(sampel)} | sudah diisi validator: {len(df)} | masih kosong: {kosong}")
    if len(df) < 20:
        print("Terlalu sedikit baris terisi untuk kappa yang bermakna. Minta validator melengkapi dulu.")
        return

    tak_dikenal = sorted(set(df["label_validator"]) - set(LABEL_COA))
    if tak_dikenal:
        print("PERINGATAN - kode label tidak dikenal (cek ejaan / daftar label):", tak_dikenal)
        df = df[df["label_validator"].isin(LABEL_COA)]

    kappa = cohen_kappa_score(df["label_otomatis"], df["label_validator"])
    sama = (df["label_otomatis"] == df["label_validator"]).mean()
    print(f"\nKesepakatan mentah : {sama:.1%}")
    print(f"Cohen's Kappa      : {kappa:.3f}  ({tafsir(kappa)})")
    if kappa >= TARGET_KAPPA:
        print(f"-> MEMENUHI target proposal (>= {TARGET_KAPPA}).")
    else:
        print(f"-> DI BAWAH target {TARGET_KAPPA}: adakan diskusi untuk merumuskan ulang aturan pelabelan "
              "(sesuai mitigasi risiko di proposal).")

    beda = df[df["label_otomatis"] != df["label_validator"]]
    print(f"\nBaris berbeda: {len(beda)}")
    if len(beda):
        pasangan = beda.groupby(["label_otomatis", "label_validator"]).size().sort_values(ascending=False)
        print("Pasangan perbedaan terbanyak (otomatis -> validator):")
        print(pasangan.head(10).to_string())
        beda[["id", "bank", "jenis", "mutasi", "keterangan_asli", "label_otomatis", "label_validator"]] \
            .to_csv(DATA / "hasil_kappa_perbedaan.csv", index=False)
        print("\nDaftar lengkap perbedaan: data/hasil_kappa_perbedaan.csv (bahan diskusi revisi aturan)")


if __name__ == "__main__":
    main()