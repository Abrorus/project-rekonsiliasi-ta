"""
Seed script: mengisi data awal Knowledge Base ke Supabase.

Menjalankan:
    python src/database/seed.py

Data yang di-seed:
1. Client (Avolut / mitra)
2. Tree Kategori Transaksi (hierarki dari DECISION_TREE)
3. Tree Perusahaan (entitas internal + master vendor/customer)
4. Tree Pola Singkatan (keyword per kategori)
5. Account Mapping (kode transaksi bank -> kode akun ERP)
6. Mapping Layer (relasi cross-domain pola -> kategori)
"""

import os, sys, uuid
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
sb = create_client(url, key)

# Client ID tetap untuk mitra Avolut (deterministic UUID)
CLIENT_ID = "a1b2c3d4-0001-4000-8000-000000000001"

# Cache node IDs yang sudah di-insert
node_ids = {}


def insert_node(tree_type, kode, nama, parent_kode=None, deskripsi=None, is_leaf=True, level=0, metadata=None):
    """Insert satu node ke tree_nodes, return UUID-nya."""
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
    if parent_kode and parent_kode in node_ids:
        data["parent_id"] = node_ids[parent_kode]

    res = sb.table("tree_nodes").insert(data).execute()
    node_id = res.data[0]["id"]
    node_ids[kode] = node_id
    return node_id


def insert_mapping(source_kode, target_kode, relation_type):
    """Insert relasi ke mapping_layer."""
    if source_kode not in node_ids or target_kode not in node_ids:
        print(f"  SKIP mapping {source_kode} -> {target_kode}: node belum ada")
        return
    sb.table("mapping_layer").insert({
        "client_id": CLIENT_ID,
        "source_node_id": node_ids[source_kode],
        "target_node_id": node_ids[target_kode],
        "relation_type": relation_type,
    }).execute()


