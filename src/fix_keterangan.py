import pandas as pd
import re

df = pd.read_csv('../data/bca_transaksi_riil_2023.csv')

def bersihkan(teks):
    teks = re.sub(r'\bCR\b', '', teks)
    teks = re.sub(r'\bDB\b', '', teks)
    teks = re.sub(r'\s+', ' ', teks).strip()
    return teks

df['keterangan'] = df['keterangan'].apply(bersihkan)
df.to_csv('../data/bca_transaksi_riil_2023.csv', index=False)

print("Selesai, contoh 5 baris pertama setelah dibersihkan:")
print(df[['tanggal', 'jenis', 'keterangan']].head())