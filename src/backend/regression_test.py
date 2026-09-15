"""
Regression test: old vs new sample dossier completeness comparison.
Run from src/backend: python regression_test.py
"""
import sys
sys.path.insert(0, '.')

from app.services.ctd_checker import check_submission, load_ich_m4_requirements

reqs = load_ich_m4_requirements()

# Old sample dossier — pre-correction M5 numbering (5.3.2 for Human PK, 5.3.5 for Efficacy)
OLD_SAMPLE = """
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
5.3.1 Biopharmaceutics
5.3.2 Human PK
5.3.5 Clinical Efficacy and Safety
"""

# New sample dossier — corrected M5 numbering (5.3.3 = Human PK, 5.3.6 = Efficacy/Safety)
NEW_SAMPLE = """
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


def print_result(label, r):
    print("=" * 62)
    print(f"  {label}")
    print("=" * 62)
    print(f"  Total required sections : {r['total_required_sections']}")
    print(f"  Present required        : {r['present_required_sections_count']}")
    print(f"  Missing required        : {r['missing_required_sections_count']}")
    print(f"  Overall completeness    : {r['overall_completeness']}%")
    print(f"  Readiness status        : {r['readiness_status']}")
    print()
    for mod_id in ["M1", "M2", "M3", "M4", "M5"]:
        ms = r["module_scores"][mod_id]
        print(
            f"  {mod_id}: {ms['completeness_percentage']}%"
            f"  (required={ms['required_sections_count']},"
            f"  present={ms['present_required_count']},"
            f"  missing={ms['missing_required_count']})"
        )
    if r["gaps"]:
        print()
        print("  REQUIRED GAPS:")
        for g in r["gaps"]:
            print(f"    [{g['priority']}] {g['section_id']} — {g['title']}")
    else:
        print()
        print("  No gaps — all required sections present.")
    print()


old_r = check_submission(OLD_SAMPLE, reqs)
new_r = check_submission(NEW_SAMPLE, reqs)

print_result("OLD SAMPLE (pre-correction: 5.3.2=Human PK, 5.3.5=Efficacy)", old_r)
print_result("NEW SAMPLE (corrected:       5.3.3=Human PK, 5.3.6=Efficacy)", new_r)

print("=" * 62)
print("  DELTA SUMMARY")
print("=" * 62)
print(f"  Overall completeness: {old_r['overall_completeness']}% -> {new_r['overall_completeness']}%")
print(f"  Total required sections: {old_r['total_required_sections']} -> {new_r['total_required_sections']}")
print(f"  Readiness: {old_r['readiness_status']} -> {new_r['readiness_status']}")
old_m5 = old_r["module_scores"]["M5"]
new_m5 = new_r["module_scores"]["M5"]
print(f"  M5 completeness: {old_m5['completeness_percentage']}% -> {new_m5['completeness_percentage']}%")
print(f"  M5 required sections: {old_m5['required_sections_count']} -> {new_m5['required_sections_count']}")
old_m1 = old_r["module_scores"]["M1"]
new_m1 = new_r["module_scores"]["M1"]
print(f"  M1 required sections: {old_m1['required_sections_count']} -> {new_m1['required_sections_count']}"
      f"  (1.6 demoted to optional)")
