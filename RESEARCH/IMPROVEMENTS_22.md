# 🔬 Research Notes: Anonymization Performance (22.txt)

This document extracts actionable improvements based on the "Advanced Inference" research on NER vs. LLM-based extraction.

## 1. Reversibility Robustness (The "Partial Name" Fix)
*   **The Issue**: If the LLM responds with a shortened name (e.g., "Alison" instead of "Alison Hill"), simple search-and-replace fails.
*   **Action**: 
    - We have already implemented **Partial Name Caching**.
    - **Future Upgrade**: Use fuzzy string matching (Levenshtein distance) during the unmasking phase to catch these edge cases.

## 2. Structured Generation (Outlines/Pydantic)
*   **The Idea**: Force local LLMs (like Phi-3) to respond in a strict JSON schema.
*   **Action**:
    - Research integration with the **Outlines** library.
    - This ensures that if a local LLM is used for high-precision PII detection, the output is 100% parseable by our substitution engine.

## 3. Hybrid NER + LLM Pass
*   **The Idea**: Small models are fast; large models are accurate.
*   **Action**:
    - Use GLiNER for the bulk of the work.
    - Send "Ambiguous" samples (Confidence < 0.6) to a local Phi-3 model for a second pass.
    - This provides "Best-of-both-worlds": High throughput and high precision.

## 4. Gender-Aware Substitution Validation
*   **The Idea**: Replacing a female name with a male name breaks the LLM's understanding of pronouns (she/he).
*   **Action**:
    - We have already implemented **Indian Gender Inference**.
    - **Future Upgrade**: Add a "Pronoun Matcher" that scans for "he/she" in the surrounding 5 words of a detected name to verify gender inference.

---
*Generated: May 2026*
