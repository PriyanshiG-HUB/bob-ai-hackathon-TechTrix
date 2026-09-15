"""
Unit and Integration Tests for Bob AI Chat Bridge API
=====================================================
Tests:
- System statistics question
- Safety signals question (global and drug-specific)
- Signal detail question
- Submission readiness check
- Gap analysis question
- Module drilldown question
- Unsupported / general help question
- Empty message handling
- Disclaimer presence across all responses
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_bob_chat_system_stats():
    response = client.post("/bob/chat", json={"message": "How many reports are in the dataset?"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "system_stats"
    assert data["tool_used"] == "get_system_stats"
    assert "2,437,039" in data["response"]
    assert "disclaimer" in data
    assert "statistical disproportionality" in data["disclaimer"].lower()


def test_bob_chat_safety_signals():
    response = client.post("/bob/chat", json={"message": "Show me the highest priority safety signals."})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "get_signals"
    assert data["tool_used"] == "get_signals"
    assert "PRIORITY_1" in data["response"]
    assert "disclaimer" in data


def test_bob_chat_safety_signals_for_drug():
    response = client.post("/bob/chat", json={"message": "Find signals for ASPIRIN"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "get_signals"
    assert "ASPIRIN" in data["response"]


def test_bob_chat_signal_detail():
    response = client.post(
        "/bob/chat",
        json={"message": "What is the PRR for MEDROXYPROGESTERONE ACETATE and Meningioma?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "signal_detail"
    assert data["tool_used"] == "get_signal_detail"

    # 1. Check data payload values match validated backend service
    d = data["data"]
    assert d is not None
    assert d["drug_name"] == "MEDROXYPROGESTERONE ACETATE"
    assert d["adverse_event"] == "Meningioma"
    assert d["a"] == 11336
    assert d["b"] == 1608
    assert d["c"] == 502
    assert d["d"] == 2423593
    assert pytest.approx(d["prr"], 0.01) == 4229.00
    assert pytest.approx(d["chi_square"], 0.01) == 2041887.44
    assert d["priority"] == "PRIORITY_1"
    assert d["confidence"] == "HIGH"

    # 2. Check formatted response string contains the exact matching metrics and no conflicting numbers
    resp = data["response"]
    assert "11,336" in resp
    assert "1,608" in resp
    assert "502" in resp
    assert "2,423,593" in resp
    assert "4229.00" in resp
    assert "2041887.44" in resp
    assert "PRIORITY_1" in resp




def test_bob_chat_check_submission():
    dossier = (
        "1.1 TOC\n1.2 Application Form\n1.3 Prescribing Info\n"
        "2.1 TOC\n2.2 Introduction\n2.3 QOS\n2.4 Nonclinical Overview\n"
        "2.5 Clinical Overview\n2.6 Nonclinical Summary\n2.7 Clinical Summary\n"
        "3.1 Module 3 TOC\n3.2.S Drug Substance\n3.2.P Drug Product\n"
        "4.1 Module 4 TOC\n4.2.1 Pharmacology\n4.2.2 PK\n4.2.3 Toxicology\n"
        "5.1 Module 5 TOC\n5.2 Tabular Listing\n5.3.3 Human PK\n5.3.6 Efficacy and Safety"
    )
    response = client.post(
        "/bob/chat",
        json={"message": "Check this CTD outline", "dossier_text": dossier}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "check_submission"
    assert data["tool_used"] == "check_submission_tool"
    assert "100.0%" in data["response"] or "100%" in data["response"]
    assert "READY" in data["response"]
    assert "ICH M4" in data["disclaimer"]


def test_bob_chat_gap_report_with_active_submission():
    # First submit partial outline
    dossier_partial = "1.1 TOC\n1.2 Form"
    check_res = client.post("/bob/chat", json={"message": "Check submission", "dossier_text": dossier_partial})
    sub_id = check_res.json()["data"]["submission_id"]

    # Ask for gaps
    gap_res = client.post("/bob/chat", json={"message": f"What are the critical gaps in {sub_id}?"})
    assert gap_res.status_code == 200
    gap_data = gap_res.json()
    assert gap_data["intent"] == "get_gap_report"
    assert "CRITICAL" in gap_data["response"]


def test_bob_chat_module_detail_with_active_submission():
    dossier = "3.1 TOC\n3.2.S Drug Substance\n3.2.P Drug Product"
    check_res = client.post("/bob/chat", json={"message": "Check submission", "dossier_text": dossier})
    sub_id = check_res.json()["data"]["submission_id"]

    mod_res = client.post("/bob/chat", json={"message": f"Show me Module 3 for {sub_id}"})
    assert mod_res.status_code == 200
    mod_data = mod_res.json()
    assert mod_data["intent"] == "get_submission_module"
    assert "M3" in mod_data["response"]


def test_bob_chat_empty_message():
    response = client.post("/bob/chat", json={"message": "   "})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "empty"


def test_bob_chat_unsupported_general_help():
    response = client.post("/bob/chat", json={"message": "Tell me a joke about airplanes"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "general_help"
    assert "AetherGuard AI" in data["response"]
    assert "Safety Signals" in data["response"]
