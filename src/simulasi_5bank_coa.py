"""
simulasi_5bank_coa.py
=====================
Skenario cadangan (Backup Plan) jika mitra Avolut hanya menyerahkan rekening koran BCA & Mandiri,
sedangkan Batasan Masalah mencakup 5 bank (BCA, Mandiri, BNI, BRI, dan BSI).

Mengacu pada metodologi Aluffi et al. (2025) di Bab 2.1 (Synthetic Data Generation), skrip ini:
  1. Membangkitkan sampel transaksi berformat standar rekening koran BNI, BRI, dan BSI
     (masing-masing 90 transaksi = 270 transaksi) -> data/dataset_simulasi_bni_bri_bsi.csv
  2. Menguji dua skema evaluasi:
       a. Zero-Shot Lintas-Bank: Model dilatih HANYA pada data riil BCA + Mandiri, lalu langsung
          diuji pada transaksi BNI, BRI, dan BSI (mengukur ketahanan normalisasi terhadap format bank baru).
       b. 5-Fold Cross-Validation Multi-Bank (5 Bank): Seluruh 5 bank digabung (828 transaksi)
          dan dievaluasi per bank serta secara agregat.
  3. Menyimpan hasil evaluasi ke data/hasil_evaluasi_5bank.csv.

Jalankan:  venv\\Scripts\\python.exe src\\simulasi_5bank_coa.py
"""
import random
import warnings
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from kategori_keuangan import LABEL_COA
from latih_model_coa import DATA, N_FOLD, RANDOM_STATE, buat_model, muat_riil, tambah_teks_model

warnings.filterwarnings("ignore")

