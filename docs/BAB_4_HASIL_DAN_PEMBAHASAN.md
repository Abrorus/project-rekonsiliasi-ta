# BAB 4 — HASIL DAN PEMBAHASAN

Bab ini memaparkan hasil implementasi dan evaluasi modul Knowledge Base (Pool 3) pada sistem rekonsiliasi keuangan cerdas SIREKON. Pembahasan difokuskan pada implementasi struktur knowledge base berbasis tree dan mapping layer pada basis data relasional, mesin inferensi forward chaining empat tahap, integrasi dengan modul NLP (Pool 2) sebagai sumber input, mekanisme feedback loop untuk pembelajaran otomatis, implementasi suggestion system pada aplikasi web, serta evaluasi kinerja end-to-end menggunakan data transaksi riil.

---

## 4.1 Gambaran Umum Implementasi Knowledge Base

Modul Knowledge Base (Pool 3) merupakan komponen akhir pada pipeline rekonsiliasi SIREKON yang bertugas memvalidasi, memperkaya, dan menyelesaikan klasifikasi transaksi keuangan sebelum dicocokkan ke sistem ERP mitra. Dalam arsitektur tiga pool, KB menerima **seluruh output** dari modul NLP (Pool 2), termasuk transaksi yang sudah berkonfiden tinggi maupun yang ambigu.

Arsitektur pipeline SIREKON terdiri dari tiga modul yang bekerja secara sekuensial:

1. **Pool 1 (Table Recognition):** Mengekstrak data transaksi dari dokumen rekening koran PDF menjadi format terstruktur JSON (dikembangkan oleh Arya Putra).
2. **Pool 2 (Natural Language Processing):** Mengklasifikasikan keterangan transaksi ke sub-kategori Chart of Accounts (CoA) menggunakan model SVM terkalibrasi, menghasilkan label beserta confidence score (dikembangkan oleh Abrorus Sholeh).
3. **Pool 3 (Knowledge Base):** Menerima seluruh output NLP, memvalidasi menggunakan pengetahuan domain terstruktur melalui mekanisme forward chaining, mencocokkan dengan data vendor dan customer mitra serta faktur ERP melalui REST API client, dan menyediakan antarmuka interaktif untuk konfirmasi manual dan feedback loop.

Modul KB diimplementasikan menggunakan:
- **Backend:** FastAPI (Python) untuk REST API
- **Basis Data:** PostgreSQL via Supabase Cloud dengan skema multitenant
- **KB Engine:** Kelas `KBEngine` pada `kb_engine.py` dengan mekanisme cache dan fallback
- **Frontend:** React + TypeScript + Tailwind CSS untuk antarmuka suggestion system
- **Adapter ERP:** `PerusahaanAPIClient` pada `api_client.py` (Adapter Pattern) untuk integrasi faktur

---

## 4.2 Implementasi Struktur Knowledge Base

Berikut adalah implementasi yang diterapkan pada struktur Knowledge Base.

### 4.2.1 Akuisisi Pengetahuan

Proses akuisisi pengetahuan untuk mengisi knowledge base dilakukan melalui beberapa sumber:

1. **Dokumen Chart of Accounts (CoA) Mitra:** Struktur hierarki kategori transaksi beserta kode akun ERP diperoleh dari dokumen CoA resmi perusahaan mitra. Dokumen ini memuat **313 kode akun** (87 parent, 226 detail) yang mencakup lima tipe akun: Asset, Liability, Owner's Equity, Revenue, dan Expense. Dari keseluruhan kode akun tersebut, **10 kode akun** yang paling sering muncul pada transaksi rekening koran telah dipetakan ke dalam Tree Kategori pada knowledge base. Dokumen CoA ini menjadi acuan utama pembangunan Tree Kategori.
2. **Data Transaksi Riil:** Rekening koran BCA periode Juli–Desember 2023 dari perusahaan mitra diperoleh dalam format file PDF. File-file PDF ini dianalisis untuk mengidentifikasi pola keterangan transaksi, daftar vendor/customer yang bertransaksi, serta format penulisan khas bank BCA. Hasil analisis ini menjadi dasar pengisian Tree Pola dan Tree Perusahaan.
3. **Konsultasi dengan Staf Keuangan:** Aturan bisnis seperti prioritas pencocokan entitas (internal → customer → vendor), pemetaan default CR/DB, serta kategori yang memerlukan review manual diperoleh melalui diskusi dengan staf keuangan mitra.
4. **Faktur dan Data ERP:** Daftar invoice beserta status pembayaran diperoleh dari sistem ERP mitra untuk mengisi Tree Invoice. Saat ini data faktur masih berupa mock data karena API sandbox ERP belum tersedia.

Seluruh pengetahuan yang diperoleh kemudian distrukturkan ke dalam empat tree utama dan mapping layer pada basis data relasional.

### 4.2.2 Skema Basis Data Relasional

Pengetahuan yang telah diperoleh diimplementasikan pada basis data PostgreSQL (Supabase Cloud) sesuai perancangan pada Bab 3. Seluruh tabel dilengkapi kolom `client_id` dan Row-Level Security (RLS) untuk mengisolasi data antar klien secara otomatis, mendukung arsitektur multitenant.

**Tabel 4.1 — Struktur Tabel Basis Data Knowledge Base**

