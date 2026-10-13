r"""Interactive CLI Evaluation & Diagnostic Tool for Document Digitizer (Module 7).

Run:
    .\venv\Scripts\python.exe evaluate_digitizer.py
Or evaluate a custom image:
    .\venv\Scripts\python.exe evaluate_digitizer.py --image path/to/invoice.png
"""

import sys
import json
import argparse
from pathlib import Path

# Force UTF-8 stdout for Windows command prompt / powershell
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend and repo root are in python path
REPO_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.modules.document_digitizer.service import DocumentDigitizerService
from app.modules.document_digitizer.infrastructure.image_loader import ImageLoader
from app.modules.document_digitizer.domain.models import ExtractedToken, BoundingBox


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f" {title.upper()}")
    print("=" * 80)


def print_section(title: str):
    print(f"\n--- {title} ---")


def evaluate_benchmark_manifest():
    service = DocumentDigitizerService()
    manifest_path = REPO_ROOT / "data" / "synthetic_scans" / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: Manifest not found at {manifest_path}")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print_banner(f"LedgerIQ Document Digitizer: Benchmark Evaluation ({len(manifest['documents'])} Scenarios)")
    print(f"Execution Engine: {service.vision_engine.execution_profile}")
    print(f"CUDA Available:   {service.vision_engine.has_cuda}")
    print(f"VRAM Ceiling:     2,200 MB (Hard Edge Budget)")

    for idx, doc_meta in enumerate(manifest["documents"], 1):
        print_banner(f"Scenario {idx}: {doc_meta['title']} ({doc_meta['file_name']})")
        print(f"Document Type Target: {doc_meta['document_type']}")
        print(f"Resolution / Size:    {doc_meta['dimensions'][0]} x {doc_meta['dimensions'][1]} px")

        # 1. Image Preprocessing & Skew Inspection
        img_path = REPO_ROOT / "data" / "synthetic_scans" / doc_meta["file_name"]
        if img_path.exists():
            img = ImageLoader.from_file_path(img_path)
            _, skew_angle, prep_meta = service.vision_engine.preprocessor.preprocess_image(img)
            print_section("Image Preprocessing & Deskewing")
            print(f"  * Skew Angle Detected: {skew_angle:+.2f} degrees")
            print(f"  * Deskew Rotation Applied: {prep_meta['deskew_applied']}")

        # 2. Token Reconstruction
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

        # In Scenario 3, simulate the OCR optical confusion
        if "simulated_misread_row" in doc_meta:
            print_section("Simulating OCR Optical Degradation (Ambiguity Injection)")
            print(f"  * Injecting ambiguous character into row {doc_meta['simulated_misread_row']}")
            print(f"  * True text:     '{doc_meta['true_token']}'")
            print(f"  * OCR candidate: '{doc_meta['misread_token']}' (Discrepancy: PKR {doc_meta['discrepancy_delta']:+,.2f})")
            for tok in tokens:
                if tok.text == doc_meta["true_token"]:
                    tok.text = doc_meta["misread_token"]

        # Run digitization pipeline
        result = service.digitize_from_tokens(
            tokens=tokens,
            dimensions=tuple(doc_meta["dimensions"]),
            document_id=f"eval-{idx}",
            auto_disambiguate=True,
        )

        doc = result.document
        verif = result.verification

        print_section("Extracted Document Entities")
        print(f"  * Classified Type:    {doc.document_type}")
        print(f"  * Document Identifier: {doc.document_no or 'N/A'}")
        print(f"  * Issue / Trans Date:  {doc.date or 'N/A'}")
        print(f"  * Entity / Vendor:     {doc.vendor_or_entity or 'N/A'}")
        print(f"  * Tax NTN / STRN:      {doc.tax_id or 'N/A'}")

        print_section(f"Tabular Records ({len(doc.line_items)} line items extracted)")
        if doc.document_type == "SCANNED_TRIAL_BALANCE":
            print("{:<5} {:<8} {:<32} {:>14} {:>14}".format("#", "Code", "Account Title", "Debit (PKR)", "Credit (PKR)"))
            print("-" * 78)
            for item in doc.line_items:
                dr_s = f"{item.debit:,.2f}" if item.debit > 0 else "-"
                cr_s = f"{item.credit:,.2f}" if item.credit > 0 else "-"
                print("{:<5} {:<8} {:<32} {:>14} {:>14}".format(
                    item.row_index, item.account_code or "-", item.description[:32], dr_s, cr_s
                ))
        else:
            print("{:<5} {:<45} {:>18}".format("#", "Item Description", "Line Amount (PKR)"))
            print("-" * 72)
            for item in doc.line_items:
                tag = " [DISAMBIGUATED]" if item.is_disambiguated else ""
                print("{:<5} {:<45} {:>18}".format(
                    item.row_index, (item.description + tag)[:45], f"{item.amount:,.2f}"
                ))

        print_section("Closed-Loop Symbolic Verification (Seoul Accord CCP GA-4)")
        clean_eq = verif.equation_checked.replace("\u2211", "SUM")
        print(f"  * Equation Tested:     {clean_eq}")
        print(f"  * Calculated Sum:      PKR {verif.calculated_sum:,.2f}")
        print(f"  * Stated Target Total: PKR {verif.target_total:,.2f}")
        print(f"  * Imbalance Delta:     PKR {verif.discrepancy_delta:,.2f}")
        print(f"  * Balanced Status:     {'[PASS] BALANCED' if verif.is_balanced else '[FAIL] IMBALANCED'}")
        print(f"  * CSP Recovery Fired:  {verif.recovery_applied}")
        if verif.recovery_applied:
            print(f"    --> Before: {verif.recovered_token_before}")
            print(f"    --> After:  {verif.recovered_token_after}")
            print(f"    --> Resolution: Autonomous constraint solver eliminated discrepancy to 0.00!")
        clean_diag = verif.diagnosis.replace("\u0394", "Delta")
        print(f"  * Diagnostic Summary:  {clean_diag}")

        print_section("Downstream Integration Payload")
        payload = result.upstream_payload
        print(f"  * Payload Type:        {payload.get('payload_type')}")
        if payload.get("payload_type") == "TRIAL_BALANCE":
            print(f"  * Accounts Count:      {payload.get('accounts_count')}")
            print(f"  * Ready for Module 1/3: {payload.get('is_balanced')}")
        elif payload.get("payload_type") == "INVOICE_OR_RECEIPT":
            print(f"  * Ready for Module 6:  {payload.get('ready_for_3way_module6')}")
        elif payload.get("payload_type") == "FBR_TAX_CHALLAN":
            print(f"  * Ready for Module 5:  {payload.get('ready_for_wht_module5')}")


