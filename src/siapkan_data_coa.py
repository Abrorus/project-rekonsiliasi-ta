"""
siapkan_data_coa.py
===================
LANGKAH 1 pipeline baru Pool 2 (berbasis CoA asli dari Pak Depta).

Yang dikerjakan skrip ini:
  a. Baca CoA.xlsx, cek apakah label Pool 2 (LABEL_COA) nyambung ke akun di CoA
     -> data/coa_peta_label.csv  (jembatan Pool 2 -> Pool 3 / Mario)
  b. Baca Dummy RK.xlsx (format rekening koran Mandiri), rapikan jadi tabel,
     lalu beri label otomatis pakai aturan kata kunci
  c. Migrasi 337 baris BCA yang sudah kamu label (kode lama 6-5000, dst) ke label baru
  d. Gabung semuanya -> data/data_riil_berlabel_coa.csv
  e. Hasilkan bahan untuk meeting validasi dengan Pak Depta:
       - data/review_catatan_unik.csv           (singkatan/catatan yang masih ragu)
       - data/sampel_validasi_20persen.xlsx     (diisi validator, TANPA label otomatis)
       - data/kunci_label_sampel.csv            (kunci jawaban, simpan sendiri)

Cara jalan (dari folder src, venv aktif):
    python siapkan_data_coa.py

PENTING: label Mandiri & sebagian label BCA adalah "label perak" (silver label):
hasil aturan kata kunci, BELUM divalidasi manusia ahli. Jangan diklaim sebagai ground truth
sebelum divalidasi staf keuangan (min. 20% sampel, Cohen's Kappa >= 0.61 sesuai proposal).
"""
import math
import re
from pathlib import Path

import pandas as pd

from kategori_keuangan import (LABEL_BELUM_PASTI, LABEL_COA, MAP_LAMA_KE_BARU,
                               PEMILIK_REKENING)

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

FILE_COA = DATA / "CoA.xlsx"
FILE_MANDIRI = DATA / "Dummy RK.xlsx"
FILE_BCA_LAMA = DATA / "bca_riil_partial_label.csv"   # hasil label_data_riil.py (kolom kode_akun_final)

RANDOM_STATE = 42
PERSEN_SAMPEL_VALIDASI = 0.20

# ---------------------------------------------------------------------
# A. COA  ->  peta label
# ---------------------------------------------------------------------
def muat_coa():
    coa = pd.read_excel(FILE_COA, dtype=str)
    coa.columns = ["key", "name", "summary", "type"]
    return coa.dropna(subset=["key"])


def buat_peta_coa(coa):
    nama_by_key = dict(zip(coa["key"], coa["name"]))
    tipe_by_key = dict(zip(coa["key"], coa["type"]))
    baris = []
    for label, info in LABEL_COA.items():
        if not info["coa"]:
            baris.append({"label": label, "label_nama": info["nama"], "arah": info["arah"],
                          "coa_key": "", "coa_nama": "", "coa_tipe": "",
                          "status": "BELUM ADA DI COA - tanyakan ke Pak Depta"})
            continue
        for key in info["coa"]:
            ada = key in nama_by_key
            baris.append({"label": label, "label_nama": info["nama"], "arah": info["arah"],
                          "coa_key": key, "coa_nama": nama_by_key.get(key, ""),
                          "coa_tipe": tipe_by_key.get(key, ""),
                          "status": "OK" if ada else "KUNCI TIDAK DITEMUKAN DI COA"})
    return pd.DataFrame(baris)


