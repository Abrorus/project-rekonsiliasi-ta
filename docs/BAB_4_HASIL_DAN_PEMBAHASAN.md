# BAB 4 — HASIL DAN PEMBAHASAN

Bab ini memaparkan hasil implementasi dan evaluasi modul Knowledge Base (Pool 3) pada sistem rekonsiliasi keuangan SIREKON. Pembahasan mencakup implementasi struktur knowledge base, mekanisme inferensi forward chaining, integrasi dengan modul NLP (Pool 2), implementasi feedback loop, serta evaluasi kinerja sistem secara end-to-end menggunakan data transaksi riil.

---

## 4.1 Implementasi Struktur Knowledge Base

### 4.1.1 Skema Basis Data Relasional

Struktur knowledge base diimplementasikan pada basis data PostgreSQL (Supabase Cloud) dengan skema multitenant sesuai perancangan pada Bab 3. Seluruh tabel dilengkapi kolom `client_id` dan Row-Level Security (RLS) untuk mengisolasi data antar klien secara otomatis. Tabel-tabel utama yang diimplementasikan meliputi:

**Tabel 4.1 — Struktur Tabel Basis Data Knowledge Base**

| No | Nama Tabel | Fungsi | Jumlah Record |
|----|-----------|--------|---------------|
| 1 | `tree_nodes` | Menyimpan seluruh node dari 4 tree (kategori, perusahaan, invoice, pola) secara self-referencing | 134 baris |
| 2 | `mapping_layer` | Menyimpan relasi cross-domain antar tree beserta nilai frequency-based confidence | 15 baris |
| 3 | `account_mapping` | Menyimpan pemetaan kode transaksi bank ke kode akun ERP mitra | — |
| 4 | `transaksi` | Menyimpan riwayat seluruh transaksi yang diproses dan divalidasi sistem | 97+ baris |
| 5 | `feedback_log` | Menyimpan jejak audit setiap konfirmasi, penolakan, dan input manual pengguna | — |

Tabel `tree_nodes` menggunakan pendekatan self-referencing di mana setiap node memiliki kolom `parent_id` yang merujuk ke `id` pada tabel yang sama. Kolom `tree_type` membedakan node berdasarkan domain tree-nya (`kategori`, `perusahaan`, `invoice`, `pola`), sementara kolom `metadata` bertipe JSONB menyimpan informasi tambahan seperti keyword pattern untuk node pola dan kode akun ERP untuk node kategori. Kolom `is_leaf` menandai apakah suatu node merupakan leaf node yang menyimpan informasi paling spesifik.

Tabel `mapping_layer` menghubungkan dua node dari tree yang berbeda melalui pasangan `source_node_id` dan `target_node_id`. Setiap relasi pada mapping layer dilengkapi dengan kolom `jumlah_konfirmasi_benar`, `total_kemunculan`, dan `confidence` yang merupakan implementasi langsung dari formula frequency-based confidence (Persamaan 2.2). Nilai confidence ini diperbarui secara otomatis melalui mekanisme feedback loop setiap kali pengguna mengonfirmasi atau menolak rekomendasi.

### 4.1.2 Implementasi Empat Tree Utama

Sesuai perancangan pada Bab 3 Sub Bab 3.2.4, empat tree utama telah diimplementasikan dan diisi dengan data dari perusahaan mitra:

**a) Tree Hierarki Kategori Transaksi**

Tree ini menyimpan klasifikasi transaksi dari root (Expense / Income) hingga leaf node yang paling spesifik. Contoh hierarki yang diimplementasikan:

```
Root: Expense
├── Biaya Operasional
│   ├── Biaya Utilitas
│   │   ├── PLN (Listrik)
│   │   ├── PDAM (Air)
│   │   └── Internet/Telkom
│   ├── Biaya Transportasi
│   │   └── BBM / Bensin
│   └── Biaya Administrasi Bank
├── Biaya Tenaga Kerja
│   ├── Gaji Karyawan
│   └── BPJS Ketenagakerjaan/Kesehatan
├── Pembayaran Vendor/Supplier
└── Pembayaran Pajak/Setoran Negara

Root: Income
├── Pembayaran dari Customer
├── Transfer Masuk (Switching)
└── Setoran Tunai
```

