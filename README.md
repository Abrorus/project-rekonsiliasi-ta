# SIREKON — Modul NLP Klasifikasi Transaksi Rekening Koran (Pool 2)

Repositori Tugas Akhir **Abrorus Shobah (NRP 5026231145)** — bagian dari sistem rekonsiliasi keuangan cerdas **SIREKON** (bersama Arya pada Pool 1 *Table Recognition* dan Mario pada Pool 3 *Knowledge Base & ERP Integration*).

## Struktur Direktori

### 1. `src/` (Kode Program Utama Pool 2)
| Berkas | Fungsi |
| --- | --- |
| `kamus_istilah.py` | Normalisasi teks, kamus sinonim singkatan perbankan, dan *stopword removal* |
| `kategori_keuangan.py` | Definisi 19 sub-kategori *Chart of Accounts* (CoA) dan pemetaan akun |
| `siapkan_data_coa.py` | Persiapan dataset BCA & Mandiri, pelabelan CoA, dan pembuatan sampel validasi 20% |
| `metrik_preprocessing.py` | Pengukuran performa *preprocessing* dan *sparsity* matriks TF-IDF |
| `latih_model_coa.py` | Pelatihan model SVM, evaluasi *5-fold CV*, dan pengujian lintas-bank |
| `bandingkan_model_coa.py` | Perbandingan performa SVM, Random Forest, SBERT, dan FinBERT + *paired t-test* |
| `eksperimen_perbaikan.py` | Eksperimen kernel Linear vs RBF, *masking* nama pihak, dan *StratifiedGroupKFold* |
| `threshold_coa.py` | Penentuan *confidence threshold* optimal ($\tau^* = 0,72$) |
| `evaluasi_routing_kb.py` | Evaluasi metrik *confidence routing* dan simulasi integrasi Pool 3 (*Knowledge Base*) |
| `simulasi_5bank_coa.py` | Pengujian kompatibilitas 5 bank (BCA, Mandiri, BNI, BRI, dan BSI) |
| `hitung_kappa.py` | Perhitungan *Cohen's Kappa* setelah file validasi 20% diisi staf keuangan mitra |
| `routing.py` | Fungsi dasar inferensi satu transaksi dan penyaringan *confidence threshold* |
| `proses_json.py` | Fungsi integrasi `klasifikasi_batch()` dan `terapkan_koreksi()` untuk Pool 1 & Pool 3 |
| `buat_visualisasi_bab4.py` | Generator grafik visualisasi Bab 4 (`.png` & `.svg`) |
| `buat_docx_bab4.py` | Generator otomatis dokumen Buku TA Final (`.docx` & `.html`) |
| `buat_pdf_kebutuhan_avolut.py` | Generator dokumen PDF ringkasan kebutuhan data mitra Avolut |

### 2. `models/` (Model Terlatih Siap Pakai)
- `model_coa_final.pkl` — Model final TF-IDF (*word* + *char n-gram*) + SVM Linear terkalibrasi
- `threshold_coa.json` — Konfigurasi *confidence threshold* optimal (`0.72`)

### 3. `docs/` (Dokumen Buku TA, Grafik, & Panduan Sidang)
- `Buku_TA_Final_Bab1_sd_Bab5.docx` — Buku Tugas Akhir lengkap Bab 1 s.d. Bab 5
- `ABSTRAK_final.md`, `BAB4_draft.md`, `BAB5_draft.md`, `BAB4_Siap_Copas_Word.html`
- `PANDUAN_SIDANG_ABROR.md` — Rangkuman materi dan definisi istilah untuk persiapan sidang
- `Kebutuhan_Data_Avolut_NLP_dan_KB.pdf` — Dokumen kebutuhan data & validasi untuk Avolut
