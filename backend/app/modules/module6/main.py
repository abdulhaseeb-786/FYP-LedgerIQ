# ==============================================================================
# MAIN PIPELINE: 3-WAY MATCHING (INVOICE - PURCHASE ORDER - RECEIPT)
# ==============================================================================

# STEP 1: IMPORT REQUIRED MODULES
import os
import pandas as pd
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from read_data import Data
from score import build_triples
from model import Model

# ==============================================================================
# CONFIGURATION / TOLERANCES
# ==============================================================================
# Allowed price variance percentage between invoice unit price and PO unit price.
# In enterprise AP (e.g. SAP / Oracle), minor differences within tolerance (e.g. 1%)
# are automatically approved without triggering costly manual exceptions.
PRICE_TOLERANCE = 0.0  # 1% tolerance (defined locally, not imported from score.py)


def set_severity(current_color, new_color):
    """
    Ensures color strictly follows audit severity hierarchy:
    RED (High Risk / Block) > YELLOW (Medium Risk / Warning) > GREEN (Clean Match).
    A RED flag can never be downgraded to YELLOW or GREEN.
    """
    severity_order = {"green": 1, "yellow": 2, "red": 3}
    if severity_order.get(new_color, 0) > severity_order.get(current_color, 0):
        return new_color
    return current_color


# ==============================================================================
# EXCEL STYLING AND EXPORT
# ==============================================================================
def style_match_sheet(ws):
    """
    Styles the 3-Way Match Excel sheet matching standard statement formatting:
    - Navy Blue header with bold white text
    - Soft badge fills for Status (Green, Yellow, Red)
    - Thin bottom borders on data rows
    - Wrap text enabled across columns (especially Notes)
    - Formatted numbers (quantities) and currency (prices)
    - Gridlines hidden, header frozen (A2), auto-filter enabled
    """
    fill = lambda c: PatternFill("solid", fgColor=c)   # helper to make a solid colour fill
    thin = Side(style="thin", color="BFBFBF")          # light grey line used for row borders
    border_bottom = Border(bottom=thin)

    ws.sheet_view.showGridLines = False                # hide default gridlines

    # Status badge color fills and font colors
    status_styles = {
        "GREEN": {"fill": fill("E2EFDA"), "font": Font(name="Calibri", size=11, bold=True, color="276A3C")},
        "YELLOW": {"fill": fill("FFF2CC"), "font": Font(name="Calibri", size=11, bold=True, color="8C6B00")},
        "RED": {"fill": fill("FCE4D6"), "font": Font(name="Calibri", size=11, bold=True, color="C00000")},
    }

    # Column widths: A to L
    column_widths = {
        "A": 14,  # Status
        "B": 24,  # Invoice Line ID
        "C": 20,  # PO Line ID
        "D": 20,  # Receipt Line ID
        "E": 28,  # Item Description
        "F": 14,  # Matched Qty
        "G": 14,  # Invoice Qty
        "H": 12,  # PO Qty
        "I": 14,  # Receipt Qty
        "J": 14,  # Invoice Price
        "K": 12,  # PO Price
        "L": 55,  # Notes (generous width with wrap_text for readability)
    }

    for col_letter, width in column_widths.items():
        ws.column_dimensions[col_letter].width = width

    # Header row (row 1): Navy Blue ("2F5597"), white bold text
    header_fill = fill("2F5597")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col in range(1, 13):
        col_letter = get_column_letter(col)
        cell = ws[f"{col_letter}1"]
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
    ws.row_dimensions[1].height = 26

    # Data rows styling
    for row in range(2, ws.max_row + 1):
        status_val = str(ws[f"A{row}"].value or "").strip().upper()

        # Style Status cell as a color badge
        status_cell = ws[f"A{row}"]
        if status_val in status_styles:
            status_cell.fill = status_styles[status_val]["fill"]
            status_cell.font = status_styles[status_val]["font"]
        status_cell.alignment = Alignment(horizontal="center", vertical="top")

        # Format remaining columns in this row
        for col in range(1, 13):
            col_letter = get_column_letter(col)
            cell = ws[f"{col_letter}{row}"]
            cell.border = border_bottom

            if col == 1:
                continue
            elif col_letter in ("F", "G", "H", "I"):
                # Quantities: right-aligned, integer format
                cell.alignment = Alignment(horizontal="right", vertical="top")
                if cell.value is not None and isinstance(cell.value, (int, float)):
                    cell.number_format = "#,##0"
            elif col_letter in ("J", "K"):
                # Prices: right-aligned, currency format
                cell.alignment = Alignment(horizontal="right", vertical="top")
                if cell.value is not None and isinstance(cell.value, (int, float)):
                    cell.number_format = "$#,##0.00"
            elif col_letter == "L":
                # Notes: wrap_text=True so text wraps and is clearly readable
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            else:
                # Text columns (IDs, Description): wrap_text=True, left-aligned
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

    ws.freeze_panes = "A2"                             # header stays visible while scrolling
    ws.auto_filter.ref = ws.dimensions                 # filter dropdowns on every column


