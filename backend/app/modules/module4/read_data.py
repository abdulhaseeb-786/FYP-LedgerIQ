"""
Reads a workbook with a bank statement sheet and a cash ledger sheet, and turns every
transaction into a clean dictionary.

USAGE
    entries_bank, entries_ledger, closing = Data("file.xlsx").get_entries()

INPUT ( sample file in input folder)
  File
    One .xlsx workbook, read with data_only=True (formula cells show their last saved value,
    so a file never opened and saved in Excel may show empty cells where formulas are).

  Sheets
    Sheet names are lowercased and spaces removed, then checked in this order:
      contains "ledger" or "cashbook"                      -> cash ledger
      contains "bank" or "statement" (not "reconciliation") -> bank statement
      anything else                                        -> skipped
    If several sheets share a source, their entries are combined and the last one's closing
    balance is kept.

  Layout (both sheets)
    - Entries start at the first row that has a recognised date in any cell.
    - The header row must be directly above that row. Titles or blank rows above it are ignored.
    - Header names are lowercased. A blank header makes an "empty" column.
    - Fully blank rows are skipped. A row with any content but no date is still kept if not first row
      and flagged "missing date".

  Dates
    Excel dates, or text in one of: 5-Jun-23, 5-Jun-2023, 05/06/2023 (day first), 2023-06-05.
    Any other text is read as a missing date.

  Amounts
    Numbers, or text like 24,300 / $24,300 / (1,200) / 1,200-. The sign is dropped (amount is
    always positive). Anything unreadable is a missing amount.

  Bank statement and cash ledger (same two layouts for both)
    a) One table with "debit" and "credit" columns. The amount is taken from whichever
       cell is filled. Do not write "amount" in these two headers.
    b) Two tables side by side (a debit table and a credit table). Tables are split at an
       empty column, or where the first header (e.g. "date") repeats. Each table needs a
       header containing "amount". The word "debit" or "credit" (only one of them) must
       appear above the entries, inside that table's columns. Otherwise its type is missing.

  Closing balance
    Bank   : needs a column whose header contains "balance". Only the first such column
             is used, so with two tables the second table's balance is ignored.
    Ledger : see the closing balance rule under OUTPUT.

  Description
    The first column that is not date / amount / debit / credit / balance / type. If another
    column (e.g. "ref") comes before the description column, that one is used instead.

  Skipped rows
    - Rows containing: opening balance, closing balance, balance b/d, c/d, b/f, c/f,
      brought forward, carried forward.
    - Rows with no date whose text starts with total, totals, grand total, subtotal.

OUTPUT (sample file in output folder)
  get_entries() returns (entries_bank, entries_ledger, closing)

  entries_bank, entries_ledger : lists of dicts, in sheet order (two-table ledger: all
  entries of the first table, then the second)
      description : lowercase str, or None
      type        : "debit" or "credit", or None.
                    Ledger: debit = money in, credit = money out.
                    Bank: the bank's own label, NOT flipped.
      amount      : positive float, or None
      date        : datetime.date, or None
      flags       : list of "missing description" / "missing type" / "missing amount" /
                    "missing date" (empty list if the entry is complete)

  closing : dict, a key exists only if that sheet was found
      closing["bank"]   : last number in the "balance" column (negative if shown as
                          (x), -x or x-), or None if there is no balance column
      closing["ledger"] : the first number to the right of a label containing
                          "balance c/d", "balance c/f", "closing balance" or "carried forward";
                          negative if it sits on the debit side (overdrawn), or None if
                          no such label exists
"""

from datetime import datetime, date
from openpyxl import load_workbook 
import re  

DATE_FORMATS = ["%d-%b-%y", "%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d"]  # text formats we recognise
CLOSING_WORDS = ["balance c/d", "balance c/f", "closing balance", "carried forward"] # for closing balance in ledger

