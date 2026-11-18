# PANDUAN LENGKAP & CONTEKAN SIDANG TUGAS AKHIR (ABROR - POOL 2 NLP SIREKON)

Dokumen ini berisi rangkuman alur dari awal sampai akhir, definisi istilah, dan jawaban atas pertanyaan-pertanyaan yang paling sering ditanyakan dosen penguji.

---

## 1. Gambaran Besar Sistem SIREKON (3 Pool)
- **Pool 1 (Arya — Table Recognition):** Membaca file PDF rekening koran bank dan mengekstraknya menjadi tabel mentah (`waktu_transaksi`, `keterangan`, `debit`, `kredit`, `saldo`).
- **Pool 2 (Abror — Modul NLP):** Membaca teks `keterangan` mutasi dan arah `debit/kredit`, membersihkan singkatan tidak baku, lalu memprediksi **Sub-Kategori Akun CoA** beserta **Confidence Score (0–1)**.
  - Jika `confidence >= 0,72` $\rightarrow$ status `OTOMATIS`.
  - Jika `confidence < 0,72` $\rightarrow$ status `PERLU_REVIEW_MANUAL` (dirujuk ke Pool 3).
- **Pool 3 (Mario — Knowledge Base, UI, & Integrasi ERP):** Memvalidasi transaksi yang dirujuk menggunakan aturan *forward-chaining* berbasis data ERP (daftar Vendor/Customer & *Open Invoice*), menampilkan sisa transaksi ambigu di UI untuk dikonfirmasi staf keuangan, lalu melakukan rekonsiliasi akhir.

---

## 2. Definisi Istilah Kunci (Biar Tidak Tertukar Saat Ditanya Penguji)
- **TF-IDF (*Term Frequency - Inverse Document Frequency*):** Metode **ekstraksi fitur** untuk mengubah kata menjadi bobot angka berdasarkan frekuensi kata di satu transaksi (TF) dikali tingkat keunikan kata tersebut di seluruh dataset (IDF).
- **Word N-Gram (1–2) & Character N-Gram (3–5):**
  - *Word N-Gram*: Memotong fitur per 1 kata dan 2 kata berurutan.
  - *Character N-Gram*: Memotong per 3–5 huruf di dalam kata agar tahan terhadap salah ketik (*typo*) atau singkatan yang menempel (misal `bpjstkfeb`).
- **Sparsity (`99,28%`):** Persentase sel bernilai nol (0) pada matriks TF-IDF. Karena teks mutasi bank sangat pendek (rata-rata 3,22 kata dari 754 fitur), 99,28% matriks berisi angka nol.
- **SVM (*Support Vector Machine*):** **Algoritme klasifikasi utama** yang mencari bidang pemisah (*hyperplane*) optimal dengan margin terlebar antar-kategori. Sangat cocok untuk matriks TF-IDF yang berdimensi tinggi dan *sparse*.
- **Random Forest:** Algoritme *ensemble* pembanding yang menggunakan 100 pohon keputusan (*decision trees*) dan mengambil suara terbanyak (*majority voting*).
- **SBERT (*Sentence-BERT*) & FinBERT:** Model bahasa berbasis *Transformer* (*deep learning*) yang mengubah kalimat menjadi vektor makna padat (*dense embedding* 384/768 dimensi), lalu diklasifikasikan menggunakan *Logistic Regression*.
- **Macro-F1 Score:** Rata-rata harmonik dari *Precision* dan *Recall* yang dihitung per kategori lalu dirata-ratakan secara setara tanpa memedulikan ukuran kelas. Wajib dipakai karena jumlah data antar-kategori sangat timpang (*imbalanced dataset*).
- **Paired t-test ($\alpha = 0,05$):** Uji statistik pada hasil 5-fold CV untuk membuktikan apakah selisih nilai F1-Score antar dua model benar-benar signifikan ($p < 0,05$) atau hanya kebetulan.
- **Cohen's Kappa ($\kappa$):** Rumus statistik untuk mengukur tingkat kesepakatan pelabelan antara peneliti dan pakar keuangan perusahaan mitra (target $\kappa \ge 0,61$ = *substantial agreement*).

---

## 3. Ringkasan Angka Hasil Eksperimen (Hafalkan 6 Angka Kunci Ini)
1. **Metrik Preprocessing & TF-IDF (566 transaksi):**
   - *Token Reduction Rate* = **34,05%** (dari 2.761 jadi 1.821 token), kosakata = **326 token unik**, *Sparsity* TF-IDF = **99,28%**.
2. **Hasil Klasifikasi Utama (5-Fold Stratified CV pada 558 transaksi, 14 sub-kategori):**
   - *Baseline* (hanya tebak dari arah CR/DB): Akurasi **56,3%**, Macro-F1 **0,106**.
   - **TF-IDF Kata+Karakter + SVM Linear**: Akurasi **95,5%**, Macro-F1 **0,895**.
3. **Perbandingan 4 Model (Rata-rata Macro-F1 ± Std per Fold):**
   - **SVM (TF-IDF):** **0,873 ± 0,068** (Akurasi **95,5%**) $\rightarrow$ **Terbaik**.
   - **SBERT:** **0,780 ± 0,051** (Akurasi 87,3%).
   - **Random Forest:** **0,776 ± 0,037** (Akurasi 90,7%).
   - **FinBERT:** **0,771 ± 0,021** (Akurasi 92,3%) $\rightarrow$ SVM menang signifikan atas FinBERT ($p = 0,0168$).
4. **Kernel Linear vs RBF & Uji Teks Baru (*StratifiedGroupKFold*):**
   - Kernel **Linear selalu unggul 0,09–0,15 poin Macro-F1 di atas RBF**.
   - Pada teks yang belum pernah dilihat sama sekali (*GroupKFold*), SVM Linear mencapai Akurasi **84,3%** dan Macro-F1 **0,737**.
5. **Confidence Threshold Optimal ($\tau^* = 0,72$):**
   - **Auto-Classification Rate:** **82,80%** (462/558 transaksi langsung otomatis) dengan **Akurasi 99,57%** (Macro-F1 0,995).
   - **Menyaring Error:** **28 dari 30 kesalahan prediksi (93,3%)** berhasil ditangkap karena skornya $< 0,72$ dan dialihkan ke Pool 3.
6. **Integrasi dengan Pool 3 (Knowledge Base):**
   - **KB Referral Rate:** **17,20%** (96/558 transaksi masuk ke Pool 3).
   - **KB Resolution Rate:** **68,75%** (66/96 transaksi berhasil diselesaikan aturan Pool 3).
   - **Overall System Coverage (Pool 2 + Pool 3):** **94,62%** (528/558 transaksi selesai otomatis dengan akurasi gabungan **98,11%**), menyisakan **5,38% (30 transaksi)** untuk review manual di UI.
