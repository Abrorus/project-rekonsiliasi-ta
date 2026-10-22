import sys
from pathlib import Path
import joblib

# Pastikan direktori 'src' terdaftar di path sistem agar import modul selalu valid
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from knowledge_base.decision_tree_kb import klasifikasi_kb
    from preprocessing import normalize_text, tokenize
    from preprocessing_lanjutan import remove_stopwords, lemmatize
except ImportError:
    from src.knowledge_base.decision_tree_kb import klasifikasi_kb
    from src.preprocessing import normalize_text, tokenize
    from src.preprocessing_lanjutan import remove_stopwords, lemmatize

def preprocess_pipeline(text):
    """Pipeline pembersihan teks mutasi sebelum masuk ke model ML."""
    if not text:
        return ""
    tokens = tokenize(normalize_text(text))
    tokens = lemmatize(remove_stopwords(tokens))
    return ' '.join(tokens)

def load_model(use_gabungan=True):
    """
    Memuat model ML SVM dan Vectorizer.
    Secara default memuat model gabungan terbaru (sintesis + riil BCA).
    """
    model_dir = BASE_DIR / "models"
    
    if use_gabungan and (model_dir / "model_gabungan_svm_linear.pkl").exists():
        model_path = model_dir / "model_gabungan_svm_linear.pkl"
        vec_path = model_dir / "vectorizer_gabungan.pkl"
    else:
        model_path = model_dir / "model_final_svm_linear.pkl"
        vec_path = model_dir / "vectorizer_final.pkl"

    model = joblib.load(model_path)
    vectorizer = joblib.load(vec_path)
    return model, vectorizer

def klasifikasi_transaksi(input_data, model, vectorizer, threshold=0.66, jenis=None, mutasi=None):
    """
    Alur Routing Utama (Pool 1 -> Pool 3):
    1. Mencoba prediksi teks menggunakan model Machine Learning (NLP).
    2. Jika confidence score >= threshold (default 0.66), langsung diproses OTOMATIS (Pool 1).
    3. Jika confidence score < threshold (ambigu/ragu), dialihkan ke Knowledge Base (Pool 3).
    
    Parameter:
    - input_data: String keterangan teks transaksi ATAU dictionary/Series baris data tabel.
    - model: Objek model classifier scikit-learn.
    - vectorizer: Objek TfidfVectorizer.
    - threshold: Batas keyakinan model (default: 0.66).
    """
    if isinstance(input_data, dict) or hasattr(input_data, 'get'):
        teks = str(input_data.get('keterangan', ''))
        
        # Deteksi jenis mutasi: bisa dari field 'jenis' (BCA) atau field 'debit'/'kredit' (skema Modul Tabel)
        if not jenis:
            if input_data.get('jenis'):
                jenis = input_data.get('jenis')
            else:
                try:
                    deb = float(str(input_data.get('debit', 0) or 0).replace(',', ''))
                    kred = float(str(input_data.get('kredit', 0) or 0).replace(',', ''))
                    if deb > 0:
                        jenis = 'DB'
                    elif kred > 0:
                        jenis = 'CR'
                except (ValueError, TypeError):
                    pass

        if not mutasi:
            mutasi = input_data.get('mutasi') or input_data.get('debit') or input_data.get('kredit')
    else:
        teks = str(input_data)

    # 1. Preprocessing teks untuk model ML
    teks_clean = preprocess_pipeline(teks)
    X = vectorizer.transform([teks_clean])
    proba = model.predict_proba(X)[0]

    kategori_ml = model.classes_[proba.argmax()]
    confidence = float(proba.max())

    # 2. Evaluasi Threshold Routing
    if confidence >= threshold:
        # Masuk POOL 1: Otomatis diselesaikan oleh Machine Learning
        return {
            "teks_input": teks,
            "jenis": jenis,
            "mutasi": mutasi,
            "pool": "Pool 1 (Otomatis ML)",
            "kategori_prediksi": kategori_ml,
            "confidence": round(confidence, 4),
            "status": "OTOMATIS",
            "metode": "Machine Learning (SVM Linear)"
        }
    else:
        # Masuk POOL 3: Confidence rendah, dialihkan ke Knowledge Base (Mario)
        kb_result = klasifikasi_kb(input_data, jenis=jenis, mutasi=mutasi)
        kb_result["pool"] = "Pool 3 (Knowledge Base)"
        kb_result["confidence_ml_awal"] = round(confidence, 4)
        kb_result["prediksi_ml_awal"] = kategori_ml
        return kb_result

def main():
    print("=== SIMULASI INTEGRASI END-TO-END (NLP + KNOWLEDGE BASE) ===\n")
    model, vectorizer = load_model()

    # Contoh transaksi variatif dari data riil & sintesis
    contoh_transaksi = [
        # Kasus 1: Teks baku jelas -> Diproses langsung oleh ML (Pool 1)
        {"keterangan": "transfer gaji karyawan kantor pusat", "jenis": "DB", "mutasi": "25,000,000.00"},
        {"keterangan": "pembayaran bensin pertamina operasional sales", "jenis": "DB", "mutasi": "350,000.00"},
        
        # Kasus 2: Transaksi ambigu / institusi negara -> Dirujuk ke Modul KB (Pool 3)
        {"keterangan": "TRSF E-BANKING 89000/BPJS TK", "jenis": "DB", "mutasi": "16,561,371.00"},
        {"keterangan": "BYR VIA E-BANKING PENERIMAAN NEGARA", "jenis": "DB", "mutasi": "14,978,282.00"},
        {"keterangan": "BYR VIA E-BANKING 0860 PLN JATIM DARBE JAYA ABADI P", "jenis": "DB", "mutasi": "1,694,321.00"},
        
        # Kasus 3: Switching Bank (Uang Masuk vs Uang Keluar) -> Diselesaikan oleh KB
        {"keterangan": "SWITCHING TRANSFER DR 008 PANCA BERSAUDARA", "jenis": "CR", "mutasi": "50,000,000.00"},
        {"keterangan": "SWITCHING TRANSFER KE 009 SENTOT PRABOWO", "jenis": "DB", "mutasi": "15,000,000.00"},
        
        # Kasus 4: Nama Vendor & Customer Riil -> Diselesaikan oleh Resolver KB
        {"keterangan": "TRSF E-BANKING CIOMAS ADISATWA", "jenis": "DB", "mutasi": "580,075,045.00"},
        {"keterangan": "TRSF E-BANKING AMERTHA JAYA", "jenis": "CR", "mutasi": "595,075,045.00"},
        
        # Kasus 5: Transaksi anomali / data belum dikenal sama sekali -> Menuju Manual Review
        {"keterangan": "REF TXN 99823 ANOMALI TANPA KETERANGAN", "jenis": "DB", "mutasi": "100,000.00"}
    ]

    for item in contoh_transaksi:
        hasil = klasifikasi_transaksi(item, model, vectorizer, threshold=0.66)
        print(f"Transaksi   : {hasil['teks_input']} [{hasil.get('jenis', '-')}]")
        print(f"Jalur Pool  : {hasil['pool']}")
        print(f"Kategori    : {hasil['kategori_prediksi']}")
        print(f"Status      : {hasil['status']} (via {hasil['metode']})")
        if 'confidence' in hasil:
            print(f"Confidence  : {hasil['confidence']}")
        elif 'confidence_ml_awal' in hasil:
            print(f"ML Awal     : {hasil['prediksi_ml_awal']} (Conf: {hasil['confidence_ml_awal']}) -> Diselamatkan KB")
        print("-" * 65)

if __name__ == '__main__':
    main()
