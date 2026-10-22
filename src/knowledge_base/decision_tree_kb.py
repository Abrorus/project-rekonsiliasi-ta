import re
try:
    from knowledge_base.kategori_keuangan import KATEGORI
except ImportError:
    from kategori_keuangan import KATEGORI

# ==============================================================================
# STRUKTUR DECISION TREE KNOWLEDGE BASE (HIERARKIS)
# Tingkat 1 (Akar): Kategori Bisnis Utama (Tax, BPJS, Perbankan, Operasional, dsb.)
# Tingkat 2 (Cabang/Kondisi): Kata kunci spesifik dan/atau kondisi jenis mutasi (CR/DB)
# Tingkat 3 (Daun): Kode Akun Keuangan (CoA)
# ==============================================================================

DECISION_TREE = {
    "perpajakan_negara": {
        "keywords": ["penerimaan negara", "pajak", "setoran negara", "pph", "ppn", "mpn"],
        "sub_rules": [
            (["penerimaan negara", "pajak", "setoran negara", "pph", "ppn", "mpn"], "6-7000")
        ]
    },
    "bpjs": {
        "keywords": ["bpjs", "bpjs tk", "bpjs kesehat", "jamsostek"],
        "sub_rules": [
            (["bpjs tk", "bpjs kesehat", "bpjs", "jamsostek"], "6-6000")
        ]
    },
    "setoran_tunai": {
        "keywords": ["setoran tunai", "setor tunai"],
        "sub_rules": [
            (["setoran tunai", "setor tunai"], "4-4000")
        ]
    },
    "perbankan": {
        "keywords": ["biaya adm", "adm bank", "biaya transfer", "ba jasa", "tolakan", "nd-biaya tolakan", "nd-lainnya", "bunga bank", "jasa giro"],
        "sub_rules": [
            (["biaya adm", "adm bank", "biaya transfer", "ba jasa", "admin", "biaya bank"], "6-1100"),
            (["tolakan", "nd-biaya tolakan", "nd-lainnya"], "6-8000"),
            (["bunga bank", "jasa giro", "bunga simpanan"], "4-3000")
        ]
    },
    "operasional": {
        "keywords": ["listrik", "pln", "telepon", "telkom", "internet", "indihome", "wifi", "gaji", "payroll", "thr", "bbm", "bensin", "pertamina", "spbu", "tol"],
        "sub_rules": [
            (["listrik", "pln"], "6-2200"),
            (["telepon", "telkom", "internet", "indihome", "wifi"], "6-2300"),
            (["gaji", "payroll", "thr"], "6-4000"),
            (["bbm", "bensin", "pertamina", "spbu", "tol"], "6-3100")
        ]
    },
    "switching_interbank": {
        "keywords": ["switching", "bi-fast", "bifast", "bif ", "llg", "rtgs", "kliring"],
        # Sub-rules dinamis yang bergantung pada konteks mutasi (CR = Masuk, DB = Keluar)
        "context_rules": [
            {"jenis": "CR", "kode": "4-5000"},
            {"jenis": "DB", "kode": "6-9000"}
        ]
    },
    "rekanan_komersial": {
        "keywords": ["po ", "vendor", "supplier", "pelanggan", "customer", "cust ", "invoice", "inv "],
        "sub_rules": [
            (["invoice", "inv ", "pelanggan", "customer", "cust "], "4-1000"),
            (["po ", "vendor", "supplier"], "6-5000")
        ]
    }
}

def _normalisasi_jenis(jenis):
    """Menyeragamkan representasi jenis mutasi ke 'CR' (Kredit/Masuk) atau 'DB' (Debit/Keluar)."""
    if not jenis:
        return None
    j = str(jenis).strip().upper()
    if j in ["CR", "KREDIT", "CASH_IN", "MASUK", "IN"]:
        return "CR"
    if j in ["DB", "DEBIT", "CASH_OUT", "KELUAR", "OUT"]:
        return "DB"
    return None

