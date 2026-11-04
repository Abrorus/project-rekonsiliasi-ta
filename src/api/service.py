"""
Business logic layer — menghubungkan API dengan NLP, KB Engine, dan Supabase.
"""

import re
import uuid
import datetime
from typing import Optional, List, Dict, Any
from api.db import get_supabase, CLIENT_ID

# Import KB Engine (baca dari Supabase, fallback ke hardcoded)
from knowledge_base.kb_engine import klasifikasi_kb_db as klasifikasi_kb
from knowledge_base.coa import konversi_kode, MAPPING_LAMA_KE_COA
from knowledge_base.kategori_keuangan import KATEGORI

# Lazy loading model NLP
_nlp_model = None
_nlp_threshold = 0.72
_nlp_vectorizer = None


def get_nlp_model():
    """Memuat model NLP, Threshold, & Vectorizer secara lazy."""
    global _nlp_model, _nlp_threshold, _nlp_vectorizer
    if _nlp_model is None:
        try:
            from routing import load_model
            loaded = load_model()
            if len(loaded) == 3:
                _nlp_model, _nlp_threshold, _nlp_vectorizer = loaded
            elif len(loaded) == 2:
                _nlp_model, _nlp_vectorizer = loaded
                _nlp_threshold = 0.72
        except Exception as e:
            print(f"Warning: Model NLP tidak dapat dimuat ({e}), fallback KB-only.")
    return _nlp_model, _nlp_threshold, _nlp_vectorizer


def _clean_mutasi(val: Any) -> float:
    """Parse nilai mutasi menjadi float yang aman."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(',', '').replace('Rp', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_iso_date(raw_date: Any) -> str:
    """Mengubah format tanggal mutasi menjadi format ISO YYYY-MM-DD untuk PostgreSQL."""
    if not raw_date or str(raw_date).strip() in ("-", "", "None"):
        return "2023-01-01"
    
    s = str(raw_date).strip()
    # Jika sudah format YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return s
    
    # Format DD/MM/YYYY atau DD-MM-YYYY
    m = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', s)
    if m:
        d, mth, y = m.groups()
        return f"{y}-{int(mth):02d}-{int(d):02d}"

    # Format DD/MM (asumsikan tahun 2023 berdasarkan data mutasi BCA)
    m2 = re.match(r'^(\d{1,2})[/-](\d{1,2})$', s)
    if m2:
        d, mth = m2.groups()
        return f"2023-{int(mth):02d}-{int(d):02d}"

    return "2023-01-01"


def proses_transaksi_batch(transaksi_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Proses batch transaksi melalui pipeline lengkap:
    1. Feature extraction / NLP (SVM Linear) untuk mendapatkan confidence & teks bersih
    2. Knowledge Base Engine (hierarki Supabase + Rekanan Resolver) sebagai pengambil keputusan akhir
    3. Simpan hasil transaksi ke database Supabase
    4. Return daftar hasil terstandarisasi untuk Frontend
    """
    sb = get_supabase()
    model, threshold, vectorizer = get_nlp_model()
    
    results = []

    for trx in transaksi_list:
        keterangan = str(trx.get("keterangan") or trx.get("ket") or "")
        jenis = str(trx.get("jenis") or "DB").upper()
        if jenis not in ("DB", "CR"):
            jenis = "DB"
            
        mutasi_float = _clean_mutasi(trx.get("mutasi") or trx.get("debit") or trx.get("kredit"))
        tanggal_raw = trx.get("tanggal") or trx.get("tgl") or trx.get("waktu_transaksi") or "-"
        tanggal_iso = _parse_iso_date(tanggal_raw)

        # 1. Jalankan NLP jika nlp_output belum tersedia
        nlp_output = trx.get("nlp_output")
        if not nlp_output and model and keterangan:
            try:
                from kamus_istilah import normalisasi_teks
                teks_clean = normalisasi_teks(keterangan)
                if vectorizer is None:
                    # Model CoA baru (Pipeline)
                    inp_teks = f"arah{jenis.lower()} " + teks_clean
                    proba = model.predict_proba([inp_teks])[0]
                else:
                    # Model lama
                    from routing import preprocess_pipeline
                    teks_clean = preprocess_pipeline(keterangan)
                    X = vectorizer.transform([teks_clean])
                    proba = model.predict_proba(X)[0]

                idx = proba.argmax()
                kategori_ml = model.classes_[idx]
                confidence = float(proba[idx])
                nlp_output = {
                    "teks_asli": keterangan,
                    "teks_bersih": teks_clean,
                    "kategori_nlp": kategori_ml,
                    "confidence": round(confidence, 4),
                    "confidence_tinggi": confidence >= threshold,
                }
            except Exception as e:
                nlp_output = None

        # 2. Jalankan KB Engine
        kb_result = klasifikasi_kb(
            keterangan,
            jenis=jenis,
            mutasi=mutasi_float,
            nlp_output=nlp_output,
        )

        # 3. Tentukan status pemetaan
        kb_status = kb_result.get("status", "MANUAL_REVIEW")
        kode_akun = kb_result.get("kode_akun", "-")
        
        if kb_status in ("KB_TEREALISASI", "NLP_VALIDATED") and kode_akun not in ("PERLU_REVIEW", "UNKNOWN", "-", ""):
            status = "auto_match"
        elif kb_status == "PERLU_REVIEW" or kode_akun == "PERLU_REVIEW":
            status = "suggestion"
        elif kb_status == "MANUAL_REVIEW" or kode_akun in ("UNKNOWN", "-", ""):
            status = "manual"
        else:
            status = "suggestion"

        kategori_node_id = _find_kategori_node(kode_akun)

        # 4. Simpan ke database Supabase (dengan graceful fallback jika gagal)
        trx_id = str(uuid.uuid4())
        try:
            row = {
                "client_id": CLIENT_ID,
                "tanggal": tanggal_iso,
                "keterangan": keterangan,
                "keterangan_bersih": kb_result.get("teks_bersih") or (nlp_output.get("teks_bersih") if nlp_output else None),
                "jenis": jenis,
                "mutasi": mutasi_float,
                "kode_akun_erp": kode_akun,
                "nama_akun": kb_result.get("kategori_prediksi"),
                "kategori_node_id": kategori_node_id,
                "nlp_confidence": nlp_output.get("confidence") if nlp_output else None,
                "metode_matching": kb_result.get("metode"),
                "status": status,
                "sumber_file": trx.get("sumber_file"),
                "metadata": {
                    "kb_status": kb_status,
                    "nama_pihak": kb_result.get("nama_pihak"),
                },
            }
            res = sb.table("transaksi").insert(row).execute()
            if res.data and len(res.data) > 0:
                trx_id = res.data[0]["id"]
        except Exception as e:
            # Fallback UUID jika DB insert gagal
            print(f"Notice: Simpan transaksi ke DB dilewati / error: {e}")

        # 5. Output terstandarisasi untuk Frontend
        results.append({
            "id": trx_id,
            "tanggal": tanggal_raw if tanggal_raw != "-" else tanggal_iso,
            "keterangan": keterangan,
            "jenis": jenis,
            "mutasi": mutasi_float,
            "kode_akun": kode_akun,
            "nama_akun": kb_result.get("kategori_prediksi") or "-",
            "status": status,
            "metode": kb_result.get("metode") or "-",
            "nama_pihak": kb_result.get("nama_pihak"),
            "conf": float(nlp_output.get("confidence") or 0.0) if nlp_output else 0.0,
            "pool": kb_result.get("pool") or ("Pool 1" if status == "auto_match" else "Pool 3"),
            # Properti alias untuk kompatibilitas frontend
            "tgl": tanggal_raw if tanggal_raw != "-" else tanggal_iso,
            "ket": keterangan,
            "akun": kode_akun,
            "nama": kb_result.get("kategori_prediksi") or "-",
        })

    return results


