"""Excel formula builders shared by the statement compilers.

Face lines are written as live references back to the `TB` worksheet so that
editing a raw balance there cascades through the notes and both statements,
and so that the workbook holds no number that Python computed independently.

Ranges are bounded to the rows the trial balance actually occupies. Whole
column references (`$C:$C`) would sweep a million rows per term and make the
workbook crawl once a statement carries a few dozen lines.
"""

from typing import Iterable, List, Tuple

from fyp_module3.core.taxonomy import face_polarity

TB_SHEET = "TB"
TB_CLASS_COL = "C"   # classification line item id
TB_DEBIT_COL = "E"
TB_CREDIT_COL = "F"

TB_FIRST_ROW = 6


def tb_range(account_count: int, first_row: int = TB_FIRST_ROW) -> Tuple[int, int]:
    """Rows on the TB sheet occupied by `account_count` ledger accounts."""
    return first_row, first_row + max(account_count, 1) - 1


def tb_sumif(line_ids: Iterable[str], rows: Tuple[int, int], tb_sheet: str = TB_SHEET) -> str:
    """Sum the named line items straight off the TB sheet, in face polarity.

    Each id contributes `debit - credit` or `credit - debit` according to the
    side it is presented on, matching `taxonomy.face_amount` exactly.
    """
    ids: List[str] = [lid for lid in line_ids if lid]
    if not ids:
        return "=0"

    first, last = rows
    keys = f"'{tb_sheet}'!${TB_CLASS_COL}${first}:${TB_CLASS_COL}${last}"
    debits = f"'{tb_sheet}'!${TB_DEBIT_COL}${first}:${TB_DEBIT_COL}${last}"
    credits = f"'{tb_sheet}'!${TB_CREDIT_COL}${first}:${TB_CREDIT_COL}${last}"

    terms: List[str] = []
    for lid in ids:
        dr = f'SUMIF({keys},"{lid}",{debits})'
        cr = f'SUMIF({keys},"{lid}",{credits})'
        terms.append(f"({dr}-{cr})" if face_polarity(lid) == "DR" else f"({cr}-{dr})")
    return "=" + "+".join(terms)


def tb_row_amount(line_id: str, tb_row: int, tb_sheet: str = TB_SHEET) -> str:
    """Reference one TB row in the polarity `line_id` is presented on."""
    dr = f"'{tb_sheet}'!{TB_DEBIT_COL}{tb_row}"
    cr = f"'{tb_sheet}'!{TB_CREDIT_COL}{tb_row}"
    return f"={dr}-{cr}" if face_polarity(line_id) == "DR" else f"={cr}-{dr}"
