# SIREKON — Modul Knowledge Base (Pool 3)

Proyek Tugas Akhir: **Sistem Rekonsiliasi Transaksi Keuangan Bank Berbasis Integrasi OCR, NLP, dan Knowledge Base**.

* **Pool 1 (Table Recognition)**: Ekstraksi tabel rekening koran format PDF (Arya Wiraguna).
* **Pool 2 (Modul NLP)**: Klasifikasi teks keterangan mutasi ke sub-kategori CoA (Abrorus Shobah).
* **Pool 3 (Knowledge Base — Branch ini)**: Mesin aturan akuntansi (*Decision Tree & KB Engine*), integrasi bagan akun (*Chart of Accounts* / CoA) mitra, pencocokan rekanan bisnis (*Vendor & Customer Resolver*), integrasi database Supabase, serta mekanisme pembelajaran mandiri (*Feedback Loop & Frequency-Based Confidence*) (Muhammad Ridho Utomo / Mario).

---

## 🏛️ Arsitektur & Alur Inferensi Pool 3

Dalam arsitektur SIREKON, seluruh transaksi hasil inferensi NLP (Pool 2) diteruskan ke **Knowledge Base (Pool 3)** sebagai penentu keputusan akhir (*decision maker*):

```
[Transaksi Bank]
       │
       ▼
 [Modul NLP Pool 2] (Klasifikasi CoA + Confidence Score)
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                 Knowledge Base Engine (Pool 3)              │
│                                                             │
│  Tahap 1: Aturan Deterministik / KB Tree                   │
│           - Beban Operasional (PLN, Gaji, BBM, Pulsa)       │
│           - Pajak Negara (Penerimaan Negara, PPN, PPh)      │
│           - BPJS Kesehatan & Ketenagakerjaan                │
│           - Biaya Admin Bank & Bunga Simpanan               │
│           - Pendapatan Sewa (Cold Storage, Gedung)          │
│                                                             │
│  Tahap 2: Business Partner / Rekanan Resolver               │
│           - Guard mutasi: CR -> Master Customer             │
│           - Guard mutasi: DB -> Master Vendor / Supplier    │
│           - Resolusi rekening perantara (Switching Bank)    │
│                                                             │
│  Tahap 3: Validasi & Pemetaan NLP Confident (>= 0.72)       │
│           - Teks bersih & confidence tinggi                 │
│           - Petakan ke kode akun CoA riil mitra             │
│                                                             │
│  Tahap 4: Ambigu / Anomali Tanpa Pola                       │
│           - Rujuk ke Manual Review (Antarmuka Akuntan)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
     [Kode Akun CoA Riil & Jurnal Rekonsiliasi Tervalidasi]
                               │
                               ▼
        [Feedback Loop: Konfirmasi / Koreksi Akuntan]
                               │
                               ▼
        [Update Frequency-Based Confidence di Database]
```

---

## 💾 Skema Database Supabase & Feedback Loop

Modul ini terhubung ke cloud database **PostgreSQL (Supabase)** dengan 5 tabel relasional:

1. **`tree_nodes`**: Pohon hierarki bagan akun (CoA), master vendor, master customer, dan faktur.
2. **`mapping_layer`**: Aturan hubungan antar-node beserta metrik pembelajaran mandiri:
   $$\text{Confidence} = \frac{\text{Jumlah Konfirmasi Benar}}{\text{Total Kemunculan}}$$
3. **`account_mapping`**: Pemetaan kode transaksi bank spesifik ke kode akun ERP mitra.
4. **`transaksi`**: Penyimpanan hasil rekonsiliasi riil (`status`, `dikonfirmasi_oleh`, `dikonfirmasi_pada`).
5. **`feedback_log`**: Jejak audit (*audit trail*) yang mencatat **siapa**, **kapan**, dan **aksi apa** yang dilakukan lengkap dengan data kode akun sebelum vs sesudah koreksi.

---

## 📁 Struktur Direktori & Berkas Penting