| No | Nama Tabel | Fungsi | Jumlah Record |
|----|-----------|--------|---------------|
| 1 | `tree_nodes` | Menyimpan seluruh node dari 4 tree secara self-referencing (`parent_id`) dengan `tree_type`, `level`, `is_leaf`, dan `metadata` (JSONB) | 134 baris |
| 2 | `mapping_layer` | Relasi cross-domain antar tree, dilengkapi `jumlah_konfirmasi_benar`, `total_kemunculan`, dan `confidence` (Persamaan 2.2) | 15 baris |
| 3 | `account_mapping` | Pemetaan kode transaksi bank ke kode akun ERP mitra | — |
| 4 | `transaksi` | Riwayat seluruh transaksi yang diproses, divalidasi, dan dicocokkan sistem | 97+ baris |
| 5 | `feedback_log` | Jejak audit setiap konfirmasi, penolakan, dan input manual pengguna | — |

Tabel `tree_nodes` menggunakan pendekatan self-referencing di mana setiap node memiliki kolom `parent_id` yang merujuk ke `id` pada tabel yang sama. Kolom `tree_type` membedakan node berdasarkan domain tree-nya (`kategori`, `perusahaan`, `invoice`, `pola`). Kolom `metadata` bertipe JSONB menyimpan informasi kontekstual per jenis node: keyword pattern untuk node pola, kode akun ERP dan jenis transaksi (CR/DB) untuk node kategori, serta tipe entitas (`vendor`, `customer`, `internal`) untuk node perusahaan. Kolom `is_leaf` menandai leaf node yang menyimpan informasi paling spesifik.

Tabel `mapping_layer` menghubungkan dua node dari tree yang berbeda melalui pasangan `source_node_id` dan `target_node_id` beserta `relation_type` (misalnya `pola_ke_kategori`). Setiap relasi dilengkapi kolom `jumlah_konfirmasi_benar`, `total_kemunculan`, dan `confidence` yang merupakan implementasi langsung dari formula frequency-based confidence pada Persamaan 2.2. Nilai confidence diperbarui secara otomatis melalui mekanisme feedback loop.

### 4.2.3 Implementasi Empat Tree Utama

Sesuai perancangan pada Bab 3 Sub Bab 3.2.4, empat tree utama telah diimplementasikan dan diisi dengan data dari perusahaan mitra:

**a) Tree Hierarki Kategori Transaksi**

Tree ini menyimpan klasifikasi transaksi dari root (Expense / Income) hingga leaf node paling spesifik. Implementasi hierarki:

```
Root: Expense
├── Biaya Operasional
│   ├── Biaya Utilitas
│   │   ├── PLN / Listrik  (kode_akun: 6.2.05.01)
│   │   ├── PDAM / Air     (kode_akun: 6.2.05.02)
│   │   └── Internet       (kode_akun: 6.2.05.03)
│   ├── Biaya Transportasi / BBM  (kode_akun: 6.2.06.01)
│   ├── Biaya Administrasi Bank   (kode_akun: PERLU_REVIEW)
│   └── Biaya Sewa Gedung/Kantor  (kode_akun: 6.2.10.01)
├── Biaya Tenaga Kerja
│   ├── Gaji Karyawan             (kode_akun: 6.2.01.01)
│   └── BPJS Ketenagakerjaan      (kode_akun: PERLU_REVIEW)
├── Pembayaran Vendor/Supplier    (kode_akun: 2.1.01.01)
├── Pembayaran Pajak/Setoran Negara (kode_akun: PERLU_REVIEW)
└── Transfer Antar Bank — Keluar  (kode_akun: 1.1.02.98)

Root: Income
├── Pembayaran dari Customer      (kode_akun: 1.1.04.01)
├── Transfer Antar Bank — Masuk   (kode_akun: 1.1.02.98)
└── Setoran Tunai                 (kode_akun: 1.1.1.01)
```

Setiap leaf node dilengkapi metadata berisi kode akun CoA yang sesuai dengan sistem ERP mitra. Kode CoA menggunakan pemisah titik (misalnya `6.2.05.01` untuk Utilities — Electricity/PLN). Untuk beberapa kategori yang memerlukan verifikasi konteks lebih lanjut (seperti Biaya Admin Bank dan Pajak), kode akun ditetapkan `PERLU_REVIEW` agar tetap ditampilkan sebagai suggestion pada antarmuka.

**b) Tree Hierarki Perusahaan**

Tree ini menyimpan daftar vendor, customer, dan entitas internal perusahaan mitra yang terdiri dari tiga tipe:
- **Vendor** (pemasok): PT Ciomas Adisatwa, CV Amertha Jaya, PT Bareka Lintas Indo, Sentot Prabowo, I Wayan Suweden, Rakhmad Wahyu, Haryanto, dan lainnya.
- **Customer** (pelanggan): PT Panca Bersaudara, NI Luh Wirantini, NI Ketut Mahayani, Heydee Margareth, dan lainnya.
- **Entitas Internal** (rekening perusahaan sendiri): PT Darbe Jaya Abadi, Darbe Inti Nusantara.

Setiap node pada tree perusahaan memiliki metadata berupa `tipe` (vendor/customer/internal) dan `kode_akun` default. Tree ini digunakan oleh mesin inferensi pada Tahap 2 (Resolusi Rekanan) untuk mencocokkan nama pihak ketiga yang diekstrak dari keterangan transaksi.

**c) Tree Hierarki Invoice**

Tree ini menyimpan relasi antara invoice induk dengan installment-nya, memungkinkan sistem mencocokkan pembayaran terhadap invoice yang belum lunas (open invoice). Implementasi saat ini menggunakan mock data faktur melalui Adapter Pattern (`PerusahaanAPIClient` pada `api_client.py`) karena API sandbox ERP mitra belum tersedia. Mock faktur yang terdaftar mencakup: INV-2023-001 (Ciomas Adisatwa), INV-2023-002 (Amertha Jaya), INV-2023-003 (Bareka Lintas Indo), dan INV-2023-004 (Panca Bersaudara).

