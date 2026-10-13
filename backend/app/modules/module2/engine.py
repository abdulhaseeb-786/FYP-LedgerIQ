"""Module 2: Directed Acyclic Graph (DAG) Year-End Adjustments Engine.

The engine manages topological ordering of inter-dependent adjustments:
1. Depreciation -> Decreases Fixed Asset NBV, increases Operating Expenses.
2. Prepayments Amortisation -> Releases advances into Administrative Expenses.
3. Expense Accruals -> Records unbilled expenses and current liabilities.
4. Doubtful Debt Allowance -> Adjusts bad debt provision against trade receivables.
5. WPPF (Workers Profit Participation) -> 5% of Profit Before Tax (depends on 1-4).
6. Tax Provision -> 29% on Profit after WPPF (depends on 5).

Any cycle is detected symbolically and reported as an unfeasible graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, Sequence, runtime_checkable

import networkx as nx

from .models import (
    JournalEntry,
    JournalLine,
    Side,
    TrialBalance,
    WorkingSet,
    ZERO,
    quantise,
    total,
)


@runtime_checkable
class Adjustment(Protocol):
    ref: str
    title: str
    depends_on: tuple[str, ...]

    def build(self, working: WorkingSet): ...


@dataclass(slots=True)
class AdjustmentRun:
    """Outcome of an adjustment run."""

    entries: list[JournalEntry]
    skipped: list[str]
    adjusted: TrialBalance
    working_set: WorkingSet


def topological_order(adjustments: Sequence[Adjustment]) -> list[str]:
    """Sort adjustments into topological order based on declared dependencies.

    Raises:
        ValueError: If a circular dependency is detected.
    """
    g = nx.DiGraph()
    refs = {a.ref for a in adjustments}

    for adj in adjustments:
        g.add_node(adj.ref)
        for dep in adj.depends_on:
            if dep in refs:
                # Dependency must be evaluated BEFORE the dependent adjustment
                g.add_edge(dep, adj.ref)

    try:
        return list(nx.topological_sort(g))
    except nx.NetworkXUnfeasible as err:
        cycles = list(nx.simple_cycles(g))
        raise ValueError(f"Circular dependency detected in adjustment graph: {cycles}") from err


def run(
    trial_balance: TrialBalance,
    adjustments: Sequence[Adjustment],
    posting_date: str = "2025-06-30",
) -> AdjustmentRun:
    """Execute the adjustments over the DAG and return the adjusted trial balance."""
    order = topological_order(adjustments)
    by_ref = {a.ref: a for a in adjustments}

    working = WorkingSet(trial_balance)
    entries: list[JournalEntry] = []
    skipped: list[str] = []

    for ref in order:
        adj = by_ref[ref]
        draft = adj.build(working)
        if draft is None or draft.is_empty:
            skipped.append(ref)
            continue

        # Convert draft postings into a verified balanced JournalEntry
        lines = tuple(
            JournalLine(
                account_code=p.account_code,
                side=p.side,
                amount=p.amount,
                narration=f"[{ref}] {p.account_name}",
            )
            for p in draft.postings
        )

        entry = JournalEntry(
            ref=ref,
            date=posting_date,
            narration=draft.narration,
            lines=lines,
            source_module="module2",
            workings=draft.workings,
        )

        working.apply(entry, draft.postings)
        entries.append(entry)

    adjusted_tb = working.to_trial_balance()

    # Guarantee double-entry parity conservation
    if adjusted_tb.parity_delta != ZERO:
        raise RuntimeError(
            f"Parity invariant violated after applying adjustments: Delta = {adjusted_tb.parity_delta}"
        )

    return AdjustmentRun(
        entries=entries,
        skipped=skipped,
        adjusted=adjusted_tb,
        working_set=working,
    )
