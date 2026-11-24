# Daftar Lengkap Kategori NLP & Treatment Posting ke ERP Avolut

Dokumen persiapan meeting bersama **Pak Tegar (Tim ERP Avolut)** — disusun berdasarkan arahan Pak Deptha (23 November 2026) serta daftar label resmi pada Modul NLP Pool 2 (`src/kategori_keuangan.py` & `models/model_coa_final.pkl`).

## Ringkasan Kategori
- **Total kategori terdaftar di sistem (`LABEL_COA`):** 21 kategori.
- **Kategori aktif di model terlatih saat ini (`model_coa_final.pkl`):** 17 kategori.
- **Kategori siap pakai via koreksi manual / *feedback learning* (data latih awal < 3 baris):** 4 kategori (`TRAVEL`, `INSURANCE`, `RENT`, `REPAIR_MAINT`).

## Tabel Pemetaan Kategori NLP ke API & Posting ERP

| No | Kode Label NLP (Output Pool 2) | Nama Kategori | Arah Mutasi | Status Model | Kelompok CoA | API ERP yang Dibutuhkan (Lookup) | Treatment Posting ke ERP (Push) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `RECEIVABLE_CUSTOMER` | Penerimaan dari Customer (Piutang) | CR (Masuk) | Aktif | 1.1.04 | Business Partner (Customer) + Open Invoice AR | **Incoming Payment** (vs Customer / Invoice) |
| 2 | `PAYABLE_VENDOR` | Pembayaran ke Supplier / Vendor | DB (Keluar) | Aktif | 2.1.01 | Business Partner (Vendor) + Open Invoice AP | **Outgoing Payment** (vs Vendor / Invoice) |
| 3 | `INTERNAL_TRANSFER` | Transfer Antar Rekening Sendiri / Intercompany (`MCM` same company) | CR / DB | Aktif | 1.1.02.98 | Bank Account / Intercompany Account | **Intercompany / Bank Transfer** (atau Incoming/Outgoing vs Charge Interco — *konfirmasi Pak Tegar*) |
| 4 | `LOAN` | Pinjaman & Return Loan Intercompany | CR / DB | Aktif | 2.2.01, 1.1.04.02 | Business Partner (Interco/Lender) atau Charges | **Incoming / Outgoing Payment** (vs Charge Loan / Interco) |
| 5 | `BANK_CHARGE` | Biaya Bank (admin, transfer, tolakan) | DB (Keluar) | Aktif | *(konfirmasi CoA)* | Charges (cari Charge Code sesuai akun) | **Outgoing Payment** (vs Charge) |
| 6 | `BANK_INTEREST` | Bunga Bank / Jasa Giro & Pajak Bunga | CR / DB | Aktif | *(konfirmasi CoA)* | Charges (cari Charge Code sesuai akun) | **Incoming Payment** (CR: bunga) / **Outgoing Payment** (DB: pajak bunga) vs Charge |
| 7 | `TAX` | Pajak & Setoran Negara (PPN, PPh) | DB (Keluar) | Aktif | 2.1.04, 2.1.05, 1.1.08 | Charges (cari Charge Code akun pajak) | **Outgoing Payment** (vs Charge) |
| 8 | `SALARY` | Gaji, Lembur & THR Karyawan | DB (Keluar) | Aktif | 6.2.01, 7.1.01 | Charges (atau Business Partner Employee) | **Outgoing Payment** (vs Charge) |
| 9 | `EMP_BENEFIT` | Tunjangan Karyawan & BPJS (TK/KS) | DB (Keluar) | Aktif | 6.2.02, 7.1.02 | Charges (cari Charge Code akun 6.2.02.01) | **Outgoing Payment** (vs Charge) |
| 10 | `UTILITIES` | Listrik (PLN), Air (PDAM) & Gas | DB (Keluar) | Aktif | 6.2.05, 7.1.05 | Charges | **Outgoing Payment** (vs Charge) |
| 11 | `COMMUNICATION` | Telepon, Internet & Pulsa | DB (Keluar) | Aktif | 6.2.06, 7.1.06 | Charges | **Outgoing Payment** (vs Charge) |
| 12 | `TRANSPORT` | Transport & BBM Operasional | DB (Keluar) | Aktif | 6.2.04, 7.1.04 | Charges | **Outgoing Payment** (vs Charge) |
| 13 | `OFFICE_GENERAL` | ATK, Konsumsi & Kebersihan Kantor | DB (Keluar) | Aktif | 6.2.07–08, 7.1.07–08 | Charges | **Outgoing Payment** (vs Charge) |
| 14 | `OTHER_EXPENSE` | Biaya Lain-lain (donasi, hadiah, dll.) | DB (Keluar) | Aktif | 6.4.01, 7.3.01 | Charges | **Outgoing Payment** (vs Charge) |
| 15 | `PETTY_CASH` | Kas Kecil, Uang Muka & Reimburse | CR / DB | Aktif | 1.1.1.97, 1.1.09.03 | Business Partner (Employee) atau Charges | **Outgoing / Incoming Payment** (vs Employee / Charge Kas Kecil) |
| 16 | `REVENUE_OTHER` | Pendapatan Jasa / Lain-lain | CR (Masuk) | Aktif | 4.1.01 | Charges (Pendapatan Lain) | **Incoming Payment** (vs Charge) |
| 17 | `CASH_DEPOSIT` | Setoran Tunai ke Bank | CR (Masuk) | Aktif | 1.1.1.01 | Bank / Cash Account | **Incoming Payment / Bank Transfer** (Kas ke Bank) |
| 18 | `TRAVEL` | Perjalanan Dinas | DB (Keluar) | Siap pakai* | 6.2.03, 7.1.03 | Charges | **Outgoing Payment** (vs Charge) |
| 19 | `INSURANCE` | Asuransi (non-BPJS) | DB (Keluar) | Siap pakai* | 6.2.09, 7.1.09 | Charges | **Outgoing Payment** (vs Charge) |
| 20 | `RENT` | Sewa (gedung, kendaraan, alat) | DB (Keluar) | Siap pakai* | 6.2.10–14, 7.1.10–14 | Charges / Vendor | **Outgoing Payment** (vs Charge / Vendor) |
| 21 | `REPAIR_MAINT` | Perbaikan & Pemeliharaan | DB (Keluar) | Siap pakai* | 6.2.15, 7.1.15 | Charges / Vendor | **Outgoing Payment** (vs Charge / Vendor) |

