import sys
import json
from pathlib import Path
import joblib

# Pastikan direktori 'src' terdaftar di path sistem agar import modul selalu valid
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from knowledge_base.kb_engine import klasifikasi_kb_db as klasifikasi_kb
except ImportError:
    try:
        from knowledge_base.decision_tree_kb import klasifikasi_kb
    except ImportError:
        from src.knowledge_base.decision_tree_kb import klasifikasi_kb

try:
    from kamus_istilah import normalisasi_teks
except ImportError:
    from src.kamus_istilah import normalisasi_teks

try:
    from preprocessing import normalize_text, tokenize
    from preprocessing_lanjutan import remove_stopwords, lemmatize
except ImportError:
    try:
        from src.preprocessing import normalize_text, tokenize
        from src.preprocessing_lanjutan import remove_stopwords, lemmatize
    except ImportError:
        pass


def preprocess_pipeline(text):
    """Pipeline pembersihan teks mutasi untuk model lama."""
    if not text:
        return ""
    try:
        tokens = tokenize(normalize_text(text))
        tokens = lemmatize(remove_stopwords(tokens))
        return ' '.join(tokens)
    except Exception:
        return normalisasi_teks(text)


def load_model():
    """
    Memuat model ML NLP.
    Prioritas:
    1. Model CoA Final (model_coa_final.pkl) dari eksperimen terbaru
    2. Model gabungan SVM Linear (model_gabungan_svm_linear.pkl)
    3. Model final awal (model_final_svm_linear.pkl)
    
    Mengembalikan: (model, threshold, vectorizer)
    Untuk model baru berbasis Pipeline, vectorizer bernilai None.
    """
    model_dir = BASE_DIR / "models"
    coa_model_path = model_dir / "model_coa_final.pkl"
    thresh_path = model_dir / "threshold_coa.json"

    # 1. Cek Model CoA Baru
    if coa_model_path.exists():
        paket = joblib.load(coa_model_path)
        threshold = 0.72
        if thresh_path.exists():
            try:
                threshold = json.loads(thresh_path.read_text()).get("threshold", 0.72)
            except Exception:
                pass
        model = paket["model"] if isinstance(paket, dict) and "model" in paket else paket
        return model, threshold, None

    # 2. Fallback Model Gabungan Lama
    if (model_dir / "model_gabungan_svm_linear.pkl").exists():
        model_path = model_dir / "model_gabungan_svm_linear.pkl"
        vec_path = model_dir / "vectorizer_gabungan.pkl"
    else:
        model_path = model_dir / "model_final_svm_linear.pkl"
        vec_path = model_dir / "vectorizer_final.pkl"

    model = joblib.load(model_path)
    vectorizer = joblib.load(vec_path)
    return model, 0.66, vectorizer


def klasifikasi_transaksi(input_data, model, vectorizer=None, threshold=0.72, jenis=None, mutasi=None):
    """
    Alur Routing Utama: NLP -> KB (selalu).

    1. NLP memproses teks (normalisasi teks riil + klasifikasi CoA + confidence).
    2. Semua hasil NLP masuk ke KB, tanpa kecuali.
    3. KB menerima info confidence dari NLP:
       - Confidence >= threshold: teks sudah bersih, KB validasi & cocokkan ke data ERP.
       - Confidence < threshold: teks masih ambigu/baru, KB analisis menggunakan aturan/tree.
    """
    if isinstance(input_data, dict) or hasattr(input_data, 'get'):
        teks = str(input_data.get('keterangan', '') or input_data.get('ket', ''))

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

    jenis_norm = str(jenis or "DB").upper()
    if jenis_norm not in ("DB", "CR"):
        jenis_norm = "DB"

    # 1. NLP: preprocessing + inferensi probabilitas
    if vectorizer is None:
        # Pipeline model baru (sudah mengandung normalizer + vectorizer FeatureUnion)
        teks_clean = normalisasi_teks(teks)
        inp_teks = f"arah{jenis_norm.lower()} " + teks_clean
        proba = model.predict_proba([inp_teks])[0]
    else:
        # Model lama
        teks_clean = preprocess_pipeline(teks)
        X = vectorizer.transform([teks_clean])
        proba = model.predict_proba(X)[0]

    idx = proba.argmax()
    kategori_ml = model.classes_[idx]
    confidence = float(proba[idx])

    nlp_output = {
        "teks_asli": teks,
        "teks_bersih": teks_clean,
        "kategori_nlp": kategori_ml,
        "confidence": round(confidence, 4),
        "confidence_tinggi": confidence >= threshold,
    }

    # 2. KB: selalu menerima output NLP
    kb_result = klasifikasi_kb(
        input_data, jenis=jenis_norm, mutasi=mutasi, nlp_output=nlp_output
    )

    kb_result["confidence_nlp"] = nlp_output["confidence"]
    kb_result["kategori_nlp"] = nlp_output["kategori_nlp"]

    erp_found = (
        kb_result.get("status") in ("KB_TEREALISASI", "NLP_VALIDATED")
        and kb_result.get("kode_akun") not in ("MANUAL_REVIEW", "PERLU_REVIEW", "UNKNOWN", "-", "", None)
    )
    if nlp_output["confidence_tinggi"] and erp_found:
        kb_result["status_ui"] = "AUTO_MATCH"
    elif (not nlp_output["confidence_tinggi"]) and erp_found:
        kb_result["status_ui"] = "SUGGESTION"
    else:
        kb_result["status_ui"] = "NOT_FOUND"

    if nlp_output["confidence_tinggi"] and kb_result.get("status") not in ("MANUAL_REVIEW", "PERLU_REVIEW"):
        kb_result["pool"] = "Jalur Otomatis (NLP + KB Validated)"
    else:
        kb_result["pool"] = "Jalur KB (Knowledge Base)"

    return kb_result


