"""Statement of Cash Flows (Indirect Method) compiler."""

from typing import List, Dict, Optional, Any

from fyp_module3.core.models import StandardizedAccountRecord
from fyp_module3.core.taxonomy import face_amount
from fyp_module3.statements.formulas import tb_sumif, tb_range

_CASH_IDS = ["sofp.ca.cash"]


class CashFlowStatement:
    """Compiles the Statement of Cash Flows using the indirect method.

    A single-period trial balance carries no opening balances, so the split of
    the movement between working capital, investing and financing activities is
    not derivable. Rather than publishing zeros - which left the old statement
    closing on a cash figure unrelated to the balance sheet - the undetermined
    portion is shown on its own line and the statement is made to close on the
    cash actually reported in the balance sheet.
    """

    def __init__(self):
        self.rows: List[Dict[str, Any]] = []
        self.closing_cash: float = 0.0
        self.undetermined_movement: float = 0.0

    def compile(
        self,
        accounts: List[StandardizedAccountRecord],
        pbt_ref: Optional[str] = None,
        cash_note_ref: Optional[str] = None,
        profit_before_tax: float = 0.0,
        opening_cash: float = 0.0,
        start_row: int = 6,
        tb_first_row: int = 6,
    ) -> List[Dict[str, Any]]:
        """Construct Cash Flow statement rows."""
        tb_rows = tb_range(len(accounts), tb_first_row)
        amounts: Dict[str, float] = {}
        for acc in accounts:
            lid = acc.line_item_id or ""
            if lid:
                amounts[lid] = amounts.get(lid, 0.0) + face_amount(lid, acc.debit, acc.credit)

        depreciation = round(amounts.get("pl.depreciation", 0.0), 2)
        finance_cost = round(amounts.get("pl.finance", 0.0), 2)
        closing_cash = round(amounts.get("sofp.ca.cash", 0.0), 2)

        self.closing_cash = closing_cash
        net_movement = round(closing_cash - opening_cash, 2)
        operating_before_wc = round(profit_before_tax + depreciation + finance_cost, 2)
        undetermined = round(net_movement - operating_before_wc, 2)
        self.undetermined_movement = undetermined

        rows: List[Dict[str, Any]] = []
        cur = start_row

        def add(label, amount=None, formula=None, style="normal"):
            nonlocal cur
            rows.append({"row": cur, "label": label, "note": None,
                         "amount": amount, "formula": formula, "style": style})
            cur += 1
            return cur - 1

        add("CASH FLOWS FROM OPERATING ACTIVITIES", style="section_header")
        pbt_row = add("Profit / (loss) before taxation", profit_before_tax,
                      f"={pbt_ref}" if pbt_ref else "=0")
        add("Adjustments for non-cash and other items:", style="sub_header")
        depn_row = add("  Depreciation and amortisation", depreciation,
                       tb_sumif(["pl.depreciation"], tb_rows))
        fc_row = add("  Finance cost", finance_cost, tb_sumif(["pl.finance"], tb_rows))

        op_wc_row = add("Operating cash flows before working capital changes",
                        operating_before_wc,
                        f"=C{pbt_row}+C{depn_row}+C{fc_row}", style="subtotal")

        undet_row = add(
            "Movements in working capital, investing and financing activities "
            "(not determinable from a single-period trial balance)",
            undetermined, None)

        net_inc_row = add("Net increase / (decrease) in cash and cash equivalents",
                          net_movement, f"=C{op_wc_row}+C{undet_row}", style="subtotal")

        open_row = add("Cash and cash equivalents at beginning of the year",
                       opening_cash, f"={opening_cash}")

        closing_formula = f"={cash_note_ref}" if cash_note_ref else tb_sumif(_CASH_IDS, tb_rows)
        close_row = add("Cash and cash equivalents at end of the year",
                        closing_cash, f"=C{net_inc_row}+C{open_row}", style="grand_total")

        add("")
        add("RECONCILIATION TO BALANCE SHEET (must be nil)", style="sub_header")
        sofp_row = add("Cash and bank balances per Statement of Financial Position",
                       closing_cash, closing_formula)
        add("Variance", 0.0, f"=C{close_row}-C{sofp_row}", style="check")

        self.rows = rows
        return rows
