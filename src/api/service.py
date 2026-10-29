"""
Business logic layer — menghubungkan API dengan KB modules dan database.
"""

from api.db import get_supabase, CLIENT_ID

# Import KB Engine (baca dari Supabase, fallback ke hardcoded)
from knowledge_base.kb_engine import klasifikasi_kb_db as klasifikasi_kb
from knowledge_base.coa import konversi_kode, MAPPING_LAMA_KE_COA
from knowledge_base.kategori_keuangan import KATEGORI


def proses_transaksi_batch(transaksi_list: list[dict]) -> list[dict]:
    """
    Proses batch transaksi melalui Knowledge Base dan simpan ke database.

    Setiap transaksi:
    1. Diproses oleh KB (decision tree + rekanan resolver)
    2. Disimpan ke tabel transaksi di Supabase
    3. Return hasil dengan status matching
    """
    sb = get_supabase()
    results = []

    for trx in transaksi_list:
        # Jalankan KB
        kb_result = klasifikasi_kb(
            trx["keterangan"],
            jenis=trx["jenis"],
            mutasi=trx.get("mutasi"),
            nlp_output=trx.get("nlp_output"),
        )

        # Tentukan status berdasarkan hasil KB
        if kb_result["status"] == "KB_TEREALISASI":
            status = "auto_match"
        elif kb_result["status"] == "NLP_VALIDATED":
            status = "auto_match"
        elif kb_result["status"] == "MANUAL_REVIEW":
            status = "manual"
        else:
            status = "suggestion"

        # Cari kategori node di database (untuk feedback loop nanti)
        kategori_node_id = _find_kategori_node(kb_result["kode_akun"])

        # Simpan ke database
        row = {
            "client_id": CLIENT_ID,
            "tanggal": trx["tanggal"],
            "keterangan": trx["keterangan"],
            "keterangan_bersih": kb_result.get("teks_bersih"),
            "jenis": trx["jenis"],
            "mutasi": trx["mutasi"],
            "kode_akun_erp": kb_result["kode_akun"],
            "nama_akun": kb_result["kategori_prediksi"],
            "kategori_node_id": kategori_node_id,
            "metode_matching": kb_result["metode"],
            "status": status,
            "sumber_file": trx.get("sumber_file"),
            "metadata": {
                "kb_status": kb_result["status"],
                "nama_pihak": kb_result.get("nama_pihak"),
            },
        }

        res = sb.table("transaksi").insert(row).execute()
        saved = res.data[0]

        results.append({
            "id": saved["id"],
            "tanggal": trx["tanggal"],
            "keterangan": trx["keterangan"],
            "jenis": trx["jenis"],
            "mutasi": trx["mutasi"],
            "kode_akun": kb_result["kode_akun"],
            "nama_akun": kb_result["kategori_prediksi"],
            "status": status,
            "metode": kb_result["metode"],
            "nama_pihak": kb_result.get("nama_pihak"),
        })

    return results


def _find_kategori_node(kode_akun: str) -> str | None:
    """Cari node ID di tree_nodes berdasarkan kode_akun di metadata."""
    if not kode_akun or kode_akun in ("UNKNOWN", "PERLU_REVIEW"):
        return None

    sb = get_supabase()
    # Cari node yang metadata-nya mengandung kode_akun ini
    res = sb.table("tree_nodes").select("id, metadata") \
        .eq("client_id", CLIENT_ID) \
        .eq("tree_type", "kategori") \
        .execute()

    for node in res.data:
        meta = node.get("metadata", {})
        if isinstance(meta, dict) and meta.get("kode_akun") == kode_akun:
            return node["id"]

    return None


def get_tree_nodes(tree_type: str) -> list[dict]:
    """Ambil semua nodes dari satu tree type, termasuk parent info."""
    sb = get_supabase()
    res = sb.table("tree_nodes").select("*") \
        .eq("client_id", CLIENT_ID) \
        .eq("tree_type", tree_type) \
        .order("level") \
        .execute()
    return res.data


def get_statistik() -> dict:
    """Hitung statistik rekonsiliasi dari database."""
    sb = get_supabase()

    # Total transaksi
    all_trx = sb.table("transaksi").select("id, status") \
        .eq("client_id", CLIENT_ID) \
        .execute()

    total = len(all_trx.data)
    if total == 0:
        return {"total": 0, "auto_match": 0, "suggestion": 0, "manual": 0, "confirmed": 0, "rejected": 0, "coverage": 0}

    counts = {}
    for trx in all_trx.data:
        s = trx["status"]
        counts[s] = counts.get(s, 0) + 1

    auto = counts.get("auto_match", 0)
    confirmed = counts.get("confirmed", 0)
    suggestion = counts.get("suggestion", 0)
    manual = counts.get("manual", 0)
    rejected = counts.get("rejected", 0)

    # Coverage = transaksi yang berhasil dikenali otomatis / total
    coverage = (auto + confirmed) / total if total > 0 else 0

    return {
        "total": total,
        "auto_match": auto,
        "suggestion": suggestion,
        "manual": manual,
        "confirmed": confirmed,
        "rejected": rejected,
        "coverage": round(coverage, 4),
    }