**d) Tree Hierarki Pola Singkatan**

Tree ini menyimpan pola keterangan transaksi per bank beserta keyword-keyword penanda. Setiap pola group node (level 1) memiliki metadata berisi daftar keyword yang digunakan pada Tahap 1 forward chaining:

**Tabel 4.2 — Daftar Pola Keyword pada Tree Pola**

| Pola | Keywords | Target Kategori |
|------|----------|-----------------|
| PLN/Listrik | `pln`, `listrik`, `token` | Biaya Utilitas — Electricity |
| BBM/Bensin | `bensin`, `bbm`, `pertamina`, `shell`, `spbu` | Biaya Transportasi |
| Gaji/Payroll | `gaji`, `salary`, `payroll`, `thr` | Biaya Tenaga Kerja |
| BPJS | `bpjs`, `jamsostek`, `kesehat` | BPJS Ketenagakerjaan |
| Pajak/Penerimaan Negara | `pajak`, `ppn`, `pph`, `mpn`, `penerimaan negara` | Pembayaran Pajak |
| Admin Bank | `biaya adm`, `admin`, `sa saldo`, `biaya transfer` | Biaya Admin Bank |
| Bunga Bank | `bunga`, `interest` | Bunga Bank |
| Setoran Tunai | `setoran tunai` | Setoran Tunai |
| Switching/Transfer | `switching`, `transfer ke`, `transfer dr` | Transfer Antar Bank |
| Biaya Tolakan | `tolakan`, `nd-biaya` | Biaya Penolakan |
| Sewa Gedung | `sewa gedung`, `sewa kantor`, `sewa ruko` | Biaya Sewa |

Pencocokan keyword menggunakan regex quasi-word-boundary (`(?<![a-z0-9])keyword(?![a-z0-9])`) untuk menghindari false positive dari substring, misalnya keyword `pln` tidak akan cocok dengan kata `berpulang`.

---

## 4.3 Arsitektur Perangkat Lunak KB Engine

Berikut adalah arsitektur perangkat lunak yang diterapkan pada mesin inferensi Knowledge Base, mencakup desain kelas utama, strategi pemuatan data dan cache, serta mekanisme fallback untuk menjamin ketersediaan sistem.

### 4.3.1 Kelas KBEngine dan Mekanisme Cache

Mesin inferensi diimplementasikan dalam kelas `KBEngine` pada `kb_engine.py`. Arsitektur engine mengikuti pola singleton di mana hanya satu instance yang aktif sepanjang siklus hidup aplikasi.

Pada saat inisialisasi, engine menerima Supabase client dan `client_id` untuk multitenant. Metode `_load_all()` memuat seluruh data dari tiga tabel Supabase (`tree_nodes`, `mapping_layer`, `account_mapping`) dalam satu siklus pemuatan, kemudian menyimpannya dalam cache internal. Cache memiliki TTL (Time-To-Live) selama **5 menit** (300 detik), sehingga perubahan pada basis data (misalnya penambahan vendor baru atau pembaruan confidence mapping) akan tercermin dalam waktu maksimal 5 menit tanpa perlu restart server.

Data yang di-cache meliputi:
- `pola_rules`: Daftar aturan pencocokan pola beserta target kategori dan confidence
- `kategori_lookup`: Indeks node kategori berdasarkan ID
- `perusahaan`: Daftar vendor, customer, dan entitas internal yang terindeks
- `account_mapping`: Pemetaan kode transaksi bank ke kode akun ERP

### 4.3.2 Mekanisme Fallback

Apabila koneksi ke Supabase gagal (timeout, network error, atau maintenance), engine melakukan fallback ke fungsi `_klasifikasi_hardcoded()` yang membaca dari dictionary Python statis (`decision_tree_kb.py`). Fallback terjadi pada dua level:
1. **Level `_load_all()`:** Jika pemuatan data gagal, engine menggunakan data hardcoded untuk klasifikasi.
2. **Level `klasifikasi_kb_db()`:** Jika inisialisasi engine gagal (misalnya modul database belum terpasang), fungsi langsung menggunakan fallback hardcoded.

Mekanisme fallback ganda ini memastikan bahwa sistem tetap beroperasi (graceful degradation) meskipun koneksi database terputus.

---

## 4.4 Mesin Inferensi Forward Chaining 4 Tahap

Implementasi forward chaining mengikuti hierarki 4 tahap sesuai perancangan pada Bab 3 Sub Bab 3.2.5. Setiap transaksi yang masuk diproses melalui tahapan secara berurutan (data-driven): apabila suatu tahap berhasil menyelesaikan transaksi, tahap berikutnya dilewati.

### 4.4.1 Tahap 1 — Aturan Deterministik KB Tree (Pencocokan Pola)

Sistem mencocokkan keterangan transaksi terhadap seluruh keyword pattern yang dimuat dari Tree Pola di Supabase. Pencocokan dilakukan pada teks asli (sebelum preprocessing NLP) **dan** teks bersih (hasil normalisasi NLP, jika confidence tinggi), sehingga pola yang mungkin terubah oleh preprocessing tetap terdeteksi.

Apabila keyword ditemukan, engine:
1. Membaca `target_node_id` dari mapping layer (relasi `pola_ke_kategori`)
2. Menelusuri (traverse) node pada Tree Kategori untuk memperoleh konteks hierarki
3. Mengambil `kode_akun` dari metadata leaf node via `_resolve_kode_akun()`
4. Untuk pola Switching/Transfer, menerapkan context rule berdasarkan jenis transaksi (CR → Transfer Masuk, DB → Transfer Keluar) melalui `_resolve_switching()`

