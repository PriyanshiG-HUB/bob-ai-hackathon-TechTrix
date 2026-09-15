#!/usr/bin/env python3
"""
AetherGuard AI — MCP Server
============================
Exposes AetherGuard's validated PRR signal detection and ICH M4 CTD submission
readiness checking capabilities as MCP tools for IBM Bob.

Architecture:
    Bob (IBM Bob IDE)
      ↓  stdio MCP protocol (mcp 2.x MCPServer)
    This server  (src/mcp_server/server.py)
      ↓  direct Python imports — ZERO duplicate logic
    Existing validated services:
      app.services.prr         — PRR / chi-square engine
      app.services.ctd_checker — ICH M4 CTD checker
      app.config               — shared paths / settings

IMPORTANT:
    This server contains NO business logic of its own.
    All statistical calculations, scoring, and data access delegate
    entirely to the validated AetherGuard service layer.

Safety language policy (enforced in every tool response):
    - Never describe signals as "confirmed", "causal", or "clinically proven".
    - Always preserve the pharmacovigilance disclaimer.
    - Readiness scores are application prototype scores — not FDA/ICH acceptance.

Run:
    cd src/mcp_server
    python server.py

Register with Bob (project-level):
    The .bob/mcp.json in the project root already contains the correct config.
    Open Bob → Settings → MCP → the 'aetherguard-ai' server should appear.
"""

import sys
import os
import logging
from typing import Optional

# ── Path setup ─────────────────────────────────────────────────────────────────
# src/mcp_server/server.py  →  src/backend must be on sys.path
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(os.path.dirname(_THIS_DIR), "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# ── Imports from existing validated services ───────────────────────────────────
from app.services.prr import get_engine              # noqa: E402
from app.services.ctd_checker import (               # noqa: E402
    check_submission,
    store_submission_result,
    get_stored_submission,
    load_ich_m4_requirements,
)
from app.config import settings                      # noqa: E402

# ── MCP 2.x ───────────────────────────────────────────────────────────────────
from mcp.server.mcpserver import MCPServer           # noqa: E402

# ── Logging — MUST use stderr (stdout = MCP protocol channel) ─────────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [AetherGuard-MCP] %(levelname)s — %(message)s",
)
logger = logging.getLogger("aetherguard_mcp")

# ── Constants ──────────────────────────────────────────────────────────────────
PHARMA_DISCLAIMER = (
    "This is a statistical disproportionality signal from spontaneous reports. "
    "It does not establish causality, incidence, prevalence, or clinical risk."
)

CTD_DISCLAIMER = (
    "This completeness check evaluates structural adherence to the ICH M4 Common Technical "
    "Document (CTD) format outline only. It does not evaluate scientific content, data integrity, "
    "or regulatory adequacy, and does NOT constitute or guarantee regulatory approval or acceptance "
    "by the FDA, EMA, PMDA, or any other health authority."
)

# ── Pre-load PRR engine cache ──────────────────────────────────────────────────
_prr_engine = None

def _get_engine():
    global _prr_engine
    if _prr_engine is None:
        _prr_engine = get_engine(settings.NORMALIZED_DATA_PATH)
    return _prr_engine


# ── MCPServer instance ─────────────────────────────────────────────────────────
mcp = MCPServer(
    name="aetherguard-ai",
    version="1.0.0",
    description=(
        "AetherGuard AI — FDA AEMS/FAERS pharmacovigilance safety signal detection "
        "and ICH M4 CTD regulatory submission readiness platform. "
        "All signals are statistical disproportionality findings; "
        "they do not establish causality, incidence, or clinical risk."
    ),
)