Setiap leaf node pada tree kategori dilengkapi metadata berisi kode akun CoA (Chart of Accounts) yang sesuai dengan sistem ERP mitra, misalnya PLN dipetakan ke kode akun `6.2.05.01` (Utilities — Electricity).

**b) Tree Hierarki Perusahaan**

Tree ini menyimpan daftar vendor, customer, dan entitas internal perusahaan mitra. Vendor yang diimplementasikan mencakup rekanan riil seperti PT Ciomas Adisatwa, CV Amertha Jaya, PT Panca Bersaudara, serta Sentot Prabowo. Tree ini digunakan oleh mesin inferensi untuk mencocokkan nama pihak ketiga pada keterangan transaksi dengan entitas yang terdaftar.

**c) Tree Hierarki Invoice**

Tree ini menyimpan relasi antara invoice induk dengan installment-nya, memungkinkan sistem mencocokkan pembayaran terhadap invoice yang belum lunas (open invoice). Implementasi saat ini menggunakan mock data faktur (Adapter Pattern) karena API sandbox ERP mitra belum tersedia.

**d) Tree Hierarki Pola Singkatan**

Tree ini menyimpan pola keterangan transaksi per bank beserta keyword-keyword yang menjadi penanda. Contoh pola yang disimpan: keyword `["pln", "listrik", "token"]` pada node pola PLN, keyword `["bpjs", "jamsostek"]` pada node pola BPJS, dan keyword `["bensin", "bbm", "pertamina", "shell", "spbu"]` pada node pola BBM.

---

## 4.2 Implementasi Mesin Inferensi Forward Chaining

### 4.2.1 Arsitektur KB Engine

Mesin inferensi diimplementasikan dalam modul `kb_engine.py` sebagai kelas `KBEngine` yang membaca seluruh struktur tree dan mapping dari Supabase secara dinamis. Engine menggunakan mekanisme cache dengan TTL (Time-To-Live) selama 5 menit untuk menghindari pemanggilan database berulang pada setiap transaksi. Apabila koneksi Supabase gagal, sistem melakukan fallback ke dictionary Python yang di-hardcode sebagai mekanisme keamanan.

Arsitektur engine mengikuti pola singleton di mana hanya satu instance `KBEngine` yang aktif sepanjang siklus hidup aplikasi, sehingga cache dapat dimanfaatkan secara optimal. Fungsi `klasifikasi_kb_db()` bertindak sebagai drop-in replacement untuk fungsi hardcoded sebelumnya, memastikan kompatibilitas dengan pipeline yang sudah ada.

### 4.2.2 Alur Forward Chaining 4 Tahap

Implementasi forward chaining mengikuti hierarki 4 tahap sesuai perancangan pada Bab 3 Sub Bab 3.2.5. Setiap transaksi yang masuk diproses melalui tahapan berikut secara berurutan (data-driven):

**Tahap 1 — Aturan Deterministik KB Tree**

Sistem mencocokkan keterangan transaksi terhadap keyword pattern yang tersimpan pada Tree Pola. Pencocokan dilakukan menggunakan regex word-boundary matching (`\b...\b`) untuk menghindari false positive dari substring. Pola yang dicek pada tahap ini meliputi:
- BBM/Bensin (keyword: `bensin`, `bbm`, `pertamina`, `shell`, `spbu`)
- Listrik/PLN (keyword: `pln`, `listrik`, `token`)
- Gaji (keyword: `gaji`, `salary`, `payroll`)
- Pajak (keyword: `pajak`, `ppn`, `pph`, `mpn`)
- BPJS (keyword: `bpjs`, `jamsostek`)
- Admin Bank (keyword: `biaya adm`, `admin`, `sa saldo`)
- Bunga Bank (keyword: `bunga`, `interest`)

Apabila ditemukan kecocokan, sistem langsung menelusuri (traverse) ke parent node pada Tree Kategori untuk memperoleh konteks kategori secara berjenjang, kemudian mengambil kode akun CoA dari metadata leaf node. Status hasil inferensi pada tahap ini adalah `KB_TEREALISASI`.

**Tahap 2 — Resolusi Rekanan Mitra dan Pencocokan Faktur ERP**

