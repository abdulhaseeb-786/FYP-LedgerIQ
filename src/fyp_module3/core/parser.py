"""Trial Balance Excel and CSV ingestion engine."""

import re
from pathlib import Path
from typing import List, Tuple, Optional, Any, Dict
import openpyxl

from fyp_module3.core.models import StandardizedAccountRecord, UpstreamModulePayload

# Excel error literals that survive a data_only load as text.
EXCEL_ERROR_TOKENS = {"#ref!", "#value!", "#n/a", "#div/0!", "#name?", "#null!", "#num!", "#spill!"}

_NIL_TOKENS = {"-", "—", "–", "n/a", "na", "nil", "none", ""}


def try_parse_numeric(val: Any) -> Optional[float]:
    """Parse a raw cell into a float, or return None when it is not a number.

    Returning None rather than silently coercing to 0.0 lets the caller tell
    "this cell is blank" apart from "this cell holds something we could not
    understand", which is the difference between clean data and silent loss.
    """
    if val is None:
        return 0.0
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if s.lower() in _NIL_TOKENS:
        return 0.0
    if s.lower() in EXCEL_ERROR_TOKENS:
        return None

    # Accounting parentheses denote a negative: (1,234.56)
    is_paren_negative = s.startswith("(") and s.endswith(")")
    if is_paren_negative:
        s = s[1:-1].strip()

    # Leading/trailing Dr/Cr markers are directional, not part of the number.
    s = re.sub(r"^(dr|cr)\.?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*(dr|cr)\.?$", "", s, flags=re.IGNORECASE)

    # Strip currency symbols, codes and thousands separators; keep sign/decimal.
    cleaned = re.sub(r"[^\d.\-+]", "", s)
    if cleaned in ("", "-", "+", ".", "-.", "+."):
        return None

    # Reject ambiguous shapes such as "1.234.567" rather than guessing.
    if cleaned.count(".") > 1:
        return None
    if cleaned.count("-") > 1 or ("-" in cleaned and not cleaned.startswith("-")):
        return None

    try:
        num = float(cleaned)
    except ValueError:
        return None
    return -num if is_paren_negative else num


def parse_numeric(val: Any) -> float:
    """Lenient wrapper for callers that cannot act on a parse failure."""
    parsed = try_parse_numeric(val)
    return 0.0 if parsed is None else parsed


def is_error_cell(val: Any) -> bool:
    """True when a cell carries a spreadsheet error literal."""
    return val is not None and str(val).strip().lower() in EXCEL_ERROR_TOKENS


# -------------------------------------------------------------------------
# Row classification
# -------------------------------------------------------------------------

_HEADER_KEYWORDS = {
    "trial balance", "description", "account name", "account title", "particulars",
    "head of account", "s.no", "sno", "sr no", "sr.no", "serial", "code",
    "debit", "credit", "dr", "cr", "amount", "account", "narration",
}

# Words that, once the total words are removed, still describe a statement
# grouping rather than a real ledger account.
_STRUCTURAL_WORDS = {
    "asset", "assets", "liability", "liabilities", "equity", "capital",
    "expense", "expenses", "expenditure", "income", "revenue", "revenues",
    "debit", "debits", "credit", "credits", "current", "non", "noncurrent",
    "fixed", "trial", "balance", "sheet", "profit", "loss", "payable",
    "payables", "receivable", "receivables", "sales", "purchases", "cost",
    "bf", "cf", "b/f", "c/f", "all", "the", "of", "and", "for", "amount",
    "column", "columns", "page", "net", "gross", "brought", "carried",
    "forward", "down", "this", "above", "below", "section",
}

_TOTAL_TOKENS = {"total", "totals", "grand", "sub", "subtotal", "sum", "checksum"}

_CHECK_LABEL = re.compile(
    r"^(check\s*sum|checksum|difference|variance|balance\s+check|out\s+of\s+balance)\s*[:\-]?$"
)


def is_header_row(name: str) -> bool:
    """True when a row is a sheet title or a column header, never an account."""
    if not name:
        return True
    return name.strip().lower().rstrip(":") in _HEADER_KEYWORDS


