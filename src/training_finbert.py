import joblib
import torch
import pandas as pd
import numpy as np
from transformers import AutoTokenizer, AutoModel
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report

def get_embeddings(texts, tokenizer, model, batch_size=16):
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        inputs = tokenizer(batch, padding=True, truncation=True, max_length=64, return_tensors='pt')
        with torch.no_grad():
            outputs = model(**inputs)
        # Ambil embedding dari token [CLS] sebagai representasi tiap kalimat
        cls_embeddings = outputs.last_hidden_state[:, 0, :].numpy()
        embeddings.append(cls_embeddings)
    return np.vstack(embeddings)

def main():
    df = pd.read_csv('../data/dataset_preprocessed_v2.csv')

    X_train_text, X_test_text, y_train, y_test = train_test_split(
        df['teks_final'], df['kategori'], test_size=0.2, random_state=42, stratify=df['kategori']
    )

    print("Loading model FinBERT (ProsusAI/finbert)... ini bakal download model pertama kali dipakai")
    tokenizer = AutoTokenizer.from_pretrained('ProsusAI/finbert')
    model = AutoModel.from_pretrained('ProsusAI/finbert')
    model.eval()

    print("Mengubah teks jadi embedding...")
    X_train_emb = get_embeddings(X_train_text.tolist(), tokenizer, model)
    X_test_emb = get_embeddings(X_test_text.tolist(), tokenizer, model)

    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_train_emb, y_train)
    y_pred = clf.predict(X_test_emb)

    acc = accuracy_score(y_test, y_pred)
    f1_macro = f1_score(y_test, y_pred, average='macro')

    print(f"\n=== FinBERT + Logistic Regression ===")
    print(f"Accuracy: {acc:.4f}  Macro F1: {f1_macro:.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    joblib.dump(clf, '../models/model_finbert.pkl')
    print("Model tersimpan di models/model_finbert.pkl")

if __name__ == '__main__':
    main()