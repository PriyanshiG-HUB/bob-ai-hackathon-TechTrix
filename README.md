# PHARMASENTINEL AI

> An AI-powered pharmaceutical safety signal detection and regulatory submission readiness platform for pharmacovigilance teams.

---

## Problem

Pharmacovigilance teams face two tightly linked challenges that are currently addressed through manual, time-intensive workflows:

1. **Safety Signal Detection** — Identifying drug–adverse event associations that warrant clinical review from millions of spontaneous FDA AEMS/FAERS reports requires statistical disproportionality analysis at scale. Manual triage of hundreds of thousands of candidate pairs is slow and error-prone.

2. **Regulatory Submission Readiness** — Preparing a pharmaceutical dossier that complies with the ICH M4 Common Technical Document (CTD) structure across Modules M1–M5 requires painstaking cross-checking against official guidance. Missing required sections are discovered late, causing costly submission delays.

---

## Key Features

### Safety Signal Detection

- **FDA AEMS/FAERS 2026 Q1 data** — ingested and normalized from the official quarterly ASCII release (Jan–Mar 2026).
- **Data normalization** — deduplication, active-ingredient standardization (`prod_ai`), and MedDRA Preferred Term alignment across DEMO, DRUG, REAC, and OUTC tables.
- **Active ingredient–based analysis** — universe restricted to suspect drug reports (`role_cod` in `PS`, `SS`) to eliminate concomitant drug noise.
- **Drug–event associations** — full contingency table (A/B/C/D) computed for every unique active-ingredient × reaction pair.
- **PRR (Proportional Reporting Ratio)** — deterministic disproportionality statistic: `PRR = (A/(A+B)) / (C/(C+D))`.
- **Pearson Chi-Square** — `χ² = N(AD−BC)² / [(A+B)(C+D)(A+C)(B+D)]` for statistical weight alongside PRR.
- **Signal confidence** — `HIGH` (A≥10, C≥5) / `MODERATE` (A≥5, C≥5) / `LOW` (A<5 or C<5).
- **Four-tier review priority**:
  - `PRIORITY_1` — PRR ≥ 4.0, A ≥ 10, C ≥ 5 — high-priority signal requiring pharmacovigilance review.
  - `PRIORITY_2` — PRR ≥ 2.0, A ≥ 5, C ≥ 5 — statistical signal suitable for further review.
  - `REVIEW` — PRR ≥ 2.0, A ≥ 5, C < 5 — potential signal; background is sparse.
  - `LOW` — does not meet configured prioritization criteria.
- **Full 2×2 A/B/C/D breakdown** returned per signal for transparent audit.
- **Pharmacovigilance disclaimer** embedded in every signal response (see Disclaimers section below).

### Regulatory Submission Readiness

- **ICH M4(R4)-based CTD structure** — requirements derived from the official ICH M4(R4) Common Technical Document guidance.
- **M1–M5 coverage** — all five CTD modules: Administrative (M1), Summaries (M2), Quality/CMC (M3), Nonclinical (M4), Clinical (M5).
- **Structural outline matching** — accepts raw text or table-of-contents outlines; extracts section IDs using deterministic regex matching; applies sub-section parent matching (e.g., `3.2.S.1` satisfies `3.2.S`).
- **Module completeness scores** — per-module `completeness_percentage` computed as `(required_present / total_required) × 100`.
- **Missing-section detection** — every unmatched required section is reported with title and importance note.
- **Prioritized gap report** — gaps classified as `CRITICAL` / `HIGH` / `MEDIUM` and sorted accordingly.
- **Readiness bands** (application prototype classifications — **NOT official FDA/ICH acceptance criteria**):
  - `READY` — ≥ 90% overall completeness
  - `MOSTLY_READY` — 75–89%
  - `NEEDS_ATTENTION` — 50–74%
  - `NOT_READY` — < 50%

> ⚠️ These readiness bands are application-level prototype classifications used to guide dossier assembly. They are **NOT** official FDA, EMA, PMDA, or ICH acceptance criteria and **do NOT** constitute or guarantee regulatory approval of any kind.

---

## Architecture

### Safety Signal Pipeline

