"""
Builds a classified chart of accounts from trial balance Excel files.

What it does:
    Reads every Excel file in input/, takes the account names, predicts each
    account's type with the fine-tuned MiniLM model, and maps it to a parent
    category and an IFRS financial statement.

Input:
    input/*.xls, input/*.xlsx  - one trial balance per file
    The account name column must match ACCOUNT_NAME_COL (default "AccountName").
    Other columns, such as debit/credit, are ignored.

Output (in chart_of_accounts/):
    chart_of_accounts_<trial balance name>.xlsx  - one file per trial balance
    Columns: account_id, account_name, account_type, subtype, financial_statement
    - account_id is the row number unless ACCOUNT_ID_COL is set
    - account_type is the parent category (asset, liability, equity, income, expense)
    - subtype is the model's prediction (e.g. asset_current, expense_direct_cost)
    - financial_statement is empty for off_balance accounts
    Every non-empty account name is classified, including repeated names.
    Re-running overwrites the previous output files.

Settings (top of file): MODEL_DIR, TRIAL_BALANCE_FOLDER, OUTPUT_FOLDER,
    ACCOUNT_NAME_COL, ACCOUNT_ID_COL.

Needs: account_type_classifier/ (from the training script), irfs_lookup.py,
    torch, transformers, pandas, openpyxl.
    Run from the project folder, because all paths are relative.
"""

import os
import sys
import json
import torch
import torch.nn as nn
import pandas as pd
from glob import glob
from transformers import AutoTokenizer, AutoModel
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

try:
    from irfs_lookup import IFRS_LOOKUP_TABLE
except ImportError:
    sys.exit(
        "Error: could not import 'irfs_lookup'. "
        "Make sure irfs_lookup.py is in the same directory as coa.py."
    )

# ---------------------------------------------------------
# Config — adjust these
# ---------------------------------------------------------
MODEL_DIR = "account_type_classifier"
TRIAL_BALANCE_FOLDER = "input"
OUTPUT_FOLDER = "output"
ACCOUNT_NAME_COL = "AccountName"     # <- change to match your file's actual column
ACCOUNT_ID_COL = None                # <- change or set to None if not present


PARENT_CATEGORY_MAP = {
    "asset_cash": "asset", "asset_current": "asset", "asset_fixed": "asset",
    "asset_non_current": "asset", "asset_prepayments": "asset", "asset_receivable": "asset",
    "equity": "equity", "equity_unaffected": "equity",
    "expense": "expense", "expense_depreciation": "expense", "expense_direct_cost": "expense",
    "income": "income", "income_other": "income",
    "liability_credit_card": "liability", "liability_current": "liability",
    "liability_non_current": "liability", "liability_payable": "liability",
    "off_balance": None,
}

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ---------------------------------------------------------
# Module-level references, populated by _load_model()
# ---------------------------------------------------------
tokenizer = None
model = None
label_classes = None
model_cfg = None

# ---------------------------------------------------------
# Model architecture (defined at module level so it can be imported)
# ---------------------------------------------------------
def mean_pool(last_hidden_state, attention_mask):
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    summed = torch.sum(last_hidden_state * mask, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts

class AccountTypeClassifier(nn.Module):
    def __init__(self, base_model, hidden_size, num_classes):
        super().__init__()
        self.base_model = base_model
        self.classifier = nn.Linear(hidden_size, num_classes)

    def forward(self, input_ids, attention_mask):
        outputs = self.base_model(input_ids=input_ids, attention_mask=attention_mask)
        pooled = mean_pool(outputs.last_hidden_state, attention_mask)
        return self.classifier(pooled)

# ---------------------------------------------------------
# Lazy model loader — called once before the first prediction
# ---------------------------------------------------------
def _load_model(model_dir=MODEL_DIR):
    global tokenizer, model, label_classes, model_cfg

    required_files = ["config.json", "label_classes.json", "model_state_dict.pt"]
    for fname in required_files:
        fpath = os.path.join(model_dir, fname)
        if not os.path.exists(fpath):
            sys.exit(
                f"Error: '{fpath}' not found. "
                "Run model.py first to train and save the model."
            )

    try:
        with open(os.path.join(model_dir, "config.json")) as f:
            model_cfg = json.load(f)
        with open(os.path.join(model_dir, "label_classes.json")) as f:
            label_classes = json.load(f)
    except (json.JSONDecodeError, KeyError) as e:
        sys.exit(f"Error: model config files in '{model_dir}' are malformed: {e}")

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        base_model = AutoModel.from_pretrained(model_cfg["base_model"]).to(device)
    except KeyError:
        sys.exit("Error: 'base_model' key missing from config.json.")
    except OSError as e:
        sys.exit(
            f"Error: failed to load tokenizer or base model.\n"
            f"Check your internet connection or that '{model_cfg.get('base_model', '?')}' is correct.\n"
            f"Details: {e}"
        )

    try:
        _model = AccountTypeClassifier(
            base_model, model_cfg["hidden_size"], model_cfg["num_classes"]
        ).to(device)
        _model.load_state_dict(
            torch.load(os.path.join(model_dir, "model_state_dict.pt"), map_location=device)
        )
        _model.eval()
        model = _model
    except RuntimeError as e:
        sys.exit(f"Error: failed to load model weights (architecture mismatch?): {e}")
    except KeyError as e:
        sys.exit(f"Error: missing key in config.json: {e}")

    print(f"Model loaded from {model_dir} ({len(label_classes)} classes, device={device})")

# ---------------------------------------------------------
# Prediction
# ---------------------------------------------------------
def predict_account_type(account_name: str) -> str:
    if model is None:
        _load_model()
    enc = tokenizer(
        account_name, padding="max_length", truncation=True,
        max_length=model_cfg["max_len"], return_tensors="pt",
    ).to(device)
    with torch.no_grad():
        logits = model(enc["input_ids"], enc["attention_mask"])
        pred_idx = torch.argmax(logits, dim=1).item()
    return label_classes[pred_idx]

# ---------------------------------------------------------
# Styling
# ---------------------------------------------------------
def style_chart(ws):
    fill = lambda c: PatternFill("solid", fgColor=c)
    thin = Side(style="thin", color="BFBFBF")

    ws.sheet_view.showGridLines = False

    for col, w in zip("ABCDE", (14, 55, 16, 26, 26)):
        ws.column_dimensions[col].width = w

    for col in "ABCDE":
        cell = ws[f"{col}1"]
        cell.fill = fill("2F5597")
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="left", vertical="center")

    for row in range(2, ws.max_row + 1):
        for col in "ABCDE":
            ws[f"{col}{row}"].border = Border(bottom=thin)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

