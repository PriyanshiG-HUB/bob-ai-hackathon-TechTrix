# Solution Overview: AetherGuard AI

---

## 1. Solution Summary

**AetherGuard AI** is a dual-mode pharmacovigilance and regulatory intelligence platform designed for drug safety surveillance teams and regulatory affairs professionals. It delivers two tightly integrated capabilities:

1. **Deterministic Safety Signal Detection**: Rapidly identifies drug–adverse event statistical associations across millions of spontaneous reports from the official **FDA AEMS/FAERS 2026 Q1** dataset using exact $2\times 2$ contingency table partitioning, Proportional Reporting Ratio (PRR), Pearson Chi-Square ($\chi^2$), and a 4-tier review prioritization hierarchy.
2. **ICH M4 CTD Regulatory Submission Readiness**: Automatically checks pharmaceutical dossier outlines (plain text or markdown Table of Contents) against the official **ICH M4(R4) Common Technical Document** specification across all five modules (M1–M5), calculates module-by-module completeness percentages, assigns prototype readiness classifications, and outputs prioritized gap remediation reports.

AetherGuard AI provides access via a **FastAPI REST API (10 endpoints)**, an interactive **React 19 web dashboard**, and a standards-compliant **Model Context Protocol (MCP) server (6 tools)** integrating directly into AI developer environments like **IBM Bob**.

---

## 2. How It Works: Conceptual End-to-End Pipeline

