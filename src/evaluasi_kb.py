import sys
from pathlib import Path
import pandas as pd
from sklearn.metrics import classification_report, accuracy_score

# Daftarkan direktori 'src' ke sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from routing import load_model, klasifikasi_transaksi
    from knowledge_base.kategori_keuangan import KATEGORI
except ImportError:
    from src.routing import load_model, klasifikasi_transaksi
    from src.knowledge_base.kategori_keuangan import KATEGORI

# Mapping nama kategori ke kode akun untuk verifikasi ML
NAMA_KE_KODE = {v['nama']: k for k, v in KATEGORI.items()}

def evaluasi_end_to_end():
    print("=" * 75)
    print("   EVALUASI KINERJA INTEGRASI KNOWLEDGE BASE (POOL 3) & NLP (POOL 1)")
    print("   Tugas Akhir: Sistem Rekonsiliasi Transaksi Keuangan")
    print("=" * 75)

    # 1. Load Model & Dataset Riil BCA
    model, vectorizer = load_model()
    dataset_path = BASE_DIR / "data" / "bca_riil_partial_label.csv"
    
    if not dataset_path.exists():
        print(f"Error: Dataset tidak ditemukan di {dataset_path}")
        return

    df = pd.read_csv(dataset_path)
    total_transaksi = len(df)
    print(f"Total Data Transaksi Riil BCA 2023 : {total_transaksi} baris\n")

    hasil_records = []
    
    # Counter Metrik
    pool1_count = 0
    pool1_benar = 0
    
    pool3_total = 0
    pool3_kb_terekon = 0
    pool3_kb_benar = 0
    pool3_manual = 0

    y_true_all = []
    y_pred_all = []

    for _, row in df.iterrows():
        # Eksekusi pipeline integrasi
        res = klasifikasi_transaksi(row, model, vectorizer, threshold=0.66)
        
        gt_kode = str(row['kode_akun_final']).strip()
        gt_nama = KATEGORI.get(gt_kode, {}).get('nama', 'Unknown')
        
        # Ekstraksi kode akun dari hasil prediksi
        pred_kode = res.get('kode_akun', '')
        if not pred_kode:
            # Jika dari Pool 1 (ML), petakan nama kategori ML ke kode akun
            pred_nama = res.get('kategori_prediksi', '')
            pred_kode = NAMA_KE_KODE.get(pred_nama, 'UNKNOWN')

        is_benar = (pred_kode == gt_kode)
        
        # Simpan untuk evaluasi per kategori
        if pred_kode != 'UNKNOWN':
            y_true_all.append(gt_kode)
            y_pred_all.append(pred_kode)
        else:
            y_true_all.append(gt_kode)
            y_pred_all.append('MANUAL_REVIEW')

        # Klasifikasi Jalur
        if res['pool'] == 'Pool 1 (Otomatis ML)':
            pool1_count += 1
            if is_benar:
                pool1_benar += 1
        else: # Pool 3
            pool3_total += 1
            if res['status'] == 'KB_TEREALISASI':
                pool3_kb_terekon += 1
                if is_benar:
                    pool3_kb_benar += 1
            else:
                pool3_manual += 1

        hasil_records.append({
            'tanggal': row.get('tanggal', ''),
            'keterangan': row.get('keterangan', ''),
            'jenis': row.get('jenis', ''),
            'mutasi': row.get('mutasi', ''),
            'kode_akun_groundtruth': gt_kode,
            'kategori_groundtruth': gt_nama,
            'jalur_pool': res['pool'],
            'status_akhir': res['status'],
            'kode_akun_prediksi': pred_kode,
            'kategori_prediksi': res['kategori_prediksi'],
            'metode_penyelesaian': res.get('metode', ''),
            'confidence_ml': res.get('confidence') or res.get('confidence_ml_awal', 0.0),
            'evaluasi': 'TEPAT' if is_benar else 'SALAH'
        })

    df_hasil = pd.DataFrame(hasil_records)
    output_csv = BASE_DIR / "data" / "hasil_evaluasi_integrasi_kb.csv"
    df_hasil.to_csv(output_csv, index=False)
    print(f"-> File rekap evaluasi lengkap tersimpan di: {output_csv}\n")

    # --------------------------------------------------------------------------
    # REKAPITULASI METRIK UNTUK LAPORAN TUGAS AKHIR
    # --------------------------------------------------------------------------
    total_otomatis = pool1_count + pool3_kb_terekon
    total_benar = pool1_benar + pool3_kb_benar
    
    coverage_sistem = (total_otomatis / total_transaksi) * 100
    akurasi_keseluruhan = (total_benar / total_otomatis) * 100 if total_otomatis > 0 else 0
    akurasi_penyelamatan_kb = (pool3_kb_benar / pool3_kb_terekon) * 100 if pool3_kb_terekon > 0 else 0

    print("=" * 75)
    print("                RINGKASAN HASIL EVALUASI SISTEM")
    print("=" * 75)
    print(f"Total Dataset Transaksi Riil           : {total_transaksi} transaksi (100.0%)")
    print("-" * 75)
    print(f"1. POOL 1 - Otomatisasi ML (NLP)       : {pool1_count} transaksi ({pool1_count/total_transaksi*100:.1f}%)")
    print(f"   - Akurasi Model ML                  : {pool1_benar}/{pool1_count} ({pool1_benar/pool1_count*100:.1f}%)")
    print()
    print(f"2. POOL 3 - Rujukan Ambigu ke KB       : {pool3_total} transaksi ({pool3_total/total_transaksi*100:.1f}%)")
    print(f"   - Berhasil Diselamatkan oleh KB     : {pool3_kb_terekon} transaksi ({pool3_kb_terekon/pool3_total*100:.1f}%)")
    print(f"   - Akurasi Penyelamatan Aturan KB    : {pool3_kb_benar}/{pool3_kb_terekon} ({akurasi_penyelamatan_kb:.1f}%)")
    print(f"   - Sisa Memerlukan Manual Review     : {pool3_manual} transaksi ({pool3_manual/total_transaksi*100:.1f}%)")
    print("-" * 75)
    print(f"TINGKAT OTOMASI SISTEM (Coverage)      : {total_otomatis}/{total_transaksi} ({coverage_sistem:.1f}%)")
    print(f"AKURASI KESELURUHAN SISTEM TERVALIDASI : {total_benar}/{total_otomatis} ({akurasi_keseluruhan:.1f}%)")
    print(f"REDUKSI BEBAN KERJA AKUNTAN MANUAL     : Memangkas {(total_otomatis/total_transaksi)*100:.1f}% pekerjaan!")
    print("=" * 75)

    # --------------------------------------------------------------------------
    # TABEL BREAKDOWN PER KATEGORI AKUN UTAMA
    # --------------------------------------------------------------------------
    print("\n=== BREAKDOWN PERFORMA PER KODE AKUN (COA) ===")
    rekap_coa = df_hasil.groupby(['kode_akun_groundtruth', 'kategori_groundtruth']).agg(
        Total=('evaluasi', 'count'),
        Benar=('evaluasi', lambda x: (x == 'TEPAT').sum()),
        Otomatis_ML=('jalur_pool', lambda x: (x == 'Pool 1 (Otomatis ML)').sum()),
        Diselamatkan_KB=('status_akhir', lambda x: (x == 'KB_TEREALISASI').sum()),
        Manual_Review=('status_akhir', lambda x: (x == 'MANUAL_REVIEW').sum())
    ).reset_index()
    
    rekap_coa['Akurasi_%'] = (rekap_coa['Benar'] / rekap_coa['Total'] * 100).round(1)
    rekap_coa = rekap_coa.sort_values(by='Total', ascending=False)
    print(rekap_coa.to_string(index=False))
    print("=" * 75)

if __name__ == '__main__':
    evaluasi_end_to_end()