def is_total_label(name: str) -> bool:
    """True when `name` reads as a total caption rather than an account title.

    The test is structural: strip the total words and inspect what is left.
    "Total" and "Total Assets" are captions; "Total Quality Management Fees"
    is a real expense account and must survive ingestion.
    """
    if not name:
        return False
    s = name.strip().lower()
    if _CHECK_LABEL.match(s):
        return True
    tokens = [t for t in re.split(r"[^a-z/]+", s) if t]
    if not tokens or not any(t in _TOTAL_TOKENS for t in tokens):
        return False
    remainder = [t for t in tokens if t not in _TOTAL_TOKENS]
    return all(t in _STRUCTURAL_WORDS for t in remainder)


def is_summary_or_header_row(name: str) -> bool:
    """Backwards-compatible predicate: header rows and total captions."""
    return is_header_row(name) or is_total_label(name)


# -------------------------------------------------------------------------
# Column detection
# -------------------------------------------------------------------------

def _looks_like_header_cell(text: str, keys: List[str], exact: List[str]) -> bool:
    return len(text) <= 24 and (any(k in text for k in keys) or text in exact)


def _numeric_profile(rows: List[List[Any]], col: int, start: int) -> Dict[str, Any]:
    """Summarise what a column contains from row `start` downwards."""
    numeric = 0
    texty = 0
    values: List[float] = []
    for row in rows[start:]:
        if col >= len(row):
            continue
        val = row[col]
        if val is None or str(val).strip() == "":
            continue
        parsed = try_parse_numeric(val)
        if parsed is None:
            texty += 1
        else:
            numeric += 1
            values.append(parsed)
    return {
        "numeric": numeric,
        "text": texty,
        "total": round(sum(values), 2),
        "nonzero": sum(1 for v in values if abs(v) > 1e-9),
    }


def _choose_amount_pair(
    rows: List[List[Any]],
    dr_cols: List[int],
    cr_cols: List[int],
    start_row: int,
) -> Tuple[int, int]:
    """Pick the debit/credit pair to read when a sheet carries several.

    Real workbooks commonly lay out branch columns, an adjustments column and
    an adjusted column side by side. Taking the leftmost pair reads one branch
    in isolation and reports a large false imbalance, so each pair is scored on
    how close it comes to balancing and how much of the ledger it covers. Among
    the pairs that balance, the rightmost wins: that is where the adjusted or
    final columns sit in conventional layouts.
    """
    pairs: List[Tuple[int, int]] = []
    used: set = set()
    for dr in sorted(dr_cols):
        for cr in sorted(cr_cols):
            if cr > dr and cr not in used:
                pairs.append((dr, cr))
                used.add(cr)
                break
    if not pairs:
        return dr_cols[0], cr_cols[0]
    if len(pairs) == 1:
        return pairs[0]

    scored = []
    for dr, cr in pairs:
        dr_profile = _numeric_profile(rows, dr, start_row)
        cr_profile = _numeric_profile(rows, cr, start_row)
        volume = max(abs(dr_profile["total"]), abs(cr_profile["total"]), 1.0)
        imbalance = abs(dr_profile["total"] - cr_profile["total"]) / volume
        coverage = dr_profile["nonzero"] + cr_profile["nonzero"]
        scored.append((imbalance, coverage, dr, cr))

    max_coverage = max(s[1] for s in scored)
    # A sparse adjustments column balances trivially; it must not outrank the
    # ledger itself, so anything covering far fewer rows is set aside.
    eligible = [s for s in scored if s[1] >= 0.5 * max_coverage] or scored

    balanced = [s for s in eligible if s[0] < 0.05]
    if balanced:
        best = max(balanced, key=lambda s: s[2])
    else:
        best = min(eligible, key=lambda s: s[0])
    return best[2], best[3]


