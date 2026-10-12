"""Statement of Financial Position (Balance Sheet) compiler with dynamic linkages."""

from typing import List, Dict, Optional, Any

from fyp_module3.core.models import StandardizedAccountRecord
from fyp_module3.core.taxonomy import face_amount
from fyp_module3.statements.notes_compiler import NotesCompiler
from fyp_module3.statements.formulas import tb_sumif, tb_range

# Every sofp.* line item this statement renders. Anything classified into a
# sofp.* id that is absent from here would silently vanish from the balance
# sheet, so `rendered_line_ids` is published for the leakage check to verify.
_NCA_IDS = ["sofp.nca.ppe", "sofp.nca.accdep", "sofp.nca.ltdeposits",
            "sofp.nca.intangible", "sofp.nca.ltinvest", "sofp.nca.dta"]
_CA_IDS = ["sofp.ca.stores", "sofp.ca.stock", "sofp.ca.debtors", "sofp.ca.allowance_ecl",
           "sofp.ca.advances", "sofp.ca.stinvest", "sofp.ca.taxrefund", "sofp.ca.cash",
           "sofp.ca.suspense"]
_EQ_IDS = ["sofp.eq.sharecapital", "sofp.eq.capitalaccount", "sofp.eq.drawings",
           "sofp.eq.reserves", "sofp.eq.retained", "sofp.eq.cy_profit_summary",
           "sofp.eq.dividend"]
_NCL_IDS = ["sofp.ncl.ltborrow", "sofp.ncl.lease", "sofp.ncl.deftax",
            "sofp.ncl.ltprov", "sofp.ncl.directorloan"]
_CL_IDS = ["sofp.cl.payables", "sofp.cl.accrued", "sofp.cl.stborrow", "sofp.cl.lease",
           "sofp.cl.currentportion", "sofp.cl.provtax", "sofp.cl.unclaimeddiv",
           "sofp.cl.suspense"]

RENDERED_LINE_IDS = frozenset(_NCA_IDS + _CA_IDS + _EQ_IDS + _NCL_IDS + _CL_IDS)


