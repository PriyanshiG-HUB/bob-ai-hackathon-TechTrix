"""
Pydantic Schemas for CTD Regulatory Submission Checker
======================================================
Data contracts for dossier outline validation, completeness scoring, and gap reporting.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CheckSubmissionRequest(BaseModel):
    dossier_text: str = Field(..., description="Raw text, markdown outline, or table of contents of the dossier")
    submission_id: Optional[str] = Field(None, description="Optional custom submission identifier")


class CTDSection(BaseModel):
    section_id: str = Field(..., description="CTD Section identifier (e.g. 1.2, 3.2.S, 5.3.5)")
    title: str = Field(..., description="Section title or description")
    is_required: bool = Field(..., description="Whether section is mandatory under ICH M4")
    matched_dossier_section: Optional[str] = Field(None, description="Matched section identifier from uploaded dossier")
    priority_if_missing: Optional[str] = Field(None, description="Priority if missing (CRITICAL, HIGH, MEDIUM)")
    importance: Optional[str] = Field(None, description="Regulatory rationale for section")


class ModuleScore(BaseModel):
    module_id: str = Field(..., description="Module identifier (M1, M2, M3, M4, M5)")
    module_name: str = Field(..., description="Full module name")
    required_sections_count: int = Field(..., description="Total required sections in module")
    present_required_count: int = Field(..., description="Number of required sections found")
    missing_required_count: int = Field(..., description="Number of required sections missing")
    completeness_percentage: float = Field(..., description="Module completeness % (0-100)")
    present_sections: List[CTDSection] = Field(..., description="List of detected sections")
    missing_required_sections: List[CTDSection] = Field(..., description="List of missing required sections")


class Gap(BaseModel):
    module_id: str = Field(..., description="Module where gap occurs (e.g. M3)")
    section_id: str = Field(..., description="Missing CTD section number (e.g. 3.2.S)")
    title: str = Field(..., description="Title of missing section")
    priority: str = Field(..., description="Prioritization tier (CRITICAL, HIGH, MEDIUM)")
    reason: str = Field(..., description="Regulatory importance and gap impact rationale")
    is_required: bool = Field(..., description="Whether section is required")


class GapSummary(BaseModel):
    total_gaps: int = Field(..., description="Total missing required sections")
    critical_gaps: int = Field(..., description="Count of CRITICAL priority gaps")
    high_gaps: int = Field(..., description="Count of HIGH priority gaps")
    medium_gaps: int = Field(..., description="Count of MEDIUM priority gaps")


class SubmissionReadinessResponse(BaseModel):
    submission_id: str = Field(..., description="Unique submission evaluation identifier")
    overall_completeness: float = Field(..., description="Overall required section completeness % (0-100)")
    readiness_status: str = Field(..., description="Prototype readiness status (READY, MOSTLY_READY, NEEDS_ATTENTION, NOT_READY)")
    readiness_description: str = Field(..., description="Description of readiness classification")
    total_required_sections: int = Field(..., description="Total required sections across all modules")
    present_required_sections_count: int = Field(..., description="Required sections found")
    missing_required_sections_count: int = Field(..., description="Required sections missing")
    module_scores: Dict[str, ModuleScore] = Field(..., description="Completeness scores for M1, M2, M3, M4, M5")
    gap_summary: GapSummary = Field(..., description="Summary counts of gaps by priority")
    gaps: List[Gap] = Field(..., description="Detailed list of all missing sections")
    present_sections: List[CTDSection] = Field(..., description="All present required sections")
    missing_sections: List[CTDSection] = Field(..., description="All missing required sections")
    extracted_sections_count: int = Field(..., description="Total raw section markers parsed from outline")
    disclaimer: str = Field(..., description="Standard regulatory disclaimer")


class GapReportResponse(BaseModel):
    submission_id: str = Field(..., description="Submission identifier")
    filter_priority: Optional[str] = Field(None, description="Applied priority filter")
    total_gaps: int = Field(..., description="Total gaps matching query")
    gap_summary: GapSummary = Field(..., description="Summary breakdown of all gaps")
    gaps: List[Gap] = Field(..., description="Filtered list of missing section gaps")
    disclaimer: str = Field(..., description="Standard regulatory disclaimer")