def _detect_by_header(rows: List[List[Any]]) -> Optional[Tuple[Optional[int], int, int, int, int]]:
    """Locate the columns from an explicit header row, when one exists."""
    for r_idx, row in enumerate(rows[:25]):
        cells = [str(c).strip().lower() if c is not None else "" for c in row]

        dr_all = [i for i, c in enumerate(cells)
                  if _looks_like_header_cell(c, ["debit", "dr."], ["dr", "dr (pkr)", "dr(pkr)"])]
        cr_all = [i for i, c in enumerate(cells)
                  if _looks_like_header_cell(c, ["credit", "cr."], ["cr", "cr (pkr)", "cr(pkr)"])]
        # A single "Debit/Credit" column is not a pair of columns.
        dr_cols = [i for i in dr_all if i not in cr_all]
        cr_cols = [i for i in cr_all if i not in dr_all]

        if dr_cols and cr_cols:
            dr_col, cr_col = _choose_amount_pair(rows, dr_cols, cr_cols, r_idx + 1)
            name_cands = [
                i for i, c in enumerate(cells)
                if any(k in c for k in ["name", "description", "particular", "title", "head", "account"])
                and i not in (dr_col, cr_col)
            ]
            name_col = name_cands[0] if name_cands else max(0, min(dr_col, cr_col) - 1)

            code_cands = [
                i for i, c in enumerate(cells)
                if any(k in c for k in ["code", "a/c no", "acc no", "number", "s.no", "sno"])
                and i not in (dr_col, cr_col, name_col)
            ]
            code_col = code_cands[0] if code_cands else None
            return code_col, name_col, dr_col, cr_col, r_idx + 1

        has_descr = any(k in c for c in cells
                        for k in ["description", "particular", "narrative", "details", "title"])
        if has_descr and bool(dr_cols) != bool(cr_cols):
            found = "Credit" if cr_cols else "Debit"
            missing = "Debit" if cr_cols else "Credit"
            raise ValueError(
                "Single-sided transaction extract detected: sheet contains a "
                f"'{found}' column without a corresponding '{missing}' column. "
                "Statutory financial statements require a complete double-entry "
                "Trial Balance with both Debit and Credit columns."
            )
    return None


def _detect_by_shape(rows: List[List[Any]]) -> Tuple[Optional[int], int, int, int, int]:
    """Infer the columns when the sheet has no header row.

    Picks the description column by text density, then scores every candidate
    (debit, credit) pair to its right by how close that pair comes to
    balancing. An account-code column is numeric but never balances against
    anything, so it loses on score instead of being mistaken for money.
    """
    width = max((len(r) for r in rows), default=0)
    if width < 2:
        raise ValueError("Worksheet does not contain enough columns to hold a Trial Balance.")

    profiles = {c: _numeric_profile(rows, c, 0) for c in range(width)}

    text_cols = [c for c in range(width) if profiles[c]["text"] > 0]
    name_col = max(text_cols, key=lambda c: (profiles[c]["text"], -c)) if text_cols else 0

    numeric_cols = [c for c in range(width) if c != name_col and profiles[c]["nonzero"] > 0]
    right_cols = [c for c in numeric_cols if c > name_col] or numeric_cols
    if len(right_cols) < 2:
        raise ValueError(
            "Could not detect distinct Debit and Credit columns. Single-sided extracts "
            "(e.g. bank credit schedules) cannot be processed as a double-entry Trial Balance."
        )

    best = None
    best_score = None
    for i, dr in enumerate(right_cols):
        for cr in right_cols[i + 1:]:
            dr_total = profiles[dr]["total"]
            cr_total = profiles[cr]["total"]
            volume = max(abs(dr_total), abs(cr_total), 1.0)
            imbalance = abs(dr_total - cr_total) / volume
            coverage = profiles[dr]["nonzero"] + profiles[cr]["nonzero"]
            # Prefer a balancing pair; break ties toward broader coverage and
            # toward the rightmost columns.
            score = (imbalance, -coverage, -(dr + cr))
            if best_score is None or score < best_score:
                best, best_score = (dr, cr), score

    dr_col, cr_col = best
    code_candidates = [c for c in range(width)
                       if c not in (name_col, dr_col, cr_col) and profiles[c]["numeric"] > 0]
    code_col = code_candidates[0] if code_candidates else None
    return code_col, name_col, dr_col, cr_col, 0


