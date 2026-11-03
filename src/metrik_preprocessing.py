"""
metrik_preprocessing.py
=======================
Pengukuran performa preprocessing & ekstraksi fitur (proposal Bab 3.2.4 dan 3.2.5) pada data CoA.

Metrik: Token Reduction Rate, Abbreviation Coverage Rate, Vocabulary Size, Average Token Length,
        Sparsity TF-IDF, jumlah fitur, Top-N token per label.
Output: data/hasil_metrik_preprocessing.csv, data/hasil_top_token_per_label.csv

Jalankan (dari folder src):  python metrik_preprocessing.py
"""
import re

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from kamus_istilah import KAMUS_RIIL, STOPWORDS_RIIL, normalisasi_teks
from latih_model_coa import DATA, LABEL_BELUM_PASTI

TOP_N = 5


def token_mentah(teks):
    t = re.sub(r"\d+", " ", str(teks).lower())
    return [x for x in re.sub(r"[^a-z\s]", " ", t).split() if len(x) > 1]


def main():
    df = pd.read_csv(DATA / "data_riil_berlabel_coa.csv")
    df = df[df["label"] != LABEL_BELUM_PASTI].reset_index(drop=True)

    mentah = df["keterangan"].apply(token_mentah)
    n_before = mentah.apply(len).sum()
    n_stop = sum(1 for toks in mentah for t in toks if t in STOPWORDS_RIIL)
    n_abbrev = sum(1 for toks in mentah for t in toks if t in KAMUS_RIIL)   # token singkatan yang dikenal kamus
    bersih = df["keterangan"].apply(normalisasi_teks)
    token_akhir = bersih.str.split()
    n_after = token_akhir.apply(len).sum()
    kosong = int((token_akhir.apply(len) == 0).sum())

    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    X = vec.fit_transform(bersih.replace("", "kosong"))
    sparsity = 1 - X.nnz / (X.shape[0] * X.shape[1])

    metrik = {
        "jumlah_transaksi": len(df),
        "token_sebelum": int(n_before),
        "token_sesudah": int(n_after),
        "token_reduction_rate_%": round((n_before - n_after) / n_before * 100, 2),
        "stopword_dibuang": int(n_stop),
        "token_singkatan_terpetakan_kamus": int(n_abbrev),
        "vocabulary_size": len({t for toks in token_akhir for t in toks}),
        "average_token_length": round(token_akhir.apply(len).mean(), 2),
        "transaksi_teks_kosong_setelah_preprocessing": kosong,
        "jumlah_fitur_tfidf": X.shape[1],
        "sparsity_tfidf_%": round(sparsity * 100, 2),
    }
    for k, v in metrik.items():
        print(f"{k:<46}: {v}")
    pd.Series(metrik).to_csv(DATA / "hasil_metrik_preprocessing.csv", header=["nilai"])

    # Top-N token per label (rata-rata bobot TF-IDF unigram)
    uni = TfidfVectorizer(sublinear_tf=True)
    U = uni.fit_transform(bersih.replace("", "kosong"))
    kosa = np.array(uni.get_feature_names_out())
    baris = []
    print("\nTop token per label:")
    for lab in sorted(df["label"].unique()):
        m = (df["label"] == lab).values
        rata = np.asarray(U[m].mean(axis=0)).ravel()
        top = list(kosa[rata.argsort()[::-1][:TOP_N]])
        baris.append({"label": lab, "n": int(m.sum()), "top_token": ", ".join(top)})
        print(f"   {lab:<20} ({int(m.sum()):>3}) {', '.join(top)}")
    pd.DataFrame(baris).to_csv(DATA / "hasil_top_token_per_label.csv", index=False)

    print("\nCATATAN: 'abbreviation coverage' di proposal = token singkatan terpetakan / seluruh token singkatan.")
    print("Penyebut (jumlah seluruh singkatan) butuh daftar singkatan acuan dari domain expert; di sini hanya")
    print("dilaporkan jumlah token yang berhasil dipetakan kamus.")


if __name__ == "__main__":
    main()