Status hasil: **KB_TEREALISASI**.

### 4.4.2 Tahap 2 — Resolusi Rekanan Mitra dan Pencocokan Faktur ERP

Apabila Tahap 1 tidak menemukan pola deterministik, sistem melanjutkan ke resolusi rekanan. Proses ini terdiri dari dua komponen:

**a) Ekstraksi dan Pencocokan Nama Rekanan**

Nama pihak ketiga diekstrak dari keterangan transaksi menggunakan fungsi `ekstrak_nama_rekanan()` pada `rekanan_resolver.py`. Fungsi ini menghilangkan prefix bank (`TRSF E-BANKING`, `BYR VIA E-BANKING`, `SWITCHING TRANSFER`, `BI-FAST BIF`, dll.), noise words, serta kode referensi. Nama yang diekstrak dicocokkan terhadap data pada Tree Perusahaan dengan urutan prioritas:

1. **Entitas Internal** → kode akun Cross Account Bank (`1.1.02.98`)
2. **Customer** → kode akun Piutang Usaha (`1.1.04.01`) untuk CR, Utang Usaha (`2.1.01.01`) untuk DB
3. **Vendor** → kode akun Utang Usaha (`2.1.01.01`)
4. **Default CR/DB** (jika ada jalur transfer tetapi nama tidak terdaftar) → CR: Customer (`1.1.04.01`), DB: Vendor (`2.1.01.01`)

**b) Pencocokan Faktur ERP**

Secara paralel, engine memanggil `erp_client.match_invoice()` melalui `PerusahaanAPIClient` (Adapter Pattern) berbasis REST API untuk mencocokkan pembayaran terhadap faktur yang belum lunas. Kriteria pencocokan meliputi nama vendor/customer dan/atau nominal mutasi. Apabila faktur ditemukan, informasi (nomor invoice, status lunas, nominal) ditambahkan ke hasil klasifikasi.

Saat ini endpoint menggunakan mock data (data faktur dummy) karena API sandbox ERP mitra belum tersedia. Arsitektur Adapter Pattern memungkinkan pergantian dari mock data ke REST API ERP riil hanya dengan mengubah konfigurasi `PERUSAHAAN_USE_MOCK=false` pada file `.env`, tanpa perubahan kode aplikasi.

Status hasil: **KB_TEREALISASI** (dengan atau tanpa informasi faktur).

### 4.4.3 Tahap 3 — Validasi NLP Confident

Untuk transaksi yang tidak terselesaikan pada Tahap 1 dan 2, sistem memanfaatkan output dari modul NLP. Apabila confidence score NLP ≥ threshold (τ = 0,72), engine:
1. Membaca label kategori NLP (misalnya `SALARY`, `PAYABLE_VENDOR`, `UTILITIES`)
2. Memetakan label tersebut ke kode akun CoA melalui `_resolve_nlp_kategori()`, yang mencari secara berurutan di: `MAPPING_LABEL_NLP_KE_COA` (mapping statis) → Tree Kategori di Supabase → Account Mapping → konversi hardcoded fallback

Status hasil: **NLP_VALIDATED**.

### 4.4.4 Tahap 4 — Ambigu / Anomali → Manual Review

Transaksi yang tidak berhasil diselesaikan pada ketiga tahap sebelumnya — confidence NLP di bawah threshold, tidak ditemukan pola deterministik, dan nama rekanan tidak dikenali — dialihkan ke status **MANUAL_REVIEW** dengan kode akun `UNKNOWN`. Pengguna diarahkan untuk melakukan pemetaan secara manual melalui antarmuka suggestion system.

### 4.4.5 Contoh Alur Inferensi

**Contoh 1 — Tahap 1 (Pola Deterministik):**

Keterangan: `"BYR VIA E-BANKING 0860 PLN JATIM DARBE JAYA ABADI P"`, jenis DB, mutasi Rp 1.694.321
- Tahap 1: Keyword `pln` ditemukan → mapping ke Tree Kategori: PLN → Biaya Utilitas → Biaya Operasional → Expense → kode akun `6.2.05.01`
- Hasil: `KB_TEREALISASI`, `6.2.05.01`, metode `KB Engine (Pola PLN/Listrik)`

**Contoh 2 — Tahap 2 (Resolusi Rekanan + Faktur):**

Keterangan: `"TRSF E-BANKING CIOMAS ADISATWA"`, jenis DB, mutasi Rp 580.075.045
- Tahap 1: Tidak ada pola deterministik cocok
- Tahap 2: Nama "CIOMAS ADISATWA" diekstrak → ditemukan di Tree Perusahaan sebagai vendor → kode akun `2.1.01.01`. Invoice matching: INV-2023-001 cocok (Rp 580.075.045, Lunas)
- Hasil: `KB_TEREALISASI`, `2.1.01.01`, metode `KB Engine (Master Vendor DB: CIOMAS ADISATWA) + Faktur ERP (INV-2023-001 Lunas)`

**Contoh 3 — Tahap 2 (Default CR → Customer):**

Keterangan: `"TRSF E-BANKING BERKAH MITRA"`, jenis CR
- Tahap 1: Tidak ada pola deterministik
- Tahap 2: Nama "BERKAH MITRA" diekstrak → tidak ada di vendor/customer/internal database, tetapi ada jalur transfer → default CR: Customer
- Hasil: `KB_TEREALISASI`, `1.1.04.01`, metode `KB Engine (Aturan Bisnis CR -> Customer)`

