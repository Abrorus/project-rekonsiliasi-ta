"""
uji_active_learning.py
======================
Eksperimen evaluasi Active Learning / Feedback Loop 5 Putaran (sesuai arahan Pak Deptha pada
meeting 23 November 2026):
  - Menguji apakah sistem benar-benar BELAJAR dari koreksi manual pengguna (baik yang confidence
    >= 0,72 maupun < 0,72) sehingga pada putaran berikutnya akurasi pada transaksi BARU (yang
    belum pernah dilihat persis sebelumnya) meningkat secara terukur.

Skenario eksperimen:
  - Dataset dibagi berdasarkan grup teks unik (agar tidak bocor duplikat) menjadi:
      * 20% Data Latih Awal (Putaran 0 — kondisi sistem baru dipakai pertama kali)
      * 60% Pool Aliran Transaksi Harian (dibagi menjadi 5 batch / putaran koreksi)
      * 20% Data Uji Tetap (Hold-out Test Set berisi teks unik yang tidak pernah masuk latih)
  - Pada tiap putaran (1 s.d. 5):
      1. Model memprediksi batch transaksi baru.
      2. Seluruh prediksi yang SALAH (baik confidence >= 0,72 maupun < 0,72) dikoreksi manusia.
      3. Koreksi dimasukkan ke data latih, model dilatih ulang.
      4. Model dievaluasi pada Hold-out Test Set (teks baru) untuk mengukur kenaikan Akurasi
         dan Macro-F1.

Output: data/hasil_active_learning_5putaran.csv

Jalankan dari folder src:  python uji_active_learning.py
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import GroupShuffleSplit

from latih_model_coa import DATA, RANDOM_STATE, buat_model, muat_riil

warnings.filterwarnings("ignore")


def main():
    df, _ = muat_riil()
    grup = pd.factorize(df["teks_model"])[0]

    # Pisahkan 20% Hold-out Test Set (teks unik yang benar-benar tidak pernah dilihat)
    gss_test = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=RANDOM_STATE)
    idx_sisa, idx_test = next(gss_test.split(df, df["label"], grup))
    df_sisa = df.iloc[idx_sisa].reset_index(drop=True)
    df_test = df.iloc[idx_test].reset_index(drop=True)

    # Dari sisa (80%), ambil 25%-nya (= 20% total) sebagai data latih awal (Putaran 0)
    grup_sisa = pd.factorize(df_sisa["teks_model"])[0]
    gss_init = GroupShuffleSplit(n_splits=1, test_size=0.75, random_state=RANDOM_STATE)
    idx_init, idx_stream = next(gss_init.split(df_sisa, df_sisa["label"], grup_sisa))
    df_train = df_sisa.iloc[idx_init].copy()
    df_stream = df_sisa.iloc[idx_stream].sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)

    # Bagi aliran transaksi menjadi 5 putaran (rounds)
    batches = [df_stream.iloc[idx].reset_index(drop=True) for idx in np.array_split(np.arange(len(df_stream)), 5)]
    label_uji = sorted(set(df_test["label"]))

    hasil = []
    # Putaran 0 (sebelum ada koreksi manual)
    model = buat_model("kata+huruf").fit(df_train["teks_model"], df_train["label"])
    pred_test = model.predict(df_test["teks_model"])
    acc0 = accuracy_score(df_test["label"], pred_test)
    f10 = f1_score(df_test["label"], pred_test, average="macro", labels=label_uji, zero_division=0)
    hasil.append({
        "putaran": 0,
        "keterangan": "Model Awal (sebelum koreksi)",
        "total_data_latih": len(df_train),
        "transaksi_masuk": 0,
        "jumlah_dikoreksi": 0,
        "akurasi_holdout": round(acc0, 4),
        "macro_f1_holdout": round(f10, 4),
    })

    # Putaran 1 s.d. 5: prediksi batch -> koreksi manual yang salah -> latih ulang -> uji hold-out
    for r, batch in enumerate(batches, start=1):
        pred_b = model.predict(batch["teks_model"])
        salah_mask = pred_b != batch["label"].values
        df_koreksi = batch[salah_mask].copy()
        # Masukkan koreksi manusia ke data latih (semua yang dikoreksi, baik auto-match maupun review)
        df_train = pd.concat([df_train, df_koreksi], ignore_index=True)
        model = buat_model("kata+huruf").fit(df_train["teks_model"], df_train["label"])

        pred_test = model.predict(df_test["teks_model"])
        acc = accuracy_score(df_test["label"], pred_test)
        f1 = f1_score(df_test["label"], pred_test, average="macro", labels=label_uji, zero_division=0)
        hasil.append({
            "putaran": r,
            "keterangan": f"Setelah Koreksi Putaran {r}",
            "total_data_latih": len(df_train),
            "transaksi_masuk": len(batch),
            "jumlah_dikoreksi": int(salah_mask.sum()),
            "akurasi_holdout": round(acc, 4),
            "macro_f1_holdout": round(f1, 4),
        })

    tab = pd.DataFrame(hasil)
    tab.to_csv(DATA / "hasil_active_learning_5putaran.csv", index=False)
    print("\n=== Evaluasi Active Learning 5 Putaran (Hold-out Teks Baru, n_test =", len(df_test), ") ===")
    print(tab.to_string(index=False))
    print("\nTersimpan: data/hasil_active_learning_5putaran.csv")


def uji_demo_feedback():
    """Verifikasi end-to-end: koreksi untuk skor <0.72 MAUPUN >=0.72 lalu uji teks sama & serupa."""
    import shutil
    from feedback_learning import FILE_FEEDBACK
    from latih_model_coa import MODELS
    from proses_json import klasifikasi_batch, refresh_model, terapkan_koreksi

    model_pkl = MODELS / "model_coa_final.pkl"
    backup_pkl = MODELS / "model_coa_final.pkl.bak"
    shutil.copyfile(model_pkl, backup_pkl)
    try:
        batch_uji = [
            {"tanggal": "2025-02-01", "keterangan": "pulsa kantor jan", "debit": 150000, "kredit": 0, "saldo": 1000000},
            {"tanggal": "2025-02-02", "keterangan": "MCM InhouseTrf payroll SANTOSA JAYA MAKMUR", "debit": 5000000, "kredit": 0, "saldo": 5000000},
        ]
        print("\n=== DEMO FEEDBACK LOOP: SEBELUM KOREKSI ===")
        h1 = klasifikasi_batch(batch_uji)
        for t in h1["transaksi"]:
            print(f"  [{t['status']:<19}] {t['keterangan']:<44} -> {t['label']:<20} conf={t['confidence']}")

        terapkan_koreksi(h1, {"0": "COMMUNICATION", "1": "INTERNAL_TRANSFER"}, simpan_feedback=True, latih_ulang=True)

        print("\n=== DEMO FEEDBACK LOOP: SESUDAH KOREKSI & RETRAIN (teks sama + teks SERUPA) ===")
        batch_besok = [
            {"tanggal": "2025-03-01", "keterangan": "pulsa kantor jan", "debit": 150000, "kredit": 0, "saldo": 1000000},
            {"tanggal": "2025-03-02", "keterangan": "bayar pulsa kantor maret", "debit": 200000, "kredit": 0, "saldo": 800000},
            {"tanggal": "2025-03-03", "keterangan": "MCM InhouseTrf payroll SANTOSA JAYA MAKMUR", "debit": 5000000, "kredit": 0, "saldo": 5000000},
            {"tanggal": "2025-03-04", "keterangan": "MCM InhouseTrf payroll feb SANTOSA JAYA MAKMUR", "debit": 5200000, "kredit": 0, "saldo": 4800000},
        ]
        h2 = klasifikasi_batch(batch_besok)
        for t in h2["transaksi"]:
            print(f"  [{t['status']:<19}] ({t['sumber_label']:<15}) {t['keterangan']:<47} -> {t['label']:<20} conf={t['confidence']}")
    finally:
        if FILE_FEEDBACK.exists():
            FILE_FEEDBACK.unlink()
        shutil.move(backup_pkl, model_pkl)
        refresh_model()


if __name__ == "__main__":
    main()
    uji_demo_feedback()