```
project-rekonsiliasi-ta/
├── data/
│   ├── CoA.xlsx                         # Bagan akun (CoA) riil mitra
│   ├── Dummy RK.xlsx                    # Sampel mutasi rekening koran
│   ├── bca_riil_partial_label.csv       # Dataset transaksi riil BCA (337 baris)
│   ├── data_riil_berlabel_coa.csv       # Dataset riil lintas-bank berlabel CoA (607 baris)
│   └── hasil_evaluasi_integrasi_kb.csv  # Rekap hasil evaluasi akurasi & coverage KB
├── models/
│   ├── model_coa_final.pkl              # Pipeline LinearSVC terkalibrasi (Pool 2)
│   └── threshold_coa.json               # Ambang batas keyakinan optimal (0.72)
├── src/
│   ├── database/
│   │   ├── schema.sql                   # DDL skema tabel Supabase
│   │   ├── seed.py                      # Skrip inisialisasi master data & CoA
│   │   └── seed_update_v2.py            # Pembaruan aturan sewa & keyword bank
│   ├── knowledge_base/
│   │   ├── coa.py                       # Hierarki CoA mitra & kamus mapping label NLP
│   │   ├── decision_tree_kb.py          # Logika pohon keputusan aturan deterministik
│   │   ├── rekanan_resolver.py          # Pencocokan nama vendor/customer
│   │   ├── kb_engine.py                 # Mesin inferensi utama berbasis Supabase
│   │   └── api_client.py                # Adapter REST API ERP perusahaan (mock/live)
│   ├── api/
│   │   ├── main.py                      # Unified FastAPI Gateway & endpoint feedback loop
│   │   ├── service.py                   # Service layer rekonsiliasi & Supabase bridge
│   │   └── db.py                        # Konektor klien Supabase
│   ├── evaluasi_kb.py                   # Evaluasi akurasi & coverage tanpa data leakage
│   └── routing.py                       # Simulasi alur integrasi end-to-end NLP -> KB
└── README.md
```

---

## 🚀 Panduan Menjalankan

Pastikan *virtual environment* Python aktif dan direktori kerja berada di folder proyek:

### 1. Konfigurasi Environment (`.env`)
Buat atau pastikan file `.env` berisi kredensial Supabase Anda:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-or-anon-key
```

### 2. Inisialisasi Database (Jika Diperlukan)
Jalankan skrip seed untuk mengisi master data pohon akun dan aturan awal:
```bash
python src/database/seed.py
python src/database/seed_update_v2.py
```

### 3. Simulasi Routing NLP $\to$ Knowledge Base
Uji simulasi inferensi untuk beberapa contoh transaksi mutasi:
```bash
python src/routing.py
```

### 4. Menjalankan Evaluasi Akurasi & Coverage KB
Jalankan evaluasi ilmiah untuk mengukur performa Knowledge Base terhadap data uji riil:
```bash
python src/evaluasi_kb.py
```

### 5. Menjalankan Server Backend API
Jalankan gateway REST API FastAPI untuk melayani permintaan dari frontend web atau sistem ERP:
```bash
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 📊 Hasil Evaluasi Terkini (Data Uji Riil BCA 2023)

Berdasarkan pengujian pada 139 data uji transaksi riil yang **belum pernah dilihat oleh model ML** (*out-of-sample test* untuk mencegah *data leakage*):

| Metrik Evaluasi | Hasil Capaian | Keterangan |
|---|:---:|---|
| **Tingkat Otomasi Sistem (Coverage)** | **100.0%** (139/139) | Seluruh transaksi berhasil diproses tanpa mandek |
| **Akurasi Keseluruhan Sistem** | **96.4%** (134/139) | Tepat sasaran ke kode CoA riil mitra |
| **Otomasi Model ML (Pool 1)** | **92.1%** (128 baris) | Akurasi ML: **98.4%** (126/128) |
| **Penyelamatan oleh KB (Pool 3)** | **7.9%** (11 baris) | Transaksi ambigu yang berhasil diselamatkan KB |
| **Transaksi Manual Review** | **0.0%** (0 baris) | Tidak ada transaksi yang gagal terpetakan |

### Breakdown Akurasi per Kelompok Akun:
* **Piutang Usaha (4-2000 $\to$ 1.1.04.01)**: 100.0% (39/39)
* **Utang Usaha / Vendor (6-5000 $\to$ 2.1.01.01)**: 92.3% (36/39)
* **Switching Antar Bank Keluar (6-9000 $\to$ 1.1.02.98)**: 92.9% (26/28)
* **Pajak & Setoran Negara (6-7000)**: 100.0% (11/11)
* **Setoran Tunai (4-4000 $\to$ 1.1.1.01)**: 100.0% (5/5)
* **Biaya Administrasi Bank (6-1100)**: 100.0% (5/5)
* **BPJS Ketenagakerjaan / Kesehatan (6-6000)**: 100.0% (4/4)
* **Biaya Penolakan Kliring (6-8000)**: 100.0% (4/4)

---

## 👥 Tim Pengembang Tugas Akhir
* **Muhammad Ridho Utomo** (Knowledge Base, Integrasi Sistem & Database)
* **Abrorus Shobah** (Modul NLP & Klasifikasi Teks)
* **Arya Wiraguna Dwiputra** (Modul Table Recognition & Deduplikasi OCR)
