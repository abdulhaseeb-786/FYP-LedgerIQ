"""Domain Data Contracts and Schemas for Document Digitizer & Edge OCR (Module 7)."""

from __future__ import annotations

from typing import List, Optional, Literal, Tuple, Dict, Any
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Spatial 2D bounding box with both normalized coordinates and pixel coordinates."""
    # Normalized [0.0 - 1.0] coordinates: standard for vision-language models
    ymin: float = Field(..., ge=0.0, le=1.0)
    xmin: float = Field(..., ge=0.0, le=1.0)
    ymax: float = Field(..., ge=0.0, le=1.0)
    xmax: float = Field(..., ge=0.0, le=1.0)
    # Absolute pixel coordinates
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @classmethod
    def from_pixels(cls, x1: int, y1: int, x2: int, y2: int, img_w: int, img_h: int, confidence: float = 1.0) -> BoundingBox:
        img_w = max(1, img_w)
        img_h = max(1, img_h)
        return cls(
            ymin=max(0.0, min(1.0, y1 / img_h)),
            xmin=max(0.0, min(1.0, x1 / img_w)),
            ymax=max(0.0, min(1.0, y2 / img_h)),
            xmax=max(0.0, min(1.0, x2 / img_w)),
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            confidence=confidence,
        )

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)

    @property
    def center_y(self) -> float:
        return (self.ymin + self.ymax) / 2.0

    @property
    def center_x(self) -> float:
        return (self.xmin + self.xmax) / 2.0

    def iou(self, other: BoundingBox) -> float:
        """Compute Intersection-over-Union with another bounding box."""
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)

        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        intersection = iw * ih

        area1 = self.width * self.height
        area2 = other.width * other.height
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0


class ExtractedToken(BaseModel):
    """Individual OCR or vision token extracted with spatial coordinates."""
    token_id: str
    text: str
    bbox: BoundingBox
    confidence: float = 1.0
    token_type: Optional[str] = "TEXT"
    reading_order_index: int = 0


class DocumentLineItem(BaseModel):
    """Extracted line item record from an invoice, receipt, or tax challan."""
    row_index: int
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: float
    account_code: Optional[str] = None
    debit: float = 0.0
    credit: float = 0.0
    bbox: Optional[BoundingBox] = None
    confidence: float = 1.0
    is_disambiguated: bool = False
    disambiguation_note: Optional[str] = None


class ExtractedDocument(BaseModel):
    """Structured document entity parsed from an image or scanned document."""
    document_id: str
    document_type: Literal[
        "RECEIPT",
        "TAX_CHALLAN",
        "VENDOR_INVOICE",
        "SCANNED_TRIAL_BALANCE",
        "UNKNOWN"
    ]
    document_no: Optional[str] = None
    date: Optional[str] = None
    vendor_or_entity: Optional[str] = None
    tax_id: Optional[str] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    discount: Optional[float] = None
    total: Optional[float] = None
    debits_total: Optional[float] = None
    credits_total: Optional[float] = None
    line_items: List[DocumentLineItem] = Field(default_factory=list)
    tokens: List[ExtractedToken] = Field(default_factory=list)
    dimensions: Tuple[int, int] = (800, 1000)
    skew_detected_deg: float = 0.0


class ArithmeticVerificationResult(BaseModel):
    """Result of deterministic closed-loop symbolic mathematical verification."""
    is_balanced: bool
    equation_checked: str
    calculated_sum: float
    target_total: float
    discrepancy_delta: float
    error_rows: List[int] = Field(default_factory=list)
    diagnosis: str
    recovery_applied: bool = False
    recovered_token_before: Optional[str] = None
    recovered_token_after: Optional[str] = None
    disputed_crops: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Bounding box pixel crops for UI Pane 3 visual auditor verification"
    )


class DigitizationResult(BaseModel):
    """Full outcome of the document digitization, OCR perception, and verification process."""
    document: ExtractedDocument
    verification: ArithmeticVerificationResult
    processing_latency_ms: float
    vram_usage_mb: float = 0.0
    execution_profile: str = "CPU_HIGH_PRECISION_PARSER"
    upstream_payload: Optional[Dict[str, Any]] = None

