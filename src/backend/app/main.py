"""
FastAPI Main Application Entrypoint
===================================
Provides REST API endpoints for FDA FAERS pharmacovigilance safety signal detection,
PRR disproportionality metrics, active-ingredient comparison, and ICH M4 CTD
dossier submission readiness checking.
"""

from typing import Optional
from fastapi import FastAPI, Query, HTTPException, Path as FastPath, Body
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.services.prr import get_engine, MEDICAL_DISCLAIMER
from app.schemas import (
    HealthResponse,
    StatsResponse,
    SignalsResponse,
    SignalDetailResponse,
    DrugComparisonResponse,
    SignalItem
)
from app.services.ctd_checker import (
    check_submission,
    store_submission_result,
    get_stored_submission,
    CTD_DISCLAIMER
)
from app.ctd_schemas import (
    CheckSubmissionRequest,
    SubmissionReadinessResponse,
    GapReportResponse,
    ModuleScore,
    Gap
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load PRR engine on startup (uses compact cache in <0.5s if built)
    get_engine(settings.NORMALIZED_DATA_PATH)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Production-grade deterministic Drug Safety Signal Detection and ICH M4 CTD Regulatory "
        "Submission Readiness API utilizing FDA FAERS/AEMS quarterly data, Proportional Reporting "
        "Ratio (PRR), Pearson Chi-Square, and automated dossier structure verification."
    ),
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# SYSTEM & STATS ENDPOINTS
# =====================================================================

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
    description="Returns the current operational status of the API service and data index."
)
async def health():
    engine = get_engine(settings.NORMALIZED_DATA_PATH)
    return HealthResponse(
        status="healthy",
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        data_loaded=engine.is_loaded
    )


@app.get(
    "/stats",
    response_model=StatsResponse,
    tags=["Dataset"],
    summary="FAERS Dataset Statistics",
    description="Returns core universe statistics, counts of unique suspect reports, active ingredients, and reaction terms."
)
async def get_dataset_stats():
    engine = get_engine(settings.NORMALIZED_DATA_PATH)
    return StatsResponse(
        reporting_period=settings.REPORTING_PERIOD,
        unique_suspect_reports=engine.total_unique_reports,
        unique_active_ingredients=len(engine.drug_reports_count),
        unique_reactions=len(engine.event_reports_count),
        candidate_drug_event_pairs=len(engine.drug_event_pair_count),
        total_normalized_associations=10085069,
        suspect_associations=5785411,
        disclaimer=MEDICAL_DISCLAIMER
    )


# =====================================================================
# SAFETY SIGNAL DETECTION ENDPOINTS
# =====================================================================

@app.get(
    "/signals",
    response_model=SignalsResponse,
    tags=["Signal Detection"],
    summary="Query Ranked Safety Signals",
    description=(
        "Returns ranked statistical disproportionality signals using deterministic PRR and "
        "multi-tier pharmacovigilance prioritization (PRIORITY_1 -> PRIORITY_2 -> REVIEW -> LOW)."
    )
)
async def get_signals(
    drug_name: Optional[str] = Query(None, description="Filter by active ingredient (prod_ai)"),
    min_prr: float = Query(2.0, ge=0.0, description="Minimum PRR threshold (default 2.0)"),
    min_reports: int = Query(3, ge=1, description="Minimum observed report count A (default 3)"),
    priority: Optional[str] = Query(None, description="Filter by priority tier (PRIORITY_1, PRIORITY_2, REVIEW, LOW)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results to return (default 50)")
):
    engine = get_engine(settings.NORMALIZED_DATA_PATH)
    
    raw_signals = engine.detect_signals(
        drug=drug_name,
        min_prr=min_prr,
        min_reports=min_reports,
        priority=priority,
        top_n=limit
    )
    
    signal_items = [SignalItem(**s) for s in raw_signals]
    
    return SignalsResponse(
        total_returned=len(signal_items),
        filters_applied={
            "drug_name": drug_name,
            "min_prr": min_prr,
            "min_reports": min_reports,
            "priority": priority,
            "limit": limit
        },
        signals=signal_items
    )


@app.get(
    "/signals/{drug}/{event}",
    response_model=SignalDetailResponse,
    tags=["Signal Detection"],
    summary="Detailed 2x2 Signal Statistics",
    description="Returns full contingency table cell counts (A, B, C, D), PRR, chi-square, confidence, and contextual interpretation."
)
async def get_signal_detail(
    drug: str = FastPath(..., description="Active ingredient name (prod_ai)"),
    event: str = FastPath(..., description="Adverse reaction MedDRA Preferred Term (reaction_pt)")
):
    engine = get_engine(settings.NORMALIZED_DATA_PATH)
    drug_clean = drug.strip().upper()
    event_clean = event.strip()
    
    if drug_clean not in engine.drug_reports_count:
        raise HTTPException(status_code=404, detail=f"Active ingredient '{drug_clean}' not found in suspect dataset.")
    if event_clean not in engine.event_reports_count:
        raise HTTPException(status_code=404, detail=f"Adverse reaction '{event_clean}' not found in dataset.")
        
    details = engine.get_signal_details(drug_clean, event_clean)
    return SignalDetailResponse(**details)


