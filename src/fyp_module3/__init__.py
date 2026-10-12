"""FYP-Module-3: Autonomous Statutory Statement & Dynamic Notes Compiler."""

from fyp_module3.core.pipeline import (
    PipelineOptions, CompilationOutcome, run_compilation,
)
from fyp_module3.core.validator import DataHealthValidator, UnprocessableDataError
from fyp_module3.core.balancer import IntelligentParityBalancer, IrreconcilableTrialBalanceError
from fyp_module3.core.verifier import StatementVerifier
from fyp_module3.core.workbook_audit import audit_workbook
from fyp_module3.core.models import (
    DesktopPipelineResult, DataHealthReport, VerificationReport, WorkbookAuditResult,
)

__version__ = "2.0.0"

__all__ = [
    # Pipeline
    "run_compilation",
    "PipelineOptions",
    "CompilationOutcome",
    # Stages
    "DataHealthValidator",
    "IntelligentParityBalancer",
    "StatementVerifier",
    "audit_workbook",
    # Contracts
    "DesktopPipelineResult",
    "DataHealthReport",
    "VerificationReport",
    "WorkbookAuditResult",
    # Errors
    "UnprocessableDataError",
    "IrreconcilableTrialBalanceError",
]


def process_trial_balance(*args, **kwargs):
    """Deferred re-export of the desktop bridge entry point."""
    from fyp_module3.desktop_bridge import process_trial_balance as _impl
    return _impl(*args, **kwargs)


def run_pipeline(*args, **kwargs):
    """Deferred re-export of the CLI entry point."""
    from fyp_module3.cli import run_pipeline as _impl
    return _impl(*args, **kwargs)


__all__ += ["process_trial_balance", "run_pipeline"]