Apabila Tahap 1 tidak menemukan pola deterministik, sistem melanjutkan ke resolusi rekanan. Nama pihak ketiga diekstrak dari keterangan transaksi menggunakan heuristik pembersihan teks (menghilangkan prefix bank seperti `TRSF`, `BYR`, `SWITCHING`, serta noise words). Nama yang diekstrak kemudian dicocokkan terhadap daftar vendor, customer, dan entitas internal pada Tree Perusahaan.

Jika nama pihak ditemukan sebagai vendor, sistem menetapkan kode akun Utang Usaha (`2.1.01.01`) untuk transaksi debit. Jika ditemukan sebagai customer, sistem menetapkan kode akun Piutang Usaha (`1.1.04.01`) untuk transaksi kredit. Selain itu, pada tahap ini sistem juga melakukan pencocokan faktur ERP melalui `PerusahaanAPIClient` (Adapter Pattern) untuk mencocokkan pembayaran terhadap invoice yang belum lunas.

**Tahap 3 — Validasi NLP Confident**

Untuk transaksi yang tidak terselesaikan pada Tahap 1 dan 2, sistem memanfaatkan output dari modul NLP (Pool 2). Model NLP berbasis LinearSVC terkalibrasi (`model_coa_final.pkl`) menghasilkan label kategori CoA beserta confidence score. Apabila confidence score ≥ threshold (θ = 0.72), label NLP dipetakan ke kode akun CoA melalui `MAPPING_LABEL_NLP_KE_COA`. Guard tambahan berupa pengecekan jenis mutasi (debit/kredit) diterapkan untuk memastikan konsistensi, misalnya label `SALARY` hanya valid untuk transaksi debit.

Terdapat 17 sub-kategori riil yang didukung oleh model NLP: `SALARY`, `RECEIVABLE_CUSTOMER`, `PAYABLE_VENDOR`, `UTILITIES`, `COMMUNICATION`, `TRANSPORT`, `INTERNAL_TRANSFER`, `BANK_CHARGE`, `BANK_INTEREST`, `EMP_BENEFIT`, `TAX`, dan lainnya.

**Tahap 4 — Ambigu / Anomali → Manual Review**

Transaksi yang tidak berhasil diselesaikan pada ketiga tahap sebelumnya (confidence NLP di bawah threshold, tidak ditemukan pola deterministik, dan nama rekanan tidak dikenali) dialihkan ke status `MANUAL_REVIEW` atau `suggestion`. Pengguna diarahkan untuk melakukan pemetaan secara manual melalui antarmuka suggestion system.

### 4.2.3 Contoh Alur Inferensi

Sebagai ilustrasi, berikut adalah contoh alur forward chaining untuk transaksi dengan keterangan `"BYR VIA E-BANKING 0860 PLN JATIM DARBE..."`, jenis `DB`, mutasi Rp 1.694.321:

1. **Tahap 1:** Sistem mencocokkan keterangan dengan keyword pattern. Keyword `pln` ditemukan pada pola PLN di Tree Pola → traverse ke parent: PLN → Biaya Utilitas → Biaya Operasional → Expense. Kode akun dari metadata: `6.2.05.01` (Utilities — Electricity/PLN).
2. **Hasil:** Status `KB_TEREALISASI`, kode akun `6.2.05.01`, metode `KB Engine (Pola PLN/Listrik — kb_engine)`.

Contoh lain untuk transaksi `"SWITCHING TRANSFER DR 008 PANCA BERSAUDARA"`, jenis `CR`, mutasi Rp 50.000.000:

1. **Tahap 1:** Tidak ditemukan pola deterministik yang cocok.
2. **Tahap 2:** Nama rekanan diekstrak: "PANCA BERSAUDARA" → ditemukan di Tree Perusahaan sebagai customer. Jenis mutasi CR → kode akun Piutang Usaha `1.1.04.01`. Invoice matching: ditemukan INV-2023-004 (Rp 50.000.000, lunas).
3. **Hasil:** Status `KB_TEREALISASI`, kode akun `1.1.04.01`, metode `KB Engine (Pola Rekanan/Switching)`, invoice `INV-2023-004 (Lunas)`.

---

## 4.3 Implementasi Feedback Loop

### 4.3.1 Mekanisme Konfirmasi dan Penolakan