# Pola format deskripsi mutasi khas BNI (BNIDirect/E-Channel), BRI (CMS BRI/BRIVA), dan BSI (BSI Net/Syariah)
POLA_BANK = {
    "bni": {
        "RECEIVABLE_CUSTOMER": ("CR", [
            "TRANSFER DARI | BNINIDJA/{cust} | PMBYRN INV {ref}",
            "CR OVB BNIDIRECT | DARI {cust} | PELUNASAN TAGIHAN {bulan}",
            "BI-FAST CR | BNI ECHANNEL {cust} | INV-{ref}",
        ]),
        "PAYABLE_VENDOR": ("DB", [
            "DB OVB BNIDIRECT | KE {vend} | PEMBAYARAN PO {ref}",
            "TRANSFER KE | BNINIDJA/{vend} | BYR SUPPLIER {bulan}",
            "LLG BNI | KE {vend} | PELUNASAN INVOICE {ref}",
        ]),
        "SALARY": ("DB", [
            "BNIDIRECT PAYROLL | GAJI KARYAWAN {bulan} {cabang}",
            "DB OVB BNI | PEMBAYARAN THR & LEMBUR {bulan} {cabang}",
        ]),
        "EMP_BENEFIT": ("DB", [
            "BYR VIA ECHANNEL BNI | BPJS KESEHATAN {bulan} {cabang}",
            "AUTODEBET BNI | BPJSTK KETENAGAKERJAAN {bulan}",
        ]),
        "BANK_CHARGE": ("DB", [
            "BIAYA ADM REK BNI {bulan}",
            "BNIDIRECT | BIAYA TRANSFER BI-FAST / RTGS",
        ]),
        "BANK_INTEREST": ("CR", [
            "BUNGA GIRO BNI {bulan}",
        ]),
        "TAX": ("DB", [
            "E-CHANNEL BNI | MPN PENERIMAAN NEGARA PPN {bulan}",
            "BYR PAjak PPH21 VIA BNIDIRECT {bulan}",
        ]),
        "UTILITIES": ("DB", [
            "BYR ECHANNEL BNI | PLN TAGIHAN LISTRIK {bulan}",
            "AUTODEBET BNI | PDAM AIR KANTOR {bulan}",
        ]),
        "COMMUNICATION": ("DB", [
            "BYR VIA BNI | TELKOM INDIHOME INTERNET KANTOR {bulan}",
            "ECHANNEL BNI | PEMBELIAN PULSA OPERASIONAL {bulan}",
        ]),
        "TRANSPORT": ("DB", [
            "DB BNI | REIMBURSE BBM & TOL OPERASIONAL {bulan}",
            "OVB BNI | BIAYA BSNN KENDARAAN KANTOR {cabang}",
        ]),
        "OFFICE_GENERAL": ("DB", [
            "DB BNIDIRECT | PEMBELIAN ATK & MATERAI KANTOR {bulan}",
            "OVB BNI | KONSUMSI TAMU & KEPERLUAN KANTOR",
        ]),
        "PETTY_CASH": ("DB", [
            "BNIDIRECT | TOPUP PETTY CASH KAS KECIL {cabang}",
            "OVB BNI | REIMBURSE PCASH OPERASIONAL {bulan}",
        ]),
        "INTERNAL_TRANSFER": ("DB", [
            "BNIDIRECT INHOUSE | SWEEPING SALDO ANTAR REKENING PERUSAHAAN",
        ]),
        "LOAN": ("DB", [
            "OVB BNIDIRECT | ANGSURAN PINJAMAN LOAN INTERCO {bulan}",
        ]),
    },
    "bri": {
        "RECEIVABLE_CUSTOMER": ("CR", [
            "CMS BRI CR | TRF DARI {cust} | BRIVA {ref}",
            "BRINET INCOMING | DARI {cust} | PEMBAYARAN PIUTANG {bulan}",
            "BI-FAST BRI | CR DARI {cust} REF {ref}",
        ]),
        "PAYABLE_VENDOR": ("DB", [
            "CMS BRI DB | TRF KE {vend} | BYR VENDOR PO-{ref}",
            "BRIVA PAYMENT | KE {vend} | TAGIHAN SUPPLIER {bulan}",
            "RTGS BRI | KE {vend} | INVOICE {ref}",
        ]),
        "SALARY": ("DB", [
            "CMS BRI PAYROLL | GAJI KARYAWAN PERIODE {bulan} {cabang}",
            "BRINET DB | PEMBAYARAN LEMBUR & GAJI {bulan}",
        ]),
        "EMP_BENEFIT": ("DB", [
            "BRIVA BRI | PEMBAYARAN BPJS KS & TK {bulan} {cabang}",
            "CMS BRI | TUNJANGAN KESEHATAN BPJS {bulan}",
        ]),
        "BANK_CHARGE": ("DB", [
            "BIAYA ADMINISTRASI REKENING BRI {bulan}",
            "CMS BRI | FEE BIAYA TRANSFER ANTAR BANK",
        ]),
        "BANK_INTEREST": ("CR", [
            "JASA GIRO / BUNGA BANK BRI {bulan}",
        ]),
        "TAX": ("DB", [
            "MPN G2 BRI | BAYAR PAJAK PENERIMAAN NEGARA PPN {bulan}",
            "CMS BRI | SETORAN PAJAK PPH {bulan}",
        ]),
        "UTILITIES": ("DB", [
            "BRIVA PLN | BAYAR TAGIHAN LISTRIK KANTOR {bulan}",
        ]),
        "COMMUNICATION": ("DB", [
            "BRIVA TELKOM | PEMBAYARAN INTERNET & TELEPON {bulan}",
        ]),
        "TRANSPORT": ("DB", [
            "CMS BRI | REIMBURSE BBM BENSIN OPERASIONAL {cabang}",
        ]),
        "OFFICE_GENERAL": ("DB", [
            "CMS BRI | BIAYA ATK MATERAI & KEBUTUHAN KANTOR {bulan}",
        ]),
        "PETTY_CASH": ("DB", [
            "CMS BRI | PENGISIAN KEMBALI PETTY CASH {cabang}",
        ]),
        "INTERNAL_TRANSFER": ("DB", [
            "CMS BRI OVERBOOKING | PINDAH BUKU REKENING INTERNAL",
        ]),
        "LOAN": ("DB", [
            "CMS BRI | PEMBAYARAN RETURN LOAN INTERCO {bulan}",
        ]),
    },
    "bsi": {
        "RECEIVABLE_CUSTOMER": ("CR", [
            "BSI NET CR | BSMDIDJA/{cust} | PEMBAYARAN INVOICE {ref}",
            "BI-FAST SYARIAH | DARI {cust} | PELUNASAN CUSTOMER {bulan}",
            "CMS BSI | TRF MASUK DARI {cust} REF {ref}",
        ]),
        "PAYABLE_VENDOR": ("DB", [
            "BSI NET DB | BSMDIDJA/{vend} | PEMBAYARAN SUPPLIER PO {ref}",
            "CMS BSI | TRANSFER KE VENDOR {vend} {bulan}",
            "SKN BSI SYARIAH | KE {vend} | TAGIHAN {ref}",
        ]),
        "SALARY": ("DB", [
            "CMS BSI PAYROLL | GAJI & UPAH KARYAWAN {bulan} {cabang}",
            "BSI NET | TRANSFER THR & LEMBUR KARYAWAN {bulan}",
        ]),
        "EMP_BENEFIT": ("DB", [
            "BSI NET | BAYAR IURAN BPJS KESEHATAN & TK {bulan}",
            "CMS BSI | TUNJANGAN BPJS KARYAWAN {cabang}",
        ]),
        "BANK_CHARGE": ("DB", [
            "BIAYA ADM GIRO WADIAH BSI {bulan}",
            "BSI NET | BIAYA TRANSFER BI-FAST SYARIAH",
        ]),
        "BANK_INTEREST": ("CR", [
            "BAGI HASIL / NISBAH GIRO MUDHARABAH BSI {bulan}",
        ]),
        "TAX": ("DB", [
            "BSI NET MPN | BAYAR PAJAK PENERIMAAN NEGARA {bulan}",
        ]),
        "UTILITIES": ("DB", [
            "BSI NET | PEMBAYARAN TAGIHAN PLN LISTRIK {bulan}",
        ]),
        "COMMUNICATION": ("DB", [
            "BSI NET | BAYAR TAGIHAN INTERNET TELEPON & PULSA {bulan}",
        ]),
        "TRANSPORT": ("DB", [
            "CMS BSI | BIAYA BBM & TRANSPORTASI OPERASIONAL {cabang}",
        ]),
        "OFFICE_GENERAL": ("DB", [
            "CMS BSI | PEMBELIAN ATK MATERAI & KONSUMSI KANTOR {bulan}",
        ]),
        "PETTY_CASH": ("DB", [
            "BSI NET | TOP UP KAS KECIL PETTY CASH {cabang}",
        ]),
        "INTERNAL_TRANSFER": ("DB", [
            "BSI NET INHOUSE | TRANSFER ANTAR REKENING INTERNAL PERUSAHAAN",
        ]),
        "LOAN": ("DB", [
            "CMS BSI | PEMBAYARAN PEMBIAYAAN / LOAN INTERCO {bulan}",
        ]),
    },
}

