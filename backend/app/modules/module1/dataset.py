"""
Builds the train/test dataset for the account type classifier.

What it does:
    Downloads the chart-of-accounts (COA) CSVs from every Odoo l10n_XX
    country module (Odoo branch 17.0) and turns them into one cleaned dataset.

Input:
    None. Data is fetched from github.com/odoo/odoo, so internet and git are
    required. A metadata-only clone is stored in ./odoo_repo/.

Cleaning steps:
    1. Keep only COA files that have id, name and account_type columns.
    2. Drop duplicate (account_name, account_type) rows.
    3. Drop account names with non-English characters.
    4. Drop account types with 100 rows or fewer.

Output (in ./data/):
    train.csv  - 80% of rows
    test.csv   - 20% of rows (stratified by account_type, random_state=42)
    Columns: account_id, account_name, account_type, country, account_name_original

Requirements: pandas, scikit-learn, langdetect, git.
Run on Google Colab, then download the data/ folder for training.
"""

import unicodedata
import os, subprocess, io, re
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.model_selection import train_test_split
import time

os.makedirs("data", exist_ok=True)

# ---------------------------------------------------------
# 1. Shallow, blob-less clone — metadata only, no bulk downloads.
#    Also sidesteps the old bug: blob URLs return HTML, not CSV.
# ---------------------------------------------------------
REPO_DIR = "odoo_repo"
if not os.path.exists(REPO_DIR):
    subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout",
         "-b", "17.0", "https://github.com/odoo/odoo.git", REPO_DIR],
        check=True
    )

def git(*args):
    return subprocess.run(
        ["git", "-C", REPO_DIR] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",   # git outputs UTF-8; Windows would otherwise default to cp1252
        errors="replace"    # a bad byte becomes "?" instead of crashing the reader thread
    )

# ---------------------------------------------------------
# 2. Discover ALL l10n_XX modules and locate their
#    Chart-of-Accounts CSV files regardless of folder layout.
# ---------------------------------------------------------

folders = git(
    "ls-tree", "-d", "--name-only", "HEAD:addons"
).stdout.splitlines()

two_letter_codes = sorted(
    m.group(1)
    for f in folders
    if (m := re.match(r"^l10n_([a-z]{2})$", f))
)

print(f"Total l10n_XX modules: {len(two_letter_codes)}")


# ---------------------------------------------------------
# 3. Search each localization module recursively for CSVs
#    that appear to contain Chart-of-Accounts data.
# ---------------------------------------------------------

country_files = {}
no_coa = []

for code in two_letter_codes:

    module = f"addons/l10n_{code}"

    # Get every file in this localization module
    result = git("ls-tree", "-r", "--name-only", f"HEAD:{module}")

    if result.returncode != 0:
        no_coa.append(code)
        continue

    files = result.stdout.splitlines()

    # Find CSV files that look like account / COA files
    csv_candidates = [
        f for f in files
        if f.lower().endswith(".csv")
        and (
            "account" in os.path.basename(f).lower()
            or "coa" in os.path.basename(f).lower()
        )
    ]

    found = False

    for relative_path in csv_candidates:

        full_path = f"{module}/{relative_path}"

        result = git("show", f"HEAD:{full_path}")

        if result.returncode != 0:
            continue

        try:
            df = pd.read_csv(io.StringIO(result.stdout), nrows=5)
        except Exception:
            continue

        # Accept files containing the basic COA fields
        columns_lower = {c.lower(): c for c in df.columns}

        has_name = "name" in columns_lower
        has_type = "account_type" in columns_lower

        if has_name and has_type:
            country_files[code] = relative_path
            found = True
            break

    if not found:
        no_coa.append(code)


# ---------------------------------------------------------
# 4. Report exactly what was discovered
# ---------------------------------------------------------

print(f"\nCountries with usable COA CSV: {len(country_files)}")
print(f"Countries without usable COA CSV: {len(no_coa)}")

"""
print("\nCOA files found:")
for code, path in country_files.items():
    print(f"{code}: {path}")
"""

print("\nNo usable COA CSV found:")
print(no_coa)

# ---------------------------------------------------------
# 5.. Load + validate each candidate (required columns + usable rows),
# ---------------------------------------------------------
REQUIRED_COLS = ["id", "name", "account_type"]
#TARGET_COUNTRIES = 80

country_dfs = {}

