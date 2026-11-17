import json
import os
import tempfile
import unittest

from src.evaluator import (cocokkan_transaksi, evaluate_end_to_end, evaluate_file,
                           evaluate_semua, muat_gt_content)


def t(w="2023-07-07", d=0.0, k=100.0, s=100.0, ket="TRSF A"):
    return {"waktu_transaksi": w, "debit": d, "kredit": k, "saldo": s, "keterangan": ket}


class TestEvaluateFile(unittest.TestCase):
    def test_semua_benar(self):
        gt = [t(s=100.0), t(s=200.0), t(d=50.0, k=0.0, s=150.0)]
        r = evaluate_file([dict(x) for x in gt], gt)
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (3, 0, 0))
        self.assertEqual((r["precision"], r["recall"], r["f1"]), (1.0, 1.0, 1.0))
        self.assertEqual(r["cer_keterangan"], 0.0)
        self.assertEqual(r["metode_cocok"], "urutan")

    def test_satu_nominal_salah(self):
        gt = [t(s=100.0), t(s=200.0)]
        pr = [t(s=100.0), t(k=101.0, s=200.0)]
        r = evaluate_file(pr, gt)
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (1, 1, 1))
        self.assertEqual(r["salah"][0]["baris_gt"], 2)
        self.assertIn("kredit", r["salah"][0]["field"])

    def test_baris_hilang_tidak_menggeser(self):
        gt = [t(w="2023-07-01", s=1.0), t(w="2023-07-02", s=2.0), t(w="2023-07-03", s=3.0)]
        pr = [gt[0], gt[2]]  # baris 2 hilang
        r = evaluate_file(pr, gt)
        self.assertEqual(r["metode_cocok"], "kunci")
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (2, 0, 1))
        self.assertEqual(r["baris_gt_tak_terpasang"], [2])

    def test_baris_berlebih(self):
        gt = [t(s=1.0)]
        pr = [t(s=1.0), t(w="2023-08-01", s=9.0)]
        r = evaluate_file(pr, gt)
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (1, 1, 0))
        self.assertEqual(r["baris_pred_tak_terpasang"], [2])

    def test_cer_keterangan_spasi_diabaikan(self):
        gt = [t(ket="ABC DEF")]
        self.assertEqual(evaluate_file([t(ket="ABC   DEF")], gt)["cer_keterangan"], 0.0)
        r = evaluate_file([t(ket="ABC DXF")], gt)
        self.assertAlmostEqual(r["cer_keterangan"], 1 / 7)
        self.assertEqual(r["tp"], 1)  # keterangan tidak memengaruhi benar/salah transaksi

    def test_toleransi_desimal_dan_waktu(self):
        gt = [t(s=100.0)]
        self.assertEqual(evaluate_file([t(s=100.004)], gt)["tp"], 1)
        self.assertEqual(evaluate_file([t(w="2023-07-08")], gt)["tp"], 0)

    def test_kompatibel_lama(self):
        gt = [t()]
        self.assertEqual(evaluate_end_to_end([t()], gt)["f1"], 1.0)


class TestEvaluateSemua(unittest.TestCase):
    def _gt(self, d, bank, nama, trans):
        os.makedirs(os.path.join(d, bank), exist_ok=True)
        with open(os.path.join(d, bank, f"{nama}_content.json"), "w", encoding="utf-8") as f:
            json.dump({"file": nama + ".pdf", "transactions": trans}, f)

    def test_agregat_dan_dilewati(self):
        gt1 = [t(s=1.0), t(s=2.0)]
        with tempfile.TemporaryDirectory() as d:
            self._gt(d, "bca", "bca_01", gt1)
            self._gt(d, "bni", "bni_01", [t()])
            self._gt(d, "bri", "bri_01", [])
            hasil = [
                {"file": "bca_01.pdf", "bank": "bca", "status": "OK", "transaksi": gt1},
                {"file": "bni_01.pdf", "bank": None, "status": "BELUM_DIDUKUNG", "transaksi": []},
                {"file": "bri_01.pdf", "bank": "bri", "status": "OK", "transaksi": [t()]},
                {"file": "bsi_01.pdf", "bank": "bsi", "status": "OK", "transaksi": [t()]},
            ]
            ev = evaluate_semua(hasil, d)
        self.assertEqual(list(ev["per_file"]), ["bca_01"])
        self.assertEqual(ev["total"]["f1"], 1.0)
        self.assertEqual(ev["dilewati"], {"bni_01": "BELUM_DIDUKUNG", "bri_01": "GT_KOSONG",
                                          "bsi_01": "GT_BELUM_ADA"})
        self.assertEqual(muat_gt_content("/tidak/ada", "bca_01"), None)