Feedback loop diimplementasikan melalui dua endpoint REST API:
- `POST /api/transaksi/{id}/konfirmasi` — untuk mengonfirmasi rekomendasi
- `POST /api/transaksi/{id}/tolak` — untuk menolak rekomendasi dan memasukkan kode akun yang benar

Setiap aksi konfirmasi atau penolakan dicatat pada tabel `feedback_log` sebagai audit trail, mencakup `transaksi_id`, `mapping_id`, `aksi` (konfirmasi/tolak/manual_input), `kode_akun_lama`, `kode_akun_baru`, dan `catatan`. Status transaksi pada tabel `transaksi` diperbarui menjadi `confirmed` atau `rejected`.

### 4.3.2 Pembaruan Frequency-Based Confidence

Sesuai formula pada Persamaan 2.2, setiap konfirmasi memperbarui nilai confidence pada mapping layer:

```
                    Jumlah Konfirmasi Benar
Confidence(r) = ───────────────────────────
                    Total Kemunculan
```

- **Konfirmasi benar:** `jumlah_konfirmasi_benar` naik +1, `total_kemunculan` naik +1 → confidence naik.
- **Penolakan:** hanya `total_kemunculan` yang naik +1 → confidence turun secara otomatis.

### 4.3.3 Simulasi Pertumbuhan Confidence

Untuk membuktikan bahwa feedback loop benar-benar membuat sistem semakin akurat, dilakukan simulasi pertumbuhan confidence pada dua skenario:

**Skenario 1: Transaksi Ambigu yang Dikonfirmasi Berulang**

Sebuah relasi mapping baru (misalnya pola "TOKPED" → kategori "Penerimaan E-Commerce") dimulai dengan confidence awal 0.50 (1 konfirmasi dari 2 kemunculan). Setelah 3 kali dikonfirmasi benar secara berturut-turut:

| Iterasi | Konfirmasi Benar | Total Kemunculan | Confidence | Status |
|---------|-----------------|-----------------|------------|--------|
| Awal | 1 | 2 | 0.50 | Suggestion |
| Ke-1 | 2 | 3 | 0.67 | Suggestion |
| Ke-2 | 3 | 4 | 0.75 | **Auto Match** (≥ 0.72) |
| Ke-3 | 4 | 5 | 0.80 | Auto Match |

Pada iterasi ke-2, confidence telah melewati threshold 0.72 sehingga sistem mulai menampilkan rekomendasi tersebut sebagai Auto Match tanpa perlu konfirmasi pengguna.

**Skenario 2: Transaksi yang Salah dan Ditolak**

Sebuah relasi mapping dengan confidence awal 0.80 (4 konfirmasi dari 5 kemunculan) ditolak 2 kali berturut-turut:

| Iterasi | Konfirmasi Benar | Total Kemunculan | Confidence | Status |
|---------|-----------------|-----------------|------------|--------|
| Awal | 4 | 5 | 0.80 | Auto Match |
| Tolak-1 | 4 | 6 | 0.67 | Suggestion |
| Tolak-2 | 4 | 7 | 0.57 | Suggestion |

Setelah 2 penolakan, confidence turun dari 0.80 ke 0.57 (di bawah threshold 0.72), sehingga sistem tidak lagi menampilkannya sebagai Auto Match melainkan sebagai Suggestion yang memerlukan konfirmasi pengguna.

Kedua skenario ini menunjukkan bahwa mekanisme feedback loop mampu meningkatkan confidence relasi yang benar seiring penggunaan, sekaligus menurunkan confidence relasi yang salah secara otomatis tanpa intervensi pengembang.

---

## 4.4 Integrasi dengan Modul NLP (Pool 2)

### 4.4.1 Pipeline Integrasi

Integrasi antara modul NLP (Pool 2, dikembangkan oleh Abrorus Sholeh) dan modul Knowledge Base (Pool 3) diimplementasikan dalam alur pipeline sebagai berikut:

```
Input Transaksi
    ↓
[Pool 2] Model NLP (LinearSVC terkalibrasi)
    → Label CoA (17 kategori) + Confidence Score
    ↓
[Pool 3] KB Engine (Forward Chaining 4 Tahap)
    → Tahap 1: Aturan Deterministik Tree
    → Tahap 2: Resolusi Rekanan + Faktur ERP
    → Tahap 3: Validasi NLP (jika confidence ≥ 0.72)
    → Tahap 4: Manual Review (fallback)
    ↓
Suggestion System → Konfirmasi Pengguna → Feedback Loop
```

