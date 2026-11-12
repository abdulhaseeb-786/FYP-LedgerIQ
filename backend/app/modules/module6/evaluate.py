import json
import os
import openpyxl

TRUTH_PATH = os.path.join("input", "ground_truth_v1_0.json")           # ground truth file
RESULTS_PATH = os.path.join("output", "three_way_match_results.xlsx")  # your results file

# expected triples (invoice line, PO line, receipt line) from the ground truth
with open(TRUTH_PATH, "r", encoding="utf-8") as f:
    truth = json.load(f)
expected = set()
for bundle in truth["bundles"].values():
    for line in bundle["expected_line_matches"]:
        expected.add((line["invoice_line_id"], line["po_line_id"], line["receipt_line_id"]))

# found triples from the Excel; columns are located by title, so removing Status is fine
rows = openpyxl.load_workbook(RESULTS_PATH).active.iter_rows(values_only=True)
header = next(rows)
cols = [header.index(h) for h in ("Invoice Line ID", "PO Line ID", "Receipt Line ID")]
found = set()
for row in rows:
    found.add(tuple(row[c] or None for c in cols))   # empty cell -> None, same as the ground truth


expected_po = {(i, p) for i, p, r in expected if i}
expected_rc = {(i, r) for i, p, r in expected if i}
found_po = {(i, p) for i, p, r in found if i}
found_rc = {(i, r) for i, p, r in found if i}

triple_hits = len(found & expected)
po_hits = len(found_po & expected_po)
rc_hits = len(found_rc & expected_rc)

print(f"Full triple accuracy:     {triple_hits} / {len(expected)} = {triple_hits / len(expected):.1%}")
print(f"Invoice-PO accuracy:      {po_hits} / {len(expected_po)} = {po_hits / len(expected_po):.1%}")
print(f"Invoice-receipt accuracy: {rc_hits} / {len(expected_rc)} = {rc_hits / len(expected_rc):.1%}")

print("\nMISSED (expected, not found):")
for t in sorted(expected - found, key=str):
    print(" ", t)
print("\nWRONG (found, not expected):")
for t in sorted(found - expected, key=str):
    print(" ", t)

correct = found & expected    # found and expected

print("precision:", len(correct), "/", len(found), "=", round(len(correct) / len(found), 3))      # how many found rows are right
print("recall:   ", len(correct), "/", len(expected), "=", round(len(correct) / len(expected), 3))  # how many expected triples were found