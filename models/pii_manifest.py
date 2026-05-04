"""
PII Manifest Models — Structured audit output for the masking pipeline.

These Pydantic models define the structured output that accompanies every
masked dataset. The manifest powers:
- Quality reports (what was detected, where, with what confidence)
- Audit trails (which detector found what)
- Compliance documentation (DPDP/GDPR evidence)
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DetectorType(str, Enum):
    REGEX = "REGEX"
    GLINER = "GLINER"
    PRESIDIO = "PRESIDIO"


class PIIDetection(BaseModel):
    """A single PII detection event."""
    entity_type: str = Field(..., description="Type of PII detected (e.g., INDIAN_PAN, person)")
    original_value: str = Field(default="[REDACTED_FROM_LOG]", description="Original value — only stored if log_raw=True")
    masked_value: str = Field(..., description="The Faker-generated replacement value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    detector: DetectorType = Field(..., description="Which detector found this (REGEX, GLINER, PRESIDIO)")
    severity: Severity = Field(..., description="Risk severity level")
    column: str = Field(..., description="Column name where the PII was found")
    row_index: int = Field(..., description="Row index in the DataFrame")
    action: str = Field(default="REDACTED", description="Action taken based on confidence (REDACTED, REVIEW, LOG_ONLY)")


class ColumnSummary(BaseModel):
    """Summary statistics for PII detected in a single column."""
    column_name: str
    total_detections: int = 0
    detection_breakdown: Dict[str, int] = Field(default_factory=dict, description="Count per PII type")
    detector_breakdown: Dict[str, int] = Field(default_factory=dict, description="Count per detector")
    severity_breakdown: Dict[str, int] = Field(default_factory=dict, description="Count per severity")
    masking_action: str = Field(default="faker_substitution", description="What masking action was applied")


class ValidationPassResult(BaseModel):
    """Result of a single Layer 3 validation pass."""
    pass_number: int
    pii_found: int = Field(..., description="Number of PII instances found in re-scan")
    types_found: List[str] = Field(default_factory=list)
    is_clean: bool = Field(default=False, description="True if no PII found in this pass")


class PIIManifest(BaseModel):
    """
    The complete audit manifest for a masking run.
    
    This is generated alongside every masked dataset and contains:
    - Summary statistics (total detections, by type, by severity)
    - Per-column breakdowns
    - Validation pass results
    - Processing metadata
    """
    # --- Metadata ---
    pipeline_version: str = Field(default="3.0.0")
    timestamp: datetime = Field(default_factory=datetime.now)
    total_rows: int = 0
    total_columns: int = 0
    processing_time_seconds: float = 0.0
    
    # --- Detection Summary ---
    total_pii_detected: int = 0
    total_pii_masked: int = 0
    detection_by_type: Dict[str, int] = Field(default_factory=dict)
    detection_by_severity: Dict[str, int] = Field(default_factory=dict)
    detection_by_detector: Dict[str, int] = Field(default_factory=dict)
    
    # --- Per-Column Detail ---
    column_summaries: List[ColumnSummary] = Field(default_factory=list)
    
    # --- Validation ---
    validation_passes: List[ValidationPassResult] = Field(default_factory=list)
    final_clean: bool = Field(default=False, description="True if all validation passes are clean")
    
    # --- Detections (without raw values for log safety) ---
    detections: List[PIIDetection] = Field(default_factory=list)

    def add_detection(self, detection: PIIDetection):
        """Add a detection and update all summary counters."""
        self.detections.append(detection)
        self.total_pii_detected += 1
        self.total_pii_masked += 1

        # Update type counter
        self.detection_by_type[detection.entity_type] = \
            self.detection_by_type.get(detection.entity_type, 0) + 1

        # Update severity counter
        self.detection_by_severity[detection.severity.value] = \
            self.detection_by_severity.get(detection.severity.value, 0) + 1

        # Update detector counter
        self.detection_by_detector[detection.detector.value] = \
            self.detection_by_detector.get(detection.detector.value, 0) + 1

    def build_column_summaries(self):
        """Build per-column summary from accumulated detections."""
        col_map: Dict[str, ColumnSummary] = {}
        for det in self.detections:
            if det.column not in col_map:
                col_map[det.column] = ColumnSummary(column_name=det.column)
            summary = col_map[det.column]
            summary.total_detections += 1
            summary.detection_breakdown[det.entity_type] = \
                summary.detection_breakdown.get(det.entity_type, 0) + 1
            summary.detector_breakdown[det.detector.value] = \
                summary.detector_breakdown.get(det.detector.value, 0) + 1
            summary.severity_breakdown[det.severity.value] = \
                summary.severity_breakdown.get(det.severity.value, 0) + 1
        self.column_summaries = list(col_map.values())

    def to_safe_dict(self) -> dict:
        """Export manifest WITHOUT raw PII values (safe for logging)."""
        data = self.model_dump()
        # Strip original_value from all detections for log safety
        for det in data.get("detections", []):
            det["original_value"] = "[REDACTED_FROM_LOG]"
        return data
