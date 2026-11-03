# =====================================================================
# kategori_keuangan.py  (VERSI 2 - sudah mengacu CoA asli dari Pak Depta)
#
# Isi file ini:
#   1. KATEGORI          -> kategori LAMA (placeholder buatan sendiri). Dibiarkan supaya
#                           skrip lama (generate_data_sintesis.py, label_data_riil.py, dst) tetap jalan.
#   2. LABEL_COA         -> kategori BARU Pool 2, disusun dari kelompok akun di CoA.xlsx
#   3. MAP_LAMA_KE_BARU  -> peta kode lama (6-5000, dst) ke label baru
#   4. MAP_SINTESIS_KE_BARU -> peta nama kategori data sintesis ke label baru
#   5. PEMILIK_REKENING  -> nama perusahaan pemilik rekening (untuk mendeteksi transfer internal)
# =====================================================================

# ---------------------------------------------------------------------
# 1. KATEGORI LAMA (jangan dihapus dulu)
# ---------------------------------------------------------------------
KATEGORI = {
    # Cash Out (Pengeluaran)
    "6-1100": {"nama": "Biaya Administrasi Bank", "jenis": "cash_out"},
    "6-2200": {"nama": "Biaya Listrik", "jenis": "cash_out"},
    "6-2300": {"nama": "Biaya Telepon/Internet", "jenis": "cash_out"},
    "6-3100": {"nama": "Biaya Operasional (BBM, dll)", "jenis": "cash_out"},
    "6-4000": {"nama": "Gaji Karyawan", "jenis": "cash_out"},
    "6-5000": {"nama": "Pembayaran Vendor/Supplier", "jenis": "cash_out"},
    "6-6000": {"nama": "Biaya BPJS Ketenagakerjaan/Kesehatan", "jenis": "cash_out"},
    "6-7000": {"nama": "Pembayaran Pajak/Setoran Negara", "jenis": "cash_out"},
    "6-8000": {"nama": "Biaya Penolakan/Lain-lain", "jenis": "cash_out"},
    "6-9000": {"nama": "Transfer Antar Bank (Switching) - Keluar", "jenis": "cash_out"},

    # Cash In (Pemasukan)
    "4-1000": {"nama": "Pendapatan Penjualan/Invoice", "jenis": "cash_in"},
    "4-2000": {"nama": "Pembayaran dari Customer", "jenis": "cash_in"},
    "4-3000": {"nama": "Pendapatan Lain-lain", "jenis": "cash_in"},
    "4-4000": {"nama": "Setoran Tunai", "jenis": "cash_in"},
    "4-5000": {"nama": "Transfer Antar Bank (Switching) - Masuk", "jenis": "cash_in"},
}

# ---------------------------------------------------------------------
# 2. LABEL BARU POOL 2 (berbasis kelompok akun di CoA Avolut)
#
# Kenapa kelompok (bukan 226 akun detail)?
#   - Data riil kita baru ~600 baris, tidak cukup untuk belajar 226 kelas.
#   - Di CoA, jenis biaya yang sama muncul dua kali: blok 6.x (biaya produksi) dan 7.1.x
#     (biaya penjualan). Dari TEKS transaksi saja, keduanya tidak bisa dibedakan.
#     Pembagian itu urusan Pool 3 (aturan/konteks). Pool 2 cukup menebak KELOMPOK-nya.
#
# arah: "keluar" = biasanya DB (cash out), "masuk" = biasanya CR (cash in), "dua_arah" = bisa keduanya
# coa : kunci akun induk (Search Key) di CoA.xlsx. Kosong [] = BELUM ADA di CoA (perlu ditanyakan).
# ---------------------------------------------------------------------
LABEL_COA = {
    # ----- ARUS KELUAR -----
    "PAYABLE_VENDOR": {"nama": "Pembayaran ke Supplier/Vendor", "arah": "keluar",
                       "coa": ["2.1.01"]},
    "SALARY":         {"nama": "Gaji, Lembur & THR", "arah": "keluar",
                       "coa": ["6.2.01", "7.1.01"]},
    "EMP_BENEFIT":    {"nama": "Tunjangan Karyawan & BPJS", "arah": "keluar",
                       "coa": ["6.2.02", "7.1.02"]},
    "TRAVEL":         {"nama": "Perjalanan Dinas", "arah": "keluar",
                       "coa": ["6.2.03", "7.1.03"]},
    "TRANSPORT":      {"nama": "Transport & BBM", "arah": "keluar",
                       "coa": ["6.2.04", "7.1.04"]},
    "UTILITIES":      {"nama": "Listrik, Air & Gas", "arah": "keluar",
                       "coa": ["6.2.05", "7.1.05"]},
    "COMMUNICATION":  {"nama": "Telepon, Internet & Pulsa", "arah": "keluar",
                       "coa": ["6.2.06", "7.1.06"]},
    "OFFICE_GENERAL": {"nama": "ATK, Konsumsi & Kebersihan Kantor", "arah": "keluar",
                       "coa": ["6.2.07", "6.2.08", "7.1.07", "7.1.08"]},
    "INSURANCE":      {"nama": "Asuransi (non-BPJS)", "arah": "keluar",
                       "coa": ["6.2.09", "7.1.09"]},
    "RENT":           {"nama": "Sewa", "arah": "keluar",
                       "coa": ["6.2.10", "6.2.11", "6.2.12", "6.2.13", "6.2.14",
                               "7.1.10", "7.1.11", "7.1.12", "7.1.13", "7.1.14"]},
    "REPAIR_MAINT":   {"nama": "Perbaikan & Pemeliharaan", "arah": "keluar",
                       "coa": ["6.2.15", "7.1.15"]},
    "OTHER_EXPENSE":  {"nama": "Biaya Lain-lain (donasi, hadiah, pelatihan, dll)", "arah": "keluar",
                       "coa": ["6.4.01", "7.3.01"]},
    "TAX":            {"nama": "Pajak & Setoran Negara", "arah": "keluar",
                       "coa": ["2.1.04", "2.1.05", "1.1.08"]},
    "BANK_CHARGE":    {"nama": "Biaya Bank (admin, transfer, tolakan)", "arah": "keluar",
                       "coa": [],   # BELUM ADA di CoA -> tanyakan ke Pak Depta
                       "catatan": "Tidak ada akun biaya bank di CoA yang diterima"},

    # ----- ARUS MASUK -----
    "RECEIVABLE_CUSTOMER": {"nama": "Penerimaan dari Customer (Piutang)", "arah": "masuk",
                            "coa": ["1.1.04"]},
    "REVENUE_OTHER":  {"nama": "Pendapatan Jasa/Lain-lain", "arah": "masuk",
                       "coa": ["4.1.01"]},
    "CASH_DEPOSIT":   {"nama": "Setoran Tunai", "arah": "masuk",
                       "coa": ["1.1.1.01"]},

    # ----- DUA ARAH -----
    "LOAN":              {"nama": "Pinjaman & Intercompany", "arah": "dua_arah",
                          "coa": ["2.2.01", "1.1.04.02"]},
    "PETTY_CASH":        {"nama": "Kas Kecil, Uang Muka & Reimburse", "arah": "dua_arah",
                          "coa": ["1.1.1.97", "1.1.09.03"]},
    "INTERNAL_TRANSFER": {"nama": "Transfer Antar Rekening Sendiri", "arah": "dua_arah",
                          "coa": ["1.1.02.98"]},
    "BANK_INTEREST":     {"nama": "Bunga & Pajak Bunga Bank", "arah": "dua_arah",
                          "coa": [],   # BELUM ADA di CoA -> tanyakan ke Pak Depta
                          "catatan": "Tidak ada akun pendapatan bunga di CoA yang diterima"},
}

