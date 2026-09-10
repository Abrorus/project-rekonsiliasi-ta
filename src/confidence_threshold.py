import numpy as np
import pandas as pd
import joblib
from sklearn.svm import SVC
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score

def main():
    df = pd.read_csv('../data/dataset_preprocessed_v2.csv')
    X_text = df['teks_final']
    y = df['kategori']

    X_train_text, X_test_text, y_train, y_test = train_test_split(
        X_text, y, test_size=0.2, random_state=42, stratify=y
    )

    vectorizer = TfidfVectorizer()
    X_train = vectorizer.fit_transform(X_train_text)
    X_test = vectorizer.transform(X_test_text)

    # probability=True biar bisa keluarin confidence score, bukan cuma label
    model = SVC(kernel='linear', C=1.0, probability=True, random_state=42)
    model.fit(X_train, y_train)

    probs = model.predict_proba(X_test)
    preds = model.predict(X_test)
    confidence = probs.max(axis=1)  # confidence tertinggi per prediksi

    # Grid search threshold dari 0.50 sampai 0.99
    hasil_threshold = []
    for t in np.arange(0.50, 1.00, 0.01):
        mask = confidence >= t
        if mask.sum() == 0:
            continue
        f1_di_atas_threshold = f1_score(y_test[mask], preds[mask], average='macro', zero_division=0)
        coverage = mask.sum() / len(y_test)  # persen transaksi yang "lolos" otomatis
        hasil_threshold.append({
            'threshold': round(t, 2),
            'f1_macro': f1_di_atas_threshold,
            'coverage': coverage,
            'jumlah_data': mask.sum(),
        })

    df_threshold = pd.DataFrame(hasil_threshold)
    print(df_threshold.to_string(index=False))

    # Pilih threshold terbaik: F1 tertinggi dengan coverage minimal 70%
    # (coverage minimal ditetapkan biar sistem tetap praktis dipakai,
    # bukan cuma ngejar F1 tinggi di sisa data yang sedikit banget)
    kandidat = df_threshold[df_threshold['coverage'] >= 0.7]
    threshold_optimal = kandidat.loc[kandidat['f1_macro'].idxmax()]

    print(f"\n=== Threshold Optimal ===")
    print(f"Threshold (τ*): {threshold_optimal['threshold']}")
    print(f"Macro F1 di atas threshold: {threshold_optimal['f1_macro']:.4f}")
    print(f"Coverage (otomatis diproses): {threshold_optimal['coverage']*100:.1f}%")
    print(f"Sisanya ({(1-threshold_optimal['coverage'])*100:.1f}%) dirujuk ke Pool 3 untuk validasi manual")

    joblib.dump(model, '../models/model_final_svm_linear.pkl')
    joblib.dump(vectorizer, '../models/vectorizer_final.pkl')
    df_threshold.to_csv('../data/hasil_threshold_grid_search.csv', index=False)
    print("\nModel final dan hasil grid search tersimpan")

if __name__ == '__main__':
    main()