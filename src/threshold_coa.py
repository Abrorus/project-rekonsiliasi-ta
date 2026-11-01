"""
threshold_coa.py
================
LANGKAH 4 pipeline Pool 2: penentuan confidence threshold pada model CoA (proposal Bab 3.2.7).

Skor confidence = probabilitas SVM terkalibrasi, dihitung OUT-OF-FOLD (5-fold) sehingga tidak bocor.
Grid threshold 0.50-0.99 (step 0.01). Threshold optimal = F1 macro tertinggi pada transaksi
yang lolos otomatis, dengan syarat auto-classification rate >= MIN_COVERAGE (seperti confidence_threshold.py lama).
Transaksi di bawah threshold dirujuk ke Pool 3 (knowledge base).

Output: data/hasil_threshold_coa.csv, models/threshold_coa.json

Jalankan (dari folder src):  python threshold_coa.py
"""
import json
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from latih_model_coa import DATA, MODELS, N_FOLD, RANDOM_STATE, buat_model, muat_riil

warnings.filterwarnings("ignore")
MIN_COVERAGE = 0.70


def main():
    df, _ = muat_riil()
    X, y = df["teks_model"], df["label"]
    cv = StratifiedKFold(n_splits=N_FOLD, shuffle=True, random_state=RANDOM_STATE)
    # kalibrasi memakai cv=3 -> label dengan < 3 contoh per fold-latih sudah disaring oleh MIN_PER_LABEL
    model = buat_model("kata+huruf", kalibrasi=True)
    proba = cross_val_predict(model, X, y, cv=cv, method="predict_proba")
    kelas = np.array(sorted(set(y)))
    pred, conf = kelas[proba.argmax(1)], proba.max(1)
    benar = pred == y.values

    baris = []
    for t in np.round(np.arange(0.50, 1.00, 0.01), 2):
        m = conf >= t
        if m.sum() < 5:
            continue
        baris.append({
            "threshold": t,
            "auto_rate": m.mean(),
            "kb_referral_rate": 1 - m.mean(),
            "akurasi_auto": accuracy_score(y[m], pred[m]),
            "f1_macro_auto": f1_score(y[m], pred[m], average="macro", labels=sorted(set(y[m])), zero_division=0),
            "salah_lolos": int((~benar[m]).sum()),
            "salah_terdeteksi_ke_kb": int((~benar[~m]).sum()),
        })
    tab = pd.DataFrame(baris)
    tab.to_csv(DATA / "hasil_threshold_coa.csv", index=False)
    print(tab.iloc[::4].round(3).to_string(index=False))

    ok = tab[tab["auto_rate"] >= MIN_COVERAGE]
    opt = ok.loc[ok["f1_macro_auto"].idxmax()]
    t_opt = float(opt["threshold"])
    print(f"\n=== Threshold optimal: {t_opt} (auto-rate >= {MIN_COVERAGE:.0%}) ===")
    print(f"Auto-classification rate : {opt['auto_rate']:.1%}")
    print(f"KB referral rate         : {opt['kb_referral_rate']:.1%}")
    print(f"Akurasi / Macro-F1 (auto): {opt['akurasi_auto']:.3f} / {opt['f1_macro_auto']:.3f}")
    print(f"Kesalahan yang berhasil dialihkan ke KB: {int(opt['salah_terdeteksi_ke_kb'])} "
          f"dari total {int((~benar).sum())} kesalahan")

    (MODELS / "threshold_coa.json").write_text(json.dumps({"threshold": t_opt}))
    print("Tersimpan: models/threshold_coa.json, data/hasil_threshold_coa.csv")


if __name__ == "__main__":
    main()

