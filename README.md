# 🛡️ Blostem Data Masking Pipeline v4

Enterprise-grade, DPDP-compliant multi-layer PII detection and masking pipeline tailored for Indian fintech data.

## 🌟 Key Features

1. **Multi-Layer Architecture**:
   - **Layer 1 (Regex)**: Deterministic high-speed matching for structured PII (PAN, Aadhaar, Phone, Email, including obfuscated patterns like `jane (at) example (dot) com`).
   - **Layer 2 (GLiNER NER)**: Context-aware zero-shot detection for unstructured free-text (Names, Addresses). Supports multiple models including `nvidia/gliner-PII`.
   - **Layer 3 (Validation)**: Output re-scanning to guarantee zero leakage.

2. **Irreversible Masking (Faker-based)**:
   - Full substitution of sensitive values with realistic synthetic data.
   - **Deterministic Session Cache**: A given identity (e.g. `Priya Sharma`) always maps to the same synthetic identity within a run to preserve referential integrity.
   - **Smart Partial-Name Matching**: The engine intelligently splits full names. If "Rajesh Sharma" becomes "Krishna Choudhury", a later isolated mention of "rajesh" will automatically become "Krishna", even in reverse-order text processing!
   - **Gender-Aware Indian Names**: Heuristic gender inference ensures Indian male names map to Indian male names, and female to female.

3. **Differential Privacy**:
   - Numeric columns (like `Amount`, `Balance`) are protected using Laplace noise (ε=1.0) to prevent targeted numerical linkage attacks while preserving overall statistical distribution.

4. **Quasi-Identifier Protection (LLM-Optimized)**:
   - `Age` is protected using Differential Privacy (Laplace noise) rounded to the nearest integer. This maintains perfect natural age distributions instead of clunky text bands.
   - `Pincode` is fully substituted with completely valid synthetic Indian Pincodes using the deterministic session cache, ensuring LLM fine-tuning datasets look 100% natural.

5. **Confidence-Based Routing**:
   - High confidence (>0.8) → Auto-redact.
   - Medium confidence (0.4-0.8) → Mask and flag for review.
   - Low confidence (<0.4) → Log only for audit.

6. **Real-time Leakage Auditor & Attack Simulator**:
   - Ground-truth evaluation cross-checking raw PII against masked output.
   - Simulates targeted LLM memorization attacks to prove privacy.

---

## 📂 Architecture & Workflows

### 1. Complete System Overview
This diagram shows the high-level flow of data from ingestion to final secure output.

```mermaid
flowchart TD
    subgraph Input
        A1[Structured Data <br/> CSV / JSON Paste] --> B
        A2[Unstructured Text <br/> Chat Logs / Emails] --> B
    end
    
    B{Data Type Router} -->|Structured| C[DataFrame Processing]
    B -->|Unstructured| D[Text Masking]
    
    C --> E[Multi-Layer Masking Engine]
    D --> E
    
    E --> F[Phase 4: Differential Privacy <br/> & Quasi-Identifiers]
    F --> G[Phase 5: Validation Scanner <br/> & Leakage Audit]
    
    G --> H[Masked Output <br/> & PII Manifest]
```

### 2. Inner Workings: Multi-Layer Detection Engine
How the pipeline actually detects and decides what to do with PII.

```mermaid
flowchart LR
    A[Raw Cell / Text] --> B[Layer 1: Regex Scanner]
    B --> C{Regex Match?}
    C -->|Yes| D[Mask via Faker]
    C -->|No| E[Layer 2: GLiNER NER]
    E --> F{Confidence Score}
    F -->|>= 0.8| G[Auto-Redact]
    F -->|0.4 - 0.79| H[Review Queue]
    F -->|< 0.4| I[Log Only]
    
    G --> J[Pass to Cache]
```

### 3. Inner Workings: Referential Integrity & Caching
How the system handles complex edge cases like case-sensitivity and partial name matches without losing context.

```mermaid
flowchart TD
    A[Detected Entity: 'Rajesh Sharma'] --> B[Length-Based Pre-Seeding]
    B --> C[Generate Synthetic: 'Krishna Choudhury']
    C --> D[Cache Full String]
    D --> E[Split & Cache Partials]
    E --> F["Cache 'rajesh' -> 'Krishna'"]
    E --> G["Cache 'sharma' -> 'Choudhury'"]
    
    H[Later Detected: 'rajesh'] --> I[Lowercase Cache Lookup]
    I --> J[Return 'Krishna' instantly]
```

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.9+
- Virtual Environment

### Installation

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Mac/Linux
# venv\Scripts\activate   # On Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Download GLiNER Model for NER
# Without this, the pipeline gracefully falls back to Regex + Column-based rules.
```

## 🎮 Running the Dashboard

```bash
streamlit run app.py
```

### Demo Guide

1. **Ingest Data**: 
   - **Upload** a raw CSV file.
   - **Paste** raw JSON/CSV directly into the new sidebar text area (e.g. `{"Name": "Rajesh", "Amount": 5000}`).
   - **Generate** a sample synthetic dataset.
2. **Toggle NER**: Check "Enable GLiNER NER" to use the ML model (requires download on first run) or leave unchecked for Regex-only + fallback mode.
3. **Select Model**: Choose between `urchade/gliner_multi_pii-v1` (multilingual) or `nvidia/gliner-PII` (optimized for English PII).
4. **Run Pipeline**: Click "Run Masking Pipeline".
5. **Explore Tabs**:
   - **Tab 1: Raw Data**: See the generated sensitive data.
   - **Tab 2: Masked Data**: Export as CSV, JSONL, Parquet, or JSON Manifest. Observe Differential Privacy in numeric columns!
   - **Tab 3: PII Manifest**: View detection charts, validation passes, and breakdown by severity.
   - **Tab 4: Utility Report**: Compare raw vs. masked distribution using Kernel Density Estimation (KDE).
   - **Tab 5: Leakage Audit**: Run the "Targeted Attack Simulation" to prove that PII is unrecoverable.
   - **Tab 6: Text Masking**: Paste free-text logs and see unstructured PII masked in real-time.

## ⚙️ Configuration
Add or modify regex patterns, GLiNER labels, and routing thresholds in `config/pii_config.yaml` without changing core Python code.
