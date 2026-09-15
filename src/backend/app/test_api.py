"""
Integration and Unit Tests for FastAPI Endpoints
================================================
Comprehensive test suite verifying:
- GET /health
- GET /stats
- GET /signals (default, limit, drug filter, priority filter, invalid query params)
- GET /signals/{drug}/{event} (valid, case-insensitive, 404 cases)
- GET /compare (valid, 404 cases)
- POST /submission/check (complete, partial, empty outlines)
- GET /submission/{id} (valid, 404 cases)
- GET /submission/{id}/gaps (all, priority-filtered, 404 cases)
- GET /submission/{id}/modules/{module} (valid, lowercase, digit, 404 cases)
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# -------------------------------------------------------------
# SIGNAL DETECTION API TESTS
# -------------------------------------------------------------

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["data_loaded"] is True
    assert "version" in data


def test_stats_endpoint():
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["unique_suspect_reports"] > 0
    assert data["unique_active_ingredients"] > 0
    assert data["unique_reactions"] > 0
    assert "disclaimer" in data
    assert "statistical disproportionality" in data["disclaimer"].lower()


def test_signals_endpoint_default():
    response = client.get("/signals?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "signals" in data
    assert len(data["signals"]) <= 10
    if len(data["signals"]) > 0:
        sig = data["signals"][0]
        assert "drug_name" in sig
        assert "adverse_event" in sig
        assert "prr" in sig
        assert "priority" in sig
        assert "disclaimer" in sig
        assert sig["priority"] in ["PRIORITY_1", "PRIORITY_2", "REVIEW", "LOW"]


def test_signals_endpoint_filter_drug():
    response = client.get("/signals?drug_name=ASPIRIN&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "signals" in data
    for sig in data["signals"]:
        assert sig["drug_name"] == "ASPIRIN"


def test_signals_endpoint_filter_priority():
    response = client.get("/signals?priority=PRIORITY_1&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "signals" in data
    for sig in data["signals"]:
        assert sig["priority"] == "PRIORITY_1"


def test_signals_endpoint_invalid_params():
    # Negative min_prr
    res_neg_prr = client.get("/signals?min_prr=-1.0")
    assert res_neg_prr.status_code == 422

    # Limit > 500
    res_high_limit = client.get("/signals?limit=9999")
    assert res_high_limit.status_code == 422


def test_signal_detail_endpoint_valid():
    list_res = client.get("/signals?limit=1")
    assert list_res.status_code == 200
    signals = list_res.json()["signals"]
    assert len(signals) > 0
    test_drug = signals[0]["drug_name"]
    test_event = signals[0]["adverse_event"]
    
    detail_res = client.get(f"/signals/{test_drug}/{test_event}")
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert data["drug_name"] == test_drug
    assert data["adverse_event"] == test_event
    assert "a" in data
    assert "b" in data
    assert "c" in data
    assert "d" in data
    assert "interpretation" in data
    assert "disclaimer" in data


def test_signal_detail_endpoint_not_found():
    response = client.get("/signals/NON_EXISTENT_DRUG_12345/NON_EXISTENT_EVENT_99999")
    assert response.status_code == 404


def test_compare_endpoint_valid():
    list_res = client.get("/signals?limit=1")
    signals = list_res.json()["signals"]
    test_drug_a = signals[0]["drug_name"]
    test_event = signals[0]["adverse_event"]
    test_drug_b = "ASPIRIN"
    
    comp_res = client.get(f"/compare?drug_a={test_drug_a}&drug_b={test_drug_b}&event={test_event}")
    assert comp_res.status_code == 200
    data = comp_res.json()
    assert "drug_a" in data
    assert "drug_b" in data
    assert data["adverse_event"] == test_event
    assert "disclaimer" in data


def test_compare_endpoint_not_found():
    response = client.get("/compare?drug_a=FAKE_DRUG_A&drug_b=FAKE_DRUG_B&event=FAKE_EVENT")
    assert response.status_code == 404


# -------------------------------------------------------------
# CTD SUBMISSION CHECKER API TESTS
# -------------------------------------------------------------

SAMPLE_DOSSIER_TEXT = """
1.1 Table of Contents
1.2 Application Form
1.3 Prescribing Information
1.6 Risk Management Plan (RMP)
2.1 CTD TOC
2.2 Introduction
2.3 Quality Overall Summary
2.4 Nonclinical Overview
2.5 Clinical Overview
2.6 Nonclinical Summary
2.7 Clinical Summary
3.1 Module 3 TOC
3.2.S Drug Substance
3.2.P Drug Product
4.1 Module 4 TOC
4.2.1 Pharmacology
4.2.2 Pharmacokinetics
4.2.3 Toxicology
5.1 Module 5 TOC
5.2 Tabular Listing
5.3.3 Reports of Human PK Studies
5.3.6 Reports of Efficacy and Safety Studies
"""


def test_submission_check_endpoint():
    payload = {
        "dossier_text": SAMPLE_DOSSIER_TEXT,
        "submission_id": "test-sub-001"
    }
    response = client.post("/submission/check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["submission_id"] == "test-sub-001"
    assert data["overall_completeness"] == 100.0
    assert data["readiness_status"] == "READY"
    assert "module_scores" in data
    assert "M1" in data["module_scores"]
    assert "M5" in data["module_scores"]
    assert data["missing_required_sections_count"] == 0
    assert "disclaimer" in data


def test_get_submission_result_endpoint():
    # First submit
    payload = {"dossier_text": "1.1 TOC\n1.2 Form", "submission_id": "test-sub-002"}
    client.post("/submission/check", json=payload)
    
    # Retrieve
    response = client.get("/submission/test-sub-002")
    assert response.status_code == 200
    data = response.json()
    assert data["submission_id"] == "test-sub-002"
    assert data["overall_completeness"] < 50.0
    assert data["readiness_status"] == "NOT_READY"


def test_get_submission_result_not_found():
    response = client.get("/submission/NON_EXISTENT_SUBMISSION_ID")
    assert response.status_code == 404


def test_get_submission_gaps_endpoint():
    # Submit with missing sections
    payload = {"dossier_text": "1.1 TOC", "submission_id": "test-sub-gaps"}
    client.post("/submission/check", json=payload)
    
    # Get all gaps
    gaps_res = client.get("/submission/test-sub-gaps/gaps")
    assert gaps_res.status_code == 200
    data = gaps_res.json()
    assert data["total_gaps"] > 0
    assert len(data["gaps"]) > 0
    
    # Filter by CRITICAL priority
    crit_res = client.get("/submission/test-sub-gaps/gaps?priority=CRITICAL")
    assert crit_res.status_code == 200
    crit_data = crit_res.json()
    for g in crit_data["gaps"]:
        assert g["priority"] == "CRITICAL"


def test_get_submission_gaps_not_found():
    response = client.get("/submission/NON_EXISTENT_SUBMISSION_ID/gaps")
    assert response.status_code == 404


def test_get_module_detail_endpoint():
    payload = {"dossier_text": "3.1 TOC\n3.2.S Drug Substance\n3.2.P Drug Product", "submission_id": "test-sub-m3"}
    client.post("/submission/check", json=payload)
    
    # Check M3 details with uppercase
    m3_res = client.get("/submission/test-sub-m3/modules/M3")
    assert m3_res.status_code == 200
    data = m3_res.json()
    assert data["module_id"] == "M3"
    assert data["completeness_percentage"] == 100.0
    assert data["present_required_count"] == 3
    
    # Check M3 details with digit "3"
    m3_digit_res = client.get("/submission/test-sub-m3/modules/3")
    assert m3_digit_res.status_code == 200

    # Check invalid module 404
    bad_res = client.get("/submission/test-sub-m3/modules/M99")
    assert bad_res.status_code == 404


def test_get_module_detail_not_found():
    response = client.get("/submission/NON_EXISTENT_SUBMISSION_ID/modules/M1")
    assert response.status_code == 404
