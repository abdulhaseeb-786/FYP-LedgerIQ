"""The single compilation pipeline.

The CLI, the desktop bridge and the Streamlit app all call `run_compilation`.
Keeping one orchestration is not tidiness for its own sake: when this logic was
duplicated three times the copies drifted, and the app quietly lost the
pre-flight health gate entirely.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional

from fyp_module3.core.models import (
    StandardizedAccountRecord, UpstreamModulePayload, AuditEntry,
    DataHealthReport, VerificationReport, WorkbookAuditResult, DesktopPipelineResult,
)
from fyp_module3.core.parser import parse_trial_balance
from fyp_module3.core.classifier import AccountClassifier
from fyp_module3.core.validator import DataHealthValidator
from fyp_module3.core.balancer import IntelligentParityBalancer, IrreconcilableTrialBalanceError
from fyp_module3.core.verifier import StatementVerifier
from fyp_module3.core.workbook_audit import audit_workbook
from fyp_module3.statements.notes_compiler import NotesCompiler
from fyp_module3.statements.profit_loss import ProfitLossStatement
from fyp_module3.statements.balance_sheet import BalanceSheetStatement
from fyp_module3.exporter.excel_writer import ExcelWorkbookCompiler

ProgressFn = Callable[[int, int, str], None]


@dataclass
class PipelineOptions:
    """Everything the pipeline can be asked to vary."""
    output_file: Optional[str] = None
    entity_name: Optional[str] = None
    period: str = "June 30, 2025"
    sheet_name: Optional[str] = None
    enforce_health_gate: bool = True
    # Off by default: an unexplained residual is reported, not capitalised.
    allow_working_capital_plug: bool = False
    # Accounts the user has re-mapped by hand, keyed by account name.
    overrides: dict = field(default_factory=dict)
    # Optional General Ledger file path or pre-computed audit report for Module 8 integration
    gl_file_path: Optional[str] = None
    audit_risk_report: Optional[Any] = None


@dataclass
class CompilationOutcome:
    """The API response plus the artefacts a UI needs to render previews."""
    result: DesktopPipelineResult
    payload: Optional[UpstreamModulePayload] = None
    accounts: List[StandardizedAccountRecord] = field(default_factory=list)
    audit_trail: List[AuditEntry] = field(default_factory=list)
    exporter: Optional[ExcelWorkbookCompiler] = None
    audit_risk_report: Optional[Any] = None


TOTAL_STEPS = 7


def _failed(message: str, health: Optional[DataHealthReport] = None,
            **kwargs) -> DesktopPipelineResult:
    return DesktopPipelineResult(
        status="FAILED_CRITICAL",
        message=message,
        is_balanced=False,
        health_report=health or DataHealthReport(
            is_processable=False,
            health_score=0.0,
            severity="CRITICAL_UNPROCESSABLE",
            headline=message,
        ),
        **kwargs,
    )


def _unverified_path(output_file: str) -> str:
    """Mark an output that failed verification so it cannot be mistaken for clean."""
    path = Path(output_file)
    if path.stem.endswith("_UNVERIFIED"):
        return str(path)
    return str(path.with_name(f"{path.stem}_UNVERIFIED{path.suffix}"))


def run_compilation(
    input_file: str,
    options: Optional[PipelineOptions] = None,
    on_progress: Optional[ProgressFn] = None,
) -> CompilationOutcome:
    """Execute the end-to-end statutory statements compiler pipeline."""
    opts = options or PipelineOptions()

    def step(n: int, message: str) -> None:
        if on_progress:
            on_progress(n, TOTAL_STEPS, message)

    input_path = Path(input_file)
    if not input_path.exists():
        return CompilationOutcome(result=_failed(f"File not found: {input_file}"))

    output_file = opts.output_file or str(
        input_path.parent / f"{input_path.stem}_Compiled_FS.xlsx")
    entity_name = opts.entity_name or input_path.stem.replace("-", " ").replace("_", " ").title()

    # ---------------------------------------------------------------- 1
    step(1, "Ingesting Trial Balance")
    try:
        payload = parse_trial_balance(str(input_path), sheet_name=opts.sheet_name)
    except Exception as exc:
        return CompilationOutcome(result=_failed(f"Parsing error: {exc}"))

    # ---------------------------------------------------------------- 2
    step(2, "Classifying accounts into Fifth Schedule taxonomy")
    AccountClassifier().classify_all(payload.accounts)
    for acc in payload.accounts:
        if acc.account_name in opts.overrides:
            line_id, note_number = opts.overrides[acc.account_name]
            acc.line_item_id = line_id
            acc.note_number = note_number
            acc.confidence = 1.0
            acc.classification_source = "manual"
            acc.is_adjusted = True
            acc.adjustment_reason = "Manual override by user"

    # ---------------------------------------------------------------- 3
    step(3, "Pre-flight data health and quality guard")
    health_report = DataHealthValidator().evaluate_health(
        accounts=payload.accounts,
        total_raw_rows=payload.total_raw_rows,
        raw_error_count=payload.error_cells_detected,
        junk_rows_count=payload.junk_rows_skipped,
    )
    if opts.enforce_health_gate and not health_report.is_processable:
        reasons = "; ".join(i.description for i in health_report.issues
                            if i.severity == "CRITICAL")
        return CompilationOutcome(
            result=_failed(f"Data Quality Gate Failed: {reasons}", health_report),
            payload=payload,
        )

    # ---------------------------------------------------------------- 4
    step(4, "Running Intelligent Parity Balancer")
    balancer = IntelligentParityBalancer(
        allow_working_capital_plug=opts.allow_working_capital_plug)
    try:
        balanced_accounts, audit_trail = balancer.balance_trial_balance(payload.accounts)
    except IrreconcilableTrialBalanceError as exc:
        return CompilationOutcome(
            result=_failed(str(exc), health_report),
            payload=payload,
        )

    # A balance the balancer moved to the other side was classified before the
    # move, so that mapping no longer describes it. Re-run the classifier over
    # exactly those accounts, leaving manual overrides and the plug alone.
    reclassifier = AccountClassifier()
    for acc in balanced_accounts:
        if acc.side_changed and acc.account_name not in opts.overrides:
            before = acc.line_item_id
            result = reclassifier.classify_account(acc)
            acc.line_item_id = result.line_item_id
            acc.note_number = result.note_number
            acc.confidence = result.confidence
            acc.classification_source = result.source
            if before != acc.line_item_id:
                acc.adjustment_reason = (
                    f"{acc.adjustment_reason}; re-classified to "
                    f"'{acc.line_item_id}' after the correction"
                )

    # ---------------------------------------------------------------- 5
    step(5, "Statement integrity verification and counter-checking")
    notes_compiler = NotesCompiler()
    pl_compiler = ProfitLossStatement(notes_compiler)
    bs_compiler = BalanceSheetStatement(notes_compiler)
    verification_report, verified_accounts = StatementVerifier().run_verification_loop(
        balanced_accounts, notes_compiler, pl_compiler, bs_compiler)

    # ---------------------------------------------------------------- 6
    step(6, "Compiling OpenXML dynamic formula workbook")
    verified_ok = (verification_report.is_bs_balanced
                   and verification_report.zero_leakage_passed
                   and verification_report.notes_reconciled)
    target_file = output_file if verified_ok else _unverified_path(output_file)

    # Optional Module 8 Audit Analytics integration (ISA 520 / ISA 240)
    audit_report = opts.audit_risk_report
    if audit_report is None and opts.gl_file_path:
        try:
            from app.modules.audit_analytics.infrastructure.gl_parser import GeneralLedgerParser
            from app.modules.audit_analytics.domain.pipeline import AuditAnalyticsPipeline
            gl_records = GeneralLedgerParser().parse_file(opts.gl_file_path)
            tb_curr = {
                "total_assets": verification_report.total_assets,
                "total_liabilities": verification_report.total_non_current_liabilities + verification_report.total_current_liabilities,
                "total_equity": verification_report.total_equity,
                "current_assets": verification_report.total_assets,
                "current_liabilities": verification_report.total_current_liabilities,
                "net_profit": verification_report.net_profit,
            }
            audit_report = AuditAnalyticsPipeline().execute_audit(
                transactions=gl_records,
                entity_name=entity_name,
                reporting_period=opts.period,
                current_tb_balances=tb_curr,
            )
        except Exception:
            pass

    exporter = ExcelWorkbookCompiler(entity_name=entity_name, period=opts.period)
    try:
        final_path = exporter.export_workbook(
            verified_accounts,
            audit_trail,
            target_file,
            audit_risk_report=audit_report,
        )
    except Exception as exc:
        return CompilationOutcome(
            result=_failed(f"Workbook generation failed: {exc}", health_report,
                           verification_report=verification_report),
            payload=payload, accounts=verified_accounts, audit_trail=audit_trail,
            audit_risk_report=audit_report,
        )

    # ---------------------------------------------------------------- 7
    step(7, "Auditing the exported workbook's own formulas")
    try:
        workbook_audit = audit_workbook(final_path)
    except Exception as exc:
        workbook_audit = WorkbookAuditResult(
            passed=False, failures=[f"Workbook audit could not run: {exc}"])

    result = _build_result(
        health_report, verification_report, workbook_audit,
        final_path, audit_trail, balancer)
    result.audit_risk_report = audit_report

    # The audit is the authority on whether the delivered file is sound, so a
    # failure there renames the artefact even if the in-memory check passed.
    if not workbook_audit.passed and not final_path.endswith("_UNVERIFIED.xlsx"):
        renamed = _unverified_path(final_path)
        try:
            Path(final_path).replace(renamed)
            result.output_file = renamed
        except OSError:
            pass

    return CompilationOutcome(
        result=result,
        payload=payload,
        accounts=verified_accounts,
        audit_trail=audit_trail,
        exporter=exporter,
        audit_risk_report=audit_report,
    )


def _build_result(
    health_report: DataHealthReport,
    verification: VerificationReport,
    workbook_audit: WorkbookAuditResult,
    output_file: str,
    audit_trail: List[AuditEntry],
    balancer: IntelligentParityBalancer,
) -> DesktopPipelineResult:
    """Decide the headline status from every check that ran."""
    problems: List[str] = []
    if not verification.is_bs_balanced:
        problems.append(
            f"balance sheet is out by PKR {verification.bs_delta:,.2f}")
    if not verification.zero_leakage_passed:
        missing = verification.unassigned_accounts + verification.unrendered_accounts
        problems.append(f"{len(missing)} account(s) reach no statement: {'; '.join(missing[:3])}")
    if not verification.notes_reconciled:
        problems.append("; ".join(verification.note_mismatches[:2]))
    problems.extend(workbook_audit.failures)

    if problems:
        return DesktopPipelineResult(
            status="FAILED_CRITICAL",
            message="Compilation completed but the statements do not verify: "
                    + "; ".join(problems),
            is_balanced=False,
            health_report=health_report,
            verification_report=verification,
            workbook_audit=workbook_audit,
            output_file=output_file,
            audit_trail=audit_trail,
        )

    if balancer.plug_applied:
        return DesktopPipelineResult(
            status="RECOVERED_WARNING",
            message=(
                f"Statements balance only because an unsupported balancing entry of "
                f"PKR {balancer.plug_amount:,.2f} was posted to working capital. "
                "The figures are not fully supported by the ledger and should not be "
                "presented as audited."
            ),
            is_balanced=True,
            health_report=health_report,
            verification_report=verification,
            workbook_audit=workbook_audit,
            output_file=output_file,
            audit_trail=audit_trail,
        )

    verified = ("Compilation completed. The exported workbook's own formulas were "
                "evaluated and every integrity check passed.")

    # If the compiler altered the client's figures, that is reported whatever
    # the health score said: a corrected ledger is not the ledger supplied.
    if audit_trail:
        applied = "; ".join(f"{e.heuristic} on '{e.account_name}'" for e in audit_trail)
        return DesktopPipelineResult(
            status="RECOVERED_WARNING",
            message=f"{verified} Note that the trial balance did not balance as supplied "
                    f"and was corrected before compilation: {applied}. Review the audit "
                    "trail before relying on these statements.",
            is_balanced=True,
            health_report=health_report,
            verification_report=verification,
            workbook_audit=workbook_audit,
            output_file=output_file,
            audit_trail=audit_trail,
        )

    if health_report.severity == "WARNING_RECOVERABLE":
        concerns = "; ".join(i.description for i in health_report.issues
                             if i.severity == "WARNING")
        return DesktopPipelineResult(
            status="RECOVERED_WARNING",
            message=f"{verified} The source data carried recoverable issues: {concerns}",
            is_balanced=True,
            health_report=health_report,
            verification_report=verification,
            workbook_audit=workbook_audit,
            output_file=output_file,
            audit_trail=audit_trail,
        )

    return DesktopPipelineResult(
        status="SUCCESS",
        message=verified,
        is_balanced=True,
        health_report=health_report,
        verification_report=verification,
        workbook_audit=workbook_audit,
        output_file=output_file,
        audit_trail=audit_trail,
    )