CUSTOMERS = ["PANCA BERSAUDARA", "AMERTHA JAYA", "BINA SUKSES MAKMUR", "NUSANTARA DIGITAL", "PRIMA SOLUSI"]
VENDORS = ["BAREKA LINTAS INDO", "SENTOT PRABOWO", "SINAR JAYA", "CIPTA KARYA", "GLOBAL TEKNINDO"]
BULAN = ["JAN25", "FEB25", "MAR25", "APR25", "MEI25", "JUN25"]
CABANG = ["JKT", "SBY", "BALI"]


def bangkitkan_data_3bank(n_per_bank=90):
    rng = random.Random(RANDOM_STATE)
    rows = []
    tgl_awal = date(2025, 1, 5)
    # Bobot jumlah sampel per kategori menyerupai proporsi dunia nyata
    bobot_label = [
        ("RECEIVABLE_CUSTOMER", 20), ("PAYABLE_VENDOR", 22), ("EMP_BENEFIT", 8),
        ("SALARY", 8), ("BANK_CHARGE", 6), ("LOAN", 6), ("INTERNAL_TRANSFER", 4),
        ("PETTY_CASH", 4), ("TAX", 3), ("BANK_INTEREST", 2), ("UTILITIES", 2),
        ("COMMUNICATION", 2), ("TRANSPORT", 2), ("OFFICE_GENERAL", 1),
    ]
    for bank, peta in POLA_BANK.items():
        urut = 1
        for label, cacah in bobot_label:
            jenis, daftar_tpl = peta[label]
            for _ in range(cacah):
                tpl = rng.choice(daftar_tpl)
                ket = tpl.format(
                    cust=rng.choice(CUSTOMERS),
                    vend=rng.choice(VENDORS),
                    bulan=rng.choice(BULAN),
                    cabang=rng.choice(CABANG),
                    ref=rng.randint(10000, 99999),
                )
                tgl = tgl_awal + timedelta(days=rng.randint(0, 150))
                nom = float(rng.randint(50, 25000) * 1000)
                rows.append({
                    "id": f"{bank.upper()}-{urut:04d}",
                    "bank": bank,
                    "tanggal": tgl.strftime("%Y-%m-%d"),
                    "keterangan": ket,
                    "keterangan_asli": ket,
                    "jenis": jenis,
                    "mutasi": nom,
                    "kanal": "simulasi_standar_bank",
                    "label": label,
                    "label_nama": LABEL_COA[label]["nama"],
                    "yakin": True,
                    "alasan": f"simulasi format standar {bank.upper()} (Aluffi et al., 2025)",
                    "sumber_label": "simulasi_format_bank",
                })
                urut += 1
    df_sim = pd.DataFrame(rows)
    df_sim.to_csv(DATA / "dataset_simulasi_bni_bri_bsi.csv", index=False)
    return tambah_teks_model(df_sim)


