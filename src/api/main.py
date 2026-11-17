"""
SIREKON Backend API — FastAPI (Unified Backend)

Pipeline Integrasi:
  Upload PDF Mutasi -> Ekstraksi Tabel (Arya) -> NLP Feature/Confidence 0.72 (Abror) -> KB Engine Forward Chaining ke ERP (Mario) -> 3 Status UI (Auto Match, Suggestion, Not Found) -> Feedback Loop

Endpoints:
  POST /api/reconcile-pdf              Upload PDF mutasi & rekonsiliasi end-to-end
  POST /api/reconcile-transactions     Proses JSON transaksi (kompatibilitas frontend)
  POST /api/rekonsiliasi               Proses JSON batch transaksi (Forward Chaining ulang setelah koreksi)
  GET  /api/demo-data                  Sampel data simulasi rekonsiliasi
  GET  /api/coa                        Daftar akun Chart of Accounts (CoA) ERP untuk pencocokan manual
  GET  /api/health                     Status kesehatan sistem & kesiapan modul
  GET  /api/stats                      Statistik rekonsiliasi & coverage live
  GET  /api/transaksi                  Daftar transaksi tersimpan di database
  GET  /api/transaksi/{id}             Detail transaksi
  POST /api/transaksi/{id}/konfirmasi  Konfirmasi rekomendasi / simpan pencocokan manual (feedback loop)
  POST /api/transaksi/{id}/tolak       Tolak & koreksi rekomendasi (feedback loop)
  GET  /api/tree/{type}                Ambil hierarki tree nodes
"""

import os
import sys
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent.parent
for p in (ROOT, ROOT / "src", ROOT / "table_recognition"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.db import get_supabase, CLIENT_ID
from api.service import (
    proses_transaksi_batch,
    get_tree_nodes,
    get_statistik,
    get_nlp_model,
    get_daftar_coa,
)
from knowledge_base.coa import coa_nama

# Impor modul Table Recognition
try:
    from table_recognition.main import process_file as process_pdf_table
    from table_recognition.src.deduplicator import deduplicate_records
except ImportError:
    try:
        from main import process_file as process_pdf_table
        from src.deduplicator import deduplicate_records
    except ImportError:
        process_pdf_table = None
        deduplicate_records = None

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SiRekon - Sistem Rekonsiliasi Bank API",
    description="Unified API: Ekstraksi Tabel -> NLP (Threshold 0.72) -> Knowledge Base (Forward Chaining ERP) -> 3 Status UI & Feedback Loop",
    version="1.0.0",
)

# Aktifkan CORS untuk Frontend React (Vite: 5173, Web: 3000, dll)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """Inisialisasi & pre-warm modul NLP saat server mulai."""
    try:
        model, _, vec = get_nlp_model()
        if model:
            logger.info("Model NLP SVM & Vectorizer berhasil dimuat.")
    except Exception as e:
        logger.warning(f"Startup notice: {e}")


# ---- Pydantic Models ----

class TransaksiInput(BaseModel):
    tanggal: Optional[str] = "-"
    keterangan: str
    jenis: Optional[str] = "DB"  # "DB" atau "CR"
    debit: Optional[float] = 0.0
    kredit: Optional[float] = 0.0
    saldo: Optional[float] = 0.0
    mutasi: Optional[float] = 0.0
    sumber_file: Optional[str] = None


class BatchInput(BaseModel):
    transaksi: List[TransaksiInput]


class TransactionItem(BaseModel):
    """Format alternatif untuk kompatibilitas frontend."""
    tgl: Optional[str] = "-"
    tanggal: Optional[str] = "-"
    ket: Optional[str] = ""
    keterangan: Optional[str] = ""
    jenis: Optional[str] = "DB"
    debit: Optional[float] = 0.0
    kredit: Optional[float] = 0.0
    saldo: Optional[float] = 0.0
    mutasi: Optional[float] = 0.0


class KonfirmasiInput(BaseModel):
    kode_akun_baru: Optional[str] = None
    catatan: Optional[str] = None
    dikonfirmasi_oleh: Optional[str] = "user"


