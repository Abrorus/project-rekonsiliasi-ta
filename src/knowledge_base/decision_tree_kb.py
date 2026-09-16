from knowledge_base.kategori_keuangan import KATEGORI

# Aturan berbentuk Tree Hierarkis (Root -> Ciri Kategori Besar -> Ciri Spesifik)
DECISION_TREE = {
    "operasional": {
        "keywords": ["listrik", "pln", "telepon", "internet", "indihome", "gaji", "payroll", "bbm", "bensin", "pertamina", "tol"],
        "sub_rules": [
            (["listrik", "pln"], "6-2200"),
            (["telepon", "internet", "indihome"], "6-2300"),
            (["gaji", "payroll"], "6-4000"),
            (["bbm", "bensin", "pertamina", "tol"], "6-3100")
        ]
    },
    "administrasi": {
        "keywords": ["admin", "biaya bank", "pajak bunga"],
        "sub_rules": [
            (["admin", "biaya bank", "pajak bunga"], "6-1100")
        ]
    },
    "vendor": {
        "keywords": ["po ", "vendor", "supplier"],
        "sub_rules": [
            (["po ", "vendor", "supplier"], "6-5000")
        ]
    },
    "pendapatan": {
        "keywords": ["invoice", "inv "],
        "sub_rules": [
            (["invoice", "inv "], "4-1000")
        ]
    }
}

def klasifikasi_kb(teks):
    """
    Fungsi Pool 3: Menggunakan struktur Decision Tree untuk mencari kategori
    secara hierarkis. Pencarian dipotong jauh lebih cepat dari flat-loop.
    """
    teks_lower = teks.lower()
    
    # Level 1: Cek cabang utama (Tingkat Akar)
    for kategori_utama, data in DECISION_TREE.items():
        # Apakah teks ini cocok dengan kata kunci utama kategori ini?
        if any(kw in teks_lower for kw in data["keywords"]):
            
            # Level 2: Masuk ke sub-cabang (Tingkat Daun / Leaf)
            for ciri_khas, kode_akun in data["sub_rules"]:
                if any(kw in teks_lower for kw in ciri_khas):
                    # Tree berhasil mencapai leaf node
                    kategori_terprediksi = f"{kode_akun} - {KATEGORI.get(kode_akun, {}).get('nama', 'Unknown')}"
                    return {
                        "teks_input": teks,
                        "kategori_prediksi": kategori_terprediksi,
                        "status": "KB_TEREALISASI",
                        "metode": f"KB Tree ({kategori_utama})"
                    }
            
            # Jika sudah masuk kategori besar, tapi anehnya tidak masuk di sub-cabang 
            break
                    
    # Jika gagal rontok atau tidak ditemukan kriteria satupun di Tree
    return {
        "teks_input": teks,
        "kategori_prediksi": "UNKNOWN",
        "status": "MANUAL_REVIEW",
        "metode": "Manual"
    }

if __name__ == "__main__":
    # Test fungsi Tree
    print(klasifikasi_kb("pembayaran tagihan listrik kantor bulan agustus"))
    print(klasifikasi_kb("pembayaran po sejahtera ref 12345"))
    print(klasifikasi_kb("beli kerupuk warung sebelah"))
