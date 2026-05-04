"""
Pipeline Orchestrator — Multi-Layer PII Detection & Masking Engine

This is the main entry point for the masking pipeline. It orchestrates:
1. Layer 1 (Regex): Deterministic pattern matching for structured PII
2. Layer 2 (GLiNER): Context-aware NER for unstructured PII
3. Masking: Irreversible Faker-based substitution
4. Layer 3 (Validation): Output re-scanning to catch leaks
5. Manifest: Structured audit output

Architecture validated by:
- Research File 7: Multi-layer stacking (Protecto production pattern)
- Research File 15: Three-tier confidence routing
- Research File 17: Wealthsimple sequential scrubber chain
- Research File 19: AlfaBank hackathon proxy-layer architecture
"""

import pandas as pd
import numpy as np
import yaml
import os
import time
import logging
from typing import Tuple, Optional, Dict, List

from core.regex_scanner import RegexScanner
from core.ner_scanner import NERScanner
from core.masker import PIIMasker
from core.validator import OutputValidator
from models.pii_manifest import (
    PIIManifest, PIIDetection, DetectorType, Severity
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "pii_config.yaml")

def _load_config() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


class MaskingPipeline:
    """
    Enterprise-grade multi-layer PII detection and masking pipeline.
    
    Usage:
        pipeline = MaskingPipeline()
        masked_df, manifest = pipeline.process(raw_df)
    """

    def __init__(self, config_path: Optional[str] = None, enable_ner: bool = True, gliner_model_override: Optional[str] = None):
        """
        Initialize the masking pipeline.
        
        Args:
            config_path: Path to pii_config.yaml (uses default if None)
            enable_ner: Whether to enable GLiNER NER (Layer 2)
            gliner_model_override: Optional GLiNER model name to override the config
        """
        self.config = _load_config() if config_path is None else yaml.safe_load(open(config_path))
        self.enable_ner = enable_ner

        if gliner_model_override:
            if "global" not in self.config:
                self.config["global"] = {}
            self.config["global"]["gliner_model"] = gliner_model_override

        # Initialize layers
        self.regex_scanner = RegexScanner(self.config)
        self.masker = PIIMasker()
        self.ner_scanner = NERScanner(self.config) if enable_ner else None
        
        # Config shortcuts
        self.column_hints = self.config.get("column_hints", {})
        self.skip_columns = set(self.column_hints.get("skip_columns", []))
        self.free_text_cols = set(self.column_hints.get("free_text_columns", []))
        self.numeric_cols = set(self.column_hints.get("numeric_columns", []))
        self.identity_cols = set(self.column_hints.get("identity_columns", []))

    def process(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, PIIManifest]:
        """
        Main entry point: Process a DataFrame through the full masking pipeline.
        
        Args:
            df: Raw DataFrame with potential PII
            
        Returns:
            Tuple of (masked DataFrame, PII Manifest)
        """
        start_time = time.time()
        
        # Initialize manifest
        manifest = PIIManifest(
            total_rows=len(df),
            total_columns=len(df.columns),
        )

        # Reset masker cache for this session (deterministic within session)
        self.masker.reset_cache()
        
        # Work on a copy
        masked_df = df.copy()
        
        logger.info(f"Starting masking pipeline: {len(df)} rows × {len(df.columns)} columns")
        logger.info(f"Layers enabled: Regex=True, NER={self.enable_ner}")

        # ----- PHASE 1: Column Classification -----
        col_types = self._classify_columns(masked_df)
        logger.info(f"Column classification: {col_types}")

        # ----- PHASE 2: Layer 1 — Regex Scan + Mask -----
        masked_df, manifest = self._apply_regex_layer(masked_df, manifest, col_types)

        # ----- PHASE 2.5: Identity Column Fallback (Names) -----
        # When GLiNER is unavailable, names have no regex pattern to catch them.
        # This fallback ensures identity_columns (e.g. Name) are always masked
        # using our gender-aware Indian name generator.
        masked_df, manifest = self._apply_identity_fallback(masked_df, manifest, col_types)

        # ----- PHASE 3: Layer 2 — GLiNER NER Scan + Mask -----
        if self.enable_ner and self.ner_scanner is not None:
            masked_df, manifest = self._apply_ner_layer(masked_df, manifest, col_types)

        # ----- PHASE 4: Numeric Column Protection -----
        masked_df = self._protect_numeric_columns(masked_df, col_types)

        # ----- PHASE 5: Quasi-Identifier Generalization -----
        masked_df = self._generalize_quasi_identifiers(masked_df)

        # ----- PHASE 6: Layer 3 — Output Validation -----
        validator = OutputValidator(
            max_passes=self.config.get("global", {}).get("max_validation_passes", 3)
        )
        masked_df, manifest = validator.validate_dataframe(
            masked_df, manifest,
            skip_columns=list(self.skip_columns | self.numeric_cols),
            known_masked_values=self.masker.generated_values
        )

        # ----- FINALIZE -----
        elapsed = time.time() - start_time
        manifest.processing_time_seconds = round(elapsed, 2)
        manifest.build_column_summaries()

        logger.info(
            f"Pipeline complete in {elapsed:.2f}s: "
            f"{manifest.total_pii_detected} PII detected, "
            f"{manifest.total_pii_masked} masked, "
            f"validation={'CLEAN' if manifest.final_clean else 'NEEDS REVIEW'}"
        )

        return masked_df, manifest

    # -----------------------------------------------------------------------
    # Phase 1: Column Classification
    # -----------------------------------------------------------------------

    def _classify_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Classify each column into a processing category.
        
        Categories:
        - skip: Don't process (Transaction_ID, Status, Date)
        - identity: Known PII columns (Name, PAN, Aadhaar) → Regex priority
        - free_text: Free text columns (Comments) → GLiNER + Regex
        - numeric: Numeric columns (Amount) → Differential Privacy
        - auto: Unknown → value-based detection
        """
        col_types = {}
        
        for col in df.columns:
            col_lower = col.lower()
            
            if col in self.skip_columns or col_lower in {c.lower() for c in self.skip_columns}:
                col_types[col] = "skip"
            elif col in self.identity_cols or col_lower in {c.lower() for c in self.identity_cols}:
                col_types[col] = "identity"
            elif col in self.free_text_cols or col_lower in {c.lower() for c in self.free_text_cols}:
                col_types[col] = "free_text"
            elif col in self.numeric_cols or col_lower in {c.lower() for c in self.numeric_cols}:
                col_types[col] = "numeric"
            else:
                # Auto-detect: check if column is numeric
                if pd.api.types.is_numeric_dtype(df[col]):
                    col_types[col] = "numeric"
                else:
                    col_types[col] = "auto"  # Will use value-based detection

        return col_types

    # -----------------------------------------------------------------------
    # Phase 2: Layer 1 — Regex
    # -----------------------------------------------------------------------

    def _apply_regex_layer(
        self, df: pd.DataFrame, manifest: PIIManifest, col_types: Dict[str, str]
    ) -> Tuple[pd.DataFrame, PIIManifest]:
        """Apply Layer 1 regex scanning and masking to all applicable columns."""
        
        logger.info("--- Layer 1: Regex Scanner ---")
        
        for col in df.columns:
            ctype = col_types.get(col, "auto")
            if ctype in ("skip", "numeric"):
                continue

            detection_count = 0
            for idx, value in df[col].items():
                if pd.isna(value) or not isinstance(value, str):
                    continue

                matches = self.regex_scanner.scan_value(str(value), column_name=col)
                
                # Intelligent Discovery: Filter matches using checksums (Gap 1 in user text)
                valid_matches = [
                    m for m in matches 
                    if self._validate_with_checksum(m.matched_text, m.pattern_name)
                ]
                
                if not valid_matches:
                    continue

                # Replace each match in the cell value
                masked_value = str(value)
                for match in sorted(valid_matches, key=lambda m: m.start, reverse=True):
                    replacement = self.masker.mask(match.matched_text, match.faker_method)
                    masked_value = (
                        masked_value[:match.start] + replacement + masked_value[match.end:]
                    )
                    
                    # Record detection in manifest
                    manifest.add_detection(PIIDetection(
                        entity_type=match.pattern_name,
                        original_value="[REDACTED_FROM_LOG]",
                        masked_value=replacement,
                        confidence=1.0,  # Regex = 100% confidence
                        detector=DetectorType.REGEX,
                        severity=Severity(match.severity),
                        column=col,
                        row_index=int(idx),
                    ))
                    detection_count += 1

                df.at[idx, col] = masked_value

            if detection_count > 0:
                logger.info(f"  Column '{col}': {detection_count} regex detections")

        return df, manifest

    def _validate_with_checksum(self, text: str, pattern_name: str) -> bool:
        """Verify if a detected string passes its expected checksum (e.g. Luhn for CC)."""
        if pattern_name == "credit_card":
            # Remove non-digits
            digits = [int(d) for d in str(text) if d.isdigit()]
            if not digits: return False
            # Luhn Algorithm
            checksum = digits[-1]
            payload = digits[:-1][::-1]
            total = checksum
            for i, d in enumerate(payload):
                if i % 2 == 0:
                    d *= 2
                    if d > 9: d -= 9
                total += d
            return (total % 10 == 0)
        return True # Default to True for other patterns

    # -----------------------------------------------------------------------
    # Phase 2.5: Identity Column Fallback (Names without GLiNER)
    # -----------------------------------------------------------------------

    def _apply_identity_fallback(
        self, df: pd.DataFrame, manifest: PIIManifest, col_types: Dict[str, str]
    ) -> Tuple[pd.DataFrame, PIIManifest]:
        """
        Fallback masking for identity columns (e.g. Name) when GLiNER is unavailable.
        
        Names cannot be caught by regex — they require NER or explicit column matching.
        When GLiNER is disabled/unavailable, this ensures the Name column is still
        masked using our gender-aware Indian name generator.
        
        This ONLY runs on columns tagged as 'identity' in pii_config.yaml.
        """
        logger.info("--- Phase 2.5: Identity Column Fallback ---")
        
        for col in df.columns:
            ctype = col_types.get(col, "auto")
            if ctype != "identity":
                continue

            detection_count = 0
            for idx, value in df[col].items():
                if pd.isna(value) or not isinstance(value, str) or not value.strip():
                    continue

                # Mask the name using gender-aware Indian name replacement
                replacement = self.masker.mask(str(value), "name")
                
                manifest.add_detection(PIIDetection(
                    entity_type="PERSON_NAME",
                    original_value="[REDACTED_FROM_LOG]",
                    masked_value=replacement,
                    confidence=1.0,
                    detector=DetectorType.REGEX,  # Column-based detection
                    severity=Severity.HIGH,
                    column=col,
                    row_index=int(idx),
                ))
                detection_count += 1
                df.at[idx, col] = replacement

            if detection_count > 0:
                logger.info(f"  Column '{col}': {detection_count} names masked (identity fallback)")

        return df, manifest

    # -----------------------------------------------------------------------
    # Phase 3: Layer 2 — GLiNER NER
    # -----------------------------------------------------------------------

    def _apply_ner_layer(
        self, df: pd.DataFrame, manifest: PIIManifest, col_types: Dict[str, str]
    ) -> Tuple[pd.DataFrame, PIIManifest]:
        """Apply Layer 2 GLiNER NER to free-text and auto-detected columns."""
        
        if self.ner_scanner is None or not self.ner_scanner.is_available:
            logger.info("--- Layer 2: GLiNER NER SKIPPED (not available) ---")
            return df, manifest
            
        logger.info("--- Layer 2: GLiNER NER Scanner ---")
        
        # NER runs on: free_text columns + identity columns + auto columns
        ner_columns = [
            col for col, ctype in col_types.items()
            if ctype in ("free_text", "identity", "auto")
        ]

        for col in ner_columns:
            detection_count = 0
            for idx, value in df[col].items():
                if pd.isna(value) or not isinstance(value, str) or not value.strip():
                    continue

                ner_matches = self.ner_scanner.scan_text(str(value))
                
                if not ner_matches:
                    continue

                # Pre-seed cache with longest matches first to ensure referential integrity
                # e.g., 'Rajesh Sharma' is cached before 'rajesh'
                masked_value = str(value)
                for match in sorted(ner_matches, key=lambda m: len(m.matched_text), reverse=True):
                    if match.matched_text in masked_value:
                        self.masker.mask(match.matched_text, match.faker_method)

                # Replace each NER match (reverse order to preserve positions)
                for match in sorted(ner_matches, key=lambda m: m.start, reverse=True):
                    # Skip if this text region was already masked by regex
                    if match.matched_text not in masked_value:
                        continue

                    # Route based on confidence thresholds
                    conf = match.confidence
                    route_cfg = self.config.get("confidence_routing", {})
                    auto_redact = route_cfg.get("auto_redact", 0.8)
                    review_queue = route_cfg.get("review_queue", 0.4)

                    if conf >= auto_redact:
                        action = "REDACTED"
                    elif conf >= review_queue:
                        action = "REVIEW"
                    else:
                        action = "LOG_ONLY"

                    if action in ("REDACTED", "REVIEW"):
                        replacement = self.masker.mask(match.matched_text, match.faker_method)
                        masked_value = masked_value.replace(match.matched_text, replacement, 1)
                    else:
                        replacement = "[LOGGED_NOT_MASKED]"
                    
                    manifest.add_detection(PIIDetection(
                        entity_type=match.entity_type,
                        original_value="[REDACTED_FROM_LOG]",
                        masked_value=replacement,
                        confidence=match.confidence,
                        detector=DetectorType.GLINER,
                        severity=Severity(
                            getattr(match, '_severity', None) or
                            self._ner_severity(match.entity_type)
                        ),
                        column=col,
                        row_index=int(idx),
                        action=action,
                    ))
                    detection_count += 1

                df.at[idx, col] = masked_value

            if detection_count > 0:
                logger.info(f"  Column '{col}': {detection_count} NER detections")

        return df, manifest

    def _ner_severity(self, entity_type: str) -> str:
        """Map NER entity type to severity level."""
        from core.ner_scanner import GLINER_LABEL_SEVERITY
        return GLINER_LABEL_SEVERITY.get(entity_type, "MEDIUM")

    # -----------------------------------------------------------------------
    # Phase 4: Numeric Column Protection (Differential Privacy)
    # -----------------------------------------------------------------------

    def _protect_numeric_columns(
        self, df: pd.DataFrame, col_types: Dict[str, str]
    ) -> pd.DataFrame:
        """Apply Laplace noise to numeric columns for differential privacy."""
        
        for col, ctype in col_types.items():
            if ctype != "numeric":
                continue
            if col not in df.columns:
                continue
            if not pd.api.types.is_numeric_dtype(df[col]):
                continue

            logger.info(f"  Applying Laplace noise to '{col}' (ε=1.0)")
            
            # Use a smaller realistic sensitivity for age
            is_age = col.lower() == 'age'
            is_integer = is_age or pd.api.types.is_integer_dtype(df[col].dropna())
            
            epsilon = 1.0
            if is_age:
                sensitivity = 5.0
            else:
                sensitivity = float(df[col].max() - df[col].min()) if len(df[col].dropna()) > 0 else 1000.0
                
            scale = sensitivity / epsilon
            noise = np.random.laplace(0, scale, len(df[col]))
            
            if is_integer:
                df[col] = (df[col] + noise).round().astype('Int64').clip(lower=0)
                if is_age:
                    df[col] = df[col].clip(lower=18, upper=100)
            else:
                df[col] = (df[col] + noise).round(2).clip(lower=0)

        return df

    # -----------------------------------------------------------------------
    # Phase 5: Quasi-Identifier Generalization
    # -----------------------------------------------------------------------

    def _generalize_quasi_identifiers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Protect quasi-identifiers using LLM-friendly techniques (Synthetics)."""
        
        # Note: Age is now natively protected by _protect_numeric_columns using DP
        
        # Find pincode column case-insensitively
        pincode_col = next((c for c in df.columns if c.lower() == 'pincode'), None)
        if pincode_col:
            logger.info(f"  Generating synthetic '{pincode_col}' for referential integrity")
            df[pincode_col] = df[pincode_col].apply(
                lambda x: self.masker.mask(
                    str(int(float(x))) if pd.notna(x) and str(x).replace('.','',1).isdigit() else str(x), 
                    "pincode"
                ) if pd.notna(x) else x
            )

        return df

    # -----------------------------------------------------------------------
    # Free-Text Masking (Gap 5 — Mentor requirement for unstructured data)
    # -----------------------------------------------------------------------

    def mask_text(self, text: str) -> dict:
        """
        Mask PII in arbitrary free text (logs, comments, documents).
        
        Mentor quote: "Same will go for unstructured data where we have
        thousands of GBs of logs."
        
        Uses backward processing (Research File 5: jftuga pattern) to
        prevent position shifts when replacing PII spans.
        
        Args:
            text: Raw text string containing potential PII
            
        Returns:
            dict with 'masked_text', 'detections' list, and 'pii_count'
        """
        if not text or not text.strip():
            return {"masked_text": text, "detections": [], "pii_count": 0}

        detections = []
        masked = text

        # Layer 1: Regex scan
        matches = self.regex_scanner.scan_text(text)
        
        # Sort by position (reverse) to avoid offset shifts — Research File 5
        for match in sorted(matches, key=lambda m: m.start, reverse=True):
            replacement = self.masker.mask(match.matched_text, match.faker_method)
            masked = masked[:match.start] + replacement + masked[match.end:]
            detections.append({
                "type": match.pattern_name,
                "original": match.matched_text[:4] + "***",  # Partial for safety
                "replacement": replacement,
                "severity": match.severity,
                "detector": "REGEX",
            })

        # Layer 2: NER scan (if available)
        if self.enable_ner and self.ner_scanner and self.ner_scanner.is_available:
            ner_matches = self.ner_scanner.scan_text(masked)
            
            # Pre-seed cache with longest matches first to ensure referential integrity
            for match in sorted(ner_matches, key=lambda m: len(m.matched_text), reverse=True):
                if match.matched_text in masked:
                    self.masker.mask(match.matched_text, match.faker_method)
                    
            for match in sorted(ner_matches, key=lambda m: m.start, reverse=True):
                if match.matched_text not in masked:
                    continue
                # Route based on confidence thresholds
                conf = match.confidence
                route_cfg = self.config.get("confidence_routing", {})
                auto_redact = route_cfg.get("auto_redact", 0.8)
                review_queue = route_cfg.get("review_queue", 0.4)

                if conf >= auto_redact:
                    action = "REDACTED"
                elif conf >= review_queue:
                    action = "REVIEW"
                else:
                    action = "LOG_ONLY"

                if action in ("REDACTED", "REVIEW"):
                    replacement = self.masker.mask(match.matched_text, match.faker_method)
                    masked = masked.replace(match.matched_text, replacement, 1)
                else:
                    replacement = "[LOGGED_NOT_MASKED]"

                detections.append({
                    "type": match.entity_type,
                    "original": match.matched_text[:4] + "***",
                    "replacement": replacement,
                    "severity": "HIGH",
                    "detector": "GLINER",
                    "action": action,
                })

        return {
            "masked_text": masked,
            "detections": detections,
            "pii_count": len(detections),
        }


