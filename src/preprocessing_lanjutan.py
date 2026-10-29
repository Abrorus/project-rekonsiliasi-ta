import pandas as pd
from kamus_istilah import KAMUS_SINGKATAN

# Kata-kata yang mau dibuang karena nggak nentuin kategori transaksi
STOPWORDS = {
    'pt', 'cv', 'ud', 'toko', 'bapak', 'ibu',
    'jan', 'feb', 'mar', 'apr', 'mei', 'jun',
    'jul', 'agt', 'sep', 'okt', 'nov', 'des',
}

# Siapin kamus singkatan versi lowercase, cuma ambil yang hasilnya satu kata
# (biar jumlah token nggak berubah pas di-expand)
KAMUS_LOWER = {
    k.lower(): v.lower()
    for k, v in KAMUS_SINGKATAN.items()
    if ' ' not in v
}

def remove_stopwords(tokens):
    return [t for t in tokens if t not in STOPWORDS]

def lemmatize(tokens):
    return [KAMUS_LOWER.get(t, t) for t in tokens]

def main():
    df = pd.read_csv('../data/dataset_preprocessed_v1.csv')
    df['tokens'] = df['tokens'].apply(eval)  # kolom tokens ke-simpen sebagai teks, balikin jadi list lagi

    df['tokens_bersih'] = df['tokens'].apply(remove_stopwords)
    df['tokens_final'] = df['tokens_bersih'].apply(lemmatize)
    df['teks_final'] = df['tokens_final'].apply(lambda toks: ' '.join(toks))

    output_path = '../data/dataset_preprocessed_v2.csv'
    df.to_csv(output_path, index=False)

    print(f"Berhasil stopword removal & lematisasi {len(df)} baris ke {output_path}")
    print(df[['keterangan', 'tokens', 'teks_final']].head())

if __name__ == '__main__':
    main()