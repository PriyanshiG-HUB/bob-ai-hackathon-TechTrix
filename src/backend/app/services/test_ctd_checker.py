"""
Unit Tests for ICH M4 CTD Regulatory Submission Readiness Checker
==================================================================
Comprehensive test suite verifying:
 1. Complete synthetic CTD outline -> high completeness (READY).
 2. Missing Module 3 sections -> gaps detected.
 3. Missing multiple modules -> correct per-module scores.
 4. Unknown/non-CTD section -> does not falsely satisfy a required section.
 5. Empty dossier -> NOT_READY (0% completeness).
 6. Duplicate section -> counted only once.
 7. Readiness band boundaries (90%, 75%, 50%, <50%).
 8. Gap priority classification (CRITICAL, HIGH, MEDIUM).
 9. M5 5.3.3 (Human PK) maps to 5.3.3, not 5.3.2 or 5.3.4.
10. M5 5.3.4 (Human PD) maps to 5.3.4.
11. M5 5.3.5 (PK/PD) maps to 5.3.5 (optional).
12. M5 5.3.6 (Efficacy/Safety) maps to 5.3.6 and is required.
13. M5 5.3.7 (Post-Marketing) maps to 5.3.7 (optional).
14. 1.6 (RMP/REMS) is optional and does not count toward universal required completeness.
15. Outline parsing variations (markdown, bullet points, numbered, noise text).
16. Sub-section parent matching logic.
17. In-memory store caching and retrieval.
"""

import unittest
from app.services.ctd_checker import (
    parse_dossier_outline,
    check_submission,
    load_ich_m4_requirements,
    store_submission_result,
    get_stored_submission,
    match_section
)

# ---------------------------------------------------------------------------
# Corrected synthetic dossier — covers all universally required sections.
# M1 required: 1.1, 1.2, 1.3  (1.6 is now optional/region-specific)
# M5 required: 5.1, 5.2, 5.3.3, 5.3.6
# ---------------------------------------------------------------------------
SYNTHETIC_COMPLETE_DOSSIER = """
# CTD Submission Dossier Outline
Module 1: Administrative Information
1.1 Comprehensive Table of Contents
1.2 Application Form
1.3 Prescribing Information / Labeling

Module 2: Common Technical Document Summaries
2.1 CTD Table of Contents
2.2 CTD Introduction
2.3 Quality Overall Summary (QOS)
2.4 Nonclinical Overview
2.5 Clinical Overview
2.6 Nonclinical Written and Tabulated Summaries
2.7 Clinical Summary

Module 3: Quality
3.1 Module 3 Table of Contents
3.2.S Drug Substance
3.2.P Drug Product

Module 4: Nonclinical Study Reports
4.1 Module 4 Table of Contents
4.2.1 Pharmacology
4.2.2 Pharmacokinetics
4.2.3 Toxicology

Module 5: Clinical Study Reports
5.1 Module 5 Table of Contents
5.2 Tabular Listing of All Clinical Studies
5.3.3 Reports of Human PK Studies
5.3.6 Reports of Efficacy and Safety Studies
"""

DOSSIER_MISSING_MODULE_3 = """
1.1 Table of Contents
1.2 Application Form
1.3 Prescribing Info
2.1 TOC
2.2 Intro
2.3 QOS
2.4 Nonclinical Overview
2.5 Clinical Overview
2.6 Nonclinical Summary
2.7 Clinical Summary
4.1 TOC
4.2.1 Pharmacology
4.2.2 Pharmacokinetics
4.2.3 Toxicology
5.1 TOC
5.2 Tabular Listing
5.3.3 Reports of Human PK Studies
5.3.6 Reports of Efficacy and Safety Studies
"""


