"""BRI dan BSI: pipeline harus OK terhadap ringkasan dokumen + rantai saldo per baris.
Dilewati bila PDF tidak ada di data/raw/<bank>/ ."""
import glob
import os
import unittest

from src.pipeline_digital import process_pdf

ROOT = os.path.dirname(os.path.dirname(__file__))
RAW = os.path.join(ROOT, "data", "raw")


def _pdfs(bank):
    return sorted(glob.glob(os.path.join(RAW, bank, f"{bank}_0*.pdf")))


class _Dasar:
    bank = None

    def setUp(self):
        if not _pdfs(self.bank):
            self.skipTest(f"PDF {self.bank} tidak ditemukan di {RAW}")

    def test_semua_ok(self):
        for p in _pdfs(self.bank):
            with self.subTest(os.path.basename(p)):
                h = process_pdf(p)
                self.assertEqual(h["bank"], self.bank)
                self.assertEqual(h["status"], "OK", h["masalah"])
                self.assertTrue(h["transaksi"])
                self.assertTrue(h["tabel_bbox"])
                self.assertTrue(h["no_rekening"])


class TestBRI(_Dasar, unittest.TestCase):
    bank = "bri"

    def test_nilai_contoh(self):
        p = os.path.join(RAW, "bri", "bri_01.pdf")
        if not os.path.exists(p):
            self.skipTest("bri_01.pdf tidak ada")
        t = process_pdf(p)["transaksi"]
        self.assertEqual(len(t), 38)
        self.assertEqual((t[0]["waktu_transaksi"], t[0]["debit"], t[0]["kredit"], t[0]["saldo"]),
                         ("2026-09-01T09:10:01", 40987.0, 0.0, 591041.22))
        self.assertEqual(t[2]["kredit"], 2750000.0)

    def test_uraian_dua_baris(self):
        p = os.path.join(RAW, "bri", "bri_03.pdf")
        if not os.path.exists(p):
            self.skipTest("bri_03.pdf tidak ada")
        ket = [r["keterangan"] for r in process_pdf(p)["transaksi"] if "SHOPEE - 128081219712004" in r["keterangan"]]
        self.assertEqual(len(ket), 1)
        self.assertTrue(ket[0].endswith("via BRImo"))


class TestBSI(_Dasar, unittest.TestCase):
    bank = "bsi"

    def test_jumlah_baris(self):
        # jumlah baris = nomor urut terakhir di kolom "No"
        harapan = {"bsi_01": 32, "bsi_02": 22, "bsi_03": 54, "bsi_04": 22, "bsi_05": 14}
        for nama, n in harapan.items():
            p = os.path.join(RAW, "bsi", nama + ".pdf")
            if not os.path.exists(p):
                continue
            with self.subTest(nama):
                self.assertEqual(len(process_pdf(p)["transaksi"]), n)

    def test_debit_tanda_minus(self):
        p = os.path.join(RAW, "bsi", "bsi_01.pdf")
        if not os.path.exists(p):
            self.skipTest("bsi_01.pdf tidak ada")
        t = process_pdf(p)["transaksi"][1]
        self.assertEqual((t["debit"], t["kredit"], t["waktu_transaksi"]), (10000.0, 0.0, "2026-09-02T01:15"))


class TestIdentifikasiSemua(unittest.TestCase):
    def test_bank_dikenali(self):
        for bank in ("bca", "bri", "bsi"):
            for p in _pdfs(bank):
                with self.subTest(os.path.basename(p)):
                    self.assertEqual(process_pdf(p)["bank"], bank)


if __name__ == "__main__":
    unittest.main()