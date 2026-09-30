import pandas as pd
import joblib
from sklearn.metrics import accuracy_score, f1_score, classification_report
from kategori_keuangan import KATEGORI
from preprocessing import normalize_text, tokenize
from preprocessing_lanjutan import remove_stopwords, lemmatize

def preprocess_pipeline(text):
    norm = normalize_text(text)
    tokens = tokenize(norm)
    tokens = remove_stopwords(tokens)
    tokens = lemmatize(tokens)
    return ' '.join(tokens)

def main():
    df = pd.read_csv('../data/bca_riil_partial_label.csv')
    model = joblib.load('../models/model_final_svm_linear.pkl')
    vectorizer = joblib.load('../models/vectorizer_final.pkl')

    kategori_sintesis = set(model.classes_)
    df['nama_kategori_asli'] = df['kode_akun_final'].map(lambda k: KATEGORI[k]['nama'])

    df_overlap = df[df['nama_kategori_asli'].isin(kategori_sintesis)].copy()
    df_baru = df[~df['nama_kategori_asli'].isin(kategori_sintesis)].copy()

    print(f"Data dengan kategori yang dikenal model: {len(df_overlap)} baris")
    print(f"Data dengan kategori baru (di luar cakupan model): {len(df_baru)} baris")
    print(f"\nRincian kategori baru:")
    print(df_baru['nama_kategori_asli'].value_counts().to_string())

    # Preprocessing teks riil pakai pipeline yang sama persis dengan data sintesis
    df_overlap['teks_final'] = df_overlap['keterangan'].apply(preprocess_pipeline)
    X_riil = vectorizer.transform(df_overlap['teks_final'])
    y_true = df_overlap['nama_kategori_asli']
    y_pred = model.predict(X_riil)

    acc = accuracy_score(y_true, y_pred)
    f1_macro = f1_score(y_true, y_pred, average='macro', zero_division=0)

    print(f"\n=== Evaluasi Model (dilatih data sintesis) pada Data Riil ===")
    print(f"Accuracy   : {acc:.4f}")
    print(f"Macro F1   : {f1_macro:.4f}")
    print(classification_report(y_true, y_pred, zero_division=0))

    df_overlap['prediksi'] = y_pred
    df_overlap.to_csv('../data/hasil_evaluasi_data_riil.csv', index=False)
    print("\nTersimpan: data/hasil_evaluasi_data_riil.csv")

if __name__ == '__main__':
    main()