# ──────────────────────────────────────────────────────────────────────────────
# Tool: get_system_stats
# ──────────────────────────────────────────────────────────────────────────────
@mcp.tool(
    description=(
        "Return AetherGuard AI dataset statistics: total unique suspect reports, "
        "unique active ingredients, unique adverse event terms, and candidate drug–event "
        "pairs from the FDA AEMS/FAERS 2026 Q1 dataset."
    )
)
def get_system_stats() -> str:
    """Return AetherGuard dataset universe statistics."""
    try:
        engine = _get_engine()
        lines = [
            "AetherGuard AI — Dataset Statistics",
            "Source: FDA AEMS/FAERS 2026 Q1 (January – March 2026)",
            "",
            f"Unique suspect reports:       {engine.total_unique_reports:>12,}",
            f"Unique active ingredients:    {len(engine.drug_reports_count):>12,}",
            f"Unique adverse event terms:   {len(engine.event_reports_count):>12,}",
            f"Candidate drug–event pairs:   {len(engine.drug_event_pair_count):>12,}",
            "",
            "Note: Universe is restricted to reports containing at least one suspect",
            "drug (role_cod PS/SS) with a valid active ingredient and adverse event term.",
        ]
        return "\n".join(lines)
    except Exception as exc:
        logger.error("get_system_stats error: %s", exc, exc_info=True)
        return f"Error retrieving system statistics: {str(exc)}"


