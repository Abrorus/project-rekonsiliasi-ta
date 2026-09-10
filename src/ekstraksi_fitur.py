import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
import joblib

def main():
    df = pd.read_csv('../data/dataset_preprocessed_v2.csv')

    X_text = df['teks_final']
    y = df['kategori']

    # Split data: 80% training, 20% testing
    X_train_text, X_test_text, y_train, y_test = train_test_split(
        X_text, y, test_size=0.2, random_state=42, stratify=y
    )

    # Vektorisasi TF-IDF -- belajar kosakata cuma dari data training
    vectorizer = TfidfVectorizer()
    X_train = vectorizer.fit_transform(X_train_text)
    X_test = vectorizer.transform(X_test_text)

    # Cek sparsity (persentase angka nol di matriks)
    sparsity = 100 * (1.0 - X_train.nnz / (X_train.shape[0] * X_train.shape[1]))

    print(f"Jumlah data training: {X_train.shape[0]}")
    print(f"Jumlah data testing : {X_test.shape[0]}")
    print(f"Jumlah kata unik (fitur): {X_train.shape[1]}")
    print(f"Sparsity matriks: {sparsity:.2f}%")

    # Simpen semuanya biar bisa dipakai lagi di tahap training model
    joblib.dump(vectorizer, '../models/tfidf_vectorizer.pkl')
    joblib.dump(X_train, '../models/X_train.pkl')
    joblib.dump(X_test, '../models/X_test.pkl')
    joblib.dump(y_train, '../models/y_train.pkl')
    joblib.dump(y_test, '../models/y_test.pkl')

    print("\nSemua file tersimpan di folder models/")

if __name__ == '__main__':
    main()