Seluruh output NLP, terlepas dari nilai confidence-nya, diteruskan ke KB Engine. KB Engine tidak hanya menerima transaksi yang ambigu (confidence < θ), tetapi juga menggunakan output NLP sebagai salah satu fakta tambahan dalam proses forward chaining. Dengan demikian, NLP dan KB bekerja secara komplementer: NLP memberikan prediksi awal berbasis machine learning, sementara KB memvalidasi dan memperkaya prediksi tersebut dengan pengetahuan domain yang terstruktur.

### 4.4.2 Routing dan Distribusi Pool

Sistem routing yang diimplementasikan pada `routing.py` mendistribusikan transaksi ke pool yang sesuai:

- **Pool 1 (Auto via ML):** Transaksi yang berhasil diklasifikasi oleh NLP dengan confidence ≥ 0.72 dan lolos validasi guard debit/kredit di KB.
- **Pool 3 (KB Rescue):** Transaksi yang dirujuk ke KB karena confidence NLP < 0.72, atau yang memerlukan pencocokan deterministik (pola, rekanan, faktur).
- **Manual Review:** Transaksi yang tidak terselesaikan oleh kedua pool.

---

## 4.5 Implementasi Suggestion System dan Aplikasi Web

### 4.5.1 Arsitektur Aplikasi

Aplikasi web diimplementasikan menggunakan arsitektur berikut:
- **Backend:** FastAPI (Python) dengan endpoint REST API untuk seluruh operasi rekonsiliasi, feedback loop, dan statistik.
- **Frontend:** React + TypeScript + Tailwind CSS dengan client-side routing (React Router).
- **Database:** PostgreSQL via Supabase Cloud dengan skema multitenant dan RLS.

### 4.5.2 Antarmuka Suggestion System

Antarmuka suggestion system menampilkan hasil rekonsiliasi dalam bentuk tabel interaktif dengan informasi berikut per transaksi:
- Tanggal, keterangan, jenis mutasi (DB/CR), dan nominal.
- Kode akun CoA yang direkomendasikan beserta nama akun.
- Status pemetaan: **Auto Match** (hijau), **Suggestion** (kuning), atau **Manual** (merah).
- Metode penyelesaian yang menjelaskan jalur inferensi yang digunakan.
- Tombol aksi: Konfirmasi (✓) dan Tolak/Koreksi (✎) untuk setiap baris yang belum divalidasi.

Statistik live ditampilkan pada bagian atas halaman hasil, mencakup jumlah Auto Match, Suggestion, Manual, Dikonfirmasi, Ditolak, serta persentase Coverage keseluruhan.

### 4.5.3 Modal Konfirmasi dan Penolakan

Dialog konfirmasi menampilkan detail transaksi (keterangan, rekomendasi KB, nama akun, metode) dan menyediakan field opsional untuk koreksi kode akun serta catatan. Pada mode penolakan, field kode akun baru bersifat wajib agar pengguna memasukkan akun yang benar sebagai bahan pembelajaran untuk feedback loop.

---

## 4.6 Evaluasi Kinerja Sistem

### 4.6.1 Dataset dan Metodologi Evaluasi

Evaluasi dilakukan menggunakan dataset transaksi riil BCA tahun 2023 dari perusahaan mitra. Untuk menghindari data leakage, dataset dibagi menjadi:
- **Data latih ML:** Baris yang digunakan untuk melatih model NLP (dieksklusikan dari metrik utama).
- **Data uji:** Baris yang belum pernah dilihat oleh model NLP (digunakan sebagai metrik utama evaluasi).

Total dataset terdiri dari 337 transaksi, di mana 139 transaksi merupakan data uji yang belum pernah dilihat model. Evaluasi bersifat end-to-end, yaitu mengukur kinerja keseluruhan pipeline dari input transaksi hingga output kode akun CoA yang dihasilkan.

### 4.6.2 Hasil Evaluasi — Data Uji (Metrik Utama)

**Tabel 4.2 — Ringkasan Hasil Evaluasi pada Data Uji (139 Transaksi)**

