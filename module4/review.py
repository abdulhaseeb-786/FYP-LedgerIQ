"""
Runs the matching pipeline on every Excel file in the input folder and writes one review
workbook per file to the output folder, for a human to check before the statement is made.

USAGE
    python review.py        (reads input/*.xlsx, writes output/review_<input name>.xlsx)

FLOW
    1. Read the bank and ledger entries and closing balances (read_data.Data)
    2. Match them and sort into groups (graph_matching.reconcile)
    3. Turn every entry or pair into a row and write the review file

OUTPUT (review_<name>.xlsx)
    Review sheet   : one row per entry or pair, with columns
                     Bank/Ledger Description, Type, Bank/Ledger Amount, Bank/Ledger Date,
                     Score, Notes (no match / amount mismatch / low score / matched),
                     Match? (Yes/No). Notes and Match? have dropdowns so the reviewer can
                     change them. A missing side shows "-".
    Balances sheet : bank closing balance in B1, ledger closing balance in B2

    Rows still marked "No" in Match? are used later to build the reconciliation statement.
"""

from read_data import Data
from graph_matching import reconcile
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation
import os
from pathlib import Path

# create proper rows to be added to excel sheet for review
def make_row(bank_e, ledger_e, score, note, match):
    # a missing column becomes a dash in every column that belongs to it
    b = bank_e or {"description": "-", "amount": "-", "date": "-"}
    l = ledger_e or {"description": "-", "amount": "-", "date": "-"}
    entry_type = (bank_e or ledger_e)["type"]
    return [b["description"], l["description"], entry_type, b["amount"], l["amount"], b["date"], l["date"], score, note, match]

def build_rows(entries_bank, entries_ledger, kept, amount_errors, low_score, unmatched_bank, unmatched_ledger):
    rows = []  # added in your order: no match, amount mismatch, low score, then matched
    rows += [make_row(entries_bank[i], None, "-", "no match", "No") for i in unmatched_bank]
    rows += [make_row(None, entries_ledger[j], "-", "no match", "No") for j in unmatched_ledger]
    rows += [make_row(entries_bank[i], entries_ledger[j], s, "amount mismatch", "No") for i, j, s in amount_errors]
    rows += [make_row(entries_bank[i], entries_ledger[j], s, "low score", "No") for i, j, s in low_score]
    rows += [make_row(entries_bank[i], entries_ledger[j], s, "matched", "Yes") for i, j, s in kept]
    return rows

# excel sheet for approval
# columns - bank entry, ledger entry, ledger type (debit/credit), bank amount, ledger amount, bank date, ledger date, score, match (no match, amount mismatch, low score, matched), match? (yes, no) 
# this should be on an online databse and a human should be allowed to review the file and then click approve on final file

headers = ["Bank Description", "Ledger Description", "Type", "Bank Amount", "Ledger Amount",
           "Bank Date", "Ledger Date", "Score", "Notes", "Match?"]

# add dropdown options for notes and match columns
def add_dropdowns(ws, last_row):
    notes_dv = DataValidation(type="list", formula1='"no match,amount mismatch,low score,matched"', allow_blank=False)
    match_dv = DataValidation(type="list", formula1='"Yes,No"', allow_blank=False)
    ws.add_data_validation(notes_dv)
    ws.add_data_validation(match_dv)

    # Notes is column I, Match? is column J (see headers); data starts on row 2
    notes_dv.add(f"I2:I{last_row}")  
    match_dv.add(f"J2:J{last_row}")

def write_review_sheet(rows, bank_balance, ledger_balance, path="output\\review.xlsx"):
    try:
        if os.path.exists(path):                            # a review file from an earlier run
            os.remove(path)                                 # delete it so a fresh one is created
    except PermissionError:                                 # Windows blocks deleting a file that is open in Excel
        raise SystemExit(f"Close {path} in Excel and run again")
    wb = Workbook()                                         # new workbook for this run
    ws = wb.active                                          # the first sheet holds the entries
    ws.title = "Review"                                     # name the statement code looks for
    ws.append(headers)                                      # header row first
    for row in rows:                                        # one sheet row per entry
        ws.append(row)                                      # add the entry
    add_dropdowns(ws, len(rows) + 1)                        # +1 because row 1 is the header
    balances = wb.create_sheet("Balances")                  # second sheet holds the two closing balances
    balances.append(["Bank Closing Balance", bank_balance])       # row 1: bank balance in column B
    balances.append(["Ledger Closing Balance", ledger_balance])   # row 2: ledger balance in column B
    wb.save(path)                                           # write the file to disk
    return path                                             # path of the saved review file

def run_pipeline(filepath, ouput_folder):
    # get all entries
    # Each entry is a dict: {description, type, amount, date, flags, source}
    Path(output_folder).mkdir(exist_ok=True)                                # create the output folder if it doesn't exist yet
    data = Data(filepath)
    entries_bank, entries_ledger, closing = data.get_entries()
    kept, low_score, amount_errors, unmatched_bank, unmatched_ledger = reconcile(entries_bank, entries_ledger)
    rows = build_rows(entries_bank, entries_ledger, kept, amount_errors, low_score, unmatched_bank, unmatched_ledger)
    out_path = Path(output_folder) / f"review_{Path(filepath).stem}.xlsx"   # input\A.xlsx -> review_A.xlsx
    path = write_review_sheet(rows, closing.get("bank"), closing.get("ledger"), out_path) # .get returns None if that sheet was missing
    return path

if __name__ == "__main__":      # runs only when you run review.py directly, not when another file imports it
    input_folder = "input"
    output_folder = "output"
    for f in sorted(Path(input_folder).glob("*.xlsx")):
        if f.name.startswith("~$"):         # skip Excel's temp lock files
            continue
        print(f"Processing {f.name}")
        print("Created", run_pipeline(str(f), output_folder))
