import unittest

from src.normalizer import (normalize_data, parse_amount, parse_waktu,
                            standardize_headers, tahun_dari_periode)


class TestParseAmount(unittest.TestCase):
    def test_us(self):
        self.assertEqual(parse_amount("16,561,371.00"), 16561371.0)
        self.assertEqual(parse_amount("40,987.00"), 40987.0)
        self.assertEqual(parse_amount("1.00"), 1.0)
        self.assertEqual(parse_amount("0.00"), 0.0)
        self.assertEqual(parse_amount("250906.71"), 250906.71)

    def test_us_tanda(self):
        self.assertEqual(parse_amount("10,000.00-"), -10000.0)  # BSI
        self.assertEqual(parse_amount("-1,000.00"), -1000.0)
        self.assertEqual(parse_amount("+1,000.00"), 1000.0)

    def test_id(self):
        self.assertEqual(parse_amount("1.234.567,89", "id"), 1234567.89)
        self.assertEqual(parse_amount("500,00", "id"), 500.0)
        self.assertEqual(parse_amount("-2.000,00", "id"), -2000.0)

    def test_ketat(self):
        for bad in ["1.234,56", "12,34.5", "abc", "", "1,23.00", "1 000.00x"]:
            with self.assertRaises(ValueError, msg=bad):
                parse_amount(bad, "us")
        with self.assertRaises(ValueError):
            parse_amount("1,234.56", "id")


class TestWaktu(unittest.TestCase):
    def test_periode(self):
        self.assertEqual(tahun_dari_periode("PERIODE : JULI 2023"), (2023, 7))
        with self.assertRaises(ValueError):
            tahun_dari_periode("PERIODE : XYZ 2023")

    def test_bca_tanggal_saja(self):
        self.assertEqual(parse_waktu("07/07", "bca", 2023), "2023-07-07")
        with self.assertRaises(ValueError):
            parse_waktu("07/07", "bca")          # tahun wajib
        with self.assertRaises(ValueError):
            parse_waktu("31/02", "bca", 2023)    # tanggal tidak ada

    def test_bri_detik(self):
        self.assertEqual(parse_waktu("01/09/26 09:10:01", "bri"), "2026-09-01T09:10:01")

    def test_bsi_menit(self):
        self.assertEqual(parse_waktu("01-09-2026\n21.41", "bsi"), "2026-09-01T21:41")

    def test_tidak_dikenal(self):
        with self.assertRaises(ValueError):
            parse_waktu("2026/09/01", "bri")


class TestHeaders(unittest.TestCase):
    def test_bri_dua_baris(self):
        r = standardize_headers({"Tanggal Transaksi\nTransaction Date": "x", "Saldo\nBalance": "y"}, "bri")
        self.assertEqual(r, {"waktu": "x", "saldo": "y"})

    def test_tidak_dikenal(self):
        with self.assertRaises(ValueError):
            standardize_headers({"Kolom Aneh": "x"}, "bca")


class TestNormalize(unittest.TestCase):
    def test_bca_kredit_debit(self):
        rows = [
            {"TANGGAL": "07/07", "KETERANGAN": "A  B", "CBG": "", "MUTASI": "16,561,371.00", "SALDO": "16,812,277.71"},
            {"TANGGAL": "07/07", "KETERANGAN": "C", "CBG": "", "MUTASI": "89,000.00 DB", "SALDO": ""},
        ]
        r = normalize_data(rows, "bca", {"periode": "JULI 2023", "no_rekening": "1"})
        self.assertEqual((r[0]["kredit"], r[0]["debit"], r[0]["saldo"]), (16561371.0, 0.0, 16812277.71))
        self.assertEqual((r[1]["kredit"], r[1]["debit"], r[1]["saldo"]), (0.0, 89000.0, None))
        self.assertEqual(r[0]["keterangan"], "A B")
        self.assertEqual(r[0]["waktu_transaksi"], "2023-07-07")
        self.assertEqual(r[0]["bank"], "bca")

    def test_bca_drop_saldo_awal(self):
        rows = [{"TANGGAL": "01/07", "KETERANGAN": "SALDO AWAL", "CBG": "", "MUTASI": "", "SALDO": "1.00"}]
        self.assertEqual(normalize_data(rows, "bca", {"periode": "JULI 2023"}), [])

    def test_bri(self):
        rows = [{"waktu": "x"}]  # kunci standar tidak dikenali sebagai header mentah
        with self.assertRaises(ValueError):
            normalize_data(rows, "bri")
        rows = [{"Tanggal Transaksi": "01/09/26 09:10:01", "Uraian Transaksi": "QRIS", "Teller": "8888546",
                 "Debet": "40,987.00", "Kredit": "0.00", "Saldo": "591,041.22"}]
        r = normalize_data(rows, "bri")[0]
        self.assertEqual((r["debit"], r["kredit"], r["saldo"]), (40987.0, 0.0, 591041.22))
        self.assertEqual(r["waktu_transaksi"], "2026-09-01T09:10:01")

    def test_bsi_debit_trailing_minus(self):
        rows = [{"No": "2", "Waktu Transaksi": "02-09-2026\n01.15", "Deskripsi": "By. Adm",
                 "Debet": "10,000.00-", "Kredit": "", "Saldo Riil": "6,572,644.00"}]
        r = normalize_data(rows, "bsi")[0]
        self.assertEqual((r["debit"], r["kredit"]), (10000.0, 0.0))
        self.assertEqual(r["waktu_transaksi"], "2026-09-02T01:15")

    def test_strict_menyebut_baris(self):
        rows = [{"TANGGAL": "07/07", "KETERANGAN": "A", "CBG": "", "MUTASI": "1.00", "SALDO": ""},
                {"TANGGAL": "07/07", "KETERANGAN": "A", "CBG": "", "MUTASI": "xx", "SALDO": ""}]
        with self.assertRaisesRegex(ValueError, "baris 2"):
            normalize_data(rows, "bca", {"periode": "JULI 2023"})
        r = normalize_data(rows, "bca", {"periode": "JULI 2023"}, strict=False)
        self.assertEqual(r[1]["flag"], "PERIKSA")

    def test_bank_belum_siap(self):
        with self.assertRaises(NotImplementedError):
            normalize_data([], "bni")


if __name__ == "__main__":
    unittest.main()