| Metrik | Nilai |
|--------|-------|
| **Total Transaksi** | 139 (100,0%) |
| **Pool 1 — Otomasi ML (NLP)** | 128 transaksi (92,1%) |
| Akurasi Model ML | 126/128 (98,4%) |
| **Pool 3 — Rujukan Ambigu ke KB** | 11 transaksi (7,9%) |
| Berhasil Diselamatkan oleh KB | 11 transaksi (100,0%) |
| Akurasi Penyelamatan KB | 8/11 (72,7%) |
| Sisa Manual Review | 0 transaksi (0,0%) |
| **Tingkat Otomasi Sistem (Coverage)** | **139/139 (100,0%)** |
| **Akurasi Keseluruhan Sistem** | **134/139 (96,4%)** |

Hasil evaluasi menunjukkan bahwa sistem mencapai **tingkat otomasi (coverage) 100%** pada data uji, artinya seluruh 139 transaksi berhasil diselesaikan secara otomatis tanpa memerlukan manual review. Akurasi keseluruhan sistem sebesar **96,4%** menunjukkan bahwa 134 dari 139 transaksi dipetakan ke kode akun CoA yang tepat.

### 4.6.3 Analisis Peran Knowledge Base (Pool 3)

Dari 139 transaksi data uji, 11 transaksi (7,9%) dirujuk ke Knowledge Base karena confidence NLP di bawah threshold atau memerlukan pencocokan deterministik. Seluruh 11 transaksi tersebut berhasil diselesaikan oleh KB Engine (tingkat penyelamatan 100%), dengan 8 di antaranya tepat sasaran (akurasi penyelamatan 72,7%).

Peran KB sebagai "penyelamat" transaksi ambigu terlihat jelas: tanpa KB, 11 transaksi tersebut akan masuk ke manual review dan menurunkan coverage menjadi 92,1%. Dengan KB, coverage meningkat dari 92,1% menjadi 100,0%, sebuah peningkatan yang signifikan dalam konteks otomasi rekonsiliasi keuangan.

### 4.6.4 Breakdown Performa per Kategori Akun

**Tabel 4.3 — Breakdown Performa per Kode Akun CoA pada Data Uji**

| Kategori | Kode CoA | Total | Benar | Akurasi |
|----------|----------|-------|-------|---------|
| Pembayaran dari Customer | 1.1.04.01 | 39 | 39 | 100,0% |
| Pembayaran Vendor/Supplier | 2.1.01.01 | 39 | 36 | 92,3% |
| Transfer Antar Bank — Keluar | 1.1.02.98 | 28 | 26 | 92,9% |
| Pembayaran Pajak/Setoran Negara | PERLU_REVIEW | 11 | 11 | 100,0% |
| Setoran Tunai | 1.1.1.01 | 5 | 5 | 100,0% |
| Biaya Administrasi Bank | PERLU_REVIEW | 5 | 5 | 100,0% |
| Transfer Antar Bank — Masuk | 1.1.02.98 | 4 | 4 | 100,0% |
| Biaya BPJS | PERLU_REVIEW | 4 | 4 | 100,0% |
| Biaya Penolakan/Lain-lain | PERLU_REVIEW | 4 | 4 | 100,0% |

Kategori dengan akurasi tertinggi (100%) meliputi Pembayaran dari Customer, Pembayaran Pajak, Setoran Tunai, Biaya Administrasi Bank, Transfer Masuk, dan BPJS. Kategori dengan akurasi sedikit lebih rendah adalah Pembayaran Vendor/Supplier (92,3%) dan Transfer Antar Bank Keluar (92,9%), yang disebabkan oleh keragaman format keterangan transaksi pada kategori tersebut.

### 4.6.5 Pembanding — Seluruh Data

Sebagai pembanding, evaluasi juga dilakukan pada seluruh 337 transaksi (termasuk data yang dipakai melatih model ML). Hasil menunjukkan coverage 98,5% (332/337) dan akurasi 93,7% (311/332). Angka ini sedikit lebih rendah dibandingkan data uji karena data latih mengandung lebih banyak variasi kasus edge yang sulit.

**Tabel 4.4 — Perbandingan Metrik Data Uji vs Seluruh Data**

