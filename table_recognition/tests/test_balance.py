import unittest

from src.balance import hitung_saldo, periksa_file, validasi_ringkasan


def rec(d=0.0, k=0.0, s=None):
    return {"debit": d, "kredit": k, "saldo": s}


class TestBalance(unittest.TestCase):
    def test_rantai(self):
        r, sel = hitung_saldo([rec(k=100.0), rec(d=30.0), rec(k=5.5)], 10.0)
        self.assertEqual([x["saldo"] for x in r], [110.0, 80.0, 85.5])
        self.assertEqual(sel, [])

    def test_checkpoint_cocok(self):
        r, sel = hitung_saldo([rec(k=100.0, s=110.0), rec(d=30.0)], 10.0)
        self.assertEqual(r[1]["saldo"], 80.0)
        self.assertEqual(sel, [])

    def test_checkpoint_beda_resync(self):
        r, sel = hitung_saldo([rec(k=100.0, s=999.0), rec(d=30.0)], 10.0)
        self.assertEqual(len(sel), 1)
        self.assertEqual(r[1]["saldo"], 969.0)  # lanjut dari nilai tercetak

    def test_input_tidak_diubah(self):
        a = [rec(k=1.0)]
        hitung_saldo(a, 0.0)
        self.assertIsNone(a[0]["saldo"])

    def test_ringkasan(self):
        r, _ = hitung_saldo([rec(k=100.0), rec(d=30.0)], 10.0)
        self.assertEqual(validasi_ringkasan(r, 80.0, 30.0, 100.0, 1, 1), [])
        self.assertEqual(len(validasi_ringkasan(r, 81.0, 31.0, 101.0, 2, 2)), 5)

    def test_periksa_status(self):
        _, rep = periksa_file([rec(k=100.0)], 10.0, saldo_akhir=110.0)
        self.assertEqual(rep["status"], "OK")
        _, rep = periksa_file([rec(k=100.0)], 10.0, saldo_akhir=111.0)
        self.assertEqual(rep["status"], "PERLU_REVIEW")


if __name__ == "__main__":
    unittest.main()