from knowledge_base.kategori_keuangan import KATEGORI

# Aturan sederhana berbasis keyword untuk mencocokkan teks ke Kategori Keuangan
KB_RULES = {
    # Biaya Operasional / Rutin
    "listrik": "6-2200",     # Biaya Listrik
    "pln": "6-2200",         # Biaya Listrik
    "telepon": "6-2300",     # Biaya Telepon/Internet
    "internet": "6-2300",    # Biaya Telepon/Internet
    "indihome": "6-2300",
    "gaji": "6-4000",        # Gaji Karyawan
    "payroll": "6-4000", 
    "bbm": "6-3100",         # Biaya Operasional (BBM, dll)
    "bensin": "6-3100",
    "pertamina": "6-3100",
    "tol": "6-3100",
    
    # Biaya Administrasi
    "admin": "6-1100",       # Biaya Administrasi Bank
    "biaya bank": "6-1100",
    "pajak bunga": "6-1100",
    
    # Vendor / Pembelian
    "po ": "6-5000",         # Pembayaran Vendor / Supplier (ada spasi agar tidak match yg lain)
    "vendor": "6-5000", 
    "supplier": "6-5000",
    
    # Customer / Pemasukan
    "invoice": "4-1000",     # Pendapatan Penjualan/Invoice
    "inv ": "4-1000",
}

def klasifikasi_kb(teks):
    """
    Fungsi Pool 3: Mencoba mengklasifikasikan transaksi menggunakan aturan baku (Knowledge Base).
    Jika cocok, return status 'KB_TEREALISASI', jika tidak, return 'MANUAL_REVIEW'.
    """
    teks_lower = teks.lower()
    
    for keyword, kode_akun in KB_RULES.items():
        if keyword in teks_lower:
            # Dapatkan nama kategori dari kamus KATEGORI
            kategori_terprediksi = f"{kode_akun} - {KATEGORI.get(kode_akun, {}).get('nama', 'Unknown')}"
            
            return {
                "teks_input": teks,
                "kategori_prediksi": kategori_terprediksi,
                "status": "KB_TEREALISASI",
                "metode": "Knowledge Base (Exact Match)"
            }
            
    # Jika tidak ada yang match di KB
    return {
        "teks_input": teks,
        "kategori_prediksi": "UNKNOWN",
        "status": "MANUAL_REVIEW",
        "metode": "Manual"
    }

if __name__ == "__main__":
    # Test sederhana
    print(klasifikasi_kb("pembayaran tagihan listrik kantor bulan agustus"))
    print(klasifikasi_kb("beli sesuatu entah apa"))
