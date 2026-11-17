# Lampiran 1: Detail 5 Kategori Transaksi yang Belum Ada di CoA

## Konteks
Berdasarkan analisis 337 transaksi mutasi BCA 2023 dan pencocokan dengan CoA perusahaan (313 kode akun), ditemukan **5 jenis transaksi** yang rutin muncul namun belum memiliki kode akun di Chart of Accounts.

---

### 1. Biaya Administrasi Bank
- **Jenis:** Biaya (Expense)
- **Contoh transaksi di mutasi:**
  - "BIAYA ADM" (admin bulanan rekening)
  - "BIAYA TRANSFER" / "BIAYA SKN" / "BIAYA RTGS"
- **Frekuensi:** Muncul setiap bulan (rutin)
- **Kondisi CoA saat ini:** Tidak ada akun biaya bank. Group yang paling dekat:
  - 6.4 Others Expenses (tapi isinya Training, Recruitment, dll)
  - 8.1 Non Operating Expenses (hanya ada Adjustment Stock Opname)
- **Saran:** Buat akun baru, misalnya `8.1.01.02 Bank Charges` atau di bawah group baru

### 2. Biaya Tolakan / Retur Transfer
- **Jenis:** Biaya (Expense)
- **Contoh transaksi:** Transfer gagal / dikembalikan
- **Kondisi CoA saat ini:** Tidak ada akun tolakan
- **Saran:** Bisa digabung dengan Biaya Admin Bank, atau akun terpisah

### 3. Bunga Bank / Jasa Giro
- **Jenis:** Pendapatan (Revenue/Income)
- **Contoh transaksi di mutasi:**
  - "BUNGA" (bunga tabungan/deposito)
  - "JASA GIRO" / "CR BUNGA"
- **Frekuensi:** Muncul setiap bulan (rutin)
- **Kondisi CoA saat ini:** Section Revenue (4.x) hanya berisi Revenue produk:
  - 4.1.01.01 Revenue - Raw Material
  - 4.1.01.02 Revenue - Semi Finished Goods
  - dst.
  - Tidak ada akun "Other Income" atau "Interest Income"
- **Saran:** Buat akun baru, misalnya `4.1.02.01 Interest Income` atau `8.2.01.01 Non Operating Income - Bank Interest`

### 4. Setoran Pajak (PPh/PPN ke Negara)
- **Jenis:** Pembayaran pajak ke pemerintah
- **Contoh transaksi di mutasi:**
  - "BYR VIA E-BANKING PENERIMAAN NEGARA" (Rp 14.978.282)
  - "SETORAN PAJAK PPH 21"
- **Kondisi CoA saat ini:**
  - Ada **Prepaid Tax** (1.1.08.xx) — ini untuk pajak yang sudah dibayar di muka (PPh 15, 22, 23, 24, 25, 4(2), VAT-in)
  - Ada **Withholding Tax** (2.1.04.xx) — ini untuk pajak yang dipotong dari pihak lain
  - **Pertanyaan:** Ketika perusahaan menyetor pajak ke negara (misal PPh 21 karyawan), apakah masuk ke salah satu Prepaid Tax / Withholding Tax yang sudah ada, atau perlu akun baru?
- **Kemungkinan mapping:**
  - PPh 21 karyawan → debit 2.1.04.01 (Withholding Tax:Art.21-Employee)?
  - PPN setoran → debit 2.1.05.01 (Tax Payable:VAT-Out)?
  - Mohon konfirmasi

### 5. BPJS (Ketenagakerjaan & Kesehatan)
- **Jenis:** Biaya tunjangan karyawan (Expense)
- **Contoh transaksi di mutasi:**
  - "TRSF E-BANKING 89000/BPJS TK" (Rp 16.561.371)
  - "BPJS KESEHATAN"
- **Kondisi CoA saat ini:**
  - Ada **Employee Benefit** (6.2.02.01 untuk produksi, 7.1.02.01 untuk sales/marketing)
  - **Pertanyaan:** Apakah BPJS bisa masuk ke Employee Benefit (6.2.02.01)? Atau perlu akun terpisah?

---

## Ringkasan Pertanyaan

| No | Kategori | Pertanyaan |
|----|----------|-----------|
| 1 | Biaya Admin Bank | Kode akun baru apa? |
| 2 | Biaya Tolakan | Gabung dengan no.1, atau akun terpisah? |
| 3 | Bunga Bank | Kode akun pendapatan bunga apa? |
| 4 | Setoran Pajak | Masuk ke Prepaid Tax / Withholding Tax yang ada, atau baru? |
| 5 | BPJS | Masuk ke Employee Benefit (6.2.02.01), atau baru? |