**Contoh 4 — Tahap 4 (Manual Review):**

Keterangan: `"TRSF E-BANKING"`, jenis DB (tanpa nama pihak)
- Tahap 1–3: Tidak ada pola, nama rekanan kosong, tidak ada output NLP yang memadai
- Tahap 4: `MANUAL_REVIEW`
- Hasil: `UNKNOWN`, metode `Manual Review (Akuntan)`

---

## 4.5 Integrasi dengan Modul NLP (Pool 2)

Berikut adalah mekanisme integrasi antara modul NLP (Pool 2) sebagai sumber input dengan Knowledge Base (Pool 3) sebagai pengambil keputusan akhir klasifikasi.

### 4.5.1 Pipeline Integrasi dan Routing

Integrasi antara modul NLP dan Knowledge Base diimplementasikan dalam `routing.py`. Alur routing:

1. **NLP memproses teks:** Normalisasi → TF-IDF → SVM terkalibrasi → confidence score + label CoA
2. **Seluruh output NLP masuk ke KB**, tanpa kecuali — KB menerima baik transaksi berkonfiden tinggi maupun rendah
3. **KB Engine menjalankan forward chaining 4 tahap**, menggunakan info confidence NLP sebagai salah satu fakta:
   - Confidence ≥ 0,72: teks sudah bersih (digunakan juga pada pencocokan pola), KB memvalidasi dan mencocokkan ke data ERP (Tahap 1–2), atau mempercayai label NLP (Tahap 3)
   - Confidence < 0,72: teks masih ambigu, KB menganalisis menggunakan aturan/tree sendiri (Tahap 1–2), jika gagal → Manual Review (Tahap 4)

Semua keputusan akhir ditetapkan oleh KB Engine, bukan oleh NLP. NLP berperan sebagai salah satu sumber fakta, bukan pengambil keputusan.

### 4.5.2 Penentuan Status UI

Setelah KB Engine mengembalikan hasil, routing menentukan status UI berdasarkan kombinasi confidence NLP dan keberhasilan KB:

| Confidence NLP | KB Berhasil? | Status UI | Keterangan |
|---------------|-------------|-----------|------------|
| ≥ 0,72 | Ya | **AUTO_MATCH** (hijau) | Rekomendasi otomatis, tidak perlu verifikasi |
| < 0,72 | Ya | **SUGGESTION** (kuning) | Rekomendasi dari aturan KB, perlu verifikasi pengguna |
| Any | Tidak | **NOT_FOUND** (merah) | Perlu input manual pengguna |

### 4.5.3 Penentuan Pool

Routing juga menentukan pool asal transaksi:
Routing juga menentukan jalur penyelesaian transaksi untuk keperluan pelacakan dan evaluasi kinerja masing-masing modul:

- **Jalur Otomatis (NLP + KB Validated):** Confidence NLP ≥ 0,72 DAN status KB bukan MANUAL_REVIEW. Transaksi pada jalur ini telah diklasifikasikan oleh NLP dengan keyakinan tinggi dan divalidasi oleh KB, sehingga berstatus AUTO_MATCH.
- **Jalur KB (Knowledge Base):** Semua transaksi lainnya — confidence NLP < 0,72, atau yang diselesaikan murni oleh aturan KB (pencocokan pola, resolusi vendor/customer, atau pencocokan faktur ERP). Transaksi pada jalur ini berstatus SUGGESTION atau NOT_FOUND.

Pada evaluasi 337 transaksi BCA, 308 transaksi (91,4%) masuk Jalur Otomatis dan 29 transaksi (8,6%) masuk Jalur KB, menunjukkan bahwa mayoritas transaksi dapat diselesaikan secara otomatis.

---

## 4.6 Implementasi Feedback Loop

### 4.6.1 Mekanisme Konfirmasi dan Penolakan

Feedback loop diimplementasikan melalui dua endpoint REST API pada backend FastAPI:
- `POST /api/transaksi/{id}/konfirmasi` — mengonfirmasi rekomendasi KB sebagai benar
- `POST /api/transaksi/{id}/tolak` — menolak rekomendasi dan memasukkan kode akun yang benar

Setiap aksi dicatat pada tabel `feedback_log` sebagai audit trail, mencakup `transaksi_id`, `mapping_id`, `aksi` (konfirmasi/tolak/manual_input), `kode_akun_lama`, `kode_akun_baru`, dan `catatan`. Status transaksi pada tabel `transaksi` diperbarui menjadi `confirmed` atau `rejected`.

### 4.6.2 Pembaruan Frequency-Based Confidence

Sesuai formula pada Persamaan 2.2, setiap konfirmasi atau penolakan memperbarui nilai confidence pada mapping layer:

$$\text{Confidence}(r) = \frac{\text{Jumlah Konfirmasi Benar}}{\text{Total Kemunculan}}$$

- **Konfirmasi benar:** `jumlah_konfirmasi_benar` +1, `total_kemunculan` +1 → confidence **naik**
- **Penolakan:** hanya `total_kemunculan` +1 → confidence **turun** secara otomatis

Setelah confidence mapping diperbarui, cache KB Engine akan di-invalidasi pada siklus berikutnya (maksimal 5 menit), sehingga aturan forward chaining pada Tahap 1 sudah menggunakan confidence terbaru.

### 4.6.3 Simulasi Pertumbuhan Confidence

Untuk membuktikan bahwa feedback loop membuat sistem semakin akurat seiring penggunaan, dilakukan simulasi pada dua skenario:

