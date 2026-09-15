# Setup & Deployment Guide: AetherGuard AI

> **Audience**: Technical evaluators, judges, and developers setting up AetherGuard AI on a clean machine.

---

## 1. Prerequisites

Ensure your system meets the following software requirements:

* **Operating System**: Windows 10/11, macOS (Intel or Apple Silicon), or Linux (Ubuntu 20.04+).
* **Python**: `3.11` or higher (verified on Python 3.11.9).
* **Node.js**: `18.x` or higher (recommended Node.js 20+).
* **npm**: `9.x` or `10.x`.
* **Git**: `2.x` or higher.
* **IBM Bob IDE** *(Optional)*: If interacting with the Model Context Protocol (MCP) server inside IBM Bob.

---

## 2. Required Accounts & External Services

* **Core Local System**: **Zero cloud accounts or API keys required**. The platform runs entirely locally using Python analytical engines, pre-indexed binary cache files, and the React single-page application.
* **Optional Cloud Integrations (Defaults in `.env.example`)**:
  * IBM watsonx.ai (`WATSONX_API_KEY`, `WATSONX_PROJECT_ID`) — *Optional*.
  * PostgreSQL (`DATABASE_URL`) — *Optional*.
  * Slack Webhooks (`SLACK_WEBHOOK_URL`) — *Optional*.

---

## 3. Repository Setup

Clone the repository and enter the project directory:

```bash
git clone https://github.com/PriyanshiG-HUB/bob-ai-hackathon-TechTrix.git
cd bob-ai-hackathon-TechTrix
```

---

## 4. Environment Configuration

### Available Environment Variables

| Variable | Required? | Default / Example | Purpose |
| :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | Optional (Frontend) | `http://127.0.0.1:8000` | Base URL used by the React frontend to communicate with FastAPI. |
| `PROJECT_NAME` | Optional (Backend) | `AetherGuard AI - FDA FAERS Safety Signal Detection` | API title displayed in OpenAPI documentation. |
| `VERSION` | Optional (Backend) | `1.0.0` | Application API version. |
| `REPORTING_PERIOD` | Optional (Backend) | `2026 Q1 (Jan - Mar 2026)` | Dataset metadata string. |
| `NORMALIZED_DATA_PATH` | Optional (Backend) | `data/processed/faers_2026Q1_normalized.csv` | Relative path to processed FAERS CSV dataset. |
| `INDEX_CACHE_PATH` | Optional (Backend) | `data/processed/prr_index_2026Q1.pkl` | Relative path to compact pre-indexed binary cache. |

### Configuration Steps
The backend and frontend contain safe built-in defaults that work out-of-the-box. If custom configuration is needed:

```bash
# Optional: Create root environment file
cp src/.env.example src/.env

# Optional: Configure frontend API target
cp src/frontend/.env.example src/frontend/.env
```

---

## 5. Dependency Installation

### Step A: Backend & MCP Dependencies

Create and activate a Python virtual environment, then install the required packages:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Windows (Command Prompt):
.\.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# Install backend, analytical, MCP, and test dependencies
pip install fastapi==0.116.2 uvicorn==0.35.0 pandas==2.2.3 numpy==2.1.2 \
            pydantic==2.10.3 pydantic-settings==2.6.1 mcp==1.26.0 \
            pytest==9.1.1 httpx==0.28.1
```

### Step B: Frontend Dependencies

```bash
cd src/frontend
npm install
cd ../..
```

---

## 6. Dataset Preparation (FAERS & In-Memory Index)

The repository includes a compact precomputed index and automated fallback logic:

* **Precomputed Index**: If `data/processed/prr_index_2026Q1.pkl` (~8.8 MB) is present, the engine loads all 397,209 reports into memory in **~0.43s**.
* **Synthetic Fallback**: If no raw or processed FAERS files are present, the backend automatically initializes an in-memory test dataset (100,000 reports with known signals like Aspirin, Ibuprofen, and Vioxx) to guarantee continuous test and evaluation execution without requiring a multi-gigabyte data download.
* **Full Ingestion (One-Time Developer Pipeline)**: If raw FDA ASCII files are placed in `data/raw/faers/2026Q1/`, the ETL pipeline can be executed via:
  ```bash
  cd src/backend
  python -c "from app.services.faers_processor import process_faers_data; process_faers_data('data/raw/faers/2026Q1/DEMO26Q1.txt', 'data/raw/faers/2026Q1/DRUG26Q1.txt', 'data/raw/faers/2026Q1/REAC26Q1.txt', 'data/raw/faers/2026Q1/OUTC26Q1.txt', 'data/processed/faers_2026Q1_normalized.csv')"
  cd ../..
  ```

---

## 7. Running the Application

### Terminal 1 — Backend API Server
```bash
# Ensure virtual environment is active
cd src/backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
* **API Root**: `http://127.0.0.1:8000`
* **Interactive Swagger UI**: `http://127.0.0.1:8000/docs`
* **ReDoc**: `http://127.0.0.1:8000/redoc`

### Terminal 2 — Frontend Web Application
```bash
cd src/frontend
npm run dev
```
* **Frontend Web Dashboard**: `http://localhost:5173`

### Terminal 3 — Standalone MCP Server *(Optional)*
```bash
cd src/mcp_server
python server.py
```
* **IBM Bob IDE Registration**: Configuration is pre-registered in `.bob/mcp.json`. Ensure the path in `.bob/mcp.json` points to your absolute repository directory.

---

## 8. Verification & Smoke Test Checklist

A judge can verify the entire platform in under 2 minutes:

