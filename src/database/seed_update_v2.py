"""
Seed Update v2: tambah data baru ke Supabase yang belum ada di seed awal.

Perubahan:
1. Branch baru: pendapatan_sewa (sewa cs, cold storage, jasa sewa, sewa tempat)
2. Keyword perbankan baru: saldo min, peng saldo min
3. Account mapping baru: SEWA, COLD STORAGE

Jalankan: python src/database/seed_update_v2.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
sb = create_client(url, key)

CLIENT_ID = "a1b2c3d4-0001-4000-8000-000000000001"


def get_node_id(kode):
    """Cari node ID berdasarkan kode."""
    res = sb.table("tree_nodes").select("id").eq("client_id", CLIENT_ID).eq("kode", kode).execute()
    return res.data[0]["id"] if res.data else None


def insert_node_if_not_exists(tree_type, kode, nama, parent_kode=None, level=0, is_leaf=True, deskripsi=None, metadata=None):
    """Insert node hanya kalau belum ada."""
    existing = get_node_id(kode)
    if existing:
        print(f"  SKIP {kode} (sudah ada)")
        return existing

    data = {
        "client_id": CLIENT_ID,
        "tree_type": tree_type,
        "kode": kode,
        "nama": nama,
        "deskripsi": deskripsi,
        "is_leaf": is_leaf,
        "level": level,
        "metadata": metadata or {},
    }
    if parent_kode:
        parent_id = get_node_id(parent_kode)
        if parent_id:
            data["parent_id"] = parent_id

    res = sb.table("tree_nodes").insert(data).execute()
    node_id = res.data[0]["id"]
    print(f"  INSERT {kode}: {nama}")
    return node_id


def insert_mapping_if_not_exists(source_kode, target_kode, relation_type):
    """Insert mapping hanya kalau belum ada."""
    source_id = get_node_id(source_kode)
    target_id = get_node_id(target_kode)
    if not source_id or not target_id:
        print(f"  SKIP mapping {source_kode} -> {target_kode}: node tidak ditemukan")
        return

    existing = sb.table("mapping_layer").select("id") \
        .eq("client_id", CLIENT_ID) \
        .eq("source_node_id", source_id) \
        .eq("target_node_id", target_id) \
        .eq("relation_type", relation_type) \
        .execute()
    if existing.data:
        print(f"  SKIP mapping {source_kode} -> {target_kode} (sudah ada)")
        return

    sb.table("mapping_layer").insert({
        "client_id": CLIENT_ID,
        "source_node_id": source_id,
        "target_node_id": target_id,
        "relation_type": relation_type,
    }).execute()
    print(f"  INSERT mapping {source_kode} -> {target_kode}")


def insert_account_mapping_if_not_exists(kode_bank, kode_erp, nama, bank=None):
    """Insert account mapping hanya kalau belum ada."""
    q = sb.table("account_mapping").select("id") \
        .eq("client_id", CLIENT_ID) \
        .eq("kode_transaksi_bank", kode_bank)
    if bank:
        q = q.eq("bank", bank)
    else:
        q = q.is_("bank", "null")
    existing = q.execute()

    if existing.data:
        print(f"  SKIP account mapping {kode_bank} (sudah ada)")
        return

    sb.table("account_mapping").insert({
        "client_id": CLIENT_ID,
        "kode_transaksi_bank": kode_bank,
        "kode_akun_erp": kode_erp,
        "nama_akun": nama,
        "bank": bank,
    }).execute()
    print(f"  INSERT account mapping {kode_bank} -> {kode_erp}")


def main():
    print("=" * 60)
    print("SIREKON — Seed Update v2")
    print("=" * 60)

    # ---- 1. Branch baru: pendapatan_sewa ----
    print("\n--- Tambah branch: pendapatan_sewa ---")
    insert_node_if_not_exists("kategori", "KAT_SEWA", "Pendapatan/Biaya Sewa",
                              parent_kode="EXPENSE", level=1, is_leaf=False,
                              deskripsi="Sewa cold storage, sewa tempat, jasa sewa")
    insert_node_if_not_exists("kategori", "KAT_SEWA_CR", "Pendapatan Sewa (PERLU_REVIEW)",
                              parent_kode="KAT_SEWA", level=2,
                              metadata={"kode_akun": "PERLU_REVIEW", "jenis": "CR"})
    insert_node_if_not_exists("kategori", "KAT_SEWA_DB", "Biaya Sewa (PERLU_REVIEW)",
                              parent_kode="KAT_SEWA", level=2,
                              metadata={"kode_akun": "PERLU_REVIEW", "jenis": "DB"})

    # Pola sewa
    insert_node_if_not_exists("pola", "POLA_SEWA", "Pola Sewa",
                              parent_kode="POLA_ROOT", level=1, is_leaf=False,
                              metadata={"keywords": ["sewa cs", "cold storage", "jasa sewa", "sewa tempat"]})
    for kw in ["sewa cs", "cold storage", "jasa sewa", "sewa tempat"]:
        kw_kode = f"POLA_SEWA_{kw.upper().replace(' ', '_')[:25]}"
        insert_node_if_not_exists("pola", kw_kode, kw, parent_kode="POLA_SEWA", level=2,
                                  metadata={"keyword": kw})

    # Mapping pola sewa -> kategori sewa
    insert_mapping_if_not_exists("POLA_SEWA", "KAT_SEWA", "pola_ke_kategori")

    # ---- 2. Keyword perbankan baru: saldo min, peng saldo min ----
    print("\n--- Tambah keyword perbankan baru ---")
    for kw in ["saldo min", "peng saldo min"]:
        kw_kode = f"POLA_ADMIN_BANK_{kw.upper().replace(' ', '_')[:25]}"
        insert_node_if_not_exists("pola", kw_kode, kw, parent_kode="POLA_ADMIN_BANK", level=2,
                                  metadata={"keyword": kw})

    # ---- 3. Account mapping baru ----
    print("\n--- Tambah account mapping baru ---")
    insert_account_mapping_if_not_exists("SEWA_CS", "PERLU_REVIEW", "Sewa Cold Storage")
    insert_account_mapping_if_not_exists("COLD_STORAGE", "PERLU_REVIEW", "Cold Storage")
    insert_account_mapping_if_not_exists("JASA_SEWA", "PERLU_REVIEW", "Jasa Sewa")
    insert_account_mapping_if_not_exists("SALDO_MIN", "PERLU_REVIEW", "Biaya Saldo Minimum")

    print("\n" + "=" * 60)
    print("UPDATE SELESAI!")
    print("=" * 60)


if __name__ == "__main__":
    main()