**Skenario 1 — Relasi Baru yang Dikonfirmasi Berulang:**

Sebuah relasi mapping baru (misalnya pola "TOKPED" → "Penerimaan E-Commerce") dimulai dengan confidence awal 0,50 (1 konfirmasi dari 2 kemunculan):

| Iterasi | Konfirmasi Benar | Total Kemunculan | Confidence | Status |
|---------|-----------------|-----------------|------------|--------|
| Awal | 1 | 2 | 0,50 | Suggestion |
| Ke-1 | 2 | 3 | 0,67 | Suggestion |
| Ke-2 | 3 | 4 | **0,75** | **Auto Match** (≥ 0,72) |
| Ke-3 | 4 | 5 | 0,80 | Auto Match |

Pada iterasi ke-2, confidence melewati threshold 0,72 sehingga relasi tersebut otomatis dipromosikan dari Suggestion menjadi Auto Match — pengguna tidak perlu lagi mengonfirmasi transaksi serupa di periode berikutnya.

**Skenario 2 — Relasi Salah yang Ditolak Berulang:**

Sebuah relasi mapping dengan confidence awal 0,80 (4 konfirmasi dari 5 kemunculan) ditolak 2 kali:

| Iterasi | Konfirmasi Benar | Total Kemunculan | Confidence | Status |
|---------|-----------------|-----------------|------------|--------|
| Awal | 4 | 5 | 0,80 | Auto Match |
| Tolak-1 | 4 | 6 | 0,67 | Suggestion |
| Tolak-2 | 4 | 7 | 0,57 | Suggestion |

Setelah 2 penolakan, confidence turun dari 0,80 ke 0,57 (di bawah threshold 0,72), sehingga sistem tidak lagi menampilkannya sebagai Auto Match melainkan sebagai Suggestion yang memerlukan verifikasi manual. Mekanisme ini memastikan bahwa aturan yang salah terdegradasi secara otomatis tanpa intervensi pengembang.

---

## 4.7 Implementasi Suggestion System dan Aplikasi Web

### 4.7.1 Arsitektur Aplikasi

Aplikasi web diimplementasikan dengan arsitektur:
- **Backend:** FastAPI (Python) menyediakan endpoint REST API: `/api/rekonsiliasi` (pipeline penuh), `/api/demo-data` (data demo), `/api/transaksi` (CRUD), `/api/transaksi/{id}/konfirmasi`, `/api/transaksi/{id}/tolak`, `/api/stats` (statistik live), serta `/api/tree` (eksplorasi tree).
- **Frontend:** React + TypeScript + Tailwind CSS dengan client-side routing (React Router). Tiga rute utama: `/` (upload), `/proses` (pemrosesan), `/hasil` (hasil interaktif).
- **Database:** PostgreSQL via Supabase Cloud, seluruh query multitenant (`client_id`) dengan RLS.

### 4.7.2 Antarmuka Halaman Hasil

Halaman hasil (`/hasil`) menampilkan tabel interaktif dengan informasi per transaksi:
- Tanggal, keterangan, jenis mutasi (DB/CR), dan nominal
- Kode akun CoA yang direkomendasikan beserta nama akun
- Status pemetaan: **Auto Match** (badge hijau), **Suggestion** (badge kuning), atau **Not Found** (badge merah)
- Metode inferensi yang menjelaskan jalur forward chaining yang digunakan (misalnya "KB Engine (Master Vendor DB: CIOMAS ADISATWA) + Faktur ERP")
- Informasi faktur ERP (jika ada): badge hijau dengan nomor invoice dan status
- Tombol aksi: Konfirmasi (✓) dan Tolak/Koreksi (✎) untuk setiap baris

### 4.7.3 Modal Konfirmasi, Penolakan, dan CoA Picker

Dialog konfirmasi menampilkan detail transaksi dan menyediakan field opsional untuk catatan. Dialog penolakan menyediakan field wajib untuk kode akun baru (dengan CoA Picker Modal yang menampilkan seluruh hierarki kode akun) serta catatan, agar input pengguna dapat digunakan sebagai bahan pembelajaran feedback loop.

Statistik live ditampilkan pada bagian atas halaman: jumlah Auto Match, Suggestion, Not Found, Dikonfirmasi, Ditolak, serta persentase Coverage keseluruhan sesuai Persamaan 2.4.

---

## 4.8 Evaluasi Kinerja Sistem

### 4.8.1 Dataset dan Metodologi Evaluasi

Evaluasi dilakukan menggunakan dataset transaksi riil BCA tahun 2023 dari perusahaan mitra (337 transaksi). Untuk menghindari data leakage, dataset dibagi:
- **Data latih ML:** 198 transaksi yang digunakan melatih model NLP (dieksklusikan dari metrik utama)
- **Data uji:** 139 transaksi yang belum pernah dilihat model NLP

Evaluasi bersifat end-to-end: mengukur kinerja keseluruhan pipeline dari input transaksi (keterangan, jenis, mutasi) hingga output kode akun CoA yang dihasilkan oleh KB Engine. Ground truth berupa kode akun yang ditetapkan berdasarkan kategorisasi perusahaan mitra.

### 4.8.2 Hasil Evaluasi pada Data Uji (Metrik Utama)

**Tabel 4.3 — Ringkasan Hasil Evaluasi pada Data Uji (139 Transaksi)**

