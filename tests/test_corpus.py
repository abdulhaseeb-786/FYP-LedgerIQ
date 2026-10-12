"""Run the labelled corpus through the pipeline and check every expectation.

Each case declares what it should produce, derived from how it was built
rather than from observed output. A case that expects to compile is also
required to survive `audit_workbook`, which evaluates the formulas in the
saved file - the only check that describes what the user actually receives.
"""

import pytest

from fyp_module3.core.parser import parse_trial_balance
from fyp_module3.core.pipeline import PipelineOptions, run_compilation
from fyp_module3.core.workbook_audit import audit_workbook
from fyp_module3.testing.corpus import CASES, write_case

COMPILING_STATUSES = {"SUCCESS", "RECOVERED_WARNING"}


@pytest.fixture(scope="module")
def corpus_dir(tmp_path_factory):
    """Materialise the corpus once for the whole module."""
    out = tmp_path_factory.mktemp("corpus")
    for case in CASES:
        write_case(case, out)
    return out


def _ids(cases):
    return [c.name for c in cases]


# ---------------------------------------------------------------- parsing

@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_ingestion_matches_the_declared_ledger(case, corpus_dir):
    """The parser must recover exactly the ledger each case was built from."""
    path = str(corpus_dir / case.filename)

    if case.expect_accounts is None and case.expect_total_dr is None:
        return  # case is about failing to parse at all

    try:
        payload = parse_trial_balance(path)
    except ValueError:
        # Cases that legitimately refuse to parse declare no account count.
        assert case.expect_accounts is None, \
            f"{case.name} was expected to parse but raised"
        return

    if case.expect_accounts is not None:
        assert len(payload.accounts) == case.expect_accounts, (
            f"{case.name}: parsed {len(payload.accounts)} accounts, "
            f"expected {case.expect_accounts} ({case.description})"
        )
    if case.expect_total_dr is not None:
        total_dr = round(sum(a.debit for a in payload.accounts), 2)
        assert total_dr == case.expect_total_dr, f"{case.name}: debits"
    if case.expect_total_cr is not None:
        total_cr = round(sum(a.credit for a in payload.accounts), 2)
        assert total_cr == case.expect_total_cr, f"{case.name}: credits"


# ---------------------------------------------------------------- compilation

@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_compilation_reaches_the_declared_outcome(case, corpus_dir, tmp_path):
    path = str(corpus_dir / case.filename)
    outcome = run_compilation(path, PipelineOptions(
        output_file=str(tmp_path / f"{case.name}_out.xlsx"),
        entity_name="Corpus Test Co",
        allow_working_capital_plug=case.allow_plug,
        enforce_health_gate=case.enforce_health_gate,
    ))
    result = outcome.result

    assert result.status == case.expect_status, (
        f"{case.name}: status {result.status}, expected {case.expect_status}. "
        f"Message: {result.message}"
    )

    if case.expect_message_contains:
        assert case.expect_message_contains.lower() in result.message.lower(), (
            f"{case.name}: message did not mention "
            f"'{case.expect_message_contains}' - got {result.message}"
        )

    if case.expect_status not in COMPILING_STATUSES:
        return

    report = result.verification_report
    if case.expect_total_assets is not None:
        assert report.total_assets == case.expect_total_assets, (
            f"{case.name}: total assets {report.total_assets:,.2f}, "
            f"expected {case.expect_total_assets:,.2f}"
        )
    if case.expect_net_profit is not None:
        assert report.net_profit == case.expect_net_profit, (
            f"{case.name}: net profit {report.net_profit:,.2f}, "
            f"expected {case.expect_net_profit:,.2f}"
        )

    for account_name, line_item_id in case.expect_classifications.items():
        account = next((a for a in outcome.accounts if a.account_name == account_name), None)
        assert account is not None, f"{case.name}: '{account_name}' missing after compilation"
        assert account.line_item_id == line_item_id, (
            f"{case.name}: '{account_name}' mapped to {account.line_item_id}, "
            f"expected {line_item_id}"
        )


# ---------------------------------------------------------------- exported file

COMPILING_CASES = [c for c in CASES if c.expect_status in COMPILING_STATUSES]


@pytest.mark.parametrize("case", COMPILING_CASES, ids=_ids(COMPILING_CASES))
def test_exported_workbook_verifies_against_its_own_formulas(case, corpus_dir, tmp_path):
    """Whatever the input shape, the delivered workbook must tie out."""
    path = str(corpus_dir / case.filename)
    outcome = run_compilation(path, PipelineOptions(
        output_file=str(tmp_path / f"{case.name}_audit.xlsx"),
        entity_name="Corpus Test Co",
        allow_working_capital_plug=case.allow_plug,
        enforce_health_gate=case.enforce_health_gate,
    ))
    assert outcome.result.output_file, f"{case.name}: nothing was exported"

    audit = audit_workbook(outcome.result.output_file)
    assert audit.passed, f"{case.name}: {audit.failures}"
    assert audit.balance_sheet_variance == 0.0
    assert audit.cash_flow_variance == 0.0
    assert audit.equity_variance == 0.0
    assert audit.trial_balance_variance == 0.0


# ---------------------------------------------------------------- corpus health

def test_corpus_covers_every_dimension():
    dimensions = {c.dimension for c in CASES}
    assert dimensions >= {
        "layout", "sheet-selection", "row-noise", "naming", "balance", "corruption",
    }


def test_corpus_case_names_are_unique():
    names = [c.name for c in CASES]
    assert len(names) == len(set(names))


def test_every_layout_variant_yields_the_same_ledger(corpus_dir):
    """The layout cases are one ledger in different clothes; they must agree."""
    layout_cases = [c for c in CASES
                    if c.dimension in ("layout", "sheet-selection")
                    and c.expect_total_dr is not None]
    totals = set()
    for case in layout_cases:
        payload = parse_trial_balance(str(corpus_dir / case.filename))
        totals.add((round(sum(a.debit for a in payload.accounts), 2),
                    round(sum(a.credit for a in payload.accounts), 2)))
    assert len(totals) == 1, f"layout variants disagreed on the ledger: {totals}"
