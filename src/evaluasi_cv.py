import pandas as pd
import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sentence_transformers import SentenceTransformer
from scipy import stats

def main():
    df = pd.read_csv('../data/dataset_preprocessed_v2.csv')
    X_text = df['teks_final']
    y = df['kategori']

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    hasil = {}

    # --- Model berbasis TF-IDF ---
    vectorizer = TfidfVectorizer()
    X_tfidf = vectorizer.fit_transform(X_text)

    model_tfidf = {
        'SVM (RBF)': SVC(kernel='rbf', C=1.0, gamma='scale', random_state=42),
        'SVM (Linear)': SVC(kernel='linear', C=1.0, random_state=42),
        'Random Forest': RandomForestClassifier(n_estimators=100, max_depth=15, min_samples_split=5, random_state=42),
    }
    for nama, model in model_tfidf.items():
        scores = cross_val_score(model, X_tfidf, y, cv=cv, scoring='f1_macro')
        hasil[nama] = scores
        print(f"{nama:<15} Macro F1 per fold: {np.round(scores, 3)}  Mean: {scores.mean():.4f}  Std: {scores.std():.4f}")

    # --- Model berbasis embedding (SBERT) ---
    print("\nMenghitung embedding SBERT untuk seluruh data...")
    sbert = SentenceTransformer('all-MiniLM-L6-v2')
    X_sbert = sbert.encode(X_text.tolist())
    scores = cross_val_score(LogisticRegression(max_iter=1000), X_sbert, y, cv=cv, scoring='f1_macro')
    hasil['SBERT'] = scores
    print(f"{'SBERT':<15} Macro F1 per fold: {np.round(scores, 3)}  Mean: {scores.mean():.4f}  Std: {scores.std():.4f}")

    # --- Ringkasan akhir ---
    print("\n=== Ringkasan 5-Fold Cross Validation ===")
    ringkasan = pd.DataFrame({nama: skor for nama, skor in hasil.items()})
    ringkasan.index = [f'Fold {i+1}' for i in range(5)]
    print(ringkasan.round(4))
    print("\nRata-rata & Std per model:")
    print(ringkasan.agg(['mean', 'std']).round(4))

    # --- Uji signifikansi: bandingin model terbaik vs runner-up ---
    urutan = ringkasan.mean().sort_values(ascending=False)
    model_1, model_2 = urutan.index[0], urutan.index[1]
    t_stat, p_value = stats.ttest_rel(ringkasan[model_1], ringkasan[model_2])
    print(f"\n=== Paired t-test: {model_1} vs {model_2} ===")
    print(f"t-statistic: {t_stat:.4f}  p-value: {p_value:.4f}")
    if p_value < 0.05:
        print(f"Signifikan (p < 0.05): {model_1} secara statistik lebih baik dari {model_2}")
    else:
        print(f"Tidak signifikan (p >= 0.05): perbedaan {model_1} dan {model_2} bisa jadi kebetulan")

    ringkasan.to_csv('../data/hasil_cv_5fold.csv')
    print("\nHasil tersimpan di data/hasil_cv_5fold.csv")

if __name__ == '__main__':
    main()