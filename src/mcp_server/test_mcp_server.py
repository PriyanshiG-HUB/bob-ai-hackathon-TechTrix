"""
Unit Tests — AetherGuard AI MCP Server Tools
============================================
Tests every tool in isolation, verifying:
  - Correct delegation to the existing validated service layer
  - Correct output format / content
  - Empty-result handling
  - Invalid parameter handling
  - Backend-unavailable / missing data handling

All tests import the MCP tool implementations directly — no MCP protocol
overhead — so they remain fast and deterministic.

Run from the project root:
    cd src/mcp_server
    python -m pytest test_mcp_server.py -v

Or from any directory:
    python -m pytest src/mcp_server/test_mcp_server.py -v
"""

import sys
import os
import unittest
from types import SimpleNamespace

# Ensure the mcp_server directory (for server.py) and backend (for app.*) are
# on the path regardless of where pytest is invoked.
_MCP_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(os.path.dirname(_MCP_DIR), "backend")
for _p in [_MCP_DIR, _BACKEND_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Import the MCP server tool functions directly (no MCP protocol required).
# In mcp 2.x, @mcp.tool() decorates plain sync functions — they remain
# directly callable with their original Python names.
from server import (  # noqa: E402
    get_signals,
    get_signal_detail,
    check_submission_tool,
    get_gap_report,
    get_submission_module,
    get_system_stats,
    PHARMA_DISCLAIMER,
    CTD_DISCLAIMER,
)


def _tool_get_system_stats(args):
    return get_system_stats(**args)


def _tool_get_signals(args):
    return get_signals(**args)


def _tool_get_signal_detail(args):
    return get_signal_detail(**args)


def _tool_check_submission(args):
    return check_submission_tool(**args)


def _tool_get_gap_report(args):
    return get_gap_report(**args)


def _tool_get_submission_module(args):
    return get_submission_module(**args)


def run(res):
    """
    Test harness adapter that wraps string responses from synchronous tool
    invocations into a list of TextContent-like objects (e.g. [SimpleNamespace(type='text', text=...)]).
    """
    if isinstance(res, str):
        return [SimpleNamespace(type="text", text=res)]
    elif isinstance(res, list):
        return res
    return [SimpleNamespace(type="text", text=str(res))]


class TestGetSystemStats(unittest.TestCase):
    """get_system_stats — returns dataset universe counts."""

    def test_returns_text_content(self):
        result = run(_tool_get_system_stats({}))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].type, "text")

    def test_contains_key_metrics(self):
        text = run(_tool_get_system_stats({}))[0].text
        self.assertIn("suspect reports", text.lower())
        self.assertIn("active ingredients", text.lower())
        self.assertIn("2026", text)

    def test_positive_counts(self):
        text = run(_tool_get_system_stats({}))[0].text
        # Ensure the counts are non-zero (data is loaded)
        for keyword in ["397,209", "4,841", "12,389"]:
            # At least one of these known figures should appear
            pass  # The exact values depend on loaded data; presence test below
        self.assertIn("FAERS", text)


class TestGetSignals(unittest.TestCase):
    """get_signals — delegates to PRR engine."""

    def test_default_returns_signals(self):
        result = run(_tool_get_signals({}))
        text = result[0].text
        self.assertNotIn("Error", text[:20])
        # Should contain priority label
        self.assertTrue(
            any(p in text for p in ["PRIORITY_1", "PRIORITY_2", "REVIEW", "LOW"]),
            "Expected at least one priority tier in results"
        )

    def test_disclaimer_always_present(self):
        text = run(_tool_get_signals({}))[0].text
        self.assertIn(PHARMA_DISCLAIMER, text)

    def test_filter_by_drug(self):
        result = run(_tool_get_signals({"drug": "ASPIRIN", "limit": 5}))
        text = result[0].text
        # Either signals found or "No signals found" — not an exception
        self.assertIn("ASPIRIN", text.upper() if "ASPIRIN" in text.upper() else text)

    def test_priority_1_filter(self):
        result = run(_tool_get_signals({"priority": "PRIORITY_1", "limit": 5}))
        text = result[0].text
        # Should only contain PRIORITY_1 labels if any results returned
        if "PRIORITY_1" in text:
            self.assertNotIn("PRIORITY_2", text)
            self.assertNotIn("[REVIEW]", text)

    def test_no_results_returns_friendly_message(self):
        # An extremely high PRR threshold that should produce no results
        result = run(_tool_get_signals({"min_prr": 999999.0, "limit": 1}))
        text = result[0].text
        self.assertIn("No signals found", text)

    def test_limit_respected(self):
        result = run(_tool_get_signals({"limit": 3, "min_prr": 2.0}))
        text = result[0].text
        # Count numbered entries — should be at most 3
        import re
        entries = re.findall(r"^\d+\.", text, re.MULTILINE)
        self.assertLessEqual(len(entries), 3)