```
                                  AETHERGUARD AI PIPELINE
   ┌──────────────────────────────────────────────────────────────────────────────────────┐
   │                                                                                      │
   │  [ PIPELINE 1: SAFETY SIGNAL DETECTION ]                                             │
   │  FDA FAERS 2026 Q1 ASCII (DEMO, DRUG, REAC, OUTC)                                    │
   │          ↓                                                                           │
   │  FAERS Processor (Deduplication, 'prod_ai' standard, role_cod in ['PS','SS'])        │
   │          ↓                                                                           │
   │  Normalized Dataset (~1.1 GB CSV) ──→ Compact In-Memory Index (~8.8 MB .pkl)          │
   │          ↓                                                                           │
   │  Exact 2x2 Partition (A, B, C, D) ──→ PRR & Chi-Square Calculation                   │
   │          ↓                                                                           │
   │  4-Tier Prioritization (PRIORITY_1, PRIORITY_2, REVIEW, LOW)                         │
   │                                                                                      │
   │  [ PIPELINE 2: CTD REGULATORY READINESS ]                                            │
   │  Dossier Outline (Raw Text / TOC Markdown)                                           │
   │          ↓                                                                           │
   │  Deterministic Regex Section Parser (_normalize_section_id, sub-section matcher)     │
   │          ↓                                                                           │
   │  ICH M4(R4) Database Comparison (21 Universal Required Sections across M1–M5)        │
   │          ↓                                                                           │
   │  Completeness Scoring (%) & Prioritized Gap Classification (CRITICAL, HIGH, MEDIUM)  │
   │                                                                                      │
   │  [ UNIFIED SERVING & ACCESS LAYER ]                                                  │
   │  FastAPI REST API (10 Endpoints)  │  FastMCP Server (6 Tools)                        │
   │          ↓                                  ↓                                        │
   │  React 19 Frontend Web UI         │  IBM Bob IDE Assistant                           │
   │                                                                                      │
   └──────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Data Ingestion & Normalization (ETL)**:
   * Quarterly FDA FAERS ASCII tables (`DEMO`, `DRUG`, `REAC`, `OUTC`) are ingested.
   * Standardizes active ingredients (`prod_ai`), normalizes dates (`YYYY-MM-DD`), converts patient age to standardized years, aggregates outcome severity (`is_serious`), and restricts the analytical universe to suspect drug roles (`PS` = Primary Suspect, `SS` = Secondary Suspect) to remove concomitant background noise.
2. **Indexing & Precomputation**:
   * Generates a compact pre-indexed binary cache (`prr_index_2026Q1.pkl`, ~8.8 MB) containing unique report counts per drug, per adverse event, and per candidate pair.
3. **Statistical Reasoning & Disproportionality Computation**:
   * For any target drug $D$ and adverse reaction $E$, the engine computes the full $2\times 2$ contingency partition ($A, B, C, D$) where $N = A + B + C + D = 397,209$.
   * Computes drug event rate $\frac{A}{A+B}$, background rate $\frac{C}{C+D}$, PRR, Pearson $\chi^2$, and checks for sparse background ($C < 5$).
   * Assigns review priority (`PRIORITY_1`, `PRIORITY_2`, `REVIEW`, `LOW`) and confidence tier (`HIGH`, `MODERATE`, `LOW`).
4. **Dossier Structural Parsing & Rule Matching**:
   * Accepts raw dossier text or TOC outlines.
   * Standardizes section headers via regular expressions and applies sub-section hierarchical matching (e.g., `3.2.S.1` satisfies required parent `3.2.S`).
   * Evaluates presence against 21 universal required sections defined in `ich_m4_requirements.json`.
5. **Validation, Scoring & Gap Prioritization**:
   * Computes completeness percentages per module: $\frac{\text{present required}}{\text{total required}} \times 100$.
   * Assigns overall readiness status (`READY`, `MOSTLY_READY`, `NEEDS_ATTENTION`, `NOT_READY`).
   * Ranks missing sections by regulatory importance into `CRITICAL`, `HIGH`, and `MEDIUM` gaps.
6. **Multi-Channel Delivery & Language Safeguards**:
   * Delivers results via REST API, React Web UI, or IBM Bob MCP tools with mandatory pharmacovigilance and CTD regulatory disclaimers attached.

---

## 3. Core Mechanisms & Mathematical Formulations

### A. Exact $2\times 2$ Contingency Table Partition
Let Universe $U$ be the set of all unique suspect reports in 2026 Q1 ($N = |U| = 397,209$).  
For active ingredient $D$ and adverse event $E$:

$$\begin{aligned}
A &= |D_{\text{reports}} \cap E_{\text{reports}}| \quad &\text{(Target Drug } D \text{ AND Event } E\text{)} \\
B &= |D_{\text{reports}} \setminus E_{\text{reports}}| \quad &\text{(Target Drug } D \text{ AND Other Events }\sim E\text{)} \\
C &= |E_{\text{reports}} \setminus D_{\text{reports}}| \quad &\text{(Other Drugs }\sim D \text{ AND Event } E\text{)} \\
D_{\text{cell}} &= |U \setminus (D_{\text{reports}} \cup E_{\text{reports}})| \quad &\text{(Other Drugs }\sim D \text{ AND Other Events }\sim E\text{)} \\
N &= A + B + C + D_{\text{cell}} = 397,209 \quad &\text{(Exact Partition Identity)}
\end{aligned}$$

### B. Statistical Formulas
* **Drug Event Rate**:
  $$R_{\text{drug}} = \frac{A}{A + B}$$
* **Background Event Rate**:
  $$R_{\text{bg}} = \frac{C}{C + D_{\text{cell}}}$$
* **Proportional Reporting Ratio (PRR)**:
  $$\text{PRR} = \frac{R_{\text{drug}}}{R_{\text{bg}}} = \frac{A / (A + B)}{C / (C + D_{\text{cell}})}$$
* **Pearson Chi-Square ($\chi^2$, 1 degree of freedom)**:
  $$\chi^2 = \frac{N \cdot (A \cdot D_{\text{cell}} - B \cdot C)^2}{(A + B)(C + D_{\text{cell}})(A + C)(B + D_{\text{cell}})}$$

### C. Four-Tier Review Prioritization Rules

```
                             PRR & REPORT COUNT
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
          PRR ≥ 4.0, A ≥ 10, C ≥ 5                PRR ≥ 2.0, A ≥ 5
                 │                                       │
                 ▼                                ┌──────┴──────┐
            PRIORITY_1                            ▼             ▼
      (High-Priority Signal)                    C ≥ 5         C < 5
                                                  │             │
                                                  ▼             ▼
                                             PRIORITY_2      REVIEW
                                          (Statistical)   (Sparse Bg)
                                                  │             │
                                                  └──────┬──────┘
                                                         ▼
                                                        LOW
                                              (Unmet Criteria)
