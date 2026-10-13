"""Generator for parameter-calibrated synthetic document scans (Module 7).

Produces realistic synthetic images (receipts, FBR tax challans, scanned trial balances)
with pixel-exact bounding box ground truth annotations and arithmetic constraints.
"""

import os
import json
import math
from pathlib import Path
from typing import Dict, List, Any, Tuple
from PIL import Image, ImageDraw, ImageFont


def _draw_text_with_bbox(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.ImageFont,
    fill=(20, 25, 35),
    img_width: int = 800,
    img_height: int = 1000,
) -> Dict[str, Any]:
    """Draw text and compute both absolute and normalized bounding box coordinates."""
    draw.text((x, y), text, font=font, fill=fill)
    bbox = draw.textbbox((x, y), text, font=font)
    x1, y1, x2, y2 = bbox
    # Normalized [ymin, xmin, ymax, xmax] standard for vision models
    norm_bbox = [
        round(y1 / img_height, 4),
        round(x1 / img_width, 4),
        round(y2 / img_height, 4),
        round(x2 / img_width, 4),
    ]
    return {
        "text": text,
        "bbox_pixels": [x1, y1, x2, y2],
        "bbox_normalized": norm_bbox,
        "width": x2 - x1,
        "height": y2 - y1,
    }


def generate_scan_01_clean_receipt(out_dir: Path) -> Dict[str, Any]:
    """Render a clean retail/commercial receipt with line items, tax, and total."""
    width, height = 750, 950
    img = Image.new("RGB", (width, height), color=(250, 250, 252))
    draw = ImageDraw.ImageDraw(img)

    # Use default font or basic bitmap font
    font_lg = ImageFont.load_default()
    font_md = ImageFont.load_default()

    tokens = []

    # Header
    tokens.append(_draw_text_with_bbox(draw, 180, 40, "METRO CASH & CARRY PAKISTAN LTD", font_lg, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 240, 65, "NTN: 1429841-7  |  STRN: 07-02-9999-012", font_md, (71, 85, 105), width, height))
    tokens.append(_draw_text_with_bbox(draw, 220, 85, "TAX INVOICE / CASH RECEIPT #REC-2025-8831", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 290, 105, "DATE: 2025-06-15 14:32:10", font_md, (71, 85, 105), width, height))

    # Divider line
    draw.line([(50, 130), (700, 130)], fill=(203, 213, 225), width=2)

    # Column Headers
    tokens.append(_draw_text_with_bbox(draw, 60, 145, "ITEM DESCRIPTION", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 420, 145, "QTY", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 500, 145, "RATE", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 610, 145, "AMOUNT", font_md, (15, 23, 42), width, height))

    draw.line([(50, 165), (700, 165)], fill=(148, 163, 184), width=1)

    items_data = [
        ("Office Paper A4 80gsm (5 Reams)", 5, 1200.0, 6000.0),
        ("Laser Toner Cartridge HP-85A", 2, 8500.0, 17000.0),
        ("Desk Organizer Mesh Tray Black", 4, 750.0, 3000.0),
        ("Heavy Duty Desktop Stapler 100p", 1, 1500.0, 1500.0),
    ]

    line_items_meta = []
    y = 185
    for idx, (desc, qty, rate, amt) in enumerate(items_data, 1):
        t_desc = _draw_text_with_bbox(draw, 60, y, desc, font_md, (30, 41, 59), width, height)
        t_qty = _draw_text_with_bbox(draw, 425, y, str(qty), font_md, (30, 41, 59), width, height)
        t_rate = _draw_text_with_bbox(draw, 495, y, f"{rate:,.2f}", font_md, (30, 41, 59), width, height)
        t_amt = _draw_text_with_bbox(draw, 605, y, f"{amt:,.2f}", font_md, (30, 41, 59), width, height)
        tokens.extend([t_desc, t_qty, t_rate, t_amt])

        line_items_meta.append({
            "row_index": idx,
            "description": desc,
            "quantity": qty,
            "rate": rate,
            "amount": amt,
            "bbox_pixels": t_amt["bbox_pixels"],
            "bbox_normalized": t_amt["bbox_normalized"],
        })
        y += 35

    draw.line([(50, y + 10), (700, y + 10)], fill=(203, 213, 225), width=2)
    y += 25

    # Totals
    subtotal = 27500.0
    tax = 4950.0  # 18% Sales Tax
    discount = 1375.0  # 5% Discount
    grand_total = subtotal + tax - discount

    tokens.append(_draw_text_with_bbox(draw, 450, y, "SUBTOTAL:", font_md, (30, 41, 59), width, height))
    tokens.append(_draw_text_with_bbox(draw, 605, y, f"{subtotal:,.2f}", font_md, (30, 41, 59), width, height))
    y += 30

    tokens.append(_draw_text_with_bbox(draw, 450, y, "SALES TAX (18%):", font_md, (30, 41, 59), width, height))
    tokens.append(_draw_text_with_bbox(draw, 605, y, f"{tax:,.2f}", font_md, (30, 41, 59), width, height))
    y += 30

    tokens.append(_draw_text_with_bbox(draw, 450, y, "DISCOUNT (5%):", font_md, (30, 41, 59), width, height))
    tokens.append(_draw_text_with_bbox(draw, 605, y, f"-{discount:,.2f}", font_md, (30, 41, 59), width, height))
    y += 35

    draw.line([(440, y - 5), (700, y - 5)], fill=(15, 23, 42), width=2)
    t_tot_label = _draw_text_with_bbox(draw, 450, y, "TOTAL PAYABLE (PKR):", font_md, (15, 23, 42), width, height)
    t_tot_val = _draw_text_with_bbox(draw, 595, y, f"{grand_total:,.2f}", font_md, (15, 23, 42), width, height)
    tokens.extend([t_tot_label, t_tot_val])
    draw.line([(440, y + 25), (700, y + 25)], fill=(15, 23, 42), width=3)

    # Footer
    tokens.append(_draw_text_with_bbox(draw, 220, y + 60, "THANK YOU FOR SHOPPING WITH US", font_md, (100, 116, 139), width, height))

    img_path = out_dir / "scan_01_clean_receipt.png"
    img.save(img_path)

    return {
        "file_name": "scan_01_clean_receipt.png",
        "document_type": "RECEIPT",
        "title": "Clean Retail Receipt",
        "document_no": "REC-2025-8831",
        "date": "2025-06-15",
        "vendor": "METRO CASH & CARRY PAKISTAN LTD",
        "dimensions": [width, height],
        "subtotal": subtotal,
        "tax": tax,
        "discount": discount,
        "total": grand_total,
        "is_arithmetically_balanced": True,
        "line_items": line_items_meta,
        "tokens": tokens,
    }