| Metrik | Nilai |
|--------|-------|
| **Total Transaksi** | 139 |
| Klasifikasi TEPAT | 134 (96,4%) |
| Klasifikasi SALAH | 5 (3,6%) |
| Manual Review | 0 (0,0%) |
| **Tingkat Otomasi (Coverage)** | **100,0%** |
| **Akurasi Keseluruhan** | **96,4%** |

Seluruh 139 transaksi data uji berhasil diselesaikan secara otomatis tanpa memerlukan manual review (coverage 100%). Dari 139 transaksi tersebut, 134 dipetakan ke kode akun yang tepat (akurasi 96,4%). Rincian per jalur:
- **Jalur Otomatis (NLP + KB Validated):** 128 transaksi (92,1%), akurasi 98,4%
- **Jalur KB (diselesaikan aturan KB):** 11 transaksi (7,9%), akurasi 72,7%

### 4.8.3 Hasil Evaluasi pada Seluruh Data BCA (337 Transaksi)

**Tabel 4.4 — Perbandingan Metrik Data Uji vs Seluruh Data**

| Metrik | Data Uji (139) | Seluruh Data (337) |
|--------|---------------|-------------------|
| TEPAT | 134 | 311 |
| SALAH | 5 | 26 |
| Manual Review | 0 | 5 |
| Coverage | 100,0% | 98,5% |
| **Akurasi** | **96,4%** | **92,3%** |
| Jalur Otomatis (NLP + KB Validated) | — | 308 (91,4%) |
| Jalur KB (KB saja) | — | 29 (8,6%) |

Pada seluruh data, 308 transaksi (91,4%) diselesaikan melalui Jalur Otomatis (NLP confident + validasi KB) dengan akurasi 95,8%, sedangkan 29 transaksi (8,6%) masuk Jalur KB — dari jumlah tersebut, 24 transaksi (82,8%) berhasil diselesaikan oleh aturan KB dengan akurasi 66,7%, dan 5 transaksi (1,5%) masuk Manual Review.

### 4.8.4 Metrik Confidence Routing dan Integrasi (558 Transaksi)

Evaluasi integrasi yang lebih luas dilakukan menggunakan `evaluasi_routing_kb.py` terhadap 558 transaksi berlabel (BCA + Mandiri). Transaksi dengan confidence NLP < 0,72 dirujuk ke Jalur KB untuk simulasi resolusi forward-chaining:

**Tabel 4.5 — Metrik Confidence Routing dan Integrasi KB**

| Metrik | Jumlah | Nilai (%) |
| --- | --- | --- |
| **Auto-Classification Rate** (diproses otomatis Jalur Otomatis) | 462 / 558 | **82,80%** |
| **KB Referral Rate** (dirujuk ke Jalur KB) | 96 / 558 | **17,20%** |
| **KB Resolution Rate** (berhasil diselesaikan aturan KB) | 66 / 96 | **68,75%** |
| **Overall System Coverage** (Jalur Otomatis + Jalur KB) | 528 / 558 | **94,62%** |
| Sisa Review Manual | 30 / 558 | 5,38% |
| Akurasi Jalur Otomatis | 462 baris | **99,57%** |
| Akurasi Sistem Hibrida (Jalur Otomatis + Jalur KB) | 528 baris | **98,11%** |
| Macro-F1 Sistem Hibrida | 528 baris | **90,10%** |

Dari 96 transaksi yang dirujuk ke Jalur KB, resolusi dicapai melalui tiga aturan forward-chaining:
- **Referensi Entitas ERP** (nama vendor/customer/entitas terdaftar): 35 transaksi
- **Pencocokan Nominal Invoice/Mutasi Historis**: 20 transaksi
- **Kamus Kata Kunci Operasional KB**: 11 transaksi
- Tidak terselesaikan → konfirmasi manual: 30 transaksi

Overall System Coverage sebesar **94,62%** menunjukkan bahwa hanya 5,38% transaksi yang benar-benar memerlukan konfirmasi manual staf keuangan — pengurangan signifikan dibandingkan proses rekonsiliasi konvensional yang seluruhnya manual.

### 4.8.5 Analisis Kesalahan

Dari 26 kesalahan pada seluruh 337 transaksi BCA, terdapat pola kesalahan yang teridentifikasi:

**Tabel 4.6 — Pola Kesalahan KB Engine**

| Pola Kesalahan | Jumlah | Penjelasan |
| --- | --- | --- |
| Transfer LLG/RTGS/BI-FAST salah dikenali sebagai Switching | 12 | Keterangan mengandung kode bank (`PT. BANK MA`, `PT. BANK OC`, `BI-FAST BIF TRANSFER KE`) yang memicu pola Switching, padahal seharusnya Pembayaran Vendor |
| Entitas perusahaan grup salah dikenali sebagai internal | 4 | Nama seperti "DARBE INTI NUSANTA" dan "ALKAFIE JAYA ABADI" dikenali sebagai entitas internal, padahal konteksnya adalah pembayaran vendor |
| BI-FAST BIAYA TXN salah ke Admin Bank | 3 | Biaya transaksi BI-FAST untuk pembayaran vendor seharusnya tetap masuk kategori Vendor, bukan Admin Bank |
| Keterangan terlalu generik → Manual Review | 5 | Keterangan seperti "TRSF E-BANKING" (tanpa nama), "peng saldo min", "BAYAR JASA TEMPAT 3 KALI" tidak cukup informatif |
| Label/pihak baru belum terdaftar | 2 | Kode akun `6.2.04.01` (biaya pengurusan) dan vendor yang belum ada di tree |

