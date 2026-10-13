"""
Matches bank statement entries to cash ledger entries and sorts them into groups.

USAGE
    kept, low_score, amount_errors, unmatched_bank, unmatched_ledger = reconcile(entries_bank, entries_ledger)

    Inputs are the entry lists from the Data reader (dicts with description, type, amount, date).

PIPELINE
    1. Find candidates
       A bank entry and a ledger entry can be paired only if all three hold:
         - type is opposite (a ledger debit pairs with a bank credit, and vice versa)
         - dates are within day_delta days of each other
         - amounts are within amount_delta (as a fraction) of the bank amount

    2. Score each candidate (0 to 1)
       Weighted sum of four scores:
         - token overlap : shared words / all distinct words in the two descriptions
         - fuzzy text    : character-level similarity of the descriptions (rapidfuzz)
         - date          : 1.0 for the same day, falling to 0.0 at day_delta days apart
         - amount        : 1.0 for an exact amount, falling to 0.0 at the amount_delta limit

    3. Pick the best one-to-one pairing
       linear_sum_assignment maximises the total score, each entry is used in at most one pair.

    4. Sort the pairs into groups
       - amount_errors : amounts differ by more than 0.01 (likely a typo or wrong amount)
       - kept          : amounts equal and score >= min_score (confirmed matches)
       - low_score     : amounts equal but score < min_score (probably a coincidence)
       - unmatched     : entries that ended up in none of the pairs above

OUTPUT
    kept, low_score, amount_errors : lists of (bank_index, ledger_index, score)
    unmatched_bank, unmatched_ledger : lists of indices into the bank / ledger entry lists

PARAMETERS (current values, can be tuned after testing on more files)
    day_delta     = 30                  max days apart for a candidate pair
    amount_delta  = 0.03                max amount difference (3% of the bank amount)
    min_score     = 0.5                 below this, an equal-amount pair goes to low_score
    weights       = token 0.3, fuzzy 0.2, date 0.1, amount 0.4   (must sum to 1; set inside score())
    amount_tol    = 0.01                amounts closer than this count as equal (set inside split_by_amount())
"""

from nltk.tokenize import RegexpTokenizer
from rapidfuzz import fuzz 
import math
import numpy as np
from scipy.optimize import linear_sum_assignment

# nltk tokenizer that keeps only word characters (letters/digits), dropping ".", "-", "#"
# (RegexpTokenizer needs no extra nltk downloads, unlike word_tokenize)
tokenizer = RegexpTokenizer(r"\w+")

day_delta = 30  # how many days apart two entries can be to still be considered a candidate match
amount_delta = 0.03  # how much the amounts can differ (as a fraction)
min_score = 0.5  # matches scoring below this are treated as coincidences (put with the other constants at the top)

# for each cash book node, filter bank statement nodes:
#     credit/debit
#     date (+- 30 days)
#     amount (+- 3%)
def is_candidate(ledger_e, bank_e):
    # Rule 1: type must be the same (debit with debit, credit with credit)
    if ledger_e["type"] == bank_e["type"]:
        return False  # different type, so this pair can never match

    # Rule 2: dates must be within 30 days of each other (this is a soft rule, so it can be relaxed if needed - consult an accountant for realistic value)
    # subtracting two dates gives a timedelta; .days is the gap, abs() ignores direction
    if abs((ledger_e["date"] - bank_e["date"]).days) > day_delta:
        return False  # too far apart in time

    # Rule 3: amounts must be within 3% of the bank amount
    # (this line is the last check, so it directly returns True or False)
    return abs(ledger_e["amount"] - bank_e["amount"]) <= amount_delta * bank_e["amount"]

def normalize(text):
    # lowercase first so "Mr. Ali" and "mr. ali" produce the same tokens
    tokens = tokenizer.tokenize(text.lower())
    # strip leading zeros from number tokens so "0007981" and "7981" become the same token
    tokens = [t.lstrip("0") if t.isdigit() else t for t in tokens]
    # return a set, because the overlap score needs intersection/union
    return set(tokens)

# assign scores using:
#     token similarity (normalize tokens then find intersection/union)
#     fuzzy string similarity using rapidfuzz library
#     date and amount match