for code, relative_path in country_files.items():

    path = f"addons/l10n_{code}/{relative_path}"

    result = git("show", f"HEAD:{path}")

    if result.returncode != 0:
        print(f"{code}: FAILED to fetch {relative_path}")
        continue

    try:
        df = pd.read_csv(io.StringIO(result.stdout))
    except Exception as e:
        print(f"{code}: FAILED to parse ({e})")
        continue

    # Handle column names
    if not all(c in df.columns for c in ["id", "name", "account_type"]):
        print(f"{code}: missing required columns")
        continue

    df = df[["id", "name", "account_type"]].rename(
        columns={
            "id": "account_id",
            "name": "account_name"
        }
    )

    df = df.dropna(subset=["account_name", "account_type"])

    if df.empty:
        continue

    df["country"] = code
    country_dfs[code] = df

print(f"\nUsing {len(country_dfs)} countries: {list(country_dfs.keys())}")

combined_df = pd.concat(country_dfs.values(), ignore_index=True)
print(f"Combined (pre-cutoff): {len(combined_df)} rows")

def is_english(text):
    for ch in str(text):
        if 32 <= ord(ch) <= 126:
            continue                          # normal printable ASCII: always allowed

        # Ask Python what kind of character this is. It returns a 2-letter code:
        # the first letter is the group (L = letter, M = accent mark, N = number,
        # P = punctuation, S = symbol, Z = space, C = invisible/control),
        # the second letter is the subtype (e.g. "Pd" = dash, "Lu" = uppercase letter).
        cat = unicodedata.category(ch)        
        if cat[0] in ("L", "M") or cat == "Nd":
            return False                      # real foreign text: reject the name

        # Anything else (dashes, fancy quotes, symbols, odd spaces, invisible characters)
        # is not a foreign word, so we let it pass and check the next character.
    return True

# Remember every translation so a repeated name is only sent to Google once
"""
translation_cache = {}

def translate_account_name(name, retries=5):
    # Already translated earlier? Return it without calling Google
    if name in translation_cache:
        return translation_cache[name]

    for attempt in range(retries):
        try:
            result = GoogleTranslator(source="auto", target="en").translate(name)
            result = result or name          # if Google returns nothing, keep the original
            translation_cache[name] = result
            time.sleep(0.3)                  # pause after each call: ~3 requests/sec, under the 5/sec limit
            return result
        except Exception:
            # Rate-limited: wait longer after each failure (2s, 4s, 8s, 16s, 32s)
            time.sleep(2 ** (attempt + 1))

    # All retries failed: keep the original name and report it
    print(f"Translation failed for '{name}'")
    translation_cache[name] = name
    return name
"""

# duplicate data remove
before = len(combined_df)
combined_df = combined_df.drop_duplicates(subset=["account_name", "account_type"]).reset_index(drop=True)
print(f"\nDropped {before - len(combined_df)} duplicate rows from dataset.")

print("\nCounts per class after original duplicate removal:")
print(combined_df["account_type"].value_counts().sort_index())

# run right after building combined_df from Odoo
combined_df["account_name_original"] = combined_df["account_name"]
non_en_mask = combined_df["account_name"].astype(str).apply(lambda x: not is_english(x))

# TEMPORARY CHECK: show 40 random flagged names with the language langdetect guessed
flagged = combined_df[non_en_mask]["account_name"].astype(str)
for name in flagged.sample(40, random_state=1):
    print(f"{detect_langs(name)[0]}  ->  {name}")   # e.g. "nl:0.99  ->  Main Safe"

# Keep only the rows NOT flagged (~ flips the mask: True becomes False and vice versa)
print(f"Removing {non_en_mask.sum()} non-English account names.")
combined_df = combined_df[~non_en_mask].reset_index(drop=True)
print(f"Rows remaining: {len(combined_df)}")

# remove classes with less than or equal to 100 instances only
# Count how many rows each account_type has
class_counts = combined_df["account_type"].value_counts()
print("Removing classes:", list(class_counts[class_counts <= 100].index))

# Class names that have MORE than 100 rows: these are the ones we keep
keep_classes = class_counts[class_counts > 100].index
combined_df = combined_df[combined_df["account_type"].isin(keep_classes)].reset_index(drop=True)

# Check: the remaining classes and their counts
print(f"Rows remaining: {len(combined_df)}")
print(combined_df["account_type"].value_counts())

# Stratified split: every account_type appears in both train and test
# in roughly the same proportion as in the full dataset.
train_df, test_df = train_test_split(
    combined_df,
    test_size=0.2,                         # 20% of rows go to test
    stratify=combined_df["account_type"],  # keep class proportions equal in both splits
    random_state=42                        # makes the split reproducible
)

# Check: class proportions should be nearly identical in both splits
print("Train class share:")
print(train_df["account_type"].value_counts(normalize=True).sort_index())
print("\nTest class share:")
print(test_df["account_type"].value_counts(normalize=True).sort_index())

# Save to CSV (your existing lines)
train_df.to_csv("data/train.csv", index=False)
test_df.to_csv("data/test.csv", index=False)