def export_to_excel(triple_results, output_path="three_way_match_results.xlsx"):
    """
    Takes all triples (matched and unmatched with color, notes, etc.)
    and exports them to a styled Excel workbook.
    """
    rows = []
    for (inv_id, po_id, rcpt_id), data in triple_results.items():
        inv = data.get("invoice")
        po = data.get("po")
        rcpt = data.get("receipt")

        # Pick item description from available node
        desc = ""
        if inv and inv.get("description"):
            desc = inv["description"]
        elif po and po.get("description"):
            desc = po["description"]
        elif rcpt and rcpt.get("description"):
            desc = rcpt["description"]

        # Format multiline bulleted notes
        notes_list = data.get("notes", [])
        notes_text = "\n".join(f"• {n}" for n in notes_list) if notes_list else ""

        rows.append({
            "Status": data.get("color", "green").upper(),
            "Invoice Line ID": inv_id or "",
            "PO Line ID": po_id or "",
            "Receipt Line ID": rcpt_id or "",
            "Item Description": desc,
            "Matched Qty": data.get("matched_quantity", 0),
            "Invoice Qty": inv["quantity"] if inv else None,
            "PO Qty": po["quantity"] if po else None,
            "Receipt Qty": rcpt["quantity"] if rcpt else None,
            "Invoice Price": inv["unit_price"] if (inv and inv.get("unit_price") is not None) else None,
            "PO Price": po["unit_price"] if (po and po.get("unit_price") is not None) else None,
            "Notes": notes_text,
        })

    df = pd.DataFrame(rows)
    sheet_name = "3-Way Match Results"

    # Write sheet and apply styling before saving
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        style_match_sheet(writer.sheets[sheet_name])

    print(f"\n[OK] Excel workbook successfully exported: {output_path}")
    return output_path