def _refine_name_column(
    rows: List[List[Any]],
    code_col: Optional[int],
    name_col: int,
    dr_col: int,
    cr_col: int,
    start_row: int,
) -> Tuple[Optional[int], int]:
    """Correct a header-chosen name column that actually holds account codes.

    Real ledgers often head the code column "Account Name" and keep the
    descriptions in an unlabelled column beside it. Trusting the header there
    yields a statement full of accounts called "1020101", so the choice is
    checked against what the column actually contains.
    """
    profile = _numeric_profile(rows, name_col, start_row)
    looks_like_codes = profile["numeric"] > profile["text"]
    if not looks_like_codes:
        return code_col, name_col

    # Look for a better description column between the labelled one and the
    # first amount column.
    limit = min(dr_col, cr_col)
    candidates = [
        c for c in range(len(max(rows, key=len)))
        if c not in (dr_col, cr_col) and c != name_col and c < max(limit, name_col + 1)
    ]
    best = None
    for c in candidates:
        candidate = _numeric_profile(rows, c, start_row)
        if candidate["text"] > profile["text"] and candidate["text"] > candidate["numeric"]:
            if best is None or candidate["text"] > _numeric_profile(rows, best, start_row)["text"]:
                best = c
    if best is None:
        return code_col, name_col
    return name_col, best


def detect_columns(rows: List[List[Any]]) -> Tuple[Optional[int], int, int, int, int]:
    """Detect (code_col, name_col, dr_col, cr_col, data_start_row)."""
    detected = _detect_by_header(rows)
    if detected is not None:
        code_col, name_col, dr_col, cr_col, start_row = detected
        code_col, name_col = _refine_name_column(
            rows, code_col, name_col, dr_col, cr_col, start_row)
        return code_col, name_col, dr_col, cr_col, start_row
    return _detect_by_shape(rows)


# -------------------------------------------------------------------------
# Sheet selection
# -------------------------------------------------------------------------

_EXCLUDED_SHEET_TERMS = ["grouping", "mapping", "chart of account", "reference", "lookup"]
_TB_SHEET_PATTERN = re.compile(r"(\btrial\s*balance\b|\btrial\b|\btb\b|\bt/b\b)", re.IGNORECASE)
_COA_PATTERN = re.compile(r"\bcoa\b", re.IGNORECASE)


def _select_sheet(wb, sheet_name: Optional[str]):
    if sheet_name:
        if sheet_name not in wb.sheetnames:
            raise ValueError(
                f"Worksheet '{sheet_name}' not found. Available sheets: {', '.join(wb.sheetnames)}."
            )
        return wb[sheet_name]

    valid = [n for n in wb.sheetnames
             if not any(t in n.strip().lower() for t in _EXCLUDED_SHEET_TERMS)
             and not _COA_PATTERN.search(n)]

    for name in valid:
        if _TB_SHEET_PATTERN.search(name):
            return wb[name]
    if valid:
        return wb[valid[0]]
    return wb.active or wb.worksheets[0]


# -------------------------------------------------------------------------
# Ingestion
# -------------------------------------------------------------------------

_EMBEDDED_CODE = re.compile(r"^([0-9][0-9\-/]{2,9})[\s.·\-:]+(.*)$")
_TOTAL_WORD = re.compile(r"\b(total|totals|sum|checksum)\b", re.IGNORECASE)


