"""Command-line interface for FYP-Module-3."""

import argparse
import sys
from typing import Optional

from tabulate import tabulate

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fyp_module3.core.pipeline import PipelineOptions, run_compilation, CompilationOutcome
from fyp_module3.core.validator import UnprocessableDataError

# Re-exported so existing callers can keep importing it from the CLI module.
__all__ = ["run_pipeline", "main", "CompilationFailed", "UnprocessableDataError"]


class CompilationFailed(RuntimeError):
    """Raised by `run_pipeline` when the compiled statements do not verify."""

    def __init__(self, outcome: CompilationOutcome):
        self.outcome = outcome
        super().__init__(outcome.result.message)


def _print_header(entity: str, period: str, sheet: Optional[str]) -> None:
    print("\n========================================================")
    print(" FYP-Module-3: Autonomous Statutory Statement Compiler")
    print(f" Entity: {entity} | Period: {period}")
    if sheet:
        print(f" Sheet: {sheet}")
    print("========================================================")


def _report(outcome: CompilationOutcome) -> None:
    """Print the full diagnostic report for a finished run."""
    result = outcome.result
    health = result.health_report

    print(f"\n[Health] Score {health.health_score:.0f}/100 ({health.severity})")
    print(f"         {health.headline}")
    for issue in health.issues:
        print(f"    [{issue.severity}] {issue.description}")
        print(f"         -> {issue.remediation_hint}")

    if outcome.audit_trail:
        print(f"\n[Balancer] {len(outcome.audit_trail)} heuristic adjustment(s) applied:")
        print(tabulate(
            [[e.heuristic, e.account_name, e.action, f"{e.delta:,.2f}"]
             for e in outcome.audit_trail],
            headers=["Heuristic", "Account", "Action", "Delta (PKR)"], tablefmt="presto"))
    elif outcome.accounts:
        print("\n[Balancer] Trial balance was already in parity; no adjustments required.")

    verification = result.verification_report
    if verification:
        print("\n[Verification] In-memory statement integrity:")
        print(tabulate([
            ["Trial Balance Parity (Dr = Cr)", f"PKR {verification.tb_delta:,.2f} variance",
             "PASSED" if verification.is_tb_balanced else "FAILED"],
            ["Total Assets", f"PKR {verification.total_assets:,.2f}", ""],
            ["Total Equity & Liabilities", f"PKR {verification.total_liabilities_and_equity:,.2f}", ""],
            ["  - Total Equity", f"PKR {verification.total_equity:,.2f}", ""],
            ["  - Non-Current Liabilities", f"PKR {verification.total_non_current_liabilities:,.2f}", ""],
            ["  - Current Liabilities", f"PKR {verification.total_current_liabilities:,.2f}", ""],
            ["Net Profit / (Loss)", f"PKR {verification.net_profit:,.2f}", ""],
            ["Balance Sheet Identity (A = L + E)", f"Variance PKR {verification.bs_delta:,.2f}",
             "PASSED" if verification.is_bs_balanced else "FAILED"],
            ["Zero Leakage (every account rendered)",
             f"{len(verification.unassigned_accounts) + len(verification.unrendered_accounts)} missing",
             "PASSED" if verification.zero_leakage_passed else "FAILED"],
            ["Note Cross-Referencing",
             f"{len(verification.note_mismatches)} mismatch(es)",
             "PASSED" if verification.notes_reconciled else "FAILED"],
        ], headers=["Audit Check / Theorem", "Computed Value", "Result"], tablefmt="presto"))

        for name in verification.unassigned_accounts + verification.unrendered_accounts:
            print(f"    [LEAKAGE] {name}")
        for mismatch in verification.note_mismatches:
            print(f"    [NOTE] {mismatch}")
        for correction in verification.auto_corrections:
            print(f"    [SELF-CORRECTION] {correction}")

    audit = result.workbook_audit
    if audit:
        # This is the check that matters: it evaluates the formulas in the file
        # the user actually receives, not the numbers held in memory.
        print("\n[Workbook Audit] Evaluating the exported file's own formulas:")
        for check in audit.checks:
            print(f"    [OK]   {check}")
        for failure in audit.failures:
            print(f"    [FAIL] {failure}")

    print("\n========================================================")
    print(f" {result.status}: {result.message}")
    if result.output_file:
        print(f" Output: {result.output_file}")
    print("========================================================\n")


def run_pipeline(
    input_file: str,
    output_file: Optional[str] = None,
    entity_name: Optional[str] = None,
    period: str = "June 30, 2025",
    sheet_name: Optional[str] = None,
    allow_working_capital_plug: bool = False,
    enforce_health_gate: bool = True,
    quiet: bool = False,
) -> str:
    """Execute the compiler pipeline and return the path of the compiled workbook.

    Raises `CompilationFailed` when the statements do not verify, so that a
    caller cannot mistake a broken workbook for a finished one.
    """
    options = PipelineOptions(
        output_file=output_file,
        entity_name=entity_name,
        period=period,
        sheet_name=sheet_name,
        allow_working_capital_plug=allow_working_capital_plug,
        enforce_health_gate=enforce_health_gate,
    )

    def progress(step: int, total: int, message: str) -> None:
        if not quiet:
            print(f"\n[Step {step}/{total}] {message}...")

    if not quiet:
        _print_header(entity_name or input_file, period, sheet_name)

    outcome = run_compilation(input_file, options, on_progress=progress)
    if not quiet:
        _report(outcome)

    if outcome.result.status == "FAILED_CRITICAL":
        raise CompilationFailed(outcome)
    return outcome.result.output_file or ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FYP-Module-3: Autonomous Statutory Statement & Dynamic Notes Compiler")
    parser.add_argument("--input", "-i", required=True,
                        help="Path to raw Trial Balance Excel workbook (.xlsx)")
    parser.add_argument("--output", "-o", help="Path to output compiled workbook (.xlsx)")
    parser.add_argument("--entity", "-e", help="Entity / Company Name")
    parser.add_argument("--sheet", "-s", help="Specific worksheet name to parse")
    parser.add_argument("--period", "-p", default="June 30, 2025",
                        help="Reporting period ended (e.g. 'June 30, 2025')")
    parser.add_argument(
        "--no-health-gate", action="store_true",
        help="Compile even when the pre-flight health check reports critical defects. "
             "Useful for inspecting what a problematic file produces; the output is "
             "still audited and marked unverified if it does not tie out.")
    parser.add_argument(
        "--allow-working-capital-plug", action="store_true",
        help="Permit an unexplained residual variance to be posted to trade debtors or "
             "creditors in order to force the balance sheet to balance. The resulting "
             "statements are NOT supported by the ledger and are flagged as such.")

    args = parser.parse_args()
    try:
        run_pipeline(
            args.input, args.output, args.entity, args.period,
            sheet_name=args.sheet,
            allow_working_capital_plug=args.allow_working_capital_plug,
            enforce_health_gate=not args.no_health_gate,
        )
    except CompilationFailed:
        # The full diagnostic report has already been printed.
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] Pipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
