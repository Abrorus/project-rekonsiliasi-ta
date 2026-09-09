import random
import csv
from datetime import date, timedelta
from kamus_istilah import KAMUS_SINGKATAN, CONTOH_VENDOR, CONTOH_CUSTOMER
from kategori_keuangan import KATEGORI

random.seed(42)  # biar hasilnya konsisten tiap dijalankan

# Template narasi per kategori (pakai singkatan biar mirip data bank asli)
TEMPLATES = {
    "6-1100": ["ADM RIB {bulan}", "BIAYA ADM {bulan}"],
    "6-2200": ["PMBYRN LSTRK {vendor}", "BYR TAGIHAN LISTRIK {vendor}"],
    "6-2300": ["PMBYRN TLP {vendor}", "BYR INTERNET {vendor}"],
    "6-3100": ["BSNN OPR {vendor}", "BYR BSNN OPERASIONAL"],
    "6-4000": ["TRF GJ KARYAWAN {bulan}", "PMBYRN GJ {bulan}"],
    "6-5000": ["TRF VND {vendor}", "PO {vendor} REF{ref}"],
    "4-1000": ["TRSFR INV {customer}", "TRF PMBYRN INV {customer}"],
    "4-2000": ["TRF MASUK {customer}", "BI-FAST {customer}"],
    "4-3000": ["PENDAPATAN LAIN {customer}"],
}

BULAN = ["JAN", "FEB", "MAR", "APR", "MEI", "JUN", "JUL", "AGT", "SEP", "OKT", "NOV", "DES"]

def generate_row(tanggal):
    kode_akun = random.choice(list(KATEGORI.keys()))
    info = KATEGORI[kode_akun]
    template = random.choice(TEMPLATES[kode_akun])

    narasi = template.format(
        vendor=random.choice(CONTOH_VENDOR),
        customer=random.choice(CONTOH_CUSTOMER),
        bulan=random.choice(BULAN),
        ref=random.randint(10000, 99999),
    )

    if info["jenis"] == "cash_out":
        nominal = random.randint(50_000, 15_000_000)
        debit, kredit = nominal, 0
    else:
        nominal = random.randint(500_000, 50_000_000)
        debit, kredit = 0, nominal

    return {
        "tanggal": tanggal.strftime("%Y-%m-%d"),
        "keterangan": narasi,
        "debit": debit,
        "kredit": kredit,
        "kode_akun": kode_akun,
        "kategori": info["nama"],
        "jenis": info["jenis"],
    }

def main(jumlah_data=300):
    start_date = date(2026, 1, 1)
    rows = []
    for _ in range(jumlah_data):
        offset = random.randint(0, 240)
        tanggal = start_date + timedelta(days=offset)
        rows.append(generate_row(tanggal))

    rows.sort(key=lambda r: r["tanggal"])

    output_path = "../data/dataset_sintesis_v1.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Berhasil generate {jumlah_data} baris data sintesis ke {output_path}")

if __name__ == "__main__":
    main()