def score(ledger_e, bank_e):

    # turn both descriptions into clean token sets using normalize()
    ledger_tokens = normalize(ledger_e["description"])
    bank_tokens = normalize(bank_e["description"])

    # token overlap = shared tokens / all distinct tokens, so it is always between 0 and 1
    union = ledger_tokens | bank_tokens
    # "if union else 0.0" avoids dividing by zero when both sets are empty
    token_score = len(ledger_tokens & bank_tokens) / len(union) if union else 0.0

    # join the sorted tokens back into one string so word order does not matter
    ledger_text = " ".join(sorted(ledger_tokens))
    bank_text = " ".join(sorted(bank_tokens))
    # fuzz.ratio gives 0-100 based on character-level similarity, so /100 puts it on a 0-1 scale
    fuzzy_score = fuzz.ratio(ledger_text, bank_text) / 100 

    # gap in days between the two dates; abs() ignores which date comes first
    days_apart = abs((ledger_e["date"] - bank_e["date"]).days)
    # 0 days apart gives 1.0, 30 days apart gives 0.0 (matches the 30-day filter in is_candidate)
    date_score = 1 - days_apart / day_delta

    # amount score: 1.0 for an exact match, falling to 0.0 at the edge of the 3% tolerance
    allowed = amount_delta * bank_e["amount"]  # the largest difference the filter lets through
    # "if allowed else 1.0" avoids dividing by zero when the ledger amount is 0
    amount_score = 1 - abs(ledger_e["amount"] - bank_e["amount"]) / allowed if allowed else 1.0

    # weights decide how much each score counts; they must add up to 1
    w_token, w_fuzzy, w_date, w_amount = 0.3, 0.2, 0.1, 0.4

    # final score = each score multiplied by its weight, then added up
    # since every score is 0-1 and the weights sum to 1, the result is also 0-1
    final_score = (w_token * token_score + w_fuzzy * fuzzy_score + w_date * date_score + w_amount * amount_score)

    return final_score  

# final matrix banjayegi (edges/scores and nodes)
def build_matrix(entries_bank, entries_ledger):
    # rows = bank entries, columns = ledger entries; every cell starts as -inf (no match possible)
    matrix = np.full((len(entries_bank), len(entries_ledger)), -math.inf)
    for i, bank_e in enumerate(entries_bank):
        for j, ledger_e in enumerate(entries_ledger):
            # only pairs that pass the candidate filter get a real score
            if is_candidate(ledger_e, bank_e):
                matrix[i][j] = score(ledger_e, bank_e)
    return matrix

# apply linear programming library to find best matches
def match_entries(matrix):
    # the library can't handle -inf, so swap it for a huge negative number
    safe = np.where(np.isinf(matrix), -1e9, matrix)
    # maximize=True because a higher score means a better match
    rows, cols = linear_sum_assignment(safe, maximize=True)
    # keep only pairs that sit on real scores; pairs on -inf cells were never candidates
    return [(i, j, matrix[i][j]) for i, j in zip(rows, cols) if matrix[i][j] != -math.inf]

# mark amount errors between nodes despite a good match
def split_by_amount(matches, entries_bank, entries_ledger):
    # sort best score first, so the weakest matches end up at the back of the list
    matches = sorted(matches, key=lambda m: m[2], reverse=True)
    exact, amount_errors = [], []
    for i, j, s in matches:
        # isclose avoids float noise; abs_tol=0.01 means "equal to the cent"
        if math.isclose(entries_bank[i]["amount"], entries_ledger[j]["amount"], abs_tol=0.01):
            exact.append((i, j, s))
        else:
            amount_errors.append((i, j, s))  # strong description match but amounts differ: likely a typo
    """
    print("Amount Errors")
    print(amount_errors)
    print("Exact")
    print(exact)
    """
    return exact, amount_errors

# based on a threshhold for score, mark nodes with low score in "exact" list as other mismatches
def threshold_cut(exact, min_score=min_score):
    # keep matches at or above the threshold; the rest are too weak to trust
    kept = [m for m in exact if m[2] >= min_score]
    # equal amounts but weak description/date match: probably unrelated payments of the same amount
    low_score = [m for m in exact if m[2] < min_score]
    return kept, low_score

# entries with no matches at all (nodes not in kept, amount_errors, or low_score)
def find_unmatched(entries_bank, entries_ledger, kept, amount_errors, low_score):
    # every pair from all three groups; an entry that appears in none of them was never paired
    paired = kept + amount_errors + low_score
    used_bank = {i for i, j, s in paired}
    used_ledger = {j for i, j, s in paired}
    unmatched_bank = [i for i in range(len(entries_bank)) if i not in used_bank]
    unmatched_ledger = [j for j in range(len(entries_ledger)) if j not in used_ledger]

    """
    print("Unmatched BANK")
    print(unmatched_bank)
    print("Unmatched Ledger")
    print(unmatched_ledger)
    """

    return unmatched_bank, unmatched_ledger

def reconcile(entries_bank, entries_ledger):
    # step 1: score every candidate pair (everything else stays -inf)
    matrix = build_matrix(entries_bank, entries_ledger)
    # step 2: let the library pick the best one-to-one pairing
    matches = match_entries(matrix)
    # step 3: sort by score and separate equal amounts from amount errors
    exact, amount_errors = split_by_amount(matches, entries_bank, entries_ledger)
    # step 4: drop weak matches from the exact list
    kept, low_score = threshold_cut(exact)
    unmatched_bank, unmatched_ledger = find_unmatched(entries_bank, entries_ledger, kept, amount_errors, low_score)
    return kept, low_score, amount_errors, unmatched_bank, unmatched_ledger