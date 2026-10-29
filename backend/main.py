import os
import sys
import shutil
import tempfile
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Pastikan root workspace terdaftar di sys.path agar impor modul src dan table_recognition valid
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Impor modul NLP & Knowledge Base
try:
    from src.routing import load_model, klasifikasi_transaksi
except ImportError as e:
    logging.error(f"Gagal mengimpor modul NLP/KB: {e}")
    load_model = None
    klasifikasi_transaksi = None

# Impor modul Table Recognition
try:
    from table_recognition.main import process_file as process_pdf_table
    from table_recognition.src.deduplicator import deduplicate_records
except ImportError as e:
    logging.error(f"Gagal mengimpor modul table_recognition: {e}")
    process_pdf_table = None
    deduplicate_records = None

# Setup FastAPI App
app = FastAPI(
    title="SiRekon - Sistem Rekonsiliasi Bank API",
    description="Backend API untuk pipeline integrasi Ekstraksi Tabel -> NLP -> Knowledge Base -> CoA Matching",
    version="1.0.0"
)

# Aktifkan CORS agar frontend Vite React (localhost:5173) bisa memanggil API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load model ML saat server mulai
ml_model = None
ml_vectorizer = None

@app.on_event("startup")
def startup_event():
    global ml_model, ml_vectorizer
    try:
        if load_model:
            ml_model, ml_vectorizer = load_model()
            logging.info("Model ML SVM & Vectorizer berhasil dimuat.")
    except Exception as e:
        logging.error(f"Error memuat model ML: {e}")

class TransactionItem(BaseModel):
    tgl: Optional[str] = "-"
    ket: str
    jenis: Optional[str] = "DB"
    mutasi: Optional[float] = 0.0

def map_reconciliation_result(raw_tx: Dict[str, Any], kb_res: Dict[str, Any]) -> Dict[str, Any]:
    """Menyelaraskan output KB ke format yang diharapkan Frontend UI."""
    kode_akun = kb_res.get("kode_akun", "-")
    status_raw = kb_res.get("status", "MANUAL_REVIEW")
    
    # Tentukan status UI ('auto' | 'review' | 'manual')
    if status_raw in ["KB_TEREALISASI", "NLP_VALIDATED"] and kode_akun not in ["PERLU_REVIEW", "UNKNOWN", "-"]:
        ui_status = "auto"
    elif status_raw == "PERLU_REVIEW" or kode_akun == "PERLU_REVIEW":
        ui_status = "review"
    else:
        ui_status = "manual"
        
    return {
        "tgl": raw_tx.get("waktu_transaksi") or raw_tx.get("tgl") or "-",
        "ket": kb_res.get("teks_input") or raw_tx.get("keterangan") or raw_tx.get("ket") or "-",
        "jenis": kb_res.get("jenis") or raw_tx.get("jenis") or "DB",
        "mutasi": float(raw_tx.get("mutasi") or raw_tx.get("debit") or raw_tx.get("kredit") or 0.0),
        "akun": kode_akun,
        "nama": kb_res.get("kategori_prediksi") or "-",
        "status": ui_status,
        "metode": kb_res.get("metode") or "-",
        "conf": float(kb_res.get("confidence_nlp") or 0.0),
        "pool": kb_res.get("pool") or "-",
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "model_loaded": ml_model is not None,
        "table_module": process_pdf_table is not None,
        "nlp_kb_module": klasifikasi_transaksi is not None
    }

@app.post("/api/reconcile-transactions")
def reconcile_transactions(transactions: List[TransactionItem]):
    """Memproses daftar transaksi langsung lewat NLP + KB."""
    if not ml_model or not ml_vectorizer or not klasifikasi_transaksi:
        raise HTTPException(status_code=500, detail="Model ML / Modul KB belum siap di server.")
        
    results = []
    for tx in transactions:
        tx_dict = tx.dict()
        kb_res = klasifikasi_transaksi(
            tx_dict,
            ml_model,
            ml_vectorizer,
            threshold=0.66,
            jenis=tx.jenis,
            mutasi=str(tx.mutasi)
        )
        results.append(map_reconciliation_result(tx_dict, kb_res))
        
    return {
        "total": len(results),
        "data": results
    }

