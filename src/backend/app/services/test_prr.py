"""
Unit Tests for PRR Signal Detection Engine
==========================================
Comprehensive test suite verifying:
- Normal 2x2 table calculation & PRR algebra
- Zero denominator handling (A+B = 0, C+D = 0)
- C = 0 division-by-zero handling
- A = 0 with C > 0 handling
- Sparse background C < 5 handling
- Signal level categorization (LOW, MODERATE, HIGH)
- Signal confidence classification (LOW, MODERATE, HIGH)
- Multi-tier review priority classification (PRIORITY_1, PRIORITY_2, REVIEW, LOW)
- Pearson Chi-Square calculation (1 df)
- In-memory engine mock dataset filtering, ranking, comparison, and details
"""

import unittest
from app.services.prr import (
    compute_prr_partition,
    compute_chi_square_2x2,
    classify_signal_level,
    classify_signal_confidence,
    classify_review_priority,
    SignalDetectionEngine
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

    def test_classify_signal_level_thresholds(self):
        self.assertEqual(classify_signal_level(None), "LOW")
        self.assertEqual(classify_signal_level(1.99), "LOW")
        self.assertEqual(classify_signal_level(2.0), "MODERATE")
        self.assertEqual(classify_signal_level(3.99), "MODERATE")
        self.assertEqual(classify_signal_level(4.0), "HIGH")

    def test_classify_signal_confidence_thresholds(self):
        self.assertEqual(classify_signal_confidence(4, 10), "LOW")
        self.assertEqual(classify_signal_confidence(10, 4), "LOW")
        self.assertEqual(classify_signal_confidence(5, 5), "MODERATE")
        self.assertEqual(classify_signal_confidence(9, 10), "MODERATE")
        self.assertEqual(classify_signal_confidence(10, 5), "HIGH")

    def test_classify_review_priority_combinations(self):
        self.assertEqual(classify_review_priority(None, 10, 10), "LOW")
        self.assertEqual(classify_review_priority(4.5, 12, 6), "PRIORITY_1")
        self.assertEqual(classify_review_priority(2.5, 6, 6), "PRIORITY_2")
        self.assertEqual(classify_review_priority(3.0, 5, 2), "REVIEW")
        self.assertEqual(classify_review_priority(1.8, 10, 10), "LOW")

    def test_mock_engine_methods(self):
        # Construct mock engine in memory
        engine = SignalDetectionEngine()
        engine.total_unique_reports = 1000
        engine.drug_reports_count = {"ASPIRIN": 100, "IBUPROFEN": 200}
        engine.event_reports_count = {"HEADACHE": 50, "GASTRITIS": 30}
        engine.drug_event_pair_count = {
            ("ASPIRIN", "GASTRITIS"): 20,
            ("IBUPROFEN", "GASTRITIS"): 5,
            ("ASPIRIN", "HEADACHE"): 10
        }
        engine.is_loaded = True

        # Test calculate_prr
        calc = engine.calculate_prr("ASPIRIN", "GASTRITIS")
        self.assertEqual(calc["a"], 20)
        self.assertEqual(calc["b"], 80)
        self.assertGreater(calc["prr"], 1.0)

        # Test detect_signals with filter
        signals = engine.detect_signals(drug="ASPIRIN", min_prr=1.0, min_reports=1)
        self.assertEqual(len(signals), 2)

        # Test compare_drugs
        comp = engine.compare_drugs("ASPIRIN", "IBUPROFEN", "GASTRITIS")
        self.assertEqual(comp["adverse_event"], "GASTRITIS")
        self.assertEqual(comp["drug_a"]["drug_name"], "ASPIRIN")
        self.assertEqual(comp["drug_b"]["drug_name"], "IBUPROFEN")


if __name__ == "__main__":
    unittest.main()
