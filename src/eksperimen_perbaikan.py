"""
eksperimen_perbaikan.py
=======================
Menjawab dua catatan dosen/penguji potensial:
  1. Proposal menetapkan SVM kernel RBF -> bandingkan RBF vs Linear (fitur kata+huruf yang sama).
  2. Model bisa menghafal NAMA PIHAK, bukan jenis transaksi -> uji
       (a) tanpa token nama pihak (masking),
       (b) validasi 'teks belum pernah dilihat' (GroupKFold: semua baris dengan teks identik berada di fold yang sama),
     supaya angka tidak digelembungkan duplikat transaksi berulang.

Output: data/hasil_eksperimen_perbaikan.csv

Jalankan (dari folder src):  python eksperimen_perbaikan.py
"""
import re
import warnings

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC, LinearSVC

from latih_model_coa import DATA, N_FOLD, RANDOM_STATE, buat_fitur, muat_riil

warnings.filterwarnings("ignore")

# token nama pihak: dari rekap_nama_untuk_labeling.csv + nama yang dominan di data Mandiri (hasil 4.3)
NAMA_TAMBAHAN = """santosa makmur jaya darbe abadi securindo tri mitra setiawan dadang tjahyono wahyu abad
megadc sugiono lesmana didit avanza panca bersaudara amertha bareka lintas indo sentot prabowo""".split()


def kumpulan_nama():
    rekap = pd.read_csv(DATA / "rekap_nama_untuk_labeling.csv")
    tok = set()
    for n in rekap["nama_pihak"]:
        tok |= set(re.sub(r"[^a-z\s]", " ", str(n).lower()).split())
    return {t for t in tok | set(NAMA_TAMBAHAN) if len(t) > 1}


def mask(teks, nama):
    return " ".join(t for t in teks.split() if t not in nama)


def model(kernel):
    clf = LinearSVC(C=1.0, class_weight="balanced", max_iter=5000, random_state=RANDOM_STATE) \
        if kernel == "linear" else SVC(kernel="rbf", C=1.0, gamma="scale", class_weight="balanced")
    return Pipeline([("fitur", buat_fitur("kata+huruf")), ("svm", clf)])


def cv_skor(X, y, kernel, grup=None):
    if grup is None:
        splitter = StratifiedKFold(N_FOLD, shuffle=True, random_state=RANDOM_STATE).split(X, y)
    else:
        splitter = StratifiedGroupKFold(N_FOLD, shuffle=True, random_state=RANDOM_STATE).split(X, y, grup)
    acc, f1 = [], []
    for tr, te in splitter:
        m = model(kernel).fit(X.iloc[tr], y.iloc[tr])
        p = m.predict(X.iloc[te])
        yt = y.iloc[te]
        acc.append(accuracy_score(yt, p))
        f1.append(f1_score(yt, p, average="macro", labels=sorted(set(yt)), zero_division=0))
    return sum(acc) / len(acc), sum(f1) / len(f1)


def main():
    df, _ = muat_riil()
    nama = kumpulan_nama()
    awal = df["teks_model"]
    tanpa_nama = awal.apply(lambda t: mask(t, nama))
    y = df["label"]
    grup = pd.factorize(awal)[0]
    print(f"Teks unik: {len(set(awal))} dari {len(df)} baris ({len(df) - len(set(awal))} duplikat) | token nama dimasking: {len(nama)}")

    baris = []
    for nama_fitur, X in [("dengan nama pihak", awal), ("tanpa nama pihak", tanpa_nama)]:
        for skema, g in [("StratifiedKFold", None), ("GroupKFold (teks belum pernah dilihat)", grup)]:
            for kernel in ["linear", "rbf"]:
                a, f = cv_skor(X, y, kernel, g)
                baris.append({"fitur": nama_fitur, "validasi": skema, "kernel": kernel, "akurasi": a, "macro_f1": f})
                print(f"{nama_fitur:<18} {skema:<40} {kernel:<7} acc={a:.3f} macroF1={f:.3f}")
    pd.DataFrame(baris).to_csv(DATA / "hasil_eksperimen_perbaikan.csv", index=False)
    print("Tersimpan: data/hasil_eksperimen_perbaikan.csv")


if __name__ == "__main__":
    main()

