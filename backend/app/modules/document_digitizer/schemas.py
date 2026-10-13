"""Pydantic v2 API Schemas and DTOs for Document Digitizer (Module 7)."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.modules.document_digitizer.domain.models import DigitizationResult, ArithmeticVerificationResult


class DigitizeImageRequest(BaseModel):
    """Request payload for processing an image scan."""
    document_id: str = "scan-01"
    image_base64: Optional[str] = Field(None, description="Base64-encoded image string")
    auto_disambiguate: bool = Field(True, description="Enable closed-loop CSP character disambiguation")
    project_id: Optional[int] = None


class DisambiguateCropRequest(BaseModel):
    """Auditor request to manually confirm or override a disputed row crop."""
    document_id: str
    row_index: int
    manual_amount_override: Optional[float] = None
    confirmed_token: Optional[str] = None


class HardwareProfileResponse(BaseModel):
    """Telemetry report for edge hardware constraints."""
    device: str
    has_cuda: bool
    vram_ceiling_mb: float = 2200.0
    active_engine: str
    zero_cloud_exfiltration_guarantee: bool = True

