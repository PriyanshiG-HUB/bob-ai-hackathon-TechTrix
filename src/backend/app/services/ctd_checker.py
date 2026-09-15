"""
ICH M4 CTD Regulatory Submission Readiness Checker Service
==========================================================
Performs deterministic structural validation and gap analysis of pharmaceutical
dossier outlines against official ICH M4(R4) Common Technical Document specifications.

Key Capabilities:
1. parse_dossier_outline: Extracts section numbers, titles, and structural markers from raw text or PDFs.
2. check_submission: Compares parsed outline against ICH M4 requirements hierarchy.
3. calculate_module_scores: Computes completeness % per Module (M1-M5).
4. generate_gap_report: Identifies missing required sections with prioritization (CRITICAL, HIGH, MEDIUM).
5. calculate_overall_readiness: Evaluates prototype readiness classification.

Prototype Readiness Classification:
- 90 - 100% : READY
- 75 - 89%  : MOSTLY_READY
- 50 - 74%  : NEEDS_ATTENTION
- < 50%     : NOT_READY

Important Regulatory Disclaimer:
--------------------------------
This completeness check evaluates structural adherence to the ICH M4 Common Technical
Document (CTD) format outline only. It does not evaluate scientific content, data integrity,
or regulatory adequacy, and does NOT constitute or guarantee regulatory approval or acceptance
by the FDA, EMA, PMDA, or any other authority.
"""

import os
import re
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

logger = logging.getLogger("ctd_checker")

CTD_DISCLAIMER = (
    "This completeness check evaluates structural adherence to the ICH M4 Common Technical "
    "Document (CTD) format outline only. It does not evaluate scientific content, data integrity, "
    "or regulatory adequacy, and does NOT constitute or guarantee regulatory approval or acceptance "
    "by the FDA, EMA, PMDA, or any other health authority."
)


def load_ich_m4_requirements(filepath: Optional[str] = None) -> Dict[str, Any]:
    """Loads official ICH M4 CTD requirements structure."""
    if filepath is None:
        project_root = Path(__file__).resolve().parents[4]
        filepath = str(project_root / "data" / "ich_m4_requirements.json")
        if not os.path.exists(filepath):
            # Fallback
            cwd = Path(os.getcwd()).resolve()
            if (cwd / "data" / "ich_m4_requirements.json").exists():
                filepath = str(cwd / "data" / "ich_m4_requirements.json")
            elif (cwd.parent / "data" / "ich_m4_requirements.json").exists():
                filepath = str(cwd.parent / "data" / "ich_m4_requirements.json")
                
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"ICH M4 requirements file not found at: {filepath}")
        
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_section_id(raw_id: str) -> str:
    """Standardizes section IDs (e.g. '3.2.s' -> '3.2.S', 'Module 1.2' -> '1.2')."""
    s = raw_id.strip().upper()
    s = re.sub(r"^MODULE\s*", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"^SECTION\s*", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"^M", "", s, flags=re.IGNORECASE) if re.match(r"^M\d", s) else s
    return s