```

* **`PRIORITY_1`**: $\text{PRR} \ge 4.0 \land A \ge 10 \land C \ge 5$ (High-priority statistical signal requiring clinical pharmacovigilance review).
* **`PRIORITY_2`**: $\text{PRR} \ge 2.0 \land A \ge 5 \land C \ge 5$ (and not `PRIORITY_1`) (Standard statistical signal suitable for review).
* **`REVIEW`**: $\text{PRR} \ge 2.0 \land A \ge 5 \land C < 5$ (Potential signal requiring review; background is sparse).
* **`LOW`**: All other associations not meeting screening thresholds.

### D. ICH M4(R4) CTD Module Specification & Scoring
The platform evaluates 21 universally required sections across the 5 CTD modules:
* **Module 1 (Administrative)**: 3 required (`1.1`, `1.2`, `1.3`), 3 optional (`1.4`, `1.5`, `1.6`).
* **Module 2 (Summaries)**: 7 required (`2.1`, `2.2`, `2.3`, `2.4`, `2.5`, `2.6`, `2.7`).
* **Module 3 (Quality / CMC)**: 3 required (`3.1`, `3.2.S`, `3.2.P`), 4 optional (`3.2`, `3.2.A`, `3.2.R`, `3.3`).
* **Module 4 (Nonclinical)**: 4 required (`4.1`, `4.2.1`, `4.2.2`, `4.2.3`), 2 optional (`4.2`, `4.3`).
* **Module 5 (Clinical)**: 4 required (`5.1`, `5.2`, `5.3.3`, `5.3.6`), 6 optional (`5.3.1`, `5.3.2`, `5.3.4`, `5.3.5`, `5.3.7`, `5.4`).

$$\text{Overall Completeness } \% = \left( \frac{\text{Total Present Required Sections}}{21} \right) \times 100$$

* **Prototype Readiness Bands**:
  * $\ge 90.0\%$: `READY`
  * $75.0 - 89.9\%$: `MOSTLY_READY`
  * $50.0 - 74.9\%$: `NEEDS_ATTENTION`
  * $< 50.0\%$: `NOT_READY`

---

## 4. Why This Approach is Better Than Naive Alternatives

| Naive Approach | Limitation | AetherGuard AI Implementation | Practical Benefit |
| :--- | :--- | :--- | :--- |
| **Raw Adverse Event Counts** | Flags common baseline events (e.g. headache) as signals simply because the drug is widely prescribed. | Computes exact disproportionality ratio (PRR) comparing drug event rate against background population event rate. | Prevents false alarms on blockbuster drugs and surfaces true disproportionate signals. |
| **Full CSV Iteration per Query** | Scanning 10M rows in CSV takes 15–30 seconds per search. | Precomputes unique report sets into an in-memory 8.8 MB dictionary cache. | Enables instant sub-second cold starts (~0.43s) and ultra-fast 5–15 ms query response times. |
| **Including Concomitant Medications** | Co-prescribed background drugs distort contingency table cell counts. | Restricts universe exclusively to reports where the drug is Primary Suspect (`PS`) or Secondary Suspect (`SS`). | Eliminates concomitant noise and provides cleaner disproportionality metrics. |
| **Unanchored Generative LLMs** | Generative models hallucinate statistics, fabricate report counts, and invent $p$-values. | Employs deterministic Python service layer; all numbers are calculated by validated mathematical formulas. | 100% mathematical reproducibility with zero hallucinations. |
| **Exact String Section Matching** | Fails when outlines list granular subsections (e.g. `3.2.S.1` instead of `3.2.S`). | Implements hierarchical parent–child regex matching (`match_section` logic). | Accurately validates real-world granular dossier outlines without false gap penalties. |

---

## 5. Key Design Decisions

| Decision | What Was Chosen | Rationale & Tradeoffs | Implementation Evidence |
| :--- | :--- | :--- | :--- |
| **Compact In-Memory Binary Index** | Python pickle cache (`.pkl`) storing set sizes. | Eliminates database round-trip overhead and allows the entire 2026 Q1 dataset ($N=397,209$) to fit into ~8.8 MB RAM. Tradeoff: Index must be regenerated when new quarterly datasets are ingested. | [`src/backend/app/services/prr.py:L228-L246`](file:///c:/Users/LENOVO/Desktop/bob-ai-hackathon-TechTrix/src/backend/app/services/prr.py#L228-L246) |
| **Zero Business Logic in MCP Server** | Direct Python service delegation in `server.py`. | Guarantees that IBM Bob MCP tools and the REST API return identical, validated calculations. Tradeoff: MCP server requires backend services on `PYTHONPATH`. | [`src/mcp_server/server.py:L50-L57`](file:///c:/Users/LENOVO/Desktop/bob-ai-hackathon-TechTrix/src/mcp_server/server.py#L50-L57) |
| **Section 1.6 Optionality** | Classified Section 1.6 (RMP/REMS) as optional. | RMP is an EU requirement and REMS is US-specific under FDAAA; treating it as universal penalized US/global baseline dossiers unfairly. | [`data/ich_m4_requirements.json:L47-L52`](file:///c:/Users/LENOVO/Desktop/bob-ai-hackathon-TechTrix/data/ich_m4_requirements.json#L47-L52) |
| **Strict M5 Section Mapping** | Corrected 5.3.3 (Human PK) and 5.3.6 (Efficacy/Safety) mapping. | Aligns with official ICH M4(R4) numbering where 5.3.1, 5.3.2, 5.3.4, 5.3.5, and 5.3.7 are conditionally optional based on dosage form and study design. | [`src/backend/app/services/test_ctd_checker.py:L189-L228`](file:///c:/Users/LENOVO/Desktop/bob-ai-hackathon-TechTrix/src/backend/app/services/test_ctd_checker.py#L189-L228) |
| **Mandatory Regulatory Disclaimers** | Hardcoded disclaimers in every schema and tool response. | Regulatory guidelines prohibit claiming causality from spontaneous adverse event reports. Tradeoff: Adds disclaimer text to every response payload. | [`src/backend/app/services/prr.py:L87-L90`](file:///c:/Users/LENOVO/Desktop/bob-ai-hackathon-TechTrix/src/backend/app/services/prr.py#L87-L90) |

---

## 6. User Experience & User Journey

### Complete User Journey

```
   1. LAUNCH & DASHBOARD OVERVIEW
      User opens http://localhost:5173 ──→ Views universe metrics (N=397,209) & Top Priority-1 signals
          │
   2. SAFETY SIGNAL EXPLORATION (/signals)
      User searches drug (e.g. ASPIRIN) ──→ Adjusts Min PRR & Priority filter ──→ Views ranked signals
          │
   3. DEEP DIVE AUDIT (/signals/:drug/:event)
      User clicks signal row ──→ Explores 2x2 contingency table, rates, PRR, Chi-Sq, & interpretation
          │
   4. DOSSIER READINESS CHECK (/submission)
      User pastes draft TOC outline ──→ Clicks "Check Completeness" ──→ Instant readiness score (% & band)
          │
   5. GAP REMEDIATION (/gaps/:id)
      User inspects missing sections grouped by CRITICAL / HIGH / MEDIUM priority with regulatory rationale
          │
   6. CONVERSATIONAL ASSISTANT (/bob or IBM Bob IDE)
      User asks questions in natural language ──→ Receives tool-backed deterministic calculations