# ──────────────────────────────────────────────────────────────────────────────
# Tool: get_signals
# ──────────────────────────────────────────────────────────────────────────────
@mcp.tool(
    description=(
        "Retrieve ranked pharmacovigilance safety signals from FDA AEMS/FAERS 2026 Q1 data "
        "using the AetherGuard PRR (Proportional Reporting Ratio) engine. "
        "Returns statistical disproportionality signals with PRR, chi-square, confidence tier, "
        "and application-level priority (PRIORITY_1 / PRIORITY_2 / REVIEW / LOW). "
        "IMPORTANT: signals are statistical findings only — they do NOT establish causality, "
        "incidence, prevalence, or clinical risk. Priority tiers are application labels, "
        "not FDA regulatory classifications."
    )
)
def get_signals(
    drug: Optional[str] = None,
    min_prr: float = 2.0,
    min_reports: int = 3,
    priority: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Retrieve ranked safety signals.

    Parameters
    ----------
    drug : str, optional
        Filter by active ingredient name (prod_ai), e.g. 'ASPIRIN'.
    min_prr : float
        Minimum PRR threshold. Default 2.0.
    min_reports : int
        Minimum observed report count (A). Default 3.
    priority : str, optional
        Filter: PRIORITY_1, PRIORITY_2, REVIEW, or LOW.
    limit : int
        Maximum results to return. Default 10.
    """
    try:
        engine = _get_engine()
        signals = engine.detect_signals(
            drug=drug or None,
            min_prr=min_prr,
            min_reports=min_reports,
            priority=priority or None,
            top_n=limit,
        )

        if not signals:
            msg = "No signals found matching the specified criteria."
            if drug:
                msg += f" Verify that '{drug}' exists as a suspect active ingredient."
            return msg

        lines = [
            "AetherGuard Safety Signals — FDA AEMS/FAERS 2026 Q1",
            f"Filters: drug={drug or 'all'}, min_prr={min_prr}, "
            f"min_reports={min_reports}, priority={priority or 'all'}, limit={limit}",
            f"Results: {len(signals)} signal(s) returned",
            "",
        ]
        for i, sig in enumerate(signals, 1):
            prr_str = f"{sig['prr']:.2f}" if sig.get("prr") is not None else "N/A"
            chi_str = f"{sig['chi_square']:.2f}" if sig.get("chi_square") is not None else "N/A"
            lines.append(
                f"{i}. [{sig['priority']}] {sig['drug_name']}  ×  {sig['adverse_event']}\n"
                f"   A={sig['a']}  PRR={prr_str}  χ²={chi_str}  "
                f"Confidence={sig['signal_confidence']}\n"
                f"   {sig.get('priority_description', '')}"
            )

        lines += ["", f"⚠ {PHARMA_DISCLAIMER}"]
        return "\n".join(lines)
    except Exception as exc:
        logger.error("get_signals error: %s", exc, exc_info=True)
        return f"Error retrieving signals: {str(exc)}"


# ──────────────────────────────────────────────────────────────────────────────
# Tool: get_signal_detail
# ──────────────────────────────────────────────────────────────────────────────
@mcp.tool(
    description=(
        "Get detailed pharmacovigilance signal statistics for a specific active ingredient "
        "and adverse event pair. Returns the full 2×2 contingency table (A, B, C, D), PRR, "
        "chi-square, drug-event rate, background event rate, signal level, confidence, "
        "priority tier, and contextual interpretation. "
        "IMPORTANT: This is a statistical disproportionality signal from spontaneous reports. "
        "It does NOT establish causality, incidence, prevalence, or clinical risk."
    )
)
def get_signal_detail(drug: str, event: str) -> str:
    """
    Get detailed 2×2 contingency statistics for a drug/event pair.

    Parameters
    ----------
    drug : str
        Active ingredient name (prod_ai), e.g. 'MEDROXYPROGESTERONE ACETATE'.
    event : str
        Adverse event MedDRA Preferred Term, e.g. 'Meningioma'.
    """
    try:
        drug = drug.strip().upper()
        event = event.strip()

        if not drug:
            return "Parameter 'drug' is required and must not be empty."
        if not event:
            return "Parameter 'event' is required and must not be empty."

        engine = _get_engine()

        if drug not in engine.drug_reports_count:
            return (
                f"Active ingredient '{drug}' was not found in the suspect dataset. "
                f"Check spelling or use get_signals to discover available drug names."
            )
        if event not in engine.event_reports_count:
            return (
                f"Adverse event '{event}' was not found in the dataset. "
                f"Check the spelling of the MedDRA Preferred Term."
            )

        detail = engine.get_signal_details(drug, event)

        prr_str = f"{detail['prr']:.4f}" if detail.get("prr") is not None else "Undefined"
        chi_str = f"{detail['chi_square']:.4f}" if detail.get("chi_square") is not None else "N/A"
        der_str = (
            f"{detail['drug_event_rate']*100:.4f}%"
            if detail.get("drug_event_rate") is not None else "N/A"
        )
        ber_str = (
            f"{detail['background_event_rate']*100:.4f}%"
            if detail.get("background_event_rate") is not None else "N/A"
        )

        lines = [
            f"Signal Detail — {drug}  ×  {event}",
            "",
            f"Priority:             {detail['priority']}",
            f"Priority description: {detail.get('priority_description', '')}",
            "",
            "2×2 Contingency Table:",
            f"  A (drug ∩ event):         {detail['a']:>10,}",
            f"  B (drug ∩ other events):  {detail['b']:>10,}",
            f"  C (other drugs ∩ event):  {detail['c']:>10,}",
            f"  D (other drugs ∩ other):  {detail['d']:>10,}",
            "",
            f"PRR:                  {prr_str}",
            f"Chi-Square (χ²):      {chi_str}",
            f"Drug-event rate:      {der_str}",
            f"Background rate:      {ber_str}",
            f"Signal level:         {detail.get('signal_level', 'N/A')}",
            f"Confidence:           {detail.get('confidence', 'N/A')}",
            f"Sparse background:    {'Yes — C < 5, interpret with caution' if detail.get('sparse_background') else 'No'}",
            f"Threshold met:        {'Yes' if detail.get('threshold_met') else 'No'}",
            "",
            f"Interpretation: {detail.get('interpretation', '')}",
            "",
            f"⚠ {PHARMA_DISCLAIMER}",
        ]
        if detail.get("undefined_reason"):
            lines.insert(-1, f"Note: {detail['undefined_reason']}")

        return "\n".join(lines)
    except Exception as exc:
        logger.error("get_signal_detail error: %s", exc, exc_info=True)
        return f"Error retrieving signal detail for {drug} / {event}: {str(exc)}"


# ──────────────────────────────────────────────────────────────────────────────
# Tool: check_submission
# ──────────────────────────────────────────────────────────────────────────────
@mcp.tool(
    description=(
        "Check an ICH M4(R4) CTD dossier outline for structural completeness against the "
        "AetherGuard requirements database. Accepts raw text, a table of contents, or a "
        "markdown outline. Returns per-module completeness scores (M1–M5), missing required "
        "sections, a prioritized gap report, and an overall application readiness band. "
        "IMPORTANT: Readiness scores are APPLICATION PROTOTYPE scores. They evaluate structural "
        "adherence to the ICH M4 CTD format only. They do NOT constitute or guarantee regulatory "
        "approval or acceptance by the FDA, EMA, PMDA, or any other authority."
    )
)
def check_submission_tool(dossier_text: str) -> str:
    """
    Check a CTD dossier outline for structural completeness.

    Parameters
    ----------
    dossier_text : str
        The dossier outline (table of contents or section list).
    """
    try:
        dossier_text = dossier_text.strip()
        if not dossier_text:
            return "'dossier_text' is required and must not be empty."

        reqs = load_ich_m4_requirements()
        result = check_submission(dossier_text, requirements=reqs)
        store_submission_result(result)

        sub_id = result["submission_id"]
        overall = result["overall_completeness"]
        status = result["readiness_status"]
        desc = result["readiness_description"]
        total_req = result["total_required_sections"]
        present = result["present_required_sections_count"]
        missing_count = result["missing_required_sections_count"]
        gap_summary = result.get("gap_summary", {})

        lines = [
            f"CTD Submission Readiness — Submission ID: {sub_id}",
            "",
            f"Overall completeness:  {overall:.1f}%",
            f"Readiness status:      {status}",
            f"Description:           {desc}",
            f"Required sections:     {present} / {total_req} present",
            "",
            "Module Scores:",
        ]
        for mod_id in ["M1", "M2", "M3", "M4", "M5"]:
            ms = result["module_scores"].get(mod_id)
            if ms:
                lines.append(
                    f"  {mod_id}: {ms['completeness_percentage']:.0f}%  "
                    f"({ms['present_required_count']}/{ms['required_sections_count']} sections)"
                )

        if missing_count > 0:
            lines += [
                "",
                f"Gaps: {missing_count} missing required section(s)",
                f"  Critical: {gap_summary.get('critical_gaps', 0)}",
                f"  High:     {gap_summary.get('high_gaps', 0)}",
                f"  Medium:   {gap_summary.get('medium_gaps', 0)}",
                "",
                f"Use get_gap_report with submission_id='{sub_id}' to see the full gap list.",
            ]
        else:
            lines += ["", "No gaps — all required sections are present."]

        lines += ["", f"⚠ {CTD_DISCLAIMER}"]
        return "\n".join(lines)
    except Exception as exc:
        logger.error("check_submission error: %s", exc, exc_info=True)
        return f"Error checking submission: {str(exc)}"


# ──────────────────────────────────────────────────────────────────────────────
# Tool: get_gap_report
# ──────────────────────────────────────────────────────────────────────────────
@mcp.tool(
    description=(
        "Retrieve the gap report for a previously checked CTD submission. "
        "Returns missing required ICH M4 sections sorted by priority (CRITICAL, HIGH, MEDIUM) "
        "with regulatory rationale for each gap. Use check_submission_tool first to obtain "
        "a submission_id."
    )
)
def get_gap_report(
    submission_id: str,
    priority: Optional[str] = None,
) -> str:
    """
    Get the gap report for a prior CTD submission check.

    Parameters
    ----------
    submission_id : str
        The submission ID returned by check_submission_tool.
    priority : str, optional
        Filter: CRITICAL, HIGH, or MEDIUM.
    """
    try:
        submission_id = submission_id.strip()
        if not submission_id:
            return "'submission_id' is required."

        stored = get_stored_submission(submission_id)
        if not stored:
            return (
                f"Submission '{submission_id}' not found. "
                f"Run check_submission_tool first to evaluate a dossier."
            )

        gaps = stored.get("gaps", [])
        if priority:
            gaps = [g for g in gaps if g.get("priority") == priority.upper()]

        if not gaps:
            filter_note = f" with priority filter '{priority}'" if priority else ""
            return f"No gaps found{filter_note} for submission '{submission_id}'."

        lines = [
            f"Gap Report — Submission: {submission_id}",
            f"Filter: {priority or 'All priorities'}",
            f"Total gaps shown: {len(gaps)}",
            "",
        ]
        for p in ["CRITICAL", "HIGH", "MEDIUM"]:
            section_gaps = [g for g in gaps if g.get("priority") == p]
            if not section_gaps:
                continue
            lines.append(f"── {p} ({len(section_gaps)}) ──────────────────────────────")
            for g in section_gaps:
                lines.append(
                    f"  [{g['module_id']}] {g['section_id']} — {g['title']}\n"
                    f"    Reason: {g.get('reason', 'Required by ICH M4 guidance.')}"
                )
            lines.append("")

        lines.append(f"⚠ {CTD_DISCLAIMER}")
        return "\n".join(lines)
    except Exception as exc:
        logger.error("get_gap_report error: %s", exc, exc_info=True)
        return f"Error retrieving gap report: {str(exc)}"


# ──────────────────────────────────────────────────────────────────────────────
# Tool: get_submission_module
# ──────────────────────────────────────────────────────────────────────────────
@mcp.tool(
    description=(
        "Get detailed completeness information for a specific CTD module (M1–M5) "
        "from a previously checked submission. Returns present and missing required sections "
        "with their importance rationale."
    )
)
def get_submission_module(submission_id: str, module: str) -> str:
    """
    Get per-module detail from a prior CTD submission check.

    Parameters
    ----------
    submission_id : str
        The submission ID from check_submission_tool.
    module : str
        CTD module code: M1, M2, M3, M4, or M5.
    """
    try:
        submission_id = submission_id.strip()
        module = module.strip().upper()

        if not submission_id:
            return "'submission_id' is required."
        if not module:
            return "'module' is required (M1, M2, M3, M4, or M5)."

        stored = get_stored_submission(submission_id)
        if not stored:
            return f"Submission '{submission_id}' not found. Run check_submission_tool first."

        ms = stored.get("module_scores", {}).get(module)
        if not ms:
            return (
                f"Module '{module}' not found in submission '{submission_id}'. "
                f"Valid modules: M1, M2, M3, M4, M5."
            )

        lines = [
            f"{module} — {ms['module_name']}",
            f"Completeness: {ms['completeness_percentage']:.1f}%  "
            f"({ms['present_required_count']}/{ms['required_sections_count']} required sections)",
            "",
        ]

        if ms["present_required_count"] > 0:
            lines.append("Present required sections:")
            for sec in ms["present_sections"]:
                if sec.get("is_required"):
                    lines.append(f"  ✓ {sec['section_id']} — {sec['title']}")
            lines.append("")

        if ms["missing_required_count"] > 0:
            lines.append("Missing required sections:")
            for sec in ms["missing_required_sections"]:
                prio = f" [{sec.get('priority_if_missing', '')}]" if sec.get("priority_if_missing") else ""
                lines.append(f"  ✗ {sec['section_id']} — {sec['title']}{prio}")
        else:
            lines.append("All required sections for this module are present.")

        lines += ["", f"⚠ {CTD_DISCLAIMER}"]
        return "\n".join(lines)
    except Exception as exc:
        logger.error("get_submission_module error: %s", exc, exc_info=True)
        return f"Error retrieving module detail: {str(exc)}"


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio

    logger.info("AetherGuard AI MCP server starting…")
    logger.info("Backend dir: %s", _BACKEND_DIR)
    logger.info("Data path:   %s", settings.NORMALIZED_DATA_PATH)

    asyncio.run(mcp.run_stdio_async())