def generate_scan_02_skewed_challan(out_dir: Path) -> Dict[str, Any]:
    """Render an FBR Computerized Payment Receipt (tax challan) with rotation skew."""
    width, height = 800, 1000
    img = Image.new("RGB", (width, height), color=(253, 252, 248))
    draw = ImageDraw.ImageDraw(img)
    font_md = ImageFont.load_default()

    tokens = []

    # FBR CPR Header
    tokens.append(_draw_text_with_bbox(draw, 220, 50, "GOVERNMENT OF PAKISTAN - REVENUE DIVISION", font_md, (20, 83, 45), width, height))
    tokens.append(_draw_text_with_bbox(draw, 240, 75, "FEDERAL BOARD OF REVENUE (FBR)", font_md, (20, 83, 45), width, height))
    tokens.append(_draw_text_with_bbox(draw, 200, 100, "COMPUTERIZED PAYMENT RECEIPT (CPR) - SRO 2025", font_md, (15, 23, 42), width, height))

    draw.rectangle([(50, 130), (750, 220)], outline=(30, 41, 59), width=2)
    tokens.append(_draw_text_with_bbox(draw, 65, 140, "CPR NUMBER: IT-202506-0091-8842", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 450, 140, "PAYMENT DATE: 2025-06-20", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 65, 165, "TAXPAYER NAME: INDUS INDUSTRIAL ENTERPRISES PVT LTD", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 65, 190, "NTN: 3081920-4  |  TAX PERIOD: TAX YEAR 2025", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 450, 190, "SECTION: 153(1)(a) WHT SUPPLIES", font_md, (15, 23, 42), width, height))

    # Payment Breakdown Box
    draw.rectangle([(50, 250), (750, 430)], outline=(100, 116, 139), width=1)
    tokens.append(_draw_text_with_bbox(draw, 70, 265, "PAYMENT PARTICULARS", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 580, 265, "AMOUNT (PKR)", font_md, (15, 23, 42), width, height))
    draw.line([(50, 290), (750, 290)], fill=(148, 163, 184), width=1)

    items = [
        ("Income Tax Withheld on Raw Material Purchases", 115000.0),
        ("Default Surcharge / Late Surcharge", 0.0),
        ("Penalty / Administrative Surcharge", 0.0),
        ("Provincial Sales Tax Withholding Deductions", 10000.0),
    ]

    line_items_meta = []
    y = 305
    for idx, (desc, amt) in enumerate(items, 1):
        t_d = _draw_text_with_bbox(draw, 70, y, desc, font_md, (51, 65, 85), width, height)
        t_a = _draw_text_with_bbox(draw, 600, y, f"{amt:,.2f}", font_md, (15, 23, 42), width, height)
        tokens.extend([t_d, t_a])
        line_items_meta.append({
            "row_index": idx,
            "description": desc,
            "amount": amt,
            "bbox_pixels": t_a["bbox_pixels"],
            "bbox_normalized": t_a["bbox_normalized"],
        })
        y += 28

    draw.line([(50, y + 5), (750, y + 5)], fill=(30, 41, 59), width=2)
    y += 18
    total_tax = 125000.0
    t_tot_label = _draw_text_with_bbox(draw, 70, y, "TOTAL AMOUNT DEPOSITED IN STATE BANK:", font_md, (15, 23, 42), width, height)
    t_tot_val = _draw_text_with_bbox(draw, 590, y, f"{total_tax:,.2f}", font_md, (15, 23, 42), width, height)
    tokens.extend([t_tot_label, t_tot_val])

    # Bank stamp box
    draw.rectangle([(50, 470), (400, 560)], outline=(148, 163, 184), width=1)
    tokens.append(_draw_text_with_bbox(draw, 60, 485, "NATIONAL BANK OF PAKISTAN - MAIN BRANCH", font_md, (71, 85, 105), width, height))
    tokens.append(_draw_text_with_bbox(draw, 60, 510, "CASH RECEIVED & SCROLL GENERATED", font_md, (22, 101, 52), width, height))
    tokens.append(_draw_text_with_bbox(draw, 60, 535, "AUTHORIZED OFFICER SIGN & STAMP", font_md, (100, 116, 139), width, height))

    # Apply 3.0-degree rotation to simulate realistic scanner skew
    rotated_img = img.rotate(3.0, expand=False, fillcolor=(253, 252, 248), resample=Image.BICUBIC)
    img_path = out_dir / "scan_02_skewed_challan.png"
    rotated_img.save(img_path)

    return {
        "file_name": "scan_02_skewed_challan.png",
        "document_type": "TAX_CHALLAN",
        "title": "FBR CPR Tax Challan (Skewed)",
        "document_no": "IT-202506-0091-8842",
        "date": "2025-06-20",
        "vendor": "FEDERAL BOARD OF REVENUE (FBR)",
        "taxpayer": "INDUS INDUSTRIAL ENTERPRISES PVT LTD",
        "dimensions": [width, height],
        "skew_angle_deg": 3.0,
        "subtotal": total_tax,
        "tax": 0.0,
        "discount": 0.0,
        "total": total_tax,
        "is_arithmetically_balanced": True,
        "line_items": line_items_meta,
        "tokens": tokens,
    }


