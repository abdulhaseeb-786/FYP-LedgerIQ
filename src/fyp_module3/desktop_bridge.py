"""Desktop App Bridge and Unified Programmatic API for FYP-Module-3.

A thin adapter over `core.pipeline`. It deliberately holds no orchestration of
its own: when this file carried its own copy of the pipeline it drifted from
the CLI's, and the two disagreed about error handling.
"""

import sys
import argparse
from typing import Optional

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

from fyp_module3.core.models import DesktopPipelineResult
from fyp_module3.core.pipeline import PipelineOptions, run_compilation


def process_trial_balance(
    input_file: str,
    output_file: Optional[str] = None,
    entity_name: Optional[str] = None,
    period: str = "June 30, 2025",
    sheet_name: Optional[str] = None,
    enforce_health_gate: bool = True,
    allow_working_capital_plug: bool = False,
) -> DesktopPipelineResult:
    """Run the compiler and return a unified result for desktop integration."""
    options = PipelineOptions(
        output_file=output_file,
        entity_name=entity_name,
        period=period,
        sheet_name=sheet_name,
        enforce_health_gate=enforce_health_gate,
        allow_working_capital_plug=allow_working_capital_plug,
    )
    return run_compilation(input_file, options).result


def main() -> None:
    parser = argparse.ArgumentParser(description="FYP-Module-3 Desktop Integration API Bridge")
    parser.add_argument("--input", "-i", required=True, help="Input Excel workbook")
    parser.add_argument("--output", "-o", help="Output Excel workbook")
    parser.add_argument("--entity", "-e", help="Company/Entity name")
    parser.add_argument("--period", "-p", default="June 30, 2025", help="Reporting period ended")
    parser.add_argument("--sheet", "-s", help="Worksheet name")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON to stdout")
    parser.add_argument("--no-health-gate", action="store_true",
                        help="Process the file even if the pre-flight health check fails")
    parser.add_argument("--allow-working-capital-plug", action="store_true",
                        help="Permit an unsupported balancing entry to force parity")

    args = parser.parse_args()
    result = process_trial_balance(
        input_file=args.input,
        output_file=args.output,
        entity_name=args.entity,
        period=args.period,
        sheet_name=args.sheet,
        enforce_health_gate=not args.no_health_gate,
        allow_working_capital_plug=args.allow_working_capital_plug,
    )

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"Status: {result.status}")
        print(f"Message: {result.message}")
        print(f"Health Score: {result.health_report.health_score}/100 "
              f"({result.health_report.severity})")
        if result.workbook_audit:
            for failure in result.workbook_audit.failures:
                print(f"  [FAIL] {failure}")
        if result.output_file:
            print(f"Compiled Workbook: {result.output_file}")

    # A workbook that does not verify must not report success to a caller that
    # is only checking the exit code.
    if result.status == "FAILED_CRITICAL":
        sys.exit(1)


if __name__ == "__main__":
    main()
