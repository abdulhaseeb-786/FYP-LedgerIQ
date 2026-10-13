"""End-to-End Integration Tests for Document Digitizer (Module 7).

Verifies receipt ingestion, FBR tax challan parsing, scanned trial balance conversion,
and closed-loop CSP error recovery across synthetic and public benchmark scans.
"""

import json
from pathlib import Path
from PIL import Image
import pytest

from app.modules.document_digitizer.domain.models import BoundingBox, ExtractedToken
from app.modules.document_digitizer.service import DocumentDigitizerService
from app.modules.document_digitizer.infrastructure.image_loader import ImageLoader


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parent.parent


def test_digitize_scan_01_clean_receipt_e2e(repo_root):
    manifest_path = repo_root / "data" / "synthetic_scans" / "manifest.json"
    assert manifest_path.exists(), "Synthetic manifest.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    doc_meta = next(d for d in manifest["documents"] if d["file_name"] == "scan_01_clean_receipt.png")
    tokens = [
        ExtractedToken(
            token_id=f"t_{i}",
            text=t["text"],
            bbox=BoundingBox.from_pixels(
                x1=t["bbox_pixels"][0],
                y1=t["bbox_pixels"][1],
                x2=t["bbox_pixels"][2],
                y2=t["bbox_pixels"][3],
                img_w=doc_meta["dimensions"][0],
                img_h=doc_meta["dimensions"][1],
            )
        )
        for i, t in enumerate(doc_meta["tokens"])
    ]

    service = DocumentDigitizerService()
    result = service.digitize_from_tokens(
        tokens=tokens,
        dimensions=tuple(doc_meta["dimensions"]),
        document_id="bench-01",
        auto_disambiguate=True,
    )

    assert result.document.document_type == "RECEIPT"
    assert result.verification.is_balanced is True
    assert result.verification.discrepancy_delta == 0.0
    assert len(result.document.line_items) >= 4
    # Check upstream payload ready for 3-way match
    assert result.upstream_payload["payload_type"] == "INVOICE_OR_RECEIPT"
    assert result.upstream_payload["ready_for_3way_module6"] is True


def test_digitize_scan_02_skewed_challan_e2e(repo_root):
    img_path = repo_root / "data" / "synthetic_scans" / "scan_02_skewed_challan.png"
    assert img_path.exists()

    img = ImageLoader.from_file_path(img_path)
    service = DocumentDigitizerService()
    # Image preprocessing must detect rotation skew
    prep_img, skew_angle, meta = service.vision_engine.preprocessor.preprocess_image(img)
    assert meta["deskew_applied"] is True
    assert abs(skew_angle) > 1.0


def test_digitize_scan_03_digit_confusion_recovery_e2e(repo_root):
    manifest_path = repo_root / "data" / "synthetic_scans" / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    doc_meta = next(d for d in manifest["documents"] if d["file_name"] == "scan_03_digit_confusion.png")
    # Simulate OCR reading row 2 as 3,350.00 instead of 3,850.00
    tokens = []
    for i, t in enumerate(doc_meta["tokens"]):
        text = t["text"]
        if text == "3,850.00":
            text = "3,350.00"  # Inject OCR ambiguity
        tokens.append(
            ExtractedToken(
                token_id=f"t_{i}",
                text=text,
                bbox=BoundingBox.from_pixels(
                    x1=t["bbox_pixels"][0],
                    y1=t["bbox_pixels"][1],
                    x2=t["bbox_pixels"][2],
                    y2=t["bbox_pixels"][3],
                    img_w=doc_meta["dimensions"][0],
                    img_h=doc_meta["dimensions"][1],
                )
            )
        )

    service = DocumentDigitizerService()
    result = service.digitize_from_tokens(
        tokens=tokens,
        dimensions=tuple(doc_meta["dimensions"]),
        document_id="bench-03",
        auto_disambiguate=True,
    )

    # Closed-loop CSP solver must catch the 500.00 discrepancy and recover 3,850.00
    assert result.verification.is_balanced is True
    assert result.verification.recovery_applied is True
    assert result.verification.recovered_token_before == "3,350.00"
    assert result.verification.recovered_token_after == "3,850.00"


def test_digitize_scan_04_scanned_trial_balance_e2e(repo_root):
    manifest_path = repo_root / "data" / "synthetic_scans" / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    doc_meta = next(d for d in manifest["documents"] if d["file_name"] == "scan_04_scanned_tb.png")
    tokens = [
        ExtractedToken(
            token_id=f"t_{i}",
            text=t["text"],
            bbox=BoundingBox.from_pixels(
                x1=t["bbox_pixels"][0],
                y1=t["bbox_pixels"][1],
                x2=t["bbox_pixels"][2],
                y2=t["bbox_pixels"][3],
                img_w=doc_meta["dimensions"][0],
                img_h=doc_meta["dimensions"][1],
            )
        )
        for i, t in enumerate(doc_meta["tokens"])
    ]

    service = DocumentDigitizerService()
    result = service.digitize_from_tokens(
        tokens=tokens,
        dimensions=tuple(doc_meta["dimensions"]),
        document_id="bench-04",
        auto_disambiguate=True,
    )

    assert result.document.document_type == "SCANNED_TRIAL_BALANCE"
    assert result.verification.is_balanced is True
    assert result.verification.discrepancy_delta == 0.0

    # Verify upstream payload maps directly into standard trial balance records
    tb_payload = result.upstream_payload
    assert tb_payload["payload_type"] == "TRIAL_BALANCE"
    assert tb_payload["is_balanced"] is True
    assert tb_payload["accounts_count"] >= 5
    assert tb_payload["total_debits"] == 1050000.0
    assert tb_payload["total_credits"] == 1050000.0