def seed_tree_kategori():
    """
    Tree Kategori Transaksi — hierarki dari DECISION_TREE.

    Root: Expense / Income
    Level 1: Perpajakan, BPJS, Perbankan, Operasional, Switching, Rekanan
    Level 2: Sub-kategori spesifik (PLN, Bensin, Gaji, dll)
    """
    print("\n=== SEED: Tree Kategori Transaksi ===")

    # Root nodes
    insert_node("kategori", "EXPENSE", "Expense", level=0, is_leaf=False)
    insert_node("kategori", "INCOME", "Income", level=0, is_leaf=False)

    # --- EXPENSE branches ---
    insert_node("kategori", "KAT_PAJAK", "Perpajakan & Pajak Negara", parent_kode="EXPENSE", level=1, is_leaf=False,
                deskripsi="PPh, PPN, setoran negara")
    insert_node("kategori", "PERLU_REVIEW_PAJAK", "Pajak (PERLU_REVIEW)", parent_kode="KAT_PAJAK", level=2,
                deskripsi="Akun posting pajak belum tersedia di CoA mitra", metadata={"kode_akun": "PERLU_REVIEW"})

    insert_node("kategori", "KAT_BPJS", "BPJS & Jaminan Sosial", parent_kode="EXPENSE", level=1, is_leaf=False,
                deskripsi="BPJS TK, BPJS Kesehatan, Jamsostek")
    insert_node("kategori", "PERLU_REVIEW_BPJS", "BPJS (PERLU_REVIEW)", parent_kode="KAT_BPJS", level=2,
                deskripsi="Akun BPJS belum ada di CoA mitra", metadata={"kode_akun": "PERLU_REVIEW"})

    insert_node("kategori", "KAT_PERBANKAN", "Biaya Perbankan", parent_kode="EXPENSE", level=1, is_leaf=False,
                deskripsi="Admin bank, tolakan, bunga")
    insert_node("kategori", "PERLU_REVIEW_ADMIN", "Biaya Admin Bank (PERLU_REVIEW)", parent_kode="KAT_PERBANKAN", level=2,
                metadata={"kode_akun": "PERLU_REVIEW"})
    insert_node("kategori", "PERLU_REVIEW_TOLAKAN", "Biaya Tolakan (PERLU_REVIEW)", parent_kode="KAT_PERBANKAN", level=2,
                metadata={"kode_akun": "PERLU_REVIEW"})
    insert_node("kategori", "PERLU_REVIEW_BUNGA", "Bunga Bank/Jasa Giro (PERLU_REVIEW)", parent_kode="KAT_PERBANKAN", level=2,
                metadata={"kode_akun": "PERLU_REVIEW"})

    insert_node("kategori", "KAT_OPERASIONAL", "Biaya Operasional", parent_kode="EXPENSE", level=1, is_leaf=False,
                deskripsi="Utilitas, gaji, transportasi")
    insert_node("kategori", "KAT_PLN", "Utilities-Electricity (PLN)", parent_kode="KAT_OPERASIONAL", level=2,
                metadata={"kode_akun": "6.2.05.01"})
    insert_node("kategori", "KAT_TELKOM", "Utilities-Water/Telephone", parent_kode="KAT_OPERASIONAL", level=2,
                deskripsi="Telepon, internet, Indihome", metadata={"kode_akun": "6.2.05.02"})
    insert_node("kategori", "KAT_GAJI", "Salary & Wages-Base Salary", parent_kode="KAT_OPERASIONAL", level=2,
                deskripsi="Gaji, payroll, THR (default produksi)", metadata={"kode_akun": "6.2.01.01"})
    insert_node("kategori", "KAT_BBM", "Transport-Transport Out", parent_kode="KAT_OPERASIONAL", level=2,
                deskripsi="BBM, bensin, Pertamina, SPBU, tol (default produksi)", metadata={"kode_akun": "6.2.04.01"})

    insert_node("kategori", "KAT_SWITCHING", "Switching/Transfer Antar Bank", parent_kode="EXPENSE", level=1, is_leaf=False)
    insert_node("kategori", "KAT_SWITCH_OUT", "Cross Account Bank (keluar)", parent_kode="KAT_SWITCHING", level=2,
                metadata={"kode_akun": "1.1.02.98", "jenis": "DB"})

    insert_node("kategori", "KAT_VENDOR", "Pembayaran Vendor", parent_kode="EXPENSE", level=1, is_leaf=False)
    insert_node("kategori", "KAT_TRADE_PAYABLE", "Trade Payable - 3rd Party", parent_kode="KAT_VENDOR", level=2,
                metadata={"kode_akun": "2.1.01.01", "jenis": "DB"})

    insert_node("kategori", "KAT_TUNAI", "Setoran Tunai", parent_kode="EXPENSE", level=1, is_leaf=False)
    insert_node("kategori", "KAT_CASH", "Cash on Hand IDR", parent_kode="KAT_TUNAI", level=2,
                metadata={"kode_akun": "1.1.1.01"})

    # --- INCOME branches ---
    insert_node("kategori", "KAT_SWITCH_IN", "Cross Account Bank (masuk)", parent_kode="INCOME", level=1,
                metadata={"kode_akun": "1.1.02.98", "jenis": "CR"})

    insert_node("kategori", "KAT_CUSTOMER", "Penerimaan Customer", parent_kode="INCOME", level=1, is_leaf=False)
    insert_node("kategori", "KAT_TRADE_RECEIVABLE", "Account Receivable 3rd Party", parent_kode="KAT_CUSTOMER", level=2,
                metadata={"kode_akun": "1.1.04.01", "jenis": "CR"})

    print(f"  -> {len([k for k in node_ids if k.startswith(('KAT_', 'EXPENSE', 'INCOME', 'PERLU_'))])} nodes inserted")


def seed_tree_perusahaan():
    """
    Tree Perusahaan — entitas internal (grup), vendor, customer.
    Data dari rekanan_resolver.py.
    """
    print("\n=== SEED: Tree Perusahaan ===")

    # Root
    insert_node("perusahaan", "GRUP_ROOT", "Semua Perusahaan", level=0, is_leaf=False)

    # Entitas internal (grup)
    insert_node("perusahaan", "GRUP_INTERNAL", "Entitas Internal / Afiliasi", parent_kode="GRUP_ROOT", level=1, is_leaf=False)
    for nama in ['DARBE JAYA ABADI', 'DARBE INTI NUSANTARA', 'DARBE AMERTHA JAYA', 'DARBE ALKAFIE JAYA ABADI']:
        kode = "INT_" + nama.replace(" ", "_")[:20]
        insert_node("perusahaan", kode, nama, parent_kode="GRUP_INTERNAL", level=2,
                    metadata={"tipe": "internal", "kode_akun": "1.1.02.98"})

    # Customer
    insert_node("perusahaan", "GRUP_CUSTOMER", "Customer", parent_kode="GRUP_ROOT", level=1, is_leaf=False)
    customers = [
        'AMERTHA JAYA', 'PANCA BERSAUDARA', 'SERA FOOD INDONESI', 'PRANAFOOD',
        'HARMONIS SENTRA', 'KELANA MAKMUR', 'DANUREJO RAYA FOOD', 'RIFALDI',
        'KETUT MAHAYANI', 'LUH WIRANTINI', 'PUTU SADNYANA', 'MAJU MAPAN BAHAGIA'
    ]
    for nama in customers:
        kode = "CUST_" + nama.replace(" ", "_")[:20]
        insert_node("perusahaan", kode, nama, parent_kode="GRUP_CUSTOMER", level=2,
                    metadata={"tipe": "customer", "kode_akun": "1.1.04.01"})

    # Vendor
    insert_node("perusahaan", "GRUP_VENDOR", "Vendor", parent_kode="GRUP_ROOT", level=1, is_leaf=False)
    vendors = [
        'BAREKA LINTAS INDO', 'SENTOT PRABOWO', 'CIOMAS ADISATWA',
        'BINA USAHA SANTOSA', 'RAKHMAD WAHYU', 'GEDE ARYA WIRATMA',
        'TIBAN', 'GUNTUR CENTRA', 'DIDIK HARYANTO',
        'MADE KARMAYASA', 'MADE RUMADIA', 'WAYAN SUWEDEN',
        'HAMIDAH', 'DANANJAYA', 'ERWIN SOFIANI', 'GEDE RENTADA', 'GEDE JULIANA',
        'BAGAS PUTRA', 'DUTA SELARAS ABADI', 'RUMIATI ALFIYAH'
    ]
    for nama in vendors:
        kode = "VEND_" + nama.replace(" ", "_")[:20]
        insert_node("perusahaan", kode, nama, parent_kode="GRUP_VENDOR", level=2,
                    metadata={"tipe": "vendor", "kode_akun": "2.1.01.01"})

    count = len(customers) + len(vendors) + 4 + 3  # customers + vendors + internal + group nodes
    print(f"  -> {count} nodes inserted")


