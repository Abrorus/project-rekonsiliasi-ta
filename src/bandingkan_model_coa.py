"""
bandingkan_model_coa.py
=======================
LANGKAH 3 pipeline Pool 2: perbandingan model pada label CoA (sesuai proposal Bab 3.2.6 & 3.2.8).

Model   : SVM (TF-IDF), Random Forest (TF-IDF), SBERT + LogReg, FinBERT + LogReg
Evaluasi: 5-fold stratified CV, Macro-F1 (mean +- std), paired t-test antar model.
Output  : data/hasil_banding_model_coa.csv, data/hasil_ttest_model_coa.csv

Jalankan (dari folder src, venv aktif):  python bandingkan_model_coa.py
"""
import warnings
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline

from latih_model_coa import DATA, N_FOLD, RANDOM_STATE, buat_model, muat_riil

warnings.filterwarnings("ignore")


def embed_sbert(teks):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2").encode(teks, show_progress_bar=False)


def embed_finbert(teks, batch=16):
    import torch
    from transformers import AutoModel, AutoTokenizer
    tok, mdl = AutoTokenizer.from_pretrained("ProsusAI/finbert"), AutoModel.from_pretrained("ProsusAI/finbert")
    mdl.eval()
    out = []
    for i in range(0, len(teks), batch):
        x = tok(teks[i:i + batch], padding=True, truncation=True, max_length=64, return_tensors="pt")
        with torch.no_grad():
            out.append(mdl(**x).last_hidden_state[:, 0, :].numpy())
    return np.vstack(out)


def main():
    df, _ = muat_riil()
    X, y = df["teks_model"], df["label"]
    cv = StratifiedKFold(n_splits=N_FOLD, shuffle=True, random_state=RANDOM_STATE)
    folds = list(cv.split(X, y))

    kandidat = {
        "SVM (TF-IDF)": ("teks", buat_model("kata+huruf")),
        "Random Forest (TF-IDF)": ("teks", Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
            ("rf", RandomForestClassifier(n_estimators=100, max_depth=15, min_samples_split=5,
                                          class_weight="balanced", random_state=RANDOM_STATE))])),
    }
    emb = {}
    for nama, fn in [("SBERT + LogReg", embed_sbert), ("FinBERT + LogReg", embed_finbert)]:
        try:
            emb[nama] = fn(X.tolist())
            kandidat[nama] = ("emb", LogisticRegression(max_iter=2000, class_weight="balanced"))
        except Exception as e:  # model belum terunduh / tidak ada internet
            print(f"[LEWATI] {nama}: {type(e).__name__}: {str(e)[:120]}")

    rows, f1_fold = [], {}
    for nama, (jenis, model) in kandidat.items():
        data = X if jenis == "teks" else emb[nama]
        acc, pre, rec, f1 = [], [], [], []
        for tr, te in folds:
            Xtr = data.iloc[tr] if jenis == "teks" else data[tr]
            Xte = data.iloc[te] if jenis == "teks" else data[te]
            model.fit(Xtr, y.iloc[tr])
            p = model.predict(Xte)
            yt = y.iloc[te]
            lab = sorted(set(yt))
            acc.append(accuracy_score(yt, p))
            pre.append(precision_score(yt, p, average="macro", labels=lab, zero_division=0))
            rec.append(recall_score(yt, p, average="macro", labels=lab, zero_division=0))
            f1.append(f1_score(yt, p, average="macro", labels=lab, zero_division=0))
        f1_fold[nama] = np.array(f1)
        rows.append({"model": nama, "accuracy": np.mean(acc), "precision_macro": np.mean(pre),
                     "recall_macro": np.mean(rec), "f1_macro": np.mean(f1), "f1_std": np.std(f1)})
        print(f"{nama:<24} acc={np.mean(acc):.3f} P={np.mean(pre):.3f} R={np.mean(rec):.3f} "
              f"F1={np.mean(f1):.3f} +- {np.std(f1):.3f}")

    hasil = pd.DataFrame(rows).sort_values("f1_macro", ascending=False)
    hasil.to_csv(DATA / "hasil_banding_model_coa.csv", index=False)

    print("\nPaired t-test F1 per fold (alpha=0.05):")
    tt = []
    for a, b in combinations(f1_fold, 2):
        t, p = stats.ttest_rel(f1_fold[a], f1_fold[b])
        tt.append({"model_a": a, "model_b": b, "t": t, "p_value": p, "signifikan": p < 0.05})
        print(f"   {a} vs {b}: t={t:.3f} p={p:.4f} {'SIGNIFIKAN' if p < 0.05 else 'tidak signifikan'}")
    pd.DataFrame(tt).to_csv(DATA / "hasil_ttest_model_coa.csv", index=False)
    print("\nTersimpan: data/hasil_banding_model_coa.csv, data/hasil_ttest_model_coa.csv")
    print("CATATAN: label masih 'label perak' (belum divalidasi staf keuangan).")


if __name__ == "__main__":
    main()

