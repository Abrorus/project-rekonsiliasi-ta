"""
latih_model_coa.py
==================
LANGKAH 2 pipeline baru Pool 2: latih & uji klasifikasi sub-kategori (label CoA).

Input : data/data_riil_berlabel_coa.csv   (hasil siapkan_data_coa.py)
        data/dataset_sintesis_v1.csv      (opsional; hanya dipakai sebagai tambahan data LATIH)
Output: models/model_coa_final.pkl, data/hasil_eksperimen_coa.csv, data/hasil_cv_per_label.csv

Tiga eksperimen:
  A. 5-fold cross-validation pada seluruh data riil (BCA + Mandiri), dibandingkan dengan BASELINE
     "tebak label terbanyak berdasarkan arah CR/DB saja" -> seberapa besar kontribusi NLP?
  B. Uji lintas-bank: latih di satu bank, uji di bank lain (generalisasi ke format & kosakata baru),
     dengan dan tanpa data sintesis.
  C. Model final (SVM linear terkalibrasi -> ada skor confidence untuk threshold).

Cara jalan (dari folder src, venv aktif):
    python latih_model_coa.py
"""
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from kamus_istilah import normalisasi_teks
from kategori_keuangan import LABEL_BELUM_PASTI, LABEL_COA, MAP_SINTESIS_KE_BARU

warnings.filterwarnings("ignore", category=UserWarning)

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
MODELS = BASE / "models"
MODELS.mkdir(exist_ok=True)

MIN_PER_LABEL = 5       # label dengan data < 5 baris tidak dilatih (terlalu sedikit untuk dievaluasi)
RANDOM_STATE = 42
N_FOLD = 5


# ---------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------
def tambah_teks_model(df):
    """teks model = token arah (CR/DB) + teks keterangan yang sudah dinormalisasi."""
    df = df.copy()
    df["teks_model"] = "arah" + df["jenis"].str.lower() + " " + df["keterangan"].apply(normalisasi_teks)
    return df


def muat_riil():
    df = pd.read_csv(DATA / "data_riil_berlabel_coa.csv")
    n_awal = len(df)
    df = df[df["label"] != LABEL_BELUM_PASTI].copy()
    semua = tambah_teks_model(df).reset_index(drop=True)       # semua baris berlabel (utk model final)
    hitung = df["label"].value_counts()
    dibuang = hitung[hitung < MIN_PER_LABEL]
    df = df[~df["label"].isin(dibuang.index)].copy()
    print(f"Data riil: {n_awal} baris -> dipakai evaluasi {len(df)} baris "
          f"(dikeluarkan: {n_awal - len(df)} baris PERLU_REVIEW / label < {MIN_PER_LABEL} contoh)")
    if len(dibuang):
        print("   Label terlalu sedikit utk dievaluasi:", ", ".join(f"{k}({v})" for k, v in dibuang.items()))
    return tambah_teks_model(df).reset_index(drop=True), semua


def muat_sintesis():
    f = DATA / "dataset_sintesis_v1.csv"
    if not f.exists():
        print("   (dataset_sintesis_v1.csv tidak ditemukan -> eksperimen dengan sintesis dilewati)")
        return None
    s = pd.read_csv(f)
    s["label"] = s["kategori"].map(MAP_SINTESIS_KE_BARU)
    s["jenis"] = s["jenis"].map({"cash_in": "CR", "cash_out": "DB"})
    s["bank"] = "sintesis"
    s = s.dropna(subset=["label", "jenis"])
    return tambah_teks_model(s[["keterangan", "jenis", "label", "bank"]]).reset_index(drop=True)


# ---------------------------------------------------------------------
# MODEL
# ---------------------------------------------------------------------
def buat_fitur(mode):
    kata = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    if mode == "kata":
        return kata
    # kata + potongan huruf: tahan terhadap singkatan/typo ("bpjstkfeb", "PJSTK", "lmbr")
    huruf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=2)
    return FeatureUnion([("kata", kata), ("huruf", huruf)])