def parse_trial_balance(file_path: str, sheet_name: Optional[str] = None) -> UpstreamModulePayload:
    """Ingest a Trial Balance Excel workbook and return a standardized payload."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Trial balance file not found: {file_path}")

    wb = openpyxl.load_workbook(file_path, data_only=True)
    target_sheet = _select_sheet(wb, sheet_name)

    raw_rows: List[List[Any]] = []
    for row in target_sheet.iter_rows(values_only=True):
        if any(c is not None and str(c).strip() != "" for c in row):
            raw_rows.append(list(row))

    if not raw_rows:
        raise ValueError(f"Sheet '{target_sheet.title}' is empty.")

    # Track error cells by position so a broken cell that also sits in an
    # amount column is reported once rather than twice.
    error_positions = {
        (r_idx, c_idx)
        for r_idx, row in enumerate(raw_rows)
        for c_idx, cell in enumerate(row)
        if is_error_cell(cell)
    }

    code_col, name_col, dr_col, cr_col, start_row = detect_columns(raw_rows)

    records: List[StandardizedAccountRecord] = []
    skipped_labels: List[str] = []
    junk_rows = 0
    running_dr = 0.0
    running_cr = 0.0

    for r_idx in range(start_row, len(raw_rows)):
        row = raw_rows[r_idx]

        name_val = row[name_col] if name_col < len(row) else None
        raw_name = str(name_val).strip() if name_val is not None else ""

        dr_raw = row[dr_col] if dr_col < len(row) else None
        cr_raw = row[cr_col] if cr_col < len(row) else None
        dr_parsed = try_parse_numeric(dr_raw)
        cr_parsed = try_parse_numeric(cr_raw)

        if dr_parsed is None or cr_parsed is None:
            for col, parsed in ((dr_col, dr_parsed), (cr_col, cr_parsed)):
                if parsed is None:
                    error_positions.add((r_idx, col))
            junk_rows += 1
            skipped_labels.append(
                f"Row {r_idx + 1}: unreadable amount in '{raw_name or '(blank)'}'"
            )
            continue

        if not raw_name:
            junk_rows += 1
            continue

        if is_header_row(raw_name):
            junk_rows += 1
            skipped_labels.append(f"Row {r_idx + 1}: header '{raw_name}'")
            continue

        # Total captions are never accounts. A section subtotal is skipped and
        # ingestion continues; only the grand total of the table ends it, and
        # that is recognised by BOTH sides reproducing the running totals
        # rather than by wording, because "Total Equity" appearing after the
        # first section would otherwise truncate the whole ledger.
        if is_total_label(raw_name):
            is_grand_total = (
                len(records) >= 2
                and running_dr > 0 and running_cr > 0
                and abs(dr_parsed - running_dr) < 0.01
                and abs(cr_parsed - running_cr) < 0.01
            )
            junk_rows += 1
            if is_grand_total:
                skipped_labels.append(
                    f"Row {r_idx + 1}: grand total '{raw_name}' - ingestion stopped")
                break
            skipped_labels.append(f"Row {r_idx + 1}: subtotal '{raw_name}' - skipped")
            continue

        code_val = None
        if code_col is not None and code_col < len(row) and row[code_col] is not None:
            code_val = str(row[code_col]).strip()

        if not code_val:
            embedded = _EMBEDDED_CODE.match(raw_name)
            if embedded and embedded.group(2).strip():
                code_val = embedded.group(1).strip()
                raw_name = embedded.group(2).strip()

        if abs(dr_parsed) < 1e-6 and abs(cr_parsed) < 1e-6:
            junk_rows += 1
            skipped_labels.append(f"Row {r_idx + 1}: nil balance '{raw_name}'")
            continue

        running_dr += dr_parsed
        running_cr += cr_parsed
        records.append(StandardizedAccountRecord(
            account_code=code_val,
            account_name=raw_name,
            debit=dr_parsed,
            credit=cr_parsed,
            net_balance=dr_parsed - cr_parsed,
            tb_row_index=r_idx + 1,
        ))

    error_cells = len(error_positions)
    total_dr = sum(r.debit for r in records)
    total_cr = sum(r.credit for r in records)
    delta = round(total_dr - total_cr, 2)

    audit_notes = [f"Ingested {len(records)} accounts from sheet '{target_sheet.title}'."]
    if junk_rows:
        audit_notes.append(f"Skipped {junk_rows} non-ledger row(s) during ingestion.")
    if error_cells:
        audit_notes.append(f"Encountered {error_cells} unreadable or errored cell(s).")

    return UpstreamModulePayload(
        client_id=path.stem,
        period_ended="June 30, 2025",
        accounts=records,
        is_balanced=abs(delta) < 0.01,
        delta=delta,
        audit_notes=audit_notes,
        total_raw_rows=max(0, len(raw_rows) - start_row),
        junk_rows_skipped=junk_rows,
        error_cells_detected=error_cells,
        skipped_row_labels=skipped_labels,
        source_sheet=target_sheet.title,
    )