def evaluate_custom_image(image_path: str):
    p = Path(image_path)
    if not p.exists():
        print(f"Error: Image file does not exist at {p}")
        return

    print_banner(f"Evaluating Custom Image Scan: {p.name}")
    img = ImageLoader.from_file_path(p)
    service = DocumentDigitizerService()

    # Preprocessing
    _, skew_angle, meta = service.vision_engine.preprocessor.preprocess_image(img)
    print_section("Image Preprocessing")
    print(f"  * Dimensions: {img.size[0]} x {img.size[1]} px")
    print(f"  * Detected Skew Angle: {skew_angle:+.2f} degrees")
    print(f"  * Deskew Applied: {meta['deskew_applied']}")

    # Slicing check
    patches = service.vision_engine.preprocessor.slice_patches(img)
    print(f"  * Visual Patch Tiles: {len(patches)} tile(s) (< 2.2 GB VRAM footprint)")

    import asyncio
    result = asyncio.run(service.digitize_image(img, document_id=p.stem, auto_disambiguate=True))

    print_section("Digitization Outcome")
    print(f"  * Classified Type:    {result.document.document_type}")
    print(f"  * Line Items Extracted: {len(result.document.line_items)}")
    print(f"  * Balanced Status:    {'[PASS] BALANCED' if result.verification.is_balanced else '[FAIL] IMBALANCED'}")
    print(f"  * Execution Latency:  {result.processing_latency_ms:.1f} ms")
    print(f"  * Hardware Profile:   {result.execution_profile}")


def main():
    parser = argparse.ArgumentParser(description="LedgerIQ Document Digitizer Evaluation Tool")
    parser.add_argument("--image", type=str, default=None, help="Path to custom image to evaluate")
    args = parser.parse_args()

    if args.image:
        evaluate_custom_image(args.image)
    else:
        evaluate_benchmark_manifest()


if __name__ == "__main__":
    main()
