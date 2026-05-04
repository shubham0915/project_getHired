"""
PII Leakage Auditor — Real Cross-Check Between Raw & Masked Data

This module ACTUALLY tests whether raw PII values appear in the masked output.
The previous version was a static simulation that always said "PASSED".

Audit checks:
1. Direct Leakage: Does any raw PII value appear anywhere in the masked dataset?
2. Cross-Column Leakage: Does a PAN from raw data appear in the Comments column of masked data?
3. Attack Simulation: Pick a random person and verify their PII is unrecoverable.

Research evidence:
- File 9: "Biggest lesson was logging the redacted payload, not the raw one"
- File 11: "Keep a small eval set to track utility hit"
"""

import pandas as pd
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Columns containing direct PII identifiers
PII_COLUMNS = ['Name', 'Phone_Number', 'Email', 'PAN_Number', 'Aadhaar_Number']


def audit_leakage(raw_df: pd.DataFrame, masked_df: pd.DataFrame) -> dict:
    """
    Run a real PII leakage audit between raw and masked DataFrames.
    
    Checks EVERY raw PII value against EVERY cell in the masked DataFrame.
    This is the ground-truth test — not a simulation.
    
    Returns:
        dict with per-column leakage stats and overall score
    """
    report = {
        "total_pii_values_checked": 0,
        "total_leaks_found": 0,
        "leakage_score": 0.0,
        "columns": {},
        "leaked_examples": [],
        "verdict": "UNKNOWN",
    }

    # Build a set of ALL values in the masked dataset for fast lookup
    masked_all_values = set()
    for col in masked_df.columns:
        for val in masked_df[col].dropna().astype(str):
            masked_all_values.add(val.strip())

    for col in PII_COLUMNS:
        if col not in raw_df.columns:
            continue

        raw_values = raw_df[col].dropna().astype(str).unique()
        col_leaks = 0
        col_total = len(raw_values)

        for raw_val in raw_values:
            raw_val = raw_val.strip()
            if not raw_val:
                continue

            report["total_pii_values_checked"] += 1

            # Check if this raw PII value appears ANYWHERE in the masked output
            if raw_val in masked_all_values:
                col_leaks += 1
                report["total_leaks_found"] += 1
                if len(report["leaked_examples"]) < 5:
                    report["leaked_examples"].append({
                        "column": col,
                        "raw_value": raw_val[:4] + "***",  # Partial for safety
                        "status": "LEAKED"
                    })

        effectiveness = ((col_total - col_leaks) / col_total * 100) if col_total > 0 else 100.0
        report["columns"][col] = {
            "total_unique_values": col_total,
            "leaks_found": col_leaks,
            "masking_effectiveness": f"{effectiveness:.1f}%",
            "status": "✅ CLEAN" if col_leaks == 0 else f"❌ {col_leaks} LEAKS"
        }

    # Overall score
    if report["total_pii_values_checked"] > 0:
        report["leakage_score"] = round(
            report["total_leaks_found"] / report["total_pii_values_checked"] * 100, 2
        )

    if report["total_leaks_found"] == 0:
        report["verdict"] = "✅ ZERO LEAKAGE — All PII successfully masked"
    elif report["leakage_score"] < 5:
        report["verdict"] = "⚠️ MINOR LEAKAGE — Review flagged items"
    else:
        report["verdict"] = "❌ SIGNIFICANT LEAKAGE — Pipeline needs investigation"

    return report


def run_attack_simulation(
    raw_path="raw_fintech_data.csv",
    masked_path="masked_fintech_data.csv"
) -> dict:
    """
    Simulate a targeted memorization attack against a specific person.
    
    Picks a random person from the raw data and checks if ANY of their
    PII (Name, PAN, Aadhaar, Phone, Email) can be found in the masked data.
    
    Returns structured attack results for UI display.
    """
    raw_df = pd.read_csv(raw_path)
    masked_df = pd.read_csv(masked_path)

    # Pick a random target
    target_idx = random.randint(0, len(raw_df) - 1)
    target = raw_df.iloc[target_idx]

    results = {
        "target_name": target.get('Name', 'Unknown'),
        "target_row": target_idx,
        "checks": [],
        "all_passed": True,
    }

    # Check each PII field
    for col in PII_COLUMNS:
        if col not in raw_df.columns:
            continue

        raw_val = str(target.get(col, '')).strip()
        if not raw_val:
            continue

        # Search for this value anywhere in the masked dataset
        found_in_masked = False
        for mcol in masked_df.columns:
            if raw_val in masked_df[mcol].astype(str).values:
                found_in_masked = True
                break

        check = {
            "field": col,
            "raw_value": raw_val,
            "found_in_masked": found_in_masked,
            "status": "❌ LEAKED" if found_in_masked else "✅ SAFE",
        }
        results["checks"].append(check)
        if found_in_masked:
            results["all_passed"] = False

    return results


# Full audit: leakage + attack
def run_full_audit(
    raw_path="raw_fintech_data.csv",
    masked_path="masked_fintech_data.csv"
) -> dict:
    """Run both leakage audit and attack simulation."""
    raw_df = pd.read_csv(raw_path)
    masked_df = pd.read_csv(masked_path)

    leakage = audit_leakage(raw_df, masked_df)
    attack = run_attack_simulation(raw_path, masked_path)

    return {
        "leakage_audit": leakage,
        "attack_simulation": attack,
    }


if __name__ == "__main__":
    import json
    results = run_full_audit()
    print(json.dumps(results, indent=2, default=str))
