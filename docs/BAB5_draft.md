# BAB 5 KESIMPULAN DAN SARAN

## 5.1 Kesimpulan

Berdasarkan hasil perancangan, implementasi, dan pengujian modul *Natural Language Processing* (NLP) pada sistem rekonsiliasi keuangan cerdas SIREKON (Pool 2), diperoleh kesimpulan yang menjawab rumusan masalah penelitian sebagai berikut:

1. **Pemrosesan Teks Keterangan Transaksi Rekening Koran Heterogen (Rumusan Masalah 1):**
   Pipeline praproses teks yang menggabungkan normalisasi karakter, tokenisasi, pemetaan kamus singkatan perbankan/operasional (*synonym mapping dictionary*), dan penghapusan *stopword* spesifik domain berhasil mereduksi *noise* sebesar **34,05%** (*Token Reduction Rate* dari 2.761 menjadi 1.821 token), menghasilkan ukuran kosakata 326 token unik dengan rata-rata 3,22 token per transaksi, serta memetakan 122 kemunculan singkatan tidak baku pada 566 transaksi riil BCA dan Mandiri. Ekstraksi fitur menggunakan kombinasi TF-IDF *word n-gram* (1–2) dan *character n-gram* (3–5) dengan *sparsity* **99,28%** terbukti tahan terhadap variasi penulisan singkatan dan *typo* pada kolom keterangan mutasi.

2. **Kinerja Mekanisme Klasifikasi Berbasis NLP dan Confidence Threshold (Rumusan Masalah 2):**
   Kombinasi fitur TF-IDF kata+karakter dan algoritme *Support Vector Machine* (SVM) terkalibrasi mampu memetakan transaksi ke dalam 14 sub-kategori *Chart of Accounts* (CoA) pada arah *cash in* (CR) dan *cash out* (DB) dengan akurasi **95,5%** dan **Macro-F1 0,895** pada evaluasi *5-fold Stratified Cross-Validation*, meningkat signifikan dibandingkan *baseline* arah CR/DB saja (akurasi 56,3%, Macro-F1 0,106). Melalui optimasi *confidence threshold* pada nilai ambang **$\tau^* = 0,72$**, sistem mengklasifikasikan **82,80%** transaksi secara otomatis dengan akurasi **99,57%** (Macro-F1 0,995) dan mengalihkan **28 dari 30 kesalahan prediksi (93,3%)** ke modul *Knowledge Base* (Pool 3). Integrasi dengan aturan *forward-chaining* pada Pool 3 menghasilkan *KB Resolution Rate* sebesar **68,75%** dan *Overall System Coverage* sebesar **94,62%** dengan akurasi gabungan **98,11%**, sehingga hanya menyisakan **5,38%** transaksi yang memerlukan konfirmasi manual staf keuangan.

3. **Evaluasi Komparatif dan Uji Ketahanan Model (Rumusan Masalah 3):**
   Berdasarkan pengujian *5-fold Stratified Cross-Validation*, model **TF-IDF + SVM Linear** (Macro-F1 **0,873 ± 0,068**) memperoleh skor rata-rata tertinggi dibandingkan **SBERT + Logistic Regression** (0,780 ± 0,051), **Random Forest** (0,776 ± 0,037), dan **FinBERT + Logistic Regression** (0,771 ± 0,021). Uji statistik *paired t-test* ($\alpha = 0,05$) membuktikan bahwa SVM unggul secara signifikan terhadap FinBERT ($p = 0,0168$), serta kompetitif terhadap Random Forest ($p = 0,0778$) dan SBERT ($p = 0,1352$) dengan biaya komputasi yang jauh lebih ringan. Eksperimen tambahan juga membuktikan bahwa kernel Linear secara konsisten mengungguli kernel RBF pada seluruh skema validasi (selisih Macro-F1 0,09–0,15), sedangkan pada pengujian ketat terhadap teks transaksi yang belum pernah dilihat sama sekali (*StratifiedGroupKFold*), model mencapai Macro-F1 **0,737** dan akurasi **84,3%**.

## 5.2 Saran

Berdasarkan keterbatasan yang ditemukan selama penelitian, diajukan beberapa saran untuk pengembangan sistem SIREKON dan penelitian selanjutnya:

1. **Perluasan Korpus Multi-Bank dan Penyeimbangan Kelas Minoritas:**
   Menambahkan data transaksi riil dari bank BNI, BRI, dan BSI serta memperbanyak sampel pada sub-kategori minoritas (seperti `UTILITIES`, `REVENUE_OTHER`, `REPAIR_MAINT`, `COMMUNICATION`, dan `TRAVEL` yang saat ini memiliki kurang dari 5 sampel) agar generalisasi lintas-bank meningkat dari kisaran Macro-F1 0,32–0,41 menuju tingkat akurasi dalam-bank.
2. **Validasi Berkelanjutan (*Active Learning* dari Koreksi Manual Pool 3):**
   Mengintegrasikan umpan balik hasil koreksi manual staf keuangan pada antarmuka Pool 3 (`sumber_label: manual` pada keluaran JSON bersih) ke dalam siklus pelatihan ulang (*periodic retraining*) dan pembaruan kamus singkatan secara otomatis, sehingga transaksi dari vendor atau pelanggan baru yang semula dirujuk ke Pool 3 dapat dikenali otomatis pada periode rekonsiliasi berikutnya.
3. **Fine-Tuning Model Bahasa Berbahasa Indonesia:**
   Apabila volume data transaksi historis perusahaan mitra telah mencapai ribuan baris unik, penelitian selanjutnya dapat menguji *fine-tuning* penuh menggunakan model bahasa yang dilatih pada korpus bahasa Indonesia (seperti IndoBERT) sebagai pembanding FinBERT berbahasa Inggris yang kurang optimal pada singkatan perbankan lokal.