def main():
    # STEP 2: GET DATA FROM read_data.py
    # loads JSON fixtures and normalizes PO, Invoice, and Receipt nodes
    data = Data("input")
    po_nodes, invoice_nodes, receipt_nodes = data.get_data()

    print(f"\n--- Data Summary ---")
    print(f"Invoice lines: {len(invoice_nodes)}")
    print(f"PO lines:      {len(po_nodes)}")
    print(f"Receipt lines: {len(receipt_nodes)}")

    # STEP 3: GET SCORE FROM score.py
    # calculates scores for all triple combinations: (inv_id, po_id, rcpt_id)
    triples = build_triples(invoice_nodes, po_nodes, receipt_nodes)
    print(f"\nGenerated {len(triples)} triple edge combinations with scores.")

    # STEP 4: GIVE TRIPLES WITH SCORES TO MODEL AND GET MATCHES FROM model.py
    # initializes the PuLP optimization model with triples and capacity constraints
    matcher = Model(triples, invoice_nodes, po_nodes, receipt_nodes)
    matches = matcher.solve()

    # filter for active matches (triples where matched quantity > 0)
    active_matches = {t: qty for t, qty in matches.items() if qty > 0}

    print(f"\n--- Matched Triples (Solver Results) ---")
    for (inv_id, po_id, rcpt_id), qty in active_matches.items():
        score = triples.get((inv_id, po_id, rcpt_id), 0)
        print(f"  Matched: Inv={inv_id} <-> PO={po_id} <-> Rcpt={rcpt_id} | Qty={qty} | Score={score}")

    # Quick lookups for nodes by id
    inv_by_id = {node["id"]: node for node in invoice_nodes}
    po_by_id = {node["id"]: node for node in po_nodes}
    rcpt_by_id = {node["id"]: node for node in receipt_nodes}

    # ==============================================================================
    # STEP 5: REAL-WORLD 3-WAY MATCH DISCREPANCY ANALYSIS
    # ==============================================================================
    triple_results = {}

    # Track matched node IDs to identify unmatched nodes later
    matched_inv_ids = set()
    matched_po_ids = set()
    matched_rcpt_ids = set()

    for (inv_id, po_id, rcpt_id), qty in active_matches.items():
        matched_inv_ids.add(inv_id)
        matched_po_ids.add(po_id)
        matched_rcpt_ids.add(rcpt_id)

        inv = inv_by_id[inv_id]
        po = po_by_id[po_id]
        rcpt = rcpt_by_id[rcpt_id]

        color = "green"
        notes = []

        # --------------------------------------------------------------------------
        # 1. QUANTITY MATCHING (REAL AP PRACTICE)
        # --------------------------------------------------------------------------
        # Check Receipt (Physical Goods Received):
        # Paying for unreceived goods is a major control failure (Phantom Inventory) 
        if inv["quantity"] > rcpt["quantity"]:
            color = set_severity(color, "yellow")
            notes.append(
                f"Quantity discrepancy (receipt): billed ({inv['quantity']}) > received ({rcpt['quantity']}). "
                f"Approved {qty} units for payment; {inv['quantity'] - qty} units held pending delivery."
            )

        # Check PO (Authorization / Contract Volume):
        # Billed quantity exceeding PO authorized volume -> YELLOW (over-billing review)
        if inv["quantity"] > po["quantity"]:
            color = set_severity(color, "yellow")
            notes.append(
                f"Quantity discrepancy (purchase order): billed ({inv['quantity']}) > PO ordered ({po['quantity']}). "
                f"{inv['quantity'] - po['quantity']} excess units require buyer authorization."
            )

        # Check Partial Delivery:
        # Goods delivered less than PO ordered -> YELLOW (back-order notice)
        if po["quantity"] > rcpt["quantity"]:
            color = set_severity(color, "yellow")
            notes.append(
                f"Partial delivery: ordered ({po['quantity']}) > received ({rcpt['quantity']}). "
                f"{po['quantity'] - rcpt['quantity']} units remaining on order."
            )

        # --------------------------------------------------------------------------
        # 2. PRICE MATCHING WITH TOLERANCE (REAL AP PRACTICE)
        # --------------------------------------------------------------------------
        # In enterprise AP, price check is strictly Invoice vs. PO (Receipts do not carry prices)
        po_price = po["unit_price"]
        inv_price = inv["unit_price"]

        if po_price > 0:
            price_variance = (inv_price - po_price) / po_price
        else:
            price_variance = 0.0

        if price_variance > PRICE_TOLERANCE:
            # Invoice price exceeds PO beyond tolerance -> RED (overbilling risk)
            color = set_severity(color, "red")
            notes.append(
                f"Price discrepancy (purchase order): invoice price ({inv_price:.2f}) > PO price ({po_price:.2f}) "
                f"by {price_variance:.1%} (exceeds {PRICE_TOLERANCE:.1%} tolerance)."
            )
        elif price_variance < -PRICE_TOLERANCE:
            # Invoice price is lower than PO beyond tolerance -> YELLOW (discount / underbilling verification)
            color = set_severity(color, "yellow")
            notes.append(
                f"Price discrepancy (purchase order): invoice price ({inv_price:.2f}) < PO price ({po_price:.2f}) "
                f"by {abs(price_variance):.1%} (exceeds {PRICE_TOLERANCE:.1%} tolerance; favorable variance)."
            )

        # Optional check: If receipt node specifies unit price, compare it
        if rcpt.get("unit_price") is not None:
            rcpt_price = rcpt["unit_price"]
            if rcpt_price > 0:
                rcpt_variance = (inv_price - rcpt_price) / rcpt_price
                if rcpt_variance > PRICE_TOLERANCE:
                    color = set_severity(color, "red")
                    notes.append(f"Price discrepancy (receipt): invoice price ({inv_price:.2f}) > receipt price ({rcpt_price:.2f})")
                elif rcpt_variance < -PRICE_TOLERANCE:
                    color = set_severity(color, "yellow")
                    notes.append(f"Price discrepancy (receipt): invoice price ({inv_price:.2f}) < receipt price ({rcpt_price:.2f})")

        # --------------------------------------------------------------------------
        # 3. CLEAN MATCH FALLBACK
        # --------------------------------------------------------------------------
        if not notes:
            notes.append("Clean match: quantities and prices agree within tolerance")

        triple_results[(inv_id, po_id, rcpt_id)] = {
            "matched_quantity": qty,
            "color": color,
            "notes": notes,
            "invoice": inv,
            "po": po,
            "receipt": rcpt,
        }

    # ==============================================================================
    # STEP 6: UNMATCHED NODES AS SEPARATE TRIPLES WITH NO MEMBERS (NONE) -> RED
    # ==============================================================================
    # Invoices received from get_data but not in active matches
    for inv in invoice_nodes:
        if inv["id"] not in matched_inv_ids:
            triple_results[(inv["id"], None, None)] = {
                "matched_quantity": 0,
                "color": "red",
                "notes": ["no matches"],
                "invoice": inv,
                "po": None,
                "receipt": None,
            }

    # Purchase Orders received from get_data but not in active matches
    for po in po_nodes:
        if po["id"] not in matched_po_ids:
            triple_results[(None, po["id"], None)] = {
                "matched_quantity": 0,
                "color": "red",
                "notes": ["no matches"],
                "invoice": None,
                "po": po,
                "receipt": None,
            }

    # Receipts received from get_data but not in active matches
    for rcpt in receipt_nodes:
        if rcpt["id"] not in matched_rcpt_ids:
            triple_results[(None, None, rcpt["id"])] = {
                "matched_quantity": 0,
                "color": "red",
                "notes": ["no matches"],
                "invoice": None,
                "po": None,
                "receipt": rcpt,
            }

    # ==============================================================================
    # PRINT DISCREPANCY ANALYSIS REPORT
    # ==============================================================================
    print("\n" + "=" * 80)
    print("REAL-WORLD 3-WAY MATCHING DISCREPANCY REPORT")
    print("=" * 80)

    print("\n--- 3-Way Matched Triples ---")
    matched_count = 0
    for (inv_id, po_id, rcpt_id), res in triple_results.items():
        if inv_id and po_id and rcpt_id:
            matched_count += 1
            tag = f"[{res['color'].upper()}]"
            print(f"\n{tag} Triple: Inv='{inv_id}' | PO='{po_id}' | Rcpt='{rcpt_id}' | Matched Qty={res['matched_quantity']}")
            for note in res["notes"]:
                print(f"    * {note}")

    print("\n--- Unmatched Nodes (Formed as Separate Triples with None Members) ---")
    unmatched_count = 0
    for (inv_id, po_id, rcpt_id), res in triple_results.items():
        if not (inv_id and po_id and rcpt_id):
            unmatched_count += 1
            tag = f"[{res['color'].upper()}]"
            print(f"\n{tag} Triple: ({inv_id}, {po_id}, {rcpt_id}) | Matched Qty={res['matched_quantity']}")
            for note in res["notes"]:
                print(f"    * {note}")

    # Summary Statistics
    counts = {"green": 0, "yellow": 0, "red": 0}
    for res in triple_results.values():
        counts[res["color"]] += 1

    print("\n" + "-" * 80)
    print(f"Summary: Total Triples={len(triple_results)} | Green={counts['green']} | Yellow={counts['yellow']} | Red={counts['red']}")
    print(f"Details: Matched Triples={matched_count} | Unmatched Triples={unmatched_count}")
    print("-" * 80)

    # ==============================================================================
    # STEP 7: EXPORT TO STYLED EXCEL WORKBOOK
    # ==============================================================================
    excel_path = "three_way_match_results.xlsx"
    folder = "output"
    os.makedirs(folder, exist_ok=True)           # creates the folder if it's missing, does nothing if it exists
    full_path = os.path.join(folder, excel_path)
    export_to_excel(triple_results, output_path=full_path)

    return matches, active_matches, triple_results, full_path


if __name__ == "__main__":
    main()