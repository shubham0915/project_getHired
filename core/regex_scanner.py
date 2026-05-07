"""
Layer 1: Regex Scanner — Deterministic Pattern Matching for Indian Fintech PII

This module scans cell values against regex patterns defined in pii_config.yaml.
It is the FIRST layer in the pipeline — fast, deterministic, and high-precision
for structured identifiers like PAN, Aadhaar, IFSC, phone numbers, and emails.

Design Decisions:
- Patterns are applied in order of specificity (most specific first) to avoid
  false positives from broad patterns (Research File 17: Wealthsimple scrubber ordering)
- Column hints narrow pattern search space (e.g., BANK_ACCOUNT regex only runs
  on columns tagged as financial_columns)
- Returns structured detection results for the PII Manifest
"""

import re
import yaml
import os
import logging
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load config once at module level
# ---------------------------------------------------------------------------
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "pii_config.yaml")

def _load_config() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

_CONFIG = _load_config()


class RegexMatch:
    """Represents a single regex match against a cell value."""
    __slots__ = ("pattern_name", "matched_text", "start", "end", "severity", "category", "faker_method")

    def __init__(self, pattern_name: str, matched_text: str, start: int, end: int,
                 severity: str, category: str, faker_method: str):
        self.pattern_name = pattern_name
        self.matched_text = matched_text
        self.start = start
        self.end = end
        self.severity = severity
        self.category = category
        self.faker_method = faker_method

    def __repr__(self):
        return f"RegexMatch({self.pattern_name}: '{self.matched_text[:20]}...' [{self.severity}])"


class RegexScanner:
    """
    Layer 1 Scanner: Scans text values against compiled regex patterns.
    
    Patterns are loaded from pii_config.yaml and compiled once at init time.
    The scanner respects:
    - Pattern ordering (most specific first)
    - Column hints (narrow search space for broad patterns)
    - Skip-if-matched rules (avoid UPI/Email conflicts)
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or _CONFIG
        self.patterns = self._compile_patterns()
        self.column_hints = self.config.get("column_hints", {})

    def _compile_patterns(self) -> List[Dict[str, Any]]:
        """Compile all regex patterns from config."""
        compiled = []
        for p in self.config.get("regex_patterns", []):
            try:
                compiled.append({
                    "name": p["name"],
                    "regex": re.compile(p["pattern"]),
                    "severity": p.get("severity", "MEDIUM"),
                    "category": p.get("category", "UNKNOWN"),
                    "faker_method": p.get("faker_method", "redact"),
                    "column_hint": p.get("column_hint", None),
                    "skip_if_matched": p.get("skip_if_matched", []),
                })
            except re.error as e:
                logger.error(f"Failed to compile regex for {p['name']}: {e}")
        return compiled

    def _should_apply_pattern(self, pattern: dict, column_name: str) -> bool:
        """Check if a pattern should be applied to this column."""
        hint = pattern.get("column_hint")
        if hint is None:
            return True  # No hint = apply everywhere

        # Check if the column name matches any of the hints
        # Also check against the column_hints config section
        for hint_col in hint:
            if hint_col.lower() in column_name.lower():
                return True

        return False

    def scan_value(self, value: str, column_name: str = "") -> List[RegexMatch]:
        """
        Scan a single cell value against all applicable regex patterns.
        
        Args:
            value: The string value to scan
            column_name: Column name (used for column hints)
            
        Returns:
            List of RegexMatch objects for all detected PII
        """
        if not isinstance(value, str) or not value.strip():
            return []

        matches: List[RegexMatch] = []
        matched_types = set()

        for pattern in self.patterns:
            # Column hint check
            if not self._should_apply_pattern(pattern, column_name):
                continue

            # Skip-if-matched check (e.g., don't match UPI if EMAIL already matched)
            skip_rules = pattern.get("skip_if_matched", [])
            if any(mt in matched_types for mt in skip_rules):
                continue

            # Run regex
            for m in pattern["regex"].finditer(value):
                try:
                    matched_text = m.group("pii")
                    start = m.start("pii")
                    end = m.end("pii")
                except IndexError:
                    matched_text = m.group()
                    start = m.start()
                    end = m.end()

                match_obj = RegexMatch(
                    pattern_name=pattern["name"],
                    matched_text=matched_text,
                    start=start,
                    end=end,
                    severity=pattern["severity"],
                    category=pattern["category"],
                    faker_method=pattern["faker_method"],
                )
                matches.append(match_obj)
                matched_types.add(pattern["name"])

        return matches

    def scan_text(self, text: str) -> List[RegexMatch]:
        """Scan free text (no column context). Used by Layer 3 validation."""
        return self.scan_value(text, column_name="")

    def get_applicable_patterns(self, column_name: str) -> List[str]:
        """List which patterns would apply to a given column."""
        return [
            p["name"] for p in self.patterns
            if self._should_apply_pattern(p, column_name)
        ]