def klasifikasi_kb(input_data, jenis=None, mutasi=None):
    """
    Fungsi Pool 3 (Knowledge Base):
    Menggunakan Decision Tree Hierarkis multi-kolom untuk mengklasifikasikan transaksi
    yang gagal / ambigu di model Machine Learning.
    
    Parameter:
    - input_data: Bisa berupa string teks keterangan ATAU dict / row pandas Series 
      yang memuat 'keterangan', 'jenis', dan 'mutasi'.
    - jenis: (opsional jika input_data string) 'CR' atau 'DB'
    - mutasi: (opsional jika input_data string) nominal transaksi
    """
    # Ekstraksi parameter jika input_data berupa dict atau pandas Series
    if isinstance(input_data, dict):
        teks = str(input_data.get('keterangan', ''))
        jenis = jenis or input_data.get('jenis')
        mutasi = mutasi or input_data.get('mutasi')
    elif hasattr(input_data, 'get'):  # pandas Series
        teks = str(input_data.get('keterangan', ''))
        jenis = jenis or input_data.get('jenis')
        mutasi = mutasi or input_data.get('mutasi')
    else:
        teks = str(input_data)

    teks_lower = teks.lower()
    jenis_norm = _normalisasi_jenis(jenis)

    # --------------------------------------------------------------------------
    # EVALUASI DECISION TREE
    # --------------------------------------------------------------------------
    for cabang, data in DECISION_TREE.items():
        # Level 1: Cek apakah teks memicu kata kunci cabang utama
        if any(kw in teks_lower for kw in data["keywords"]):

            # Kasus Khusus: Cabang yang memerlukan logika konteks jenis mutasi (CR/DB)
            if "context_rules" in data:
                for c_rule in data["context_rules"]:
                    if jenis_norm == c_rule["jenis"]:
                        kode_akun = c_rule["kode"]
                        nama_akun = KATEGORI.get(kode_akun, {}).get("nama", "Unknown")
                        return {
                            "teks_input": teks,
                            "jenis": jenis_norm,
                            "mutasi": mutasi,
                            "kode_akun": kode_akun,
                            "kategori_prediksi": f"{kode_akun} - {nama_akun}",
                            "status": "KB_TEREALISASI",
                            "metode": f"KB Tree ({cabang}_{jenis_norm.lower()})"
                        }

                # Fallback heuristik jika 'jenis' tidak diberikan: cek kata 'ke' vs 'dari'
                if "ke " in teks_lower or " /kbb" in teks_lower:
                    kode_akun = "6-9000"
                else:
                    kode_akun = "4-5000"
                nama_akun = KATEGORI.get(kode_akun, {}).get("nama", "Unknown")
                return {
                    "teks_input": teks,
                    "jenis": jenis_norm,
                    "mutasi": mutasi,
                    "kode_akun": kode_akun,
                    "kategori_prediksi": f"{kode_akun} - {nama_akun}",
                    "status": "KB_TEREALISASI",
                    "metode": f"KB Tree ({cabang}_heuristik)"
                }

            # Level 2: Evaluasi sub-rules reguler
            if "sub_rules" in data:
                for ciri_khas, kode_akun in data["sub_rules"]:
                    if any(kw in teks_lower for kw in ciri_khas):
                        nama_akun = KATEGORI.get(kode_akun, {}).get("nama", "Unknown")
                        return {
                            "teks_input": teks,
                            "jenis": jenis_norm,
                            "mutasi": mutasi,
                            "kode_akun": kode_akun,
                            "kategori_prediksi": f"{kode_akun} - {nama_akun}",
                            "status": "KB_TEREALISASI",
                            "metode": f"KB Tree ({cabang})"
                        }

    # --------------------------------------------------------------------------
    # LEVEL DAUN AKHIR: Jika tidak ada aturan spesifik yang cocok di Tree
    # --------------------------------------------------------------------------
    return {
        "teks_input": teks,
        "jenis": jenis_norm,
        "mutasi": mutasi,
        "kode_akun": "UNKNOWN",
        "kategori_prediksi": "UNKNOWN",
        "status": "MANUAL_REVIEW",
        "metode": "Manual Review (Akuntan)"
    }

if __name__ == "__main__":
    print("=== PENGUJIAN DECISION TREE KNOWLEDGE BASE ===")
    
    test_cases = [
        # (keterangan, jenis, mutasi)
        ("TRSF E-BANKING 89000/BPJS TK", "DB", "16,561,371.00"),
        ("BYR VIA E-BANKING PENERIMAAN NEGARA", "DB", "14,978,282.00"),
        ("BYR VIA E-BANKING 0860 PLN JATIM DARBE JAYA ABADI", "DB", "1,694,321.00"),
        ("BA JASA E-BANKING BIAYA TRANSFER SME", "DB", "2,900.00"),
        ("ND-BIAYA TOLAKAN 8160", "DB", "25,000.00"),
        ("SETORAN TUNAI 0465 PANCA BERSAUDARA", "CR", "520,716,650.00"),
        ("SWITCHING TRANSFER DR 008 PANCA BERSAUDARA", "CR", "50,000,000.00"),
        ("SWITCHING TRANSFER KE 009 SENTOT PRABOWO", "DB", "15,000,000.00"),
        ("Pembayaran tagihan internet indihome", "DB", "450,000.00"),
        ("Transaksi aneh yang tidak ada di kamus", "DB", "100,000.00")
    ]

    for item in test_cases:
        hasil = klasifikasi_kb(item[0], jenis=item[1], mutasi=item[2])
        print(f"Input    : {hasil['teks_input']} [{hasil['jenis']}]")
        print(f"Prediksi : {hasil['kategori_prediksi']}")
        print(f"Status   : {hasil['status']} via {hasil['metode']}\n")
