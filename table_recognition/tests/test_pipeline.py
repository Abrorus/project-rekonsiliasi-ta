import unittest
from src.normalizer import parse_amount, parse_date
from src.evaluator import calculate_iou, levenshtein_distance

class TestPipelineCore(unittest.TestCase):
    
    def test_parse_amount_idr(self):
        self.assertEqual(parse_amount("1.500.000,00"), 1500000.0)
        self.assertEqual(parse_amount("Rp 500.000"), 500000.0)
        self.assertEqual(parse_amount("DB 1.000"), 1000.0)
        self.assertEqual(parse_amount(""), 0.0)
        
    def test_parse_date_bca(self):
        # Format tanpa tahun harus ditarik dari nama file
        res = parse_date("12/06", "bca_rekening_2026.pdf")
        self.assertEqual(res, "2026-06-12")
        
    def test_cer_levenshtein(self):
        self.assertEqual(levenshtein_distance("kitten", "sitting"), 3)
        self.assertEqual(levenshtein_distance("sama", "sama"), 0)

    def test_iou_calculation(self):
        boxA = (0, 0, 10, 10)
        boxB = (5, 5, 15, 15)
        # Inter = 5x5 = 25. Union = 100 + 100 - 25 = 175. IoU = 25/175
        iou = calculate_iou(boxA, boxB)
        self.assertAlmostEqual(iou, 25/175)

if __name__ == '__main__':
    unittest.main()