def parse_dossier_outline(content: str) -> List[Dict[str, str]]:
    """
    Deterministically parses dossier text/outline to extract identified section numbers and titles.
    Accepts raw text, table of contents lines, or markdown outlines.
    """
    if not content or not content.strip():
        return []
        
    extracted_sections = []
    seen_ids = set()
    
    # Common CTD section ID patterns:
    # 1.1, 1.2, 1.3, 1.6
    # 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
    # 3.1, 3.2.S, 3.2.P, 3.2.A, 3.2.R, 3.3
    # 4.1, 4.2.1, 4.2.2, 4.2.3, 4.3
    # 5.1, 5.2, 5.3.1, 5.3.2, 5.3.3, 5.3.4, 5.3.5, 5.3.6, 5.3.7, 5.4
    # Also matches module headers e.g. "Module 1", "Module 3.2.S"
    
    # Regex pattern matching leading CTD section number followed by title or separator
    pattern = re.compile(
        r"(?:(?:Module|Section|M)\s*)?([1-5](?:\.\d+(?:\.[A-Z0-9]+)*|\.[A-Z]))[:\.\-\s\t]+([^\r\n]+)",
        re.IGNORECASE
    )
    
    lines = content.splitlines()
    for line in lines:
        line_str = line.strip()
        if not line_str or line_str.startswith("#") and len(line_str) == 1:
            continue
            
        # Clean markdown headers
        clean_line = re.sub(r"^#+\s*", "", line_str).strip()
        
        match = pattern.search(clean_line)
        if match:
            raw_sec_id = match.group(1).strip()
            raw_title = match.group(2).strip()
            
            norm_sec_id = _normalize_section_id(raw_sec_id)
            if norm_sec_id not in seen_ids:
                seen_ids.add(norm_sec_id)
                extracted_sections.append({
                    "section_id": norm_sec_id,
                    "title": raw_title or f"Section {norm_sec_id}"
                })
        else:
            # Check for standalone section codes like "3.2.S Drug Substance"
            standalone_match = re.match(r"^([1-5](?:\.[0-9A-Za-z]+)+)\s+(.*)$", clean_line)
            if standalone_match:
                norm_sec_id = _normalize_section_id(standalone_match.group(1))
                if norm_sec_id not in seen_ids:
                    seen_ids.add(norm_sec_id)
                    extracted_sections.append({
                        "section_id": norm_sec_id,
                        "title": standalone_match.group(2).strip() or f"Section {norm_sec_id}"
                    })
                    
    return extracted_sections


def match_section(found_sec_id: str, req_sec_id: str) -> bool:
    """Matches an extracted section ID against an official requirement ID."""
    norm_found = _normalize_section_id(found_sec_id)
    norm_req = _normalize_section_id(req_sec_id)
    
    # Direct match (e.g. "3.2.S" == "3.2.S" or "1.2" == "1.2")
    if norm_found == norm_req:
        return True
        
    # Sub-section matching: If dossier provides "3.2.S.1" or "3.2.S.2", it satisfies parent "3.2.S"
    if norm_found.startswith(norm_req + "."):
        return True
        
    return False


