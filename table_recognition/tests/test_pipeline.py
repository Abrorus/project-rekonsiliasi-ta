import unittest

from src.evaluator import calculate_iou, levenshtein_distance


class TestMetrics(unittest.TestCase):
    def test_iou_sama(self):
        self.assertAlmostEqual(calculate_iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0)

    def test_iou_terpisah(self):
        self.assertEqual(calculate_iou((0, 0, 10, 10), (20, 20, 30, 30)), 0.0)

    def test_iou_separuh(self):
        self.assertAlmostEqual(calculate_iou((0, 0, 10, 10), (5, 0, 15, 10)), 1 / 3, places=3)

    def test_levenshtein(self):
        self.assertEqual(levenshtein_distance("kitten", "sitting"), 3)
        self.assertEqual(levenshtein_distance("", "abc"), 3)
        self.assertEqual(levenshtein_distance("abc", "abc"), 0)


if __name__ == "__main__":
    unittest.main()