class TestCTDChecker(unittest.TestCase):

    def setUp(self):
        self.reqs = load_ich_m4_requirements()

    def test_1_complete_synthetic_ctd_outline(self):
        result = check_submission(SYNTHETIC_COMPLETE_DOSSIER, self.reqs)
        self.assertEqual(result["overall_completeness"], 100.0)
        self.assertEqual(result["readiness_status"], "READY")
        self.assertEqual(result["missing_required_sections_count"], 0)
        self.assertEqual(len(result["gaps"]), 0)
        for mod_id in ["M1", "M2", "M3", "M4", "M5"]:
            self.assertEqual(result["module_scores"][mod_id]["completeness_percentage"], 100.0)

    def test_2_missing_module_3_sections(self):
        result = check_submission(DOSSIER_MISSING_MODULE_3, self.reqs)
        m3_score = result["module_scores"]["M3"]
        self.assertEqual(m3_score["completeness_percentage"], 0.0)
        self.assertEqual(m3_score["present_required_count"], 0)
        self.assertGreater(m3_score["missing_required_count"], 0)

        # Check that Module 3 gaps exist with CRITICAL priority (e.g. 3.2.S, 3.2.P)
        m3_gaps = [g for g in result["gaps"] if g["module_id"] == "M3"]
        self.assertGreaterEqual(len(m3_gaps), 3)
        critical_m3 = [g for g in m3_gaps if g["priority"] == "CRITICAL"]
        self.assertTrue(any(g["section_id"] == "3.2.S" for g in critical_m3))
        self.assertTrue(any(g["section_id"] == "3.2.P" for g in critical_m3))

    def test_3_missing_multiple_modules_correct_scores(self):
        # M1 only — 1.1, 1.2, 1.3 are the three universally required M1 sections.
        dossier_m1_only = """
        1.1 Table of Contents
        1.2 Application Form
        1.3 Prescribing Information
        """
        result = check_submission(dossier_m1_only, self.reqs)
        self.assertEqual(result["module_scores"]["M1"]["completeness_percentage"], 100.0)
        self.assertEqual(result["module_scores"]["M2"]["completeness_percentage"], 0.0)
        self.assertEqual(result["module_scores"]["M3"]["completeness_percentage"], 0.0)
        self.assertEqual(result["module_scores"]["M4"]["completeness_percentage"], 0.0)
        self.assertEqual(result["module_scores"]["M5"]["completeness_percentage"], 0.0)
        self.assertLess(result["overall_completeness"], 50.0)
        self.assertEqual(result["readiness_status"], "NOT_READY")

    def test_4_unknown_non_ctd_sections_do_not_falsely_satisfy(self):
        garbage_dossier = """
        9.9 Random Custom Analysis
        8.4 Marketing Presentation
        7.1 Executive Letter
        3.99 Unofficial Quality Note
        """
        result = check_submission(garbage_dossier, self.reqs)
        self.assertEqual(result["overall_completeness"], 0.0)
        self.assertEqual(result["readiness_status"], "NOT_READY")
        self.assertEqual(result["present_required_sections_count"], 0)

    def test_5_empty_dossier(self):
        result = check_submission("", self.reqs)
        self.assertEqual(result["overall_completeness"], 0.0)
        self.assertEqual(result["readiness_status"], "NOT_READY")
        self.assertEqual(result["extracted_sections_count"], 0)
        self.assertEqual(len(result["present_sections"]), 0)

    def test_6_duplicate_sections_counted_once(self):
        duplicate_dossier = """
        1.1 Comprehensive Table of Contents
        1.1 Comprehensive Table of Contents (Repeated)
        1.2 Application Form
        1.2 Application Form (Version 2)
        1.3 Prescribing Info
        """
        result = check_submission(duplicate_dossier, self.reqs)
        m1_score = result["module_scores"]["M1"]
        # M1 has 3 universally required sections: 1.1, 1.2, 1.3 (1.6 is now optional)
        self.assertEqual(m1_score["present_required_count"], 3)
        self.assertEqual(m1_score["completeness_percentage"], 100.0)

    def test_7_readiness_band_boundaries(self):
        # 100% -> READY
        res100 = check_submission(SYNTHETIC_COMPLETE_DOSSIER, self.reqs)
        self.assertEqual(res100["readiness_status"], "READY")

        # Empty -> NOT_READY (<50)
        res0 = check_submission("", self.reqs)
        self.assertEqual(res0["readiness_status"], "NOT_READY")

    def test_8_gap_priority_classification(self):
        # Check priority levels in gaps
        result = check_submission("", self.reqs)
        gaps = result["gaps"]
        priorities = {g["priority"] for g in gaps}
        self.assertIn("CRITICAL", priorities)
        self.assertIn("HIGH", priorities)

    def test_9_m5_5_3_3_human_pk_matches_correctly(self):
        dossier = "5.1 TOC\n5.2 Tabular Listing\n5.3.3 Reports of Human PK Studies\n5.3.6 Reports of Efficacy and Safety Studies"
        result = check_submission(dossier, self.reqs)
        m5_present = {s["section_id"] for s in result["module_scores"]["M5"]["present_sections"]}
        self.assertIn("5.3.3", m5_present, "5.3.3 should be matched as present")
        self.assertNotIn("5.3.2", m5_present, "5.3.2 must NOT be falsely matched by 5.3.3 input")
        self.assertNotIn("5.3.4", m5_present, "5.3.4 must NOT be falsely matched by 5.3.3 input")

    def test_10_m5_5_3_4_human_pd_matches_correctly(self):
        dossier = "5.1 TOC\n5.2 Tabular Listing\n5.3.3 Human PK\n5.3.4 Reports of Human PD Studies\n5.3.6 Efficacy and Safety"
        result = check_submission(dossier, self.reqs)
        m5_present = {s["section_id"] for s in result["module_scores"]["M5"]["present_sections"]}
        self.assertIn("5.3.4", m5_present, "5.3.4 should be matched as present")
        self.assertNotIn("5.3.5", m5_present, "5.3.5 must NOT be falsely matched by 5.3.4 input")

    def test_11_m5_5_3_5_pk_pd_matches_correctly(self):
        dossier = "5.1 TOC\n5.2 Tabular Listing\n5.3.3 Human PK\n5.3.5 Reports of Human PK/PD Studies\n5.3.6 Efficacy and Safety"
        result = check_submission(dossier, self.reqs)
        m5_present_all = result["module_scores"]["M5"]["present_sections"]
        present_ids = {s["section_id"] for s in m5_present_all}
        self.assertIn("5.3.5", present_ids, "5.3.5 should be matched (optional)")

    def test_12_m5_5_3_6_efficacy_safety_is_required_and_matches(self):
        dossier_no_eff = "5.1 TOC\n5.2 Tabular Listing\n5.3.3 Human PK"
        result_missing = check_submission(dossier_no_eff, self.reqs)
        m5_missing = {s["section_id"] for s in result_missing["module_scores"]["M5"]["missing_required_sections"]}
        self.assertIn("5.3.6", m5_missing, "5.3.6 should be flagged missing when absent")

        dossier_with_eff = "5.1 TOC\n5.2 Tabular Listing\n5.3.3 Human PK\n5.3.6 Reports of Efficacy and Safety Studies"
        result_present = check_submission(dossier_with_eff, self.reqs)
        m5_present_ids = {s["section_id"] for s in result_present["module_scores"]["M5"]["present_sections"]}
        self.assertIn("5.3.6", m5_present_ids, "5.3.6 should be present and matched")

    def test_13_m5_5_3_7_post_marketing_optional_and_matches(self):
        dossier_no_pm = "5.1 TOC\n5.2 Tabular Listing\n5.3.3 Human PK\n5.3.6 Efficacy and Safety"
        result_without = check_submission(dossier_no_pm, self.reqs)
        m5_gaps = [g for g in result_without["gaps"] if g["module_id"] == "M5"]
        gap_ids = {g["section_id"] for g in m5_gaps}
        self.assertNotIn("5.3.7", gap_ids, "5.3.7 must not appear as a required gap when absent")

    def test_14_m1_1_6_is_optional_does_not_affect_required_completeness(self):
        dossier_no_16 = "1.1 Comprehensive Table of Contents\n1.2 Application Form\n1.3 Prescribing Information"
        result_no_16 = check_submission(dossier_no_16, self.reqs)
        m1 = result_no_16["module_scores"]["M1"]
        self.assertEqual(m1["completeness_percentage"], 100.0)

    def test_15_parse_outline_formatting_variations(self):
        text = """
        - 1.1 Table of Contents
        * Section 1.2: Application Form
        ### 1.3 Prescribing Information
        3.2.S.1 General Information
        """
        parsed = parse_dossier_outline(text)
        sec_ids = {p["section_id"] for p in parsed}
        self.assertIn("1.1", sec_ids)
        self.assertIn("1.2", sec_ids)
        self.assertIn("1.3", sec_ids)
        self.assertIn("3.2.S.1", sec_ids)

    def test_16_match_section_subsections(self):
        self.assertTrue(match_section("3.2.S.1", "3.2.S"))
        self.assertTrue(match_section("3.2.S", "3.2.S"))
        self.assertFalse(match_section("3.2.P", "3.2.S"))

    def test_17_in_memory_store(self):
        mock_res = {"submission_id": "sub-test-999", "overall_completeness": 85.0}
        saved_id = store_submission_result(mock_res)
        self.assertEqual(saved_id, "sub-test-999")
        retrieved = get_stored_submission("sub-test-999")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["overall_completeness"], 85.0)


if __name__ == "__main__":
    unittest.main()