def main():
    print("=== SIMULASI INTEGRASI END-TO-END (MODEL COA NLP -> KB) ===\n")
    model, threshold, vectorizer = load_model()
    print(f"Model dimuat: {type(model).__name__} | Threshold: {threshold}")
    print(f"Total kelas model: {len(model.classes_)}\n")

    contoh_transaksi = [
        {"keterangan": "transfer gaji karyawan kantor pusat", "jenis": "DB", "mutasi": "25,000,000.00"},
        {"keterangan": "pembayaran bensin pertamina operasional sales", "jenis": "DB", "mutasi": "350,000.00"},
        {"keterangan": "TRSF E-BANKING 89000/BPJS TK", "jenis": "DB", "mutasi": "16,561,371.00"},
        {"keterangan": "BYR VIA E-BANKING PENERIMAAN NEGARA", "jenis": "DB", "mutasi": "14,978,282.00"},
        {"keterangan": "BYR VIA E-BANKING 0860 PLN JATIM DARBE JAYA ABADI P", "jenis": "DB", "mutasi": "1,694,321.00"},
        {"keterangan": "SWITCHING TRANSFER DR 008 PANCA BERSAUDARA", "jenis": "CR", "mutasi": "50,000,000.00"},
        {"keterangan": "SWITCHING TRANSFER KE 009 SENTOT PRABOWO", "jenis": "DB", "mutasi": "15,000,000.00"},
        {"keterangan": "TRSF E-BANKING CIOMAS ADISATWA", "jenis": "DB", "mutasi": "580,075,045.00"},
        {"keterangan": "TRSF E-BANKING AMERTHA JAYA", "jenis": "CR", "mutasi": "595,075,045.00"},
        {"keterangan": "pembayaran sewa gedung kantor", "jenis": "DB", "mutasi": "15,000,000.00"},
        {"keterangan": "REF TXN 99823 ANOMALI TANPA KETERANGAN", "jenis": "DB", "mutasi": "100,000.00"},
    ]

    for item in contoh_transaksi:
        hasil = klasifikasi_transaksi(item, model, vectorizer=vectorizer, threshold=threshold)
        print(f"Transaksi    : {hasil['teks_input']} [{hasil.get('jenis', '-')}]")
        print(f"Pool         : {hasil.get('pool', '-')}")
        print(f"Kode Akun    : {hasil.get('kode_akun', '-')}")
        print(f"Kategori     : {hasil.get('kategori_prediksi', '-')}")
        print(f"Status       : {hasil.get('status', '-')} (via {hasil.get('metode', '-')})")
        print(f"NLP          : {hasil.get('kategori_nlp', '-')} (conf={hasil.get('confidence_nlp', '-')})")
        print("-" * 70)


if __name__ == '__main__':
    main()