@app.post("/api/reconcile-pdf")
async def reconcile_pdf(file: UploadFile = File(...)):
    """
    Pipeline Penuh End-to-End:
    1. Simpan PDF sementara.
    2. Ekstraksi tabel mutasi (Modul Tabel).
    3. Rekonsiliasi & klasifikasi transaksi (Modul NLP + KB).
    4. Return hasil ke Frontend.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang didukung.")
        
    if not process_pdf_table:
        raise HTTPException(status_code=500, detail="Modul Table Recognition belum terpasang.")
        
    # Simpan file ke direktori temporary
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # 1. Ekstraksi Tabel dari PDF
        raw_records = process_pdf_table(tmp_path)
        if deduplicate_records:
            raw_records = deduplicate_records(raw_records)

        # Jika PDF belum memiliki baris transaksi yang terdeteksi
        if not raw_records:
            return {
                "filename": file.filename,
                "total": 0,
                "message": "Tidak ada baris transaksi yang berhasil diekstrak dari PDF ini. Pastikan format tabel sesuai standar bank (BCA, Mandiri, BRI, BNI, BSI).",
                "data": []
            }

        # 2. Jalankan Rekonsiliasi untuk setiap baris
        results = []
        for row in raw_records:
            jenis = "DB" if float(row.get("debit", 0) or 0) > 0 else "CR"
            mutasi = row.get("debit") if jenis == "DB" else row.get("kredit")
            
            kb_res = klasifikasi_transaksi(
                row,
                ml_model,
                ml_vectorizer,
                threshold=0.66,
                jenis=jenis,
                mutasi=mutasi
            )
            results.append(map_reconciliation_result(row, kb_res))

        return {
            "filename": file.filename,
            "total": len(results),
            "data": results
        }

    finally:
        # Bersihkan file temporary
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@app.get("/api/demo-data")
def get_demo_data():
    """Mengembalikan data simulasi transaksi riil yang diproses langsung oleh NLP + KB."""
    if not ml_model or not ml_vectorizer or not klasifikasi_transaksi:
        raise HTTPException(status_code=500, detail="Model ML / Modul KB belum siap di server.")
        
    contoh_transaksi = [
        {"tgl": "02/01/2023", "keterangan": "transfer gaji karyawan kantor pusat", "jenis": "DB", "mutasi": 25000000.0},
        {"tgl": "02/01/2023", "keterangan": "pembayaran bensin pertamina operasional sales", "jenis": "DB", "mutasi": 350000.0},
        {"tgl": "03/01/2023", "keterangan": "TRSF E-BANKING 89000/BPJS TK", "jenis": "DB", "mutasi": 16561371.0},
        {"tgl": "04/01/2023", "keterangan": "BYR VIA E-BANKING PENERIMAAN NEGARA", "jenis": "DB", "mutasi": 14978282.0},
        {"tgl": "04/01/2023", "keterangan": "BYR VIA E-BANKING 0860 PLN JATIM DARBE JAYA ABADI P", "jenis": "DB", "mutasi": 1694321.0},
        {"tgl": "05/01/2023", "keterangan": "SWITCHING TRANSFER DR 008 PANCA BERSAUDARA", "jenis": "CR", "mutasi": 50000000.0},
        {"tgl": "05/01/2023", "keterangan": "SWITCHING TRANSFER KE 009 SENTOT PRABOWO", "jenis": "DB", "mutasi": 15000000.0},
        {"tgl": "06/01/2023", "keterangan": "TRSF E-BANKING CIOMAS ADISATWA", "jenis": "DB", "mutasi": 580075045.0},
        {"tgl": "06/01/2023", "keterangan": "TRSF E-BANKING AMERTHA JAYA", "jenis": "CR", "mutasi": 595075045.0},
        {"tgl": "07/01/2023", "keterangan": "pembayaran sewa gedung kantor", "jenis": "DB", "mutasi": 15000000.0},
        {"tgl": "08/01/2023", "keterangan": "REF TXN 99823 ANOMALI TANPA KETERANGAN", "jenis": "DB", "mutasi": 100000.0},
    ]

    results = []
    for item in contoh_transaksi:
        kb_res = klasifikasi_transaksi(
            item,
            ml_model,
            ml_vectorizer,
            threshold=0.66,
            jenis=item["jenis"],
            mutasi=str(item["mutasi"])
        )
        results.append(map_reconciliation_result(item, kb_res))

    return {
        "total": len(results),
        "data": results
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