def generate_scan_03_digit_confusion(out_dir: Path) -> Dict[str, Any]:
    """
    Render a receipt with intentional digit ambiguity (8 vs 3) to test closed-loop CSP recovery.
    True row 2 amount = 3,850.00.
    Simulated OCR confusion text = 3,350.00 (Delta = 500.00).
    Total = 12,036.00.
    """
    width, height = 700, 850
    img = Image.new("RGB", (width, height), color=(252, 252, 250))
    draw = ImageDraw.ImageDraw(img)
    font_md = ImageFont.load_default()

    tokens = []
    tokens.append(_draw_text_with_bbox(draw, 180, 40, "AL-MADINA HARDWARE & ELECTRICALS", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 220, 65, "BILL / CASH MEMO #MH-7719", font_md, (71, 85, 105), width, height))
    tokens.append(_draw_text_with_bbox(draw, 260, 85, "DATE: 2025-06-22", font_md, (71, 85, 105), width, height))

    draw.line([(40, 110), (660, 110)], fill=(203, 213, 225), width=2)
    tokens.append(_draw_text_with_bbox(draw, 50, 125, "ITEM", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 550, 125, "AMOUNT", font_md, (15, 23, 42), width, height))
    draw.line([(40, 145), (660, 145)], fill=(148, 163, 184), width=1)

    items = [
        ("Electrical Wiring Spool 3-Core 90m", 4200.0, "4,200.00"),
        ("Circuit Breaker 32A Triple Pole", 3850.0, "3,850.00"),  # Ambiguity target
        ("PVC Conduit Pipe 10ft Bundle", 2150.0, "2,150.00"),
    ]

    line_items_meta = []
    y = 165
    for idx, (desc, amt, text_val) in enumerate(items, 1):
        t_d = _draw_text_with_bbox(draw, 50, y, desc, font_md, (30, 41, 59), width, height)
        t_a = _draw_text_with_bbox(draw, 545, y, text_val, font_md, (30, 41, 59), width, height)
        tokens.extend([t_d, t_a])

        line_items_meta.append({
            "row_index": idx,
            "description": desc,
            "amount": amt,
            "ocr_confused_candidate": "3,350.00" if idx == 2 else text_val,
            "bbox_pixels": t_a["bbox_pixels"],
            "bbox_normalized": t_a["bbox_normalized"],
        })
        y += 35

    draw.line([(40, y + 10), (660, y + 10)], fill=(203, 213, 225), width=2)
    y += 25

    subtotal = 10200.0
    tax = 1836.0  # 18%
    total = 12036.0

    tokens.append(_draw_text_with_bbox(draw, 420, y, "SUBTOTAL:", font_md, (30, 41, 59), width, height))
    tokens.append(_draw_text_with_bbox(draw, 545, y, f"{subtotal:,.2f}", font_md, (30, 41, 59), width, height))
    y += 30

    tokens.append(_draw_text_with_bbox(draw, 420, y, "SALES TAX (18%):", font_md, (30, 41, 59), width, height))
    tokens.append(_draw_text_with_bbox(draw, 545, y, f"{tax:,.2f}", font_md, (30, 41, 59), width, height))
    y += 35

    draw.line([(400, y - 5), (660, y - 5)], fill=(15, 23, 42), width=2)
    t_tot_label = _draw_text_with_bbox(draw, 420, y, "GRAND TOTAL (PKR):", font_md, (15, 23, 42), width, height)
    t_tot_val = _draw_text_with_bbox(draw, 540, y, f"{total:,.2f}", font_md, (15, 23, 42), width, height)
    tokens.extend([t_tot_label, t_tot_val])
    draw.line([(400, y + 25), (660, y + 25)], fill=(15, 23, 42), width=3)

    img_path = out_dir / "scan_03_digit_confusion.png"
    img.save(img_path)

    return {
        "file_name": "scan_03_digit_confusion.png",
        "document_type": "RECEIPT",
        "title": "Receipt with Digit Confusion (8 vs 3)",
        "document_no": "MH-7719",
        "date": "2025-06-22",
        "vendor": "AL-MADINA HARDWARE & ELECTRICALS",
        "dimensions": [width, height],
        "subtotal": subtotal,
        "tax": tax,
        "discount": 0.0,
        "total": total,
        "is_arithmetically_balanced": True,
        "simulated_misread_row": 2,
        "misread_token": "3,350.00",
        "true_token": "3,850.00",
        "discrepancy_delta": 500.0,
        "line_items": line_items_meta,
        "tokens": tokens,
    }


