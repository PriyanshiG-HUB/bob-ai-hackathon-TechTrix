"""
Pydantic Response and Request Schemas
====================================
Defines robust data contracts for pharmacovigilance safety signal detection APIs.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status (e.g. healthy)")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="API Version")
    data_loaded: bool = Field(..., description="Whether the PRR index is in memory")


class StatsResponse(BaseModel):
    reporting_period: str = Field(..., description="FAERS reporting quarter (e.g. 2026 Q1)")
    unique_suspect_reports: int = Field(..., description="Total unique primary_id reports with suspect drugs (Universe N)")
    unique_active_ingredients: int = Field(..., description="Count of distinct suspect active ingredients (prod_ai)")
    unique_reactions: int = Field(..., description="Count of distinct MedDRA adverse reaction Preferred Terms")
    candidate_drug_event_pairs: int = Field(..., description="Count of distinct observed (active ingredient, reaction) pairs")
    total_normalized_associations: Optional[int] = Field(None, description="Total rows in normalized dataset")
    suspect_associations: Optional[int] = Field(None, description="Total suspect rows in normalized dataset")
    disclaimer: str = Field(..., description="Standard pharmacovigilance disclaimer")


class SignalItem(BaseModel):
    drug_name: str = Field(..., description="Normalized active ingredient (prod_ai)")
    adverse_event: str = Field(..., description="MedDRA Preferred Term (reaction_pt)")
    a: int = Field(..., description="Unique reports with target drug and target event")
    b: int = Field(..., description="Unique reports with target drug without target event")
    c: int = Field(..., description="Unique reports with other drugs with target event")
    d: int = Field(..., description="Unique reports with other drugs without target event")
    prr: Optional[float] = Field(None, description="Proportional Reporting Ratio")
    chi_square: Optional[float] = Field(None, description="Pearson Chi-Square statistic (1 df)")
    drug_event_rate: Optional[float] = Field(None, description="A / (A + B)")
    background_event_rate: Optional[float] = Field(None, description="C / (C + D)")
    sparse_background: bool = Field(..., description="True if C < 5")
    signal_level: str = Field(..., description="PRR magnitude label (LOW, MODERATE, HIGH)")
    signal_confidence: str = Field(..., description="Statistical confidence label (LOW, MODERATE, HIGH)")
    priority: str = Field(..., description="Application prioritization tier (PRIORITY_1, PRIORITY_2, REVIEW, LOW)")
    priority_description: str = Field(..., description="Human-readable priority description")
    disclaimer: str = Field(..., description="Standard pharmacovigilance disclaimer")


class SignalsResponse(BaseModel):
    total_returned: int = Field(..., description="Number of signals returned in this page/query")
    filters_applied: Dict[str, Any] = Field(..., description="Query filters applied")
    signals: List[SignalItem] = Field(..., description="List of ranked safety signals")


class SignalDetailResponse(BaseModel):
    drug_name: str = Field(..., description="Normalized active ingredient (prod_ai)")
    adverse_event: str = Field(..., description="MedDRA Preferred Term (reaction_pt)")
    a: int = Field(..., description="Unique reports with target drug and target event")
    b: int = Field(..., description="Unique reports with target drug without target event")
    c: int = Field(..., description="Unique reports with other drugs with target event")
    d: int = Field(..., description="Unique reports with other drugs without target event")
    observed_reports: int = Field(..., description="Report count A")
    drug_event_rate: Optional[float] = Field(None, description="A / (A + B)")
    background_event_rate: Optional[float] = Field(None, description="C / (C + D)")
    prr: Optional[float] = Field(None, description="Proportional Reporting Ratio")
    chi_square: Optional[float] = Field(None, description="Pearson Chi-Square statistic (1 df)")
    sparse_background: bool = Field(..., description="True if C < 5")
    signal_level: str = Field(..., description="PRR magnitude label")
    confidence: str = Field(..., description="Statistical confidence label")
    priority: str = Field(..., description="Application prioritization tier")
    priority_description: str = Field(..., description="Human-readable priority description")
    interpretation: str = Field(..., description="Contextual interpretation of signal metrics")
    disclaimer: str = Field(..., description="Standard pharmacovigilance disclaimer")
    undefined_reason: Optional[str] = Field(None, description="Reason if PRR is undefined")
    threshold_met: bool = Field(..., description="Whether configured screening thresholds are met")


class DrugComparisonResponse(BaseModel):
    adverse_event: str = Field(..., description="Target adverse reaction compared")
    drug_a: SignalDetailResponse = Field(..., description="Statistics for Drug A")
    drug_b: SignalDetailResponse = Field(..., description="Statistics for Drug B")
    comparison_note: str = Field(..., description="Methodological comparative interpretation notice")
    disclaimer: str = Field(..., description="Standard pharmacovigilance disclaimer")