class BalanceSheetStatement:
    """Compiles the classified Balance Sheet per Fifth Schedule."""

    rendered_line_ids = RENDERED_LINE_IDS

    def __init__(self, notes_compiler: NotesCompiler):
        self.notes_compiler = notes_compiler
        self.rows: List[Dict[str, Any]] = []
        self.total_assets: float = 0.0
        self.total_equity_and_liabilities: float = 0.0
        self.total_equity: float = 0.0
        self.total_non_current_liabilities: float = 0.0
        self.total_current_liabilities: float = 0.0
        self.total_non_current_assets: float = 0.0
        self.total_current_assets: float = 0.0
        # Populated when a note subtotal disagrees with the face line it feeds.
        self.reconciliation_errors: List[str] = []

    # -----------------------------------------------------------------
    def _sum(self, *line_ids: str) -> float:
        return round(sum(self._amounts.get(lid, 0.0) for lid in line_ids), 2)

    def _live(self, *line_ids: str) -> str:
        """Formula pulling `line_ids` live off the TB worksheet."""
        return tb_sumif(line_ids, self._tb_rows)

    def _note_linked(self, note_number: int, label: str, amount: float) -> Optional[str]:
        """Return the formula linking a face line to its note subtotal.

        The workbook ships the formula, not the Python amount, so the two must
        agree. A disagreement is recorded rather than silently exported.
        """
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
        net_profit_ref: Optional[str] = None,
        net_profit: float = 0.0,
        start_row: int = 6,
        tb_first_row: int = 6,
    ) -> List[Dict[str, Any]]:
        """Construct Statement of Financial Position rows with live formula linkages."""
        self._tb_rows = tb_range(len(accounts), tb_first_row)
        self._amounts: Dict[str, float] = {}
        for acc in accounts:
            line_id = acc.line_item_id or ""
            if line_id.startswith("sofp."):
                self._amounts[line_id] = self._amounts.get(line_id, 0.0) + face_amount(
                    line_id, acc.debit, acc.credit
                )

        self.rows = []
        self.reconciliation_errors = []
        cur = start_row

        # ------------------------------------------------------- ASSETS
        cur = self._row(cur, "ASSETS", None, style="section_header")
        cur = self._row(cur, "NON-CURRENT ASSETS", None, style="sub_header")

        nca_start = cur
        ppe_val = self._sum("sofp.nca.ppe", "sofp.nca.accdep")
        cur = self._row(cur, "Property, plant and equipment", ppe_val,
                        note=4 if self.notes_compiler.get_note_cell_ref(4) else None,
                        formula=(self._note_linked(4, "Property, plant and equipment", ppe_val)
                                 or self._live("sofp.nca.ppe", "sofp.nca.accdep")))

        dep_val = self._sum("sofp.nca.ltdeposits")
        cur = self._row(cur, "Long-term deposits and prepayments", dep_val,
                        note=5 if self.notes_compiler.get_note_cell_ref(5) else None,
                        formula=(self._note_linked(5, "Long-term deposits and prepayments", dep_val)
                                 or self._live("sofp.nca.ltdeposits")))

        intangible_val = self._sum("sofp.nca.intangible")
        if intangible_val != 0:
            cur = self._row(cur, "Intangible assets", intangible_val,
                            formula=self._live("sofp.nca.intangible"))
        ltinv_val = self._sum("sofp.nca.ltinvest")
        if ltinv_val != 0:
            cur = self._row(cur, "Long-term investments", ltinv_val,
                            formula=self._live("sofp.nca.ltinvest"))
        dta_val = self._sum("sofp.nca.dta")
        if dta_val != 0:
            cur = self._row(cur, "Deferred taxation - net asset", dta_val,
                            formula=self._live("sofp.nca.dta"))

        nca_end = cur - 1
        nca_total_row = cur
        self.total_non_current_assets = round(
            ppe_val + dep_val + intangible_val + ltinv_val + dta_val, 2)
        cur = self._row(cur, "Total Non-Current Assets", self.total_non_current_assets,
                        formula=f"=SUM(C{nca_start}:C{nca_end})", style="subtotal")

        cur = self._row(cur, "CURRENT ASSETS", None, style="sub_header")

        ca_start = cur
        stores_val = self._sum("sofp.ca.stores")
        if stores_val != 0:
            cur = self._row(cur, "Stores, spares and loose tools", stores_val,
                            formula=self._live("sofp.ca.stores"))

        stock_val = self._sum("sofp.ca.stock")
        cur = self._row(cur, "Stock-in-trade", stock_val,
                        note=6 if self.notes_compiler.get_note_cell_ref(6) else None,
                        formula=(self._note_linked(6, "Stock-in-trade", stock_val)
                                 or self._live("sofp.ca.stock")))

        debtors_val = self._sum("sofp.ca.debtors", "sofp.ca.allowance_ecl")
        cur = self._row(cur, "Trade debts", debtors_val,
                        note=7 if self.notes_compiler.get_note_cell_ref(7) else None,
                        formula=(self._note_linked(7, "Trade debts", debtors_val)
                                 or self._live("sofp.ca.debtors", "sofp.ca.allowance_ecl")))

        adv_val = self._sum("sofp.ca.advances")
        cur = self._row(cur, "Advances, deposits, prepayments and other receivables", adv_val,
                        formula=self._live("sofp.ca.advances"))

        stinv_val = self._sum("sofp.ca.stinvest")
        if stinv_val != 0:
            cur = self._row(cur, "Short-term investments", stinv_val,
                            formula=self._live("sofp.ca.stinvest"))
        taxrefund_val = self._sum("sofp.ca.taxrefund")
        if taxrefund_val != 0:
            cur = self._row(cur, "Tax refunds due from Government", taxrefund_val,
                            formula=self._live("sofp.ca.taxrefund"))

        cash_val = self._sum("sofp.ca.cash")
        cur = self._row(cur, "Cash and bank balances", cash_val,
                        note=8 if self.notes_compiler.get_note_cell_ref(8) else None,
                        formula=(self._note_linked(8, "Cash and bank balances", cash_val)
                                 or self._live("sofp.ca.cash")))

        suspense_dr = self._sum("sofp.ca.suspense")
        if suspense_dr != 0:
            cur = self._row(cur, "Suspense account - unclassified debit balances", suspense_dr,
                            formula=self._live("sofp.ca.suspense"))

        ca_end = cur - 1
        ca_total_row = cur
        self.total_current_assets = round(
            stores_val + stock_val + debtors_val + adv_val + stinv_val
            + taxrefund_val + cash_val + suspense_dr, 2)
        cur = self._row(cur, "Total Current Assets", self.total_current_assets,
                        formula=f"=SUM(C{ca_start}:C{ca_end})", style="subtotal")

        total_assets_row = cur
        self.total_assets = round(self.total_non_current_assets + self.total_current_assets, 2)
        cur = self._row(cur, "TOTAL ASSETS", self.total_assets,
                        formula=f"=C{nca_total_row}+C{ca_total_row}", style="grand_total")
        cur += 1

        # ------------------------------------------ EQUITY AND LIABILITIES
        cur = self._row(cur, "EQUITY AND LIABILITIES", None, style="section_header")
        cur = self._row(cur, "SHARE CAPITAL AND RESERVES", None, style="sub_header")

        eq_start = cur
        cap_val = self._sum("sofp.eq.sharecapital", "sofp.eq.capitalaccount", "sofp.eq.drawings")
        cur = self._row(cur, "Share capital / Capital account", cap_val,
                        note=9 if self.notes_compiler.get_note_cell_ref(9) else None,
                        formula=(self._note_linked(9, "Share capital / Capital account", cap_val)
                                 or self._live("sofp.eq.sharecapital", "sofp.eq.capitalaccount", "sofp.eq.drawings")))

        reserves_val = self._sum("sofp.eq.reserves")
        if reserves_val != 0:
            cur = self._row(cur, "Reserves and surplus", reserves_val,
                            formula=self._live("sofp.eq.reserves"))

        # Opening unappropriated profit, plus any dividend declared out of it.
        opening_re = self._sum("sofp.eq.retained", "sofp.eq.cy_profit_summary",
                               "sofp.eq.dividend")
        if net_profit_ref:
            re_formula = (f"={opening_re}+{net_profit_ref}" if opening_re != 0
                          else f"={net_profit_ref}")
        elif opening_re != 0:
            re_formula = f"={opening_re}"
        else:
            re_formula = None
        closing_re = round(opening_re + net_profit, 2)
        cur = self._row(cur, "Unappropriated profit / (accumulated loss)", closing_re,
                        formula=re_formula)

        eq_end = cur - 1
        eq_total_row = cur
        self.total_equity = round(cap_val + reserves_val + closing_re, 2)
        cur = self._row(cur, "Total Equity", self.total_equity,
                        formula=f"=SUM(C{eq_start}:C{eq_end})", style="subtotal")

        cur = self._row(cur, "NON-CURRENT LIABILITIES", None, style="sub_header")

        ncl_start = cur
        lt_borrow = self._sum("sofp.ncl.ltborrow")
        lease_ncl = self._sum("sofp.ncl.lease")
        deftax_val = self._sum("sofp.ncl.deftax")
        ltprov_val = self._sum("sofp.ncl.ltprov")
        director_loan = self._sum("sofp.ncl.directorloan")

        ncl_lines = [
            ("Long-term financing and borrowings", lt_borrow, "sofp.ncl.ltborrow"),
            ("Lease liabilities - non-current portion", lease_ncl, "sofp.ncl.lease"),
            ("Deferred taxation", deftax_val, "sofp.ncl.deftax"),
            ("Employee benefit obligations", ltprov_val, "sofp.ncl.ltprov"),
            ("Loan from directors / related parties", director_loan, "sofp.ncl.directorloan"),
        ]
        if not any(v != 0 for _, v, _id in ncl_lines):
            cur = self._row(cur, "Long-term borrowings", 0.0, formula="=0")
        else:
            for label, value, lid in ncl_lines:
                if value != 0:
                    cur = self._row(cur, label, value, formula=self._live(lid))

        ncl_end = cur - 1
        ncl_total_row = cur
        self.total_non_current_liabilities = round(
            lt_borrow + lease_ncl + deftax_val + ltprov_val + director_loan, 2)
        cur = self._row(cur, "Total Non-Current Liabilities", self.total_non_current_liabilities,
                        formula=f"=SUM(C{ncl_start}:C{ncl_end})", style="subtotal")

        cur = self._row(cur, "CURRENT LIABILITIES", None, style="sub_header")

        cl_start = cur
        payables_val = self._sum("sofp.cl.payables", "sofp.cl.accrued")
        cur = self._row(cur, "Trade and other payables", payables_val,
                        note=10 if self.notes_compiler.get_note_cell_ref(10) else None,
                        formula=(self._note_linked(10, "Trade and other payables", payables_val)
                                 or self._live("sofp.cl.payables", "sofp.cl.accrued")))

        st_borrow = self._sum("sofp.cl.stborrow")
        lease_cl = self._sum("sofp.cl.lease")
        cp_ncl = self._sum("sofp.cl.currentportion")
        tax_liab = self._sum("sofp.cl.provtax")
        unclaimed_div = self._sum("sofp.cl.unclaimeddiv")
        suspense_cr = self._sum("sofp.cl.suspense")

        for label, value, lid in [
            ("Short-term borrowings", st_borrow, "sofp.cl.stborrow"),
            ("Current portion of lease liabilities", lease_cl, "sofp.cl.lease"),
            ("Current portion of long-term liabilities", cp_ncl, "sofp.cl.currentportion"),
            ("Provision for taxation", tax_liab, "sofp.cl.provtax"),
            ("Dividend payable", unclaimed_div, "sofp.cl.unclaimeddiv"),
            ("Suspense account - unclassified credit balances", suspense_cr, "sofp.cl.suspense"),
        ]:
            if value != 0:
                cur = self._row(cur, label, value, formula=self._live(lid))

        cl_end = cur - 1
        cl_total_row = cur
        self.total_current_liabilities = round(
            payables_val + st_borrow + lease_cl + cp_ncl + tax_liab
            + unclaimed_div + suspense_cr, 2)
        cur = self._row(cur, "Total Current Liabilities", self.total_current_liabilities,
                        formula=f"=SUM(C{cl_start}:C{cl_end})", style="subtotal")

        total_eq_liab_row = cur
        self.total_equity_and_liabilities = round(
            self.total_equity + self.total_non_current_liabilities
            + self.total_current_liabilities, 2)
        cur = self._row(cur, "TOTAL EQUITY AND LIABILITIES", self.total_equity_and_liabilities,
                        formula=f"=C{eq_total_row}+C{ncl_total_row}+C{cl_total_row}",
                        style="grand_total")
        cur += 1

        self._row(cur, "BALANCE SHEET INTEGRITY CHECK (Assets - Liabilities & Equity)",
                  round(self.total_assets - self.total_equity_and_liabilities, 2),
                  formula=f"=C{total_assets_row}-C{total_eq_liab_row}", style="check")

        return self.rows