def _find_kategori_node(kode_akun: str) -> Optional[str]:
    """Cari node ID di tree_nodes berdasarkan kode_akun di metadata."""
    if not kode_akun or kode_akun in ("UNKNOWN", "PERLU_REVIEW", "-"):
        return None

    try:
        sb = get_supabase()
        res = sb.table("tree_nodes").select("id, metadata") \
            .eq("client_id", CLIENT_ID) \
            .eq("tree_type", "kategori") \
            .execute()

        for node in res.data:
            meta = node.get("metadata", {})
            if isinstance(meta, dict) and meta.get("kode_akun") == kode_akun:
                return node["id"]
    except Exception:
        pass

    return None


def get_tree_nodes(tree_type: str) -> List[Dict[str, Any]]:
    """Ambil semua nodes dari satu tree type, termasuk parent info."""
    sb = get_supabase()
    res = sb.table("tree_nodes").select("*") \
        .eq("client_id", CLIENT_ID) \
        .eq("tree_type", tree_type) \
        .order("level") \
        .execute()
    return res.data


def get_statistik() -> Dict[str, Any]:
    """Hitung statistik rekonsiliasi riil dari database Supabase."""
    sb = get_supabase()
    try:
        all_trx = sb.table("transaksi").select("id, status") \
            .eq("client_id", CLIENT_ID) \
            .execute()

        total = len(all_trx.data)
        if total == 0:
            return {"total": 0, "auto_match": 0, "suggestion": 0, "manual": 0, "confirmed": 0, "rejected": 0, "coverage": 0.0}

        counts = {}
        for trx in all_trx.data:
            s = trx["status"]
            counts[s] = counts.get(s, 0) + 1

        auto = counts.get("auto_match", 0)
        confirmed = counts.get("confirmed", 0)
        suggestion = counts.get("suggestion", 0)
        manual = counts.get("manual", 0)
        rejected = counts.get("rejected", 0)

        coverage = (auto + confirmed) / total if total > 0 else 0.0

        return {
            "total": total,
            "auto_match": auto,
            "suggestion": suggestion,
            "manual": manual,
            "confirmed": confirmed,
            "rejected": rejected,
            "coverage": round(coverage, 4),
        }
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return {"total": 0, "auto_match": 0, "suggestion": 0, "manual": 0, "confirmed": 0, "rejected": 0, "coverage": 0.0}