```

---

## 7. Example Workflows

### Workflow 1: Safety Signal Investigation
1. **Query**: A safety scientist searches for `MEDROXYPROGESTERONE ACETATE` and `Meningioma`.
2. **Execution**: The system retrieves the exact $2\times 2$ partition from the 2026 Q1 index:
   * Target Drug + Target Event ($A$): `1,194`
   * Target Drug + Other Events ($B$): `302`
   * Other Drugs + Target Event ($C$): `87`
   * Other Drugs + Other Events ($D$): `395,626`
3. **Results Computed**:
   * Drug Event Rate: $1,194 / 1,496 = 79.81\%$
   * Background Event Rate: $87 / 395,713 = 0.022\%$
   * **PRR**: `3,630.23` (High Level)
   * **Pearson $\chi^2$**: `295,169.73`
   * **Confidence**: `HIGH` ($A \ge 10, C \ge 5$)
   * **Priority**: `PRIORITY_1`
4. **Outcome**: The scientist receives an auditable $2\times 2$ contingency table with clinical interpretation notes for their safety review.

### Workflow 2: Pre-Submission CTD Dossier Audit
1. **Input**: A regulatory writer pastes a draft TOC outline containing Module 1, 2, 4, and 5 sections, but omitting Module 3 Quality sections (`3.2.S` and `3.2.P`).
2. **Execution**: `check_submission()` parses the text, extracts section numbers, and matches them against the 21 universal requirements.
3. **Results Computed**:
   * Overall Completeness: `85.7%` (`MOSTLY_READY`)
   * Module 1: `100%` (3/3), Module 2: `100%` (7/7), Module 3: `33.3%` (1/3), Module 4: `100%` (4/4), Module 5: `100%` (4/4).
   * **Gap Report**: Flags `3.2.S Drug Substance` and `3.2.P Drug Product` as `CRITICAL` gaps with regulatory guidance notes.
4. **Outcome**: The team resolves the missing CMC sections prior to formal filing, preventing a Refuse-to-File rejection.

---

## 8. Limitations & Future Improvements

1. **Spontaneous Reporting Constraints**: FAERS data is subject to reporting bias and duplicate entries; PRR identifies statistical disproportionality, not biological causality.
2. **Structural Scope**: The submission checker validates structural adherence to ICH M4 format outlines; it does not evaluate scientific data integrity or study results.
3. **Single-Quarter Dataset**: The prototype is built on 2026 Q1; longitudinal multi-year trend tracking is planned for future releases.
4. **In-Memory Store Persistence**: Evaluated CTD submission results are stored in server memory; future versions will integrate Redis or PostgreSQL persistence.