# ============================================================================
# Convenience functions (backward compatibility + text masking API)
# ============================================================================

def process_dataframe(
    df: pd.DataFrame, enable_ner: bool = True, gliner_model_override: Optional[str] = None
) -> Tuple[pd.DataFrame, PIIManifest]:
    """
    Process a DataFrame through the full masking pipeline.
    
    This is the main API for the masking engine.
    
    Args:
        df: Raw DataFrame with potential PII
        enable_ner: Whether to enable GLiNER NER (Layer 2)
        gliner_model_override: Optional GLiNER model name to override the config
        
    Returns:
        Tuple of (masked DataFrame, PII Manifest)
    """
    pipeline = MaskingPipeline(enable_ner=enable_ner, gliner_model_override=gliner_model_override)
    return pipeline.process(df)


def mask_text(text: str, enable_ner: bool = False, gliner_model_override: Optional[str] = None) -> dict:
    """
    Mask PII in arbitrary free text.
    
    Args:
        text: Raw text string
        enable_ner: Whether to use GLiNER NER
        gliner_model_override: Optional GLiNER model name to override the config
        
    Returns:
        dict with 'masked_text', 'detections', 'pii_count'
    """
    pipeline = MaskingPipeline(enable_ner=enable_ner, gliner_model_override=gliner_model_override)
    return pipeline.mask_text(text)

