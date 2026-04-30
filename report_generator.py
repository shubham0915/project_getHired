import pandas as pd
import numpy as np
from scipy.stats import ks_2samp, entropy

def kl_divergence(p, q):
    """Calculates KL divergence between two arrays of data by binning them."""
    # Create histogram bins
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

def generate_quality_report(raw_df: pd.DataFrame, masked_df: pd.DataFrame) -> dict:
    report = {
        "Data Shape Preserved": raw_df.shape == masked_df.shape,
        "Total Rows": len(raw_df),
        "Metrics": []
    }
    
    # Check text redaction/substitution
    text_columns = ['Name', 'Phone_Number', 'Email', 'PAN_Number', 'Aadhaar_Number']
    for col in text_columns:
        if col in raw_df.columns and col in masked_df.columns:
            # Count how many values changed
            changed_count = (raw_df[col] != masked_df[col]).sum()
            percent_changed = (changed_count / len(raw_df)) * 100
            report["Metrics"].append({
                "Column": col,
                "Type": "Text (PII)",
                "Action": "Substituted/Masked",
                "Effectiveness": f"{percent_changed:.1f}% changed"
            })
            
    # Check structure preservation
    if 'Amount' in raw_df.columns and 'Amount' in masked_df.columns:
        raw_amt = raw_df['Amount'].dropna().values
        masked_amt = masked_df['Amount'].dropna().values
        
        # KS Test (values closer to 0 mean distributions are identical)
        ks_stat, p_value = ks_2samp(raw_amt, masked_amt)
        
        # KL Divergence (values closer to 0 mean identical)
        kl_div = kl_divergence(raw_amt, masked_amt)
        
        report["Metrics"].append({
            "Column": "Amount",
            "Type": "Numeric (DP)",
            "Action": "Laplace Noise",
            "Effectiveness": f"KS-Stat: {ks_stat:.3f} | KL-Div: {kl_div:.4f}"
        })
        
    if 'Account_Number' in raw_df.columns and 'Account_Number' in masked_df.columns:
        # Check uniqueness preservation
        raw_unique = raw_df['Account_Number'].nunique()
        masked_unique = masked_df['Account_Number'].nunique()
        report["Metrics"].append({
            "Column": "Account_Number",
            "Type": "Identifier",
            "Action": "Hashed",
            "Effectiveness": f"Unique Counts: {raw_unique} -> {masked_unique}"
        })
        
    return report

if __name__ == "__main__":
    raw = pd.read_csv("raw_fintech_data.csv")
    masked = pd.read_csv("masked_fintech_data.csv")
    report = generate_quality_report(raw, masked)
    import json
    print(json.dumps(report, indent=2))
