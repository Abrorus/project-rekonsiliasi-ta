import joblib
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report

def main():
    df = pd.read_csv('../data/dataset_preprocessed_v2.csv')

    X_train_text, X_test_text, y_train, y_test = train_test_split(
        df['teks_final'], df['kategori'], test_size=0.2, random_state=42, stratify=df['kategori']
    )

    print("Loading model SBERT (all-MiniLM-L6-v2)... ini bakal download model pertama kali dipakai")
    sbert = SentenceTransformer('all-MiniLM-L6-v2')

    print("Mengubah teks jadi embedding...")
    X_train_emb = sbert.encode(X_train_text.tolist())
    X_test_emb = sbert.encode(X_test_text.tolist())

    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_train_emb, y_train)
    y_pred = clf.predict(X_test_emb)

    acc = accuracy_score(y_test, y_pred)
    f1_macro = f1_score(y_test, y_pred, average='macro')

    print(f"\n=== SBERT + Logistic Regression ===")
    print(f"Accuracy: {acc:.4f}  Macro F1: {f1_macro:.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    joblib.dump(clf, '../models/model_sbert.pkl')
    print("Model tersimpan di models/model_sbert.pkl")

if __name__ == '__main__':
    main()