# 🔬 Research Notes: LangChain Experimental Masking (24.txt)

This document extracts actionable improvements from the "LangChain JS Masking" research video.

## 1. Professional Terminology: "Rehydration"
*   **The Idea**: In the LangChain ecosystem, the process of unmasking/de-anonymizing data is called **Rehydration**.
*   **Action**: 
    - Update the UI/README to use the term "Rehydration Engine" instead of just "Unmasker." This aligns the project with standard AI framework terminology.

## 2. "Double-Masking" Prevention (Regex Hygiene)
*   **The Issue**: The speaker found that a random hash (e.g., `EMAIL_8291`) was being masked *again* by a greedy Bank Account regex because it contained digits.
*   **Action**: 
    - Implement an **Exclusion Logic**: Once a string has been masked (enclosed in a specific pattern or added to the manifest), it should be skipped by subsequent regex layers.

## 3. Streaming Support (Real-Time Masking)
*   **The Idea**: Modern AI apps use streaming (token-by-token).
*   **Action**:
    - Research how to implement a **Stream-Safe Masker**. This would process a generator of strings and mask them on-the-fly before they are displayed in a chat UI.

## 4. Verification via LangSmith
*   **The Idea**: Prove that no PII ever leaves the local environment by showing the "Input" logs in LangSmith.
*   **Action**:
    - Add a "Security Proof" section to the Demo Guide.
    - Explain how developers can verify our pipeline by inspecting the trace in LangSmith, proving that the raw PII was swapped for synthetic data *before* the API call.

## 5. UI Integration (The "Chat Summary" Demo)
*   **The Idea**: A common real-world use case is summarizing a long customer chat while keeping it anonymous.
*   **Action**:
    - Add a "Customer Support Demo" button in the **Text Masking tab**.
    - This button will load a sample chat history containing PII, mask it, and then show a "Summary" that is safe for a manager to read.

---
*Generated: May 2026*
