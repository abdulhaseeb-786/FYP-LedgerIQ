"""Text normalization, abbreviation expansion, and token similarity."""

import re
from typing import List, Set

ABBREVIATIONS = {
    "a/c": "account", "ac": "account", "acct": "account", "a/r": "receivable",
    "ar": "receivable", "a/p": "payable", "ap": "payable", "recv": "receivable",
    "recvble": "receivable", "rec": "receivable", "pybl": "payable",
    "exp": "expense", "exps": "expense", "expence": "expense", "expences": "expense",
    "expenses": "expense", "liab": "liability", "liabs": "liability",
    "liabilities": "liability", "dep": "depreciation", "depn": "depreciation",
    "depr": "depreciation", "amort": "amortisation", "amortization": "amortisation",
    "accum": "accumulated", "acc": "accumulated", "accumulted": "accumulated",
    "lt": "long term", "l/t": "long term", "st": "short term", "s/t": "short term",
    "fa": "fixed asset", "ppe": "property plant and equipment",
    "cos": "cost of sales", "cogs": "cost of goods sold",
    "p&l": "profit and loss", "pl": "profit and loss",
    "gst": "sales tax", "wht": "withholding tax", "pol": "fuel",
    "stationary": "stationery", "coorinator": "coordinator",
    "traveling": "travelling", "organisation": "organization",
    "recievable": "receivable", "payble": "payable", "creditor": "creditors",
    "debtor": "debtors", "inv": "investment", "misc": "miscellaneous",
    "admin": "administrative", "gen": "general", "mgmt": "management",
    "no": "", "nos": "", "sno": "", "srno": ""
}

STOPWORDS: Set[str] = {
    "the", "a", "an", "of", "for", "to", "and", "or", "in", "on", "at",
    "by", "with", "from", "as", "is", "total", "sub", "subtotal",
    "balance", "amount", "value", "less", "add"
}


def normalize_name(raw: str) -> str:
    """Normalize account title by removing codes, expanding abbreviations, and cleaning punctuation."""
    if not raw:
        return ""
    
    s = str(raw).strip()
    
    # Strip leading code like "1006-3 · " or "1001 - " or "1002 "
    s = re.sub(r'^\s*[\d\-]+[\s\.\·\-\:]+\s*', '', s)
    s = s.lower()
    
    # Normalize quotes and ampersands
    s = s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    s = s.replace('&', ' and ')
    
    # Keep '/' temporarily so abbreviations like a/c, a/r survive
    s = re.sub(r'[^a-z0-9/ ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    
    tokens = s.split(' ')
    expanded = []
    for token in tokens:
        if not token:
            continue
        if token in ABBREVIATIONS:
            replacement = ABBREVIATIONS[token]
            if replacement:
                expanded.append(replacement)
        else:
            expanded.append(token.replace('/', ' '))
            
    res = ' '.join(expanded)
    res = re.sub(r'\s+', ' ', res).strip()
    return res


def tokenize(normalized: str) -> List[str]:
    """Split normalized text into meaningful tokens without stopwords."""
    if not normalized:
        return []
    words = normalized.split(' ')
    return [w for w in words if w and w not in STOPWORDS and len(w) > 1]


def jaccard_similarity(tokens1: List[str], tokens2: List[str]) -> float:
    """Compute token Jaccard similarity."""
    set1, set2 = set(tokens1), set(tokens2)
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0


def bigram_dice_similarity(str1: str, str2: str) -> float:
    """Character bigram Dice coefficient for robust typo resilience."""
    if not str1 or not str2:
        return 0.0
    if str1 == str2:
        return 1.0
    
    bigrams1 = {str1[i:i+2] for i in range(len(str1) - 1)}
    bigrams2 = {str2[i:i+2] for i in range(len(str2) - 1)}
    
    if not bigrams1 or not bigrams2:
        return 0.0
        
    intersection = len(bigrams1.intersection(bigrams2))
    return (2.0 * intersection) / (len(bigrams1) + len(bigrams2))

