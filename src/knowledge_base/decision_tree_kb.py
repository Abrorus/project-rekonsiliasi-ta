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
            (["penerimaan negara", "pajak", "setoran negara", "pph", "ppn", "mpn"], "PERLU_REVIEW")  # Pajak — akun posting belum pasti di CoA mitra
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
        "keywords": [
            "biaya adm", "adm bank", "biaya transfer", "biaya txn", "ba jasa", "admin",
            "biaya bank", "tolakan", "nd-biaya tolakan", "nd-lainnya", "bunga bank",
            "jasa giro", "bunga simpanan", "saldo min", "peng saldo min"
        ],
        "sub_rules": [
            (["biaya adm", "adm bank", "biaya transfer", "biaya txn", "ba jasa", "admin", "biaya bank", "saldo min", "peng saldo min"], "PERLU_REVIEW"),  # Biaya Admin Bank
            (["tolakan", "nd-biaya tolakan", "nd-lainnya"], "PERLU_REVIEW"),  # Biaya Tolakan
            (["bunga bank", "jasa giro", "bunga simpanan"], "PERLU_REVIEW")   # Bunga Bank
        ]
    },
    "pendapatan_sewa": {
        "keywords": ["sewa cs", "cold storage", "jasa sewa", "sewa tempat"],
        "context_rules": [
            {"jenis": "CR", "kode": "PERLU_REVIEW"},  # Pendapatan Sewa Cold Storage / Tempat
            {"jenis": "DB", "kode": "PERLU_REVIEW"}   # Biaya Sewa
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

def klasifikasi_kb(input_data, jenis=None, mutasi=None, nlp_output=None):
    """
    Knowledge Base — menerima SEMUA transaksi (baik NLP confident maupun tidak).

    Parameter:
    - input_data: String teks keterangan ATAU dict/Series baris data.
    - jenis: 'CR' atau 'DB'
    - mutasi: nominal transaksi
    - nlp_output: dict dari NLP berisi {teks_asli, teks_bersih, kategori_nlp,
      confidence, confidence_tinggi}. Jika None, KB bekerja tanpa info NLP.
    """
    if isinstance(input_data, dict) or hasattr(input_data, 'get'):
        teks = str(input_data.get('keterangan', ''))

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

    # Parsing angka mutasi float untuk verifikasi nominal kecil
    try:
        mutasi_val = float(str(mutasi or 0).replace(',', ''))
    except (ValueError, TypeError):
        mutasi_val = 0.0

    # Jika NLP confidence tinggi, gunakan juga teks bersih dari NLP untuk matching
    teks_bersih_lower = None
    if nlp_output and nlp_output.get("confidence_tinggi"):
        teks_bersih_lower = nlp_output.get("teks_bersih", "").lower()

    def _cek_keyword(keywords):
        """Cek keyword di teks asli, dan juga di teks bersih NLP jika tersedia."""
        if _cocok_keyword(keywords, teks_lower):
            return True
        if teks_bersih_lower and _cocok_keyword(keywords, teks_bersih_lower):
            return True
        return False

    # --------------------------------------------------------------------------
    # TAHAP 1: EVALUASI DECISION TREE (aturan pasti KB)
    # Aturan pasti selalu dijalankan, baik NLP confident maupun tidak.
    # --------------------------------------------------------------------------
    for cabang, data in DECISION_TREE.items():
        if _cek_keyword(data["keywords"]):

            if "context_rules" in data:
                if jenis_norm == "DB":
                    # Khusus switching / bi-fast: periksa apakah ada biaya transaksi bank
                    if _cek_keyword(["biaya txn", "biaya transfer"]) or (mutasi_val > 0 and mutasi_val <= 6500 and "biaya" in teks_lower):
                        return {
                            "teks_input": teks,
                            "jenis": jenis_norm,
                            "mutasi": mutasi,
                            "kode_akun": "PERLU_REVIEW",
                            "kategori_prediksi": "PERLU_REVIEW - Biaya Administrasi Perbankan",
                            "status": "KB_TEREALISASI",
                            "metode": f"KB Tree (perbankan -> Biaya Admin Transfer)"
                        }

                    rek_res = resolve_rekanan(teks, jenis="DB")
                    if rek_res and "Master Vendor" in rek_res.get("metode", ""):
                        return {
                            "teks_input": teks,
                            "jenis": jenis_norm,
                            "mutasi": mutasi,
                            "kode_akun": "2.1.01.01",
                            "kategori_prediksi": "2.1.01.01 - Trade Payable - 3rd Party",
                            "status": "KB_TEREALISASI",
                            "metode": f"KB Tree ({cabang} -> {rek_res['metode']})"
                        }

                for c_rule in data["context_rules"]:
                    if jenis_norm == c_rule["jenis"]:
                        kode_akun = c_rule["kode"]
                        nama_akun = KATEGORI.get(kode_akun, {}).get("nama", "Akun Belum Terdaftar")
                        if kode_akun == "PERLU_REVIEW":
                            nama_akun = "Akun Belum Tersedia di CoA Mitra"
                        return {
                            "teks_input": teks,
                            "jenis": jenis_norm,
                            "mutasi": mutasi,
                            "kode_akun": kode_akun,
                            "kategori_prediksi": f"{kode_akun} - {nama_akun}",
                            "status": "KB_TEREALISASI",
                            "metode": f"KB Tree ({cabang}_{jenis_norm.lower()})"
                        }

                kode_akun = "1.1.02.98"
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

            if "sub_rules" in data:
                for ciri_khas, kode_akun in data["sub_rules"]:
                    if _cek_keyword(ciri_khas):
                        nama_akun = KATEGORI.get(kode_akun, {}).get("nama", "Unknown")
                        if kode_akun == "PERLU_REVIEW":
                            nama_akun = "Akun Belum Tersedia di CoA Mitra"
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
    # TAHAP 2: RESOLUSI REKANAN (VENDOR & CUSTOMER MATCHING)
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
    # TAHAP 3: GUNAKAN HASIL NLP (jika confidence tinggi dan KB tidak punya aturan)
    # NLP sudah yakin dan teks sudah bersih, KB terima hasilnya.
    # NLP mengembalikan nama kategori lama (misal "Pembayaran Vendor/Supplier"),
    # KB konversi ke kode CoA riil.
    # --------------------------------------------------------------------------
    if nlp_output and nlp_output.get("confidence_tinggi"):
        kategori_nlp = nlp_output["kategori_nlp"]

        # NLP return nama kategori → cari kode lama → konversi ke CoA riil
        nama_ke_kode_lama = {v["nama"]: k for k, v in KATEGORI.items() if "-" in k}
        kode_lama = nama_ke_kode_lama.get(kategori_nlp, kategori_nlp)
        hasil_coa = konversi_kode(kode_lama)

        return {
            "teks_input": teks,
            "jenis": jenis_norm,
            "mutasi": mutasi,
            "kode_akun": hasil_coa["kode_coa"],
            "kategori_prediksi": f"{hasil_coa['kode_coa']} - {hasil_coa['nama_coa']}",
            "status": "NLP_VALIDATED",
            "metode": f"NLP Confident (conf={nlp_output['confidence']}) -> KB Validated"
        }

    # --------------------------------------------------------------------------
    # TAHAP 4: KB tidak bisa menentukan & NLP juga tidak yakin -> Manual Review
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
        ("BI-FAST BIF BIAYA TXN KE GUNTUR CENTRA A KBB", "DB", "2,500.00"),
        ("TRSF E-BANKING BAYAR JASA SEWA CS", "CR", "1,000,000.00"),
        ("TRSF E-BANKING MAJU MAPAN BAHAGIA", "DB", "70,465,000.00"),
        ("Pembayaran tagihan internet indihome", "DB", "450,000.00"),
        ("Transaksi aneh yang tidak ada di kamus", "DB", "100,000.00")
    ]

    for item in test_cases:
        hasil = klasifikasi_kb(item[0], jenis=item[1], mutasi=item[2])
        print(f"Input    : {hasil['teks_input']} [{hasil['jenis']}]")
        print(f"Prediksi : {hasil['kategori_prediksi']}")
        print(f"Status   : {hasil['status']} via {hasil['metode']}\n")
