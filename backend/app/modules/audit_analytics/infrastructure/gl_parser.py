"""General Ledger File Ingestion & Normalizer (CSV & OpenXML Excel)."""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import re
import csv
import openpyxl

from app.modules.audit_analytics.domain.models import GLTransactionRecord


class GLParserException(Exception):
    """Raised when General Ledger file cannot be parsed or lacks required columns."""
    pass


def parse_clean_float(val: Any) -> float:
    """Parse numeric values with accounting format support like (1,000.00)."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s or s in ("-", "--", "nil", "none"):
        return 0.0

    # Negative accounting format: (1,234.56)
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    # Strip currency symbols and commas
    s = re.sub(r"[^\d.-]", "", s)
    if not s:
        return 0.0

    try:
        num = float(s)
        return -num if is_negative else num
    except ValueError:
        return 0.0


def parse_clean_date(val: Any) -> datetime:
    """Parse heterogeneous date formats into standard datetime."""
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())

    s = str(val).strip()
    if not s:
        return datetime.now()

    # Try common formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    # Try extracting digits if standard string
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    return datetime.now()


class GeneralLedgerParser:
    """Ingests multi-column General Ledger spreadsheets and CSV files."""

    def parse_file(self, file_path: str, sheet_name: Optional[str] = None) -> List[GLTransactionRecord]:
        path = Path(file_path)
        if not path.exists():
            raise GLParserException(f"General Ledger file not found: {file_path}")

        suffix = path.suffix.lower()
        if suffix in (".xlsx", ".xlsm"):
            return self._parse_excel(path, sheet_name)
        elif suffix == ".csv":
            return self._parse_csv(path)
        else:
            raise GLParserException(f"Unsupported General Ledger file format: {suffix}. Supported: .xlsx, .csv")

    def _parse_excel(self, path: Path, sheet_name: Optional[str]) -> List[GLTransactionRecord]:
        wb = openpyxl.load_workbook(str(path), data_only=True)
        ws = wb[sheet_name] if (sheet_name and sheet_name in wb.sheetnames) else wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise GLParserException("Excel sheet is empty.")

        return self._extract_records_from_matrix(rows)

    def _parse_csv(self, path: Path) -> List[GLTransactionRecord]:
        rows = []
        with open(str(path), mode="r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.reader(f)
            for r in reader:
                rows.append(r)
        if not rows:
            raise GLParserException("CSV file is empty.")

        return self._extract_records_from_matrix(rows)

    def _extract_records_from_matrix(self, rows: List[Any]) -> List[GLTransactionRecord]:
        # 1. Detect header row (first row with at least 3 recognizable column names)
        header_row_idx = -1
        col_map: Dict[str, int] = {}

        for r_idx, row in enumerate(rows[:20]):
            curr_map = self._map_columns([str(c or "").strip().lower() for c in row])
            if len(curr_map) >= 3 and ("account_name" in curr_map or "amount" in curr_map or "debit" in curr_map):
                header_row_idx = r_idx
                col_map = curr_map
                break

        if header_row_idx == -1 or not col_map:
            # Fallback to row 0 if no clear header found
            header_row_idx = 0
            col_map = self._map_columns([str(c or "").strip().lower() for c in rows[0]])

        records: List[GLTransactionRecord] = []
        for r_idx in range(header_row_idx + 1, len(rows)):
            row = rows[r_idx]
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue

            acc_name = self._get_cell(row, col_map.get("account_name"))
            if not acc_name:
                acc_name = self._get_cell(row, col_map.get("account_code")) or f"Account_{r_idx}"

            voucher_no = self._get_cell(row, col_map.get("voucher_no")) or f"VCH-{r_idx:05d}"
            date_raw = self._get_cell(row, col_map.get("date"))
            dt = parse_clean_date(date_raw)

            acc_code = self._get_cell(row, col_map.get("account_code"))
            narration = self._get_cell(row, col_map.get("narration")) or ""
            user_id = self._get_cell(row, col_map.get("user_id")) or "system"

            debit = parse_clean_float(self._get_cell(row, col_map.get("debit")))
            credit = parse_clean_float(self._get_cell(row, col_map.get("credit")))
            net_amt = parse_clean_float(self._get_cell(row, col_map.get("net_amount")))

            # SAP FI / Banking Debit-Credit indicator ('S' = Soll/Debit, 'H' = Haben/Credit)
            ind_val = str(self._get_cell(row, col_map.get("indicator")) or "").strip().upper()
            if ind_val in ("S", "DR", "DEBIT", "D"):
                amt_val = abs(net_amt) if net_amt != 0.0 else (debit or credit)
                debit, credit, net_amt = amt_val, 0.0, amt_val
            elif ind_val in ("H", "CR", "CREDIT", "C"):
                amt_val = abs(net_amt) if net_amt != 0.0 else (credit or debit)
                debit, credit, net_amt = 0.0, amt_val, -amt_val
            elif debit == 0.0 and credit == 0.0 and net_amt != 0.0:
                if net_amt > 0:
                    debit = net_amt
                else:
                    credit = abs(net_amt)
            elif net_amt == 0.0 and (debit != 0.0 or credit != 0.0):
                net_amt = debit - credit

            # Ignore rows with 0 balances and no name
            if debit == 0.0 and credit == 0.0 and net_amt == 0.0:
                continue

            records.append(
                GLTransactionRecord(
                    row_index=r_idx + 1,
                    voucher_no=str(voucher_no),
                    date=dt,
                    account_code=str(acc_code) if acc_code else None,
                    account_name=str(acc_name),
                    narration=str(narration),
                    debit=debit,
                    credit=credit,
                    net_amount=net_amt,
                    user_id=str(user_id),
                )
            )

        if not records:
            raise GLParserException("No valid transaction rows found in General Ledger.")

        return records

    @staticmethod
    def _map_columns(headers: List[str]) -> Dict[str, int]:
        m: Dict[str, int] = {}
        for idx, h in enumerate(headers):
            h_clean = h.replace("_", " ").replace("-", " ")
            if any(k in h_clean for k in ["voucher", "vch", "doc no", "document", "jv", "reference", "ref no", "belnr", "trans id"]):
                m["voucher_no"] = idx
            elif any(k in h_clean for k in ["date", "posting date", "trans date", "time", "budat", "bldat"]):
                m["date"] = idx
            elif any(k in h_clean for k in ["account code", "acct code", "gl code", "code", "acct no", "hkont", "saknr"]):
                m["account_code"] = idx
            elif any(k in h_clean for k in ["account title", "account name", "account", "head of account", "gl name", "txt20", "txt50"]):
                m["account_name"] = idx
            elif any(k in h_clean for k in ["narration", "description", "memo", "particulars", "remarks", "sgtxt"]):
                m["narration"] = idx
            elif any(k in h_clean for k in ["debit", "dr amount", "dr"]) and "indicator" not in h_clean:
                m["debit"] = idx
            elif any(k in h_clean for k in ["credit", "cr amount", "cr"]) and "indicator" not in h_clean:
                m["credit"] = idx
            elif any(k in h_clean for k in ["shkzg", "indicator", "dr cr", "dc"]):
                m["indicator"] = idx
            elif any(k in h_clean for k in ["net amount", "amount", "total amount", "dmbtr", "wrbtr"]):
                m["net_amount"] = idx
            elif any(k in h_clean for k in ["user", "created by", "posted by", "operator", "usnam"]):
                m["user_id"] = idx
        return m

    @staticmethod
    def _get_cell(row: List[Any], idx: Optional[int]) -> Any:
        if idx is not None and 0 <= idx < len(row):
            return row[idx]
        return None
