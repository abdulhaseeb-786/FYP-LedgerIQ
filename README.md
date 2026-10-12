# FYP-Module-3: Autonomous Statutory Statement & Dynamic Notes Compiler

**Module ID:** `M3-M9-COMPOUND`  
**Standard:** Companies Act 2017 (Fifth Schedule) & IFRS for SMEs  

An autonomous compiler that ingests 3-to-4 column Trial Balance Excel workbooks (balanced or unbalanced), resolves discrepancies via auditor-grade heuristics, classifies accounts into statutory line items, dynamically synthesizes numbered explanatory disclosure notes (Notes 4 through 12), and exports a fully linked OpenXML (`.xlsx`) workbook powered by recalculating formulas.

---

## Key Features

1. **Intelligent Parity Balancer (Handling Unbalanced TBs):**
   - **Heuristic 1 (Inverted Polarity):** Detects a balance posted on the wrong side. Because flipping a balance of `b` moves the variance by `2b`, only an account holding exactly `|Δ| / 2`, on the side that moves the variance toward zero, can correct the ledger.
   - **Heuristic 2 (Transposition & Slide):** Identifies digit-swap and decimal-slide errors (`Δ mod 9 == 0`). The required correction is derived from the direction of the variance, and amounts are compared in integer *paisa* so fractional balances survive.
   - **Heuristic 3 (Working Capital Absorption) — opt-in:** Posts an unexplained residual to `Trade Creditors`/`Trade Debtors` to force parity. **Off by default.** See *Unbalanced trial balances* below.
   - Every heuristic is applied, then kept only if it strictly reduces the absolute variance; otherwise it is rolled back.
2. **Dynamic Statutory Notes Synthesizer:**
   - Synthesizes variable-length disclosure notes (Notes 4–12) with itemized schedules.
   - Note subtotals and the face lines they support are derived from one shared polarity rule, and the compiler refuses to link a face line to a note whose subtotal disagrees with it.
3. **Live OpenXML Formulas driven by the `TB` sheet:**
   - Note line items reference their `TB` row (`='TB'!E7-'TB'!F7`); face lines without a note read the ledger directly (`=SUMIF('TB'!$C$6:$C$40,"sofp.ca.cash",…)`); subtotals, gross and net profit, and equity linkages are `=SUM(...)` / cross-sheet references.
   - Editing any raw number on the `TB` sheet cascades through Notes, P&L, Balance Sheet, Changes in Equity and Cash Flows in Microsoft Excel.
4. **Post-export workbook audit:**
   - After saving, the compiler re-reads the `.xlsx` and **evaluates its own formulas** to confirm trial balance parity, `A = L + E`, cash flow reconciliation, equity reconciliation and every note cross-reference. The integrity claim is therefore made about the file you receive, not about values held in memory.
5. **Standard Accounting Presentation:**
   - Single top border, double bottom underline for totals.
   - Accounting number format mask: `_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)`.

---

## Quick Start

### 1. Environment Setup

```bash
cd FYP-working

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

### 2. Run Compiler via CLI

```bash
# Basic usage
python -m fyp_module3.cli --input path/to/TB.xlsx --output Financial_Statements.xlsx

# Specify company name and year-end date
python -m fyp_module3.cli --input path/to/TB.xlsx --output output.xlsx \
    --entity "Aimal Khan Traders" --period "June 30, 2025"
```

| Flag | Effect |
| --- | --- |
| `--sheet` | Parse a named worksheet instead of auto-detecting |
| `--no-health-gate` | Compile despite critical pre-flight defects, for diagnosis |
| `--allow-working-capital-plug` | Permit an unsupported balancing entry (see below) |

The CLI **exits non-zero** when the statements do not verify.

### 3. Interactive App

```bash
streamlit run src/fyp_module3/app.py
```

### 4. Programmatic Use

```python
from fyp_module3 import run_compilation, PipelineOptions

