import joblib
from knowledge_base.decision_tree_kb import klasifikasi_kb

def load_model():
    model = joblib.load('../models/model_final_svm_linear.pkl')
    vectorizer = joblib.load('../models/vectorizer_final.pkl')
    return model, vectorizer

def klasifikasi_transaksi(teks, model, vectorizer, threshold=0.66):
    """
    Klasifikasi satu transaksi. Kalau confidence >= threshold,
    diproses otomatis. Kalau di bawah, dirujuk ke Pool 3 (manual/KB).
    """
    X = vectorizer.transform([teks])
    proba = model.predict_proba(X)[0]

    kategori_prediksi = model.classes_[proba.argmax()]
    confidence = proba.max()

    if confidence >= threshold:
        status = "OTOMATIS"
        metode = "Model ML"
        return {
            "teks_input": teks,
            "kategori_prediksi": kategori_prediksi,
            "confidence": round(float(confidence), 4),
            "status": status,
            "metode": metode
        }
    else:
        # Masuk ke Pool 3 (Knowledge Base)
        kb_result = klasifikasi_kb(teks)
        kb_result["confidence"] = round(float(confidence), 4) # Tetap retain confidence awal sebagai info
        return kb_result

def main():
    model, vectorizer = load_model()

    # Contoh simulasi beberapa transaksi (nanti diganti input asli/dari Pool 1)
    contoh_transaksi = [
        "transfer gaji karyawan",
        "bayar tagihan listrik berkah",
        "pembayaran global teknindo periode",
        "po sejahtera ref",
    ]

    print("=== Simulasi Routing Transaksi ===\n")
    for teks in contoh_transaksi:
        hasil = klasifikasi_transaksi(teks, model, vectorizer)
        print(f"Input       : {hasil['teks_input']}")
        print(f"Kategori    : {hasil['kategori_prediksi']}")
        print(f"Confidence  : {hasil['confidence']}")
        print(f"Status      : {hasil['status']}")
        print(f"Metode      : {hasil.get('metode', 'Tidak diketahui')}\n")

if __name__ == '__main__':
    main()