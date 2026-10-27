# Kamus Istilah & Singkatan Perbankan Indonesia
# Ini masih versi awal (v0.1) — nanti diupdate kalau Avolut kasih data riil

KAMUS_SINGKATAN = {
    "TRF": "Transfer",
    "TRSFR": "Transfer",
    "BI-FAST": "Transfer BI-FAST",
    "RTGS": "Transfer RTGS",
    "KLR": "Kliring",
    "BYR": "Bayar",
    "PMBYRN": "Pembayaran",
    "PMBYRAN": "Pembayaran",
    "ADM": "Biaya Administrasi",
    "BSNN": "Bensin/BBM Operasional",
    "OPR": "Operasional",
    "GJ": "Gaji",
    "LSTRK": "Listrik",
    "TLP": "Telepon/Internet",
    "SW": "Setor Warkat",
    "KRD": "Kredit",
    "DB": "Debit",
    "INV": "Invoice",
    "PO": "Purchase Order",
    "VND": "Vendor",
    "CUST": "Customer",
}

CONTOH_VENDOR = [
    "PT Sinar Jaya", "CV Maju Bersama", "PT Anugerah Sentosa",
    "Toko Berkah", "PT Cipta Karya", "CV Sumber Rejeki",
    "PT Karya Mandiri", "UD Sejahtera", "PT Global Teknindo",
]

CONTOH_CUSTOMER = [
    "PT Nusantara Digital", "CV Prima Solusi", "PT Delta Teknologi",
    "Bapak Andi Wijaya", "Ibu Siti Rahayu", "PT Cahaya Abadi",
]


# =====================================================================
# TAMBAHAN v0.2  -  istilah dari data riil (rekening koran BCA 2023 & Mandiri dummy 2025)
# Dipakai oleh latih_model_coa.py. Kunci HARUS huruf kecil.
# Tanda (?) = tebakan dari konteks, WAJIB dikonfirmasi ke Pak Depta / staf keuangan.
# =====================================================================
import re

KAMUS_RIIL = {
    # singkatan -> bentuk baku (boleh lebih dari satu kata)
    "payroll": "gaji", "gj": "gaji",
    "lmbr": "lembur",
    "ks": "kesehatan",                      # "BPJS KS" = BPJS Kesehatan
    "bpjstk": "bpjs tk", "pjstk": "bpjs tk",
    "rembes": "reimburse",
    "rturn": "return", "retur": "return",
    "ln": "loan", "qln": "loan",            # (?) "LN interco", "Rturn LN" -> loan antar perusahaan
    "intrco": "interco",
    "pcash": "petty cash", "pecash": "petty cash",
    "tup": "topup",
    "srgm": "seragam",
    "smbangan": "sumbangan",
    "bensin": "bbm", "bsnn": "bbm",
    "byr": "bayar", "pmbyrn": "pembayaran", "pemby": "pembayaran",
    "inv": "invoice", "aym": "ayam",
    "lstrk": "listrik", "tlp": "telepon", "adm": "administrasi",
    "ope": "operasional", "opr": "operasional",
}

# kata yang dibuang karena tidak menentukan kategori (boilerplate bank, bulan, kode lokasi)
STOPWORDS_RIIL = set("""
trsf trf transfer banking via mcm inhousetrf fee ke dari kbb switching bifast bi fast inc gl
cenaidja bmriidja bninidja bbijidja rtgs llg ref no ppu tanggal tgl
pt cv ud toko bapak ibu px
jan feb mar apr mei jun jul agu agt ags sep okt nov des
januari februari maret juni juli agustus september oktober november desember
lekko
jakarta jkt bali sby surabaya jombang jember jmber ssr bbg mbs cta ces def airmas
""".split())
# catatan: 'lekko' = artefak anonimisasi di file dummy; kode lokasi/cabang (ssr, bbg, mbs, ...) = tebakan (?)


def normalisasi_teks(teks):
    """Rapikan teks keterangan transaksi untuk model: huruf kecil, buang angka/simbol,
    ganti singkatan memakai KAMUS_RIIL, buang stopword."""
    t = str(teks).lower()
    t = re.sub(r"\d+", " ", t)          # angka (tanggal, nominal, nomor referensi) tidak informatif
    t = re.sub(r"[^a-z\s]", " ", t)
    hasil = []
    for tok in t.split():
        for kata in KAMUS_RIIL.get(tok, tok).split():
            if kata not in STOPWORDS_RIIL and len(kata) > 1:
                hasil.append(kata)
    return " ".join(hasil)