```
FDA AEMS/FAERS 2026 Q1 (raw ASCII files)
              ↓
       FAERS Processor
  (normalization, deduplication,
   suspect filtering, join)
              ↓
  Normalized CSV Dataset (~1.1 GB)
              ↓
   PRR / Signal Detection Engine
  (contingency table, PRR, χ², priority)
              ↓
   Compact PRR Index (~8.8 MB .pkl)
              ↓
       FastAPI Backend
       ↙             ↘
React Bob AI UI    IBM Bob MCP Server (6 Tools)
```

### CTD Readiness Pipeline

```
CTD Dossier Outline (text / TOC)
              ↓
        CTD Checker Service
  (regex parse → section extraction
   → ICH M4 requirement matching)
              ↓
  ICH M4(R4) Requirements JSON
    (M1–M5, required/optional flags)
              ↓
   M1–M5 Completeness Scores
              ↓
   Prioritized Gap Report
              ↓
       FastAPI Backend
       ↙             ↘
React Frontend     Bob AI Chat Bridge / MCP
```

---

## Backend API & Bob AI Bridge

Base URL (local): `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs`

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Returns service operational status and whether the PRR data index is loaded. |
| `GET` | `/stats` | Returns FAERS dataset universe statistics: unique suspect reports, active ingredients, reactions, candidate pairs, total associations. |

### Safety Signal Detection

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/signals` | Query ranked safety signals with optional filters: `drug_name`, `min_prr` (default 2.0), `min_reports` (default 3), `priority` tier, `limit`. Returns PRR, chi-square, confidence, and priority tier per signal. |
| `GET` | `/signals/{drug}/{event}` | Full 2×2 contingency table detail (A, B, C, D counts), PRR, chi-square, signal level, confidence, and contextual interpretation for a specific active ingredient × adverse event pair. |
| `GET` | `/compare` | Side-by-side independent PRR comparison of two active ingredients (`drug_a`, `drug_b`) against the same adverse `event`. |

### Regulatory Submission Readiness

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/submission/check` | Submit a dossier outline text for ICH M4 structural evaluation. Returns per-module completeness scores (M1–M5), missing required sections, gap report, and overall readiness band. |
| `GET` | `/submission/{submission_id}` | Retrieve a previously evaluated submission result by ID. |
| `GET` | `/submission/{submission_id}/gaps` | Retrieve the gap report for a submission; optionally filter by priority (`CRITICAL`, `HIGH`, `MEDIUM`). |
| `GET` | `/submission/{submission_id}/modules/{module}` | Retrieve detailed completeness data for a single CTD module (`M1`–`M5`). |

