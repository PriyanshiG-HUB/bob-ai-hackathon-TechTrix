"""
Unit Tests for PRR Signal Detection Engine
==========================================
Tests:
- Normal 2x2 table calculation
- Zero denominator handling
- C = 0 division-by-zero handling
- Sparse background C < 5 handling
- High PRR with sparse background
- High-confidence signal classification
- Review priority classification (PRIORITY_1, PRIORITY_2, REVIEW, LOW)
- Pearson Chi-Square calculation
"""

import unittest
from app.services.prr import (
    compute_prr_partition,
    compute_chi_square_2x2,
    classify_signal_level,
    classify_signal_confidence,
    classify_review_priority
)


class TestPRREngine(unittest.TestCase):

    def test_normal_2x2_table(self):
        # A = 20, B = 80 -> A + B = 100 (Drug event rate = 0.20)
        # C = 50, D = 950 -> C + D = 1000 (Bg event rate = 0.05)
        # PRR = 0.20 / 0.05 = 4.0
        a, b, c, d = 20, 80, 50, 950
        prr, drug_rate, bg_rate, undefined_reason = compute_prr_partition(a, b, c, d)
        self.assertIsNone(undefined_reason)
        self.assertEqual(prr, 4.0)
        self.assertEqual(drug_rate, 0.20)
        self.assertEqual(bg_rate, 0.05)
        
        chi2 = compute_chi_square_2x2(a, b, c, d)
        self.assertIsNotNone(chi2)
        self.assertGreater(chi2, 0.0)

    def test_zero_denominator_target_drug(self):
        # A + B = 0
        a, b, c, d = 0, 0, 10, 100
        prr, drug_rate, bg_rate, reason = compute_prr_partition(a, b, c, d)
        self.assertIsNone(prr)
        self.assertIn("Target drug has zero total reports", reason)

    def test_c_zero_division_by_zero(self):
        # C = 0 -> background rate = 0
        a, b, c, d = 10, 90, 0, 1000
        prr, drug_rate, bg_rate, reason = compute_prr_partition(a, b, c, d)
        self.assertIsNone(prr)
        self.assertEqual(bg_rate, 0.0)
        self.assertIn("Background event rate is zero", reason)

    def test_a_zero_c_positive(self):
        # A = 0, C > 0 -> PRR should be 0.0
        a, b, c, d = 0, 100, 10, 1000
        prr, drug_rate, bg_rate, reason = compute_prr_partition(a, b, c, d)
        self.assertIsNone(reason)
        self.assertEqual(prr, 0.0)
        self.assertEqual(drug_rate, 0.0)

    def test_sparse_background_and_confidence(self):
        # Sparse background: C = 2 (< 5)
        a, b, c, d = 6, 1, 2, 397200
        prr, _, _, _ = compute_prr_partition(a, b, c, d)
        self.assertIsNotNone(prr)
        self.assertGreater(prr, 1000.0)
        
        confidence = classify_signal_confidence(a, c)
        self.assertEqual(confidence, "LOW")  # Because C < 5
        
        priority = classify_review_priority(prr, a, c)
        self.assertEqual(priority, "REVIEW")  # High PRR, A >= 5, but C < 5 -> REVIEW

    def test_priority_1_and_high_confidence_signal(self):
        # A >= 10, C >= 5, PRR >= 4
        a, b, c, d = 50, 200, 20, 10000
        prr, _, _, _ = compute_prr_partition(a, b, c, d)
        self.assertIsNotNone(prr)
        self.assertGreaterEqual(prr, 4.0)
        
        confidence = classify_signal_confidence(a, c)
        self.assertEqual(confidence, "HIGH")  # A >= 10 and C >= 5
        
        priority = classify_review_priority(prr, a, c)
        self.assertEqual(priority, "PRIORITY_1")  # PRR >= 4, A >= 10, C >= 5

    def test_priority_2_moderate_confidence_signal(self):
        # PRR >= 2.0, A = 7 (>= 5, < 10), C = 10 (>= 5)
        # Drug rate = 7/20 = 0.35, Bg rate = 10/1000 = 0.01 -> PRR = 35.0
        a, b, c, d = 7, 13, 10, 990
        prr, _, _, _ = compute_prr_partition(a, b, c, d)
        self.assertEqual(classify_signal_confidence(a, c), "MODERATE")
        self.assertEqual(classify_review_priority(prr, a, c), "PRIORITY_2")

    def test_low_priority_when_threshold_unmet(self):
        # PRR < 2.0
        a, b, c, d = 5, 95, 50, 950  # Drug rate = 0.05, Bg rate = 0.05 -> PRR = 1.0
        prr, _, _, _ = compute_prr_partition(a, b, c, d)
        self.assertEqual(classify_signal_level(prr), "LOW")
        self.assertEqual(classify_review_priority(prr, a, c), "LOW")


if __name__ == "__main__":
    unittest.main()
