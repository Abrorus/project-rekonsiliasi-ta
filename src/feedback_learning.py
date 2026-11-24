"""
feedback_learning.py
====================
Mekanisme pembelajaran berkelanjutan (Active Learning / Feedback Loop) untuk Modul NLP Pool 2.

Sesuai arahan Pak Deptha & dosen pembimbing:
  - Setiap koreksi dari pengguna (BAIK yang semula confidence >= 0,72 / OTOMATIS maupun < 0,72 / PERLU_REVIEW_MANUAL)
    dicatat secara permanen ke data/feedback_koreksi.csv.
  - Saat latih_ulang_dengan_feedback() dijalankan:
      1. Koreksi manusia menimpa (override) label lama untuk pola teks yang sama pada dataset dasar
         agar model tidak bingung oleh label lama yang salah.
      2. Koreksi manusia diberi penguatan bobot (BOBOT_FEEDBACK) saat pelatihan ulang LinearSVC
         terkalibrasi sehingga hyperplane bergeser bukan hanya untuk teks persis sama, tetapi juga
         untuk transaksi SERUPA melalui fitur TF-IDF kata + karakter n-gram.
      3. Model final (models/model_coa_final.pkl) diperbarui di disk agar prediksi berikutnya
         langsung menggunakan pengetahuan baru.

Pemakaian dari kode Python / FastAPI (Mario):
    from src.feedback_learning import catat_koreksi, latih_ulang_dengan_feedback
"""
from datetime import datetime
from pathlib import Path
import warnings

import joblib
import pandas as pd

from kamus_istilah import normalisasi_teks
from kategori_keuangan import LABEL_COA
from latih_model_coa import DATA, MIN_PER_LABEL, MODELS, buat_model, muat_riil, muat_sintesis

warnings.filterwarnings("ignore", category=UserWarning)

FILE_FEEDBACK = DATA / "feedback_koreksi.csv"
KOLOM_FEEDBACK = [
    "timestamp", "keterangan", "jenis", "teks_model",
    "label_lama", "label_baru", "confidence_lama", "status_lama",
]
BOBOT_FEEDBACK = 3  # penguatan sampel koreksi manusia agar segera mempengaruhi hyperplane SVM


def _buat_teks_model(keterangan, jenis):
    return f"arah{str(jenis).lower()} " + normalisasi_teks(str(keterangan))


def muat_feedback():
    if not FILE_FEEDBACK.exists():
        return pd.DataFrame(columns=KOLOM_FEEDBACK)
    df = pd.read_csv(FILE_FEEDBACK)
    for k in KOLOM_FEEDBACK:
        if k not in df.columns:
            df[k] = ""
    return df[KOLOM_FEEDBACK]


def peta_memori_koreksi():
    """
    Mengembalikan dict {teks_model: label_baru} dari koreksi terbaru.
    Jika teks yang sama dikoreksi lebih dari sekali, koreksi PALING BARU yang berlaku.
    """
    fb = muat_feedback()
    if fb.empty:
        return {}
    return dict(zip(fb["teks_model"], fb["label_baru"]))


def catat_koreksi(daftar_koreksi):
    """
    daftar_koreksi: list of dict dengan minimal key: keterangan, jenis, label_baru.
    Opsional: label_lama, confidence_lama, status_lama.
    Menyimpan ke data/feedback_koreksi.csv dan mengembalikan jumlah baris baru yang dicatat.
    """
    if not daftar_koreksi:
        return 0
    baris_baru = []
    waktu = datetime.now().isoformat(timespec="seconds")
    for item in daftar_koreksi:
        lab = str(item["label_baru"]).strip().upper()
        if lab not in LABEL_COA:
            raise ValueError(f"Label koreksi tidak dikenal: {lab}")
        jenis = str(item.get("jenis", "DB")).strip().upper()
        ket = str(item.get("keterangan", "")).strip()
        baris_baru.append({
            "timestamp": waktu,
            "keterangan": ket,
            "jenis": jenis,
            "teks_model": _buat_teks_model(ket, jenis),
            "label_lama": str(item.get("label_lama", "")),
            "label_baru": lab,
            "confidence_lama": float(item.get("confidence_lama", 0.0) or 0.0),
            "status_lama": str(item.get("status_lama", "")),
        })

    lama = muat_feedback()
    gab = pd.concat([lama, pd.DataFrame(baris_baru)], ignore_index=True)
    gab.to_csv(FILE_FEEDBACK, index=False)
    return len(baris_baru)


def latih_ulang_dengan_feedback(mode="kata+huruf", simpan=True):
    """
    Melatih ulang model SVM terkalibrasi dengan menggabungkan:
      - Data riil dasar (data_riil_berlabel_coa.csv)
      - Data sintesis untuk kelas langka (< MIN_PER_LABEL)
      - Seluruh koreksi manusia dari data/feedback_koreksi.csv (dengan override label lama + bobot)
    Mengembalikan model terlatih.
    """
    _, semua = muat_riil()
    sint = muat_sintesis()
    fb = muat_feedback()

    latih = semua[["keterangan", "jenis", "label", "teks_model"]].copy()
    if sint is not None:
        hitung = latih["label"].value_counts()
        langka = set(hitung[hitung < MIN_PER_LABEL].index)
        if langka:
            tambahan = sint[sint["label"].isin(langka)][["keterangan", "jenis", "label", "teks_model"]]
            latih = pd.concat([latih, tambahan], ignore_index=True)

    if not fb.empty:
        # 1. Koreksi terbaru menimpa label lama pada teks_model yang sama
        terbaru = fb.drop_duplicates(subset=["teks_model"], keep="last")
        peta_override = dict(zip(terbaru["teks_model"], terbaru["label_baru"]))
        mask_override = latih["teks_model"].isin(peta_override)
        if mask_override.any():
            latih.loc[mask_override, "label"] = latih.loc[mask_override, "teks_model"].map(peta_override)

        # 2. Tambahkan baris koreksi manusia dengan bobot BOBOT_FEEDBACK agar menggeser hyperplane
        df_fb = terbaru[["keterangan", "jenis", "label_baru", "teks_model"]].rename(
            columns={"label_baru": "label"}
        )
        latih = pd.concat([latih] + [df_fb] * BOBOT_FEEDBACK, ignore_index=True)

    # Kalibrasi cv=3 butuh minimal 3 contoh per kelas
    total = latih["label"].value_counts()
    latih = latih[~latih["label"].isin(total[total < 3].index)].reset_index(drop=True)

    model = buat_model(mode, kalibrasi=True).fit(latih["teks_model"], latih["label"])
    if simpan:
        joblib.dump(
            {
                "model": model,
                "mode": mode,
                "labels": list(model.classes_),
                "jumlah_feedback": len(fb),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
            MODELS / "model_coa_final.pkl",
        )
    return model
