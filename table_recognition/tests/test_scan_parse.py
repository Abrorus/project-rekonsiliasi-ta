import unittest

from src.scan_parse import (bersihkan_keterangan, meta_bni, meta_mandiri, parse_jam, parse_nominal,
                            parse_tanggal)


class TestNominal(unittest.TestCase):
    def test_bni_bertanda(self):
        self.assertEqual(parse_nominal("+4,000,000", 0), 4000000.0)
        self.assertEqual(parse_nominal("-7,500,000", 0), -7500000.0)

    def test_mandiri_desimal(self):
        self.assertEqual(parse_nominal("+4.000.000,00", 2), 4000000.0)
        self.assertEqual(parse_nominal("-2.500,00", 2), -2500.0)
        self.assertEqual(parse_nominal("4.023.570,80", 2), 4023570.8)

    def test_pemisah_tertukar_ditoleransi(self):
        # titik/koma tertukar oleh OCR: nilai tetap benar karena hanya digit + 2 digit akhir dipakai
        self.assertEqual(parse_nominal("+4,000.000,00", 2), 4000000.0)
        self.assertEqual(parse_nominal("2.027.570.80", 2), 2027570.8)

    def test_tak_terbaca(self):
        self.assertIsNone(parse_nominal("", 0))
        self.assertIsNone(parse_nominal("abc", 2))


class TestWaktu(unittest.TestCase):
    def test_tanggal(self):
        self.assertEqual(parse_tanggal("01 May 2026"), (1, 5, 2026))
        self.assertEqual(parse_tanggal("06 Jan. 2026"), (6, 1, 2026))
        self.assertEqual(parse_tanggal("OS Jan 2026"), (5, 1, 2026))      # O->0, S->5
        self.assertEqual(parse_tanggal("_ 30 May 2026"), (30, 5, 2026))

    def test_tanggal_hari_tak_terbaca(self):
        h, b, t = parse_tanggal("?? Feb 2026")
        self.assertIsNone(h)
        self.assertEqual((b, t), (2, 2026))

    def test_bulan_indonesia_dan_inggris(self):
        self.assertEqual(parse_tanggal("17 Agu 2026")[1], 8)
        self.assertEqual(parse_tanggal("17 Aug 2026")[1], 8)
        self.assertEqual(parse_tanggal("17 Okt 2026")[1], 10)

    def test_jam(self):
        self.assertEqual(parse_jam("10:28:18WIB"), (10, 28, 18))
        self.assertEqual(parse_jam("113713WB"), (11, 37, 13))      # titik dua hilang
        self.assertIsNone(parse_jam("12:22:68WIB"))                # detik tidak valid
        self.assertIsNone(parse_jam("1:2:3"))


class TestKeterangan(unittest.TestCase):
    def test_bersihkan(self):
        self.assertEqual(bersihkan_keterangan("Transfer | : | BNI - PT AIRPAY"), "Transfer BNI - PT AIRPAY")


class TestMeta(unittest.TestCase):
    def test_bni(self):
        teks = ("Laporan Mutasi Rekening\nPeriode: 1 - 28 Februari 2026\n"
                "ARYA WIRAGUNA DWIPUTRA TAPLUS DIGITAL - 1780342641\n"
                "Saldo Awal Total Pemasukan Total Pengeluaran Saldo Akhir\n"
                "4,137,502 +17,880,000 -21,796,055 221,447\n")
        m = meta_bni(teks)
        self.assertEqual(m["no_rekening"], "1780342641")
        self.assertEqual(m["periode"], (2026, 2))
        self.assertEqual((m["saldo_awal"], m["total_kredit"], m["total_debit"], m["saldo_akhir"]),
                         (4137502.0, 17880000.0, 21796055.0, 221447.0))

    def test_bni_saldo_akhir_tak_terbaca(self):
        teks = ("Periode: 1 - 28 Februari 2026\nSaldo Awal Total Pemasukan Total Pengeluaran Saldo Akhir\n"
                "4,137,502 +17,880,000 -21,796,055 DOMAIN\n")
        self.assertNotIn("saldo_akhir", meta_bni(teks))

    def test_mandiri(self):
        teks = ("Periode/Period : 01 May 2026 - 31 May 2026\n"
                "Saldo Awal/Initial Balance : 23.570,80\n"
                "Nomor Rekening/Account Number : 1370021685108 Dana Masuk/Incoming Transactions + 6.075.000,00\n"
                "Dana Keluar/Outgoing Transactions: - 6.079.500,00\n"
                "Saldo Akhir/Closing Balance : 19.070,80\n")
        m = meta_mandiri(teks)
        self.assertEqual(m["no_rekening"], "1370021685108")
        self.assertEqual(m["periode"], (2026, 5))
        self.assertEqual(m["saldo_awal"], 23570.8)
        self.assertEqual(m["total_kredit"], 6075000.0)
        self.assertEqual(m["total_debit"], 6079500.0)
        self.assertEqual(m["saldo_akhir"], 19070.8)


if __name__ == "__main__":
    unittest.main()