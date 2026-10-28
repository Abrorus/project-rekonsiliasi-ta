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
    Alur Routing Utama: NLP -> KB (selalu).

    1. NLP memproses teks (normalisasi + klasifikasi + confidence).
    2. Semua hasil NLP masuk ke KB, tanpa kecuali.
    3. KB menerima info confidence dari NLP:
       - Confidence >= threshold: teks sudah bersih, KB validasi & cocokkan ke data ERP.
       - Confidence < threshold: teks masih berantakan, KB analisis ulang dari awal.
    """
    if isinstance(input_data, dict) or hasattr(input_data, 'get'):
        teks = str(input_data.get('keterangan', ''))

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

    # 1. NLP: preprocessing + klasifikasi
    teks_clean = preprocess_pipeline(teks)
    X = vectorizer.transform([teks_clean])
    proba = model.predict_proba(X)[0]

    kategori_ml = model.classes_[proba.argmax()]
    confidence = float(proba.max())

    nlp_output = {
        "teks_asli": teks,
        "teks_bersih": teks_clean,
        "kategori_nlp": kategori_ml,
        "confidence": round(confidence, 4),
        "confidence_tinggi": confidence >= threshold,
    }

    # 2. KB: selalu menerima output NLP
    kb_result = klasifikasi_kb(
        input_data, jenis=jenis, mutasi=mutasi, nlp_output=nlp_output
    )

    kb_result["confidence_nlp"] = nlp_output["confidence"]
    kb_result["kategori_nlp"] = nlp_output["kategori_nlp"]

    if nlp_output["confidence_tinggi"] and kb_result["status"] != "MANUAL_REVIEW":
        kb_result["pool"] = "Pool 1 (NLP Confident + KB Validated)"
    else:
        kb_result["pool"] = "Pool 3 (Knowledge Base)"

    return kb_result

def main():
    print("=== SIMULASI INTEGRASI END-TO-END (NLP -> KB) ===\n")
    model, vectorizer = load_model()

    contoh_transaksi = [
        # NLP confident + KB punya aturan (KB menang)
        {"keterangan": "transfer gaji karyawan kantor pusat", "jenis": "DB", "mutasi": "25,000,000.00"},
        {"keterangan": "pembayaran bensin pertamina operasional sales", "jenis": "DB", "mutasi": "350,000.00"},
        # NLP ragu + KB punya aturan pasti
        {"keterangan": "TRSF E-BANKING 89000/BPJS TK", "jenis": "DB", "mutasi": "16,561,371.00"},
        {"keterangan": "BYR VIA E-BANKING PENERIMAAN NEGARA", "jenis": "DB", "mutasi": "14,978,282.00"},
        {"keterangan": "BYR VIA E-BANKING 0860 PLN JATIM DARBE JAYA ABADI P", "jenis": "DB", "mutasi": "1,694,321.00"},
        # Switching & Rekanan
        {"keterangan": "SWITCHING TRANSFER DR 008 PANCA BERSAUDARA", "jenis": "CR", "mutasi": "50,000,000.00"},
        {"keterangan": "SWITCHING TRANSFER KE 009 SENTOT PRABOWO", "jenis": "DB", "mutasi": "15,000,000.00"},
        {"keterangan": "TRSF E-BANKING CIOMAS ADISATWA", "jenis": "DB", "mutasi": "580,075,045.00"},
        {"keterangan": "TRSF E-BANKING AMERTHA JAYA", "jenis": "CR", "mutasi": "595,075,045.00"},
        # NLP confident + KB tidak punya aturan -> NLP validated
        {"keterangan": "pembayaran sewa gedung kantor", "jenis": "DB", "mutasi": "15,000,000.00"},
        # Tidak ada yang bisa menentukan -> Manual Review
        {"keterangan": "REF TXN 99823 ANOMALI TANPA KETERANGAN", "jenis": "DB", "mutasi": "100,000.00"},
    ]

    for item in contoh_transaksi:
        hasil = klasifikasi_transaksi(item, model, vectorizer, threshold=0.66)
        print(f"Transaksi    : {hasil['teks_input']} [{hasil.get('jenis', '-')}]")
        print(f"Pool         : {hasil['pool']}")
        print(f"Kode Akun    : {hasil.get('kode_akun', '-')}")
        print(f"Kategori     : {hasil['kategori_prediksi']}")
        print(f"Status       : {hasil['status']} (via {hasil['metode']})")
        print(f"NLP          : {hasil.get('kategori_nlp', '-')} (conf={hasil.get('confidence_nlp', '-')})")
        print("-" * 70)

if __name__ == '__main__':
    main()
