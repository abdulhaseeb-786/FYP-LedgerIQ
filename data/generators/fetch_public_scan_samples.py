"""Seeds realistic public enterprise scans and benchmarks (CORD / SROIE / FBR CPR).

Module 7 public dataset corpus adhering to enterprise formats.
"""

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def _draw_field(draw, x, y, text, font, fill=(20, 20, 20), img_w=800, img_h=1000):
    draw.text((x, y), text, font=font, fill=fill)
    bbox = draw.textbbox((x, y), text, font=font)
    x1, y1, x2, y2 = bbox
    return {
        "text": text,
        "bbox_pixels": [x1, y1, x2, y2],
        "bbox_normalized": [
            round(y1 / img_h, 4),
            round(x1 / img_w, 4),
            round(y2 / img_h, 4),
            round(x2 / img_w, 4),
        ],
    }


def create_cord_sample(out_dir: Path):
    """CORD benchmark style commercial merchant receipt."""
    w, h = 600, 800
    img = Image.new("RGB", (w, h), (252, 252, 250))
    draw = ImageDraw.ImageDraw(img)
    font = ImageFont.load_default()

    tokens = []
    tokens.append(_draw_field(draw, 170, 30, "STARBUCKS COFFEE PAKISTAN", font, (20, 20, 20), w, h))
    tokens.append(_draw_field(draw, 200, 50, "STORE #0412 - GULBERG III", font, (100, 100, 100), w, h))
    tokens.append(_draw_field(draw, 230, 70, "POS-01  TRANS-90412", font, (100, 100, 100), w, h))
    tokens.append(_draw_field(draw, 220, 90, "2025-06-18 09:45 AM", font, (100, 100, 100), w, h))

    draw.line([(30, 115), (570, 115)], fill=(200, 200, 200), width=1)
    tokens.append(_draw_field(draw, 40, 125, "QTY  ITEM", font, (50, 50, 50), w, h))
    tokens.append(_draw_field(draw, 480, 125, "TOTAL", font, (50, 50, 50), w, h))
    draw.line([(30, 145), (570, 145)], fill=(200, 200, 200), width=1)

    items = [
        ("1  Caffe Latte Grande", 1350.0),
        ("2  Butter Croissant", 1100.0),
        ("1  Iced Caramel Macchiato", 1650.0),
        ("1  Blueberry Muffin", 650.0),
    ]

    y = 160
    for desc, amt in items:
        t_d = _draw_field(draw, 40, y, desc, font, (30, 30, 30), w, h)
        t_a = _draw_field(draw, 490, y, f"{amt:,.2f}", font, (30, 30, 30), w, h)
        tokens.extend([t_d, t_a])
        y += 30

    draw.line([(30, y + 10), (570, y + 10)], fill=(200, 200, 200), width=1)
    y += 25

    subtotal = 4750.0
    tax = 760.0  # 16% PRA Services Tax
    total = 5510.0

    tokens.append(_draw_field(draw, 340, y, "SUBTOTAL:", font, (30, 30, 30), w, h))
    tokens.append(_draw_field(draw, 490, y, f"{subtotal:,.2f}", font, (30, 30, 30), w, h))
    y += 25

    tokens.append(_draw_field(draw, 340, y, "PRA SALES TAX (16%):", font, (30, 30, 30), w, h))
    tokens.append(_draw_field(draw, 490, y, f"{tax:,.2f}", font, (30, 30, 30), w, h))
    y += 30

    draw.line([(320, y - 5), (570, y - 5)], fill=(20, 20, 20), width=2)
    tokens.append(_draw_field(draw, 340, y, "TOTAL DUE (PKR):", font, (10, 10, 10), w, h))
    tokens.append(_draw_field(draw, 485, y, f"{total:,.2f}", font, (10, 10, 10), w, h))

    img_path = out_dir / "cord_retail_receipt_01.png"
    img.save(img_path)

    data = {
        "file_name": "cord_retail_receipt_01.png",
        "benchmark_source": "CORD_FORMAT",
        "merchant": "STARBUCKS COFFEE PAKISTAN",
        "date": "2025-06-18",
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "is_arithmetically_balanced": True,
        "tokens": tokens,
    }
    with open(out_dir / "cord_retail_receipt_01.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def create_fbr_sample(out_dir: Path):
    """Pakistan FBR CPR Computerized Payment Receipt template."""
    w, h = 750, 900
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.ImageDraw(img)
    font = ImageFont.load_default()

    tokens = []
    tokens.append(_draw_field(draw, 180, 40, "FEDERAL BOARD OF REVENUE - GOVERNMENT OF PAKISTAN", font, (10, 80, 40), w, h))
    tokens.append(_draw_field(draw, 220, 65, "COMPUTERIZED PAYMENT RECEIPT (CPR) - ANNEX-C", font, (10, 80, 40), w, h))

    draw.rectangle([(40, 100), (710, 200)], outline=(100, 100, 100), width=1)
    tokens.append(_draw_field(draw, 50, 115, "CPR Number: ST-202506-0044-1190", font, (20, 20, 20), w, h))
    tokens.append(_draw_field(draw, 420, 115, "Payment Date: 2025-06-25", font, (20, 20, 20), w, h))
    tokens.append(_draw_field(draw, 50, 140, "Taxpayer: NISHAT PACKAGING MILLS LTD", font, (20, 20, 20), w, h))
    tokens.append(_draw_field(draw, 50, 165, "STRN: 03-01-4819-001-88", font, (20, 20, 20), w, h))
    tokens.append(_draw_field(draw, 420, 165, "Tax Period: June 2025", font, (20, 20, 20), w, h))

    draw.rectangle([(40, 220), (710, 360)], outline=(100, 100, 100), width=1)
    tokens.append(_draw_field(draw, 50, 235, "Head of Account / Tax Particulars", font, (50, 50, 50), w, h))
    tokens.append(_draw_field(draw, 540, 235, "Amount (PKR)", font, (50, 50, 50), w, h))
    draw.line([(40, 255), (710, 255)], fill=(200, 200, 200), width=1)

    items = [
        ("0200000 - Sales Tax Domestic Supplies (18%)", 360000.0),
        ("0210000 - Withholding Sales Tax by Withholding Agent", 45000.0),
    ]

    y = 270
    for desc, amt in items:
        t_d = _draw_field(draw, 50, y, desc, font, (30, 30, 30), w, h)
        t_a = _draw_field(draw, 550, y, f"{amt:,.2f}", font, (30, 30, 30), w, h)
        tokens.extend([t_d, t_a])
        y += 28

    draw.line([(40, y + 10), (710, y + 10)], fill=(20, 20, 20), width=2)
    y += 20
    total = 405000.0
    tokens.append(_draw_field(draw, 50, y, "TOTAL TAX DEPOSITED (PKR):", font, (10, 10, 10), w, h))
    tokens.append(_draw_field(draw, 540, y, f"{total:,.2f}", font, (10, 10, 10), w, h))

    img_path = out_dir / "fbr_cpr_tax_challan.png"
    img.save(img_path)

    data = {
        "file_name": "fbr_cpr_tax_challan.png",
        "benchmark_source": "FBR_CPR_PAKISTAN",
        "cpr_number": "ST-202506-0044-1190",
        "taxpayer": "NISHAT PACKAGING MILLS LTD",
        "date": "2025-06-25",
        "total": total,
        "is_arithmetically_balanced": True,
        "tokens": tokens,
    }
    with open(out_dir / "fbr_cpr_tax_challan.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def main():
    repo_root = Path(__file__).resolve().parent.parent.parent
    out_dir = repo_root / "data" / "public_scans"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "corpus_version": "1.0.0",
        "description": "Realistic enterprise document templates (CORD, FBR CPR)",
        "documents": [],
    }

    doc1 = create_cord_sample(out_dir)
    doc2 = create_fbr_sample(out_dir)
    manifest["documents"] = [doc1, doc2]

    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated realistic public scan samples in {out_dir}")


if __name__ == "__main__":
    main()