### Bob AI Conversational Chat Bridge

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/bob/chat` | Deterministic local tool-orchestration bridge answering conversational queries on dataset stats, safety signals, 2×2 contingency tables, PRR/χ² statistics, CTD readiness, and gap remediation without hallucinations. |

---

## Model Context Protocol (MCP) Server

PHARMASENTINEL AI provides a standards-compliant MCP Server (`src/mcp_server/server.py`) exposing 6 validated tools for integration with AI assistants (e.g. IBM Bob):

1. `get_system_stats` — Retrieve FAERS 2026 Q1 dataset universe metrics ($N=397,209$).
2. `get_signals` — Retrieve ranked statistical safety signals filtered by active ingredient or priority.
3. `get_signal_detail` — Retrieve exact 2×2 contingency metrics, PRR, χ², and confidence for a drug–event pair.
4. `check_submission` — Evaluate a raw text or TOC outline against ICH M4(R4) CTD requirements.
5. `get_gap_report` — Query missing required CTD sections categorized by priority (`CRITICAL`, `HIGH`, `MEDIUM`).
6. `get_submission_module` — Retrieve granular completeness scores and section status for Modules M1–M5.

Configuration template is available at [`.bob/mcp.json`](.bob/mcp.json) and [`src/mcp_server/mcp_config_template.json`](src/mcp_server/mcp_config_template.json).


---

## Dataset

| Metric | Value |
|--------|-------|
| Reporting period | 2026 Q1 (January – March 2026) |
| Unique suspect reports | 397,209 |
| Unique active ingredients | 4,841 |
| Unique adverse reaction terms | 12,389 |
| Candidate drug–event pairs | 633,557 |
| Total normalized associations | 10,085,069 |
| Suspect-only associations | 5,785,411 |
| Compact PRR index size | ~8.8 MB (`.pkl`) |

Raw FAERS/AEMS quarterly ASCII files (`data/raw/faers/`) and large generated processed artifacts (`data/processed/faers_2026Q1_normalized.csv`, `data/processed/prr_index_2026Q1.pkl`) are **intentionally excluded from version control** via `.gitignore`. They are local-only artifacts produced by running the FAERS processor pipeline.

---

## Performance

- **Index build**: compact PRR index pre-built from normalized CSV; once built, loaded from `.pkl` cache.
- **Cold-start load time**: ~0.43 seconds reported during local prototype validation (index already built).
- **Typical query latency**: ~5–15 ms per signal query under local prototype conditions.

> These figures reflect local prototype measurements. No production performance guarantees are made or implied.

---

## Testing

All backend and MCP tests are validated with `pytest`, and the frontend is validated with TypeScript & Vite build checks.

| Suite | File / Command | Result |
|-------|----------------|--------|
| PRR Signal Detection | `src/backend/app/services/test_prr.py` | **8 / 8 passed** ✅ |
| CTD Checker | `src/backend/app/services/test_ctd_checker.py` | **14 / 14 passed** ✅ |
| FastAPI Endpoints | `src/backend/app/test_api.py` | **12 / 12 passed** ✅ |
| Bob AI Chat Bridge | `src/backend/app/test_bob_chat.py` | **9 / 9 passed** ✅ |
| MCP Server (6 Tools) | `src/mcp_server/test_mcp_server.py` | **32 / 32 passed** ✅ |
| Frontend Build & Types | `cd src/frontend && npm run build` | **0 errors / built** ✅ |
| **Total Automated Tests** | | **75 / 75 passed** ✅ |

---

## Safety / Regulatory Disclaimers

### Pharmacovigilance Disclaimer

> "This is a statistical disproportionality signal from spontaneous reports. It does not establish causality, incidence, prevalence, or clinical risk."

PRR priority levels (`PRIORITY_1`, `PRIORITY_2`, `REVIEW`, `LOW`) are **application prioritization labels only** and do **NOT** represent FDA regulatory classifications.

### CTD Submission Disclaimer

> "This completeness check evaluates structural adherence to the ICH M4 Common Technical Document (CTD) format outline only. It does not evaluate scientific content, data integrity, or regulatory adequacy, and does NOT constitute or guarantee regulatory approval or acceptance by the FDA, EMA, PMDA, or any other health authority."

---

## Project Structure

```
bob-ai-hackathon-TechTrix/
├── .bob/
│   └── mcp.json                     # IBM Bob MCP server integration configuration
├── data/
│   ├── ich_m4_requirements.json     # ICH M4(R4) CTD requirements definition (M1–M5)
│   ├── processed/                   # Generated artifacts — NOT committed (see .gitignore)
│   │   ├── .gitkeep
│   │   ├── faers_2026Q1_normalized.csv   # ~1.1 GB — local only
│   │   └── prr_index_2026Q1.pkl          # ~8.8 MB compact PRR index — local only
│   └── raw/
│       └── faers/
│           └── 2026Q1/              # Raw FAERS ASCII files — NOT committed
│               ├── .gitkeep
│               ├── DEMO26Q1.txt
│               ├── DRUG26Q1.txt
│               ├── OUTC26Q1.txt
│               └── REAC26Q1.txt
├── src/
│   ├── backend/
│   │   ├── regression_test.py       # Old vs new CTD scoring regression script
│   │   └── app/
│   │       ├── config.py            # FastAPI settings (paths, CORS, metadata)
│   │       ├── ctd_schemas.py       # Pydantic response models for CTD endpoints
│   │       ├── main.py              # FastAPI application and route definitions
│   │       ├── schemas.py           # Pydantic response models for signal endpoints
│   │       ├── test_api.py          # FastAPI endpoint integration tests (12 tests)
│   │       ├── test_bob_chat.py     # Bob AI chat bridge integration tests (9 tests)
│   │       └── services/
│   │           ├── bob_chat.py      # Deterministic local chat orchestration bridge
│   │           ├── ctd_checker.py   # ICH M4 CTD structural checker service
│   │           ├── faers_processor.py  # FAERS raw data ingestion and normalization
│   │           ├── prr.py           # PRR/chi-square signal detection engine
│   │           ├── test_ctd_checker.py  # CTD checker unit tests (14 tests)
│   │           └── test_prr.py      # PRR engine unit tests (8 tests)
│   ├── frontend/                    # React 19 + TypeScript + Vite web application
│   │   ├── package.json
│   │   ├── src/
│   │   │   ├── App.tsx              # Router & layout entry point
│   │   │   ├── components/          # TopBar, Sidebar, ContingencyTable, etc.
│   │   │   ├── pages/               # Dashboard, Signals, SignalDetail, Submission, GapReport, BobAI
│   │   │   ├── services/api.ts      # Typed Axios API client (including bobChat)
│   │   │   └── types/api.ts         # TypeScript data contracts matching FastAPI schemas
│   │   └── vite.config.ts
│   └── mcp_server/
│       ├── server.py                # Standalone FastMCP server (6 tools)
│       ├── test_mcp_server.py       # MCP test suite (32 tests)
│       └── mcp_config_template.json # Configuration template
├── docs/
│   ├── architecture.md
│   ├── problem-statement.md
│   ├── setup-guide.md
│   ├── solution-overview.md
│   └── template-guide.md
├── demo/
│   ├── demo-video-link.txt
│   ├── live-demo-url.txt
│   └── screenshots/
├── presentation/
│   └── README.md
├── .gitignore
├── CONTRIBUTING.md
├── README.md                        # This file
└── submission.yaml                  # Hackathon submission metadata
```

---

## Setup & Running

### Prerequisites

- Python 3.11 or later
- Node.js 18+ and npm (for frontend)

### 1. Clone the repository

```bash
git clone https://github.com/PriyanshiG-HUB/bob-ai-hackathon-TechTrix.git
cd bob-ai-hackathon-TechTrix
```

### 2. Backend Setup

```bash
# Create and activate virtual environment
python -m venv .venv
# Linux / macOS: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1

