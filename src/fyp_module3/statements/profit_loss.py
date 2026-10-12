"""Statement of Profit or Loss compiler."""

from typing import List, Dict, Optional, Any

from fyp_module3.core.models import StandardizedAccountRecord
from fyp_module3.core.taxonomy import face_amount
from fyp_module3.statements.notes_compiler import NotesCompiler
from fyp_module3.statements.formulas import tb_sumif, tb_range

# Every pl.* line item this statement renders; published so the leakage check
# can prove no classified account is dropped on the way to the workbook.
RENDERED_LINE_IDS = frozenset({
    "pl.revenue", "pl.salesreturns", "pl.cos", "pl.distribution", "pl.admin",
    "pl.depreciation", "pl.otherexp", "pl.otherincome", "pl.finance", "pl.tax",
})


class ProfitLossStatement:
    """Compiles the Statement of Profit or Loss with dynamic formula linkages."""

    rendered_line_ids = RENDERED_LINE_IDS

    def __init__(self, notes_compiler: NotesCompiler):
        self.notes_compiler = notes_compiler
        self.rows: List[Dict[str, Any]] = []
        self.net_profit: float = 0.0
        self.profit_before_tax: float = 0.0
        self.net_profit_cell_ref: Optional[str] = None
        self.pbt_cell_ref: Optional[str] = None
        self.reconciliation_errors: List[str] = []

    # -----------------------------------------------------------------
    def _sum(self, *line_ids: str) -> float:
        return round(sum(self._amounts.get(lid, 0.0) for lid in line_ids), 2)

    def _note_linked(self, note_number: int, label: str, amount: float) -> Optional[str]:
        """Link a face line to its note subtotal, but only if the two agree."""
        ref = self.notes_compiler.get_note_cell_ref(note_number)
        if ref is None:
            return None
        note_total = self.notes_compiler.get_note_total(note_number)
        if note_total is None or abs(note_total - amount) > 0.01:
            self.reconciliation_errors.append(
                f"Note {note_number} subtotal {note_total:,.2f} does not agree with "
                f"'{label}' at {amount:,.2f} (difference {(note_total or 0.0) - amount:,.2f})."
            )
            return None
        return f"={ref}"

    def _row(self, cur: int, label: str, amount: Optional[float],
             note: Optional[int] = None, formula: Optional[str] = None,
             style: str = "normal") -> int:
        self.rows.append({"row": cur, "label": label, "note": note,
                          "amount": amount, "formula": formula, "style": style})
        return cur + 1

    # -----------------------------------------------------------------
    def compile(
        self,
        accounts: List[StandardizedAccountRecord],
        start_row: int = 6,
        tb_first_row: int = 6,
    ) -> List[Dict[str, Any]]:
        """Construct statement rows with live formula linkages."""
        self._tb_rows = tb_range(len(accounts), tb_first_row)
        self._amounts: Dict[str, float] = {}
        for acc in accounts:
            line_id = acc.line_item_id or ""
            if line_id.startswith("pl."):
                self._amounts[line_id] = self._amounts.get(line_id, 0.0) + face_amount(
                    line_id, acc.debit, acc.credit
                )

        self.rows = []
        self.reconciliation_errors = []
        cur = start_row

        # 1. Revenue, net of returns. Sales returns carry credit-side polarity,
        #    so they are already negative and simply add in.
        net_rev = self._sum("pl.revenue", "pl.salesreturns")
        rev_row = cur
        cur = self._row(cur, "Revenue - net", net_rev,
                        formula=tb_sumif(["pl.revenue", "pl.salesreturns"], self._tb_rows))

        # 2. Cost of sales (Note 11)
        cos = self._sum("pl.cos")
        cos_row = cur
        cur = self._row(cur, "Cost of sales", cos,
                        note=11 if self.notes_compiler.get_note_cell_ref(11) else None,
                        formula=(self._note_linked(11, "Cost of sales", cos)
                                 or tb_sumif(["pl.cos"], self._tb_rows)))

        # 3. Gross profit
        gp_row = cur
        cur = self._row(cur, "Gross profit / (loss)", round(net_rev - cos, 2),
                        formula=f"=C{rev_row}-C{cos_row}", style="subtotal")

        # 4. Operating expenses
        dist = self._sum("pl.distribution")
        dist_row = cur
        cur = self._row(cur, "Distribution and selling expenses", dist,
                        formula=tb_sumif(["pl.distribution"], self._tb_rows))

        admin = self._sum("pl.admin", "pl.depreciation")
        admin_row = cur
        cur = self._row(cur, "Administrative expenses", admin,
                        note=12 if self.notes_compiler.get_note_cell_ref(12) else None,
                        formula=(self._note_linked(12, "Administrative expenses", admin)
                                 or tb_sumif(["pl.admin", "pl.depreciation"], self._tb_rows)))

        # 5. Operating profit
        operating = round(net_rev - cos - dist - admin, 2)
        op_row = cur
        cur = self._row(cur, "Operating profit / (loss)", operating,
                        formula=f"=C{gp_row}-(C{dist_row}+C{admin_row})", style="subtotal")

        # 6. Other income and expenses
        other_income = self._sum("pl.otherincome")
        oi_row = cur
        cur = self._row(cur, "Other income", other_income,
                        formula=tb_sumif(["pl.otherincome"], self._tb_rows))

        other_exp = self._sum("pl.otherexp")
        oe_row = cur
        cur = self._row(cur, "Other operating expenses", other_exp,
                        formula=tb_sumif(["pl.otherexp"], self._tb_rows))

        # 7. Finance cost
        finance = self._sum("pl.finance")
        fc_row = cur
        cur = self._row(cur, "Finance cost", finance, formula=tb_sumif(["pl.finance"], self._tb_rows))

        # 8. Profit before taxation
        pbt = round(operating + other_income - other_exp - finance, 2)
        pbt_row = cur
        cur = self._row(cur, "Profit / (loss) before taxation", pbt,
                        formula=f"=C{op_row}+C{oi_row}-C{oe_row}-C{fc_row}", style="subtotal")

        # 9. Taxation
        tax = self._sum("pl.tax")
        tax_row = cur
        cur = self._row(cur, "Taxation", tax, formula=tb_sumif(["pl.tax"], self._tb_rows))

        # 10. Profit after taxation
        net_profit = round(pbt - tax, 2)
        pat_row = cur
        self._row(cur, "Profit / (loss) after taxation", net_profit,
                  formula=f"=C{pbt_row}-C{tax_row}", style="grand_total")

        self.profit_before_tax = pbt
        self.net_profit = net_profit
        self.pbt_cell_ref = f"'Profit or Loss'!C{pbt_row}"
        self.net_profit_cell_ref = f"'Profit or Loss'!C{pat_row}"
        return self.rows