def generate_scan_04_scanned_tb(out_dir: Path) -> Dict[str, Any]:
    """Render a multi-column scanned Trial Balance with Debit and Credit parity."""
    width, height = 850, 750
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.ImageDraw(img)
    font_md = ImageFont.load_default()

    tokens = []
    tokens.append(_draw_text_with_bbox(draw, 240, 40, "CRESCENT TEXTILE MILLS LIMITED", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 270, 65, "UNADJUSTED WORKING TRIAL BALANCE", font_md, (30, 41, 59), width, height))
    tokens.append(_draw_text_with_bbox(draw, 310, 85, "AS AT JUNE 30, 2025", font_md, (100, 116, 139), width, height))

    draw.rectangle([(50, 120), (800, 160)], fill=(241, 245, 249), outline=(148, 163, 184))
    tokens.append(_draw_text_with_bbox(draw, 65, 135, "CODE", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 140, 135, "ACCOUNT TITLE", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 520, 135, "DEBIT (PKR)", font_md, (15, 23, 42), width, height))
    tokens.append(_draw_text_with_bbox(draw, 680, 135, "CREDIT (PKR)", font_md, (15, 23, 42), width, height))

    rows = [
        ("1010", "Cash and Bank Balances", 250000.0, 0.0),
        ("1020", "Trade Debts (Receivables)", 480000.0, 0.0),
        ("1030", "Stock-in-Trade (Raw Materials)", 320000.0, 0.0),
        ("2010", "Trade and Other Payables", 0.0, 350000.0),
        ("3010", "Issued Share Capital", 0.0, 700000.0),
    ]

    tb_items_meta = []
    y = 180
    for code, title, dr, cr in rows:
        t_c = _draw_text_with_bbox(draw, 65, y, code, font_md, (30, 41, 59), width, height)
        t_t = _draw_text_with_bbox(draw, 140, y, title, font_md, (30, 41, 59), width, height)
        dr_str = f"{dr:,.2f}" if dr > 0 else "-"
        cr_str = f"{cr:,.2f}" if cr > 0 else "-"
        t_dr = _draw_text_with_bbox(draw, 510, y, dr_str, font_md, (30, 41, 59), width, height)
        t_cr = _draw_text_with_bbox(draw, 670, y, cr_str, font_md, (30, 41, 59), width, height)
        tokens.extend([t_c, t_t, t_dr, t_cr])

        tb_items_meta.append({
            "account_code": code,
            "account_name": title,
            "debit": dr,
            "credit": cr,
            "bbox_pixels": t_t["bbox_pixels"],
            "bbox_normalized": t_t["bbox_normalized"],
        })
        y += 35

    draw.line([(50, y + 10), (800, y + 10)], fill=(15, 23, 42), width=2)
    y += 25

    total_dr = 1050000.0
    total_cr = 1050000.0
    t_tot_label = _draw_text_with_bbox(draw, 140, y, "TOTALS", font_md, (15, 23, 42), width, height)
    t_dr_tot = _draw_text_with_bbox(draw, 495, y, f"{total_dr:,.2f}", font_md, (15, 23, 42), width, height)
    t_cr_tot = _draw_text_with_bbox(draw, 655, y, f"{total_cr:,.2f}", font_md, (15, 23, 42), width, height)
    tokens.extend([t_tot_label, t_dr_tot, t_cr_tot])
    draw.line([(50, y + 25), (800, y + 25)], fill=(15, 23, 42), width=3)

    img_path = out_dir / "scan_04_scanned_tb.png"
    img.save(img_path)

    return {
        "file_name": "scan_04_scanned_tb.png",
        "document_type": "SCANNED_TRIAL_BALANCE",
        "title": "Unadjusted Working Trial Balance",
        "entity_name": "CRESCENT TEXTILE MILLS LIMITED",
        "dimensions": [width, height],
        "total_debits": total_dr,
        "total_credits": total_cr,
        "is_arithmetically_balanced": True,
        "accounts": tb_items_meta,
        "tokens": tokens,
    }


def main():
    repo_root = Path(__file__).resolve().parent.parent.parent
    out_dir = repo_root / "data" / "synthetic_scans"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "corpus_version": "1.0.0",
        "description": "Synthetic benchmark documents for Module 7 edge OCR and symbolic verifier",
        "documents": [],
    }

    doc1 = generate_scan_01_clean_receipt(out_dir)
    doc2 = generate_scan_02_skewed_challan(out_dir)
    doc3 = generate_scan_03_digit_confusion(out_dir)
    doc4 = generate_scan_04_scanned_tb(out_dir)

    manifest["documents"] = [doc1, doc2, doc3, doc4]

    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated 4 calibrated benchmark scans in {out_dir}")


if __name__ == "__main__":
    main()

