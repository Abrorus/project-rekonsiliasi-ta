"""PDF BCA asli -> extractor harus sama dengan fixture, dan pipeline harus OK vs footer.
Dilewati bila PDF tidak ada di RAW_DIR (ubah bila lokasi berbeda)."""
import os
import unittest

from src.extractors import extract_bca
from src.pipeline_digital import process_pdf
from tests.fixture_util import daftar_fixture, muat_fixture

ROOT = os.path.dirname(os.path.dirname(__file__))
RAW_DIR = os.path.join(ROOT, "data", "raw", "bca")


def _pdf(nama):
    return os.path.join(RAW_DIR, nama + ".pdf")


class TestDigitalBCA(unittest.TestCase):
    def setUp(self):
        if not os.path.isdir(RAW_DIR):
            self.skipTest(f"PDF tidak ditemukan di {RAW_DIR}")

    def test_ekstraksi_sama_dengan_fixture(self):
        for nama in daftar_fixture("bca"):
            with self.subTest(nama):
                rows, meta, _ = extract_bca(_pdf(nama))
                fx = muat_fixture("bca", nama)
                self.assertEqual(rows, fx["rows"])
                self.assertEqual(meta, fx["meta"])

    def test_pipeline_ok(self):
        for nama in daftar_fixture("bca"):
            with self.subTest(nama):
                h = process_pdf(_pdf(nama))
                self.assertEqual(h["bank"], "bca")
                self.assertEqual(h["status"], "OK", h["masalah"])
                self.assertEqual(h["no_rekening"], "6265555903")
                self.assertTrue(h["tabel_bbox"])

    def test_bbox_valid(self):
        h = process_pdf(_pdf("bca_01"))
        for b in h["tabel_bbox"]:
            x0, t, x1, bt = b["bbox"]
            self.assertTrue(x0 < x1 and t < bt)


class TestIdentifier(unittest.TestCase):
    def test_kenali(self):
        from src.bank_identifier import kenali_bank
        self.assertEqual(kenali_bank("TANGGAL KETERANGAN CBG MUTASI SALDO"), "bca")
        self.assertEqual(kenali_bank("Tanggal Transaksi Uraian Transaksi Teller Debet Kredit Saldo"), "bri")
        self.assertEqual(kenali_bank("No Waktu No.Referensi Nama Pengirim Bank Pengirim Saldo Riil"), "bsi")
        self.assertIsNone(kenali_bank("laporan apa saja"))


if __name__ == "__main__":
    unittest.main()