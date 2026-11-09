"""Uji penerimaan BCA: baris mentah (fixture) -> normalizer -> saldo -> cocok dengan GT.

Bagian footer selalu jalan. Bagian GT dilewati bila folder GT tidak ditemukan.
Ubah GT_DIR bila lokasi GT di repo berbeda.
"""
import json
import os
import unittest

from src.balance import periksa_file
from src.normalizer import normalize_data
from tests.fixture_util import daftar_fixture, f, muat_fixture

ROOT = os.path.dirname(os.path.dirname(__file__))
GT_DIR = os.path.join(ROOT, "data", "ground_truth", "bca")


def _norm(s):
    return " ".join(str(s).split())


def _proses(nama):
    fx = muat_fixture("bca", nama)
    m = fx["meta"]
    recs = normalize_data(fx["rows"], "bca", dict(m, source_file=fx["file"]))
    return periksa_file(recs, f(m["saldo_awal"]), f(m["saldo_akhir"]), f(m["mutasi_db"]),
                        f(m["mutasi_cr"]), m["n_db"], m["n_cr"])


class TestBCA(unittest.TestCase):
    def test_ada_fixture(self):
        self.assertEqual(len(daftar_fixture("bca")), 6)

    def test_footer_cocok(self):
        for nama in daftar_fixture("bca"):
            with self.subTest(nama):
                _, rep = _proses(nama)
                self.assertEqual(rep["status"], "OK", rep["masalah"])

    def test_kontinuitas_bulan(self):
        prev = None
        for nama in daftar_fixture("bca"):
            m = muat_fixture("bca", nama)["meta"]
            if prev is not None:
                self.assertEqual(m["saldo_awal"], prev, nama)
            prev = m["saldo_akhir"]

    def test_sama_dengan_gt(self):
        if not os.path.isdir(GT_DIR):
            self.skipTest(f"GT tidak ditemukan di {GT_DIR}")
        for nama in daftar_fixture("bca"):
            with self.subTest(nama):
                recs, _ = _proses(nama)
                with open(os.path.join(GT_DIR, nama + "_content.json"), encoding="utf-8") as fh:
                    gt = json.load(fh)["transactions"]
                self.assertEqual(len(recs), len(gt))
                for i, (r, g) in enumerate(zip(recs, gt), 1):
                    self.assertEqual(r["waktu_transaksi"], g["waktu_transaksi"], f"baris {i}")
                    self.assertEqual(r["keterangan"], _norm(g["keterangan"]), f"baris {i}")
                    self.assertAlmostEqual(r["debit"], g["debit"], 2, f"baris {i}")
                    self.assertAlmostEqual(r["kredit"], g["kredit"], 2, f"baris {i}")
                    self.assertAlmostEqual(r["saldo"], g["saldo"], 2, f"baris {i}")


if __name__ == "__main__":
    unittest.main()