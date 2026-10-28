import sys
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

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

def tandai_data_latih(df):
    """
    Menandai baris data riil yang ikut dipakai melatih model gabungan.

    Mereplikasi persis pembagian data di retrain_gabungan.py (filter kategori overlap sintesis,
    kategori langka < 5 sampel masuk training, sisanya split 70/30 stratified, random_state=42).
    Evaluasi pada baris yang dipakai latih akan menggelembungkan akurasi (data leakage),
    sehingga metrik utama dihitung hanya pada baris yang belum pernah dilihat model.
    """
    kategori_sintesis = set(pd.read_csv(BASE_DIR / "data" / "dataset_preprocessed_v2.csv")['kategori'])
    nama_kategori = df['kode_akun_final'].map(lambda k: KATEGORI[k]['nama'])
    df_riil = df[nama_kategori.isin(kategori_sintesis)].assign(kategori=nama_kategori)

    counts = df_riil['kategori'].value_counts()
    kategori_cukup = counts[counts >= 5].index
    df_riil_cukup = df_riil[df_riil['kategori'].isin(kategori_cukup)]
    df_riil_langka = df_riil[~df_riil['kategori'].isin(kategori_cukup)]

    riil_train, _ = train_test_split(
        df_riil_cukup, test_size=0.3, random_state=42, stratify=df_riil_cukup['kategori']
    )
    indeks_latih = riil_train.index.union(df_riil_langka.index)
    return df.index.isin(indeks_latih)

def cetak_ringkasan(df_hasil, judul):
    total = len(df_hasil)
    pool1 = df_hasil[df_hasil['jalur_pool'] == 'Pool 1 (Otomatis ML)']
    pool3 = df_hasil[df_hasil['jalur_pool'] != 'Pool 1 (Otomatis ML)']
    pool3_kb = pool3[pool3['status_akhir'] == 'KB_TEREALISASI']
    pool3_manual = pool3[pool3['status_akhir'] == 'MANUAL_REVIEW']

    pool1_benar = (pool1['evaluasi'] == 'TEPAT').sum()
    pool3_kb_benar = (pool3_kb['evaluasi'] == 'TEPAT').sum()
    total_otomatis = len(pool1) + len(pool3_kb)
    total_benar = pool1_benar + pool3_kb_benar

    def persen(a, b):
        return a / b * 100 if b > 0 else 0.0

    print("=" * 75)
    print(f"   {judul}")
    print("=" * 75)
    print(f"Total Dataset Transaksi                : {total} transaksi (100.0%)")
    print("-" * 75)
    print(f"1. POOL 1 - Otomatisasi ML (NLP)       : {len(pool1)} transaksi ({persen(len(pool1), total):.1f}%)")
    print(f"   - Akurasi Model ML                  : {pool1_benar}/{len(pool1)} ({persen(pool1_benar, len(pool1)):.1f}%)")
    print()
    print(f"2. POOL 3 - Rujukan Ambigu ke KB       : {len(pool3)} transaksi ({persen(len(pool3), total):.1f}%)")
    print(f"   - Berhasil Diselamatkan oleh KB     : {len(pool3_kb)} transaksi ({persen(len(pool3_kb), len(pool3)):.1f}%)")
    print(f"   - Akurasi Penyelamatan Aturan KB    : {pool3_kb_benar}/{len(pool3_kb)} ({persen(pool3_kb_benar, len(pool3_kb)):.1f}%)")
    print(f"   - Sisa Memerlukan Manual Review     : {len(pool3_manual)} transaksi ({persen(len(pool3_manual), total):.1f}%)")
    print("-" * 75)
    print(f"TINGKAT OTOMASI SISTEM (Coverage)      : {total_otomatis}/{total} ({persen(total_otomatis, total):.1f}%)")
    print(f"AKURASI KESELURUHAN SISTEM TERVALIDASI : {total_benar}/{total_otomatis} ({persen(total_benar, total_otomatis):.1f}%)")
    print("=" * 75)

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
    df['dipakai_latih_ml'] = tandai_data_latih(df)
    print(f"Total Data Transaksi Riil BCA 2023 : {len(df)} baris")
    print(f"  - Pernah dipakai melatih model ML : {df['dipakai_latih_ml'].sum()} baris")
    print(f"  - Data uji (belum pernah dilihat) : {(~df['dipakai_latih_ml']).sum()} baris\n")

    hasil_records = []

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

        hasil_records.append({
            'tanggal': row.get('tanggal', ''),
            'keterangan': row.get('keterangan', ''),
            'jenis': row.get('jenis', ''),
            'mutasi': row.get('mutasi', ''),
            'dipakai_latih_ml': row['dipakai_latih_ml'],
            'kode_akun_groundtruth': gt_kode,
            'kategori_groundtruth': gt_nama,
            'jalur_pool': res['pool'],
            'status_akhir': res['status'],
            'kode_akun_prediksi': pred_kode,
            'kategori_prediksi': res['kategori_prediksi'],
            'metode_penyelesaian': res.get('metode', ''),
            'confidence_ml': res.get('confidence') or res.get('confidence_ml_awal', 0.0),
            'evaluasi': 'TEPAT' if pred_kode == gt_kode else 'SALAH'
        })

    df_hasil = pd.DataFrame(hasil_records)
    output_csv = BASE_DIR / "data" / "hasil_evaluasi_integrasi_kb.csv"
    df_hasil.to_csv(output_csv, index=False)
    print(f"-> File rekap evaluasi lengkap tersimpan di: {output_csv}\n")

    # --------------------------------------------------------------------------
    # REKAPITULASI METRIK UNTUK LAPORAN TUGAS AKHIR
    # Metrik utama: data uji saja. Seluruh data hanya sebagai pembanding (terkena leakage).
    # --------------------------------------------------------------------------
    df_uji = df_hasil[~df_hasil['dipakai_latih_ml']]
    cetak_ringkasan(df_uji, "RINGKASAN HASIL EVALUASI - DATA UJI (METRIK UTAMA)")
    print()
    cetak_ringkasan(df_hasil, "PEMBANDING - SELURUH DATA (termasuk data latih ML)")

    # --------------------------------------------------------------------------
    # TABEL BREAKDOWN PER KATEGORI AKUN UTAMA (DATA UJI)
    # --------------------------------------------------------------------------
    print("\n=== BREAKDOWN PERFORMA PER KODE AKUN (COA) - DATA UJI ===")
    rekap_coa = df_uji.groupby(['kode_akun_groundtruth', 'kategori_groundtruth']).agg(
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
