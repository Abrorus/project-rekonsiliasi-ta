"""Profil per bank: SEMUA aturan yang berbeda antar bank ada di sini sebagai data.

Normalizer dan balance tidak boleh berisi kondisi `if bank == ...`.
Menambah bank baru = menambah satu entri di PROFILES.

Status:
- bca, bri, bsi : lengkap (format sudah diverifikasi dari PDF sampel).
- bni, mandiri  : ready=False untuk normalizer digital; diproses pipeline_scan (langkah 5), lihat catatan di entri.
"""

# Pola waktu memakai named group: d, m, y (2 atau 4 digit), H, M, S (opsional).
# Presisi output mengikuti group yang ada (tanggal saja / sampai menit / sampai detik).

# Penanda identitas bank: semua penanda harus ada di teks header tabel halaman pertama
# (dibandingkan huruf kecil, spasi dilipat). Dipakai bank_identifier.
PROFILES = {
    "bca": {
        "ready": True,
        "layout": "words",
        "id_markers": ["tanggal", "keterangan", "cbg", "mutasi", "saldo"],
        "locale": "us",                 # 16,561,371.00
        "amount_mode": "mutasi_label",  # satu kolom MUTASI; debit berlabel "DB", kredit tanpa label
        "debit_label": "DB",
        "waktu_patterns": [r"^(?P<d>\d{2})/(?P<m>\d{2})$"],
        "year_source": "periode",       # tahun dari "PERIODE : JULI 2023"
        "saldo_per_row": False,         # saldo hanya tercetak di sebagian baris -> dihitung
        "drop_patterns": [r"^SALDO AWAL"],
        "headers": {
            "waktu": ["tanggal"],
            "keterangan": ["keterangan"],
            "cabang": ["cbg"],
            "mutasi": ["mutasi"],
            "saldo": ["saldo"],
        },
    },
    "bri": {
        "ready": True,
        "layout": "words",
        "id_markers": ["uraian transaksi", "teller", "debet", "kredit", "saldo"],
        "locale": "us",                 # 40,987.00
        "amount_mode": "debit_kredit",
        "waktu_patterns": [
            r"^(?P<d>\d{2})/(?P<m>\d{2})/(?P<y>\d{2}) (?P<H>\d{2}):(?P<M>\d{2}):(?P<S>\d{2})$"
        ],
        "year_source": "in_cell",
        "saldo_per_row": True,
        "drop_patterns": [],
        "headers": {
            "waktu": ["tanggal transaksi transaction date", "tanggal transaksi"],
            "keterangan": ["uraian transaksi transaction description", "uraian transaksi"],
            "teller": ["teller user id", "teller"],
            "debit": ["debet debit", "debet", "debit"],
            "kredit": ["kredit credit", "kredit", "credit"],
            "saldo": ["saldo balance", "saldo"],
        },
    },
    "bsi": {
        "ready": True,
        "layout": "grid",
        "id_markers": ["waktu", "no.referensi", "nama pengirim", "bank pengirim", "saldo riil"],
        "locale": "us",                 # 6,582,644.00 ; debit berakhiran "-" (10,000.00-)
        "amount_mode": "debit_kredit",
        "waktu_patterns": [
            r"^(?P<d>\d{2})-(?P<m>\d{2})-(?P<y>\d{4})\s+(?P<H>\d{2})\.(?P<M>\d{2})$"
        ],
        "year_source": "in_cell",
        "saldo_per_row": True,
        "drop_patterns": [],
        "headers": {
            "no": ["no"],
            "waktu": ["waktu transaksi"],
            "referensi": ["no.referensi"],
            "pengirim": ["nama pengirim"],
            "bank_pengirim": ["bank pengirim"],
            "penerima": ["nama penerima"],
            "bank_penerima": ["bank penerima"],
            "keterangan": ["deskripsi"],
            "debit": ["debet"],
            "kredit": ["kredit"],
            "saldo": ["saldo riil"],
            "kode": ["kode"],
        },
    },
    # Bank scan (BNI, Mandiri) TIDAK lewat normalizer/profile digital: ocr_scan + scan_parse +
    # balance.koreksi_dp di pipeline_scan. Entri ini hanya mencatat format agar dokumentasi satu tempat.
    "bni": {"ready": False, "layout": "scan", "locale": "us", "amount_mode": "signed", "desimal": 0,
            "kolom": ["Tanggal & Waktu", "Rincian Transaksi", "Nominal", "Saldo"],
            "id_scan": "kata header 'Rincian' (tanpa 'Keterangan')", "headers": {}},
    "mandiri": {"ready": False, "layout": "scan", "locale": "id", "amount_mode": "signed", "desimal": 2,
                "kolom": ["No", "Tanggal", "Keterangan", "Nominal", "Saldo"],
                "id_scan": "kata header 'Keterangan' (tanpa 'Rincian')", "headers": {}},
}


def get_profile(key):
    k = str(key).lower()
    if k not in PROFILES:
        raise KeyError(f"Profil bank tidak dikenal: {key!r}")
    return PROFILES[k]