# Install backend & MCP dependencies
pip install fastapi==0.116.2 uvicorn==0.35.0 pandas==2.2.3 numpy==2.1.2 \
            pydantic==2.10.3 pydantic-settings==2.6.1 mcp==1.26.0 \
            pytest==9.1.1 httpx==0.28.1
```

### 3. Start Backend Server

```bash
cd src/backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API docs: `http://127.0.0.1:8000/docs`

### 4. Frontend Setup & Run

```bash
cd src/frontend
npm install
npm run dev
```

- Web UI: `http://localhost:5173`

### 5. Running All Tests

```bash
# Backend unit & integration tests (43 tests)
cd src/backend
python -m pytest app/services/test_prr.py app/services/test_ctd_checker.py app/test_api.py app/test_bob_chat.py -v

# MCP server tests (32 tests)
cd ../mcp_server
python -m pytest test_mcp_server.py -v

# Frontend build check
cd ../frontend
npm run build
```

---

## Current Status

### ✅ Completed

- **FAERS 2026 Q1 Data Pipeline**: Ingestion, suspect drug filtering (`PS`/`SS`), normalization, and compact binary caching (~8.8 MB).
- **Deterministic PRR Engine**: Proportional Reporting Ratio, Pearson Chi-Square ($\chi^2$), $2\times 2$ contingency table generation, and 4-tier review priority (`PRIORITY_1`, `PRIORITY_2`, `REVIEW`, `LOW`).
- **ICH M4(R4) CTD Checker**: Full M1–M5 structural parsing, required section matching, module completeness scoring, and prioritized gap classification (`CRITICAL`, `HIGH`, `MEDIUM`).
- **FastAPI REST API**: 10 endpoints serving statistical signals, comparison, submission assessment, module drilldown, and Bob chat.
- **Model Context Protocol (MCP) Server**: 6 standardized MCP tools (`get_system_stats`, `get_signals`, `get_signal_detail`, `check_submission`, `get_gap_report`, `get_submission_module`) with `.bob/mcp.json` integration.
- **React 19 Frontend**: Full UI dashboard for interactive signal triage, contingency table breakdown, dossier readiness evaluation, and live Bob AI conversational chat.
- **75 Automated Tests**: 100% passing across PRR, CTD, FastAPI, Bob Chat, and MCP suites.

---

## Team

| Field | Value |
|-------|-------|
| **Project** | PHARMASENTINEL AI |
| **Repository** | [PriyanshiG-HUB/bob-ai-hackathon-TechTrix](https://github.com/PriyanshiG-HUB/bob-ai-hackathon-TechTrix) |

