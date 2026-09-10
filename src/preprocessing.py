import pandas as pd
import re

def normalize_text(text):
    text = str(text).lower()                    # samain jadi huruf kecil semua
    text = re.sub(r'[^a-z\s]', ' ', text)        # buang angka & simbol, sisain huruf & spasi
    text = re.sub(r'\s+', ' ', text).strip()     # rapiin spasi ganda jadi satu
    return text

def tokenize(text):
    return text.split()

def main():
    df = pd.read_csv('../data/dataset_sintesis_v1.csv')

    df['teks_normalisasi'] = df['keterangan'].apply(normalize_text)
    df['tokens'] = df['teks_normalisasi'].apply(tokenize)
    df['jumlah_token'] = df['tokens'].apply(len)

    output_path = '../data/dataset_preprocessed_v1.csv'
    df.to_csv(output_path, index=False)

    print(f"Berhasil normalisasi & tokenisasi {len(df)} baris ke {output_path}")
    print(df[['keterangan', 'teks_normalisasi', 'tokens']].head())

if __name__ == '__main__':
    main()