def seed_tree_pola():
    """
    Tree Pola Singkatan — keyword patterns per kategori.
    Data dari DECISION_TREE keywords.
    """
    print("\n=== SEED: Tree Pola Singkatan ===")

    insert_node("pola", "POLA_ROOT", "Semua Pola", level=0, is_leaf=False)

    pola_data = {
        "POLA_PAJAK": {
            "nama": "Pola Perpajakan",
            "keywords": ["penerimaan negara", "pajak", "setoran negara", "pph", "ppn", "mpn"],
            "target_kategori": "KAT_PAJAK"
        },
        "POLA_BPJS": {
            "nama": "Pola BPJS",
            "keywords": ["bpjs", "bpjs tk", "bpjs kesehat", "bpjs kesehatan", "jamsostek"],
            "target_kategori": "KAT_BPJS"
        },
        "POLA_TUNAI": {
            "nama": "Pola Setoran Tunai",
            "keywords": ["setoran tunai", "setor tunai"],
            "target_kategori": "KAT_TUNAI"
        },
        "POLA_ADMIN_BANK": {
            "nama": "Pola Biaya Admin Bank",
            "keywords": ["biaya adm", "adm bank", "biaya transfer", "biaya txn", "ba jasa", "admin", "biaya bank"],
            "target_kategori": "KAT_PERBANKAN"
        },
        "POLA_TOLAKAN": {
            "nama": "Pola Tolakan",
            "keywords": ["tolakan", "nd-biaya tolakan", "nd-lainnya"],
            "target_kategori": "KAT_PERBANKAN"
        },
        "POLA_BUNGA": {
            "nama": "Pola Bunga/Jasa Giro",
            "keywords": ["bunga bank", "jasa giro", "bunga simpanan"],
            "target_kategori": "KAT_PERBANKAN"
        },
        "POLA_PLN": {
            "nama": "Pola PLN/Listrik",
            "keywords": ["listrik", "pln"],
            "target_kategori": "KAT_PLN"
        },
        "POLA_TELKOM": {
            "nama": "Pola Telepon/Internet",
            "keywords": ["telepon", "telkom", "internet", "indihome", "wifi"],
            "target_kategori": "KAT_TELKOM"
        },
        "POLA_GAJI": {
            "nama": "Pola Gaji/Payroll",
            "keywords": ["gaji", "payroll", "thr"],
            "target_kategori": "KAT_GAJI"
        },
        "POLA_BBM": {
            "nama": "Pola BBM/Transportasi",
            "keywords": ["bbm", "bensin", "pertamina", "spbu", "tol"],
            "target_kategori": "KAT_BBM"
        },
        "POLA_SWITCHING": {
            "nama": "Pola Switching/Transfer",
            "keywords": ["switching", "bi-fast", "bifast", "bif", "llg", "rtgs", "kliring"],
            "target_kategori": "KAT_SWITCHING"
        },
    }

    count = 0
    for kode, data in pola_data.items():
        insert_node("pola", kode, data["nama"], parent_kode="POLA_ROOT", level=1, is_leaf=False,
                    metadata={"keywords": data["keywords"]})

        # Insert setiap keyword sebagai leaf node
        for kw in data["keywords"]:
            kw_kode = f"{kode}_{kw.upper().replace(' ', '_').replace('-', '_')[:25]}"
            insert_node("pola", kw_kode, kw, parent_kode=kode, level=2,
                        metadata={"keyword": kw})
            count += 1

    print(f"  -> {count} keyword nodes + {len(pola_data)} group nodes inserted")
    return pola_data