# ---------------------------------------------------------
# Process a single trial balance file
# Returns (new_rows, skipped_rows) — does not write to disk itself
# ---------------------------------------------------------
def process_file(filepath: str) -> tuple[list, list]:
    try:
        df = pd.read_excel(filepath)
    except Exception as e:
        raise RuntimeError(
            f"Could not read '{os.path.basename(filepath)}': {e}"
        )

    # fail early with a clear message if the account name column is missing
    if ACCOUNT_NAME_COL not in df.columns:
        raise KeyError(
            f"'{ACCOUNT_NAME_COL}' not found in {os.path.basename(filepath)}. "
            f"Available columns: {list(df.columns)}"
        )

    new_rows, skipped_rows = [], []
    seen_account_names = set()    # created fresh for EVERY file, so names are never shared across files

    for idx, row in df.iterrows():
        account_name = str(row[ACCOUNT_NAME_COL]).strip()
        if not account_name or account_name.lower() == "nan":
            continue              # skip empty cells

        # use the real account id column if present, otherwise fall back to the row number
        account_id = row[ACCOUNT_ID_COL] if ACCOUNT_ID_COL and ACCOUNT_ID_COL in df.columns else idx

        # same name already seen earlier IN THIS FILE -> log it as a duplicate and move on
        """
        if account_name in seen_account_names:
            skipped_rows.append({
                "account_id": account_id,
                "account_name": account_name,
                "reason": "duplicate_account_name",
            })
            continue
        """

        # classify the account name
        try:
            subtype = predict_account_type(account_name)
        except Exception as e:
            skipped_rows.append({
                "account_id": account_id,
                "account_name": account_name,
                "reason": f"prediction_failed: {e}",
            })
            continue

        parent_category = PARENT_CATEGORY_MAP.get(subtype, None)
        financial_statement = IFRS_LOOKUP_TABLE.get(subtype, None)

        new_rows.append({
            "account_id": account_id,
            "account_name": account_name,
            "account_type": parent_category,
            "subtype": subtype,
            "financial_statement": financial_statement,
        })

        seen_account_names.add(account_name)

    return new_rows, skipped_rows

# ---------------------------------------------------------
# Process an entire folder — finds files, delegates each to process_file
# ---------------------------------------------------------
def process_folder(folder_path: str = TRIAL_BALANCE_FOLDER, output_folder: str = OUTPUT_FOLDER):
    files = sorted(
        glob(os.path.join(folder_path, "*.xls"))
        + glob(os.path.join(folder_path, "*.xlsx"))
    )
    if not files:
        raise FileNotFoundError(f"No .xls or .xlsx files found in {folder_path}")

    os.makedirs(output_folder, exist_ok=True)

    for filepath in files:
        # trial balance file name without folder or extension, e.g. "input/TB_Jan.xlsx" -> "TB_Jan"
        tb_name = os.path.splitext(os.path.basename(filepath))[0]

        try:
            new_rows, skipped_rows = process_file(filepath)
        except (KeyError, RuntimeError) as e:
            print(f"Warning: skipping '{tb_name}': {e}")
            continue

        if not new_rows:
            print(f"Warning: '{tb_name}' produced no classified accounts. Skipping output.")
            continue

        # one chart of accounts file per trial balance: chart_of_accounts_TB_Jan.xlsx
        chart_path = os.path.join(output_folder, f"chart_of_accounts_{tb_name}.xlsx")
        try:
            with pd.ExcelWriter(chart_path, engine="openpyxl") as writer:
                pd.DataFrame(new_rows).to_excel(writer, index=False, sheet_name="Chart of Accounts")
                style_chart(writer.sheets["Chart of Accounts"])
        except PermissionError:
            print(f"Warning: cannot write '{chart_path}' (file open in another program?). Skipping.")
            continue

        # one duplicates file per trial balance (only if this file had duplicates / prediction failures)
        if skipped_rows:
            dup_path = os.path.join(output_folder, f"duplicates_{tb_name}.xlsx")
            try:
                pd.DataFrame(skipped_rows).to_excel(dup_path, index=False)
            except PermissionError:
                print(f"Warning: cannot write '{dup_path}' (file open in another program?). Skipping.")

        print(f"{tb_name}: {len(new_rows)} accounts -> {chart_path}, {len(skipped_rows)} skipped")


if __name__ == "__main__":
    _load_model()
    process_folder()
