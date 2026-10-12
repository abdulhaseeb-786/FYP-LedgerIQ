"""Dynamic Statutory Notes Synthesizer (Section 5, Fourth & Fifth Schedules)."""

from typing import List, Dict, Optional
from collections import defaultdict

from fyp_module3.core.models import StandardizedAccountRecord, CompiledNote, NoteItem
from fyp_module3.core.taxonomy import face_amount

NOTE_REGISTRY = {
    4: {"title": "PROPERTY, PLANT AND EQUIPMENT", "stmt": "SOFP", "line_id": "sofp.nca.ppe"},
    5: {"title": "LONG-TERM DEPOSITS AND PREPAYMENTS", "stmt": "SOFP", "line_id": "sofp.nca.ltdeposits"},
    6: {"title": "STOCK-IN-TRADE", "stmt": "SOFP", "line_id": "sofp.ca.stock"},
    7: {"title": "TRADE DEBTS", "stmt": "SOFP", "line_id": "sofp.ca.debtors"},
    8: {"title": "CASH AND BANK BALANCES", "stmt": "SOFP", "line_id": "sofp.ca.cash"},
    9: {"title": "SHARE CAPITAL / CAPITAL ACCOUNT", "stmt": "SOFP", "line_id": "sofp.eq.sharecapital"},
    10: {"title": "TRADE AND OTHER PAYABLES", "stmt": "SOFP", "line_id": "sofp.cl.payables"},
    11: {"title": "COST OF SALES", "stmt": "PL", "line_id": "pl.cos"},
    12: {"title": "ADMINISTRATIVE EXPENSES", "stmt": "PL", "line_id": "pl.admin"},
}

# Row offsets within a single note block.
_TITLE_OFFSET = 0
_HEADER_OFFSET = 1
_FIRST_ITEM_OFFSET = 2
_BLOCK_GAP = 3


class NotesCompiler:
    """Compiles itemized sub-accounts into dynamically laid out statutory disclosure notes."""

    def __init__(self):
        self.notes: List[CompiledNote] = []
        self.coordinate_map: Dict[int, str] = {}   # note_number -> "'Notes'!C45"
        self.totals: Dict[int, float] = {}         # note_number -> signed subtotal

    def compile_notes(
        self,
        accounts: List[StandardizedAccountRecord],
        start_row: int = 5,
        tb_start_row: int = 6,
    ) -> List[CompiledNote]:
        """Group accounts into notes and calculate row coordinates.

        Every item is signed with `face_amount`, i.e. the same convention the
        face statements use, so a note subtotal is always directly comparable
        to the line it supports.
        """
        grouped: Dict[int, List[NoteItem]] = defaultdict(list)

        # `accounts` is written to the TB worksheet in this order starting at
        # `tb_start_row`, so the position here is the row a note item can point
        # its formula at.
        for offset, acc in enumerate(accounts):
            note_num = acc.note_number
            if not note_num or note_num not in NOTE_REGISTRY:
                continue
            grouped[note_num].append(NoteItem(
                account_code=acc.account_code,
                account_name=acc.account_name,
                amount=face_amount(acc.line_item_id or "", acc.debit, acc.credit),
                line_item_id=acc.line_item_id,
                tb_row_index=acc.tb_row_index,
                tb_sheet_row=tb_start_row + offset,
            ))

        self.notes = []
        self.coordinate_map = {}
        self.totals = {}
        current_row = start_row

        for note_num in sorted(NOTE_REGISTRY.keys()):
            items = grouped.get(note_num, [])
            if not items:
                continue

            meta = NOTE_REGISTRY[note_num]
            subtotal_row = current_row + _FIRST_ITEM_OFFSET + len(items)
            cell_ref = f"'Notes'!C{subtotal_row}"

            note_obj = CompiledNote(
                note_number=note_num,
                title=meta["title"],
                target_statement=meta["stmt"],
                target_line_id=meta["line_id"],
                items=items,
                start_row=current_row,
                subtotal_row=subtotal_row,
                subtotal_cell_ref=cell_ref,
            )

            self.notes.append(note_obj)
            self.coordinate_map[note_num] = cell_ref
            self.totals[note_num] = round(sum(i.amount for i in items), 2)

            current_row = subtotal_row + _BLOCK_GAP

        return self.notes

    def get_note_cell_ref(self, note_number: int) -> Optional[str]:
        """Return the Excel formula cell reference for a note subtotal."""
        return self.coordinate_map.get(note_number)

    def get_note_total(self, note_number: int) -> Optional[float]:
        """Return the signed Python subtotal for a note, or None when absent."""
        return self.totals.get(note_number)

    def first_item_row(self, note: CompiledNote) -> int:
        """Row index of the first itemised line inside `note`."""
        return (note.start_row or 0) + _FIRST_ITEM_OFFSET