def check_submission(
    dossier_text: str,
    requirements: Optional[Dict[str, Any]] = None,
    submission_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates a dossier outline against ICH M4 requirements.
    Calculates per-module completeness, identifies missing sections, generates gaps, and scores overall readiness.
    """
    if requirements is None:
        requirements = load_ich_m4_requirements()
        
    sub_id = submission_id or str(uuid.uuid4())[:8]
    parsed_sections = parse_dossier_outline(dossier_text)
    found_section_ids = {s["section_id"] for s in parsed_sections}
    
    module_scores: Dict[str, Dict[str, Any]] = {}
    gaps: List[Dict[str, Any]] = []
    
    total_required_sections = 0
    total_required_found = 0
    
    all_present_sections: List[Dict[str, Any]] = []
    all_missing_sections: List[Dict[str, Any]] = []
    
    for mod in requirements.get("modules", []):
        mod_id = mod["module_id"]
        mod_name = mod["module_name"]
        
        mod_req_sections = [s for s in mod.get("sections", []) if s.get("is_required", True)]
        mod_opt_sections = [s for s in mod.get("sections", []) if not s.get("is_required", True)]
        
        mod_present_req = []
        mod_missing_req = []
        mod_present_opt = []
        
        # Check required sections
        for sec in mod_req_sections:
            sec_id = sec["section_id"]
            # Check if any found section satisfies this requirement
            matched_found = [fid for fid in found_section_ids if match_section(fid, sec_id)]
            
            if matched_found:
                mod_present_req.append({
                    "section_id": sec_id,
                    "title": sec["title"],
                    "matched_dossier_section": matched_found[0],
                    "is_required": True
                })
            else:
                mod_missing_req.append({
                    "section_id": sec_id,
                    "title": sec["title"],
                    "is_required": True,
                    "priority_if_missing": sec.get("priority_if_missing", "HIGH"),
                    "importance": sec.get("importance", "Required by ICH M4 guidance.")
                })
                # Add to gaps
                gaps.append({
                    "module_id": mod_id,
                    "section_id": sec_id,
                    "title": sec["title"],
                    "priority": sec.get("priority_if_missing", "HIGH"),
                    "reason": sec.get("importance", "Required by ICH M4 guidance."),
                    "is_required": True
                })
                
        # Check optional sections (informational)
        for sec in mod_opt_sections:
            sec_id = sec["section_id"]
            matched_found = [fid for fid in found_section_ids if match_section(fid, sec_id)]
            if matched_found:
                mod_present_opt.append({
                    "section_id": sec_id,
                    "title": sec["title"],
                    "matched_dossier_section": matched_found[0],
                    "is_required": False
                })
                
        # Module scoring: (required sections found / total required sections) * 100
        req_count = len(mod_req_sections)
        found_req_count = len(mod_present_req)
        
        score_pct = round((found_req_count / req_count * 100.0), 1) if req_count > 0 else 100.0
        
        total_required_sections += req_count
        total_required_found += found_req_count
        
        module_scores[mod_id] = {
            "module_id": mod_id,
            "module_name": mod_name,
            "required_sections_count": req_count,
            "present_required_count": found_req_count,
            "missing_required_count": len(mod_missing_req),
            "completeness_percentage": score_pct,
            "present_sections": mod_present_req + mod_present_opt,
            "missing_required_sections": mod_missing_req
        }
        
        all_present_sections.extend(mod_present_req)
        all_missing_sections.extend(mod_missing_req)
        
    # Overall score & prototype readiness band
    overall_completeness = round((total_required_found / total_required_sections * 100.0), 1) if total_required_sections > 0 else 0.0
    
    if overall_completeness >= 90.0:
        readiness_status = "READY"
        readiness_description = "Dossier structure demonstrates high alignment with ICH M4 requirements."
    elif overall_completeness >= 75.0:
        readiness_status = "MOSTLY_READY"
        readiness_description = "Dossier structure is largely complete with a few outstanding required sections."
    elif overall_completeness >= 50.0:
        readiness_status = "NEEDS_ATTENTION"
        readiness_description = "Significant structural sections are missing across one or more CTD modules."
    else:
        readiness_status = "NOT_READY"
        readiness_description = "Major required CTD modules or sections are absent; substantial assembly required."
        
    # Sort gaps by priority: CRITICAL -> HIGH -> MEDIUM
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    gaps.sort(key=lambda g: priority_order.get(g["priority"], 99))
    
    gap_summary = {
        "total_gaps": len(gaps),
        "critical_gaps": sum(1 for g in gaps if g["priority"] == "CRITICAL"),
        "high_gaps": sum(1 for g in gaps if g["priority"] == "HIGH"),
        "medium_gaps": sum(1 for g in gaps if g["priority"] == "MEDIUM")
    }
    
    result = {
        "submission_id": sub_id,
        "overall_completeness": overall_completeness,
        "readiness_status": readiness_status,
        "readiness_description": readiness_description,
        "total_required_sections": total_required_sections,
        "present_required_sections_count": total_required_found,
        "missing_required_sections_count": len(all_missing_sections),
        "module_scores": module_scores,
        "gaps": gaps,
        "gap_summary": gap_summary,
        "present_sections": all_present_sections,
        "missing_sections": all_missing_sections,
        "extracted_sections_count": len(parsed_sections),
        "disclaimer": CTD_DISCLAIMER
    }
    
    return result


# In-memory store for submission checking results
_submissions_store: Dict[str, Dict[str, Any]] = {}


def store_submission_result(result: Dict[str, Any]) -> str:
    """Caches submission readiness result in memory."""
    sub_id = result["submission_id"]
    _submissions_store[sub_id] = result
    return sub_id


def get_stored_submission(submission_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a stored submission result by ID."""
    return _submissions_store.get(submission_id)
