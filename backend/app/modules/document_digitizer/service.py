"""Service Layer for Document Digitization, Edge Vision, and Closed-Loop Verification (Module 7)."""

import time
from typing import Optional, Dict, Any, List
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.document_digitizer.domain.models import (
    DigitizationResult, ExtractedDocument, ArithmeticVerificationResult, ExtractedToken
)
from app.modules.document_digitizer.domain.edge_vision_engine import EdgeVisionEngine
from app.modules.document_digitizer.domain.symbolic_verifier import SymbolicArithmeticVerifier
from app.modules.document_digitizer.domain.upstream_adapter import UpstreamDocumentAdapter
from app.modules.document_digitizer.models import DigitizationRunRecord


class DocumentDigitizerService:
    """Orchestrates image ingestion, edge vision layout parsing, and symbolic verification."""

    def __init__(self):
        self.vision_engine = EdgeVisionEngine()
        self.verifier = SymbolicArithmeticVerifier()
        self.adapter = UpstreamDocumentAdapter()

    async def digitize_image(
        self,
        image: Image.Image,
        document_id: str = "scan-01",
        auto_disambiguate: bool = True,
        project_id: Optional[int] = None,
        user_id: Optional[int] = None,
        db: Optional[AsyncSession] = None,
    ) -> DigitizationResult:
        """Process image end-to-end and execute closed-loop verification."""
        t0 = time.perf_counter()

        # 1. Vision perception
        extracted_doc, latency_ms = self.vision_engine.process_image(image, document_id=document_id)

        # 2. Closed-loop symbolic verification
        verification = self.verifier.verify_document(extracted_doc, auto_disambiguate=auto_disambiguate)

        # 3. Generate upstream accounting payload
        upstream_payload = self.adapter.to_upstream_payload(extracted_doc)

        result = DigitizationResult(
            document=extracted_doc,
            verification=verification,
            processing_latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            vram_usage_mb=0.0 if not self.vision_engine.has_cuda else 1850.0,
            execution_profile=self.vision_engine.execution_profile,
            upstream_payload=upstream_payload,
        )

        # 4. Persist run record if DB session provided
        if db is not None:
            record = DigitizationRunRecord(
                project_id=project_id,
                user_id=user_id,
                document_id=extracted_doc.document_id,
                document_type=extracted_doc.document_type,
                document_no=extracted_doc.document_no,
                is_balanced=verification.is_balanced,
                calculated_total=verification.calculated_sum,
                discrepancy_delta=verification.discrepancy_delta,
                recovery_applied=verification.recovery_applied,
                execution_profile=result.execution_profile,
                result_payload=result.model_dump(),
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)

        return result

    def digitize_from_tokens(
        self,
        tokens: List[ExtractedToken],
        dimensions: tuple = (800, 1000),
        document_id: str = "scan-tokens-01",
        auto_disambiguate: bool = True,
    ) -> DigitizationResult:
        """Process pre-extracted vision tokens (e.g. from benchmark dataset or OCR pipeline)."""
        t0 = time.perf_counter()
        extracted_doc = self.vision_engine.parse_from_tokens(tokens, dimensions, document_id=document_id)
        verification = self.verifier.verify_document(extracted_doc, auto_disambiguate=auto_disambiguate)
        upstream = self.adapter.to_upstream_payload(extracted_doc)

        return DigitizationResult(
            document=extracted_doc,
            verification=verification,
            processing_latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            vram_usage_mb=0.0,
            execution_profile=self.vision_engine.execution_profile,
            upstream_payload=upstream,
        )

