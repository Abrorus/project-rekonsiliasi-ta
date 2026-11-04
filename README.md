# project-rekonsiliasi-ta
Project TA Abror, Arya, dan Mario — SIREKON. Bagian ini: **Pool 2 (modul NLP)**, klasifikasi keterangan transaksi ke sub-kategori CoA.

## Urutan menjalankan (dari folder `src`, venv aktif)
| Langkah | Perintah | Keluaran |
|---|---|---|
| 1. Siapkan & labeli data | `python siapkan_data_coa.py` | `data/data_riil_berlabel_coa.csv`, bahan validasi 20% |
| 2. Metrik preprocessing | `python metrik_preprocessing.py` | `data/hasil_metrik_preprocessing.csv` |
| 3. Latih & uji (CV, lintas-bank) | `python latih_model_coa.py` | `models/model_coa_final.pkl` |
| 4. Bandingkan SVM/RF/SBERT/FinBERT | `python bandingkan_model_coa.py` | `data/hasil_banding_model_coa.csv` (SBERT/FinBERT: set `HF_HUB_OFFLINE=1` bila model sudah ter-cache) |
| 5. Tentukan threshold | `python threshold_coa.py` | `models/threshold_coa.json` |
| 6. Simulasi routing | `python routing.py` | — |
| 7. Keluaran JSON untuk Pool 3 | `python proses_json.py input.json output.json` (tambah `--koreksi koreksi.json` setelah review manual) | JSON dengan status OTOMATIS / PERLU_REVIEW_MANUAL, lalu JSON bersih |

## Catatan
- Label masih "label perak" (aturan otomatis); belum divalidasi staf keuangan (target Cohen's Kappa >= 0.61).
- Skrip lama (`training_*.py`, `confidence_threshold.py`, `retrain_gabungan.py`, dst.) memakai kategori sintesis lama dan dipertahankan sebagai riwayat.
