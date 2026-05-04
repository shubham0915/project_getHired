"""
Masking Engine — Backward-Compatible Wrapper

This module wraps the new multi-layer pipeline (core/pipeline.py) while
maintaining the same API that app.py expects.

DEPRECATED: Direct use of this module is deprecated.
Use `from core.pipeline import MaskingPipeline` instead.
"""

import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_dataframe(df: pd.DataFrame, enable_ner: bool = True) -> pd.DataFrame:
    """
    Process a DataFrame through the multi-layer masking pipeline.
    
    This wrapper maintains backward compatibility with app.py by returning
    only the masked DataFrame. The PII Manifest is stored as an attribute
    on the returned DataFrame for optional access.
    
    Args:
        df: Raw DataFrame with potential PII
        enable_ner: Whether to enable GLiNER NER (Layer 2).
                    Set to False for faster processing on structured-only data.
        
    Returns:
        Masked DataFrame (with manifest attached as df.attrs['pii_manifest'])
    """
    try:
        from core.pipeline import MaskingPipeline
        pipeline = MaskingPipeline(enable_ner=enable_ner)
        masked_df, manifest = pipeline.process(df)
        
        # Attach manifest to DataFrame for optional access
        masked_df.attrs['pii_manifest'] = manifest.to_safe_dict()
        masked_df.attrs['pii_manifest_obj'] = manifest
        
        return masked_df
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        logger.info("Falling back to basic column-name masking...")
        return _fallback_masking(df)


def _fallback_masking(df: pd.DataFrame) -> pd.DataFrame:
    """
    Minimal fallback masking if the new pipeline fails.
    Uses basic Faker substitution on known column names.
    """
    from faker import Faker
    import random
    import string
    
    fake = Faker('en_IN')
    masked_df = df.copy()
    
    # Simple column-name-based masking
    if 'Name' in masked_df.columns:
        masked_df['Name'] = masked_df['Name'].apply(lambda x: fake.name() if pd.notna(x) else x)
    if 'Phone_Number' in masked_df.columns:
        masked_df['Phone_Number'] = masked_df['Phone_Number'].apply(lambda x: fake.phone_number() if pd.notna(x) else x)
    if 'Email' in masked_df.columns:
        masked_df['Email'] = masked_df['Email'].apply(lambda x: fake.email() if pd.notna(x) else x)
    if 'PAN_Number' in masked_df.columns:
        masked_df['PAN_Number'] = masked_df['PAN_Number'].apply(
            lambda x: f"{''.join(random.choices(string.ascii_uppercase, k=5))}{random.randint(1000,9999)}{random.choice(string.ascii_uppercase)}" if pd.notna(x) else x
        )
    if 'Aadhaar_Number' in masked_df.columns:
        masked_df['Aadhaar_Number'] = masked_df['Aadhaar_Number'].apply(
            lambda x: ''.join(random.choices(string.digits, k=12)) if pd.notna(x) else x
        )
    if 'Account_Number' in masked_df.columns:
        masked_df['Account_Number'] = masked_df['Account_Number'].apply(
            lambda x: ''.join(random.choices(string.digits, k=len(str(x)))) if pd.notna(x) else x
        )
    if 'Age' in masked_df.columns:
        masked_df['Age'] = masked_df['Age'].apply(lambda x: "26-35" if pd.notna(x) else x)
    if 'Pincode' in masked_df.columns:
        masked_df['Pincode'] = masked_df['Pincode'].apply(
            lambda x: str(x)[:3] + "XXX" if pd.notna(x) else x
        )
    if 'Amount' in masked_df.columns:
        noise = np.random.laplace(0, 1000, len(masked_df))
        masked_df['Amount'] = (masked_df['Amount'] + noise).round(2).clip(lower=0)
    
    return masked_df


if __name__ == "__main__":
    df = pd.read_csv("raw_fintech_data.csv")
    masked_df = process_dataframe(df, enable_ner=False)  # Start without NER for speed
    masked_df.to_csv("masked_fintech_data.csv", index=False)
    
    # Print manifest summary if available
    if 'pii_manifest' in masked_df.attrs:
        import json
        manifest = masked_df.attrs['pii_manifest']
        print("\n=== PII MANIFEST SUMMARY ===")
        print(f"Total PII Detected: {manifest.get('total_pii_detected', 0)}")
        print(f"Detection by Type: {json.dumps(manifest.get('detection_by_type', {}), indent=2)}")
        print(f"Detection by Severity: {json.dumps(manifest.get('detection_by_severity', {}), indent=2)}")
        print(f"Validation Clean: {manifest.get('final_clean', False)}")
        print(f"Processing Time: {manifest.get('processing_time_seconds', 0)}s")
    
    print("\nSaved masked_fintech_data.csv")