| Metrik | Data Uji (139) | Seluruh Data (337) |
|--------|---------------|-------------------|
| Coverage | 100,0% | 98,5% |
| Akurasi Keseluruhan | 96,4% | 93,7% |
| Pool 1 (ML) | 92,1% | 91,4% |
| Pool 3 (KB Rescue) | 7,9% | 8,6% |
| Manual Review | 0,0% | 1,5% |

---

## 4.7 Pembahasan

### 4.7.1 Efektivitas Pendekatan Tree + Map

Hasil evaluasi membuktikan bahwa pendekatan representasi tree + map yang diadopsi dari literatur (Yang et al., 2023; Kovas & Hatzilygeroudis, 2024) efektif diterapkan pada domain rekonsiliasi keuangan. Keunggulan utama yang tervalidasi meliputi:

1. **Interpretability:** Setiap rekomendasi yang dihasilkan dapat ditelusuri jalur inferensinya, dari leaf node hingga root, sesuai kebutuhan auditabilitas domain keuangan.
2. **Modularitas:** Penambahan pola transaksi baru (misalnya keyword baru untuk PLN) dapat dilakukan langsung pada tabel `tree_nodes` tanpa memodifikasi kode program.
3. **Skalabilitas:** Struktur multitenant memungkinkan knowledge base yang sama digunakan oleh beberapa klien perusahaan dengan data yang terisolasi.

### 4.7.2 Komplementaritas NLP dan KB

Integrasi antara NLP (Pool 2) dan KB (Pool 3) menunjukkan hubungan yang komplementer. NLP berhasil menangani 92,1% transaksi secara otomatis dengan akurasi tinggi (98,4%), sementara KB berhasil menyelamatkan seluruh 7,9% transaksi yang ambigu. Pembagian peran ini sesuai dengan desain yang direncanakan: NLP sebagai penyaring utama berbasis machine learning, dan KB sebagai validator dan penyelamat berbasis pengetahuan domain.

3 dari 11 transaksi yang diselamatkan KB memiliki kode akun yang kurang tepat (akurasi KB 72,7%). Hal ini disebabkan oleh keterbatasan cakupan aturan deterministik untuk pola transaksi yang sangat spesifik atau format keterangan yang tidak standar. Peningkatan akurasi KB dapat dilakukan dengan memperkaya tree pola dan mapping layer berdasarkan feedback pengguna seiring waktu.

### 4.7.3 Validasi Feedback Loop

Simulasi pertumbuhan confidence (Sub Bab 4.3.3) membuktikan bahwa mekanisme feedback loop berfungsi sesuai desain: relasi yang dikonfirmasi benar secara berulang akan naik confidence-nya hingga menjadi Auto Match, sementara relasi yang salah akan turun confidence-nya menjadi Suggestion yang memerlukan verifikasi manual. Mekanisme ini menjawab permasalahan yang diidentifikasi pada Bab 1, yaitu ketiadaan mekanisme pembelajaran otomatis pada proses rekonsiliasi konvensional.

### 4.7.4 Keterbatasan

Beberapa keterbatasan yang ditemukan selama implementasi dan evaluasi:

1. **API Sandbox Mitra:** Integrasi dengan sistem ERP mitra masih menggunakan mock data (Adapter Pattern) karena pihak mitra belum menyediakan URL endpoint dan API key untuk sandbox. Ketika sandbox tersedia, sistem tinggal mengubah konfigurasi `PERUSAHAAN_USE_MOCK=false` pada file `.env`.
2. **Modul Table Recognition:** Pengujian end-to-end dari PDF belum dapat dilakukan karena modul ekstraksi tabel (Pool 1, dikembangkan oleh Arya Putra) masih dalam tahap pengembangan. Evaluasi saat ini menggunakan data transaksi yang sudah diekstrak.
3. **Evaluasi satu bank:** Dataset evaluasi saat ini hanya mencakup rekening koran BCA. Evaluasi lintas-bank (Mandiri, BRI, BNI) perlu dilakukan untuk mengukur generalisasi knowledge base.
4. **Penilaian knowledge expert:** Validasi kualitatif oleh pihak perusahaan mitra belum dilaksanakan pada tahap ini dan akan dilakukan pada tahap selanjutnya.