def seed_mapping_layer(pola_data):
    """
    Mapping Layer — relasi pola -> kategori (cross-domain).
    """
    print("\n=== SEED: Mapping Layer (Pola -> Kategori) ===")

    count = 0
    for kode_pola, data in pola_data.items():
        target = data["target_kategori"]
        if kode_pola in node_ids and target in node_ids:
            insert_mapping(kode_pola, target, "pola_ke_kategori")
            count += 1

    # Mapping perusahaan -> kategori
    # Internal -> Switching
    if "GRUP_INTERNAL" in node_ids and "KAT_SWITCHING" in node_ids:
        insert_mapping("GRUP_INTERNAL", "KAT_SWITCHING", "perusahaan_ke_kategori")
        count += 1
    # Customer -> Trade Receivable
    if "GRUP_CUSTOMER" in node_ids and "KAT_TRADE_RECEIVABLE" in node_ids:
        insert_mapping("GRUP_CUSTOMER", "KAT_TRADE_RECEIVABLE", "perusahaan_ke_kategori")
        count += 1
    # Vendor -> Trade Payable
    if "GRUP_VENDOR" in node_ids and "KAT_TRADE_PAYABLE" in node_ids:
        insert_mapping("GRUP_VENDOR", "KAT_TRADE_PAYABLE", "perusahaan_ke_kategori")
        count += 1

    print(f"  -> {count} mappings inserted")


def seed_account_mapping():
    """
    Account Mapping — kode transaksi bank -> kode akun ERP.
    Dari MAPPING_LAMA_KE_COA di coa.py.
    """
    print("\n=== SEED: Account Mapping ===")

    mappings = [
        ("ADM", "PERLU_REVIEW", "Biaya Admin Bank", "BCA"),
        ("PLN", "6.2.05.01", "Utilities-Electricity", None),
        ("PLNPSC", "6.2.05.01", "Utilities-Electricity", None),
        ("BSNN", "6.2.04.01", "Transport-Transport Out (BBM)", None),
        ("MTR", "PERLU_REVIEW", "Biaya Admin Bank", "MANDIRI"),
        ("GAJI", "6.2.01.01", "Salary & Wages-Base Salary", None),
        ("PAYROLL", "6.2.01.01", "Salary & Wages-Base Salary", None),
        ("THR", "6.2.01.01", "Salary & Wages-Base Salary", None),
        ("BPJS", "PERLU_REVIEW", "BPJS (akun belum tersedia)", None),
        ("PAJAK", "PERLU_REVIEW", "Pajak (akun belum tersedia)", None),
        ("PPH", "PERLU_REVIEW", "Pajak PPh", None),
        ("PPN", "PERLU_REVIEW", "Pajak PPN", None),
        ("SWITCHING", "1.1.02.98", "Cross Account Bank", None),
        ("BIFAST", "1.1.02.98", "Cross Account Bank", None),
        ("LLG", "1.1.02.98", "Cross Account Bank", None),
        ("RTGS", "1.1.02.98", "Cross Account Bank", None),
        ("TOLAKAN", "PERLU_REVIEW", "Biaya Tolakan", None),
        ("BUNGA", "PERLU_REVIEW", "Bunga Bank/Jasa Giro", None),
        ("SETOR_TUNAI", "1.1.1.01", "Cash on Hand IDR", None),
        ("TELKOM", "6.2.05.02", "Utilities-Water/Telephone", None),
        ("INDIHOME", "6.2.05.02", "Utilities-Water/Telephone", None),
        ("WIFI", "6.2.05.02", "Utilities-Water/Telephone", None),
    ]

    for kode_bank, kode_erp, nama, bank in mappings:
        sb.table("account_mapping").insert({
            "client_id": CLIENT_ID,
            "kode_transaksi_bank": kode_bank,
            "kode_akun_erp": kode_erp,
            "nama_akun": nama,
            "bank": bank,
        }).execute()

    print(f"  -> {len(mappings)} account mappings inserted")


def main():
    print("=" * 60)
    print("SIREKON — Seed Knowledge Base ke Supabase")
    print("=" * 60)
    print(f"Client ID: {CLIENT_ID}")
    print(f"Supabase : {url}")

    seed_tree_kategori()
    seed_tree_perusahaan()
    pola_data = seed_tree_pola()
    seed_mapping_layer(pola_data)
    seed_account_mapping()

    print("\n" + "=" * 60)
    print(f"SELESAI! Total nodes: {len(node_ids)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
