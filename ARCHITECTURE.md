# Architecture v3 — Multi-Layer Masking Pipeline

> **Status:** Phase 1 complete ✅ | Phase 2 (GLiNER) ready | Phase 3 (UI) pending

---

## Pipeline Architecture

```
Input DataFrame
       │
       ▼
┌──────────────────────┐
│  Phase 1: Classify   │  skip | identity | free_text | numeric | auto
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  Phase 2: REGEX      │  PAN, Aadhaar, Email, Phone, IFSC, etc.
│  (Layer 1)           │  Deterministic, 100% confidence
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  Phase 3: GLiNER     │  Names, Addresses, Organizations
│  (Layer 2)           │  Context-aware, model confidence
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  Phase 4: DP Noise   │  Laplace noise on numeric columns
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  Phase 5: Generalize │  Age → bands, Pincode → partial
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  Phase 6: VALIDATE   │  Re-scan output with whitelist
│  (Layer 3)           │  Iterative until clean (max 3)
└──────┬───────────────┘
       ▼
  Masked DataFrame + PII Manifest (JSON)
```

## File Structure

```
data-masking-pipeline/
├── config/
│   └── pii_config.yaml           # Pattern definitions, thresholds, column hints
├── core/
│   ├── __init__.py
│   ├── regex_scanner.py           # Layer 1: Compiled regex patterns
│   ├── ner_scanner.py             # Layer 2: GLiNER lazy-loaded NER
│   ├── masker.py                  # Faker-based irreversible substitution
│   ├── validator.py               # Layer 3: Output re-scanner with whitelist
│   └── pipeline.py                # Main orchestrator (6 phases)
├── models/
│   ├── __init__.py
│   └── pii_manifest.py            # Pydantic models for audit output
├── masking_engine.py              # Backward-compatible wrapper
├── app.py                         # Streamlit UI
├── data_generator.py              # Sample data generator
├── auditor.py                     # Memorization attack simulator
└── report_generator.py            # Quality metrics (KS-test, KL-div)
```

## v1 → v3 Changelog

| Aspect | v1 (Old) | v3 (New) |
|---|---|---|
| **Masking** | Reversible FPE (pyffx) | Irreversible Faker substitution |
| **Detection** | Column-name dependent | Value-based multi-layer |
| **NER** | Presidio only | GLiNER + Regex |
| **Patterns** | Hardcoded in Python | Configurable YAML |
| **Output** | DataFrame only | DataFrame + PII Manifest |
| **Validation** | None | Iterative re-scan with whitelist |
| **Numeric** | Fixed sensitivity | Dynamic sensitivity from data |
| **Audit Trail** | None | Full Pydantic manifest |
