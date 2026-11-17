import unittest

from src.balance import koreksi_dp


def obs(*pairs):
    return list(pairs)


class TestKoreksiDP(unittest.TestCase):
    def test_tanda_salah_dan_digit_hilang(self):
        # saldo sebenarnya: 1000 -> 5000 -> 3500 -> 3800 -> 3700 -> 3500
        rows = [dict(nominal=[(4000, 2)], saldo=[(5000, 2)]),
                dict(nominal=[(1500, 2)], saldo=[(3500, 2)]),      # tanda nominal salah
                dict(nominal=[(300, 2)], saldo=[(3800, 2)]),
                dict(nominal=[(-100, 2)], saldo=[(700, 2)]),       # digit depan saldo hilang
                dict(nominal=[(-200, 2)], saldo=[(3500, 2)])]
        out, kor = koreksi_dp(rows, saldo_awal=1000, saldo_akhir=3500)
        self.assertEqual([o["saldo"] for o in out], [5000, 3500, 3800, 3700, 3500])
        self.assertEqual([o["nominal"] for o in out], [4000, -1500, 300, -100, -200])
        self.assertEqual({(k["indeks"], k["jenis"]) for k in kor}, {(1, "nominal"), (3, "saldo")})

    def test_data_benar_tidak_diubah(self):
        rows = [dict(nominal=[(100.5, 1)], saldo=[(1100.5, 1)]),
                dict(nominal=[(-50.0, 1)], saldo=[(1050.5, 1)])]
        out, kor = koreksi_dp(rows, saldo_awal=1000.0, saldo_akhir=1050.5)
        self.assertEqual(kor, [])
        self.assertEqual(out[1]["saldo"], 1050.5)

    def test_hipotesis_alternatif_dipakai(self):
        # varian OCR kedua memuat nilai benar; rantai saldo memilihnya
        rows = [dict(nominal=[(1000, 2)], saldo=[(2000, 1), (2001, 1)]),
                dict(nominal=[(-500, 2)], saldo=[(1501, 1), (1500, 1)])]
        out, _ = koreksi_dp(rows, saldo_awal=1000)
        self.assertEqual([o["saldo"] for o in out], [2000, 1500])

    def test_tanpa_saldo_awal(self):
        rows = [dict(nominal=[(100, 1)], saldo=[(600, 1)]),
                dict(nominal=[(-200, 1)], saldo=[(400, 1)])]
        out, kor = koreksi_dp(rows)
        self.assertEqual([o["saldo"] for o in out], [600, 400])
        self.assertEqual(kor, [])

    def test_kosong(self):
        self.assertEqual(koreksi_dp([]), ([], []))


if __name__ == "__main__":
    unittest.main()