def buat_model(mode, kalibrasi=False):
    svm = LinearSVC(C=1.0, class_weight="balanced", max_iter=5000, random_state=RANDOM_STATE)
    if kalibrasi:
        svm = CalibratedClassifierCV(svm, cv=3)
    return Pipeline([("fitur", buat_fitur(mode)), ("svm", svm)])


def skor(y_true, y_pred):
    """Macro-F1 dihitung hanya pada label yang benar-benar ada di data uji."""
    labels = sorted(set(y_true))
    return (accuracy_score(y_true, y_pred),
            f1_score(y_true, y_pred, average="macro", labels=labels, zero_division=0))


def baseline_arah(train, test):
    """Baseline: untuk tiap arah (CR/DB) tebak label yang paling sering di data latih."""
    mayoritas = train.groupby("jenis")["label"].agg(lambda x: x.value_counts().index[0])
    global_maj = train["label"].value_counts().index[0]
    return test["jenis"].map(mayoritas).fillna(global_maj).values


# ---------------------------------------------------------------------
# EKSPERIMEN
# ---------------------------------------------------------------------
def eksperimen_a(df, hasil):
    print("\n" + "=" * 72)
    print("A. 5-FOLD CROSS-VALIDATION (BCA + Mandiri digabung)")
    print("=" * 72)
    cv = StratifiedKFold(n_splits=N_FOLD, shuffle=True, random_state=RANDOM_STATE)

    base_pred = pd.Series(index=df.index, dtype=object)
    for tr, te in cv.split(df, df["label"]):
        base_pred.iloc[te] = baseline_arah(df.iloc[tr], df.iloc[te])
    a, f = skor(df["label"], base_pred)
    print(f"{'Baseline (arah CR/DB saja)':<34} acc={a:.3f}  macroF1={f:.3f}")
    hasil.append({"eksperimen": "A-CV", "metode": "baseline arah", "akurasi": a, "macro_f1": f})

    terbaik, pred_terbaik = None, None
    for mode in ["kata", "kata+huruf"]:
        model = buat_model(mode)
        pred = cross_val_predict(model, df["teks_model"], df["label"], cv=cv)
        a, f = skor(df["label"], pred)
        print(f"{'TF-IDF ' + mode + ' + SVM':<34} acc={a:.3f}  macroF1={f:.3f}")
        hasil.append({"eksperimen": "A-CV", "metode": f"TF-IDF {mode} + SVM", "akurasi": a, "macro_f1": f})
        if terbaik is None or f > terbaik[1]:
            terbaik, pred_terbaik = (mode, f), pred

    mode, _ = terbaik
    print(f"\nMode terbaik: {mode}")
    y = df["label"]
    print("\nPer bank (mode terbaik):")
    for bank, idx in df.groupby("bank").groups.items():
        a, f = skor(y.loc[idx], pred_terbaik[df.index.get_indexer(idx)])
        print(f"   {bank:<10} n={len(idx):<4} acc={a:.3f}  macroF1={f:.3f}")

    yakin = df["yakin"].values
    a, f = skor(y[yakin], pred_terbaik[yakin])
    print(f"\nHanya baris 'yakin' (aturan eksplisit)  n={int(yakin.sum())}: acc={a:.3f}  macroF1={f:.3f}")
    hasil.append({"eksperimen": "A-CV", "metode": "mode terbaik, baris yakin saja", "akurasi": a, "macro_f1": f})

    print("\nLaporan per label (mode terbaik):")
    laporan = classification_report(y, pred_terbaik, zero_division=0, output_dict=True)
    tabel = pd.DataFrame(laporan).T.loc[sorted(set(y))][["precision", "recall", "f1-score", "support"]]
    print(tabel.round(2).to_string())
    tabel.to_csv(DATA / "hasil_cv_per_label.csv")
    return mode


