import pandas as pd
import re
from kategori_keuangan import KATEGORI

# Aturan otomatis berdasarkan kata kunci yang sudah pasti jelas
ATURAN_KEYWORD = [
    (r'\bBPJS\s*TK\b', '6-6000'),
    (r'\bBPJS\s*KESEHAT', '6-6000'),
    (r'\bPLN\b', '6-2200'),
    (r'\bBIAYA ADM\b', '6-1100'),
    (r'\bBA JASA E-BANKING\b|\bBIAYA TRANSFER\b', '6-1100'),
    (r'\bPENERIMAAN NEGARA\b', '6-7000'),
    (r'\bND-BIAYA TOLAKAN\b|\bND-LAINNYA\b', '6-8000'),
    (r'\bSETORAN TUNAI\b', '4-4000'),
    (r'\bSWITCHING\b', None),  # ditentukan oleh CR/DB, lihat di bawah
]

KATA_NOISE = {
    'AYAM', 'KARKAS', 'DAGING', 'AYM', 'BELI', 'BAYAR', 'BYR', 'AY',
    'WHOLE', 'HIDUP', 'HDP', 'HD', 'DLL', 'MDM', 'MEATS', 'BLD', 'BLP',
    'INV', 'INVOICE', 'PEMBAYARAN', 'PEMBY', 'PEMINDAHBUKUAN', 'PEMAN',
    'DJA', 'ELIT', 'JASA', 'SEWA', 'CS', 'TEMPAT', 'KALI',
    'PENGISIAN', 'PENGURUSAN', 'PENG', 'SALDO', 'MIN', 'MINIM',
    'KBB', 'KE', 'VIA', 'RTGS', 'LLG', 'REF', 'NO', 'PPU',
    'TANGGAL', 'TGL', 'PT', 'BANK', 'TXN', 'BIAYA', 'OICE',
}

def auto_label(row):
    k = row['keterangan'].upper()
    for pattern, kode in ATURAN_KEYWORD:
        if re.search(pattern, k):
            if kode is None and 'SWITCHING' in k:
                return '4-5000' if row['jenis'] == 'CR' else '6-9000'
            return kode
    return None  # belum bisa ditentukan otomatis

def is_kode_atau_angka(token):
    """True kalau token itu kode referensi/angka, bukan bagian nama."""
    if re.fullmatch(r'[\d.,]+', token):          # murni angka
        return True
    if re.fullmatch(r'[A-Z0-9]{4,8}', token) and re.search(r'\d', token) and re.search(r'[A-Z]', token):
        return True                               # kode campuran huruf-angka, mis. QV8B, 5XSK
    if len(token) <= 2:
        return True                               # sisa 1-2 huruf, biasanya pecahan kode
    return False

def extract_nama_pihak(keterangan):
    k = keterangan.upper()
    for prefix in ['TRSF E-BANKING CR', 'TRSF E-BANKING', 'BYR VIA E-BANKING',
                   'SWITCHING', 'BI-FAST', 'BIF', 'TRANSFER']:
        k = k.replace(prefix, '')

    k = re.sub(r'[^\w\s.]', ' ', k)  # buang simbol selain titik (buat "P.HAR")
    tokens = k.split()

    hasil = [t for t in tokens if t not in KATA_NOISE and not is_kode_atau_angka(t)]
    return ' '.join(hasil).strip()

def main():
    df = pd.read_csv('../data/bca_transaksi_riil_2023.csv')

    df['kode_akun_otomatis'] = df.apply(auto_label, axis=1)
    df['nama_pihak'] = df['keterangan'].apply(extract_nama_pihak)

    n_auto = df['kode_akun_otomatis'].notna().sum()
    n_manual = df['kode_akun_otomatis'].isna().sum()
    print(f"Otomatis terlabel: {n_auto} baris")
    print(f"Perlu keputusan manual: {n_manual} baris\n")

    # Kelompokkan sisa yang belum terlabel berdasarkan nama pihak, urut dari yang paling sering muncul
    sisa = df[df['kode_akun_otomatis'].isna()]
    rekap_nama = sisa.groupby(['nama_pihak', 'jenis']).size().reset_index(name='jumlah_transaksi')
    rekap_nama = rekap_nama.sort_values('jumlah_transaksi', ascending=False)

    print("=== Rekap nama pihak yang perlu kamu putuskan kategorinya ===")
    print(rekap_nama.to_string(index=False))

    # Deteksi nama yang muncul di CR dan DB (pola nggak konsisten, perlu dicek manual)
    nama_cr = set(sisa[sisa['jenis'] == 'CR']['nama_pihak'])
    nama_db = set(sisa[sisa['jenis'] == 'DB']['nama_pihak'])
    nama_anomali = nama_cr & nama_db
    print(f"\n=== Nama yang muncul di CR maupun DB (perlu dicek manual, {len(nama_anomali)} nama) ===")
    print(sorted(n for n in nama_anomali if n.strip()))
    print(f"\n=== Detail 21 baris yang masih perlu keputusan manual ===")
    manual = df[df['kode_akun_final'].isna()][['tanggal', 'keterangan', 'jenis', 'mutasi']]
    print(manual.to_string(index=False))
    manual.to_csv('../data/manual_review.csv', index=False)

    # Terapkan default: CR -> Pembayaran dari Customer, DB -> Pembayaran Vendor/Supplier
    # KECUALI nama yang masuk daftar anomali di atas
    def default_label(row):
        if pd.notna(row['kode_akun_otomatis']):
            return row['kode_akun_otomatis']
        if 'DARBE JAYA ABADI' in row['nama_pihak'] or 'DARBE INTI NUSANTA' in row['nama_pihak']:
            return '4-5000' if row['jenis'] == 'CR' else '6-9000'  # penyesuaian saldo, bukan transaksi bisnis
        if row['nama_pihak'] in nama_anomali:
            return None  # sengaja dibiarkan kosong, keputusan manual
        return '4-2000' if row['jenis'] == 'CR' else '6-5000'

    df['kode_akun_final'] = df.apply(default_label, axis=1)

    n_final_auto = df['kode_akun_final'].notna().sum()
    n_final_manual = df['kode_akun_final'].isna().sum()
    print(f"\nSetelah default rule: {n_final_auto} baris terlabel, {n_final_manual} baris masih perlu manual")

    df.to_csv('../data/bca_riil_partial_label.csv', index=False)
    rekap_nama.to_csv('../data/rekap_nama_untuk_labeling.csv', index=False)
    print("\nTersimpan: data/bca_riil_partial_label.csv dan data/rekap_nama_untuk_labeling.csv")

if __name__ == '__main__':
    main()