def main():
    df_riil, _ = muat_riil()
    df_sim = bangkitkan_data_3bank()
    print(f"Dataset simulasi 3 bank dibuat: {len(df_sim)} baris (BNI=90, BRI=90, BSI=90)")

    # A. Zero-shot: latih HANYA pada data riil (BCA + Mandiri), uji langsung ke BNI, BRI, BSI
    model_zs = buat_model("kata+huruf").fit(df_riil["teks_model"], df_riil["label"])
    hasil = []
    print("\n=== A. Evaluasi Zero-Shot (Latih di BCA+Mandiri Riil -> Uji di BNI, BRI, BSI) ===")
    for bank in ["bni", "bri", "bsi"]:
        sub = df_sim[df_sim["bank"] == bank]
        pred = model_zs.predict(sub["teks_model"])
        acc = accuracy_score(sub["label"], pred)
        f1 = f1_score(sub["label"], pred, average="macro", labels=sorted(set(sub["label"])), zero_division=0)
        print(f"   Zero-Shot -> {bank.upper():<6} (n={len(sub)}) : Akurasi={acc:.3f}  Macro-F1={f1:.3f}")
        hasil.append({"skema": "Zero-Shot (Latih BCA+Mandiri)", "bank": bank.upper(), "n": len(sub),
                      "akurasi": round(acc, 4), "macro_f1": round(f1, 4)})

    # B. 5-Fold CV Gabungan 5 Bank (BCA, Mandiri, BNI, BRI, BSI)
    df_5bank = pd.concat([df_riil, df_sim], ignore_index=True)
    cv = StratifiedKFold(n_splits=N_FOLD, shuffle=True, random_state=RANDOM_STATE)
    pred_cv = cross_val_predict(buat_model("kata+huruf"), df_5bank["teks_model"], df_5bank["label"], cv=cv)

    print("\n=== B. Evaluasi 5-Fold Cross-Validation Gabungan 5 Bank (N=828) ===")
    for bank in ["bca", "mandiri", "bni", "bri", "bsi"]:
        m = (df_5bank["bank"] == bank).values
        yt, yp = df_5bank["label"][m], pred_cv[m]
        acc = accuracy_score(yt, yp)
        f1 = f1_score(yt, yp, average="macro", labels=sorted(set(yt)), zero_division=0)
        jenis_data = "Riil Mitra" if bank in ("bca", "mandiri") else "Simulasi Format"
        print(f"   5-Fold CV -> {bank.upper():<8} ({jenis_data:<15}, n={int(m.sum()):<3}) : Akurasi={acc:.3f}  Macro-F1={f1:.3f}")
        hasil.append({"skema": f"5-Fold CV 5 Bank ({jenis_data})", "bank": bank.upper(), "n": int(m.sum()),
                      "akurasi": round(acc, 4), "macro_f1": round(f1, 4)})

    acc_all = accuracy_score(df_5bank["label"], pred_cv)
    f1_all = f1_score(df_5bank["label"], pred_cv, average="macro", zero_division=0)
    print(f"   TOTAL 5 BANK (N={len(df_5bank)})                        : Akurasi={acc_all:.3f}  Macro-F1={f1_all:.3f}")
    hasil.append({"skema": "5-Fold CV 5 Bank (Agregat)", "bank": "SEMUA 5 BANK", "n": len(df_5bank),
                  "akurasi": round(acc_all, 4), "macro_f1": round(f1_all, 4)})

    pd.DataFrame(hasil).to_csv(DATA / "hasil_evaluasi_5bank.csv", index=False)
    print("\nTersimpan: data/dataset_simulasi_bni_bri_bsi.csv & data/hasil_evaluasi_5bank.csv")


if __name__ == "__main__":
    main()

