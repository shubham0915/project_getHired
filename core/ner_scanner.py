"""
Layer 2: NER Scanner — Context-Aware PII Detection with GLiNER

This module uses GLiNER (a bidirectional transformer encoder) for zero-shot
named entity recognition. It catches PII that regex cannot detect:
- Person names (no fixed pattern)
- Addresses (variable format)  
- Organization names
- Context-dependent PII in free text

Model Selection (from Research Batch 3):
- Primary: urchade/gliner_multi_pii-v1 (multilingual, 55+ PII types, MIT license)
- Alternative: nvidia/gliner-PII (570M params, NVIDIA-backed, commercial license)

The model is loaded lazily (only when first needed) to avoid slow startup
when only regex detection is sufficient.
"""

import os
import yaml
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "pii_config.yaml")

def _load_config() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

_CONFIG = _load_config()


class NERMatch:
    """Represents a single GLiNER entity detection."""
    __slots__ = ("entity_type", "matched_text", "start", "end", "confidence", "faker_method")

    def __init__(self, entity_type: str, matched_text: str, start: int, end: int,
                 confidence: float, faker_method: str = "redact"):
        self.entity_type = entity_type
        self.matched_text = matched_text
        self.start = start
        self.end = end
        self.confidence = confidence
        self.faker_method = faker_method

    def __repr__(self):
        return f"NERMatch({self.entity_type}: '{self.matched_text[:20]}' [{self.confidence:.2f}])"


# Mapping from GLiNER labels to our internal faker methods
GLINER_LABEL_TO_FAKER = {
    "person": "person",
    "phone number": "phone_number",
    "email": "email",
    "address": "address",
    "organization": "organization",
    "bank account number": "bank_account",
    "credit card number": "credit_card",
    "date of birth": "date_of_birth",
    "tax identification number": "pan",      # Maps to PAN for India
    "national id number": "aadhaar",         # Maps to Aadhaar for India
    "passport number": "passport",
    "ip address": "redact",
    "username": "redact",
}

# Severity mapping for GLiNER labels
GLINER_LABEL_SEVERITY = {
    "person": "HIGH",
    "phone number": "MEDIUM",
    "email": "MEDIUM",
    "address": "MEDIUM",
    "organization": "LOW",
    "bank account number": "CRITICAL",
    "credit card number": "CRITICAL",
    "date of birth": "MEDIUM",
    "tax identification number": "CRITICAL",
    "national id number": "CRITICAL",
    "passport number": "CRITICAL",
    "ip address": "LOW",
    "username": "MEDIUM",
}


class NERScanner:
    """
    Layer 2 Scanner: GLiNER-based context-aware NER for PII detection.
    
    The model is loaded lazily — only when scan_text() is first called.
    This avoids the ~5-10 second model load time when the pipeline
    only needs regex (Layer 1) for structured data.
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or _CONFIG
        self._model = None
        self._model_name = self.config.get("global", {}).get(
            "gliner_model", "urchade/gliner_multi_pii-v1"
        )
        self._threshold = self.config.get("global", {}).get("gliner_threshold", 0.4)
        self._labels = self.config.get("gliner_labels", list(GLINER_LABEL_TO_FAKER.keys()))

    def _load_model(self):
        """Lazy-load the GLiNER model."""
        if self._model is not None:
            return

        try:
            from gliner import GLiNER
            logger.info(f"Loading GLiNER model: {self._model_name}")
            self._model = GLiNER.from_pretrained(self._model_name)
            logger.info("GLiNER model loaded successfully")
        except ImportError:
            logger.warning(
                "GLiNER not installed. Layer 2 NER detection disabled. "
                "Install with: pip install gliner"
            )
            self._model = None
        except Exception as e:
            logger.error(f"Failed to load GLiNER model: {e}")
            self._model = None

    @property
    def is_available(self) -> bool:
        """Check if GLiNER is available (installed and model loadable)."""
        if self._model is None:
            self._load_model()
        return self._model is not None

    def scan_text(self, text: str) -> List[NERMatch]:
        """
        Scan free text for PII using GLiNER NER.
        
        Args:
            text: The text to scan (typically a free-text column value)
            
        Returns:
            List of NERMatch objects for all detected entities
        """
        if not text or not isinstance(text, str) or not text.strip():
            return []

        if not self.is_available:
            return []

        try:
            entities = self._model.predict_entities(
                text,
                self._labels,
                threshold=self._threshold
            )
        except Exception as e:
            logger.error(f"GLiNER prediction failed: {e}")
            return []

        matches = []
        for entity in entities:
            label = entity.get("label", "unknown")
            faker_method = GLINER_LABEL_TO_FAKER.get(label, "redact")
            severity = GLINER_LABEL_SEVERITY.get(label, "MEDIUM")

            match = NERMatch(
                entity_type=label,
                matched_text=entity.get("text", ""),
                start=entity.get("start", 0),
                end=entity.get("end", 0),
                confidence=entity.get("score", 0.0),
                faker_method=faker_method,
            )
            matches.append(match)

        return matches

    def scan_batch(self, texts: List[str]) -> List[List[NERMatch]]:
        """Scan multiple texts. Returns a list of match lists."""
        return [self.scan_text(t) for t in texts]
