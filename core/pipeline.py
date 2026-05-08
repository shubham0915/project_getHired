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

import re
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
        self.endpoint_cols = set(self.column_hints.get("endpoint_columns", []))
        self.numeric_cols = set(self.column_hints.get("numeric_columns", []))
        self.identity_cols = set(self.column_hints.get("identity_columns", []))
        self.pseudonymize_cols = set(self.column_hints.get("pseudonymize_columns", []))

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
        # Only run fallback if NER is disabled to avoid conflicting masks
        if not self.enable_ner or self.ner_scanner is None or not self.ner_scanner.is_available:
            masked_df, manifest = self._apply_identity_fallback(masked_df, manifest, col_types)

        # ----- PHASE 2.5b: Free-Text Name Scanner -----
        # Scan free_text columns for embedded names using contextual triggers
        # and dictionary lookup. Runs regardless of NER availability because
        # GLiNER may miss vernacular patterns like "naam Rajesh hai".
        masked_df, manifest = self._apply_freetext_name_scan(masked_df, manifest, col_types)

        # ----- PHASE 3: Layer 2 — GLiNER NER Scan + Mask -----
        if self.enable_ner and self.ner_scanner is not None:
            masked_df, manifest = self._apply_ner_layer(masked_df, df, manifest, col_types)

        # ----- PHASE 4: Numeric Column Protection -----
        masked_df = self._protect_numeric_columns(masked_df, col_types)

        # ----- PHASE 4.5: Pseudonymize High-Cardinality IDs -----
        masked_df = self._pseudonymize_columns(masked_df, col_types)

        # ----- PHASE 5: Quasi-Identifier Generalization -----
        masked_df = self._generalize_quasi_identifiers(masked_df)

        # ----- PHASE 6: Layer 3 — Output Validation -----
        validator = OutputValidator(
            max_passes=self.config.get("global", {}).get("max_validation_passes", 3),
            use_ner=self.enable_ner
        )
        masked_df, manifest = validator.validate_dataframe(
            masked_df, manifest,
            # Pass ALL columns that should be untouched — including those
            # dynamically classified as skip/numeric/pseudonymize by content analysis
            skip_columns=list({
                col for col, ctype in col_types.items()
                if ctype in ("skip", "numeric", "pseudonymize")
            }),
            known_masked_values=self.masker.generated_values,
            col_types=col_types
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

    # -----------------------------------------------------------------------
    # Content-First Column Classification (Schema-Agnostic)
    # -----------------------------------------------------------------------
    # The pipeline does NOT trust column headers. A column named 'col_A'
    # could contain PANs; a column named 'Name' could contain garbage.
    # Classification is driven by sampling actual cell values and probing
    # them with regex to measure PII density, cardinality, and text length.
    #
    # YAML column_hints are used as SOFT BOOSTS (tiebreakers), never as
    # hard gates. The only exception is 'pseudonymize_columns' — that is
    # an intentional operational directive ("hash these IDs"), not a PII
    # classification, so it IS respected as a hard override.
    # -----------------------------------------------------------------------

    _CONTENT_SAMPLE_SIZE = 100  # Number of non-null values to probe per column
    _PII_DENSITY_THRESHOLD = 0.10  # 10%+ of sampled values contain PII → scan it
    _CATEGORICAL_MAX_UNIQUE = 30  # Low cardinality → likely enum/status, safe to skip
    _FREETEXT_AVG_LEN = 60  # Average string length above this → free-text

    def _classify_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Content-first column classification.

        For each column, we sample values and measure:
        1. PII density   — % of sampled values that match at least one regex pattern
        2. Cardinality   — number of unique values (low = categorical = skip)
        3. Avg length    — long strings suggest free-text (GLiNER + Regex)
        4. Numeric dtype — pure numbers with no PII → Differential Privacy

        Categories produced:
        - skip:          Low-cardinality non-PII (Status, Gender, Boolean columns)
        - pseudonymize:  Operational override from config (hash high-cardinality IDs)
        - identity:      Content-detected as mostly names (GLiNER priority)
        - free_text:     Long strings, often with embedded PII (GLiNER + Regex)
        - numeric:       Pure numeric, no PII patterns (Differential Privacy)
        - endpoint:      API endpoint paths (soft hint, regex scan)
        - auto:          Default — full regex + NER scan on every value
        """
        col_types = {}
        col_lower_set = lambda s: {c.lower() for c in s}

        for col in df.columns:
            col_lower = col.lower()

            # --- Hard overrides (operational directives, not PII classification) ---
            if col in self.pseudonymize_cols or col_lower in col_lower_set(self.pseudonymize_cols):
                col_types[col] = "pseudonymize"
                logger.debug(f"  Column '{col}' → pseudonymize (config directive)")
                continue

            if col in self.endpoint_cols or col_lower in col_lower_set(self.endpoint_cols):
                col_types[col] = "endpoint"
                logger.debug(f"  Column '{col}' → endpoint (config directive)")
                continue

            # --- Content analysis ---
            non_null = df[col].dropna()
            if len(non_null) == 0:
                col_types[col] = "skip"
                logger.debug(f"  Column '{col}' → skip (all null)")
                continue

            sample = non_null.head(self._CONTENT_SAMPLE_SIZE).astype(str)
            n_unique = df[col].nunique()
            n_total = len(non_null)

            # Check if column is purely numeric
            is_numeric = pd.api.types.is_numeric_dtype(df[col])

            # --- PII probe: run regex on sample values ---
            pii_hits = 0
            pii_types_seen: Dict[str, int] = {}  # pattern_name → count
            for val in sample:
                val_str = str(val)
                matches = self.regex_scanner.scan_value(val_str, column_name="")  # no column context!
                # Filter out known false-positive patterns:
                # - DATE_OF_BIRTH_ISO matching timestamps (contain 'T' or ':')
                credible_matches = [
                    m for m in matches
                    if not (m.pattern_name == "DATE_OF_BIRTH_ISO" and ("T" in val_str or ":" in val_str))
                ]
                if credible_matches:
                    pii_hits += 1
                    for m in credible_matches:
                        pii_types_seen[m.pattern_name] = pii_types_seen.get(m.pattern_name, 0) + 1

            pii_density = pii_hits / max(len(sample), 1)

            # --- Credibility filter ---
            # Some broad regex patterns (VOTER_ID, PINCODE, IP_ADDRESS, ATTACHED_NAME)
            # produce false positives on non-PII columns (ticket IDs, status codes,
            # enum values like "Self-employed", "Web-Mobile", etc.)
            # If ONLY these "noisy" patterns fired, downgrade the PII density.
            _NOISY_PATTERNS = {"VOTER_ID", "INDIAN_PINCODE", "IP_ADDRESS", "MAC_ADDRESS",
                               "VEHICLE_CHASSIS_VIN", "SWIFT_BIC", "ATTACHED_NAME"}
            if pii_types_seen and all(t in _NOISY_PATTERNS for t in pii_types_seen.keys()):
                # All hits are from noisy patterns → likely false positives
                pii_density = 0.0
                logger.debug(
                    f"  Column '{col}': PII probe downgraded to 0% (only noisy patterns: "
                    f"{list(pii_types_seen.keys())})"
                )

            # --- Cardinality check ---
            is_low_cardinality = (n_unique <= self._CATEGORICAL_MAX_UNIQUE) and (n_total > 5)

            # --- Average string length (for text vs structured) ---
            avg_len = sample.str.len().mean() if len(sample) > 0 else 0

            # --- Decision tree ---

            # 1. If content has PII, NEVER skip — regardless of column name
            if pii_density >= self._PII_DENSITY_THRESHOLD:
                if avg_len >= self._FREETEXT_AVG_LEN:
                    col_types[col] = "free_text"
                    logger.info(
                        f"  Column '{col}' → free_text (PII density={pii_density:.0%}, "
                        f"avg_len={avg_len:.0f}, types={list(pii_types_seen.keys())})"
                    )
                else:
                    col_types[col] = "auto"
                    logger.info(
                        f"  Column '{col}' → auto [PII detected] (density={pii_density:.0%}, "
                        f"types={list(pii_types_seen.keys())})"
                    )
                continue

            # 2. Pure numeric column with no PII → Differential Privacy
            #    Exclude boolean columns (pandas treats bool as numeric)
            is_boolean = pd.api.types.is_bool_dtype(df[col])
            if is_numeric and not is_boolean and pii_density < self._PII_DENSITY_THRESHOLD:
                # Safety: columns with 'id', 'account', 'number' in name might be
                # identifiers that shouldn't get Laplace noise
                is_id_like = any(
                    kw in col_lower
                    for kw in ['id', 'number', 'num', 'code', 'pin', 'account', 'aadhaar']
                )
                if is_id_like:
                    col_types[col] = "auto"  # Scan as string, regex will decide
                    logger.info(f"  Column '{col}' → auto (numeric but id-like name, scanning)")
                else:
                    col_types[col] = "numeric"
                    logger.debug(f"  Column '{col}' → numeric (pure numbers, no PII)")
                continue

            # Also: if a numeric column got flagged ONLY because of PINCODE
            # false-positives (6-digit integers matching \b[1-9]\d{5}\b), treat
            # it as numeric anyway — monetary amounts are not pincodes.
            if is_numeric and not is_boolean and pii_density >= self._PII_DENSITY_THRESHOLD:
                only_pincode = all(t == "INDIAN_PINCODE" for t in pii_types_seen.keys())
                if only_pincode:
                    col_types[col] = "numeric"
                    logger.info(
                        f"  Column '{col}' → numeric (PINCODE-only false positive on integers, "
                        f"treating as DP candidate)"
                    )
                    continue

            # 3. Name detection heuristic (catches names even without NER/GLiNER)
            #    This runs BEFORE the cardinality skip — because a column of 20
            #    unique names (cardinality=20 ≤ 30) would be wrongly skipped as
            #    categorical. Names are PII and must NEVER be skipped.
            #
            #    Regex can't detect names — they have no pattern. But we already
            #    have 100 curated Indian first names in PIIMasker. If a significant
            #    fraction of values start with a known Indian name, this is likely
            #    a name column. This ensures a column named 'col_X' with names
            #    like "Rajesh Sharma" is correctly classified as identity.
            if not is_numeric and avg_len < self._FREETEXT_AVG_LEN:
                name_hits = self._probe_for_names(sample)
                if name_hits >= 0.15:  # 15%+ of values match known Indian names
                    col_types[col] = "identity"
                    logger.info(
                        f"  Column '{col}' → identity (name probe: {name_hits:.0%} of "
                        f"values match known Indian first names)"
                    )
                    continue

            # 4. Low cardinality + no PII + no names → categorical, safe to skip
            if is_low_cardinality and pii_density < self._PII_DENSITY_THRESHOLD:
                col_types[col] = "skip"
                logger.debug(
                    f"  Column '{col}' → skip (categorical: {n_unique} unique values, "
                    f"0 PII in sample)"
                )
                continue

            # 5. Long average string length → free text (even without regex PII,
            #    GLiNER may find names, addresses, etc.)
            if avg_len >= self._FREETEXT_AVG_LEN:
                col_types[col] = "free_text"
                logger.info(f"  Column '{col}' → free_text (avg_len={avg_len:.0f}, no regex PII but long text)")
                continue

            # 5. Check YAML hints as soft tiebreaker for ambiguous cases
            hint_type = self._check_yaml_hint(col_lower)
            if hint_type:
                col_types[col] = hint_type
                logger.debug(f"  Column '{col}' → {hint_type} (YAML hint tiebreaker)")
                continue

            # 6. Default: scan everything — let regex + NER decide per-value
            col_types[col] = "auto"
            logger.debug(f"  Column '{col}' → auto (default, will scan)")

        return col_types

    def _check_yaml_hint(self, col_lower: str) -> Optional[str]:
        """
        Check if any YAML column hint matches this column name.
        Returns the hint-based type or None if no match.
        Used ONLY as a soft tiebreaker for ambiguous columns.
        """
        col_lower_set = lambda s: {c.lower() for c in s}

        if col_lower in col_lower_set(self.skip_columns):
            return "skip"
        if col_lower in col_lower_set(self.identity_cols):
            return "identity"
        if col_lower in col_lower_set(self.free_text_cols):
            return "free_text"
        if col_lower in col_lower_set(self.numeric_cols):
            return "numeric"
        return None

    # Build a frozen lookup set of known Indian names (first + surnames)
    # Used by _probe_for_names for content-based name detection.
    # First names come from PIIMasker (100 curated), surnames are the most
    # common 60 Indian family names covering all major regions/communities.
    _COMMON_INDIAN_SURNAMES = [
        'sharma', 'verma', 'patel', 'gupta', 'singh', 'kumar', 'reddy',
        'nair', 'menon', 'iyer', 'iyengar', 'desai', 'joshi', 'mehta',
        'mishra', 'thakur', 'patil', 'kaur', 'tiwari', 'kulkarni',
        'rao', 'kapoor', 'chatterjee', 'banerjee', 'mukherjee', 'ghosh',
        'das', 'sen', 'bose', 'shah', 'pandey', 'chauhan', 'yadav',
        'shetty', 'hegde', 'bhat', 'naidu', 'choudhary', 'agarwal',
        'jain', 'saxena', 'pillai', 'subramanian', 'krishnan', 'rajan',
        'murthy', 'venkatesh', 'gill', 'sandhu', 'dhillon', 'bhatt',
        'trivedi', 'shukla', 'dubey', 'srivastava', 'bajaj', 'malhotra',
        'kohli', 'khanna', 'arora', 'sethi',
    ]

    _KNOWN_INDIAN_NAMES: frozenset = frozenset(
        n.lower() for n in (
            PIIMasker._INDIAN_MALE_FIRST
            + PIIMasker._INDIAN_FEMALE_FIRST
            + _COMMON_INDIAN_SURNAMES
        )
    )

    def _probe_for_names(self, sample: pd.Series) -> float:
        """
        Probe a column sample for person names using our curated Indian name list.
        
        Names have no regex pattern — this is the ONLY way to detect them without
        NER. We extract the first word from each value and check against our 100
        curated Indian first names (male + female).
        
        Args:
            sample: Series of string values (already converted to str)
            
        Returns:
            Fraction of sample values whose first word matches a known Indian name.
            0.15 (15%) is the threshold for classifying as identity column.
        """
        if len(sample) == 0:
            return 0.0

        hits = 0
        for val in sample:
            val_str = str(val).strip()
            if not val_str:
                continue
            # Extract first word (handles "Rajesh Sharma", "rajesh", etc.)
            first_word = val_str.split()[0].lower()
            if first_word in self._KNOWN_INDIAN_NAMES:
                hits += 1

        return hits / max(len(sample), 1)

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
            if ctype in ("skip", "numeric", "pseudonymize"):
                continue

            # Pre-cast: if pandas loaded this column as numeric (int64/float64)
            # but it contains PII (phone, bank_acct_no, pincode), convert to
            # string first. Otherwise replacing int cells with string values
            # creates mixed-type columns that break Parquet export.
            if df[col].dtype in ('int64', 'float64', 'int32', 'float32'):
                df[col] = df[col].astype(str)

            detection_count = 0
            for idx, value in df[col].items():
                if pd.isna(value):
                    continue

                # Convert to string — phone numbers, account numbers, pincodes
                # are semantically strings even if pandas loads them as int64
                val_str = str(value).strip()
                if not val_str:
                    continue

                matches = self.regex_scanner.scan_value(val_str, column_name=col)
                
                # Intelligent Discovery: Filter matches using checksums (Gap 1 in user text)
                valid_matches = [
                    m for m in matches 
                    if self._validate_with_checksum(m.matched_text, m.pattern_name, ctype)
                ]

                # Context-aware PINCODE filtering for free-text columns:
                # A 6-digit number in free text is almost always an amount, not
                # a pincode. Only treat it as a pincode if preceded by a
                # POSITIVE location indicator (pin/pincode/zip/postal).
                if ctype in ("free_text", "auto"):
                    context_filtered = []
                    for m in valid_matches:
                        if m.pattern_name == "INDIAN_PINCODE":
                            prefix = val_str[:m.start].rstrip().lower()
                            pincode_indicators = ('pin', 'pincode', 'pin code', 'zip',
                                                  'postal', 'area code', 'pin:', 'pin-')
                            has_pincode_context = any(
                                prefix.endswith(ind) for ind in pincode_indicators
                            )
                            if not has_pincode_context:
                                continue  # Skip: no pincode context, likely an amount
                        context_filtered.append(m)
                    valid_matches = context_filtered
                
                if not valid_matches:
                    continue

                # Replace each match in the cell value
                masked_value = val_str
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
                        row_index=int(str(idx)),  # type: ignore
                    ))
                    detection_count += 1

                df.at[idx, col] = masked_value

            if detection_count > 0:
                logger.info(f"  Column '{col}': {detection_count} regex detections")

        return df, manifest

    def _validate_with_checksum(self, text: str, pattern_name: str, column_type: str = "auto") -> bool:
        """Verify if a detected string passes its expected checksum (e.g. Luhn for CC, Verhoeff for Aadhaar)."""
        pattern_lower = pattern_name.lower()
        if pattern_lower == "credit_card":
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
            
        elif pattern_lower == "aadhaar":
            # In free-text logs, allow Aadhaar matches even if checksum fails
            if column_type in ("free_text", "auto"):
                return True
            # Remove non-digits
            digits = [int(d) for d in str(text) if d.isdigit()]
            if len(digits) != 12: return False
            
            # Verhoeff math tables
            d_table = [
                [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
                [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
                [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
                [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
            ]
            p_table = [
                [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
                [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
                [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
            ]
            
            c = 0
            for i, p in enumerate(reversed(digits)):
                c = d_table[c][p_table[i % 8][p]]
            return c == 0
            
        elif pattern_lower == "gstin":
            if len(text) != 15: return False
            alphanumeric = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            char_to_val = {char: i for i, char in enumerate(alphanumeric)}
            factor = 1
            total = 0
            for char in text[:-1]:
                if char not in char_to_val: return False
                val = char_to_val[char]
                digit = val * factor
                digit = (digit // 36) + (digit % 36)
                total += digit
                factor = 2 if factor == 1 else 1
            remainder = total % 36
            checksum_val = (36 - remainder) % 36
            expected_char = alphanumeric[checksum_val]
            return text[-1].upper() == expected_char
            
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
                    row_index=int(str(idx)),  # type: ignore
                ))
                detection_count += 1
                df.at[idx, col] = replacement

            if detection_count > 0:
                logger.info(f"  Column '{col}': {detection_count} names masked (identity fallback)")

        return df, manifest

    # -----------------------------------------------------------------------
    # Phase 2.5b: Free-Text Name Scanner (Names inside unstructured text)
    # -----------------------------------------------------------------------
    # Regex can't catch names — they have no pattern. GLiNER handles this
    # perfectly but may be unavailable or slow. This lightweight fallback
    # uses two strategies:
    #   1. CONTEXTUAL: "naam Rajesh Sharma hai" → extract after trigger words
    #   2. DICTIONARY: Any token matching our 160 curated Indian names
    #
    # Both approaches replace detected names with gender-aware synthetic
    # Indian names from PIIMasker for natural-looking output.
    # -----------------------------------------------------------------------

    # Multilingual name introduction triggers (Hindi, Telugu, Kannada, Tamil, Malayalam, English)
    _NAME_TRIGGERS = re.compile(
        r'(?:naam|name\s+is|my\s+name\s+is|this\s+is|i\s+am|'
        r'naa\s+peru|nan\s+hesaru|en\s+peyar|ente\s+peru|'
        r'mera\s+naam|hamara\s+naam|apna\s+naam|'
        r'I\'m|Im)\s+'
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        re.IGNORECASE
    )

    def _apply_freetext_name_scan(
        self, df: pd.DataFrame, manifest: PIIManifest, col_types: Dict[str, str]
    ) -> Tuple[pd.DataFrame, PIIManifest]:
        """
        Scan free_text and auto columns for embedded person names.

        Strategy 1: Contextual triggers (multilingual).
            "mera naam Rajesh Sharma hai" → replace "Rajesh Sharma"
        Strategy 2: Dictionary-based token scan.
            Any capitalized word matching our curated Indian name list.
            Consecutive name tokens are merged ("Rajesh" + "Sharma" → full name).
        """
        logger.info("--- Phase 2.5b: Free-Text Name Scanner ---")

        freetext_cols = [
            col for col, ctype in col_types.items()
            if ctype in ("free_text",)
        ]

        if not freetext_cols:
            return df, manifest

        # Build a name → replacement cache for consistency within the session
        name_replacement_cache: Dict[str, str] = {}
        total_names = 0

        for col in freetext_cols:
            for idx, value in df[col].items():
                if pd.isna(value) or not isinstance(value, str):
                    continue

                text = str(value)
                names_found: list = []  # (start, end, name_text)

                # --- Strategy 1: Contextual triggers ---
                for m in self._NAME_TRIGGERS.finditer(text):
                    name_text = m.group(1).strip()
                    # Remove trailing "hai", "hain", "hu" (Hindi verb)
                    name_text = re.sub(r'\s+(?:hai|hain|hu|hoon|here|here\.?)$', '', name_text, flags=re.IGNORECASE)
                    if name_text and len(name_text) > 2:
                        names_found.append((m.start(1), m.start(1) + len(name_text), name_text))

                # --- Strategy 2: Dictionary-based token scan ---
                # Find capitalized words matching known Indian names
                words = list(re.finditer(r'\b([A-Z][a-z]+)\b', text))
                i = 0
                while i < len(words):
                    word = words[i].group(1)
                    if word.lower() in self._KNOWN_INDIAN_NAMES:
                        # Check if next word is also a name (full name: "Rajesh Sharma")
                        name_start = words[i].start()
                        name_parts = [word]
                        j = i + 1
                        while j < len(words):
                            next_word = words[j].group(1)
                            # Check if adjacent (allow 1 space gap)
                            gap = words[j].start() - (words[j-1].end())
                            if gap <= 1 and next_word.lower() in self._KNOWN_INDIAN_NAMES:
                                name_parts.append(next_word)
                                j += 1
                            else:
                                break
                        name_end = words[j-1].end()
                        full_name = ' '.join(name_parts)

                        # Avoid duplicates with Strategy 1 (overlapping ranges)
                        already_found = any(
                            s <= name_start < e or s < name_end <= e
                            for s, e, _ in names_found
                        )
                        if not already_found:
                            names_found.append((name_start, name_end, full_name))
                        i = j
                    else:
                        i += 1

                # --- Apply replacements (right to left to preserve offsets) ---
                if not names_found:
                    continue

                # Sort by start position descending
                names_found.sort(key=lambda x: x[0], reverse=True)

                for start, end, original_name in names_found:
                    # Use cache for consistency (same name → same replacement)
                    if original_name not in name_replacement_cache:
                        name_replacement_cache[original_name] = self.masker.mask(
                            original_name, "name"
                        )
                    replacement = name_replacement_cache[original_name]

                    text = text[:start] + replacement + text[end:]

                    manifest.add_detection(PIIDetection(
                        entity_type="PERSON_NAME",
                        original_value="[REDACTED_FROM_LOG]",
                        masked_value=replacement,
                        confidence=0.85,
                        detector=DetectorType.REGEX,
                        severity=Severity.HIGH,
                        column=col,
                        row_index=int(str(idx)),
                    ))
                    total_names += 1

                df.at[idx, col] = text

        if total_names > 0:
            logger.info(f"  Free-text name scan: {total_names} names masked across {len(freetext_cols)} columns")

        return df, manifest

    # -----------------------------------------------------------------------
    # Phase 3: Layer 2 — GLiNER NER
    # -----------------------------------------------------------------------

    def _apply_ner_layer(
        self, df: pd.DataFrame, raw_df: pd.DataFrame, manifest: PIIManifest, col_types: Dict[str, str]
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
            for idx, masked_val in df[col].items():
                original_value = raw_df.at[idx, col]
                if pd.isna(original_value) or not isinstance(original_value, str) or not original_value.strip():
                    continue

                # Scan the original text so we don't accidentally treat fake data from Layer 1 as real PII
                ner_matches = self.ner_scanner.scan_text(str(original_value))
                
                if not ner_matches:
                    continue

                # Pre-seed cache with longest matches first to ensure referential integrity
                # e.g., 'Rajesh Sharma' is cached before 'rajesh'
                masked_value = str(masked_val)
                for match in sorted(ner_matches, key=lambda m: len(m.matched_text), reverse=True):
                    if match.matched_text in masked_value:
                        self.masker.mask(match.matched_text, match.faker_method)

                # Replace each NER match (longest first to avoid partial replacements)
                for match in sorted(ner_matches, key=lambda m: len(m.matched_text), reverse=True):
                    # Check if the text still exists in masked_value (Regex might have modified it)
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
                        # Replace in string to bypass offset shifts caused by Layer 1
                        masked_value = masked_value.replace(match.matched_text, replacement)
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
                        row_index=int(str(idx)),  # type: ignore
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

            # Skip low-cardinality integer columns — these are categorical codes
            # (http_status=200/404/500, priority=1/2/3) not continuous values.
            # DP noise on them creates nonsensical outputs (200 → 203).
            n_unique = df[col].nunique()
            if n_unique <= 30 and pd.api.types.is_integer_dtype(df[col]):
                logger.info(f"  Skipping '{col}' — categorical integer ({n_unique} unique values)")
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
    # Phase 4.5: Pseudonymize High-Cardinality Identifiers
    # -----------------------------------------------------------------------

    def _pseudonymize_columns(
        self, df: pd.DataFrame, col_types: Dict[str, str]
    ) -> pd.DataFrame:
        """Deterministically pseudonymize high-cardinality identifier columns."""

        for col, ctype in col_types.items():
            if ctype != "pseudonymize":
                continue
            if col not in df.columns:
                continue

            df[col] = df[col].apply(
                lambda x: self.masker.mask(str(x), "hash") if pd.notna(x) and str(x).strip() else x
            )

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
        Uses exact offset mapping and overlap resolution to prevent position shifts.
        """
        if not text or not text.strip():
            return {"masked_text": text, "detections": [], "pii_count": 0}

        all_matches = []

        # Layer 1: Regex scan
        matches = self.regex_scanner.scan_text(text)
        for match in matches:
            if not self._validate_with_checksum(match.matched_text, match.pattern_name):
                continue
            all_matches.append({
                "start": match.start, "end": match.end, "text": match.matched_text,
                "type": match.pattern_name, "severity": match.severity,
                "detector": "REGEX", "faker_method": match.faker_method,
                "confidence": 1.0, "action": "REDACTED", "priority": 0
            })

        # Layer 2: NER scan (if available)
        if self.enable_ner and self.ner_scanner and self.ner_scanner.is_available:
            ner_matches = self.ner_scanner.scan_text(text)
            
            # Pre-seed cache to ensure referential integrity
            for match in sorted(ner_matches, key=lambda m: len(m.matched_text), reverse=True):
                self.masker.mask(match.matched_text, match.faker_method)
                    
            for match in ner_matches:
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

                all_matches.append({
                    "start": match.start, "end": match.end, "text": match.matched_text,
                    "type": match.entity_type, "severity": getattr(match, '_severity', "HIGH"),
                    "detector": "GLINER", "faker_method": match.faker_method,
                    "confidence": match.confidence, "action": action, "priority": 1
                })

        # Resolve Overlaps: Sort by priority (Regex first), then length (longest first)
        all_matches.sort(key=lambda x: (x["priority"], -(x["end"] - x["start"])))
        used = [False] * len(text)
        resolved_matches = []

        for m in all_matches:
            start, end = m["start"], m["end"]
            if not any(used[start:end]):
                for i in range(start, end):
                    used[i] = True
                resolved_matches.append(m)

        # Apply Replacements Backward to prevent offset shifts
        resolved_matches.sort(key=lambda x: x["start"], reverse=True)
        masked = text
        detections = []

        for m in resolved_matches:
            if m["action"] in ("REDACTED", "REVIEW"):
                replacement = self.masker.mask(m["text"], m["faker_method"])
                masked = masked[:m["start"]] + replacement + masked[m["end"]:]
            else:
                replacement = "[LOGGED_NOT_MASKED]"

            detections.append({
                "type": m["type"],
                "original": m["text"][:4] + "***",
                "replacement": replacement,
                "severity": m["severity"],
                "detector": m["detector"],
                "action": m["action"],
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

