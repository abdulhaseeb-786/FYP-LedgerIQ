"""ISA 520 Analytical Procedures: Statutory Financial Ratios & Comparative Variance Engine."""

from typing import Dict, Any, Optional, List
from app.modules.audit_analytics.domain.models import RatioValue, ISARatiosReport

DEFAULT_VARIANCE_ALERT_THRESHOLD = 15.0  # Percentage YoY variance triggering ISA 520 audit alert


class FinancialRatioAnalyzer:
    """Computes statutory financial ratios and flags anomalous period-over-period movements."""

    def __init__(self, variance_threshold_pct: float = DEFAULT_VARIANCE_ALERT_THRESHOLD):
        self.variance_threshold_pct = variance_threshold_pct

    def compute_ratios(
        self,
        current_data: Dict[str, float],
        prior_data: Optional[Dict[str, float]] = None,
        period_current: str = "Current Year",
        period_prior: Optional[str] = None,
    ) -> ISARatiosReport:
        """
        Evaluate full statutory ratio matrix from extracted accounting balances.

        Expected keys in current_data / prior_data:
            - current_assets, current_liabilities, cash, inventory, trade_debtors
            - total_assets, total_liabilities, total_equity
            - revenue, gross_profit, operating_profit, net_profit, finance_costs
        """
        definitions = [
            # 1. Liquidity Ratios
            {
                "code": "CR",
                "name": "Current Ratio",
                "category": "Liquidity",
                "formula_desc": "Current Assets / Current Liabilities",
                "min": 1.10, "max": 3.00,
                "calc": lambda d: self._safe_div(d.get("current_assets", 0.0), d.get("current_liabilities", 0.0)),
            },
            {
                "code": "QR",
                "name": "Quick Ratio (Acid-Test)",
                "category": "Liquidity",
                "formula_desc": "(Current Assets - Inventory) / Current Liabilities",
                "min": 0.80, "max": 2.00,
                "calc": lambda d: self._safe_div(d.get("current_assets", 0.0) - d.get("inventory", 0.0), d.get("current_liabilities", 0.0)),
            },
            {
                "code": "CASH_R",
                "name": "Cash Ratio",
                "category": "Liquidity",
                "formula_desc": "Cash & Cash Equivalents / Current Liabilities",
                "min": 0.20, "max": 1.00,
                "calc": lambda d: self._safe_div(d.get("cash", 0.0), d.get("current_liabilities", 0.0)),
            },
            # 2. Solvency Ratios
            {
                "code": "DE",
                "name": "Debt-to-Equity Ratio",
                "category": "Solvency",
                "formula_desc": "Total Liabilities / Total Equity",
                "min": 0.00, "max": 2.50,
                "calc": lambda d: self._calc_de(d),
            },
            {
                "code": "EQ_RATIO",
                "name": "Equity Ratio",
                "category": "Solvency",
                "formula_desc": "Total Equity / Total Assets",
                "min": 0.25, "max": 0.85,
                "calc": lambda d: self._safe_div(d.get("total_equity", 0.0), d.get("total_assets", 0.0)),
            },
            {
                "code": "IC",
                "name": "Interest Coverage Ratio",
                "category": "Solvency",
                "formula_desc": "EBIT (Operating Profit) / Finance Costs",
                "min": 2.00, "max": None,
                "calc": lambda d: self._safe_div(d.get("operating_profit", 0.0), d.get("finance_costs", 0.0)),
            },
            # 3. Profitability Ratios
            {
                "code": "GPM",
                "name": "Gross Profit Margin (%)",
                "category": "Profitability",
                "formula_desc": "(Gross Profit / Revenue) * 100",
                "min": 10.0, "max": None,
                "calc": lambda d: self._calc_pct(d.get("gross_profit", 0.0), d.get("revenue", 0.0)),
            },
            {
                "code": "OPM",
                "name": "Operating Profit Margin (%)",
                "category": "Profitability",
                "formula_desc": "(Operating Profit / Revenue) * 100",
                "min": 5.0, "max": None,
                "calc": lambda d: self._calc_pct(d.get("operating_profit", 0.0), d.get("revenue", 0.0)),
            },
            {
                "code": "NPM",
                "name": "Net Profit Margin (%)",
                "category": "Profitability",
                "formula_desc": "(Net Profit / Revenue) * 100",
                "min": 2.0, "max": None,
                "calc": lambda d: self._calc_pct(d.get("net_profit", 0.0), d.get("revenue", 0.0)),
            },
            {
                "code": "ROE",
                "name": "Return on Equity (%)",
                "category": "Profitability",
                "formula_desc": "(Net Profit / Total Equity) * 100",
                "min": 5.0, "max": None,
                "calc": lambda d: self._calc_pct(d.get("net_profit", 0.0), d.get("total_equity", 0.0)),
            },
            # 4. Activity Ratios
            {
                "code": "ART",
                "name": "Receivables Turnover",
                "category": "Activity",
                "formula_desc": "Revenue / Trade Debtors",
                "min": 4.0, "max": None,
                "calc": lambda d: self._safe_div(d.get("revenue", 0.0), d.get("trade_debtors", 0.0)),
            },
            {
                "code": "DSO",
                "name": "Days Sales Outstanding (Days)",
                "category": "Activity",
                "formula_desc": "365 / Receivables Turnover",
                "min": None, "max": 90.0,
                "calc": lambda d: self._calc_dso(d),
            },
        ]

        evaluated_ratios: List[RatioValue] = []
        alerts_count = 0

        for item in definitions:
            curr_val = item["calc"](current_data)
            prior_val = item["calc"](prior_data) if prior_data else None

            delta_pct = None
            is_alert = False
            reasons = []

            # Benchmark check on current value
            if curr_val is not None:
                b_min = item["min"]
                b_max = item["max"]
                if b_min is not None and curr_val < b_min:
                    is_alert = True
                    reasons.append(f"Current value ({curr_val:.2f}) falls below benchmark min ({b_min:.2f})")
                if b_max is not None and curr_val > b_max:
                    is_alert = True
                    reasons.append(f"Current value ({curr_val:.2f}) exceeds benchmark max ({b_max:.2f})")

            # Comparative YoY Variance Check (ISA 520)
            if curr_val is not None and prior_val is not None and abs(prior_val) > 0.0001:
                delta_pct = ((curr_val - prior_val) / abs(prior_val)) * 100.0
                if abs(delta_pct) >= self.variance_threshold_pct:
                    is_alert = True
                    direction = "surge" if delta_pct > 0 else "drop"
                    reasons.append(
                        f"Significant YoY {direction} of {abs(delta_pct):.1f}% exceeds audit tolerance (+/-{self.variance_threshold_pct:.0f}%)"
                    )

            if is_alert:
                alerts_count += 1

            evaluated_ratios.append(
                RatioValue(
                    code=item["code"],
                    name=item["name"],
                    category=item["category"],
                    formula_desc=item["formula_desc"],
                    current_value=round(curr_val, 3) if curr_val is not None else None,
                    prior_value=round(prior_val, 3) if prior_val is not None else None,
                    delta_percentage=round(delta_pct, 2) if delta_pct is not None else None,
                    benchmark_min=item["min"],
                    benchmark_max=item["max"],
                    is_alert=is_alert,
                    alert_message="; ".join(reasons) if reasons else None,
                )
            )

        if alerts_count == 0:
            summary = "All financial ratios operate within expected benchmark corridors with stable period-over-period trends."
        elif alerts_count <= 3:
            summary = f"Detected {alerts_count} ratio variance alerts requiring standard auditor analytical inquiries."
        else:
            summary = f"Detected {alerts_count} significant ratio abnormalities. High risk of operational instability or balance sheet distortion."

        return ISARatiosReport(
            period_current=period_current,
            period_prior=period_prior,
            ratios=evaluated_ratios,
            total_alerts=alerts_count,
            summary_verdict=summary,
        )

    @staticmethod
    def _safe_div(num: float, den: float) -> Optional[float]:
        if abs(den) < 0.0001:
            return None
        return num / den

    @staticmethod
    def _calc_pct(num: float, den: float) -> Optional[float]:
        if abs(den) < 0.0001:
            return None
        return (num / den) * 100.0

    @staticmethod
    def _calc_de(d: Dict[str, float]) -> Optional[float]:
        eq = d.get("total_equity", 0.0)
        liab = d.get("total_liabilities", 0.0)
        if eq <= 0.0001:
            return None  # Negative or zero equity
        return liab / eq

    @staticmethod
    def _calc_dso(d: Dict[str, float]) -> Optional[float]:
        rev = d.get("revenue", 0.0)
        debtors = d.get("trade_debtors", 0.0)
        if rev <= 0.0001 or debtors <= 0.0001:
            return None
        turnover = rev / debtors
        return 365.0 / turnover