class Data:
    # Reads both files and holds one list of nodes for each
    def __init__(self, path):
        self.path = path  # path of workbook

    def is_number(self, cell):
        # True if the cell is a number, or text that looks like one (e.g. "24,300" or "(1,200)")
        if isinstance(cell, (int, float)):
            return True                              # already a real number
        if not isinstance(cell, str):
            return False                             # blank (None) or another type
        text = cell.strip().replace(",", "").replace("$", "")  # drop commas and currency sign
        text = text.strip("()-")                     # drop brackets / minus used for negatives
        return text.replace(".", "", 1).isdigit()    # allow one decimal point, rest must be digits

    def is_date(self, cell):        
        # True if the cell is a real date, or text that matches one of our formats
        if isinstance(cell, (datetime, date)):
            return True                              # Excel already gave us a real date
        if not isinstance(cell, str):
            return False                             # blank or a number, not a date
        for fmt in DATE_FORMATS:
            try:
                datetime.strptime(cell.strip(), fmt) # try to parse the text with this format
                return True                          # parsing worked, so it is a date
            except ValueError:
                pass                                 # wrong format, try the next one
        return False                                 # no format matched

    # headers skip. if row has date and a number, it is the first row
    def find_first_entry_row(self, rows):
        # rows = the sheet as a list of rows, each row being a list of cell values
        for index, row in enumerate(rows):                         # go through rows from the top
            has_date = any(self.is_date(cell) for cell in row)     # does any cell in this row hold a date?
            # has_number = any(self.is_number(cell) for cell in row) # does any cell in this row hold a number?
            if has_date:                            # an entry needs both
                return index                                       # first such row = where entries start
        return None                                                # no entry found in the whole sheet

    # get column names
    def get_column_names(self, rows, start_row):
        # rows = whole sheet, start_row = result of find_first_entry_row
        # the header row is the row right above the first entry
        header_row = rows[start_row - 1] if start_row > 0 else []   # no row above means no headers
        width = max(len(row) for row in rows[start_row:])           # number of columns in the sheet
        names = []                                                   # one name per column
        for col in range(width):
            cell = header_row[col] if col < len(header_row) else None  # short header rows count as blank
            if cell is None or str(cell).strip() == "":
                names.append("empty")                                # no header name in this column
            else:
                names.append(str(cell).strip().lower())              # clean the name and lowercase it
        return names

    # Is table debit or credit?
    def get_table_type(self, rows, start_row, first_col, last_col):
        # looks at the rows above the entries (titles + header), only inside this table's columns
        found = set()                                         # words found here: "debit" and/or "credit"
        for row in rows[:start_row]:
            for col in range(first_col, min(last_col + 1, len(row))):  # stay inside the table's columns
                text = str(row[col]).lower() if row[col] is not None else ""  # blank cell -> empty text
                if "debit" in text:
                    found.add("debit")                        # this table mentions debit
                if "credit" in text:
                    found.add("credit")                       # this table mentions credit
        return found.pop() if len(found) == 1 else None       # exactly one word = the type, else unknown

    # check if sheet has multiple tables and store their starting and ending cols
    def find_tables(self, rows, start_row, labels):
        # labels = result of get_column_names, e.g. ["empty", "date", "details" etc]
        # the first non-empty column's label marks where a table begins
        first_label = next((l for l in labels if l != "empty"), None)
        if first_label is None:
            return []                                # the sheet has no columns with data
        tables = []                                  # each table is stored as (first_col, last_col)
        start = None                                 # first column of the table we are building
        for col, label in enumerate(labels):
            if label == first_label:
                if start is not None:
                    tables.append((start, col - 1))  # a new date column closes the previous table
                start = col                          # and starts a new one here
            elif label == "empty" and start is not None:
                tables.append((start, col - 1))      # an empty column closes the current table
                start = None                         # no table is open now
        if start is not None:
            tables.append((start, len(labels) - 1))  # close a table that runs to the last column
        if len(tables) > 1:                          # only with 2+ tables does the type matter
            tables = [
                (first, last, self.get_table_type(rows, start_row, first, last))  # add type to each table
                for first, last in tables
            ]
        return tables

    def is_summary_row(self, entry):
        # True if the entry is an opening/closing balance row or a total row
        BALANCE_WORDS = ["opening balance", "closing balance", "balance b/d", "balance c/d",
                         "balance b/f", "balance c/f", "brought forward", "carried forward"]
        TOTAL_PATTERN = re.compile(r"^(grand\s+|sub\s*)?totals?\b")   # "total", "totals", "grand total", "subtotal", "total debits"
        has_date = entry.get("date") is not None                      # real transactions carry a date, total rows don't
        for value in entry.values():
            if isinstance(value, str):                                # only text cells can hold these labels
                text = value.strip().lower()
                if any(word in text for word in BALANCE_WORDS):
                    return True                                       # balance labels never appear in real descriptions
                if not has_date and TOTAL_PATTERN.match(text):
                    return True                                       # starts with "total" and has no date = a totals row
        return False  

    def normalize_entry(self, entry):
        # turns one raw entry into a clean dictionary with exactly four keys:
        # description, type, amount, date

        # --- description: first column that is not date / amount / type / balance ---
        description = None
        for name, value in entry.items():
            if name not in ("date", "amount", "debit", "credit", "balance", "type") and "amount" not in name:
                description = value                           # first remaining column = the description
                break                                         # one is enough
        if description is not None:
            description = str(description).strip().lower()    # clean spaces and lowercase it
            if description == "":
                description = None                           # empty text counts as missing

        # --- amount: raw text -> positive float ---
        amount = entry.get("amount")
        if isinstance(amount, (int, float)):
            amount = abs(float(amount))                       # already a number, just make it positive
        elif amount is not None:
            text = str(amount).strip().replace(",", "").replace("$", "")  # drop commas and currency sign
            text = text.strip("()-").strip()                  # drop brackets / minus used for negatives
            try:
                amount = float(text)                          # "24,300" -> 24300.0
            except ValueError:
                amount = None                                 # not a valid number, so treat it as missing

        # --- date: raw cell -> date object ---
        raw_date = entry.get("date")
        clean_date = None                                     # stays None if nothing below works
        if isinstance(raw_date, datetime):
            clean_date = raw_date.date()                      # Excel datetime -> plain date
        elif isinstance(raw_date, date):
            clean_date = raw_date                             # already a plain date
        elif isinstance(raw_date, str):
            for fmt in DATE_FORMATS:                          # try each known text format
                try:
                    clean_date = datetime.strptime(raw_date.strip(), fmt).date()
                    break                                     # parsing worked, stop trying
                except ValueError:
                    pass                                      # wrong format, try the next one

        return {"description": description, "type": entry.get("type"),
                "amount": amount, "date": clean_date}

    # missing values flag krta hai
    def get_flags(self, clean):
        # clean = the dictionary returned by normalize_entry
        flags = []                                        # notes about this entry, empty if all is fine
        for field in ("description", "type", "amount", "date"):  # the four fields every node needs
            if clean[field] is None:                      # None means missing or unreadable
                flags.append("missing " + field)          # e.g. "missing date"
        return flags

    def read_row_range(self, row, first_col, last_col, names, source):
        # row = one sheet row, (first_col, last_col) = one table's columns, names = from get_column_names
        entry = {}                                           # will map column name -> raw cell value
        for col in range(first_col, last_col + 1):           # only look inside this table's columns
            cell = row[col] if col < len(row) else None      # short rows count as blank cells
            if cell == "":
                cell = None                                  # treat empty text as blank
            if "amount" in names[col]:
                entry["amount"] = cell
                
            # flipped debit and credit to match ledger
            elif "debit" in names[col] and cell is not None:
                entry["amount"] = cell                 # store the cell under its column name eg {"debit": ---} 
                entry["type"] = "debit"                          # tag the entry with its type
            elif "credit" in names[col] and cell is not None:
                entry["amount"] = cell                 # store the cell under its column name eg {"credit": ---}
                entry["type"] = "credit"                         # tag the entry with its type
            
            else:
                entry[names[col]] = cell                         # store the cell under its column name eg {"date": ---}
        return entry

    def read_entries(self, rows, source):
        start_row = self.find_first_entry_row(rows)           # row where the entries begin
        if start_row is None:
            return []                                         # no entries found in this sheet
        names = self.get_column_names(rows, start_row)        # column names from the header row
        tables = self.find_tables(rows, start_row, names)     # (first, last) or (first, last, type) tuples

        # print("Columns: ", names)
        # print("Tables: ", tables)

        for table in tables:                                  # one table at a time
            first_col, last_col = table[0], table[1]          # first two values are always the column range
            table_type = table[2] if len(table) == 3 else None  # type only exists when there are 2+ tables
            for row in rows[start_row:]:                      # go through all rows of this table
                entry = self.read_row_range(row, first_col, last_col, names, source)  # read this table's cells
                if any(v is not None for v in entry.values()) and not self.is_summary_row(entry):  # skip fully blank ranges
                    if table_type is not None:
                        entry["type"] = table_type                # tag the non-empty entry with its type
                    entry = self.normalize_entry(entry)   # clean description, amount and date in one call
                    entry["flags"] = self.get_flags(entry)

                    # print(source)
                    # print(entry)  # temporary print for validation

                    if source == "ledger":
                        self.entries_ledger.append(entry)                     # keep the entry
                    elif source == "bank":
                        self.entries_bank.append(entry)

    def to_float(self, cell):
        # number or text like "179,300" / "$179,300" -> float
        if isinstance(cell, (int, float)):
            return float(cell)
        text = cell.strip()
        negative = text.startswith(("(", "-")) or text.endswith("-")
        value = float(text.replace(",", "").replace("$", "").strip("()-"))
        # bank statement mein balance negative hoskta hai
        return -value if negative else value  

    # current column kis table mein lie krraha hai - debit or credit (for identifying negative closing balance in ledger)
    def get_side(self, names, tables, col):
        # which side of the cash book a column belongs to: "debit", "credit", or None if unknown
        if col >= len(names):                                 # column outside the header row
            return None                                       # cannot tell, so unknown
        if "debit" in names[col]:
            return "debit"                                    # single table with a debit column
        if "credit" in names[col]:
            return "credit"                                   # single table with a credit column
        for table in tables:                                  # two tables side by side
            if len(table) == 3 and table[0] <= col <= table[1]:   # this table's columns contain col (type is the 3rd value)
                return table[2]                               # "debit" or "credit", read from above the table
        return None                                           # side could not be found

    def get_closing_balance(self, rows, source):
        if source == "ledger":
            start_row = self.find_first_entry_row(rows)            # row where entries begin
            if start_row is None:                                  # sheet without entries has no balance
                return None
            names = self.get_column_names(rows, start_row)         # column names from the header row
            tables = self.find_tables(rows, start_row, names)      # table column ranges, with types when there are two
            for row in rows:                                       # look through every row for a "balance c/d" label
                for col, cell in enumerate(row):
                    if isinstance(cell, str) and any(w in cell.lower() for w in CLOSING_WORDS):
                        for num_col in range(col + 1, len(row)):   # first number to the right of the label
                            if self.is_number(row[num_col]):
                                value = self.to_float(row[num_col])             # the c/d amount
                                side = self.get_side(names, tables, num_col)    # which side the c/d sits on
                                return -value if side == "debit" else value     # c/d on debit side = overdrawn = negative
            return None                                            # no closing balance row found
        
        # bank: the value in the "balance" column on the last row that has one
        start_row = self.find_first_entry_row(rows)
        names = self.get_column_names(rows, start_row)
        balance_col = next((c for c, n in enumerate(names) if "balance" in n), None)
        closing = None
        for row in rows[start_row:]:
            if balance_col is not None and balance_col < len(row) and self.is_number(row[balance_col]):
                closing = self.to_float(row[balance_col])   # last row with a balance wins
        return closing

    def get_entries(self):
        workbook = load_workbook(self.path, data_only=True)    # data_only=True gives values, not formulas
        self.entries_ledger = []                               # reset, so calling twice doesn't duplicate
        self.entries_bank = []
        self.closing = {}

        for sheet in workbook.worksheets:                      # go through the sheets one by one
            # print(sheet)
            name = sheet.title.lower().replace(" ", "")        # "Bank Statement" -> "bankstatement"
            if "ledger" in name or "cashbook" in name:
                source = "ledger"                              # name contains "ledger" = cash ledger
                # print(sheet)
            elif ("bank" in name or "statement" in name) and ("reconciliation" not in name):
                source = "bank"                                # name contains "bank" = bank statement
                # print(sheet)
            else:
                source = None
                continue                                       # unknown sheet name, so skip this sheet
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]  # sheet -> list of rows

            if (source == "bank") or (source == "ledger"):
                self.closing[source] = self.get_closing_balance(rows, source)
                self.read_entries(rows, source)          # read this sheet with its source
        return self.entries_bank, self.entries_ledger, self.closing