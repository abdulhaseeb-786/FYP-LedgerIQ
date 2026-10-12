"""Statement of Changes in Equity compiler."""

from typing import List, Dict, Optional, Any

from fyp_module3.core.models import StandardizedAccountRecord
from fyp_module3.core.taxonomy import face_amount
from fyp_module3.statements.formulas import tb_sumif, tb_range

# Columns on the exported sheet: B = capital and reserves, C = unappropriated
# profit, D = total.
_CAPITAL_COL = "B"
_RETAINED_COL = "C"

_BROUGHT_FORWARD_CAPITAL = ["sofp.eq.sharecapital", "sofp.eq.capitalaccount", "sofp.eq.reserves"]
_BROUGHT_FORWARD_RETAINED = ["sofp.eq.retained", "sofp.eq.cy_profit_summary"]


class EquityStatement:
    """Compiles the Statement of Changes in Equity.

    The closing balances here are the same figures the balance sheet reports,
    built from the same line items, so the two statements cannot drift apart.
    """

    def __init__(self):
        self.rows: List[Dict[str, Any]] = []
        self.closing_capital: float = 0.0
        self.closing_retained: float = 0.0
        self.total_equity: float = 0.0

    def compile(
        self,
        accounts: List[StandardizedAccountRecord],
        net_profit_ref: Optional[str] = None,
        net_profit: float = 0.0,
        period_label: str = "the period end",
        start_row: int = 6,
        tb_first_row: int = 6,
    ) -> List[Dict[str, Any]]:
        """Construct Statement of Changes in Equity table rows."""
        tb_rows = tb_range(len(accounts), tb_first_row)
        amounts: Dict[str, float] = {}
        for acc in accounts:
            lid = acc.line_item_id or ""
            if lid.startswith("sofp.eq."):
                amounts[lid] = amounts.get(lid, 0.0) + face_amount(lid, acc.debit, acc.credit)

        def total(ids):
            return round(sum(amounts.get(i, 0.0) for i in ids), 2)

        bf_capital = total(_BROUGHT_FORWARD_CAPITAL)
        bf_retained = total(_BROUGHT_FORWARD_RETAINED)
        drawings = total(["sofp.eq.drawings"])      # already negative (credit polarity)
        dividend = total(["sofp.eq.dividend"])      # already negative

        self.rows = []
        cur = start_row

        # The opening figure is what the ledger carries before this period's
        # result is appropriated - it is not a restated prior-year balance,
        # and is labelled accordingly rather than as "Balance as at July 01".
        self.rows.append({
            "row": cur,
            "label": "Balance brought forward per trial balance",
            "capital_formula": tb_sumif(_BROUGHT_FORWARD_CAPITAL, tb_rows),
            "retained_formula": tb_sumif(_BROUGHT_FORWARD_RETAINED, tb_rows),
            "capital": bf_capital,
            "retained": bf_retained,
            "total_formula": f"={_CAPITAL_COL}{cur}+{_RETAINED_COL}{cur}",
            "style": "normal",
        })
        cur += 1

        self.rows.append({
            "row": cur,
            "label": "Total comprehensive income / (loss) for the year",
            "capital": 0.0,
            "retained": net_profit,
            "retained_formula": f"={net_profit_ref}" if net_profit_ref else "=0",
            "total_formula": f"={_CAPITAL_COL}{cur}+{_RETAINED_COL}{cur}",
            "style": "normal",
        })
        cur += 1

        if drawings != 0:
            self.rows.append({
                "row": cur,
                "label": "Drawings during the year",
                "capital": drawings,
                "capital_formula": tb_sumif(["sofp.eq.drawings"], tb_rows),
                "retained": 0.0,
                "total_formula": f"={_CAPITAL_COL}{cur}+{_RETAINED_COL}{cur}",
                "style": "normal",
            })
            cur += 1

        if dividend != 0:
            self.rows.append({
                "row": cur,
                "label": "Dividend declared during the year",
                "capital": 0.0,
                "retained": dividend,
                "retained_formula": tb_sumif(["sofp.eq.dividend"], tb_rows),
                "total_formula": f"={_CAPITAL_COL}{cur}+{_RETAINED_COL}{cur}",
                "style": "normal",
            })
            cur += 1

        end_r = cur - 1
        self.closing_capital = round(bf_capital + drawings, 2)
        self.closing_retained = round(bf_retained + net_profit + dividend, 2)
        self.total_equity = round(self.closing_capital + self.closing_retained, 2)

        self.rows.append({
            "row": cur,
            "label": f"Balance as at {period_label}",
            "capital_formula": f"=SUM({_CAPITAL_COL}{start_row}:{_CAPITAL_COL}{end_r})",
            "retained_formula": f"=SUM({_RETAINED_COL}{start_row}:{_RETAINED_COL}{end_r})",
            "capital": self.closing_capital,
            "retained": self.closing_retained,
            "total_formula": f"={_CAPITAL_COL}{cur}+{_RETAINED_COL}{cur}",
            "style": "grand_total",
        })

        return self.rows
