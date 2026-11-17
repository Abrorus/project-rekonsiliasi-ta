import glob
import os
import unittest

from src.deduplicator import deduplicate_records


def r(waktu="2023-07-07", d=0.0, k=100.0, s=100.0, rek="111", bank="bca", src="a.pdf"):
    return {"bank": bank, "no_rekening": rek, "source_file": src, "waktu_transaksi": waktu,
            "keterangan": "x", "debit": d, "kredit": k, "saldo": s}


class TestDedup(unittest.TestCase):
    def test_duplikat_antar_file_dibuang(self):
        hasil, lap = deduplicate_records([r(src="a.pdf"), r(src="b.pdf")], return_report=True)
        self.assertEqual(len(hasil), 1)
        self.assertEqual(hasil[0]["source_file"], "a.pdf")
        self.assertEqual(lap["dibuang"], 1)
        self.assertEqual(lap["rincian"][0]["dibuang_dari"], "b.pdf")

    def test_saldo_membedakan_transaksi_sama_hari_sama(self):
        a, b = r(s=100.0), r(s=200.0)
        self.assertEqual(len(deduplicate_records([a, b])), 2)

    def test_rekening_berbeda_tidak_digabung(self):
        self.assertEqual(len(deduplicate_records([r(rek="1"), r(rek="2")])), 2)

    def test_bank_berbeda_tidak_digabung(self):
        self.assertEqual(len(deduplicate_records([r(bank="bca"), r(bank="bri")])), 2)

    def test_tanpa_rekening_dipertahankan(self):
        self.assertEqual(len(deduplicate_records([r(rek=None), r(rek=None)])), 2)

    def test_pembulatan(self):
        self.assertEqual(len(deduplicate_records([r(s=100.0), r(s=100.0000001)])), 1)

    def test_kosong_dan_urutan(self):
        self.assertEqual(deduplicate_records([]), [])
        x = [r(waktu="2023-07-01", s=1.0), r(waktu="2023-07-02", s=2.0)]
        self.assertEqual(deduplicate_records(x), x)


class TestDedupData(unittest.TestCase):
    def test_periode_tumpang_tindih_bsi(self):
        """bsi_01 (1-17 Sep) dan bsi_03 (1-30 Sep) tumpang tindih -> duplikat harus terdeteksi."""
        raw = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw", "bsi")
        p1, p3 = os.path.join(raw, "bsi_01.pdf"), os.path.join(raw, "bsi_03.pdf")
        if not (os.path.exists(p1) and os.path.exists(p3)):
            self.skipTest("PDF BSI tidak ada")
        from src.pipeline_digital import process_pdf
        a, b = process_pdf(p1), process_pdf(p3)
        unik, lap = deduplicate_records(a["transaksi"] + b["transaksi"], return_report=True)
        self.assertGreater(lap["dibuang"], 0)
        self.assertEqual(lap["akhir"], len(a["transaksi"]) + len(b["transaksi"]) - lap["dibuang"])


if __name__ == "__main__":
    unittest.main()