### Check 1 — Health Endpoint
```bash
curl http://127.0.0.1:8000/health
```
* **Expected Output**:
  ```json
  {"status":"healthy","service":"AetherGuard AI - FDA FAERS Safety Signal Detection","version":"1.0.0","data_loaded":true}
  ```

### Check 2 — Statistical Signal Detection
```bash
curl "http://127.0.0.1:8000/signals?limit=1&priority=PRIORITY_1"
```
* **Expected Output**: Returns HTTP 200 with `total_returned: 1`, a signal item containing $A, B, C, D$ cell counts, PRR $\ge 4.0$, Chi-Square, and mandatory pharmacovigilance disclaimer.

### Check 3 — CTD Dossier Submission Checker
```bash
curl -X POST "http://127.0.0.1:8000/submission/check" \
     -H "Content-Type: application/json" \
     -d "{\"dossier_text\": \"1.1 TOC\n1.2 Form\n1.3 Prescribing Info\n2.1 TOC\n2.2 Intro\n2.3 QOS\n2.4 Nonclin Overview\n2.5 Clin Overview\n2.6 Nonclin Summary\n2.7 Clin Summary\n3.1 TOC\n3.2.S Substance\n3.2.P Product\n4.1 TOC\n4.2.1 Pharm\n4.2.2 PK\n4.2.3 Tox\n5.1 TOC\n5.2 Tabular Listing\n5.3.3 Human PK\n5.3.6 Efficacy and Safety\"}"
```
* **Expected Output**: Returns HTTP 200 with `overall_completeness: 100.0`, `readiness_status: "READY"`, and `missing_required_sections_count: 0`.

### Check 4 — Web UI Walkthrough
1. Open `http://localhost:5173` in a browser.
2. Confirm the 4 dataset statistics cards render ($N=397,209$).
3. Navigate to **Signals** (`/signals`) and verify the filterable grid.
4. Navigate to **Submission Readiness** (`/submission`), click **"Load Sample Outline"**, then click **"Check Completeness"**. Confirm the 100% READY scorecard appears.
5. Navigate to **Bob AI** (`/bob`), click the suggested prompt *"Show me the highest priority safety signals"*, and verify the tool-backed response.

---

## 9. Troubleshooting Guide

| Error / Symptom | Likely Cause | Diagnostic Step | Exact Solution |
| :--- | :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'app'` when running pytest | Running pytest from root without `PYTHONPATH` set to `src/backend`. | Check current terminal directory. | Run pytest from `src/backend`: `cd src/backend && python -m pytest app/services/test_prr.py ...` or set `$env:PYTHONPATH="src/backend"`. |
| `ModuleNotFoundError: No module named 'pandas'` | Virtual environment not activated. | Run `python -c "import pandas"`. | Activate `.venv` (`.\.venv\Scripts\Activate.ps1` or `source .venv/bin/activate`). |
| Port 8000 already in use | Another background process occupies port 8000. | Run `netstat -ano \| findstr 8000`. | Terminate the process or launch uvicorn on port 8001: `uvicorn app.main:app --port 8001` (and set `VITE_API_BASE_URL=http://127.0.0.1:8001` in `src/frontend/.env`). |
| Frontend displays `Network Error` / `Connection Refused` | Backend server is not running. | Verify `http://127.0.0.1:8000/health` responds in browser. | Start backend server using `uvicorn app.main:app --reload` from `src/backend`. |
| MCP tool fails in IBM Bob | Incorrect absolute path in `.bob/mcp.json`. | Check paths in `.bob/mcp.json`. | Replace placeholder paths in `.bob/mcp.json` with the current machine's absolute path to `src/mcp_server/server.py` and `src/backend`. |
| Deprecation warning on Pydantic v2 Config | Deprecation notice from third-party Starlette/Pydantic package. | Inspect test stdout. | Informational only. Does not affect test pass status or application stability. |

---

## 10. Running the Automated Test Suite

The project includes **75 automated tests** across 5 test suites.

```bash
# 1. Run Backend Unit & Integration Tests (43 tests)
cd src/backend
python -m pytest app/services/test_prr.py app/services/test_ctd_checker.py app/test_api.py app/test_bob_chat.py -v

# 2. Run MCP Server Tests (32 tests)
cd ../mcp_server
python -m pytest test_mcp_server.py -v

# 3. Run Frontend Typecheck and Production Build Check
cd ../frontend
npm run build
```

* **Expected Result**: **75 passed tests**, 0 build errors.

---

## 11. Common Mistakes to Avoid

1. **Running Backend Tests from the Project Root**: The Python modules use package-relative imports (`from app.services...`). Always `cd src/backend` before running backend tests or starting uvicorn.
2. **Forgetting to Install Frontend Dependencies**: If Vite fails to start, ensure you ran `npm install` inside `src/frontend`.
3. **Overlooking Disclaimers in Test Assertions**: All tests verify that pharmacovigilance and CTD regulatory disclaimers are preserved in output schemas.

---

## 12. Quick Start (Minimum Commands)

```bash
# Clone
git clone https://github.com/PriyanshiG-HUB/bob-ai-hackathon-TechTrix.git
cd bob-ai-hackathon-TechTrix

# Backend Setup & Run (Terminal 1)
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # or: source .venv/bin/activate
pip install fastapi==0.116.2 uvicorn==0.35.0 pandas==2.2.3 numpy==2.1.2 pydantic==2.10.3 pydantic-settings==2.6.1 mcp==1.26.0 pytest==9.1.1 httpx==0.28.1
cd src/backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend Setup & Run (Terminal 2)
cd src/frontend
npm install
npm run dev

# Open Browser
# Web UI: http://localhost:5173
# API Docs: http://127.0.0.1:8000/docs
```