# ---------------------------------------------------------------------
# B. ATURAN LABEL (kata kunci pada CATATAN transaksi, huruf kecil)
#    format: (label, regex, yakin, alasan)
#    yakin=False berarti kata kuncinya masih tebakan -> masuk daftar tanya Pak Depta
# ---------------------------------------------------------------------
ATURAN = [
    ("BANK_CHARGE", r"\bbiaya adm|biaya transfer|biaya tolakan|biaya surat|biaya txn|\bba jasa|transaction fee", True,
     "kata 'biaya adm / transfer / tolakan'"),
    ("TAX", r"\bppn\b|\bpph\b|\bpajak\b|penerimaan negara|\bdjp\b", True, "kata pajak/PPN/penerimaan negara"),
    ("EMP_BENEFIT", r"bpjs|pjstk|jamsostek|\bbpu\b", True, "kata BPJS"),
    ("SALARY", r"\bgaji|payroll|lembur|lmbr|\bthr|\bupah|honor|insentif|\bbonus", True, "kata gaji/lembur/THR"),
    ("SALARY", r"tkbm", False, "(?) TKBM = tenaga kerja bongkar muat -> upah"),
    ("PETTY_CASH", r"p(e)?cash|petty|rembes|reimburs|kasbon|ksbon", False, "(?) kas kecil / reimburse / kasbon"),
    ("EMP_BENEFIT", r"\btk\b", False, "(?) 'TK' + kode cabang + bulan, diduga BPJS Ketenagakerjaan"),
    ("UTILITIES", r"\bpln\b|listrik|pdam|\btoken\b", True, "kata listrik/PLN/PDAM"),
    ("COMMUNICATION", r"pulsa|telepon|\btelp\b|internet|wifi|indihome|kuota", True, "kata pulsa/telepon/internet"),
    ("TRANSPORT", r"\bbbm\b|bensin|\bsolar\b|parkir|\btol\b|ongkir|transport", True, "kata BBM/bensin/transport"),
    ("REPAIR_MAINT", r"renov|perbaikan|\bservis|\bservice\b|reset printer|maintenance", False,
     "(?) perbaikan/renovasi -> Repair & Maintenance"),
    ("OTHER_EXPENSE", r"sumbangan|smbangan|donasi|parcel|hadiah|disnaker|training|pelatihan|iklan", False,
     "(?) donasi/parcel/hadiah -> Others Expenses"),
    ("OFFICE_GENERAL", r"\batk\b|stampel|stempel|materai|beverage|cleaning|konsumsi|snack|pantry|fotokopi|printing|\bmeals?\b|office cost",
     False, "(?) ATK/konsumsi/kebersihan kantor"),
    ("EMP_BENEFIT", r"seragam|srgm|\bapd\b", False, "(?) perlengkapan karyawan -> Employee Benefit"),
    ("TRAVEL", r"\bdinas\b|tiket|hotel|travel|bustrip|business trip", False, "(?) perjalanan dinas"),
    ("INTERNAL_TRANSFER", r"pindah dana", False, "(?) 'pindah dana' = pemindahan dana antar rekening"),
    ("LOAN", r"\bloan\b|\bq?ln|rturn\s?ln|return\s?ln|interco|intrco|investfee|pinjam|\bkpr\b|cicil", False,
     "(?) LN = loan / pinjaman antar perusahaan"),
]
ATURAN_COMPILED = [(l, re.compile(rx), y, a) for l, rx, y, a in ATURAN]


def cocok_aturan(catatan):
    teks = str(catatan).lower()
    for label, rx, yakin, alasan in ATURAN_COMPILED:
        if rx.search(teks):
            return label, yakin, alasan
    return None


def cek_arah(label, jenis, yakin, alasan):
    """Kalau arah transaksi (CR/DB) tidak lazim untuk label tsb, turunkan keyakinan."""
    arah = LABEL_COA[label]["arah"]
    if (arah == "keluar" and jenis == "CR") or (arah == "masuk" and jenis == "DB"):
        return False, alasan + " | arah " + jenis + " tidak lazim (mungkin pengembalian)"
    return yakin, alasan


# ---------------------------------------------------------------------
# C. PARSER REKENING KORAN MANDIRI (format MCM)
# ---------------------------------------------------------------------
def _to_num(seri):
    return pd.to_numeric(seri.astype(str).str.replace(",", "", regex=False), errors="coerce").fillna(0)


