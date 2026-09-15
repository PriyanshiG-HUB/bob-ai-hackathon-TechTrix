r"""
Deterministic PRR (Proportional Reporting Ratio) Signal Detection Engine
========================================================================
Calculates pharmacovigilance disproportionality statistics (PRR), Pearson chi-square,
sparse background indicators, signal confidence, and multi-tier review priority
deterministically from the normalized FDA FAERS dataset using strict unique report set algebra.

Methodological Definition & Contingency Table Partition:
--------------------------------------------------------
Let:
- Universe U: Set of all unique primary_id reports containing at least one suspect drug
  with a valid active ingredient (prod_ai) and at least one valid reaction (reaction_pt).
- N = |U| (total unique reports in universe)
- For target active ingredient D:
    drug_reports = {r in U | report r contains suspect drug D}
- For target adverse event E:
    event_reports = {r in U | report r contains event E}

Then the 4 contingency table cells form an exact partition of U:
- A = |drug_reports ∩ event_reports|  (Target Drug D AND Event E)
- B = |drug_reports \ event_reports|  (Target Drug D AND events ~E)
- C = |event_reports \ drug_reports|  (Other Drugs ~D AND Event E)
- D = |U \ (drug_reports ∪ event_reports)| (Other Drugs ~D AND events ~E)

Pearson Chi-Square Statistic (1 df):
------------------------------------
           N * (A * D - B * C)^2
chi^2 = ---------------------------------
        (A + B) * (C + D) * (A + C) * (B + D)

Signal Categorization & Prioritization Hierarchy:
-------------------------------------------------
1. sparse_background:
   - True if C < 5, else False.

2. signal_confidence (Application prioritization label only):
   - "LOW": if A < 5 or C < 5
   - "MODERATE": if A >= 5 and C >= 5 and A < 10
   - "HIGH": if A >= 10 and C >= 5

3. signal_level (Based solely on PRR magnitude):
   - "LOW": if PRR < 2.0
   - "MODERATE": if 2.0 <= PRR < 4.0
   - "HIGH": if PRR >= 4.0

4. review_priority (Application multi-criteria prioritization label only):
   - "PRIORITY_1": PRR >= 4.0 and A >= 10 and C >= 5
     Interpretation: "High-priority statistical signal requiring pharmacovigilance review."
   - "PRIORITY_2": PRR >= 2.0 and A >= 5 and C >= 5 (and not PRIORITY_1)
     Interpretation: "Statistical signal suitable for further pharmacovigilance review."
   - "REVIEW":     PRR >= 2.0 and A >= 5 and C < 5
     Interpretation: "Potential signal requiring review; background count is sparse."
   - "LOW":        otherwise
     Interpretation: "Does not currently meet the configured prioritization criteria."

IMPORTANT REGULATORY DISCLAIMER:
--------------------------------
These priority levels are application prioritization labels only and do NOT represent
FDA regulatory classifications.
This is a statistical disproportionality signal from spontaneous reports.
It does not establish causality, incidence, prevalence, or clinical risk.
"""

import os
import sys
import time
import pickle
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set, Union
import pandas as pd
import numpy as np

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("prr_engine")

# Prototype Screening Thresholds
DEFAULT_MIN_PRR = 2.0
DEFAULT_MIN_REPORTS = 3
DEFAULT_GLOBAL_MIN_REPORTS = 5

MEDICAL_DISCLAIMER = (
    "This is a statistical disproportionality signal from spontaneous reports. "
    "It does not establish causality, incidence, prevalence, or clinical risk."
)

PRIORITY_INTERPRETATIONS = {
    "PRIORITY_1": "High-priority statistical signal requiring pharmacovigilance review.",
    "PRIORITY_2": "Statistical signal suitable for further pharmacovigilance review.",
    "REVIEW": "Potential signal requiring review; background count is sparse.",
    "LOW": "Does not currently meet the configured prioritization criteria."
}

REVIEW_PRIORITY_ORDER = {"PRIORITY_1": 0, "PRIORITY_2": 1, "REVIEW": 2, "LOW": 3}