def eksperimen_b(df, sint, mode, hasil):
    print("\n" + "=" * 72)
    print("B. UJI LINTAS-BANK (latih di satu bank, uji di bank lain)")
    print("=" * 72)
    varian = [("tanpa sintesis", None)]
    if sint is not None:
        varian.append(("dengan sintesis", sint))
    for nama_v, tambahan in varian:
        for bank_latih, bank_uji in [("bca", "mandiri"), ("mandiri", "bca")]:
            train = df[df["bank"] == bank_latih]
            test = df[df["bank"] == bank_uji]
            if tambahan is not None:
                train = pd.concat([train, tambahan], ignore_index=True)
            bisa = test["label"].isin(set(train["label"]))
            test_ok = test[bisa]
            model = buat_model(mode).fit(train["teks_model"], train["label"])
            a, f = skor(test_ok["label"], model.predict(test_ok["teks_model"]))
            ab, fb = skor(test_ok["label"], baseline_arah(train, test_ok))
            print(f"{bank_latih:>8} -> {bank_uji:<8} [{nama_v:<15}] "
                  f"uji {len(test_ok)}/{len(test)} baris (labelnya dikenal model) | "
                  f"model: acc={a:.3f} F1={f:.3f} | baseline arah: acc={ab:.3f} F1={fb:.3f}")
            hasil.append({"eksperimen": "B-lintas-bank", "metode": f"{bank_latih}->{bank_uji} ({nama_v})",
                          "akurasi": a, "macro_f1": f})


def model_final(semua, sint, mode):
    print("\n" + "=" * 72)
    print("C. MODEL FINAL (data riil + sintesis HANYA untuk label langka, SVM terkalibrasi)")
    print("=" * 72)
    hitung = semua["label"].value_counts()
    langka = set(hitung[hitung < MIN_PER_LABEL].index)
    latih = semua
    if sint is not None and langka:
        tambahan = sint[sint["label"].isin(langka)]
        latih = pd.concat([semua, tambahan], ignore_index=True)
        print(f"Sintesis ditambahkan untuk label langka: "
              + ", ".join(f"{k}(+{(tambahan['label'] == k).sum()})" for k in sorted(langka) if (tambahan['label'] == k).any()))
    total = latih["label"].value_counts()
    tak_cukup = total[total < 3]            # kalibrasi probabilitas butuh >= 3 contoh per label
    if len(tak_cukup):
        print("Label TIDAK bisa dilatih (data < 3 baris, butuh sampel dari Avolut):",
              ", ".join(f"{k}({v})" for k, v in tak_cukup.items()))
    latih = latih[~latih["label"].isin(tak_cukup.index)]

    model = buat_model(mode, kalibrasi=True).fit(latih["teks_model"], latih["label"])
    joblib.dump({"model": model, "mode": mode, "labels": list(model.classes_)}, MODELS / "model_coa_final.pkl")
    print(f"Tersimpan: models/model_coa_final.pkl  ({len(model.classes_)} label)")

    contoh = [
        ("BPJS KS Jakarta Feb25", "DB"), ("payroll Bali 5Feb", "DB"), ("lembur toyib", "DB"),
        ("TRSF E-BANKING PANCA BERSAUDARA", "CR"), ("TRSF E-BANKING BAREKA LINTAS INDO", "DB"),
        ("BYR VIA E-BANKING PLN JATIM", "DB"), ("BIAYA ADM", "DB"), ("bbm megadc", "DB"),
        ("pulsa kantor jan", "DB"), ("beli kopi untuk tamu", "DB"),
    ]
    X = pd.Series([f"arah{j.lower()} " + normalisasi_teks(t) for t, j in contoh])
    proba = model.predict_proba(X)
    print("\nContoh prediksi (label | confidence):")
    for (teks, jenis), p in zip(contoh, proba):
        i = p.argmax()
        print(f"   [{jenis}] {teks:<36} -> {model.classes_[i]:<20} {p[i]:.2f}   ({LABEL_COA[model.classes_[i]]['nama']})")


def main():
    riil, riil_semua = muat_riil()
    sint = muat_sintesis()
    hasil = []
    mode = eksperimen_a(riil, hasil)
    eksperimen_b(riil, sint, mode, hasil)
    model_final(riil_semua, sint, mode)
    pd.DataFrame(hasil).to_csv(DATA / "hasil_eksperimen_coa.csv", index=False)
    print("\nRingkasan eksperimen tersimpan: data/hasil_eksperimen_coa.csv")
    print("CATATAN: label = 'label perak' (aturan otomatis), belum divalidasi staf keuangan.")


if __name__ == "__main__":
    main()