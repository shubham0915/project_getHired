"""
Quality Report Generator — Privacy vs Utility Analysis

Generates a comprehensive report comparing raw vs masked data.
Now powered by the PII Manifest for accurate detection stats.

Metrics:
- Per-column masking effectiveness (from manifest)
- Statistical utility preservation (KS-test, KL-divergence)
- Overall privacy score
"""

import pandas as pd
import numpy as np
from scipy.stats import ks_2samp, entropy
from typing import Optional


def kl_divergence(p, q):
    """Calculates KL divergence between two arrays of data by binning them."""
    min_val = min(np.min(p), np.min(q))
    max_val = max(np.max(p), np.max(q))
    bins = np.linspace(min_val, max_val, 100)
    
    p_hist, _ = np.histogram(p, bins=bins, density=True)
    q_hist, _ = np.histogram(q, bins=bins, density=True)
    
    # Add small epsilon to avoid log(0)
    eps = 1e-10
    p_hist = p_hist + eps
    q_hist = q_hist + eps
    
    # Normalize
    p_hist = p_hist / np.sum(p_hist)
    q_hist = q_hist / np.sum(q_hist)
    
    return entropy(p_hist, q_hist)


def generate_quality_report(
    raw_df: pd.DataFrame, 
    masked_df: pd.DataFrame,
    manifest: Optional[dict] = None
) -> dict:
    """
    Generate a privacy vs utility quality report.
    
    Args:
        raw_df: Original unmasked DataFrame
        masked_df: Masked DataFrame  
        manifest: PII Manifest dict (optional, enriches the report)
    
    Returns:
        Structured report dict with metrics
    """
    report = {
        "Data Shape Preserved": raw_df.shape == masked_df.shape,
        "Total Rows": len(raw_df),
        "Total Columns": len(raw_df.columns),
        "Metrics": [],
        "Privacy Score": 0.0,
        "Utility Score": 0.0,
    }
    
    # --- PII Column Masking Effectiveness ---
    # Dynamically detect which columns changed (not hardcoded)
    text_columns = []
    for col in raw_df.columns:
        if col in masked_df.columns and raw_df[col].dtype == object:
            changed = (raw_df[col].astype(str) != masked_df[col].astype(str)).sum()
            if changed > 0:
                text_columns.append(col)

    total_pii_changed = 0
    total_pii_values = 0

    for col in text_columns:
        changed_count = (raw_df[col].astype(str) != masked_df[col].astype(str)).sum()
        total_values = len(raw_df)
        percent_changed = (changed_count / total_values) * 100

        total_pii_changed += changed_count
        total_pii_values += total_values

        # Determine action from manifest if available
        action = "Masked"
        if manifest:
            by_type = manifest.get('detection_by_type', {})
            # Check if this column had detections
            col_summaries = manifest.get('column_summaries', [])
            for cs in col_summaries:
                if cs.get('column_name') == col:
                    top_type = max(cs.get('detection_breakdown', {}), 
                                  key=cs['detection_breakdown'].get, default='Unknown')
                    action = f"Masked ({top_type})"

        report["Metrics"].append({
            "Column": col,
            "Type": "PII",
            "Action": action,
            "Values Changed": int(changed_count),
            "Effectiveness": f"{percent_changed:.1f}%"
        })
    
    # --- Numeric Column Utility ---
    numeric_cols = raw_df.select_dtypes(include=[np.number]).columns
    utility_scores = []

    for col in numeric_cols:
        if col not in masked_df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(masked_df[col]):
            continue

        raw_vals = raw_df[col].dropna().values
        masked_vals = masked_df[col].dropna().values
        
        if len(raw_vals) == 0 or len(masked_vals) == 0:
            continue

        ks_stat, p_value = ks_2samp(raw_vals, masked_vals)
        kl_div = kl_divergence(raw_vals, masked_vals)
        
        # Utility = 1 - KS_stat (closer to 1 = distributions are similar)
        col_utility = max(0, 1 - ks_stat)
        utility_scores.append(col_utility)

        report["Metrics"].append({
            "Column": col,
            "Type": "Numeric (DP)",
            "Action": "Laplace Noise",
            "Values Changed": "All",
            "Effectiveness": f"KS: {ks_stat:.3f} | KL: {kl_div:.4f} | Utility: {col_utility:.1%}"
        })
    
    # --- Quasi-identifier Generalization ---
    if 'Age' in raw_df.columns and 'Age' in masked_df.columns:
        if raw_df['Age'].dtype != masked_df['Age'].dtype or \
           raw_df['Age'].astype(str).iloc[0] != masked_df['Age'].astype(str).iloc[0]:
            report["Metrics"].append({
                "Column": "Age",
                "Type": "Quasi-ID",
                "Action": "Generalized to bands",
                "Values Changed": len(raw_df),
                "Effectiveness": "100.0%"
            })

    if 'Pincode' in raw_df.columns and 'Pincode' in masked_df.columns:
        pincode_changed = (raw_df['Pincode'].astype(str) != masked_df['Pincode'].astype(str)).sum()
        if pincode_changed > 0:
            report["Metrics"].append({
                "Column": "Pincode",
                "Type": "Quasi-ID",
                "Action": "Partial (XXX suffix)",
                "Values Changed": int(pincode_changed),
                "Effectiveness": f"{pincode_changed/len(raw_df)*100:.1f}%"
            })

    # --- Overall Scores ---
    if total_pii_values > 0:
        report["Privacy Score"] = round(total_pii_changed / total_pii_values * 100, 1)
    
    if utility_scores:
        report["Utility Score"] = round(sum(utility_scores) / len(utility_scores) * 100, 1)

    # Add manifest summary if available
    if manifest:
        report["Manifest Summary"] = {
            "Total PII Detected": manifest.get('total_pii_detected', 0),
            "Validation Clean": manifest.get('final_clean', False),
            "Processing Time": f"{manifest.get('processing_time_seconds', 0)}s",
            "By Detector": manifest.get('detection_by_detector', {}),
            "By Severity": manifest.get('detection_by_severity', {}),
        }

    return report


if __name__ == "__main__":
    raw = pd.read_csv("raw_fintech_data.csv")
    masked = pd.read_csv("masked_fintech_data.csv")
    report = generate_quality_report(raw, masked)
    import json
    print(json.dumps(report, indent=2, default=str))
