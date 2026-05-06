"""
Layer 3: Output Validator — Post-Masking PII Re-Scanner

The "safety net" layer. After masking is complete, this module re-scans
the output using both Layer 1 (Regex) and Layer 2 (GLiNER) to catch
any PII that slipped through.

Design: Iterative scanning (from Research File 7: jftuga tool pattern)
- Re-scan the masked output
- If PII is found AND it's not a known masked value (whitelist), flag it
- Repeat until clean OR max_passes reached
- Record each validation pass in the PII Manifest

Key insight: Since Faker generates format-preserving values (fake PANs look
like real PANs), the validator must use a WHITELIST of values produced by the
masker to distinguish "intentional synthetic value" from "PII leak".
"""

import pandas as pd
import logging
from typing import Tuple, List, Dict, Set

from core.regex_scanner import RegexScanner
from core.masker import PIIMasker
from models.pii_manifest import PIIManifest, PIIDetection, ValidationPassResult, DetectorType, Severity

logger = logging.getLogger(__name__)


class OutputValidator:
    """
    Layer 3: Re-scans masked output to catch any surviving PII.
    
    Uses a whitelist from the masker's cache to distinguish intentional
    synthetic replacements from actual PII leaks.
    """

    def __init__(self, max_passes: int = 3, use_ner: bool = False):
        self.max_passes = max_passes
        self.use_ner = use_ner
        self.regex_scanner = RegexScanner()
        self.masker = PIIMasker()

        # Lazy NER import
        self._ner_scanner = None
        if self.use_ner:
            try:
                from core.ner_scanner import NERScanner
                self._ner_scanner = NERScanner()
            except Exception as e:
                logger.warning(f"NER scanner not available for validation: {e}")

    @staticmethod
    def _validate_with_checksum(text: str, pattern_name: str) -> bool:
        """Verify if a detected string passes its expected checksum."""
        pattern_lower = pattern_name.lower()
        if pattern_lower == "credit_card":
            digits = [int(d) for d in str(text) if d.isdigit()]
            if not digits: return False
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
            digits = [int(d) for d in str(text) if d.isdigit()]
            if len(digits) != 12: return False
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
        return True

    def validate_dataframe(
        self, df: pd.DataFrame, manifest: PIIManifest, 
        skip_columns: List[str] = None,
        known_masked_values: Set[str] = None
    ) -> Tuple[pd.DataFrame, PIIManifest]:
        """
        Run iterative validation passes on the masked DataFrame.
        
        Args:
            df: The masked DataFrame to validate
            manifest: The PII Manifest to update with validation results
            skip_columns: Columns to skip during validation
            known_masked_values: Set of values produced by the masker (whitelist).
                                These are intentional synthetic values that should
                                NOT be flagged as PII leaks.
            
        Returns:
            Tuple of (cleaned DataFrame, updated Manifest)
        """
        skip = set(skip_columns or [])
        whitelist = known_masked_values or set()
        validated_df = df.copy()

        for pass_num in range(1, self.max_passes + 1):
            logger.info(f"Validation Pass {pass_num}/{self.max_passes}")
            
            pii_found_count = 0
            types_found = set()

            for col in validated_df.columns:
                if col in skip:
                    continue

                for idx, value in validated_df[col].items():
                    if not isinstance(value, str) or not value.strip():
                        continue

                    # Re-scan with regex
                    regex_matches = self.regex_scanner.scan_value(str(value), column_name=col)
                    
                    # Apply checksum filtering
                    valid_matches = [
                        m for m in regex_matches 
                        if self._validate_with_checksum(m.matched_text, m.pattern_name)
                    ]
                    
                    for match in sorted(valid_matches, key=lambda m: m.start, reverse=True):
                        # Check whitelist: if this matched text is a KNOWN masked value,
                        # it's an intentional synthetic replacement, not a leak.
                        if match.matched_text in whitelist:
                            continue

                        # This is an actual PII leak in the output! Mask it.
                        masked_replacement = self.masker.mask(match.matched_text, match.faker_method)
                        value = value[:match.start] + masked_replacement + value[match.end:]
                        whitelist.add(masked_replacement)  # Add new replacement to whitelist
                        pii_found_count += 1
                        types_found.add(match.pattern_name)
                        
                        # Record in manifest
                        manifest.add_detection(PIIDetection(
                            entity_type=f"VALIDATION_{match.pattern_name}",
                            original_value="[REDACTED_FROM_LOG]",
                            masked_value=masked_replacement,
                            confidence=1.0,
                            detector=DetectorType.REGEX,
                            severity=Severity(match.severity),
                            column=col,
                            row_index=int(str(idx)),  # type: ignore
                        ))

                    # Re-scan with NER
                    if self.use_ner and self._ner_scanner and self._ner_scanner.is_available:
                        ner_matches = self._ner_scanner.scan_text(str(value))
                        for match in sorted(ner_matches, key=lambda m: m.start, reverse=True):
                            if match.matched_text in whitelist:
                                continue
                            
                            masked_replacement = self.masker.mask(match.matched_text, match.faker_method)
                            value = value[:match.start] + masked_replacement + value[match.end:]
                            whitelist.add(masked_replacement)
                            pii_found_count += 1
                            types_found.add(match.entity_type)
                            
                            manifest.add_detection(PIIDetection(
                                entity_type=f"VALIDATION_{match.entity_type}",
                                original_value="[REDACTED_FROM_LOG]",
                                masked_value=masked_replacement,
                                confidence=match.confidence,
                                detector=DetectorType.GLINER,
                                severity=Severity.HIGH,
                                column=col,
                                row_index=int(str(idx)),  # type: ignore
                            ))

                    validated_df.at[idx, col] = value

            # Record validation pass
            pass_result = ValidationPassResult(
                pass_number=pass_num,
                pii_found=pii_found_count,
                types_found=list(types_found),
                is_clean=(pii_found_count == 0),
            )
            manifest.validation_passes.append(pass_result)

            if pii_found_count == 0:
                logger.info(f"Validation Pass {pass_num}: CLEAN — no PII found")
                manifest.final_clean = True
                break
            else:
                logger.warning(
                    f"Validation Pass {pass_num}: Found {pii_found_count} NEW PII instances "
                    f"({', '.join(types_found)}). Re-masking and continuing..."
                )

        if not manifest.final_clean:
            logger.warning(
                f"Validation did NOT achieve clean state after {self.max_passes} passes. "
                "Manual review recommended."
            )

        return validated_df, manifest