LABEL_BELUM_PASTI = "PERLU_REVIEW"   # baris yang aturannya belum bisa memutuskan

# ---------------------------------------------------------------------
# 3. PETA KODE LAMA -> LABEL BARU (untuk memigrasi 337 baris BCA yang sudah kamu label)
# ---------------------------------------------------------------------
MAP_LAMA_KE_BARU = {
    "6-1100": "BANK_CHARGE",
    "6-2200": "UTILITIES",
    "6-2300": "COMMUNICATION",
    "6-3100": "PAYABLE_VENDOR",          # 2 baris "pengurusan elit" = pembayaran ke pihak ketiga
    "6-4000": "SALARY",
    "6-5000": "PAYABLE_VENDOR",
    "6-6000": "EMP_BENEFIT",
    "6-7000": "TAX",
    "6-8000": "BANK_CHARGE",             # biaya tolakan & biaya surat referensi
    "6-9000": "PAYABLE_VENDOR",          # "switching" itu jalur transfer, bukan akun -> ikut arah DB
    "4-1000": "RECEIVABLE_CUSTOMER",
    "4-2000": "RECEIVABLE_CUSTOMER",
    "4-3000": "REVENUE_OTHER",
    "4-4000": "CASH_DEPOSIT",
    "4-5000": "RECEIVABLE_CUSTOMER",     # "switching" masuk = customer bayar lewat jalur switching
}

# ---------------------------------------------------------------------
# 4. PETA NAMA KATEGORI DATA SINTESIS (dataset_sintesis_v1.csv) -> LABEL BARU
# ---------------------------------------------------------------------
MAP_SINTESIS_KE_BARU = {
    "Biaya Administrasi Bank": "BANK_CHARGE",
    "Biaya Listrik": "UTILITIES",
    "Biaya Telepon/Internet": "COMMUNICATION",
    "Biaya Operasional (BBM, dll)": "TRANSPORT",
    "Gaji Karyawan": "SALARY",
    "Pembayaran Vendor/Supplier": "PAYABLE_VENDOR",
    "Pendapatan Penjualan/Invoice": "RECEIVABLE_CUSTOMER",
    "Pembayaran dari Customer": "RECEIVABLE_CUSTOMER",
    "Pendapatan Lain-lain": "REVENUE_OTHER",
}

# ---------------------------------------------------------------------
# 5. PEMILIK REKENING (huruf besar) -> dipakai untuk mendeteksi transfer ke rekening sendiri
# ---------------------------------------------------------------------
PEMILIK_REKENING = {
    "bca": ["DARBE JAYA ABADI", "DARBE INTI NUSANTA"],
    "mandiri": ["SANTOSA JAYA MAKMUR"],
}