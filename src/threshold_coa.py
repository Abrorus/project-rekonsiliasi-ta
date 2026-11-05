"""
threshold_coa.py
================
LANGKAH 4 pipeline Pool 2: penentuan confidence threshold pada model CoA (proposal Bab 3.2.7).

Skor confidence = probabilitas SVM terkalibrasi, dihitung OUT-OF-FOLD (5-fold) sehingga tidak bocor.
Dievaluasi pada dua skema:
  1. StratifiedKFold (standar: mencerminkan distribusi transaksi rutin/berulang) -> dipakai sebagai threshold utama.
  2. StratifiedGroupKFold (ketat: teks identik tidak boleh terpecah antar fold / teks baru) -> analisis sensitivitas.

Output: data/hasil_threshold_coa.csv, data/hasil_threshold_coa_group.csv, models/threshold_coa.json

Jalankan (dari folder src):  python threshold_coa.py
"""
import json
import warnings

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from latih_model_coa import DATA, MODELS, N_FOLD, RANDOM_STATE, buat_fitur, buat_model, muat_riil

warnings.filterwarnings("ignore")
MIN_COVERAGE = 0.70


def tabel_threshold(y, pred, conf):
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
    return pd.DataFrame(baris), int((~benar).sum())


def cetak_ringkasan(judul, tab, total_salah):
    print(f"\n=== {judul} ===")
    print(tab.iloc[::4].round(3).to_string(index=False))
    ok = tab[tab["auto_rate"] >= MIN_COVERAGE]
    opt = ok.loc[ok["f1_macro_auto"].idxmax()]
    t_opt = float(opt["threshold"])
    print(f"\nThreshold optimal: {t_opt} (auto-rate >= {MIN_COVERAGE:.0%})")
    print(f"Auto-classification rate : {opt['auto_rate']:.1%}")
    print(f"KB referral rate         : {opt['kb_referral_rate']:.1%}")
    print(f"Akurasi / Macro-F1 (auto): {opt['akurasi_auto']:.3f} / {opt['f1_macro_auto']:.3f}")
    print(f"Kesalahan dialihkan ke KB: {int(opt['salah_terdeteksi_ke_kb'])} dari {total_salah} kesalahan")
    return t_opt


def main():
    df, _ = muat_riil()
    X, y = df["teks_model"], df["label"]
    kelas = np.array(sorted(set(y)))

    # 1. StratifiedKFold (standar)
    cv_std = StratifiedKFold(n_splits=N_FOLD, shuffle=True, random_state=RANDOM_STATE)
    proba_std = cross_val_predict(buat_model("kata+huruf", kalibrasi=True), X, y, cv=cv_std, method="predict_proba")
    tab_std, salah_std = tabel_threshold(y, kelas[proba_std.argmax(1)], proba_std.max(1))
    tab_std.to_csv(DATA / "hasil_threshold_coa.csv", index=False)
    t_std = cetak_ringkasan("1. StratifiedKFold (Distribusi Transaksi Rutin)", tab_std, salah_std)

    # 2. StratifiedGroupKFold (ketat: teks belum pernah dilihat)
    grup = pd.factorize(X)[0]
    cv_grp = list(StratifiedGroupKFold(n_splits=N_FOLD, shuffle=True, random_state=RANDOM_STATE).split(X, y, grup))
    proba_grp = np.zeros((len(y), len(kelas)))
    for tr, te in cv_grp:
        cnt = y.iloc[tr].value_counts()
        tr = np.asarray(tr)[y.iloc[tr].isin(cnt[cnt >= 2].index).values]
        folds_kal = int(min(3, y.iloc[tr].value_counts().min()))
        svm = CalibratedClassifierCV(LinearSVC(C=1.0, class_weight="balanced", max_iter=5000,
                                               random_state=RANDOM_STATE), cv=folds_kal)
        m = Pipeline([("fitur", buat_fitur("kata+huruf")), ("svm", svm)]).fit(X.iloc[tr], y.iloc[tr])
        proba_grp[np.ix_(te, np.searchsorted(kelas, m.classes_))] = m.predict_proba(X.iloc[te])
    tab_grp, salah_grp = tabel_threshold(y, kelas[proba_grp.argmax(1)], proba_grp.max(1))
    tab_grp.to_csv(DATA / "hasil_threshold_coa_group.csv", index=False)
    t_grp = cetak_ringkasan("2. StratifiedGroupKFold (Teks Belum Pernah Dilihat)", tab_grp, salah_grp)

    (MODELS / "threshold_coa.json").write_text(json.dumps({"threshold": t_std, "threshold_group_cv": t_grp}))
    print("\nTersimpan: models/threshold_coa.json, data/hasil_threshold_coa.csv, data/hasil_threshold_coa_group.csv")


if __name__ == "__main__":
    main()
