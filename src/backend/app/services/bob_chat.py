"""
AetherGuard AI — Bob Chat Orchestration Router
===============================================
Routes user questions to existing validated AetherGuard services/tools:
1. get_system_stats: Universe & dataset statistics
2. get_signals: Ranked safety signals & drug queries
3. get_signal_detail: 2x2 contingency table & disproportionality metrics
4. check_submission_tool: CTD dossier outline completeness & readiness
5. get_gap_report: Missing required section gap analysis
6. get_submission_module: Module-level drilldown (M1-M5)

Safety Language Enforcement:
- Never describe signals as "confirmed", "causal", or "proven".
- Always preserve statistical disproportionality and regulatory disclaimers.
- Does not pretend to be an external proprietary IBM Bob hosted API.
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field

from app.services.prr import (
    get_engine,
    MEDICAL_DISCLAIMER,
    DEFAULT_MIN_PRR,
    DEFAULT_MIN_REPORTS,
    DEFAULT_GLOBAL_MIN_REPORTS
)
from app.services.ctd_checker import (
    check_submission,
    store_submission_result,
    get_stored_submission,
    load_ich_m4_requirements,
    CTD_DISCLAIMER,
    _submissions_store
)
from app.config import settings

logger = logging.getLogger("bob_chat")

HELP_RESPONSE = (
    "I am the AetherGuard AI assistant (local tool bridge). I can help you with:\n\n"
    "1. **Safety Signals**: Explore high-priority signals or filter by drug (e.g. *\"Show me the highest priority safety signals\"*, *\"Find signals for aspirin\"*)\n"
    "2. **Signal Details & PRR**: Inspect 2×2 contingency metrics and disproportionality ratios (e.g. *\"What is the PRR for MEDROXYPROGESTERONE ACETATE and Meningioma?\"*)\n"
    "3. **Submission Readiness**: Check dossier outlines against ICH M4(R4) CTD requirements (e.g. *\"Check this CTD outline: 1.1 TOC, 1.2 Form, 2.1 TOC...\"*)\n"
    "4. **Regulatory Gaps**: Review missing required CTD sections by priority (e.g. *\"What are the critical gaps in submission {id}?\"*)\n"
    "5. **Module Completeness**: Drill down into Module 1–5 scores (e.g. *\"Show me Module 3 for submission {id}\"*)\n"
    "6. **Dataset Statistics**: Inquire about dataset size and universe metrics (e.g. *\"How many reports are in the dataset?\"*)\n\n"
    f"⚠ {MEDICAL_DISCLAIMER}"
)


class BobChatRequest(BaseModel):
    message: str = Field(..., description="User query or instruction")
    dossier_text: Optional[str] = Field(None, description="Optional raw dossier outline if checking submission")
    submission_id: Optional[str] = Field(None, description="Optional active submission ID for context")


class BobChatResponse(BaseModel):
    response: str = Field(..., description="Assistant textual answer")
    tool_used: Optional[str] = Field(None, description="AetherGuard tool invoked (or None)")
    intent: str = Field(..., description="Detected user intent")
    data: Optional[Dict[str, Any]] = Field(None, description="Structured payload returned by tool")
    disclaimer: str = Field(..., description="Mandatory safety / regulatory disclaimer")


def _extract_submission_id(text: str, current_sub_id: Optional[str]) -> Optional[str]:
    """Finds an 8-char hex or custom submission ID in text or returns context ID."""
    if current_sub_id and current_sub_id.strip():
        return current_sub_id.strip()
    # Check if any known submission ID from store is explicitly mentioned
    for k in _submissions_store.keys():
        if k.lower() in text.lower():
            return k
    # Look for hex/id patterns
    matches = re.findall(r"\b([a-f0-9]{8}|[a-zA-Z0-9_\-]{4,20})\b", text)
    for m in matches:
        if m.lower() not in [
            "submission", "module", "report", "check", "gaps", "critical",
            "what", "show", "tell", "this", "that", "first", "highest", "ready"
        ]:
            if m in _submissions_store:
                return m
    if _submissions_store:
        # Fallback to the latest submission in memory
        return list(_submissions_store.keys())[-1]
    return None


def route_bob_chat(
    message: str,
    dossier_text: Optional[str] = None,
    submission_id: Optional[str] = None
) -> BobChatResponse:
    """Deterministic routing and response generation based on intent classification."""
    msg_clean = message.strip()
    if not msg_clean:
        return BobChatResponse(
            response="Please enter a question or command. Type 'help' to see what I can do.",
            tool_used=None,
            intent="empty",
            data=None,
            disclaimer=MEDICAL_DISCLAIMER
        )

    msg_lower = msg_clean.lower()
    engine = get_engine(settings.NORMALIZED_DATA_PATH)

    # -------------------------------------------------------------
    # 1. SYSTEM STATS & UNIVERSE METRICS
    # -------------------------------------------------------------
    if any(k in msg_lower for k in ["how many reports", "dataset stat", "system stat", "what data", "universe size", "total reports", "about dataset", "faers data"]):
        stats_data = {
            "reporting_period": settings.REPORTING_PERIOD,
            "unique_suspect_reports": engine.total_unique_reports,
            "unique_active_ingredients": len(engine.drug_reports_count),
            "unique_reactions": len(engine.event_reports_count),
            "candidate_drug_event_pairs": len(engine.drug_event_pair_count),
        }
        text_resp = (
            f"**AetherGuard AI — Dataset Statistics ({settings.REPORTING_PERIOD})**\n\n"
            f"• **Total Unique Suspect Reports ($N$)**: {engine.total_unique_reports:,}\n"
            f"• **Unique Active Ingredients (`prod_ai`)**: {len(engine.drug_reports_count):,}\n"
            f"• **Unique Adverse Event Terms (`reaction_pt`)**: {len(engine.event_reports_count):,}\n"
            f"• **Observed Drug–Event Pairs**: {len(engine.drug_event_pair_count):,}\n\n"
            "Note: The analysis universe strictly includes unique reports containing at least one suspect drug "
            "(role code PS/SS) with valid active ingredient and reaction terms.\n\n"
            f"⚠ {MEDICAL_DISCLAIMER}"
        )
        return BobChatResponse(
            response=text_resp,
            tool_used="get_system_stats",
            intent="system_stats",
            data=stats_data,
            disclaimer=MEDICAL_DISCLAIMER
        )

    # -------------------------------------------------------------
    # 2. SIGNAL DETAIL (DRUG + EVENT PAIR)
    # -------------------------------------------------------------
    # Match patterns like "PRR for DRUG and EVENT", "details for DRUG and EVENT"
    prr_detail_match = re.search(
        r"(?:prr|detail|details|contingency|table)\s+(?:for|of|on)?\s*([A-Za-z0-9\s\\/\-]+?)\s+(?:and|&|x|×|with)\s+([A-Za-z0-9\s\-]+)",
        msg_clean,
        re.IGNORECASE
    )
    if prr_detail_match:
        cand_drug = prr_detail_match.group(1).strip().upper()
        cand_event = prr_detail_match.group(2).strip()

        # Strip extraneous words
        cand_drug = re.sub(r"^(?:THE\s+|WHAT\s+IS\s+|SHOW\s+ME\s+)", "", cand_drug, flags=re.IGNORECASE).strip()

        # Case-insensitive resolution of drug and event against index keys
        matched_drug = None
        for d_key in engine.drug_reports_count:
            if d_key.upper() == cand_drug.upper():
                matched_drug = d_key
                break

        matched_event = None
        if cand_event in engine.event_reports_count:
            matched_event = cand_event
        else:
            for e_key in engine.event_reports_count:
                if e_key.lower() == cand_event.lower():
                    matched_event = e_key
                    break

        if matched_drug and matched_event:
            detail = engine.get_signal_details(matched_drug, matched_event)
            prr_val = f"{detail['prr']:.2f}" if detail.get("prr") is not None else "Undefined"
            chi2_val = f"{detail['chi_square']:.2f}" if detail.get("chi_square") is not None else "N/A"

            text_resp = (
                f"**Signal Detail — {matched_drug} × {matched_event}**\n\n"
                f"• **Priority Tier**: `{detail['priority']}` ({detail.get('priority_description', '')})\n"
                f"• **Signal Level (PRR)**: `{detail.get('signal_level', 'N/A')}` | **Statistical Confidence**: `{detail.get('confidence', 'N/A')}`\n"
                f"• **PRR**: **{prr_val}** | **Chi-Square (χ²)**: **{chi2_val}**\n"

                f"• **Drug Event Rate**: {detail.get('drug_event_rate', 0)*100:.3f}% | **Background Rate**: {detail.get('background_event_rate', 0)*100:.5f}%\n"
                f"• **Sparse Background ($C < 5$)**: {'Yes' if detail.get('sparse_background') else 'No'}\n\n"
                f"**2×2 Contingency Table**:\n"
                f"- $A$ (Drug $D$ + Event $E$): **{detail['a']:,}**\n"
                f"- $B$ (Drug $D$ + Other Events): **{detail['b']:,}** (Total for {matched_drug}: {detail['a']+detail['b']:,})\n"
                f"- $C$ (Other Drugs + Event $E$): **{detail['c']:,}**\n"
                f"- $D$ (Other Drugs + Other Events): **{detail['d']:,}**\n\n"
                f"*{detail.get('interpretation', '')}*\n\n"
                f"⚠ {MEDICAL_DISCLAIMER}"
            )
            return BobChatResponse(
                response=text_resp,
                tool_used="get_signal_detail",
                intent="signal_detail",
                data=detail,
                disclaimer=MEDICAL_DISCLAIMER
            )


    # -------------------------------------------------------------
    # 3. SAFETY SIGNALS LIST & DRUG QUERIES
    # -------------------------------------------------------------
    if any(k in msg_lower for k in ["signal", "safety", "prr", "highest priority", "top signals", "disproportionality"]):
        # Extract drug name if specified (e.g. "for aspirin", "drug: aspirin")
        drug_name = None
        drug_match = re.search(r"(?:for|drug|active ingredient)[:\s]+([A-Za-z0-9\s\\/\-]+)$", msg_clean, re.IGNORECASE)
        if drug_match:
            candidate = drug_match.group(1).strip().upper()
            candidate = re.sub(r"^(?:THE\s+|A\s+|ALL\s+)", "", candidate).strip()
            if candidate in engine.drug_reports_count:
                drug_name = candidate

        # Extract priority if specified
        priority_filter = None
        for p in ["PRIORITY_1", "PRIORITY_2", "REVIEW", "LOW"]:
            if p.lower() in msg_lower:
                priority_filter = p
                break
        if not priority_filter and ("critical" in msg_lower or "highest" in msg_lower or "high priority" in msg_lower):
            priority_filter = "PRIORITY_1"

        signals = engine.detect_signals(
            drug=drug_name,
            min_prr=DEFAULT_MIN_PRR,
            min_reports=DEFAULT_GLOBAL_MIN_REPORTS if not drug_name else DEFAULT_MIN_REPORTS,
            priority=priority_filter,
            top_n=10
        )

        if not signals:
            msg_txt = f"No safety signals found for criteria (drug: {drug_name or 'all'}, priority: {priority_filter or 'all'})."
            return BobChatResponse(
                response=msg_txt,
                tool_used="get_signals",
                intent="get_signals",
                data={"signals": []},
                disclaimer=MEDICAL_DISCLAIMER
            )

        lines = [
            f"**AetherGuard Safety Signals (FDA AEMS/FAERS {settings.REPORTING_PERIOD})**\n",
            f"Filters applied: **Drug**: `{drug_name or 'All'}` | **Priority**: `{priority_filter or 'All'}`\n"
        ]
        for i, s in enumerate(signals[:10], 1):
            prr_str = f"{s['prr']:.2f}" if s.get("prr") is not None else "N/A"
            chi2_str = f"{s['chi_square']:.1f}" if s.get("chi_square") is not None else "N/A"
            lines.append(
                f"{i}. **[{s['priority']}]** `{s['drug_name']}` × **{s['adverse_event']}**\n"
                f"   • $A={s['a']}$ reports | PRR = **{prr_str}** | $\\chi^2 = {chi2_str}$ | Confidence: `{s['signal_confidence']}`\n"
                f"   • *{s.get('priority_description', '')}*"
            )

        lines.append(f"\n⚠ {MEDICAL_DISCLAIMER}")
        return BobChatResponse(
            response="\n".join(lines),
            tool_used="get_signals",
            intent="get_signals",
            data={"signals": signals[:10]},
            disclaimer=MEDICAL_DISCLAIMER
        )

    # -------------------------------------------------------------
    # 4. SUBMISSION READINESS & DOSSIER CHECK
    # -------------------------------------------------------------
    # Check if dossier text was provided directly or in message
    has_dossier_content = dossier_text or any(sec in msg_clean for sec in ["1.1", "1.2", "2.1", "3.2.S", "4.2.1", "5.3.5", "Module 1", "Module 2", "Module 3"])
    if any(k in msg_lower for k in ["check this", "check submission", "analyze dossier", "check ctd", "check my submission"]) or (has_dossier_content and "ready" in msg_lower):
        text_to_check = dossier_text if dossier_text else msg_clean
        # Strip conversational prefix if embedded in message
        text_to_check = re.sub(r"^(?:check this ctd|check submission|analyze dossier|is my submission ready)[:\s]*", "", text_to_check, flags=re.IGNORECASE)

        reqs = load_ich_m4_requirements()
        res = check_submission(text_to_check, requirements=reqs, submission_id=submission_id)
        store_submission_result(res)

        lines = [
            f"**ICH M4 CTD Submission Readiness Assessment**\n",
            f"• **Submission ID**: `{res['submission_id']}`",
            f"• **Overall Completeness**: **{res['overall_completeness']}%** (`{res['readiness_status']}`)",
            f"• **Description**: {res['readiness_description']}",
            f"• **Required Sections Present**: {res['present_required_sections_count']} / {res['total_required_sections']}\n",
            "**Module Scores (M1–M5)**:"
        ]
        for m_id, m_data in res["module_scores"].items():
            lines.append(f"- **{m_id}**: {m_data['completeness_percentage']:.0f}% ({m_data['present_required_count']}/{m_data['required_sections_count']} sections)")

        if res["missing_required_sections_count"] > 0:
            lines.append(f"\n**Missing Sections ({res['missing_required_sections_count']} Gaps)**:")
            lines.append(f"• Critical Gaps: {res['gap_summary']['critical_gaps']} | High: {res['gap_summary']['high_gaps']} | Medium: {res['gap_summary']['medium_gaps']}")
            lines.append(f"Ask *\"What are the critical gaps in submission {res['submission_id']}?\"* for full gap analysis.")
        else:
            lines.append("\n✓ **All required ICH M4 sections detected in outline.**")

        lines.append(f"\n⚠ {CTD_DISCLAIMER}")
        return BobChatResponse(
            response="\n".join(lines),
            tool_used="check_submission_tool",
            intent="check_submission",
            data=res,
            disclaimer=CTD_DISCLAIMER
        )

    # -------------------------------------------------------------
    # 5. GAP REPORT & "WHAT SHOULD I FIX FIRST"
    # -------------------------------------------------------------
    if any(k in msg_lower for k in ["gap", "gaps", "what should i fix", "fix first", "missing section", "critical gap"]):
        active_sub_id = _extract_submission_id(msg_clean, submission_id)
        if not active_sub_id or active_sub_id not in _submissions_store:
            return BobChatResponse(
                response=(
                    "To review regulatory gaps, please first submit or check a dossier outline "
                    "(e.g. on the **Submission Readiness** page or by providing your dossier outline here).\n\n"
                    "Example: *\"Check this CTD outline: 1.1 TOC, 1.2 Form, 2.1 TOC, 3.1 TOC...\"*"
                ),
                tool_used=None,
                intent="get_gap_report_prompt",
                data=None,
                disclaimer=CTD_DISCLAIMER
            )

        stored = get_stored_submission(active_sub_id)
        gaps = stored.get("gaps", [])

        # Priority filter
        if "critical" in msg_lower:
            gaps = [g for g in gaps if g["priority"] == "CRITICAL"]
        elif "high" in msg_lower:
            gaps = [g for g in gaps if g["priority"] == "HIGH"]

        if not gaps:
            return BobChatResponse(
                response=f"No gaps found for submission `{active_sub_id}`. All evaluated required sections are present.",
                tool_used="get_gap_report",
                intent="get_gap_report",
                data={"submission_id": active_sub_id, "gaps": []},
                disclaimer=CTD_DISCLAIMER
            )

        lines = [
            f"**Regulatory Gap Analysis — Submission `{active_sub_id}`**\n",
            f"Found **{len(gaps)}** outstanding gap(s):\n"
        ]
        for g in gaps:
            lines.append(
                f"• **[{g['priority']}]** `[{g['module_id']}] Section {g['section_id']}` — **{g['title']}**\n"
                f"   *Impact/Rationale*: {g.get('reason', 'Required under ICH M4 guidelines.')}"
            )

        lines.append(f"\n⚠ {CTD_DISCLAIMER}")
        return BobChatResponse(
            response="\n".join(lines),
            tool_used="get_gap_report",
            intent="get_gap_report",
            data={"submission_id": active_sub_id, "gaps": gaps},
            disclaimer=CTD_DISCLAIMER
        )

    # -------------------------------------------------------------
    # 6. MODULE-SPECIFIC DRILLDOWN (M1 - M5)
    # -------------------------------------------------------------
    mod_match = re.search(r"\b(m[1-5]|module\s*[1-5])\b", msg_lower)
    if mod_match and any(k in msg_lower for k in ["show", "what is missing", "score", "detail", "status"]):
        mod_code = mod_match.group(1).upper().replace("ODULE", "").replace(" ", "")
        if not mod_code.startswith("M"):
            mod_code = f"M{mod_code}"

        active_sub_id = _extract_submission_id(msg_clean, submission_id)
        if not active_sub_id or active_sub_id not in _submissions_store:
            return BobChatResponse(
                response=(
                    f"To view details for {mod_code}, please first submit a dossier outline on the **Submission Readiness** page "
                    f"or paste your outline here for analysis."
                ),
                tool_used=None,
                intent="get_submission_module_prompt",
                data=None,
                disclaimer=CTD_DISCLAIMER
            )

        stored = get_stored_submission(active_sub_id)

        ms = stored.get("module_scores", {}).get(mod_code)
        if not ms:
            return BobChatResponse(
                response=f"Module {mod_code} information not found for submission `{active_sub_id}`.",
                tool_used="get_submission_module",
                intent="get_submission_module",
                data=None,
                disclaimer=CTD_DISCLAIMER
            )

        lines = [
            f"**{mod_code} — {ms['module_name']}**\n",
            f"• **Completeness**: **{ms['completeness_percentage']:.1f}%** ({ms['present_required_count']}/{ms['required_sections_count']} required sections)\n"
        ]
        if ms["missing_required_count"] > 0:
            lines.append("**Missing Required Sections**:")
            for s in ms["missing_required_sections"]:
                lines.append(f"- ✗ `Section {s['section_id']}`: {s['title']} [{s.get('priority_if_missing', '')}]")
        else:
            lines.append("✓ All required sections for this module are present in the dossier.")

        lines.append(f"\n⚠ {CTD_DISCLAIMER}")
        return BobChatResponse(
            response="\n".join(lines),
            tool_used="get_submission_module",
            intent="get_submission_module",
            data=ms,
            disclaimer=CTD_DISCLAIMER
        )

    # -------------------------------------------------------------
    # 7. FALLBACK / GENERAL QUERY
    # -------------------------------------------------------------
    return BobChatResponse(
        response=HELP_RESPONSE,
        tool_used=None,
        intent="general_help",
        data=None,
        disclaimer=MEDICAL_DISCLAIMER
    )
