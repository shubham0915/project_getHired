# 🔬 Research Notes: Anonymizing for RAG (23.txt)

This document extracts actionable improvements based on the LangChain + Microsoft Presidio integration patterns.

## 1. RAG-Ready Chunks
*   **The Idea**: Anonymize documents *before* they are embedded into a Vector Store.
*   **Action**:
    - Add a feature to "Chunk & Scrub." 
    - This breaks down long PDFs/Documents into paragraphs, masks them, and then stores them in a format ready for OpenAI embeddings.
- **Benefit**: Ensures the Knowledge Base is PII-free.

## 2. Custom Pattern Recognizers (Faker Operators)
*   **The Idea**: Add support for region-specific or industry-specific patterns (e.g., Polish ID).
*   **Action**:
    - Update `pii_config.yaml` to allow users to define both a **Detection Regex** and a **Faker Template**.
    - Example: `label: POLISH_ID, pattern: [A-Z]{3}[0-9]{6}, faker_template: {{random_letters(3)}}{{random_digits(6)}}`.

## 3. LangChain "Runnable" Integration
*   **The Idea**: Make the pipeline a native part of the LangChain ecosystem.
*   **Action**:
    - Export the pipeline as a **LangChain Transformer**.
    - This allows other developers to simply add `.pipe(masking_pipeline)` to their AI chains.

## 4. Multi-Instance Mapping (Indexing)
*   **The Idea**: Handle cases where the same PII type appears multiple times (Email 1, Email 2).
*   **Action**:
    - We have already implemented deterministic hashing for this.
    - **Verification**: Ensure that `email_address_1` and `email_address_2` mapping is consistent throughout the document.

---
*Generated: May 2026*