def baca_mandiri_mentah(path):
    raw = pd.read_excel(path, header=None, dtype=object)
    # baris header = baris yang punya sel 'Remark'
    hdr = next(i for i, row in raw.iterrows() if any(str(v).strip() == "Remark" for v in row))
    kolom = {str(v).strip(): j for j, v in raw.iloc[hdr].items() if pd.notna(v)}
    kdate = next(j for nama, j in kolom.items() if "Date" in nama)   # header di file 'PoSSRng Date' (rusak)
    data = raw.iloc[hdr + 1:]
    df = pd.DataFrame({
        "tanggal_raw": data[kdate],
        "remark": data[kolom["Remark"]],
        "ref": data[kolom["Reference No"]],
        "debit": _to_num(data[kolom["Debit"]]),
        "kredit": _to_num(data[kolom["Credit"]]),
        "saldo": _to_num(data[kolom["Balance"]]),
    }).dropna(subset=["tanggal_raw"]).reset_index(drop=True)
    return df


def _ref_mirip_kode(seg):
    s = seg.strip()
    if not s or s == "-":
        return True
    if s in ("99102", "99101", "14200"):
        return True
    return bool(re.fullmatch(r"[0-9A-Z\- ]{8,}", s)) and bool(re.search(r"\d", s))


def _hapus_ulangan_di_ekor(teks):
    """'a b c b c' (ulangan di ekor) -> 'b c'. Dipakai karena kolom Remark mengulang catatan 2-3x."""
    tok = teks.split()
    for k in range(1, len(tok) // 2 + 1):
        if tok[-k:] == tok[-2 * k:-k]:
            return " ".join(tok[-k:])
    return teks


def urai_remark(remark, ref):
    """Kembalikan (catatan, lawan_transaksi, kanal, jenis_baris)."""
    r = str(remark).strip()
    ref = str(ref).strip()

    # --- baris buatan sistem bank (Biaya Adm / Bunga / Pajak) ---
    m = re.match(r"^(Biaya Adm|Bunga|Pajak)\s+\d+", r)
    if m:
        return m.group(1).lower(), "", "sistem_bank", "sistem"

    # --- lawan transaksi ---
    lawan = ""
    m = (re.search(r"\b(?:KE|DARI)\s+(.+?)(?:\s+Transfer\b|\s{2,}|$)", r)
         or re.search(r"[A-Z]{4}IDJA/(.+?)\s+\d{6,}", r)
         or re.search(r"-\s+([A-Z][A-Z .,&]+?)\s*14200", r)
         or re.match(r"^([A-Z][A-Z .,&]+?)\s*-\s*\d+\s+14200$", r))
    if m:
        lawan = re.sub(r"\s+", " ", m.group(1)).strip(" -")

    # --- kanal ---
    if "MCM InhouseTrf" in r:
        kanal = "inhouse"
    elif "BIFAST" in r.upper():
        kanal = "bifast"
    elif re.search(r"[A-Z]{4}IDJA/", r):
        kanal = "antarbank"
    else:
        kanal = "lainnya"

    # --- catatan ---
    if ref and ref != "-" and not re.fullmatch(r"[\d\s]+", ref):
        catatan = ref                       # kolom Reference No sering berisi catatan lengkap
    else:
        pre = re.split(r"MCM InhouseTrf|[A-Z]{4}IDJA/|BIFAST Inc GL-CS", r)[0]
        segmen = [s.strip() for s in re.split(r"\s{2,}|\|", pre)]
        segmen = [s for s in segmen if not _ref_mirip_kode(s) and not s.startswith("- ")]
        catatan = max(segmen, key=len) if segmen else ""
        catatan = _hapus_ulangan_di_ekor(catatan)
    catatan = re.sub(r"\s+", " ", catatan).strip()
    if re.fullmatch(r"[\d ]*", catatan):
        catatan = ""
    return catatan, lawan, kanal, "transaksi"


def beri_label_mandiri(catatan, lawan, jenis, mutasi, jenis_baris):
    """Kembalikan (label, alasan, yakin, sumber)."""
    # 1. baris sistem bank
    if jenis_baris == "sistem":
        if catatan == "biaya adm":
            return "BANK_CHARGE", "baris sistem: Biaya Adm", True, "aturan_kata_kunci"
        return "BANK_INTEREST", f"baris sistem: {catatan}", True, "aturan_kata_kunci"

    # 2. aturan kata kunci pada catatan
    hasil = cocok_aturan(catatan)
    if hasil:
        label, yakin, alasan = hasil
        yakin, alasan = cek_arah(label, jenis, yakin, alasan)
        return label, alasan, yakin, "aturan_kata_kunci"

    # 3. 'pemby' / 'pembayaran' pada uang masuk dari pihak luar = customer bayar
    if jenis == "CR" and re.search(r"\bpemby|\bpembayaran|\btagihan|\binvoice", catatan.lower()):
        return "RECEIVABLE_CUSTOMER", "catatan pembayaran/tagihan + uang masuk", True, "aturan_kata_kunci"

    internal = any(p in lawan.upper() for p in PEMILIK_REKENING["mandiri"])

    # 4. baris tanpa catatan sama sekali
    if catatan == "":
        if not lawan:
            if mutasi <= 10000:
                return "BANK_CHARGE", "baris referensi saja, nominal kecil = biaya transfer antarbank", True, \
                       "aturan_kata_kunci"
            return LABEL_BELUM_PASTI, "baris referensi saja, nominal besar, tujuan tidak diketahui", False, "default"
        if internal:
            return "INTERNAL_TRANSFER", "ke/dari rekening sendiri, tanpa catatan tujuan", False, "default_arah"
        if jenis == "CR":
            return "RECEIVABLE_CUSTOMER", "tanpa catatan, uang masuk dari pihak luar (default arah)", False, "default_arah"
        return "PAYABLE_VENDOR", "tanpa catatan, uang keluar ke pihak luar (default arah)", False, "default_arah"

    # 5. ada catatan tapi tidak dikenali aturan -> tanyakan
    return LABEL_BELUM_PASTI, "catatan tidak dikenali aturan (singkatan baru?)", False, "default"


def proses_mandiri():
    mentah = baca_mandiri_mentah(FILE_MANDIRI)
    baris = []
    for i, r in mentah.iterrows():
        catatan, lawan, kanal, jenis_baris = urai_remark(r["remark"], r["ref"])
        jenis = "CR" if r["kredit"] > 0 else "DB"
        mutasi = float(r["kredit"] if r["kredit"] > 0 else r["debit"])
        label, alasan, yakin, sumber = beri_label_mandiri(catatan, lawan, jenis, mutasi, jenis_baris)
        tgl = pd.to_datetime(str(r["tanggal_raw"]), format="%d/%m/%Y %H:%M:%S", errors="coerce")
        baris.append({
            "id": f"MDR-{i + 1:04d}", "bank": "mandiri",
            "tanggal": tgl.strftime("%Y-%m-%d") if pd.notna(tgl) else "",
            "keterangan": (catatan + " " + lawan).strip() or re.sub(r"\s+", " ", str(r["remark"])).strip(),
            "keterangan_asli": re.sub(r"\s{2,}", " | ", str(r["remark"]).strip()),
            "jenis": jenis, "mutasi": mutasi, "kanal": kanal,
            "label": label, "yakin": yakin, "alasan": alasan, "sumber_label": sumber,
        })
    return propagasi_lawan(pd.DataFrame(baris))


def propagasi_lawan(df):
    """Baris TANPA catatan dari lawan transaksi yang sama dengan baris-baris berlabel eksplisit
    (mis. TRI MITRA SECURINDO berkali-kali berlabel LOAN) diberi label mayoritas lawan tsb.
    Rekening sendiri dikecualikan karena dipakai untuk banyak tujuan."""
    asli = df["keterangan_asli"]
    lawan = asli.str.extract(r"\b(?:KE|DARI)\s+(.+?)(?:\s+Transfer|\s*\||$)")[0]
    lawan = lawan.fillna(asli.str.extract(r"[A-Z]{4}IDJA/(.+?)\s+\d{6,}")[0])
    df["_lawan"] = lawan.str.strip().str.upper()
    milik = [p.upper() for p in PEMILIK_REKENING["mandiri"]]
    bukan_milik = ~df["_lawan"].fillna("").apply(lambda x: any(m in x for m in milik))
    eksplisit = df[(df["sumber_label"] == "aturan_kata_kunci") & df["_lawan"].notna() & bukan_milik
                   & ~df["label"].isin(["BANK_CHARGE", "BANK_INTEREST", LABEL_BELUM_PASTI])]
    # syarat: minimal 2 baris eksplisit dan >= 70% sepakat pada satu label (supaya tidak menebak dari 1 contoh)
    peta = {}
    for lawan_nama, grup in eksplisit.groupby("_lawan"):
        hitung = grup["label"].value_counts()
        if len(grup) >= 2 and hitung.iloc[0] / len(grup) >= 0.7:
            peta[lawan_nama] = hitung.index[0]
    target = df["sumber_label"].eq("default_arah") & df["_lawan"].isin(peta) & bukan_milik
    for i in df[target].index:
        lbl = peta[df.loc[i, "_lawan"]]
        df.loc[i, "label"] = lbl
        df.loc[i, "alasan"] = f"lawan transaksi {df.loc[i, '_lawan']} berlabel {lbl} di baris lain"
        df.loc[i, "sumber_label"] = "propagasi_lawan"
    return df.drop(columns="_lawan")


# ---------------------------------------------------------------------
# D. MIGRASI BCA (label lama -> label baru)
# ---------------------------------------------------------------------
def proses_bca():
    df = pd.read_csv(FILE_BCA_LAMA)
    baris = []
    for i, r in df.iterrows():
        ket = str(r["keterangan"])
        kode = r["kode_akun_final"]
        label = MAP_LAMA_KE_BARU[kode]
        alasan, sumber = f"migrasi dari kode lama {kode}", "migrasi_lama"

        milik_sendiri = any(p in ket.upper() for p in PEMILIK_REKENING["bca"])
        if kode in {"6-5000", "4-2000", "6-9000", "4-5000", "6-1100"} and (milik_sendiri or "SALDO MIN" in ket.upper()):
            label = "INTERNAL_TRANSFER"
            alasan = "nama pemilik rekening / 'saldo min' pada keterangan = transfer ke rekening sendiri"
            sumber = "aturan_kata_kunci"

        tgl = f"{int(r['tahun'])}-{int(r['bulan']):02d}-{r['tanggal'][:2]}"
        baris.append({
            "id": f"BCA-{i + 1:04d}", "bank": "bca", "tanggal": tgl,
            "keterangan": ket, "keterangan_asli": ket,
            "jenis": r["jenis"], "mutasi": float(str(r["mutasi"]).replace(",", "")),
            "kanal": "switching" if "SWITCHING" in ket.upper() else "transfer",
            "label": label, "yakin": True, "alasan": alasan, "sumber_label": sumber,
        })
    return pd.DataFrame(baris)


# ---------------------------------------------------------------------
# E. BAHAN VALIDASI
# ---------------------------------------------------------------------
def buat_sampel_validasi(df):
    pool = df[df["label"] != LABEL_BELUM_PASTI]
    potongan = []
    for label, grup in pool.groupby("label"):
        n = max(1, math.ceil(len(grup) * PERSEN_SAMPEL_VALIDASI))
        potongan.append(grup.sample(n=min(n, len(grup)), random_state=RANDOM_STATE))
    s = pd.concat(potongan).sort_values("id").reset_index(drop=True)

    untuk_validator = s[["id", "bank", "tanggal", "jenis", "mutasi", "keterangan_asli"]].copy()
    untuk_validator["label_validator"] = ""
    daftar_label = pd.DataFrame([{"label": k, "nama": v["nama"], "arah": v["arah"],
                                  "kelompok_akun_CoA": ", ".join(v["coa"]) or "(belum ada di CoA)"}
                                 for k, v in LABEL_COA.items()])
    with pd.ExcelWriter(DATA / "sampel_validasi_20persen.xlsx") as xw:
        untuk_validator.to_excel(xw, sheet_name="Sampel", index=False)
        daftar_label.to_excel(xw, sheet_name="Daftar Label", index=False)
    s[["id", "label"]].rename(columns={"label": "label_otomatis"}).to_csv(
        DATA / "kunci_label_sampel.csv", index=False)
    return len(s)


def buat_review_catatan(df):
    ragu = df[(~df["yakin"]) | (df["label"] == LABEL_BELUM_PASTI)].copy()
    ragu["catatan_kunci"] = ragu["keterangan"].str.lower().str.replace(r"\d+", "", regex=True).str.strip()
    rekap = (ragu.groupby("catatan_kunci")
             .agg(jumlah=("id", "count"), bank=("bank", "first"),
                  contoh_asli=("keterangan_asli", "first"),
                  label_usulan=("label", lambda x: x.value_counts().index[0]),
                  alasan=("alasan", "first"))
             .reset_index().sort_values("jumlah", ascending=False))
    rekap["jawaban_pak_depta"] = ""
    rekap.to_csv(DATA / "review_catatan_unik.csv", index=False)
    return rekap


# ---------------------------------------------------------------------
def main():
    print("=" * 70)
    print("A. Cek peta label -> CoA")
    coa = muat_coa()
    peta = buat_peta_coa(coa)
    peta.to_csv(DATA / "coa_peta_label.csv", index=False)
    print(f"   CoA: {len(coa)} akun ({(coa['summary'] == 'No').sum()} akun daun)")
    masalah = peta[peta["status"] != "OK"]
    for _, r in masalah.iterrows():
        print(f"   ! {r['label']:<20} {r['status']}  {r['coa_key']}")
    print(f"   Peta tersimpan: data/coa_peta_label.csv ({len(peta)} baris)")

    print("=" * 70)
    print("B. Proses Mandiri (Dummy RK.xlsx)")
    mdr = proses_mandiri()
    print(f"   {len(mdr)} baris | CR={int((mdr.jenis == 'CR').sum())} DB={int((mdr.jenis == 'DB').sum())}")

    print("C. Migrasi BCA")
    bca = proses_bca()
    print(f"   {len(bca)} baris")

    gab = pd.concat([bca, mdr], ignore_index=True)
    gab["label_nama"] = gab["label"].map(lambda x: LABEL_COA.get(x, {}).get("nama", "(perlu review)"))
    kolom = ["id", "bank", "tanggal", "keterangan", "keterangan_asli", "jenis", "mutasi", "kanal",
             "label", "label_nama", "yakin", "alasan", "sumber_label"]
    gab[kolom].to_csv(DATA / "data_riil_berlabel_coa.csv", index=False)

    print("=" * 70)
    print("D. Distribusi label (semua bank)")
    tabel = (gab.pivot_table(index="label", columns="bank", values="id", aggfunc="count", fill_value=0)
             .assign(total=lambda t: t.sum(axis=1)).sort_values("total", ascending=False))
    print(tabel.to_string())
    n_ragu = int(((~gab["yakin"]) | (gab["label"] == LABEL_BELUM_PASTI)).sum())
    print(f"\n   Baris yakin (aturan eksplisit) : {int(gab['yakin'].sum())}")
    print(f"   Baris masih ragu / PERLU_REVIEW : {n_ragu}")

    print("=" * 70)
    print("E. Bahan meeting validasi")
    rekap = buat_review_catatan(gab)
    print(f"   data/review_catatan_unik.csv      : {len(rekap)} catatan unik untuk ditanyakan")
    n = buat_sampel_validasi(gab)
    print(f"   data/sampel_validasi_20persen.xlsx: {n} baris (kirim ke validator, TANPA label otomatis)")
    print(f"   data/kunci_label_sampel.csv       : kunci jawaban (simpan sendiri, jangan dikirim)")
    print("\nSelesai. Data gabungan: data/data_riil_berlabel_coa.csv")


if __name__ == "__main__":
    main()