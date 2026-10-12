"""Pre-flight Data Health & Quality Guard for FYP-Module-3.

Validates raw input sheets and standardized accounts before statement
compilation. Detects severe rubbish, non-accounting junk, extreme imbalances,
and single-sided extracts, flagging the user with explicit, actionable auditor
diagnostics when data cannot be processed.
"""

import re
from typing import List

from fyp_module3.core.models import (
    StandardizedAccountRecord, DataHealthReport, DataQualityIssue
)

MIN_LEDGER_ACCOUNTS = 4


class UnprocessableDataError(ValueError):
    """Raised when incoming data contains severe defects making compilation impossible."""

    def __init__(self, report: DataHealthReport):
        self.report = report
        critical = [f"- {i.description}" for i in report.issues if i.severity == "CRITICAL"]
        if not critical:
            critical = [f"- Overall data health score of {report.health_score:.0f}/100 "
                        "is below the minimum required to compile statements."]
        super().__init__(
            f"CRITICAL: This data cannot be compiled (Health Score: {report.health_score:.0f}/100).\n"
            f"{report.headline}\n"
            "Specific issues identified:\n" + "\n".join(critical)
        )


class DataHealthValidator:
    """Evaluates raw spreadsheet rows and parsed accounts against auditing standards."""

    def evaluate_health(
        self,
        accounts: List[StandardizedAccountRecord],
        total_raw_rows: int = 0,
        raw_error_count: int = 0,
        junk_rows_count: int = 0
    ) -> DataHealthReport:
        """Run comprehensive pre-flight sanity checks on parsed accounts."""
        issues: List[DataQualityIssue] = []
        score = 100.0

        # 1. Corrupt spreadsheet formulas (#REF!, #VALUE!, unreadable amounts).
        if raw_error_count > 0:
            score -= min(30.0, raw_error_count * 10.0)
            issues.append(DataQualityIssue(
                severity="CRITICAL" if raw_error_count >= 3 else "WARNING",
                category="Corruption",
                description=f"Detected {raw_error_count} corrupted or unreadable cell(s) "
                            "(e.g. #REF!, #VALUE!, #N/A, or an amount that is not a number).",
                remediation_hint="Resolve broken formulas and non-numeric amounts before re-uploading.",
            ))

        # 2. Junk / narrative row ratio, measured by the parser rather than guessed.
        if total_raw_rows > 0 and junk_rows_count > 0:
            junk_ratio = junk_rows_count / total_raw_rows
            if junk_ratio > 0.60:
                score -= 40.0
                issues.append(DataQualityIssue(
                    severity="CRITICAL",
                    category="Structure",
                    description=f"High noise ratio: {junk_rows_count} of {total_raw_rows} rows "
                                f"({junk_ratio * 100:.0f}%) were narrative notes, headers, blank "
                                "or nil-balance lines rather than ledger entries.",
                    remediation_hint="Ensure the uploaded file contains a clean ledger trial balance table.",
                ))
            elif junk_ratio > 0.30:
                score -= 10.0
                issues.append(DataQualityIssue(
                    severity="WARNING",
                    category="Structure",
                    description=f"{junk_rows_count} of {total_raw_rows} rows were filtered out "
                                "during parsing as non-accounting lines.",
                    remediation_hint="Clean up unnecessary text comments or non-accounting blocks.",
                ))

        # 3. Minimum ledger account count.
        if len(accounts) == 0:
            issues.append(DataQualityIssue(
                severity="CRITICAL",
                category="Structure",
                description="Zero valid financial ledger accounts were found in the uploaded file.",
                remediation_hint="Ensure the worksheet contains account descriptions with "
                                 "associated debit and credit amounts.",
            ))
            return self._build_report(0.0, issues, accounts, total_raw_rows, junk_rows_count)

        if len(accounts) < MIN_LEDGER_ACCOUNTS:
            score -= 45.0
            issues.append(DataQualityIssue(
                severity="CRITICAL",
                category="Structure",
                description=f"Insufficient ledger accounts found ({len(accounts)} account(s)). "
                            "A statutory balance sheet and profit & loss statement require at "
                            f"least {MIN_LEDGER_ACCOUNTS} fundamental heads of accounts "
                            "(Assets, Liabilities, Equity, Income/Expense).",
                remediation_hint="Provide a complete trial balance rather than a partial extract.",
            ))

        # 4. All-zero balances.
        initial_dr = sum(a.debit for a in accounts)
        initial_cr = sum(a.credit for a in accounts)
        volume = max(initial_dr, initial_cr)

        if volume < 1e-4:
            issues.append(DataQualityIssue(
                severity="CRITICAL",
                category="Arithmetic",
                description="All parsed debit and credit balances are zero. "
                            "The file contains no monetary values.",
                remediation_hint="Verify that the source file contains numerical balances.",
            ))
            return self._build_report(0.0, issues, accounts, total_raw_rows, junk_rows_count)

        # 5. Single-sided extract or extreme imbalance.
        delta = round(abs(initial_dr - initial_cr), 2)
        imbalance_pct = (delta / volume * 100.0) if volume > 0 else 0.0

        if initial_dr < 1e-6 or initial_cr < 1e-6:
            score -= 50.0
            side = "Credit" if initial_dr < 1e-6 else "Debit"
            issues.append(DataQualityIssue(
                severity="CRITICAL",
                category="Double-Entry Parity",
                description=f"Single-sided transaction extract detected: the file has "
                            f"PKR {volume:,.2f} in {side}s but nothing on the opposite side. "
                            "Double-entry bookkeeping requires both debits and credits.",
                remediation_hint="Provide both debit and credit columns, or ensure offsetting "
                                 "double-entry balancing accounts exist.",
            ))
        elif imbalance_pct > 5.0 and delta > 500_000.0:
            score -= 40.0
            issues.append(DataQualityIssue(
                severity="CRITICAL",
                category="Double-Entry Parity",
                description=f"Severe ledger imbalance: debits differ from credits by "
                            f"PKR {delta:,.2f} ({imbalance_pct:.1f}% of total volume). This "
                            "exceeds the maximum allowable auditor materiality threshold.",
                remediation_hint="Investigate and reconcile the missing counter-entries.",
            ))
        elif delta > 0.01:
            score -= min(15.0, imbalance_pct * 2.0)
            issues.append(DataQualityIssue(
                severity="WARNING",
                category="Double-Entry Parity",
                description=f"Trial balance has an initial imbalance of PKR {delta:,.2f} "
                            f"({imbalance_pct:.2f}%). The Intelligent Parity Balancer will "
                            "attempt heuristic reconciliation.",
                remediation_hint="Review the balancing heuristics in the audit trail tab.",
            ))

        # 6. Accounts the classifier could not map. These sit in suspense rather
        #    than quietly landing in administrative expenses, so they must be
        #    surfaced: an unreviewed suspense balance is an unfinished statement.
        unmapped = [a for a in accounts if a.classification_source == "default"]
        unmapped_ratio = len(unmapped) / len(accounts)
        if unmapped:
            sample = ", ".join(f"'{a.account_name}'" for a in unmapped[:3])
            # Never CRITICAL: suspense is rendered on the balance sheet and the
            # accounting identity still holds, so the statements are sound but
            # incomplete - a review task, not a reason to refuse the file.
            if unmapped_ratio > 0.50:
                score -= 35.0
                severity = "WARNING"
            elif unmapped_ratio > 0.20:
                score -= 15.0
                severity = "WARNING"
            else:
                score -= 5.0
                severity = "WARNING"
            issues.append(DataQualityIssue(
                severity=severity,
                category="Taxonomy",
                description=f"{len(unmapped)} of {len(accounts)} accounts "
                            f"({unmapped_ratio * 100:.0f}%) could not be mapped to a Fifth "
                            f"Schedule line item and were routed to suspense (e.g. {sample}).",
                remediation_hint="Rename these accounts to standard accounting titles, or "
                                 "re-assign them in the Account Overrides section.",
            ))

        # 7. Gibberish account names.
        gibberish = [a for a in accounts
                     if re.match(r"^[\d\W_]+$", a.account_name.strip())
                     or len(a.account_name.strip()) <= 1]
        if gibberish:
            is_critical = (len(gibberish) / len(accounts)) > 0.30
            score -= 25.0 if is_critical else 10.0
            issues.append(DataQualityIssue(
                severity="CRITICAL" if is_critical else "WARNING",
                category="Data Integrity",
                description=f"Found {len(gibberish)} ledger line(s) with invalid, numeric-only, "
                            "or symbol-only descriptions.",
                remediation_hint="Ensure all ledger accounts have meaningful descriptive names.",
            ))

        return self._build_report(max(0.0, min(100.0, score)), issues, accounts,
                                  total_raw_rows, junk_rows_count)

    # -----------------------------------------------------------------
    def _build_report(
        self,
        score: float,
        issues: List[DataQualityIssue],
        accounts: List[StandardizedAccountRecord],
        total_raw_rows: int,
        junk_rows_count: int
    ) -> DataHealthReport:
        has_critical = any(i.severity == "CRITICAL" for i in issues)
        initial_dr = sum(a.debit for a in accounts)
        initial_cr = sum(a.credit for a in accounts)
        delta = round(abs(initial_dr - initial_cr), 2)
        volume = max(initial_dr, initial_cr)
        imbalance_pct = (delta / volume * 100.0) if volume > 0 else 0.0
        avg_conf = (sum(a.confidence for a in accounts) / len(accounts)) if accounts else 0.0

        # Processability is decided by whether a blocking defect was found, not
        # by the advisory score: a file can accumulate many warnings and still
        # produce arithmetically sound statements.
        if has_critical:
            severity = "CRITICAL_UNPROCESSABLE"
            is_processable = False
            headline = "Critical data quality issues detected: this file cannot be compiled."
        elif score < 85.0:
            severity = "WARNING_RECOVERABLE"
            is_processable = True
            headline = "Data contains recoverable variances or noise; review the warnings below."
        else:
            severity = "CLEAN"
            is_processable = True
            headline = "Data structure valid and ready for statutory statement compilation."

        return DataHealthReport(
            is_processable=is_processable,
            health_score=round(score, 1),
            severity=severity,
            headline=headline,
            issues=issues,
            total_raw_rows=total_raw_rows,
            valid_accounts_count=len(accounts),
            junk_rows_skipped=junk_rows_count,
            average_classifier_confidence=round(avg_conf, 3),
            initial_dr=initial_dr,
            initial_cr=initial_cr,
            initial_delta=delta,
            imbalance_percentage=round(imbalance_pct, 2)
        )