*\*Catatan: 4 kategori bertanda "Siap pakai" sudah terdaftar di `LABEL_COA` dan `proses_json.py`, tetapi belum muncul pada prediksi awal karena sampel riilnya < 3 baris; akan otomatis dipelajari begitu dikoreksi melalui `feedback_learning.py`.*

## 4 Poin Konfirmasi ke Pak Tegar saat Meeting
1. **Penyederhanaan Treatment (5 Pola sesuai Pak Deptha):**
   - **Pola 1 (Customer):** `RECEIVABLE_CUSTOMER` $\rightarrow$ Lookup Business Partner (Customer) + Invoice $\rightarrow$ Push **Incoming Payment**.
   - **Pola 2 (Vendor):** `PAYABLE_VENDOR` $\rightarrow$ Lookup Business Partner (Vendor) + Invoice $\rightarrow$ Push **Outgoing Payment**.
   - **Pola 3 (Employee / Reimburse):** `PETTY_CASH` (atau transfer ke perorangan) $\rightarrow$ Apakah di ERP masuk Business Partner tipe *Employee* atau langsung *Charge*?
   - **Pola 4 (Intercompany / Transfer Sendiri):** `INTERNAL_TRANSFER`, `CASH_DEPOSIT`, `LOAN` $\rightarrow$ Apakah ada endpoint khusus *Bank/Intercompany Transfer* di ERP atau tetap lewat Incoming/Outgoing Payment melawan *Charge* perantara?
   - **Pola 5 (Biaya & Pendapatan Langsung via Charges):** `BANK_CHARGE`, `BANK_INTEREST`, `TAX`, `SALARY`, `EMP_BENEFIT`, `UTILITIES`, `COMMUNICATION`, `TRANSPORT`, `OFFICE_GENERAL`, `OTHER_EXPENSE`, `REVENUE_OTHER`, `TRAVEL`, `INSURANCE`, `RENT`, `REPAIR_MAINT` $\rightarrow$ Lookup API **Charges** (berdasarkan kode akun CoA) $\rightarrow$ Push **Outgoing Payment** (DB) atau **Incoming Payment** (CR).
2. **Konfirmasi kode Charge / akun CoA** untuk `BANK_CHARGE` dan `BANK_INTEREST`.
3. **Kredensial API Sandbox ERP:** Base URL, Token/API Key, serta daftar endpoint untuk GET (`Business Partner`, `Invoice`, `Charges`) dan POST (`Incoming Payment`, `Outgoing Payment`).
4. **Pembaruan fungsi Feedback Loop dari Pool 2:** Sampaikan ke Mario bahwa di `src/proses_json.py` sudah tersedia fungsi `terapkan_koreksi()` dan `catat_koreksi_tunggal()` yang otomatis menyimpan koreksi (baik untuk transaksi $\ge 0,72$ maupun $< 0,72$) dan melatih ulang model SVM.