# ---- Endpoints ----

@app.get("/")
def root():
    return {
        "status": "ok",
        "app": "SiRekon Unified API",
        "version": "1.0.0",
    }


@app.get("/api/health")
def health_check():
    model, threshold, _ = get_nlp_model()
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "nlp_threshold": threshold,
        "table_module": process_pdf_table is not None,
        "supabase_connected": True,
    }


@app.get("/api/coa")
def list_coa():
    """Mengambil daftar lengkap akun CoA ERP mitra untuk pencocokan manual di UI."""
    coa_list = get_daftar_coa()
    return {
        "total": len(coa_list),
        "coa": coa_list,
    }


@app.post("/api/reconcile-pdf")
async def reconcile_pdf(file: UploadFile = File(...)):
    """
    Pipeline Rekonsiliasi End-to-End dari PDF:
    1. Simpan PDF mutasi sementara
    2. Ekstraksi tabel transaksi (Modul Table Recognition: Tanggal, Keterangan, Debit, Kredit, Saldo)
    3. Normalisasi & deduplikasi baris
    4. Klasifikasi cerdas (NLP Confidence 0.72 + KB Engine Forward Chaining ke ERP)
    5. Simpan transaksi ke database & sediakan UUID untuk Feedback Loop
    6. Return hasil komprehensif ke Frontend
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang didukung.")

    if not process_pdf_table:
        raise HTTPException(status_code=500, detail="Modul Table Recognition belum terpasang.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = process_pdf_table(tmp_path)
        # process_file() returns {"file", "bank", "status", "transaksi": [...], ...}
        if isinstance(result, dict):
            raw_records = result.get("transaksi", [])
            source_bank = result.get("bank", "")
            source_file = result.get("file", file.filename)
            for rec in raw_records:
                rec.setdefault("bank", source_bank)
                rec.setdefault("source_file", source_file)
        else:
            raw_records = result or []
        if deduplicate_records and raw_records:
            raw_records = deduplicate_records(raw_records)

        if not raw_records:
            return {
                "filename": file.filename,
                "total": 0,
                "message": "Tidak ada baris transaksi yang berhasil diekstrak dari PDF ini. Pastikan format tabel sesuai standar bank.",
                "hasil": [],
                "data": [],
            }

        transaksi_list = []
        for row in raw_records:
            debit_val = float(str(row.get("debit", 0) or 0).replace(",", "").strip() or 0)
            kredit_val = float(str(row.get("kredit", 0) or 0).replace(",", "").strip() or 0)
            saldo_val = float(str(row.get("saldo", 0) or 0).replace(",", "").strip() or 0)

            if debit_val > 0:
                jenis = "DB"
                mutasi = debit_val
            elif kredit_val > 0:
                jenis = "CR"
                mutasi = kredit_val
            else:
                jenis = str(row.get("jenis") or "DB").upper()
                mutasi = float(str(row.get("mutasi", 0) or 0).replace(",", "").strip() or 0)
                if jenis == "DB":
                    debit_val = mutasi
                else:
                    kredit_val = mutasi

            keterangan = str(row.get("keterangan") or row.get("deskripsi") or row.get("uraian") or "")
            tanggal = str(row.get("waktu_transaksi") or row.get("tanggal") or row.get("tgl") or "-")

            transaksi_list.append({
                "tanggal": tanggal,
                "keterangan": keterangan,
                "jenis": jenis,
                "debit": debit_val,
                "kredit": kredit_val,
                "saldo": saldo_val,
                "mutasi": mutasi,
                "sumber_file": file.filename,
            })

        results = proses_transaksi_batch(transaksi_list)

        return {
            "filename": file.filename,
            "total": len(results),
            "hasil": results,
            "data": results,
        }

    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@app.post("/api/reconcile-transactions")
def reconcile_transactions(transactions: List[TransactionItem]):
    """Memproses daftar transaksi mentah JSON melalui pipeline NLP + KB Engine."""
    tx_list = []
    for tx in transactions:
        ket = tx.keterangan or tx.ket or ""
        tgl = tx.tanggal if tx.tanggal and tx.tanggal != "-" else (tx.tgl or "-")
        tx_list.append({
            "tanggal": tgl,
            "keterangan": ket,
            "jenis": tx.jenis or "DB",
            "debit": tx.debit or 0.0,
            "kredit": tx.kredit or 0.0,
            "saldo": tx.saldo or 0.0,
            "mutasi": tx.mutasi or 0.0,
        })
    results = proses_transaksi_batch(tx_list)
    return {
        "total": len(results),
        "hasil": results,
        "data": results,
    }


@app.post("/api/rekonsiliasi")
def rekonsiliasi(batch: BatchInput):
    """Endpoint batch rekonsiliasi standar (mendukung re-evaluasi Forward Chaining setelah koreksi keterangan)."""
    results = proses_transaksi_batch(
        [t.model_dump() for t in batch.transaksi]
    )
    return {
        "total": len(results),
        "hasil": results,
        "data": results,
    }


@app.get("/api/demo-data")
def get_demo_data():
    """Mengembalikan data simulasi transaksi dengan 5 kolom standar yang diproses via pipeline penuh."""
    contoh_transaksi = [
        {
            "tanggal": "2023-01-02",
            "keterangan": "transfer gaji karyawan kantor pusat",
            "jenis": "DB",
            "debit": 25000000.0,
            "kredit": 0.0,
            "saldo": 475000000.0,
            "mutasi": 25000000.0,
        },
        {
            "tanggal": "2023-01-02",
            "keterangan": "pembayaran bensin pertamina operasional sales",
            "jenis": "DB",
            "debit": 350000.0,
            "kredit": 0.0,
            "saldo": 474650000.0,
            "mutasi": 350000.0,
        },
        {
            "tanggal": "2023-01-03",
            "keterangan": "TRSF E-BANKING 89000/BPJS TK",
            "jenis": "DB",
            "debit": 16561371.0,
            "kredit": 0.0,
            "saldo": 458088629.0,
            "mutasi": 16561371.0,
        },
        {
            "tanggal": "2023-01-04",
            "keterangan": "BYR VIA E-BANKING PENERIMAAN NEGARA",
            "jenis": "DB",
            "debit": 14978282.0,
            "kredit": 0.0,
            "saldo": 443110347.0,
            "mutasi": 14978282.0,
        },
        {
            "tanggal": "2023-01-04",
            "keterangan": "BYR VIA E-BANKING 0860 PLN JATIM DARBE JAYA ABADI P",
            "jenis": "DB",
            "debit": 1694321.0,
            "kredit": 0.0,
            "saldo": 441416026.0,
            "mutasi": 1694321.0,
        },
        {
            "tanggal": "2023-01-05",
            "keterangan": "SWITCHING TRANSFER DR 008 PANCA BERSAUDARA",
            "jenis": "CR",
            "debit": 0.0,
            "kredit": 50000000.0,
            "saldo": 491416026.0,
            "mutasi": 50000000.0,
        },
        {
            "tanggal": "2023-01-05",
            "keterangan": "SWITCHING TRANSFER KE 009 SENTOT PRABOWO",
            "jenis": "DB",
            "debit": 15000000.0,
            "kredit": 0.0,
            "saldo": 476416026.0,
            "mutasi": 15000000.0,
        },
        {
            "tanggal": "2023-01-06",
            "keterangan": "TRSF E-BANKING CIOMAS ADISATWA",
            "jenis": "DB",
            "debit": 580075045.0,
            "kredit": 0.0,
            "saldo": 196340981.0,
            "mutasi": 580075045.0,
        },
        {
            "tanggal": "2023-01-06",
            "keterangan": "TRSF E-BANKING AMERTHA JAYA",
            "jenis": "CR",
            "debit": 0.0,
            "kredit": 595075045.0,
            "saldo": 791416026.0,
            "mutasi": 595075045.0,
        },
        {
            "tanggal": "2023-01-07",
            "keterangan": "pembayaran sewa gedung kantor",
            "jenis": "DB",
            "debit": 15000000.0,
            "kredit": 0.0,
            "saldo": 776416026.0,
            "mutasi": 15000000.0,
        },
        {
            "tanggal": "2023-01-08",
            "keterangan": "REF TXN 99823 ANOMALI TANPA KETERANGAN",
            "jenis": "DB",
            "debit": 100000.0,
            "kredit": 0.0,
            "saldo": 776316026.0,
            "mutasi": 100000.0,
        },
    ]
    results = proses_transaksi_batch(contoh_transaksi)
    return {
        "total": len(results),
        "hasil": results,
        "data": results,
    }


@app.get("/api/transaksi")
def list_transaksi(status: Optional[str] = None, limit: int = 100):
    """Ambil daftar transaksi tersimpan dari database Supabase."""
    sb = get_supabase()
    query = sb.table("transaksi").select("*").eq("client_id", CLIENT_ID).order("created_at", desc=True).limit(limit)
    if status:
        if status == "not_found":
            status = "manual"
        query = query.eq("status", status)
    res = query.execute()
    return {"total": len(res.data), "transaksi": res.data}


@app.get("/api/transaksi/{transaksi_id}")
def get_transaksi(transaksi_id: str):
    """Detail satu transaksi."""
    sb = get_supabase()
    res = sb.table("transaksi").select("*").eq("id", transaksi_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    return res.data[0]


def _resolve_nama_akun_lengkap(kode_akun: str, default_nama: Optional[str] = None) -> str:
    """Mengambil format 'KODE - Nama Akun' dari CoA ERP."""
    if not kode_akun or kode_akun in ("CONFIRMED", "NOT_FOUND", "UNKNOWN", "-"):
        return default_nama or kode_akun
    try:
        nama = coa_nama(kode_akun)
        if nama:
            return f"{kode_akun} - {nama}"
    except Exception:
        pass
    return default_nama or kode_akun


@app.post("/api/transaksi/{transaksi_id}/konfirmasi")
def konfirmasi_transaksi(transaksi_id: str, body: KonfirmasiInput):
    """
    Feedback Loop: User menyetujui rekomendasi KB atau menetapkan akun ERP manual (pada Not Found / Suggestion).
    1. Update status transaksi menjadi 'confirmed'
    2. Catat audit feedback ke feedback_log
    3. Perbarui frequency-based confidence di mapping_layer
    """
    sb = get_supabase()

    res = sb.table("transaksi").select("*").eq("id", transaksi_id).execute()
    if not res.data:
        kode_final = body.kode_akun_baru or "CONFIRMED"
        return {
            "status": "confirmed",
            "transaksi_id": transaksi_id,
            "kode_akun": kode_final,
            "nama_akun": _resolve_nama_akun_lengkap(kode_final),
        }
        
    trx = res.data[0]
    kode_akun_final = body.kode_akun_baru or trx["kode_akun_erp"]
    nama_akun_final = _resolve_nama_akun_lengkap(kode_akun_final, trx.get("nama_akun"))

    # 1. Update status transaksi
    sb.table("transaksi").update({
        "status": "confirmed",
        "kode_akun_erp": kode_akun_final,
        "nama_akun": nama_akun_final,
        "dikonfirmasi_pada": "now()",
        "dikonfirmasi_oleh": body.dikonfirmasi_oleh or "user",
    }).eq("id", transaksi_id).execute()

    # 2. Simpan feedback log
    try:
        aksi_type = "manual_input" if trx.get("status") == "manual" else "konfirmasi"
        sb.table("feedback_log").insert({
            "client_id": CLIENT_ID,
            "transaksi_id": transaksi_id,
            "aksi": aksi_type,
            "kode_akun_lama": trx.get("kode_akun_erp"),
            "kode_akun_baru": kode_akun_final,
            "catatan": body.catatan,
        }).execute()
    except Exception as e:
        logger.warning(f"Catat feedback log dilewati: {e}")

    # 3. Update frequency-based confidence di mapping_layer
    if trx.get("kategori_node_id"):
        _update_confidence(trx["kategori_node_id"], konfirmasi=True)

    return {
        "status": "confirmed",
        "transaksi_id": transaksi_id,
        "kode_akun": kode_akun_final,
        "nama_akun": nama_akun_final,
    }


@app.post("/api/transaksi/{transaksi_id}/tolak")
def tolak_transaksi(transaksi_id: str, body: KonfirmasiInput):
    """
    Feedback Loop: User menolak rekomendasi KB & memasukkan koreksi akun ERP yang benar.
    1. Update status transaksi menjadi 'rejected' (atau ter-koreksi dengan kode akun baru)
    2. Catat audit feedback ke feedback_log
    3. Perbarui frequency-based confidence di mapping_layer (confidence turun)
    """
    sb = get_supabase()

    res = sb.table("transaksi").select("*").eq("id", transaksi_id).execute()
    if not res.data:
        kode_final = body.kode_akun_baru or "-"
        return {
            "status": "rejected",
            "transaksi_id": transaksi_id,
            "kode_akun": kode_final,
            "nama_akun": _resolve_nama_akun_lengkap(kode_final),
        }

    trx = res.data[0]
    kode_akun_final = body.kode_akun_baru or trx.get("kode_akun_erp")
    nama_akun_final = _resolve_nama_akun_lengkap(kode_akun_final, trx.get("nama_akun"))

    # 1. Update status transaksi
    update_payload = {
        "status": "rejected",
        "dikonfirmasi_pada": "now()",
        "dikonfirmasi_oleh": body.dikonfirmasi_oleh or "user",
    }
    if body.kode_akun_baru:
        update_payload["kode_akun_erp"] = kode_akun_final
        update_payload["nama_akun"] = nama_akun_final

    sb.table("transaksi").update(update_payload).eq("id", transaksi_id).execute()

    # 2. Simpan feedback log
    try:
        sb.table("feedback_log").insert({
            "client_id": CLIENT_ID,
            "transaksi_id": transaksi_id,
            "aksi": "tolak",
            "kode_akun_lama": trx.get("kode_akun_erp"),
            "kode_akun_baru": body.kode_akun_baru,
            "catatan": body.catatan,
        }).execute()
    except Exception as e:
        logger.warning(f"Catat feedback log dilewati: {e}")

    # 3. Update confidence (total_kemunculan bertambah, konfirmasi tidak bertambah -> score turun)
    if trx.get("kategori_node_id"):
        _update_confidence(trx["kategori_node_id"], konfirmasi=False)

    return {
        "status": "rejected",
        "transaksi_id": transaksi_id,
        "kode_akun": kode_akun_final,
        "nama_akun": nama_akun_final,
    }


@app.get("/api/stats")
def stats():
    """Statistik live rekonsiliasi dan rasio coverage otomatis."""
    return get_statistik()


@app.get("/api/tree/{tree_type}")
def tree(tree_type: str):
    """Ambil hierarki tree nodes (kategori / perusahaan / invoice / pola)."""
    valid = ["kategori", "perusahaan", "invoice", "pola"]
    if tree_type not in valid:
        raise HTTPException(status_code=400, detail=f"tree_type harus salah satu dari: {valid}")
    nodes = get_tree_nodes(tree_type)
    return {"tree_type": tree_type, "total": len(nodes), "nodes": nodes}


def _update_confidence(kategori_node_id: str, konfirmasi: bool):
    """Update frequency-based confidence di mapping_layer (Persamaan 2.2 proposal TA)."""
    try:
        sb = get_supabase()
        mappings = sb.table("mapping_layer").select("*") \
            .eq("client_id", CLIENT_ID) \
            .eq("target_node_id", kategori_node_id) \
            .execute()

        for m in mappings.data:
            new_total = m["total_kemunculan"] + 1
            new_konfirmasi = m["jumlah_konfirmasi_benar"] + (1 if konfirmasi else 0)
            new_confidence = new_konfirmasi / new_total if new_total > 0 else 0.0

            sb.table("mapping_layer").update({
                "total_kemunculan": new_total,
                "jumlah_konfirmasi_benar": new_konfirmasi,
                "confidence": round(new_confidence, 4),
            }).eq("id", m["id"]).execute()
    except Exception as e:
        logger.warning(f"Update confidence dilewati: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="127.0.0.1", port=8000, reload=True)
