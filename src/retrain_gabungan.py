import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, f1_score, classification_report
from kategori_keuangan import KATEGORI
from preprocessing import normalize_text, tokenize
from preprocessing_lanjutan import remove_stopwords, lemmatize

def preprocess_pipeline(text):
    tokens = tokenize(normalize_text(text))
    tokens = lemmatize(remove_stopwords(tokens))
    return ' '.join(tokens)

def main():
    # data sintesis (sudah preprocessed)
    df_sintesis = pd.read_csv('../data/dataset_preprocessed_v2.csv')[['teks_final', 'kategori']]

    # data riil, hanya yang kategorinya overlap dengan 9 kategori awal
    df_riil = pd.read_csv('../data/bca_riil_partial_label.csv')
    df_riil['nama_kategori_asli'] = df_riil['kode_akun_final'].map(lambda k: KATEGORI[k]['nama'])
    kategori_sintesis = set(df_sintesis['kategori'])
    df_riil = df_riil[df_riil['nama_kategori_asli'].isin(kategori_sintesis)].copy()
    df_riil['teks_final'] = df_riil['keterangan'].apply(preprocess_pipeline)
    df_riil = df_riil.rename(columns={'nama_kategori_asli': 'kategori'})[['teks_final', 'kategori']]

    # pisah data riil: kategori dengan sampel cukup (>=5) di-split train/test,
    # kategori langka (<5 sampel) semua masuk training saja (belum cukup buat dites)
    counts = df_riil['kategori'].value_counts()
    kategori_cukup = counts[counts >= 5].index
    df_riil_cukup = df_riil[df_riil['kategori'].isin(kategori_cukup)]
    df_riil_langka = df_riil[~df_riil['kategori'].isin(kategori_cukup)]

    riil_train, riil_test = train_test_split(
        df_riil_cukup, test_size=0.3, random_state=42, stratify=df_riil_cukup['kategori']
    )

    print(f"Data riil kategori langka (<5 sampel, semua masuk training): {len(df_riil_langka)} baris")
    print(f"Data riil kategori cukup -> train: {len(riil_train)}, test: {len(riil_test)}")

    df_train = pd.concat([df_sintesis, riil_train, df_riil_langka], ignore_index=True)
    df_test = riil_test

    print(f"\nTotal data training (sintesis + riil): {len(df_train)} baris")
    print(f"Total data testing (riil murni, belum pernah dilihat model): {len(df_test)} baris")

    vectorizer = TfidfVectorizer()
    X_train = vectorizer.fit_transform(df_train['teks_final'])
    X_test = vectorizer.transform(df_test['teks_final'])

    model = SVC(kernel='linear', C=1.0, probability=True, random_state=42)
    model.fit(X_train, df_train['kategori'])
    y_pred = model.predict(X_test)

    acc = accuracy_score(df_test['kategori'], y_pred)
    f1_macro = f1_score(df_test['kategori'], y_pred, average='macro', zero_division=0)

    print(f"\n=== Evaluasi Model Baru (dilatih sintesis + riil) pada Data Riil Test ===")
    print(f"Accuracy   : {acc:.4f}")
    print(f"Macro F1   : {f1_macro:.4f}")
    print(classification_report(df_test['kategori'], y_pred, zero_division=0))

    joblib.dump(model, '../models/model_gabungan_svm_linear.pkl')
    joblib.dump(vectorizer, '../models/vectorizer_gabungan.pkl')
    print("\nModel & vectorizer baru tersimpan sebagai '_gabungan'")

if __name__ == '__main__':
    main()