@app.get(
    "/compare",
    response_model=DrugComparisonResponse,
    tags=["Comparative Analysis"],
    summary="Compare Two Active Ingredients Against an Event",
    description="Performs side-by-side independent PRR disproportionality calculations for two active ingredients against the same adverse reaction."
)
async def compare_drugs(
    drug_a: str = Query(..., description="First active ingredient (prod_ai)"),
    drug_b: str = Query(..., description="Second active ingredient (prod_ai)"),
    event: str = Query(..., description="Target adverse reaction (reaction_pt)")
):
    engine = get_engine(settings.NORMALIZED_DATA_PATH)
    drug_a_clean = drug_a.strip().upper()
    drug_b_clean = drug_b.strip().upper()
    event_clean = event.strip()
    
    if drug_a_clean not in engine.drug_reports_count:
        raise HTTPException(status_code=404, detail=f"Active ingredient '{drug_a_clean}' not found in suspect dataset.")
    if drug_b_clean not in engine.drug_reports_count:
        raise HTTPException(status_code=404, detail=f"Active ingredient '{drug_b_clean}' not found in suspect dataset.")
    if event_clean not in engine.event_reports_count:
        raise HTTPException(status_code=404, detail=f"Adverse reaction '{event_clean}' not found in dataset.")
        
    comparison = engine.compare_drugs(drug_a_clean, drug_b_clean, event_clean)
    return DrugComparisonResponse(
        adverse_event=comparison["adverse_event"],
        drug_a=SignalDetailResponse(**comparison["drug_a"]),
        drug_b=SignalDetailResponse(**comparison["drug_b"]),
        comparison_note=comparison["comparison_note"],
        disclaimer=comparison["disclaimer"]
    )


# =====================================================================
# REGULATORY SUBMISSION READINESS (CTD CHECKER) ENDPOINTS
# =====================================================================

@app.post(
    "/submission/check",
    response_model=SubmissionReadinessResponse,
    tags=["Regulatory Submission"],
    summary="Check Dossier Outline Against ICH M4 CTD",
    description=(
        "Evaluates pharmaceutical dossier outline structure against official ICH M4 specifications, "
        "calculates per-module completeness (M1-M5), detects missing sections, and generates prioritized gap report."
    )
)
async def check_dossier_submission(
    payload: CheckSubmissionRequest = Body(...)
):
    result = check_submission(
        dossier_text=payload.dossier_text,
        submission_id=payload.submission_id
    )
    store_submission_result(result)
    return SubmissionReadinessResponse(**result)


@app.get(
    "/submission/{submission_id}",
    response_model=SubmissionReadinessResponse,
    tags=["Regulatory Submission"],
    summary="Get Stored Submission Readiness Result",
    description="Returns the previously evaluated CTD readiness evaluation by submission ID."
)
async def get_submission_result(
    submission_id: str = FastPath(..., description="Unique submission identifier")
):
    res = get_stored_submission(submission_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Submission evaluation '{submission_id}' not found.")
    return SubmissionReadinessResponse(**res)


@app.get(
    "/submission/{submission_id}/gaps",
    response_model=GapReportResponse,
    tags=["Regulatory Submission"],
    summary="Get Submission Gaps by Priority",
    description="Returns missing required sections for a submission, optionally filtered by priority tier (CRITICAL, HIGH, MEDIUM)."
)
async def get_submission_gaps(
    submission_id: str = FastPath(..., description="Unique submission identifier"),
    priority: Optional[str] = Query(None, description="Filter gaps by priority (CRITICAL, HIGH, MEDIUM)")
):
    res = get_stored_submission(submission_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Submission evaluation '{submission_id}' not found.")
        
    gaps_list = res.get("gaps", [])
    if priority:
        p_clean = priority.strip().upper()
        filtered_gaps = [g for g in gaps_list if g.get("priority") == p_clean]
    else:
        filtered_gaps = gaps_list
        
    return GapReportResponse(
        submission_id=submission_id,
        filter_priority=priority,
        total_gaps=len(filtered_gaps),
        gap_summary=res.get("gap_summary", {}),
        gaps=filtered_gaps,
        disclaimer=CTD_DISCLAIMER
    )


@app.get(
    "/submission/{submission_id}/modules/{module}",
    response_model=ModuleScore,
    tags=["Regulatory Submission"],
    summary="Get Detailed Module Completeness",
    description="Returns detailed completeness score, detected sections, and missing sections for a specific CTD module (M1-M5)."
)
async def get_module_detail(
    submission_id: str = FastPath(..., description="Unique submission identifier"),
    module: str = FastPath(..., description="CTD Module code (M1, M2, M3, M4, M5 or 1, 2, 3, 4, 5)")
):
    res = get_stored_submission(submission_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Submission evaluation '{submission_id}' not found.")
        
    mod_clean = module.strip().upper()
    if not mod_clean.startswith("M") and mod_clean.isdigit():
        mod_clean = f"M{mod_clean}"
        
    mod_scores = res.get("module_scores", {})
    if mod_clean not in mod_scores:
        raise HTTPException(
            status_code=404,
            detail=f"Module '{module}' not found. Valid modules are M1, M2, M3, M4, M5."
        )
        
    return ModuleScore(**mod_scores[mod_clean])
