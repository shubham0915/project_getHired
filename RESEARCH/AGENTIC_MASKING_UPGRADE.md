# 🚀 Future Upgrade: Agentic Masking & Multi-Role PETs (2026 Frontier)

This document outlines the theoretical framework and implementation plan for upgrading the current pipeline to the **"2026 Agentic Masking"** standard.

## 🧠 What is Agentic Masking?
Agentic Masking is a middleware layer that sits between an AI Agent (or User) and a sensitive database. Instead of a "one-size-fits-all" redaction, the pipeline dynamically masks data based on the **User Role** and their specific **"Need-to-Know"** at that exact moment.

## 🛠️ The 6 Privacy-Enhancing Technologies (PETs)
As of 2026, the industry standard relies on these six pillars. Our current status is tracked below:

| Technique | Status | Description |
| :--- | :--- | :--- |
| **Semantic Masking** | ✅ **Active** | Using **GLiNER (Zero-Shot NER)** to detect PII based on context (e.g., recipient names in chat logs) rather than just patterns. |
| **Differential Privacy** | ✅ **Active** | Using **Laplace Noise (ε=1.0)** for numeric columns to prevent re-identification while preserving statistical trends. |
| **Synthetic Data 2.0** | ✅ **Active** | Using **Salted HMAC-SHA256 Seeds** for deterministic Faker substitution. Ensures irreversible but consistent mapping across tables. |
| **FPE / Tokenization** | ❌ *Skipped* | Intentionally avoided due to "Master Key" risk. Replaced by irreversible synthetic substitution for higher security. |
| **Agentic Masking** | ⏳ *Planned* | Dynamic masking based on **User Roles** (Manager vs. Scientist vs. Public) to prevent prompt injection. |
| **Homomorphic Encr.** | 🔬 *Future* | Performing calculations on encrypted data without ever decrypting it (High-stakes fintech). |

## 🎯 Proposed "Agentic" Implementation
To demonstrate this on Demo Day, we will add a **Role-Based Access Control (RBAC)** simulation to the Streamlit dashboard:

### 1. User Roles
*   **Data Scientist**: Needs high data utility for ML training. 
    *   *Strategy*: Synthetic Names + Low-Noise Differential Privacy.
*   **Compliance Auditor**: Needs to verify privacy without seeing data.
    *   *Strategy*: Full Redaction `[REDACTED]` + High-Noise Differential Privacy.
*   **Manager / Operations**: Needs to see the "shape" of the business.
    *   *Strategy*: Partially Masked (e.g., First Name only) + Exact Aggregates.

### 2. Implementation Logic
The `PIIMasker` and `DifferentialPrivacy` engines will receive a `user_role` parameter.
```python
def mask_by_role(value, role):
    if role == "Data Scientist":
        return faker.name()  # High utility
    if role == "Public":
        return "[REDACTED]"   # Maximum privacy
```

## 📈 Security vs. Utility Matrix (2026)
| Technique | Security | Utility | Best For |
| :--- | :--- | :--- | :--- |
| **Synthetic Data** | Ultra High | High | Testing & ML Training |
| **Differential Privacy** | Mathematical | Medium | Aggregated Analytics |
| **FPE / Tokenization** | High | Ultra High | Operational Processing |
| **Semantic Masking** | High | High | LLM / RAG Pipelines |
| **Homomorphic Encr.** | Maximum | High | Cross-border Analytics |

---
*Created during the Blostem "Hack to the Future" Sprint - May 2026*