outcome = run_compilation("TB.xlsx", PipelineOptions(entity_name="Acme (Pvt) Ltd"))
print(outcome.result.status)          # SUCCESS | RECOVERED_WARNING | FAILED_CRITICAL
print(outcome.result.workbook_audit)  # what the exported formulas actually evaluate to
```

### 5. Run Automated Tests

```bash
pytest -v
```

### 6. Generate the test corpus

Public trial balances essentially do not exist - firms publish finished
statements, not working papers - so robustness is tested against deliberately
constructed shapes instead of volume of real data.

```bash
python -m fyp_module3.testing.corpus --out data/generated
```

This writes 24 labelled trial balances plus a `manifest.json` describing what
each one should produce. The cases span six dimensions:

| Dimension | Covers |
| --- | --- |
| `layout` | 3-col, 4-col, no header row, codes inside names, a name column holding codes, several debit/credit pairs, amounts as formatted text |
| `sheet-selection` | Mapping/grouping/COA decoy tabs, the ledger not on the first sheet |
| `row-noise` | Section captions, mid-table subtotals, narrative rows, nil balances, an account legitimately named "Total ..." |
| `naming` | Abbreviations, misspellings, contra accounts, party sub-ledger names |
| `balance` | Transposition with paisa, an inverted entry, two-sided rows, an unexplained residual, the opt-in plug, a pre-closed profit summary |
| `corruption` | `#REF!` cells, a single-sided extract, a narrative-only sheet |

`tests/test_corpus.py` runs every case and checks the parsed ledger, the
compilation status, the classifications, and - for anything that compiles -
that the exported workbook's own formulas tie out to nil variance.

---

## Unbalanced trial balances

A trial balance that does not balance is a data problem, not a formatting problem. If Heuristics 1 and 2 cannot explain the variance, the compiler **reports it and stops** rather than capitalising the difference into working capital.

Passing `--allow-working-capital-plug` permits the plug. When it is used:

- the residual is posted to `Trade Creditors`/`Trade Debtors` with a confidence of `0.00`;
- the audit trail records it as an **unsupported entry**;
- the run returns `RECOVERED_WARNING`, never `SUCCESS`;
- the statements are not supported by the ledger and should not be presented as audited.

A variance above the materiality ceiling (over 5% of volume *and* over PKR 500,000) is refused even with the flag set.

## Unclassified accounts

An account whose title matches no Fifth Schedule line item — or whose closest match sits on the opposite side of the ledger — is routed to a **suspense** line (`sofp.ca.suspense` / `sofp.cl.suspense`) and reported, rather than being absorbed into administrative expenses or trade payables where it would quietly shift reported profit. Suspense balances appear on the face of the balance sheet and can be re-mapped in the app's *Account Overrides* tab.

## Output status

| Status | Meaning |
| --- | --- |
| `SUCCESS` | Every in-memory check and every formula in the exported workbook verifies |
| `RECOVERED_WARNING` | Compiles and ties out, but the supplied ledger was altered (a heuristic correction or an unsupported balancing entry) or carried recoverable data noise |
| `FAILED_CRITICAL` | Pre-flight gate failed, the ledger could not be balanced, or the exported workbook does not verify |

A workbook that fails verification is still written — for diagnosis — but its filename is suffixed `_UNVERIFIED` so it cannot be mistaken for a finished deliverable.

---

## Architecture

```
core/parser.py          Ingestion: sheet, column-pair and end-of-table detection
core/classifier.py      Fifth Schedule taxonomy mapping, suspense fallback
core/validator.py       Pre-flight data health gate
core/balancer.py        Heuristics 1-3, each rolled back unless it improves parity
core/verifier.py        A = L + E, zero leakage, note reconciliation, self-correction
core/workbook_audit.py  Evaluates the exported .xlsx formulas
core/pipeline.py        The single orchestration used by the CLI, bridge and app
core/taxonomy.py        Line items plus `face_polarity` / `face_amount`
testing/corpus.py       The labelled trial balance corpus and its expectations
statements/             Notes, P&L, SOFP, Changes in Equity, Cash Flows
exporter/               7-tab OpenXML writer
```

`core/taxonomy.face_polarity` is the single source of truth for which side a line item is presented on. The notes compiler and both face statements call it rather than re-deriving the rule, because a polarity that disagrees between a note and the line it feeds is what lets a workbook ship out of balance.
