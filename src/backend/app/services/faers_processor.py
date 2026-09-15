"""
FAERS Data Processor Service
============================
Performs extraction, normalization, deduplication, and integration of raw FDA FAERS
quarterly ASCII data files into a high-performance normalized analytical association dataset.

Input Files (FAERS quarterly release format):
- DEMO: Patient demographic & administrative data (primaryid, caseid, event_dt, age, sex, etc.)
- DRUG: Medicinal product information (role_cod, drugname, prod_ai, etc.)
- REAC: Adverse event Preferred Terms (pt)
- OUTC: Patient outcome severity categories (outc_cod)

Output Schema:
- primary_id: Specific report version ID (join key)
- case_id: Case identifier
- event_date: Event date formatted as YYYY-MM-DD (or blank if missing)
- fda_date: FDA receipt date formatted as YYYY-MM-DD (or blank if missing)
- age: Normalized patient age in years (or blank if missing/unspecified)
- sex: Patient sex
- country: Country of event occurrence
- drug_name: Reported drug name (trimmed uppercase)
- prod_ai: Active ingredient name (trimmed uppercase)
- drug_role: Reported role code (PS, SS, C, I, etc.)
- is_suspect: Boolean (True if role_cod in ['PS', 'SS'], else False)
- reaction_pt: MedDRA Preferred Term
- outcome_codes: Semicolon-delimited distinct outcomes (e.g. "HO;DE")
- is_serious: Boolean (True if serious outcome code present, else False)
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("faers_processor")

SERIOUS_OUTCOME_CODES = {"DE", "LT", "HO", "DS", "CA", "RI", "OT"}


def _parse_faers_date(date_series: pd.Series) -> pd.Series:
    """Safely format YYYYMMDD string dates into YYYY-MM-DD string without guessing invalid values."""
    s = date_series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    # Check for exactly 8 numeric digits
    valid_mask = s.str.match(r"^\d{8}$", na=False)
    
    # Extract YYYY-MM-DD
    formatted = pd.Series("", index=date_series.index)
    
    valid_dates = s[valid_mask]
    years = valid_dates.str.slice(0, 4)
    months = valid_dates.str.slice(4, 6)
    days = valid_dates.str.slice(6, 8)
    
    # Basic sanity check on month and day values
    m_num = pd.to_numeric(months, errors="coerce")
    d_num = pd.to_numeric(days, errors="coerce")
    y_num = pd.to_numeric(years, errors="coerce")
    
    date_ok = (m_num >= 1) & (m_num <= 12) & (d_num >= 1) & (d_num <= 31) & (y_num >= 1900) & (y_num <= 2100)
    valid_indices = valid_dates[date_ok].index
    
    formatted.loc[valid_indices] = (
        years.loc[valid_indices] + "-" + months.loc[valid_indices] + "-" + days.loc[valid_indices]
    )
    return formatted


def _normalize_age_in_years(age_col: pd.Series, age_cod_col: pd.Series) -> pd.Series:
    """
    Safely normalize age to numerical years based on FDA age_cod:
    - YR: Years (x 1.0)
    - MON: Months (x 1.0 / 12.0)
    - WK: Weeks (x 1.0 / 52.1429)
    - DY: Days (x 1.0 / 365.25)
    - HR: Hours (x 1.0 / 8766.0)
    - DEC: Decades (x 10.0)
    Missing, unspecified, or invalid age values remain blank / null.
    """
    ages = pd.to_numeric(age_col, errors="coerce")
    cods = age_cod_col.astype(str).str.strip().str.upper()
    
    norm_age = pd.Series(np.nan, index=age_col.index, dtype=float)
    
    # Valid positive ages only
    valid_num = ages > 0
    
    yr_mask = valid_num & ((cods == "YR") | (cods == "") | (cods == "NAN"))
    norm_age.loc[yr_mask] = ages.loc[yr_mask]
    
    mon_mask = valid_num & (cods == "MON")
    norm_age.loc[mon_mask] = ages.loc[mon_mask] / 12.0
    
    wk_mask = valid_num & (cods == "WK")
    norm_age.loc[wk_mask] = ages.loc[wk_mask] / 52.1429
    
    dy_mask = valid_num & (cods == "DY")
    norm_age.loc[dy_mask] = ages.loc[dy_mask] / 365.25
    
    dec_mask = valid_num & (cods == "DEC")
    norm_age.loc[dec_mask] = ages.loc[dec_mask] * 10.0
    
    hr_mask = valid_num & (cods == "HR")
    norm_age.loc[hr_mask] = ages.loc[hr_mask] / 8766.0
    
    # Round to 2 decimal places for sub-year ages or integer for standard ages
    return norm_age.round(2)


def process_faers_data(
    demo_path: str,
    drug_path: str,
    reac_path: str,
    outc_path: str,
    output_path: str
) -> Dict[str, Any]:
    """
    Processes the raw FDA FAERS demographic, drug, reaction, and outcome files,
    performing validation, cleaning, relational normalization, and deduplication.
    
    Parameters
    ----------
    demo_path : str
        Path to DEMO file (e.g., DEMO26Q1.txt)
    drug_path : str
        Path to DRUG file (e.g., DRUG26Q1.txt)
    reac_path : str
        Path to REAC file (e.g., REAC26Q1.txt)
    outc_path : str
        Path to OUTC file (e.g., OUTC26Q1.txt)
    output_path : str
        Path to save the resulting normalized CSV file.
        
    Returns
    -------
    dict
        Processing statistics and summary metrics.
    """
    start_time = time.time()
    logger.info("Starting FAERS dataset processing...")
    
    for fpath in [demo_path, drug_path, reac_path, outc_path]:
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Required input file not found: {fpath}")
            
    # -------------------------------------------------------------
    # 1. READ DEMO
    # -------------------------------------------------------------
    demo_cols = [
        "primaryid", "caseid", "caseversion",
        "event_dt", "fda_dt", "age", "age_cod",
        "sex", "occr_country"
    ]
    logger.info(f"Reading DEMO from {demo_path}...")
    df_demo = pd.read_csv(
        demo_path,
        sep="$",
        usecols=demo_cols,
        dtype=str,
        encoding="utf-8",
        encoding_errors="replace"
    )
    raw_demo_count = len(df_demo)
    logger.info(f"Loaded {raw_demo_count:,} DEMO rows.")
    
    # Standardize string fields
    df_demo["primaryid"] = df_demo["primaryid"].str.strip()
    df_demo["caseid"] = df_demo["caseid"].str.strip()
    
    # Deduplicate DEMO by primaryid keeping first/latest
    df_demo = df_demo.drop_duplicates(subset=["primaryid"])
    
    # Normalize dates
    df_demo["event_date"] = _parse_faers_date(df_demo["event_dt"])
    df_demo["fda_date"] = _parse_faers_date(df_demo["fda_dt"])
    
    # Normalize age
    df_demo["age_clean"] = _normalize_age_in_years(df_demo["age"], df_demo["age_cod"])
    
    # Clean sex and country
    df_demo["sex_clean"] = df_demo["sex"].fillna("").str.strip().str.upper()
    df_demo["country_clean"] = df_demo["occr_country"].fillna("").str.strip().str.upper()
    
    # Compact demo table
    df_demo_clean = df_demo[[
        "primaryid", "caseid", "event_date", "fda_date",
        "age_clean", "sex_clean", "country_clean"
    ]].rename(columns={
        "primaryid": "primary_id",
        "caseid": "case_id",
        "age_clean": "age",
        "sex_clean": "sex",
        "country_clean": "country"
    })
    del df_demo  # Free memory
    
    # -------------------------------------------------------------
    # 2. READ OUTC (Aggregate distinct outcomes per primaryid)
    # -------------------------------------------------------------
    outc_cols = ["primaryid", "outc_cod"]
    logger.info(f"Reading OUTC from {outc_path}...")
    df_outc = pd.read_csv(
        outc_path,
        sep="$",
        usecols=outc_cols,
        dtype=str,
        encoding="utf-8",
        encoding_errors="replace"
    )
    raw_outc_count = len(df_outc)
    logger.info(f"Loaded {raw_outc_count:,} OUTC rows.")
    
    df_outc["primaryid"] = df_outc["primaryid"].str.strip()
    df_outc["outc_cod"] = df_outc["outc_cod"].fillna("").str.strip().str.upper()
    df_outc = df_outc[df_outc["outc_cod"] != ""].drop_duplicates()
    
    # Group outcomes by primaryid
    def _agg_outcomes(group):
        codes = sorted(list(set(group)))
        return ";".join(codes)
        
    df_outc_agg = df_outc.groupby("primaryid")["outc_cod"].apply(_agg_outcomes).reset_index()
    df_outc_agg.rename(columns={"primaryid": "primary_id", "outc_cod": "outcome_codes"}, inplace=True)
    
    # Calculate is_serious per primaryid
    def _check_serious(codes_str: str) -> bool:
        if not codes_str:
            return False
        codes = set(codes_str.split(";"))
        return bool(codes & SERIOUS_OUTCOME_CODES)
        
    df_outc_agg["is_serious"] = df_outc_agg["outcome_codes"].apply(_check_serious)
    del df_outc  # Free memory
    
    # Join outcomes into demographic data
    df_demo_outc = pd.merge(df_demo_clean, df_outc_agg, on="primary_id", how="left")
    df_demo_outc["outcome_codes"] = df_demo_outc["outcome_codes"].fillna("")
    df_demo_outc["is_serious"] = df_demo_outc["is_serious"].fillna(False).astype(bool)
    del df_demo_clean, df_outc_agg  # Free memory
    
    # -------------------------------------------------------------
    # 3. READ DRUG
    # -------------------------------------------------------------
    drug_cols = ["primaryid", "role_cod", "drugname", "prod_ai"]
    logger.info(f"Reading DRUG from {drug_path}...")
    df_drug = pd.read_csv(
        drug_path,
        sep="$",
        usecols=drug_cols,
        dtype=str,
        encoding="utf-8",
        encoding_errors="replace"
    )
    raw_drug_count = len(df_drug)
    logger.info(f"Loaded {raw_drug_count:,} DRUG rows.")
    
    df_drug["primaryid"] = df_drug["primaryid"].str.strip()
    df_drug["drugname"] = df_drug["drugname"].fillna("").str.strip().str.upper()
    df_drug["prod_ai"] = df_drug["prod_ai"].fillna("").str.strip().str.upper()
    df_drug["role_cod"] = df_drug["role_cod"].fillna("").str.strip().str.upper()
    
    # Remove rows with empty drugname and empty prod_ai
    df_drug = df_drug[(df_drug["drugname"] != "") | (df_drug["prod_ai"] != "")]
    
    # Determine suspect flag
    df_drug["is_suspect"] = df_drug["role_cod"].isin(["PS", "SS"])
    
    # Deduplicate at (primaryid, drugname, prod_ai, role_cod) level
    df_drug = df_drug.drop_duplicates(subset=["primaryid", "drugname", "prod_ai", "role_cod"])
    df_drug.rename(columns={
        "primaryid": "primary_id",
        "drugname": "drug_name",
        "role_cod": "drug_role"
    }, inplace=True)
    
    # -------------------------------------------------------------
    # 4. READ REAC
    # -------------------------------------------------------------
    reac_cols = ["primaryid", "pt"]
    logger.info(f"Reading REAC from {reac_path}...")
    df_reac = pd.read_csv(
        reac_path,
        sep="$",
        usecols=reac_cols,
        dtype=str,
        encoding="utf-8",
        encoding_errors="replace"
    )
    raw_reac_count = len(df_reac)
    logger.info(f"Loaded {raw_reac_count:,} REAC rows.")
    
    df_reac["primaryid"] = df_reac["primaryid"].str.strip()
    df_reac["pt"] = df_reac["pt"].fillna("").str.strip()
    
    # Remove empty reaction terms
    df_reac = df_reac[df_reac["pt"] != ""]
    
    # Deduplicate reaction terms per primaryid
    df_reac = df_reac.drop_duplicates(subset=["primaryid", "pt"])
    df_reac.rename(columns={"primaryid": "primary_id", "pt": "reaction_pt"}, inplace=True)
    
    # -------------------------------------------------------------
    # 5. INTEGRATION & CONTROLLED JOIN
    # -------------------------------------------------------------
    logger.info("Merging DRUG and REAC associations on primary_id...")
    # Merge DRUG and REAC
    df_assoc = pd.merge(df_drug, df_reac, on="primary_id", how="inner")
    del df_drug, df_reac  # Free memory
    
    logger.info(f"Generated {len(df_assoc):,} drug-reaction pair rows. Merging demographic & outcome attributes...")
    # Merge DEMO + OUTC info
    df_final = pd.merge(df_assoc, df_demo_outc, on="primary_id", how="inner")
    del df_assoc, df_demo_outc  # Free memory
    
    # Deduplicate final associations
    subset_keys = ["primary_id", "drug_name", "prod_ai", "drug_role", "reaction_pt"]
    df_final = df_final.drop_duplicates(subset=subset_keys)
    
    # Align to required target schema
    target_columns = [
        "primary_id",
        "case_id",
        "event_date",
        "fda_date",
        "age",
        "sex",
        "country",
        "drug_name",
        "prod_ai",
        "drug_role",
        "is_suspect",
        "reaction_pt",
        "outcome_codes",
        "is_serious"
    ]
    df_final = df_final[target_columns]
    
    # -------------------------------------------------------------
    # 6. WRITE OUTPUT & COMPUTE STATISTICS
    # -------------------------------------------------------------
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    logger.info(f"Writing normalized dataset to {output_path}...")
    df_final.to_csv(output_path, index=False, encoding="utf-8")
    
    elapsed_time = round(time.time() - start_time, 2)
    
    # Collect statistics
    stats = {
        "status": "success",
        "elapsed_seconds": elapsed_time,
        "demo_reports_raw": raw_demo_count,
        "drug_rows_raw": raw_drug_count,
        "reac_rows_raw": raw_reac_count,
        "outc_rows_raw": raw_outc_count,
        "unique_primary_ids": int(df_final["primary_id"].nunique()),
        "unique_case_ids": int(df_final["case_id"].nunique()),
        "unique_reported_drugs": int(df_final["drug_name"].replace("", np.nan).nunique()),
        "unique_active_ingredients": int(df_final["prod_ai"].replace("", np.nan).nunique()),
        "unique_reactions": int(df_final["reaction_pt"].nunique()),
        "normalized_associations": len(df_final),
        "suspect_associations": int(df_final["is_suspect"].sum()),
        "output_path": output_path,
        "output_size_bytes": os.path.getsize(output_path)
    }
    
    logger.info("FAERS processing complete!")
    return stats


def main():
    """Command-line entry point to process the default 2026Q1 dataset."""
    # From src/backend/app/services/faers_processor.py -> project_root is 3 parents up
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    if not (project_root / "data" / "raw" / "faers").exists():
        project_root = Path(__file__).resolve().parents[3]
    if not (project_root / "data" / "raw" / "faers").exists():
        # Fallback to checking cwd or search
        cwd = Path(os.getcwd()).resolve()
        if (cwd / "data" / "raw" / "faers").exists():
            project_root = cwd
        elif (cwd.parent / "data" / "raw" / "faers").exists():
            project_root = cwd.parent
        elif (cwd.parent.parent / "data" / "raw" / "faers").exists():
            project_root = cwd.parent.parent
            
    demo_file = project_root / "data" / "raw" / "faers" / "2026Q1" / "DEMO26Q1.txt"
    drug_file = project_root / "data" / "raw" / "faers" / "2026Q1" / "DRUG26Q1.txt"
    reac_file = project_root / "data" / "raw" / "faers" / "2026Q1" / "REAC26Q1.txt"
    outc_file = project_root / "data" / "raw" / "faers" / "2026Q1" / "OUTC26Q1.txt"
    out_file = project_root / "data" / "processed" / "faers_2026Q1_normalized.csv"
    
    print("=" * 65)
    print("FDA FAERS Data Processor (2026 Q1)")
    print("=" * 65)
    print(f"DEMO:   {demo_file}")
    print(f"DRUG:   {drug_file}")
    print(f"REAC:   {reac_file}")
    print(f"OUTC:   {outc_file}")
    print(f"OUTPUT: {out_file}")
    print("-" * 65)
    
    stats = process_faers_data(
        demo_path=str(demo_file),
        drug_path=str(drug_file),
        reac_path=str(reac_file),
        outc_path=str(outc_file),
        output_path=str(out_file)
    )
    
    print("\nProcessing Results & Statistics:")
    print("-" * 65)
    for k, v in stats.items():
        if isinstance(v, int):
            print(f"  {k:30}: {v:,}")
        elif isinstance(v, float):
            print(f"  {k:30}: {v:.2f}")
        else:
            print(f"  {k:30}: {v}")
    print("=" * 65)


if __name__ == "__main__":
    main()
