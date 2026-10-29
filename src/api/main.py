"""
SIREKON Backend API — FastAPI

Endpoints:
  POST /api/upload          Upload PDF mutasi bank
  POST /api/rekonsiliasi    Proses rekonsiliasi (terima JSON transaksi)
  GET  /api/transaksi       Ambil daftar transaksi
  GET  /api/transaksi/{id}  Detail satu transaksi
  POST /api/transaksi/{id}/konfirmasi   Konfirmasi rekomendasi (feedback loop)
  POST /api/transaksi/{id}/tolak        Tolak rekomendasi (feedback loop)
  GET  /api/stats           Statistik rekonsiliasi
  GET  /api/tree/{type}     Ambil tree nodes
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid

from api.db import get_supabase, CLIENT_ID
from api.service import proses_transaksi_batch, get_tree_nodes, get_statistik

app = FastAPI(
    title="SiRekon API",
    description="Backend API untuk Sistem Rekonsiliasi Transaksi Keuangan",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Models ----

class TransaksiInput(BaseModel):
    tanggal: str
    keterangan: str
    jenis: str  # "DB" atau "CR"
    mutasi: float
    sumber_file: Optional[str] = None


class BatchInput(BaseModel):
    transaksi: list[TransaksiInput]


class KonfirmasiInput(BaseModel):
    kode_akun_baru: Optional[str] = None
    catatan: Optional[str] = None


# ---- Endpoints ----

@app.get("/")
def root():
    return {"status": "ok", "app": "SiRekon API", "version": "0.1.0"}


@app.post("/api/rekonsiliasi")
def rekonsiliasi(batch: BatchInput):
    """
    Terima batch transaksi, proses melalui KB, simpan ke database.
    Return hasil rekonsiliasi per transaksi.
    """
    results = proses_transaksi_batch(
        [t.model_dump() for t in batch.transaksi]
    )
    return {"total": len(results), "hasil": results}


@app.get("/api/transaksi")
def list_transaksi(status: Optional[str] = None, limit: int = 100):
    """Ambil daftar transaksi dari database."""
    sb = get_supabase()
    query = sb.table("transaksi").select("*").eq("client_id", CLIENT_ID).order("created_at", desc=True).limit(limit)
    if status:
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


@app.post("/api/transaksi/{transaksi_id}/konfirmasi")
def konfirmasi_transaksi(transaksi_id: str, body: KonfirmasiInput):
    """
    User mengonfirmasi rekomendasi KB.
    Update status transaksi + update frequency-based confidence di mapping.
    """
    sb = get_supabase()

    # Ambil transaksi
    res = sb.table("transaksi").select("*").eq("id", transaksi_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    trx = res.data[0]

    kode_akun_final = body.kode_akun_baru or trx["kode_akun_erp"]

    # Update status transaksi
    sb.table("transaksi").update({
        "status": "confirmed",
        "kode_akun_erp": kode_akun_final,
        "dikonfirmasi_pada": "now()",
    }).eq("id", transaksi_id).execute()

    # Simpan feedback log
    sb.table("feedback_log").insert({
        "client_id": CLIENT_ID,
        "transaksi_id": transaksi_id,
        "aksi": "konfirmasi",
        "kode_akun_lama": trx["kode_akun_erp"],
        "kode_akun_baru": kode_akun_final,
        "catatan": body.catatan,
    }).execute()

    # Update confidence di mapping_layer (jika ada kategori_node_id)
    if trx.get("kategori_node_id"):
        _update_confidence(trx["kategori_node_id"], konfirmasi=True)

    return {"status": "confirmed", "transaksi_id": transaksi_id, "kode_akun": kode_akun_final}


@app.post("/api/transaksi/{transaksi_id}/tolak")
def tolak_transaksi(transaksi_id: str, body: KonfirmasiInput):
    """
    User menolak rekomendasi KB.
    Update status + catat feedback, confidence turun.
    """
    sb = get_supabase()

    res = sb.table("transaksi").select("*").eq("id", transaksi_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    trx = res.data[0]

    # Update status
    sb.table("transaksi").update({
        "status": "rejected",
    }).eq("id", transaksi_id).execute()

    # Simpan feedback log
    sb.table("feedback_log").insert({
        "client_id": CLIENT_ID,
        "transaksi_id": transaksi_id,
        "aksi": "tolak",
        "kode_akun_lama": trx["kode_akun_erp"],
        "kode_akun_baru": body.kode_akun_baru,
        "catatan": body.catatan,
    }).execute()

    # Update confidence (tolak = kemunculan naik, konfirmasi tidak)
    if trx.get("kategori_node_id"):
        _update_confidence(trx["kategori_node_id"], konfirmasi=False)

    return {"status": "rejected", "transaksi_id": transaksi_id}


@app.get("/api/stats")
def stats():
    """Statistik rekonsiliasi."""
    return get_statistik()


@app.get("/api/tree/{tree_type}")
def tree(tree_type: str):
    """Ambil tree nodes berdasarkan type (kategori/perusahaan/invoice/pola)."""
    valid = ["kategori", "perusahaan", "invoice", "pola"]
    if tree_type not in valid:
        raise HTTPException(status_code=400, detail=f"tree_type harus salah satu dari: {valid}")
    nodes = get_tree_nodes(tree_type)
    return {"tree_type": tree_type, "total": len(nodes), "nodes": nodes}


def _update_confidence(kategori_node_id: str, konfirmasi: bool):
    """Update frequency-based confidence di mapping_layer (Persamaan 2.2 proposal)."""
    sb = get_supabase()
    mappings = sb.table("mapping_layer").select("*") \
        .eq("client_id", CLIENT_ID) \
        .eq("target_node_id", kategori_node_id) \
        .execute()

    for m in mappings.data:
        new_total = m["total_kemunculan"] + 1
        new_konfirmasi = m["jumlah_konfirmasi_benar"] + (1 if konfirmasi else 0)
        new_confidence = new_konfirmasi / new_total if new_total > 0 else 0

        sb.table("mapping_layer").update({
            "total_kemunculan": new_total,
            "jumlah_konfirmasi_benar": new_konfirmasi,
            "confidence": round(new_confidence, 4),
        }).eq("id", m["id"]).execute()