class TestGTRusak(unittest.TestCase):
    def test_json_rusak_tidak_menjatuhkan_evaluasi(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "bni"))
            with open(os.path.join(d, "bni", "bni_01_content.json"), "w", encoding="utf-8") as f:
                f.write('{"transactions": [\n {"debit": 1.0,},\n ]}')
            hasil = [{"file": "bni_01.pdf", "bank": None, "status": "BELUM_DIDUKUNG", "transaksi": []}]
            ev = evaluate_semua(hasil, d)
        self.assertEqual(ev["per_file"], {})
        self.assertTrue(ev["dilewati"]["bni_01"].startswith("GT_RUSAK (baris 2"))


class TestEvaluasiBCAAsli(unittest.TestCase):
    def test_bca_f1_satu(self):
        """Dengan GT BCA yang sudah benar, seluruh transaksi harus cocok (F1 = 1)."""
        root = os.path.dirname(os.path.dirname(__file__))
        gt_dir, raw = os.path.join(root, "data", "ground_truth"), os.path.join(root, "data", "raw", "bca")
        if not (os.path.isdir(os.path.join(gt_dir, "bca")) and os.path.isdir(raw)):
            self.skipTest("GT atau PDF BCA tidak ada")
        from src.pipeline_digital import process_pdf
        hasil = [process_pdf(os.path.join(raw, f"bca_0{n}.pdf")) for n in range(1, 7)]
        ev = evaluate_semua(hasil, gt_dir)
        self.assertEqual(len(ev["per_file"]), 6)
        for nama, r in ev["per_file"].items():
            self.assertEqual(r["f1"], 1.0, f"{nama}: {r['salah'][:3]}")


if __name__ == "__main__":
    unittest.main()


class TestEvaluateSel(unittest.TestCase):
    def test_cer_dan_akurasi_sel(self):
        from src.evaluator import evaluate_sel
        pred = [{"tanggal": "01 Feb 2026", "waktu": "08:19:21WIB", "keterangan": "Transfer BNI", "nominal": "+4,000,000", "saldo": "8,137,502"},
                {"tanggal": "02 Feb 2026", "waktu": "13:04:28WIB", "keterangan": "Qris", "nominal": "-111,000", "saldo": "526,502"}]
        gt = [{"tanggal_waktu": "01 Feb 2026 08:19:21 WIB", "keterangan": "Transfer BNI", "nominal": "+4,000,000", "saldo": "8,137,502"},
              {"tanggal_waktu": "02 Feb 2026 13:04:28 WIB", "keterangan": "Qris", "nominal": "-111,000", "saldo": "526,502"}]
        r = evaluate_sel(pred, gt)
        self.assertEqual(r["cer"]["tanggal_waktu"], 0.0)          # spasi diabaikan
        self.assertEqual(r["akurasi_sel"]["saldo"], 1.0)
        pred[1]["saldo"] = "26,502"                                  # satu digit hilang
        r = evaluate_sel(pred, gt)
        self.assertEqual(r["kesalahan"]["saldo"], 1)
        self.assertAlmostEqual(r["akurasi_sel"]["saldo"], 0.5)

    def test_jumlah_baris_beda(self):
        from src.evaluator import evaluate_sel
        r = evaluate_sel([{"tanggal": "", "waktu": "", "keterangan": "", "nominal": "", "saldo": ""}],
                         [{"tanggal_waktu": "", "keterangan": "", "nominal": "", "saldo": ""}] * 2)
        self.assertTrue(r["baris_tidak_sama"])
        self.assertEqual(r["n_dibandingkan"], 1)