"""
evaluasi_routing_kb.py
======================
Menghitung:
  1. Matriks Konfusi (Confusion Matrix) 5-fold CV pada 14 sub-kategori CoA -> data/confusion_matrix_coa.csv
  2. Keempat metrik Confidence Routing sesuai Tabel Proposal Bab 3.2.7:
       - Auto-Classification Rate (N_auto / N_total)
       - KB Referral Rate         (N_referred / N_total)
       - KB Resolution Rate       (N_resolved / N_referred)
       - Overall System Coverage  ((N_auto + N_resolved) / N_total)
     Simulasi resolusi Pool 3 (Knowledge Base) dilakukan berbasis aturan forward-chaining sesuai
     proposal Bab 3.2.7: pencocokan daftar vendor/customer terdaftar, nomor rekening internal,
     kamus sinonim/kata kunci operasional, dan pencocokan nominal mutasi berulang.

Output:
  - data/confusion_matrix_coa.csv
  - data/hasil_metrik_routing_kb.csv

Jalankan dari folder src:  python evaluasi_routing_kb.py
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from latih_model_coa import DATA, N_FOLD, RANDOM_STATE, buat_model, muat_riil

warnings.filterwarnings("ignore")
THRESHOLD_OPT = 0.72


def simulasi_kb_pool3(df_train, baris_uji):
    """
    Simulasi forward-chaining Knowledge Base (Pool 3) pada transaksi yang confidence < threshold:
      Aturan 1 (Referensi Pihak/Rekening Terdaftar):
        Jika keterangan mengandung nama vendor/customer/entitas yang sudah pernah tercatat di ERP (data latih)
        dengan arah (CR/DB) yang sama, gunakan kategori mayoritas entitas tersebut.
      Aturan 2 (Pencocokan Nominal Invoice/Mutasi Historis):
        Jika nominal mutasi persis sama dengan transaksi historis berarah sama (mis. cicilan/invoice terbuka),
        gunakan kategori transaksi historis tersebut.
      Aturan 3 (Kamus Kata Kunci Spesifik Operasional):
        Jika mengandung kata kunci spesifik (kopi/tamu/materai -> OFFICE_GENERAL, pulsa -> COMMUNICATION,
        pln/listrik -> UTILITIES, bbm/tol/parkir -> TRANSPORT), petakan ke sub-kategori terkait.
    Mengembalikan (label_kb, berhasil_resolved: bool, aturan_dipakai: str).
    """
    ket = str(baris_uji["keterangan"]).lower()
    jenis = baris_uji["jenis"]
    mutasi = baris_uji["mutasi"]

    # Aturan 3: Kamus Kata Kunci Operasional KB
    aturan_kamus = [
        (["kopi", "tamu", "materai", "atk", "kertas", "galon", "konsumsi"], "OFFICE_GENERAL"),
        (["pulsa", "paket data", "kuota", "indihome", "telkom"], "COMMUNICATION"),
        (["pln", "listrik", "pdam", "air"], "UTILITIES"),
        (["bbm", "pertamina", "tol", "parkir", "bensin", "grab", "gojek"], "TRANSPORT"),
        (["pajak", "ppn", "pph", "penerimaan negara"], "TAX"),
        (["adm", "biaya transfer", "biaya admin"], "BANK_CHARGE"),
    ]
    for kata_list, label_target in aturan_kamus:
        if any(k in ket for k in kata_list):
            return label_target, True, "Aturan Kamus Operasional KB"

    # Aturan 1: Pencocokan Entitas / Rekanan ERP (teks_model yang sama arahnya di data historis)
    searah = df_train[df_train["jenis"] == jenis]
    token_uji = [t for t in str(baris_uji["teks_model"]).split() if not t.startswith("arah") and len(t) > 3]
    for tok in token_uji:
        cocok = searah[searah["teks_model"].str.contains(rf"\b{tok}\b", regex=True)]
        if len(cocok) >= 2:
            top_label = cocok["label"].value_counts().index[0]
            if cocok["label"].value_counts().iloc[0] / len(cocok) >= 0.75:
                return top_label, True, f"Referensi Entitas ERP ({tok})"

    # Aturan 2: Pencocokan Nominal Invoice / Mutasi Identik
    if pd.notna(mutasi) and float(mutasi) > 0:
        cocok_nom = searah[np.isclose(searah["mutasi"].astype(float), float(mutasi), rtol=1e-5)]
        if len(cocok_nom) >= 1:
            return cocok_nom["label"].value_counts().index[0], True, "Matching Nominal Invoice/Mutasi ERP"

    return None, False, "Perlu Konfirmasi Manual Staf"


def main():
    df, _ = muat_riil()
    X, y = df["teks_model"], df["label"]
    kelas = np.array(sorted(set(y)))

    cv = StratifiedKFold(n_splits=N_FOLD, shuffle=True, random_state=RANDOM_STATE)
    model_kal = buat_model("kata+huruf", kalibrasi=True)
    proba = cross_val_predict(model_kal, X, y, cv=cv, method="predict_proba")
    pred_svm = kelas[proba.argmax(1)]
    conf = proba.max(1)

    # 1. Confusion Matrix 14x14
    cm = confusion_matrix(y, pred_svm, labels=kelas)
    df_cm = pd.DataFrame(cm, index=kelas, columns=kelas)
    df_cm.to_csv(DATA / "confusion_matrix_coa.csv")
    print(f"Confusion Matrix ({len(kelas)}x{len(kelas)}) tersimpan di: data/confusion_matrix_coa.csv")

    # 2. Evaluasi Routing ke Pool 3 (out-of-fold)
    auto_mask = conf >= THRESHOLD_OPT
    referred_idx = np.where(~auto_mask)[0]

    pred_final = pred_svm.copy()
    resolved_flags = []
    aturan_log = []

    # Map setiap baris ke fold-train masing-masing agar simulasi KB tidak bocor data uji
    fold_train_map = {}
    for tr, te in cv.split(X, y):
        for idx in te:
            fold_train_map[idx] = df.iloc[tr]

    for idx in referred_idx:
        lbl_kb, ok, alasan = simulasi_kb_pool3(fold_train_map[idx], df.iloc[idx])
        resolved_flags.append(ok)
        aturan_log.append(alasan)
        if ok and lbl_kb in kelas:
            pred_final[idx] = lbl_kb

    n_total = len(df)
    n_auto = int(auto_mask.sum())
    n_referred = int((~auto_mask).sum())
    n_resolved = int(sum(resolved_flags))
    n_unresolved = n_referred - n_resolved

    auto_rate = n_auto / n_total * 100
    ref_rate = n_referred / n_total * 100
    res_rate = (n_resolved / n_referred * 100) if n_referred else 0.0
    cov_rate = (n_auto + n_resolved) / n_total * 100

    # Akurasi pada transaksi yang terklasifikasi sistem (Pool 2 Auto + Pool 3 Resolved)
    tertangani_mask = auto_mask.copy()
    for idx, ok in zip(referred_idx, resolved_flags):
        if ok:
            tertangani_mask[idx] = True

    acc_auto = accuracy_score(y[auto_mask], pred_svm[auto_mask]) * 100
    acc_gabungan = accuracy_score(y[tertangani_mask], pred_final[tertangani_mask]) * 100
    f1_gabungan = f1_score(y[tertangani_mask], pred_final[tertangani_mask], average="macro", zero_division=0) * 100

    metrik_routing = pd.DataFrame([
        {"Metrik": "Auto-Classification Rate (Jalur Otomatis)", "Jumlah": f"{n_auto}/{n_total}", "Nilai (%)": round(auto_rate, 2)},
        {"Metrik": "KB Referral Rate (Dirujuk ke Jalur KB)", "Jumlah": f"{n_referred}/{n_total}", "Nilai (%)": round(ref_rate, 2)},
        {"Metrik": "KB Resolution Rate (Diselesaikan Aturan Jalur KB)", "Jumlah": f"{n_resolved}/{n_referred}", "Nilai (%)": round(res_rate, 2)},
        {"Metrik": "Overall System Coverage (Jalur Otomatis + Jalur KB)", "Jumlah": f"{n_auto + n_resolved}/{n_total}", "Nilai (%)": round(cov_rate, 2)},
        {"Metrik": "Sisa Review Manual Staf Keuangan", "Jumlah": f"{n_unresolved}/{n_total}", "Nilai (%)": round(n_unresolved / n_total * 100, 2)},
        {"Metrik": "Akurasi Jalur Otomatis", "Jumlah": f"{n_auto} baris", "Nilai (%)": round(acc_auto, 2)},
        {"Metrik": "Akurasi Sistem Hibrida (Jalur Otomatis + Jalur KB)", "Jumlah": f"{n_auto + n_resolved} baris", "Nilai (%)": round(acc_gabungan, 2)},
        {"Metrik": "Macro-F1 Sistem Hibrida (Jalur Otomatis + Jalur KB)", "Jumlah": f"{n_auto + n_resolved} baris", "Nilai (%)": round(f1_gabungan, 2)},
    ])
    metrik_routing.to_csv(DATA / "hasil_metrik_routing_kb.csv", index=False)
    print("\n=== Hasil Pengukuran Performa Confidence Routing & Integrasi KB ===")
    print(metrik_routing.to_string(index=False))
    print("\nRincian resolusi di Jalur KB:")
    print(pd.Series(aturan_log).value_counts().to_string())


if __name__ == "__main__":
    main()

