# Draft Chat ke Mitra (Avolut)

---

Selamat siang Pak/Bu,

Saya Mario (mahasiswa ITS yang sedang mengerjakan Tugas Akhir Sistem Rekonsiliasi — SIREKON). Terima kasih atas kerjasamanya selama ini, data-data yang sudah diberikan sangat membantu progress project kami.

Saat ini progress modul Knowledge Base (bagian saya) sudah berjalan cukup baik, namun ada **2 hal** yang masih saya butuhkan dari pihak mitra agar sistem bisa berjalan lebih optimal dan lengkap:

---

## 1. Penambahan Kode Akun (CoA) untuk 5 Kategori Transaksi

Setelah saya analisis data mutasi BCA 2023 dan mencocokkannya dengan **Chart of Accounts (CoA) yang sudah diberikan** (313 kode akun), ternyata ada **5 jenis transaksi** yang rutin muncul di mutasi bank namun **belum ada kode akun yang sesuai di CoA**:

| No | Jenis Transaksi | Contoh di Mutasi BCA | Status di CoA Saat Ini |
|----|---|---|---|
| 1 | **Biaya Admin Bank** (admin bulanan, biaya transfer, SKN/RTGS) | "BIAYA ADM", "BIAYA TRANSFER" | Tidak ada akun biaya bank |
| 2 | **Biaya Tolakan** (retur/gagal transfer) | Transaksi tolakan/pengembalian | Tidak ada akun tolakan |
| 3 | **Bunga Bank / Jasa Giro** (pendapatan bunga) | "BUNGA", "JASA GIRO", "CR BUNGA" | Tidak ada akun pendapatan bunga (Revenue hanya untuk produk di 4.1.01.xx) |
| 4 | **Setoran Pajak** (PPh/PPN ke negara) | "BYR VIA E-BANKING PENERIMAAN NEGARA" | Ada Prepaid Tax (1.1.08.xx) dan Withholding Tax (2.1.04.xx), tapi itu untuk pajak yang dipotong/diterima, bukan yang disetor ke negara |
| 5 | **BPJS** (TK & Kesehatan) | "TRSF E-BANKING 89000/BPJS TK" | Tidak ada akun spesifik BPJS. Apakah bisa masuk ke Employee Benefit (6.2.02.01)? |

**Yang saya butuhkan:**
Mohon konfirmasi untuk masing-masing kategori di atas:
- Apakah perlu **dibuatkan kode akun baru** di CoA? Jika iya, kode dan nama akunnya apa?
- Atau bisa **dimasukkan ke akun yang sudah ada**? Jika iya, ke akun mana?

Saya lampirkan **detail lengkap beserta kandidat akun** yang mungkin cocok sebagai bahan pertimbangan.

---

## 2. Akses Data ERP (API atau Export Data)

Modul KB saya sudah menyiapkan koneksi ke sistem ERP perusahaan, sehingga sistem bisa mencocokkan transaksi bank dengan data vendor/customer dan invoice secara otomatis. Saat ini masih menggunakan **data dummy** karena belum ada akses ke data ERP asli.

Data yang dibutuhkan sistem:

| No | Data | Fungsi di Sistem |
|----|------|-----------------|
| 1 | **Daftar Vendor & Customer** terdaftar | Mencocokkan nama di mutasi bank dengan rekanan resmi perusahaan |
| 2 | **Daftar Invoice Outstanding** (belum lunas) | Rekonsiliasi otomatis: mencocokkan nominal mutasi dengan tagihan terbuka |
| 3 | **CoA terbaru** (jika ada update setelah file yang sudah diberikan) | Memastikan mapping kode akun selalu up-to-date |

**Yang saya butuhkan:**
- **Base URL** API ERP (misal: `https://api.avolut.com/v1` atau URL sandbox/testing)
- **API Key / Token** otentikasi untuk akses
- Saya lampirkan spesifikasi endpoint yang dibutuhkan sistem beserta contoh format response-nya

---

Kedua hal ini sangat penting agar:
1. Transaksi pajak, BPJS, biaya bank, dan bunga bank tidak lagi perlu ditangani manual (saat ini sistem menandai "Perlu Review" karena belum ada kode akun)
2. Pencocokan vendor/customer dan invoice bisa menggunakan data asli dari API ERP, bukan dummy

Mohon arahannya, terima kasih banyak 🙏

Salam,
**Muhammad Ridho Utomo**
NRP 5026231143 — Teknik Informatika ITS