Kesalahan terbanyak (12 dari 26) disebabkan oleh format transfer antar bank (LLG/RTGS/BI-FAST) yang mengandung kode institusi bank sehingga memicu pola Switching. Perbaikan dapat dilakukan dengan menambahkan aturan prioritas yang mengenali format LLG/RTGS/BI-FAST sebagai pembayaran vendor ketika nama pihak ketiga teridentifikasi setelah kode bank.

5 transaksi masuk Manual Review karena keterangan terlalu generik. Kasus ini justru menunjukkan pentingnya feedback loop: setelah pengguna mengonfirmasi pemetaan manual, mapping layer diperbarui dan transaksi serupa di periode berikutnya dapat dikenali otomatis oleh KB.

---

## 4.9 Pembahasan

### 4.9.1 Efektivitas Pendekatan Tree + Mapping Layer

Hasil evaluasi membuktikan bahwa pendekatan representasi tree + mapping layer yang diadopsi dari literatur (Yang et al., 2023) efektif untuk domain rekonsiliasi keuangan:

1. **Interpretability:** Setiap rekomendasi yang dihasilkan dapat ditelusuri jalur inferensinya — dari keyword yang cocok, ke pola yang terdeteksi, ke node kategori target, hingga kode akun CoA final. Informasi metode penyelesaian ditampilkan per transaksi pada antarmuka, memenuhi kebutuhan auditabilitas domain keuangan.
2. **Modularitas:** Penambahan pola transaksi baru (misalnya keyword `sewa gedung` yang ditambahkan pada commit terbaru) dapat dilakukan langsung pada tabel `tree_nodes` tanpa modifikasi kode engine. Demikian pula penambahan vendor/customer baru cukup dilakukan pada tree perusahaan di Supabase.
3. **Skalabilitas:** Struktur multitenant (`client_id` + RLS) memungkinkan knowledge base yang sama digunakan oleh beberapa klien perusahaan dengan data yang terisolasi. Cache TTL 5 menit menjaga performa pada beban transaksi yang tinggi.

### 4.9.2 Komplementaritas KB dengan NLP

KB Engine dan NLP bekerja secara komplementer, bukan substitutif. NLP (Pool 2) mampu menangani 82,8% transaksi secara otomatis dengan akurasi 99,57%, sementara KB berhasil menyelamatkan 68,75% dari 96 transaksi ambigu yang dirujuk. Tanpa KB, seluruh 96 transaksi tersebut akan masuk manual review, menurunkan coverage dari 94,62% menjadi 82,80%.

Peran KB yang paling krusial terlihat pada transaksi yang mengandung nama rekanan: NLP mungkin tidak yakin (confidence < 0,72) karena nama rekanan bersifat unik dan jarang muncul di data latih, tetapi KB dapat langsung mengenali nama tersebut melalui Tree Perusahaan. Demikian pula untuk pola deterministik seperti PLN, BPJS, atau Pajak — KB mengenalinya melalui keyword pattern tanpa bergantung pada model statistik.

### 4.9.3 Validasi Feedback Loop

Simulasi pertumbuhan confidence (Sub Bab 4.6.3) membuktikan bahwa mekanisme feedback loop berfungsi sesuai desain:
- Relasi yang dikonfirmasi berulang naik confidence-nya hingga menjadi Auto Match (≥ 0,72)
- Relasi yang salah turun confidence-nya menjadi Suggestion

Mekanisme ini menjawab permasalahan yang diidentifikasi pada Bab 1, yaitu ketiadaan mekanisme pembelajaran otomatis pada proses rekonsiliasi konvensional. Dengan feedback loop, sistem secara bertahap memperluas cakupan Auto Match dari waktu ke waktu tanpa perlu retraining model ML.

### 4.9.4 Keterbatasan

1. **API Sandbox Mitra:** Integrasi ERP masih menggunakan mock data (Adapter Pattern) karena pihak mitra belum menyediakan endpoint dan API key untuk sandbox. Ketika sandbox tersedia, konfigurasi `PERUSAHAAN_USE_MOCK=false` mengaktifkan koneksi riil tanpa perubahan kode.
2. **Modul Table Recognition (Pool 1):** Masih dalam tahap pengembangan oleh anggota tim lain, sehingga pengujian end-to-end dari PDF belum dapat dilakukan. Evaluasi saat ini menggunakan data yang sudah diekstrak.
3. **Evaluasi satu bank:** Dataset evaluasi end-to-end (337 transaksi) hanya mencakup rekening koran BCA. Evaluasi lintas-bank (BNI, BRI, BSI) untuk modul KB perlu dilakukan setelah data riil tersedia.
4. **Validasi pakar:** Validasi kualitatif oleh staf keuangan perusahaan mitra belum dilaksanakan. Bahan validasi sudah tersedia (`sampel_validasi_20persen.xlsx`), menunggu pengisian oleh validator.
5. **Format LLG/RTGS/BI-FAST:** 12 dari 26 kesalahan disebabkan oleh format transfer antar bank yang belum ditangani secara spesifik pada aturan forward chaining. Perbaikan ini merupakan prioritas pengembangan berikutnya.
6. **Cakupan kode akun:** Knowledge base saat ini meng-cover 10 dari 313 kode akun CoA mitra, difokuskan pada kategori yang paling sering muncul pada rekening koran. Perluasan cakupan kode akun dapat dilakukan secara bertahap melalui feedback loop dan penambahan node pada Tree Kategori di Supabase tanpa modifikasi kode.
7. **Label belum divalidasi:** Label ground truth berasal dari aturan kata kunci yang belum divalidasi staf keuangan. Angka akurasi yang dilaporkan bersifat tentatif sampai validasi Cohen's Kappa dilaksanakan.
