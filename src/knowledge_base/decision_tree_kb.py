import re
try:
    from knowledge_base.kategori_keuangan import KATEGORI
    from knowledge_base.rekanan_resolver import resolve_rekanan
    from knowledge_base.coa import MAPPING_LAMA_KE_COA, konversi_kode, coa_nama
except ImportError:
    try:
        from src.knowledge_base.kategori_keuangan import KATEGORI
        from src.knowledge_base.rekanan_resolver import resolve_rekanan
        from src.knowledge_base.coa import MAPPING_LAMA_KE_COA, konversi_kode, coa_nama
    except ImportError:
        from kategori_keuangan import KATEGORI
        from rekanan_resolver import resolve_rekanan
        from coa import MAPPING_LAMA_KE_COA, konversi_kode, coa_nama

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
            (["penerimaan negara", "pajak", "setoran negara", "pph", "ppn", "mpn"], "PERLU_REVIEW")  # Pajak — akun posting belum pasti
        ]
    },
    "bpjs": {
        # 'bpjs kesehat' tetap dipertahankan karena keterangan BCA terpotong ("07004/BPJS KESEHAT")
        "keywords": ["bpjs", "bpjs tk", "bpjs kesehat", "bpjs kesehatan", "jamsostek"],
        "sub_rules": [
            (["bpjs tk", "bpjs kesehat", "bpjs kesehatan", "bpjs", "jamsostek"], "PERLU_REVIEW")  # BPJS — akun belum ada di CoA mitra
        ]
    },
    "setoran_tunai": {
        "keywords": ["setoran tunai", "setor tunai"],
        "sub_rules": [
            (["setoran tunai", "setor tunai"], "1.1.1.01")  # Cash on Hand:IDR
        ]
    },
    "perbankan": {
        "keywords": ["biaya adm", "adm bank", "biaya transfer", "biaya txn", "ba jasa", "admin", "biaya bank", "tolakan", "nd-biaya tolakan", "nd-lainnya", "bunga bank", "jasa giro", "bunga simpanan"],
        "sub_rules": [
            (["biaya adm", "adm bank", "biaya transfer", "biaya txn", "ba jasa", "admin", "biaya bank"], "PERLU_REVIEW"),  # Biaya Admin Bank — akun belum ada di CoA mitra
            (["tolakan", "nd-biaya tolakan", "nd-lainnya"], "PERLU_REVIEW"),  # Biaya Tolakan — akun belum ada di CoA mitra
            (["bunga bank", "jasa giro", "bunga simpanan"], "PERLU_REVIEW")   # Bunga Bank — akun belum ada di CoA mitra
        ]
    },
    "operasional": {
        "keywords": ["listrik", "pln", "telepon", "telkom", "internet", "indihome", "wifi", "gaji", "payroll", "thr", "bbm", "bensin", "pertamina", "spbu", "tol"],
        "sub_rules": [
            (["listrik", "pln"], "6.2.05.01"),             # Utilities-Electricity
            (["telepon", "telkom", "internet", "indihome", "wifi"], "6.2.05.02"),  # Utilities-Water/Telephone
            (["gaji", "payroll", "thr"], "6.2.01.01"),     # Salary & Wages-Base Salary (produksi)
            (["bbm", "bensin", "pertamina", "spbu", "tol"], "6.2.04.01")  # Transport-Transport.Out (produksi)
        ]
    },
    "switching_interbank": {
        "keywords": ["switching", "bi-fast", "bifast", "bif", "llg", "rtgs", "kliring"],
        "context_rules": [
            {"jenis": "CR", "kode": "1.1.02.98"},  # Cross Account Bank (masuk)
            {"jenis": "DB", "kode": "1.1.02.98"}   # Cross Account Bank (keluar)
        ]
    },
    "rekanan_komersial": {
        "keywords": ["po", "vendor", "supplier", "pelanggan", "customer", "cust", "invoice", "inv"],
        "context_rules": [
            {"jenis": "DB", "kode": "2.1.01.01"},  # Trade Payable-Local (bayar vendor)
            {"jenis": "CR", "kode": "1.1.04.01"}   # Trade Receivable-Local (terima customer)
        ]
    }
}

def _cocok_keyword(keywords, teks_lower):
    """
    True jika salah satu keyword muncul sebagai kata/frasa utuh di teks.
    Batas kata mencegah salah cocok substring, mis. 'tol' di 'tolakan' atau 'po' di 'depo'.
    """
    for kw in keywords:
        pola = r'(?<![a-z0-9])' + re.escape(kw.strip()) + r'(?![a-z0-9])'
        if re.search(pola, teks_lower):
            return True
    return False

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
    if isinstance(input_data, dict) or hasattr(input_data, 'get'):
        teks = str(input_data.get('keterangan', ''))
        
        # Deteksi jenis mutasi: bisa dari field 'jenis' (BCA) atau field 'debit'/'kredit' (skema Modul Tabel)
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

    teks_lower = teks.lower()
    jenis_norm = _normalisasi_jenis(jenis)

    # --------------------------------------------------------------------------
    # EVALUASI DECISION TREE
    # --------------------------------------------------------------------------
    for cabang, data in DECISION_TREE.items():
        # Level 1: Cek apakah teks memicu kata kunci cabang utama
        if _cocok_keyword(data["keywords"], teks_lower):

            # Kasus Khusus: Cabang yang memerlukan logika konteks jenis mutasi (CR/DB)
            if "context_rules" in data:
                # Jika transfer keluar (DB), periksa apakah ada nama vendor terdaftar (mis. BI-FAST ke Vendor)
                if jenis_norm == "DB":
                    rek_res = resolve_rekanan(teks, jenis="DB")
                    if rek_res and "Master Vendor" in rek_res.get("metode", ""):
                        return {
                            "teks_input": teks,
                            "jenis": jenis_norm,
                            "mutasi": mutasi,
                            "kode_akun": "2.1.01.01",
                            "kategori_prediksi": "2.1.01.01 - Trade Payable-Local",
                            "status": "KB_TEREALISASI",
                            "metode": f"KB Tree ({cabang} -> {rek_res['metode']})"
                        }

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
                kode_akun = "1.1.02.98"  # Cross Account Bank (arah tidak diketahui)
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
                    if _cocok_keyword(ciri_khas, teks_lower):
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
    # LEVEL RESOLUSI REKANAN (VENDOR & CUSTOMER MATCHING)
    # --------------------------------------------------------------------------
    rekanan_res = resolve_rekanan(teks, jenis=jenis_norm)
    if rekanan_res:
        return {
            "teks_input": teks,
            "jenis": jenis_norm,
            "mutasi": mutasi,
            "kode_akun": rekanan_res["kode_akun"],
            "kategori_prediksi": f"{rekanan_res['kode_akun']} - {rekanan_res['nama_kategori']}",
            "nama_pihak": rekanan_res.get("nama_pihak", ""),
            "status": rekanan_res["status"],
            "metode": f"KB Tree (rekanan -> {rekanan_res['metode']})"
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