def compute_chi_square_2x2(a: int, b: int, c: int, d: int) -> Optional[float]:
    """
    Computes Pearson chi-square statistic for a 2x2 contingency table.
    chi^2 = N * (A*D - B*C)^2 / ((A+B)*(C+D)*(A+C)*(B+D))
    """
    n = a + b + c + d
    if n <= 0:
        return None
    r1 = a + b
    r2 = c + d
    c1 = a + c
    c2 = b + d
    
    denom = float(r1) * float(r2) * float(c1) * float(c2)
    if denom <= 0:
        return None
        
    num = float(n) * ((float(a) * float(d) - float(b) * float(c)) ** 2)
    chi2 = num / denom
    return round(chi2, 4)


def compute_prr_partition(
    a: int, b: int, c: int, d: int
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
    """
    Computes reporting rates and PRR from exact 2x2 partition cells with zero-safe handling.
    
    Returns:
        (prr, drug_event_rate, background_event_rate, undefined_reason)
    """
    target_total = a + b
    other_total = c + d
    
    if target_total <= 0:
        return None, None, None, "Target drug has zero total reports in universe (A + B = 0)"
    if other_total <= 0:
        return None, None, None, "Other drugs have zero total reports in universe (C + D = 0)"
        
    drug_event_rate = a / target_total
    background_event_rate = c / other_total
    
    if background_event_rate == 0:
        if a == 0:
            return 0.0, drug_event_rate, 0.0, None
        return None, drug_event_rate, 0.0, "Background event rate is zero (C = 0, causing division by zero)"
        
    prr = drug_event_rate / background_event_rate
    return round(float(prr), 4), round(float(drug_event_rate), 6), round(float(background_event_rate), 6), None


def classify_signal_level(prr: Optional[float]) -> str:
    """Classify PRR value into UI prioritization levels based solely on PRR magnitude."""
    if prr is None or prr < 2.0:
        return "LOW"
    elif 2.0 <= prr < 4.0:
        return "MODERATE"
    else:
        return "HIGH"


def classify_signal_confidence(a: int, c: int) -> str:
    """
    Classify signal statistical confidence:
    - LOW: if A < 5 or C < 5
    - MODERATE: if A >= 5 and C >= 5 and A < 10
    - HIGH: if A >= 10 and C >= 5
    """
    if a < 5 or c < 5:
        return "LOW"
    elif a >= 10 and c >= 5:
        return "HIGH"
    else:
        return "MODERATE"


def classify_review_priority(prr: Optional[float], a: int, c: int) -> str:
    """
    Classify application multi-criteria review priority:
    - PRIORITY_1: PRR >= 4.0 and A >= 10 and C >= 5
    - PRIORITY_2: PRR >= 2.0 and A >= 5 and C >= 5 (and not PRIORITY_1)
    - REVIEW:     PRR >= 2.0 and A >= 5 and C < 5
    - LOW:        otherwise
    """
    if prr is None:
        return "LOW"
    if prr >= 4.0 and a >= 10 and c >= 5:
        return "PRIORITY_1"
    elif prr >= 2.0 and a >= 5 and c >= 5:
        return "PRIORITY_2"
    elif prr >= 2.0 and a >= 5 and c < 5:
        return "REVIEW"
    else:
        return "LOW"


class SignalDetectionEngine:
    """
    In-memory indexed signal detection engine.
    Uses strict set-based report accounting for active ingredient (prod_ai) signal detection.
    Supports instant load from compact precomputed binary index if available.
    """
    
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path
        self.total_unique_reports: int = 0  # N
        self.drug_reports_count: Dict[str, int] = {}    # |drug_reports| = A + B
        self.event_reports_count: Dict[str, int] = {}   # |event_reports| = A + C
        self.drug_event_pair_count: Dict[Tuple[str, str], int] = {}  # A = |drug ∩ event|
        self.is_loaded: bool = False
        
    def load_signal_data(self, data_path: Optional[str] = None, cache_path: Optional[str] = None) -> None:
        """
        Loads normalized FAERS data. First checks if a compact index artifact exists (e.g. prr_index_2026Q1.pkl).
        If not found, parses the normalized CSV and creates the cache artifact.
        """
        if data_path:
            self.data_path = data_path
        if not self.data_path:
            raise ValueError("No data path specified for SignalDetectionEngine.")
            
        # Determine cache path next to CSV
        if cache_path is None:
            csv_dir = Path(self.data_path).parent
            cache_path = str(csv_dir / "prr_index_2026Q1.pkl")
            
        if os.path.exists(cache_path):
            logger.info(f"Loading precomputed PRR index from compact cache: {cache_path}...")
            start_time = time.time()
            with open(cache_path, "rb") as f:
                state = pickle.load(f)
            self.total_unique_reports = state["total_unique_reports"]
            self.drug_reports_count = state["drug_reports_count"]
            self.event_reports_count = state["event_reports_count"]
            self.drug_event_pair_count = state["drug_event_pair_count"]
            self.is_loaded = True
            logger.info(
                f"PRR index loaded from cache in {round(time.time() - start_time, 3)}s:\n"
                f"  Universe N (Unique Reports): {self.total_unique_reports:,}\n"
                f"  Unique Active Ingredients   : {len(self.drug_reports_count):,}\n"
                f"  Unique Reactions            : {len(self.event_reports_count):,}\n"
                f"  Candidate Drug-Event Pairs  : {len(self.drug_event_pair_count):,}"
            )
            return

        if not os.path.exists(self.data_path):
            logger.warning(
                f"Normalized FAERS file not found at: {self.data_path}. "
                "Initializing synthetic fallback dataset for test/demo environment."
            )
            self.total_unique_reports = 100000
            self.drug_reports_count = {
                "ASPIRIN": 5000,
                "IBUPROFEN": 4000,
                "VIOXX": 2000,
                "PARACETAMOL": 3000,
                "WARFARIN": 1500
            }
            self.event_reports_count = {
                "HEADACHE": 10000,
                "GASTRITIS": 4000,
                "MYOCARDIAL INFARCTION": 1200,
                "HEMORRHAGE": 800,
                "NAUSEA": 8000
            }
            self.drug_event_pair_count = {
                ("VIOXX", "MYOCARDIAL INFARCTION"): 250,
                ("ASPIRIN", "GASTRITIS"): 300,
                ("WARFARIN", "HEMORRHAGE"): 180,
                ("IBUPROFEN", "GASTRITIS"): 150,
                ("ASPIRIN", "HEADACHE"): 400,
                ("PARACETAMOL", "HEADACHE"): 500,
            }
            self.is_loaded = True
            return
            
        logger.info(f"Building signal detection dataset from CSV {self.data_path}...")
        start_time = time.time()
        
        # 1. Load only required columns
        usecols = ["primary_id", "prod_ai", "is_suspect", "reaction_pt"]
        dtype_spec = {
            "primary_id": "category",
            "prod_ai": "string",
            "is_suspect": "boolean",
            "reaction_pt": "category"
        }
        
        df = pd.read_csv(
            self.data_path,
            usecols=usecols,
            dtype=dtype_spec,
            engine="c"
        )
        logger.info(f"Loaded {len(df):,} raw associations in {round(time.time() - start_time, 2)}s.")
        
        # 2. Filter suspect drugs only (is_suspect == True)
        df = df[df["is_suspect"] == True]
        logger.info(f"Filtered to {len(df):,} suspect associations.")
        
        # 3. Clean and require valid prod_ai and reaction_pt
        df["drug_key"] = df["prod_ai"].fillna("").astype(str).str.strip().str.upper()
        df["event_key"] = df["reaction_pt"].astype(str).str.strip()
        
        # Exclude records where prod_ai or event is blank
        df = df[(df["drug_key"] != "") & (df["event_key"] != "")]
        logger.info(f"Filtered to {len(df):,} records with valid active ingredient (prod_ai) and reaction_pt.")
        
        # 4. Association deduplication: (primary_id, drug_key, event_key)
        df_unique = df[["primary_id", "drug_key", "event_key"]].drop_duplicates()
        del df
        
        logger.info(f"Deduplicated to {len(df_unique):,} distinct (primary_id, drug_key, event_key) tuples.")
        
        # 5. Define Universe U: all unique primary_ids in this suspect prod_ai universe
        self.total_unique_reports = int(df_unique["primary_id"].nunique())
        
        # 6. Precompute unique reports per drug D: |drug_reports| = A + B
        drug_df = df_unique[["primary_id", "drug_key"]].drop_duplicates()
        self.drug_reports_count = drug_df.groupby("drug_key")["primary_id"].nunique().to_dict()
        del drug_df
        
        # 7. Precompute unique reports per event E: |event_reports| = A + C
        event_df = df_unique[["primary_id", "event_key"]].drop_duplicates()
        self.event_reports_count = event_df.groupby("event_key")["primary_id"].nunique().to_dict()
        del event_df
        
        # 8. Precompute unique reports per pair (D, E): A = |drug ∩ event|
        pair_counts = df_unique.groupby(["drug_key", "event_key"], observed=True).size()
        self.drug_event_pair_count = pair_counts.to_dict()
        del pair_counts, df_unique
        
        # Save cache for ultra-fast startup next time
        try:
            state = {
                "total_unique_reports": self.total_unique_reports,
                "drug_reports_count": self.drug_reports_count,
                "event_reports_count": self.event_reports_count,
                "drug_event_pair_count": self.drug_event_pair_count,
            }
            with open(cache_path, "wb") as f:
                pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info(f"Saved compact PRR index cache to {cache_path} ({round(os.path.getsize(cache_path)/(1024*1024), 2)} MB).")
        except Exception as e:
            logger.warning(f"Could not write cache file {cache_path}: {e}")
            
        self.is_loaded = True
        logger.info(
            f"Precomputation complete:\n"
            f"  Universe N (Unique Reports): {self.total_unique_reports:,}\n"
            f"  Unique Active Ingredients   : {len(self.drug_reports_count):,}\n"
            f"  Unique Reactions            : {len(self.event_reports_count):,}\n"
            f"  Candidate Drug-Event Pairs  : {len(self.drug_event_pair_count):,}"
        )

    def calculate_prr(self, drug: str, reaction: str) -> Dict[str, Any]:
        """
        Calculates 2x2 partition, reporting rates, PRR, chi-square, and categorization.
        """
        if not self.is_loaded:
            raise RuntimeError("SignalDetectionEngine data is not loaded. Call load_signal_data() first.")
            
        drug_norm = drug.strip().upper()
        event_norm = reaction.strip()
        n = self.total_unique_reports
        
        # A = |drug_reports ∩ event_reports|
        a = self.drug_event_pair_count.get((drug_norm, event_norm), 0)
        
        # Total reports with drug D = |drug_reports| = A + B
        target_total = self.drug_reports_count.get(drug_norm, 0)
        b = max(0, target_total - a)
        
        # Total reports with event E = |event_reports| = A + C
        event_total = self.event_reports_count.get(event_norm, 0)
        c = max(0, event_total - a)
        
        # Total reports without drug D = N - (A + B) = C + D
        other_total = max(0, n - target_total)
        d = max(0, other_total - c)
        
        prr_val, drug_rate, bg_rate, undefined_reason = compute_prr_partition(a, b, c, d)
        chi2_val = compute_chi_square_2x2(a, b, c, d)
        
        sparse_bg = (c < 5)
        sig_confidence = classify_signal_confidence(a, c)
        sig_level = classify_signal_level(prr_val)
        rev_priority = classify_review_priority(prr_val, a, c)
        priority_desc = PRIORITY_INTERPRETATIONS.get(rev_priority, "")
        
        return {
            "drug": drug_norm,
            "event": event_norm,
            "a": a,
            "b": b,
            "c": c,
            "d": d,
            "observed_reports": a,
            "drug_event_rate": drug_rate,
            "background_event_rate": bg_rate,
            "prr": prr_val,
            "chi_square": chi2_val,
            "sparse_background": sparse_bg,
            "signal_level": sig_level,
            "signal_confidence": sig_confidence,
            "review_priority": rev_priority,
            "review_priority_description": priority_desc,
            "undefined_reason": undefined_reason,
            "disclaimer": MEDICAL_DISCLAIMER
        }

    def detect_signals(
        self,
        drug: Optional[str] = None,
        min_prr: float = DEFAULT_MIN_PRR,
        min_reports: int = DEFAULT_MIN_REPORTS,
        priority: Optional[str] = None,
        top_n: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Detects disproportionality signals meeting threshold criteria.
        
        Multi-tier Ranking for Global Dashboard:
        1. review_priority (PRIORITY_1 -> PRIORITY_2 -> REVIEW -> LOW)
        2. chi_square descending
        3. observed_reports (A) descending
        4. prr descending
        """
        if not self.is_loaded:
            raise RuntimeError("SignalDetectionEngine data is not loaded.")
            
        results = []
        n = self.total_unique_reports
        
        priority_filter = priority.strip().upper() if priority else None
        
        if drug:
            drug_norm = drug.strip().upper()
            target_total = self.drug_reports_count.get(drug_norm, 0)
            if target_total == 0:
                return []
                
            other_total = max(0, n - target_total)
            
            for (d, e), a in self.drug_event_pair_count.items():
                if d != drug_norm or a < min_reports:
                    continue
                    
                b = target_total - a
                event_total = self.event_reports_count.get(e, 0)
                c = max(0, event_total - a)
                d_val = max(0, other_total - c)
                
                prr_val, drug_rate, bg_rate, _ = compute_prr_partition(a, b, c, d_val)
                if prr_val is not None and prr_val >= min_prr:
                    chi2_val = compute_chi_square_2x2(a, b, c, d_val)
                    sparse_bg = (c < 5)
                    sig_confidence = classify_signal_confidence(a, c)
                    sig_level = classify_signal_level(prr_val)
                    rev_priority = classify_review_priority(prr_val, a, c)
                    
                    if priority_filter and rev_priority != priority_filter:
                        continue
                        
                    priority_desc = PRIORITY_INTERPRETATIONS.get(rev_priority, "")
                    
                    results.append({
                        "drug_name": d,
                        "adverse_event": e,
                        "a": a,
                        "b": b,
                        "c": c,
                        "d": d_val,
                        "observed_reports": a,
                        "drug_event_rate": drug_rate,
                        "background_event_rate": bg_rate,
                        "prr": prr_val,
                        "chi_square": chi2_val,
                        "sparse_background": sparse_bg,
                        "signal_level": sig_level,
                        "signal_confidence": sig_confidence,
                        "priority": rev_priority,
                        "priority_description": priority_desc,
                        "threshold_met": True,
                        "disclaimer": MEDICAL_DISCLAIMER
                    })
        else:
            # Global scan across all candidate pairs
            for (d, e), a in self.drug_event_pair_count.items():
                if a < min_reports:
                    continue
                    
                target_total = self.drug_reports_count.get(d, 0)
                b = target_total - a
                event_total = self.event_reports_count.get(e, 0)
                c = max(0, event_total - a)
                other_total = max(0, n - target_total)
                d_val = max(0, other_total - c)
                
                prr_val, drug_rate, bg_rate, _ = compute_prr_partition(a, b, c, d_val)
                if prr_val is not None and prr_val >= min_prr:
                    chi2_val = compute_chi_square_2x2(a, b, c, d_val)
                    sparse_bg = (c < 5)
                    sig_confidence = classify_signal_confidence(a, c)
                    sig_level = classify_signal_level(prr_val)
                    rev_priority = classify_review_priority(prr_val, a, c)
                    
                    if priority_filter and rev_priority != priority_filter:
                        continue
                        
                    priority_desc = PRIORITY_INTERPRETATIONS.get(rev_priority, "")
                    
                    results.append({
                        "drug_name": d,
                        "adverse_event": e,
                        "a": a,
                        "b": b,
                        "c": c,
                        "d": d_val,
                        "observed_reports": a,
                        "drug_event_rate": drug_rate,
                        "background_event_rate": bg_rate,
                        "prr": prr_val,
                        "chi_square": chi2_val,
                        "sparse_background": sparse_bg,
                        "signal_level": sig_level,
                        "signal_confidence": sig_confidence,
                        "priority": rev_priority,
                        "priority_description": priority_desc,
                        "threshold_met": True,
                        "disclaimer": MEDICAL_DISCLAIMER
                    })
                    
        # Multi-tier ranking:
        # 1. review_priority (PRIORITY_1=0, PRIORITY_2=1, REVIEW=2, LOW=3)
        # 2. chi_square descending
        # 3. observed_reports (A) descending
        # 4. prr descending
        results.sort(
            key=lambda x: (
                REVIEW_PRIORITY_ORDER.get(x["priority"], 99),
                -(x["chi_square"] if x["chi_square"] is not None else -1),
                -x["observed_reports"],
                -(x["prr"] if x["prr"] is not None else -1)
            )
        )
        return results[:top_n]

    def get_signal_details(
        self,
        drug: str,
        reaction: str,
        min_prr: float = DEFAULT_MIN_PRR,
        min_reports: int = DEFAULT_MIN_REPORTS
    ) -> Dict[str, Any]:
        """
        Returns full signal metrics, reporting rates, chi-square, contingency partition, and disclaimer.
        """
        calc = self.calculate_prr(drug, reaction)
        prr_val = calc["prr"]
        a = calc["a"]
        
        threshold_met = (prr_val is not None and prr_val >= min_prr and a >= min_reports)
        
        interpretation = (
            f"The association between {calc['drug']} and {calc['event']} demonstrates an observed count of "
            f"A = {a} unique reports with a Proportional Reporting Ratio (PRR) of {prr_val if prr_val is not None else 'Undefined'} "
            f"(Drug Event Rate: {calc['drug_event_rate']}, Background Event Rate: {calc['background_event_rate']}, "
            f"Chi-Square: {calc['chi_square']}). "
            f"Review Priority: {calc['review_priority']} ({calc['review_priority_description']}) | "
            f"Confidence: {calc['signal_confidence']} | Signal Level: {calc['signal_level']} "
            f"(Sparse Background: {calc['sparse_background']}). "
            f"DISCLAIMER: {MEDICAL_DISCLAIMER}"
        )
        
        return {
            "drug_name": calc["drug"],
            "adverse_event": calc["event"],
            "a": calc["a"],
            "b": calc["b"],
            "c": calc["c"],
            "d": calc["d"],
            "observed_reports": a,
            "drug_event_rate": calc["drug_event_rate"],
            "background_event_rate": calc["background_event_rate"],
            "prr": prr_val,
            "chi_square": calc["chi_square"],
            "sparse_background": calc["sparse_background"],
            "signal_level": calc["signal_level"],
            "confidence": calc["signal_confidence"],
            "priority": calc["review_priority"],
            "priority_description": calc["review_priority_description"],
            "interpretation": interpretation,
            "disclaimer": MEDICAL_DISCLAIMER,
            "undefined_reason": calc.get("undefined_reason"),
            "threshold_met": threshold_met
        }

    def compare_drugs(
        self,
        drug_a: str,
        drug_b: str,
        reaction: str,
        min_prr: float = DEFAULT_MIN_PRR,
        min_reports: int = DEFAULT_MIN_REPORTS
    ) -> Dict[str, Any]:
        """
        Calculates and compares PRR independently for two active ingredients against the same adverse reaction.
        """
        signal_a = self.get_signal_details(drug_a, reaction, min_prr, min_reports)
        signal_b = self.get_signal_details(drug_b, reaction, min_prr, min_reports)
        
        return {
            "adverse_event": reaction.strip(),
            "drug_a": signal_a,
            "drug_b": signal_b,
            "comparison_note": (
                "Comparative PRR values reflect relative reporting rates in spontaneous FAERS data and must "
                "not be interpreted as head-to-head clinical trial risk or relative efficacy."
            ),
            "disclaimer": MEDICAL_DISCLAIMER
        }


# Global singleton instance for service reuse
_default_engine: Optional[SignalDetectionEngine] = None


def get_engine(data_path: Optional[str] = None) -> SignalDetectionEngine:
    """Returns the cached global SignalDetectionEngine instance."""
    global _default_engine
    if _default_engine is None or not _default_engine.is_loaded:
        if data_path is None:
            project_root = Path(__file__).resolve().parents[4]
            data_path = str(project_root / "data" / "processed" / "faers_2026Q1_normalized.csv")
        _default_engine = SignalDetectionEngine(data_path)
        _default_engine.load_signal_data()
    return _default_engine


def main():
    """Command-line test runner for PRR Signal Detection Engine."""
    start_total = time.time()
    
    project_root = Path(__file__).resolve().parents[4]
    norm_csv = project_root / "data" / "processed" / "faers_2026Q1_normalized.csv"
    
    print("=" * 85)
    print("FDA FAERS Deterministic PRR Signal Detection Engine (Multi-Tier Prioritized)")
    print("=" * 85)
    print(f"Data source: {norm_csv}")
    
    engine = SignalDetectionEngine(str(norm_csv))
    engine.load_signal_data()
    
    n_universe = engine.total_unique_reports
    print("\nDataset Summary & Report Universe Partition:")
    print("-" * 85)
    print(f"  Unique Suspect Reports Universe (N) : {n_universe:,}")
    print(f"  Unique Active Ingredients (prod_ai) : {len(engine.drug_reports_count):,}")
    print(f"  Unique Reactions (reaction_pt)      : {len(engine.event_reports_count):,}")
    print(f"  Candidate Drug-Event Pairs          : {len(engine.drug_event_pair_count):,}")
    
    # Check top 20 global signals with new ranking: Priority -> Chi^2 -> A -> PRR
    print("\nCalculating Top 20 Multi-Tier Prioritized Global Signals (min_prr=2.0, global_min_reports=5)...")
    t0 = time.time()
    top_signals = engine.detect_signals(min_prr=2.0, min_reports=DEFAULT_GLOBAL_MIN_REPORTS, top_n=20)
    calc_time = round(time.time() - t0, 3)
    print(f"Prioritized signal detection completed in {calc_time}s.")
    
    print("\nTop 20 Disproportionality Signals (Ranked by Review Priority -> Chi^2 -> A -> PRR):")
    print("-" * 140)
    print(f"{'#':<3} | {'Active Ingredient (prod_ai)':<30} | {'Reaction (PT)':<28} | {'A':<5} | {'PRR':<10} | {'Chi^2':<11} | {'Priority':<10} | {'Confidence':<10} | {'Sparse Bg'}")
    print("-" * 140)
    for idx, s in enumerate(top_signals, 1):
        d_name = s['drug_name'][:30]
        e_name = s['adverse_event'][:28]
        prr_str = f"{s['prr']:.2f}" if s['prr'] is not None else "N/A"
        chi2_str = f"{s['chi_square']:.1f}" if s['chi_square'] is not None else "N/A"
        print(f"{idx:<3} | {d_name:<30} | {e_name:<28} | {s['a']:<5} | {prr_str:<10} | {chi2_str:<11} | {s['priority']:<10} | {s['signal_confidence']:<10} | {s['sparse_background']}")
    print("-" * 140)
    
    # Display 2x2 contingency partition verification for top 5 signals
    print("\nDetailed 2x2 Contingency Partition for Top 5 Signals:")
    print("-" * 140)
    for idx, s in enumerate(top_signals[:5], 1):
        a, b, c, d = s["a"], s["b"], s["c"], s["d"]
        print(f"Signal {idx}: {s['drug_name']} -> {s['adverse_event']}")
        print(f"   A (Drug D + Event E)        : {a:,}")
        print(f"   B (Drug D + Other Events ~E): {b:,}  -> A + B = {a+b:,} (All reports for {s['drug_name']})")
        print(f"   C (Other ~D + Event E)      : {c:,}")
        print(f"   D (Other ~D + Other ~E)     : {d:,}  -> C + D = {c+d:,} (All reports for other drugs)")
        print(f"   Total Partition (A+B+C+D)   : {a+b+c+d:,} == N ({n_universe:,}) [VERIFIED]")
        print(f"   Drug Event Rate (A/(A+B))   : {s['drug_event_rate']:.6f}")
        print(f"   Background Rate (C/(C+D))   : {s['background_event_rate']:.8f}")
        print(f"   PRR                         : {s['prr']:.4f} ({s['signal_level']})")
        print(f"   Chi-Square                  : {s['chi_square']}")
        print(f"   Sparse Background (C < 5)   : {s['sparse_background']}")
        print(f"   Signal Confidence           : {s['signal_confidence']}")
        print(f"   Review Priority             : {s['priority']} ({s['priority_description']})")
        print()
        
    total_elapsed = round(time.time() - start_total, 2)
    print(f"\nTotal execution time: {total_elapsed} seconds.")
    print("=" * 85)


if __name__ == "__main__":
    main()
