# AetherGuard AI

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
              ↓
    React Frontend  ←→  Bob AI / MCP [PLANNED]
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
              ↓
  React Frontend / Bob AI [PLANNED]
```

> **IBM Bob / MCP integration** is **PLANNED** and not yet implemented in this release.

---

## Backend API

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

All tests are located in [`src/backend/`](src/backend/) and run with `pytest`.

| Suite | File | Result |
|-------|------|--------|
| PRR Signal Detection | `app/services/test_prr.py` | **8 / 8 passed** ✅ |
| CTD Checker | `app/services/test_ctd_checker.py` | **14 / 14 passed** ✅ |
| FastAPI Endpoints | `app/test_api.py` | **12 / 12 passed** ✅ |
| **Total** | | **34 / 34 passed** ✅ |

> **Note**: A pre-existing Pydantic v2 deprecation warning (`Support for class-based config is deprecated, use ConfigDict instead`) appears in test output. This originates in a third-party library dependency and does not affect functionality.

### Running Tests

```bash
cd src/backend
python -m pytest app/services/test_prr.py app/services/test_ctd_checker.py app/test_api.py -v
```

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
│   │   ├── __init__.py
│   │   ├── regression_test.py       # Old vs new CTD scoring regression script
│   │   └── app/
│   │       ├── __init__.py
│   │       ├── config.py            # FastAPI settings (paths, CORS, metadata)
│   │       ├── ctd_schemas.py       # Pydantic response models for CTD endpoints
│   │       ├── main.py              # FastAPI application and all route definitions
│   │       ├── schemas.py           # Pydantic response models for signal endpoints
│   │       ├── test_api.py          # FastAPI endpoint integration tests (12 tests)
│   │       └── services/
│   │           ├── __init__.py
│   │           ├── ctd_checker.py   # ICH M4 CTD structural checker service
│   │           ├── faers_processor.py  # FAERS raw data ingestion and normalization
│   │           ├── prr.py           # PRR/chi-square signal detection engine
│   │           ├── test_ctd_checker.py  # CTD checker unit tests (14 tests)
│   │           └── test_prr.py      # PRR engine unit tests (8 tests)
│   └── .env.example                 # Environment variable template (copy to .env)
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
├── .env.example                     # Root environment template
├── .gitignore
├── CONTRIBUTING.md
├── README.md                        # This file
└── submission.yaml                  # Hackathon submission metadata
```

---

## Setup

### Prerequisites

- Python 3.11 or later
- No Node.js required for the current backend-only implementation (React frontend is planned)

### 1. Clone the repository

```bash
git clone https://github.com/PriyanshiG-HUB/bob-ai-hackathon-TechTrix.git
cd bob-ai-hackathon-TechTrix
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

### 3. Install backend dependencies

```bash
pip install fastapi==0.116.2 uvicorn==0.35.0 pandas==2.2.3 numpy==2.1.2 \
            pydantic==2.10.3 pydantic-settings==2.6.1 \
            pytest==9.1.1 httpx==0.28.1
```

### 4. Prepare FAERS data (one-time)

Place the raw FAERS 2026 Q1 ASCII files into `data/raw/faers/2026Q1/`:

```
DEMO26Q1.txt  DRUG26Q1.txt  OUTC26Q1.txt  REAC26Q1.txt
```

Then run the FAERS processor to build the normalized CSV and PRR index:

```bash
cd src/backend
python -c "from app.services.faers_processor import process_faers; process_faers()"
```

> If the processed artifacts are already present at `data/processed/`, this step can be skipped.

### 5. Start the FastAPI backend

```bash
cd src/backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API root: `http://localhost:8000`
- Interactive Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 6. Run tests

```bash
cd src/backend
python -m pytest app/services/test_prr.py app/services/test_ctd_checker.py app/test_api.py -v
```

---

## Current Status

### ✅ Completed

- FDA AEMS/FAERS 2026 Q1 data ingestion and normalization
- Suspect drug filtering and active-ingredient universe construction
- PRR signal detection engine (PRR, chi-square, confidence, priority)
- Compact PRR index (~8.8 MB, ~0.43 s cold-start load)
- FastAPI REST API with 9 endpoints (signal detection + CTD readiness)
- ICH M4(R4) CTD requirements definition (M1–M5, corrected 5.3.x numbering)
- CTD structural checker (section parsing, matching, module scoring, gap reports)
- 34 automated tests (8 PRR + 14 CTD + 12 API), all passing

### 🔲 Planned

- **React frontend** — dashboard for signal exploration and CTD readiness visualization
- **IBM Bob / MCP integration** — conversational pharmacovigilance assistant via Bob AI
- **Final demo and presentation assets** — recorded walkthrough, screenshots, slide deck

---

## Team

| Field | Value |
|-------|-------|
| **Project** | AetherGuard AI |
| **Repository** | [PriyanshiG-HUB/bob-ai-hackathon-TechTrix](https://github.com/PriyanshiG-HUB/bob-ai-hackathon-TechTrix) |