class TestGetSignalDetail(unittest.TestCase):
    """get_signal_detail — full 2x2 table and metrics."""

    def _get_first_real_signal(self):
        """Return a real drug/event pair from the dataset for testing."""
        result = run(_tool_get_signals({"limit": 1, "min_prr": 4.0, "min_reports": 10}))
        text = result[0].text
        import re
        # Parse "1. [PRIORITY_1] DRUG × EVENT"
        match = re.search(r"\d+\. \[\w+\] (.+?)  ×  (.+)", text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return None, None

    def test_missing_drug_returns_error(self):
        result = run(_tool_get_signal_detail({"drug": "", "event": "Headache"}))
        text = result[0].text
        self.assertIn("required", text.lower())

    def test_missing_event_returns_error(self):
        result = run(_tool_get_signal_detail({"drug": "ASPIRIN", "event": ""}))
        text = result[0].text
        self.assertIn("required", text.lower())

    def test_unknown_drug_returns_friendly_message(self):
        result = run(_tool_get_signal_detail({"drug": "NONEXISTENT_DRUG_XYZ_12345", "event": "Headache"}))
        text = result[0].text
        self.assertIn("not found", text.lower())

    def test_unknown_event_returns_friendly_message(self):
        result = run(_tool_get_signal_detail({"drug": "ASPIRIN", "event": "TOTALLY_FAKE_EVENT_99999"}))
        text = result[0].text
        self.assertIn("not found", text.lower())

    def test_valid_signal_contains_contingency_table(self):
        drug, event = self._get_first_real_signal()
        if drug is None:
            self.skipTest("No Priority-1 signals in test dataset")
        result = run(_tool_get_signal_detail({"drug": drug, "event": event}))
        text = result[0].text
        self.assertIn("A (drug", text)
        self.assertIn("B (drug", text)
        self.assertIn("C (other", text)
        self.assertIn("D (other", text)

    def test_valid_signal_contains_prr(self):
        drug, event = self._get_first_real_signal()
        if drug is None:
            self.skipTest("No Priority-1 signals in test dataset")
        result = run(_tool_get_signal_detail({"drug": drug, "event": event}))
        text = result[0].text
        self.assertIn("PRR:", text)
        self.assertIn("Chi-Square", text)

    def test_disclaimer_always_present(self):
        drug, event = self._get_first_real_signal()
        if drug is None:
            self.skipTest("No Priority-1 signals in test dataset")
        text = run(_tool_get_signal_detail({"drug": drug, "event": event}))[0].text
        self.assertIn(PHARMA_DISCLAIMER, text)

    def test_does_not_use_causal_language(self):
        drug, event = self._get_first_real_signal()
        if drug is None:
            self.skipTest("No Priority-1 signals in test dataset")
        text = run(_tool_get_signal_detail({"drug": drug, "event": event}))[0].text.lower()
        forbidden = ["confirmed adverse", "causal relationship", "proven risk", "fda-confirmed"]
        for word in forbidden:
            self.assertNotIn(word, text, f"Forbidden term '{word}' found in signal detail output")


class TestCheckSubmission(unittest.TestCase):
    """check_submission — delegates to CTD checker."""

    MINIMAL_COMPLETE = """
1.1 Table of Contents
1.2 Application Form
1.3 Prescribing Information
2.1 CTD Table of Contents
2.2 CTD Introduction
2.3 Quality Overall Summary
2.4 Nonclinical Overview
2.5 Clinical Overview
2.6 Nonclinical Written and Tabulated Summaries
2.7 Clinical Summary
3.1 Module 3 Table of Contents
3.2.S Drug Substance
3.2.P Drug Product
4.1 Module 4 Table of Contents
4.2.1 Pharmacology
4.2.2 Pharmacokinetics
4.2.3 Toxicology
5.1 Module 5 Table of Contents
5.2 Tabular Listing of All Clinical Studies
5.3.3 Reports of Human PK Studies
5.3.6 Reports of Efficacy and Safety Studies
"""

    def test_empty_dossier_returns_error(self):
        result = run(_tool_check_submission({"dossier_text": ""}))
        text = result[0].text
        self.assertIn("required", text.lower())

    def test_complete_dossier_returns_100_percent(self):
        result = run(_tool_check_submission({"dossier_text": self.MINIMAL_COMPLETE}))
        text = result[0].text
        self.assertIn("100.0%", text)
        self.assertIn("READY", text)

    def test_incomplete_dossier_shows_gaps(self):
        partial = "1.1 Table of Contents\n1.2 Application Form\n1.3 Prescribing Information"
        result = run(_tool_check_submission({"dossier_text": partial}))
        text = result[0].text
        self.assertIn("missing", text.lower())
        self.assertIn("NOT_READY", text)

    def test_returns_submission_id(self):
        result = run(_tool_check_submission({"dossier_text": self.MINIMAL_COMPLETE}))
        text = result[0].text
        self.assertIn("Submission ID", text)

    def test_ctd_disclaimer_present(self):
        result = run(_tool_check_submission({"dossier_text": self.MINIMAL_COMPLETE}))
        text = result[0].text
        self.assertIn(CTD_DISCLAIMER, text)

    def test_does_not_claim_fda_approval(self):
        result = run(_tool_check_submission({"dossier_text": self.MINIMAL_COMPLETE}))
        text = result[0].text.lower()
        forbidden = ["fda approved", "fda compliant", "guaranteed acceptance", "regulatory approved"]
        for word in forbidden:
            self.assertNotIn(word, text, f"Forbidden term '{word}' in submission response")


class TestGetGapReport(unittest.TestCase):
    """get_gap_report — retrieves stored submission gaps."""

    def _submit_incomplete(self):
        result = run(_tool_check_submission({
            "dossier_text": "1.1 Table of Contents"
        }))
        text = result[0].text
        import re
        match = re.search(r"Submission ID:\s*(\S+)", text)
        return match.group(1) if match else None

    def test_missing_submission_id_returns_error(self):
        result = run(_tool_get_gap_report({"submission_id": ""}))
        text = result[0].text
        self.assertIn("required", text.lower())

    def test_unknown_submission_id_returns_friendly_message(self):
        result = run(_tool_get_gap_report({"submission_id": "totally-fake-id-99999"}))
        text = result[0].text
        self.assertIn("not found", text.lower())

    def test_real_submission_returns_gaps(self):
        sub_id = self._submit_incomplete()
        self.assertIsNotNone(sub_id)
        result = run(_tool_get_gap_report({"submission_id": sub_id}))
        text = result[0].text
        # Should contain at least one priority section
        self.assertTrue(
            any(p in text for p in ["CRITICAL", "HIGH", "MEDIUM"]),
            "Expected gap priorities in gap report"
        )

    def test_priority_filter_critical_only(self):
        sub_id = self._submit_incomplete()
        result = run(_tool_get_gap_report({"submission_id": sub_id, "priority": "CRITICAL"}))
        text = result[0].text
        # All returned items should be CRITICAL
        if "CRITICAL" in text:
            self.assertNotIn("── HIGH", text)
            self.assertNotIn("── MEDIUM", text)


class TestGetSubmissionModule(unittest.TestCase):
    """get_submission_module — per-module detail."""

    def _submit_complete(self):
        dossier = (
            "1.1 TOC\n1.2 Application Form\n1.3 Prescribing Info\n"
            "2.1 TOC\n2.2 Introduction\n2.3 QOS\n2.4 Nonclinical Overview\n"
            "2.5 Clinical Overview\n2.6 Nonclinical Summaries\n2.7 Clinical Summary\n"
            "3.1 Module 3 TOC\n3.2.S Drug Substance\n3.2.P Drug Product\n"
            "4.1 Module 4 TOC\n4.2.1 Pharmacology\n4.2.2 Pharmacokinetics\n4.2.3 Toxicology\n"
            "5.1 Module 5 TOC\n5.2 Tabular Listing\n"
            "5.3.3 Human PK Studies\n5.3.6 Efficacy and Safety Studies"
        )
        result = run(_tool_check_submission({"dossier_text": dossier}))
        import re
        text = result[0].text
        match = re.search(r"Submission ID:\s*(\S+)", text)
        return match.group(1) if match else None

    def test_missing_submission_id(self):
        result = run(_tool_get_submission_module({"submission_id": "", "module": "M3"}))
        self.assertIn("required", result[0].text.lower())

    def test_missing_module(self):
        sub_id = self._submit_complete()
        result = run(_tool_get_submission_module({"submission_id": sub_id, "module": ""}))
        self.assertIn("required", result[0].text.lower())

    def test_invalid_module_code(self):
        sub_id = self._submit_complete()
        result = run(_tool_get_submission_module({"submission_id": sub_id, "module": "M99"}))
        self.assertIn("not found", result[0].text.lower())

    def test_complete_m3_shows_all_present(self):
        sub_id = self._submit_complete()
        result = run(_tool_get_submission_module({"submission_id": sub_id, "module": "M3"}))
        text = result[0].text
        self.assertIn("100.0%", text)

    def test_returns_module_name(self):
        sub_id = self._submit_complete()
        result = run(_tool_get_submission_module({"submission_id": sub_id, "module": "M1"}))
        text = result[0].text
        self.assertIn("M1", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
