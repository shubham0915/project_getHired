"""
Test: Content-First Column Classification (Schema-Agnostic)

Proves that the pipeline detects PII by analyzing cell VALUES,
not column headers. A column named 'col_A' with PANs must be
detected and masked — a column named 'gender' with M/F values
must be auto-skipped.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

from core.pipeline import MaskingPipeline


def test_content_first_classification():
    """
    Build a DataFrame with deliberately misleading column names.
    The pipeline MUST still detect and mask PII based on content.
    """
    print("\n" + "=" * 70)
    print("TEST: Content-First Column Classification (Schema-Agnostic)")
    print("=" * 70)

    df = pd.DataFrame({
        "col_A": [  # Actually contains PANs
            "ABCDE1234F", "FGHIJ5678K", "KLMNO9012P", "QRSTU3456V", "WXYZA7890B"
        ],
        "col_B": [  # Actually contains phone numbers
            "9876543210", "8765432109", "7654321098", "6543210987", "9012345678"
        ],
        "col_C": [  # Actually contains emails
            "raj@gmail.com", "priya@yahoo.co.in", "amit@outlook.com",
            "neha@proton.me", "vikram@hotmail.com"
        ],
        "col_D": [  # Actually contains ISO DOBs
            "1990-05-15", "1985-11-23", "2001-03-08", "1978-07-30", "1995-12-01"
        ],
        "col_E": [  # Categorical (should be auto-skipped)
            "Active", "Inactive", "Active", "Pending", "Active"
        ],
        "col_F": [  # Free text with embedded PII
            "Customer Ramesh called about PAN XYZAB1234C and phone 9111222333",
            "Email from priya (neha.sharma@gmail.com) regarding FD maturity",
            "User reported issue with account 1234567890123 at SBIN0001234",
            "Complaint: DOB 1995-06-20 is wrong in records, phone 8000111222",
            "Please update PAN ABCDE9999F for user, Aadhaar last 4 = 3197",
        ],
        "col_G": [  # Numeric amounts (should get DP, not regex)
            10000, 25000, 50000, 75000, 100000
        ],
        "col_H": [  # Boolean/categorical
            True, False, True, True, False
        ],
    })

    print(f"\nInput DataFrame: {len(df)} rows x {len(df.columns)} columns")
    print(f"Column names: {list(df.columns)}")
    print("\nSample values per column:")
    for col in df.columns:
        print(f"  {col}: {df[col].iloc[0]}")

    pipeline = MaskingPipeline(enable_ner=False)
    masked_df, manifest = pipeline.process(df)

    print("\n" + "-" * 70)
    print("RESULTS:")
    print("-" * 70)

    results = {}

    pan_masked = all(masked_df["col_A"].iloc[i] != df["col_A"].iloc[i] for i in range(len(df)))
    results["col_A (PANs)"] = "MASKED" if pan_masked else "LEAKED"

    phone_masked = all(masked_df["col_B"].iloc[i] != df["col_B"].iloc[i] for i in range(len(df)))
    results["col_B (Phones)"] = "MASKED" if phone_masked else "LEAKED"

    email_masked = all(masked_df["col_C"].iloc[i] != df["col_C"].iloc[i] for i in range(len(df)))
    results["col_C (Emails)"] = "MASKED" if email_masked else "LEAKED"

    dob_masked = all(masked_df["col_D"].iloc[i] != df["col_D"].iloc[i] for i in range(len(df)))
    results["col_D (ISO DOBs)"] = "MASKED" if dob_masked else "LEAKED"

    cat_preserved = all(masked_df["col_E"].iloc[i] == df["col_E"].iloc[i] for i in range(len(df)))
    results["col_E (Categorical)"] = "PRESERVED" if cat_preserved else "INCORRECTLY MODIFIED"

    text_modified = any(masked_df["col_F"].iloc[i] != df["col_F"].iloc[i] for i in range(len(df)))
    results["col_F (Free Text PII)"] = "MASKED" if text_modified else "LEAKED"

    amounts_noisy = all(masked_df["col_G"].iloc[i] != df["col_G"].iloc[i] for i in range(len(df)))
    results["col_G (Amounts/DP)"] = "DP APPLIED" if amounts_noisy else "No noise (possible)"

    bool_preserved = all(str(masked_df["col_H"].iloc[i]) == str(df["col_H"].iloc[i]) for i in range(len(df)))
    results["col_H (Boolean)"] = "PRESERVED" if bool_preserved else "INCORRECTLY MODIFIED"

    for col_desc, status in results.items():
        symbol = "✅" if status in ("MASKED", "PRESERVED", "DP APPLIED") else "❌"
        print(f"  {symbol} {col_desc}: {status}")

    print(f"\nManifest: {manifest.total_pii_detected} PII detected, {manifest.total_pii_masked} masked")
    print(f"Validation: {'CLEAN' if manifest.final_clean else 'NEEDS REVIEW'}")

    passes = sum(1 for s in results.values() if s in ("MASKED", "PRESERVED", "DP APPLIED"))
    fails = sum(1 for s in results.values() if s in ("LEAKED", "INCORRECTLY MODIFIED"))
    print(f"\n{'=' * 70}")
    print(f"SCORE: {passes}/{len(results)} passed, {fails} failed")
    if fails == 0:
        print("ALL TESTS PASSED — Pipeline is truly schema-agnostic!")
    print("=" * 70)


def test_name_detection():
    """
    THE CRITICAL TEST: A column called 'col_X' containing Indian names.
    Names have no regex pattern. Without NER/GLiNER, the ONLY way to
    detect them is the name probe heuristic using our 100 curated names.
    """
    print("\n" + "=" * 70)
    print("TEST: Name Detection Without NER (Content-Based)")
    print("=" * 70)

    names = [
        "Rajesh Sharma", "Priya Patel", "Amit Verma", "Neha Gupta",
        "Vikram Singh", "Anjali Reddy", "Rohan Kapoor", "Sneha Nair",
        "Karthik Menon", "Deepika Iyer", "Rahul Desai", "Pooja Joshi",
        "Arjun Mehta", "Kavya Rao", "Sanjay Mishra", "Divya Thakur",
        "Ganesh Patil", "Simran Kaur", "Manish Tiwari", "Aditi Kulkarni",
    ]
    df = pd.DataFrame({
        "col_X": names,
        "col_Y": [f"Category_{i % 4}" for i in range(20)],
    })

    print(f"\nInput: {len(df)} rows, column 'col_X' contains Indian names")
    print(f"Sample: {names[:5]}")
    print("NER/GLiNER: DISABLED (testing pure content-based detection)\n")

    pipeline = MaskingPipeline(enable_ner=False)
    col_types = pipeline._classify_columns(df)

    print(f"\nClassification results:")
    for col, ctype in col_types.items():
        print(f"  {col} -> {ctype}")

    masked_df, manifest = pipeline.process(df)

    names_masked = sum(
        1 for i in range(len(df))
        if masked_df["col_X"].iloc[i] != df["col_X"].iloc[i]
    )
    cat_preserved = all(
        masked_df["col_Y"].iloc[i] == df["col_Y"].iloc[i]
        for i in range(len(df))
    )

    print(f"\nResults:")
    col_x_type = col_types.get("col_X", "unknown")
    print(f"  col_X classified as: {col_x_type} -> {'✅ identity' if col_x_type == 'identity' else '❌ MISSED'}")
    print(f"  col_X names masked:  {names_masked}/{len(df)} -> {'✅' if names_masked == len(df) else '❌'}")
    print(f"  col_Y preserved:     {'✅' if cat_preserved else '❌'}")

    print(f"\nManifest: {manifest.total_pii_detected} PII detected, {manifest.total_pii_masked} masked")

    if col_x_type == "identity" and names_masked == len(df) and cat_preserved:
        print("\n🎉 Name detection works WITHOUT NER — even with misleading column name!")
    else:
        print("\n⚠️  Name detection needs improvement")
    print("=" * 70)


def test_hackathon_data_classification():
    """
    Test classification on the actual hackathon support_tickets_unstructured.csv.
    """
    print("\n" + "=" * 70)
    print("TEST: Hackathon Data Auto-Classification")
    print("=" * 70)

    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "details", "Builder Pack", "01_synthetic_data", "support_tickets_unstructured.csv"
    )

    if not os.path.exists(csv_path):
        print(f"Hackathon data not found at: {csv_path}")
        return

    df = pd.read_csv(csv_path)
    print(f"\nLoaded: {len(df)} rows x {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")

    pipeline = MaskingPipeline(enable_ner=False)
    col_types = pipeline._classify_columns(df)

    print("\nAuto-classification results:")
    for col, ctype in col_types.items():
        print(f"  {col:25s} -> {ctype}")

    print("\nExpectation checks:")
    ft_type = col_types.get("free_text", "MISSING")
    is_ft_ok = ft_type in ("free_text", "auto")
    print(f"  free_text -> {ft_type}: {'✅' if is_ft_ok else '❌ CRITICAL: PII column would be skipped!'}")

    for cat_col in ["channel", "priority", "category", "resolved", "language"]:
        ct = col_types.get(cat_col, "MISSING")
        is_ok = ct == "skip"
        print(f"  {cat_col:15s} -> {ct}: {'✅ auto-skipped' if is_ok else 'will be scanned (harmless but slow)'}")


if __name__ == "__main__":
    test_content_first_classification()
    test_name_detection()
    test_hackathon_data_classification()
