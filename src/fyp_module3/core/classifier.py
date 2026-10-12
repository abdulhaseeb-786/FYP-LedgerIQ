"""Account classification engine mapping raw ledger accounts to Fifth Schedule taxonomy."""

from typing import List, Tuple
from fyp_module3.core.models import StandardizedAccountRecord, ClassificationResult
from fyp_module3.core.taxonomy import (
    get_line_items, get_line_item, SUSPENSE_DR_ID, SUSPENSE_CR_ID,
)
from fyp_module3.core.normalizer import normalize_name, tokenize, jaccard_similarity, bigram_dice_similarity


class AccountClassifier:
    """Classifies trial balance accounts into Fifth Schedule statement line items."""

    def __init__(self, confidence_threshold: float = 0.70):
        self.confidence_threshold = confidence_threshold
        self.line_items = get_line_items()
        
        # Build normalized alias index: (alias, line_item_id, item_dict)
        self.alias_index: List[Tuple[str, str, dict]] = []
        for item in self.line_items:
            for alias in item.get("aliases", []):
                norm_alias = normalize_name(alias)
                if norm_alias:
                    self.alias_index.append((norm_alias, item["id"], item))

    def classify_account(self, account: StandardizedAccountRecord) -> ClassificationResult:
        """Classify a single account record with strict accounting polarity protection."""
        raw_name = account.account_name
        norm_name = normalize_name(raw_name)
        tokens = tokenize(norm_name)
        # Derive the side from the balances themselves rather than from
        # net_balance, which callers are not obliged to keep in step.
        is_debit = (account.debit - account.credit) > 0

        # -------------------------------------------------------------
        # Layer 0: Accountant Rule Heuristics (High Priority Overrides)
        # -------------------------------------------------------------
        # 1. Pre-closed Current Year Profit / Loss summary account
        if any(term in norm_name for term in ["current year profit", "current year loss", "profit for the year", "loss for the year", "current year profit loss"]):
            item = get_line_item("sofp.eq.cy_profit_summary")
            if item:
                return self._build_result(account, item, confidence=0.99, source="exact")

        # 2. Allowance for ECL / Doubtful Debts (Contra-asset)
        if any(term in norm_name for term in ["allowance for expected credit loss", "expected credit loss", "allowance for doubtful", "allowance for bad debts", "provision for doubtful debts", "ecl allowance"]):
            item = get_line_item("sofp.ca.allowance_ecl") or get_line_item("sofp.ca.debtors")
            if item:
                return self._build_result(account, item, confidence=0.99, source="exact")

        # 3. Sales Returns and Discounts (Contra-revenue)
        if any(term in norm_name for term in ["sales returns", "sales return", "returns inward", "sales discount"]):
            item = get_line_item("pl.salesreturns")
            if item:
                return self._build_result(account, item, confidence=0.99, source="exact")

        # 4. Directors' Current Account / Loans (Credit -> Liability, not Cash!)
        if "director" in norm_name and any(term in norm_name for term in ["current account", "loan", "current a/c"]):
            item = get_line_item("sofp.ncl.directorloan") if not is_debit else get_line_item("sofp.ca.advances")
            if item:
                return self._build_result(account, item, confidence=0.95, source="heuristic")

        # 5. Liabilities with "accrued", "payable", "obligation", "provision"
        # Must NEVER be mapped to P&L expense if balance is Credit!
        is_liability_keyword = any(kw in tokens or kw in norm_name for kw in ["accrued", "payable", "obligation", "liability", "liabilities", "provision"])
        if is_liability_keyword and not is_debit:
            # Check specific liabilities using tokens to avoid "rent" in "current"
            if any(k in tokens for k in ["salaries", "salary", "utilities", "utility", "markup", "interest", "rent", "wages"]):
                item = get_line_item("sofp.cl.accrued")
                if item:
                    return self._build_result(account, item, confidence=0.95, source="heuristic")
            elif any(k in tokens or k in norm_name for k in ["gratuity", "employee benefit", "pension"]):
                item = get_line_item("sofp.ncl.ltprov")
                if item:
                    return self._build_result(account, item, confidence=0.95, source="heuristic")
            elif any(k in tokens or k in norm_name for k in ["dividend", "unclaimed dividend"]):
                item = get_line_item("sofp.cl.unclaimeddiv")
                if item:
                    return self._build_result(account, item, confidence=0.95, source="heuristic")
            elif any(k in tokens or k in norm_name for k in ["lease", "ijarah"]):
                is_non_curr = "non" in tokens or "long" in tokens or "non current" in norm_name
                item = get_line_item("sofp.ncl.lease") if is_non_curr else get_line_item("sofp.cl.lease")
                if item:
                    return self._build_result(account, item, confidence=0.95, source="heuristic")
            elif any(k in tokens for k in ["taxation", "tax"]):
                item = get_line_item("sofp.cl.provtax")
                if item:
                    return self._build_result(account, item, confidence=0.95, source="heuristic")

        # -------------------------------------------------------------
        # Layer 1: Exact Match on Normalized Name
        # -------------------------------------------------------------
        exact_matches = [
            (item_id, item) for (alias, item_id, item) in self.alias_index
            if alias == norm_name
        ]
        if exact_matches:
            best_id, best_item = self._disambiguate_side(exact_matches, is_debit)
            return self._build_result(account, best_item, confidence=0.98, source="exact")

        # -------------------------------------------------------------
        # Layer 2: Substring & Token Containment Match
        # -------------------------------------------------------------
        # Candidates whose name matches well but whose balance sits on the
        # opposite side. These are recorded rather than discarded: a name that
        # clearly reads as an expense but carries a credit balance is a
        # suspected posting error, not an invitation to match something else.
        polarity_conflicts: List[str] = []

        containment_matches = []
        for alias, item_id, item in self.alias_index:
            # Full alias inside account name or vice versa
            if (alias in norm_name or norm_name in alias) and len(alias) >= 4:
                # Do not map credit accounts to expenses via loose containment!
                if not is_debit and item["stmt"] == "PL" and item.get("natural") == "DR":
                    polarity_conflicts.append(item["label"])
                    continue
                # Do not map debit accounts to liabilities via loose containment
                if is_debit and item["stmt"] == "SOFP" and item.get("section") in ("Current liabilities", "Non-current liabilities", "Share capital and reserves") and not item.get("contra_of"):
                    polarity_conflicts.append(item["label"])
                    continue

                base_score = min(0.94, len(alias) / max(len(norm_name), len(alias)))
                if (item.get("natural") == "DR") == is_debit:
                    base_score += 0.10
                containment_matches.append((base_score, item_id, item))

        if containment_matches:
            containment_matches.sort(key=lambda x: x[0], reverse=True)
            top_score = containment_matches[0][0]
            top_candidates = [(item_id, item) for (score, item_id, item) in containment_matches if score >= top_score - 0.15]
            best_id, best_item = self._disambiguate_side(top_candidates, is_debit)
            # Containment is a strong signal but it is not an exact match, and
            # labelling it "exact" misreports how the mapping was reached.
            return self._build_result(account, best_item,
                                      confidence=round(min(0.95, top_score), 2),
                                      source="heuristic")

        # -------------------------------------------------------------
        # Layer 3: Fuzzy Token & Character Similarity
        # -------------------------------------------------------------
        fuzzy_candidates = []
        for alias, item_id, item in self.alias_index:
            # Polarity guard for fuzzy matches
            if not is_debit and item["stmt"] == "PL" and item.get("natural") == "DR":
                if bigram_dice_similarity(norm_name, alias) > 0.75:
                    polarity_conflicts.append(item["label"])
                continue

            alias_tokens = tokenize(alias)
            j_score = jaccard_similarity(tokens, alias_tokens)
            d_score = bigram_dice_similarity(norm_name, alias)
            combined_score = 0.5 * j_score + 0.5 * d_score

            # Side agreement bonus
            item_natural_is_dr = item.get("natural") == "DR"
            if item_natural_is_dr == is_debit:
                combined_score += 0.10

            if combined_score > 0.40:
                fuzzy_candidates.append((combined_score, item_id, item))

        if fuzzy_candidates:
            fuzzy_candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_id, best_item = fuzzy_candidates[0]
            confidence = min(0.92, round(best_score, 2))
            # A weak fuzzy hit is a guess. Accepting it silently is how a
            # credit-side expense ends up presented as an accrued liability
            # and profit is overstated, so anything under the threshold is
            # parked in suspense and reported instead.
            if confidence >= self.confidence_threshold:
                return self._build_result(account, best_item, confidence=confidence, source="fuzzy")
            polarity_conflicts.append(
                f"{best_item['label']} (best match, {confidence * 100:.0f}% confidence)"
            )

        # -------------------------------------------------------------
        # Layer 4: Suspense Fallback
        # -------------------------------------------------------------
        # Nothing recognised this account. Routing it to administrative
        # expenses (debit) or trade payables (credit) - as an earlier revision
        # did - silently moves reported profit and hides the failure, so an
        # unclassified balance is parked in suspense and reported instead.
        suspense_id = SUSPENSE_DR_ID if is_debit else SUSPENSE_CR_ID
        default_item = get_line_item(suspense_id) or self.line_items[0]

        if polarity_conflicts:
            reason = (
                f"closest candidate was '{polarity_conflicts[0]}', which is not a safe "
                f"mapping for a {'debit' if is_debit else 'credit'} balance"
            )
        else:
            reason = "account title did not match any Fifth Schedule line item"

        result = self._build_result(account, default_item, confidence=0.0, source="default")
        result.unclassified_reason = reason
        return result

    def _disambiguate_side(self, candidates: List[Tuple[str, dict]], is_debit: bool) -> Tuple[str, dict]:
        """Select candidate that matches the debit/credit nature."""
        matching = []
        for item_id, item in candidates:
            item_natural = item.get("natural", "DR")
            if (item_natural == "DR" and is_debit) or (item_natural == "CR" and not is_debit):
                matching.append((item_id, item))
        if matching:
            return matching[0]
        return candidates[0]

    def _build_result(self, account: StandardizedAccountRecord, item: dict, confidence: float, source: str) -> ClassificationResult:
        return ClassificationResult(
            account_name=account.account_name,
            line_item_id=item["id"],
            statement=item["stmt"],
            section=item["section"],
            label=item["label"],
            note_number=item.get("note_number"),
            confidence=confidence,
            source=source
        )

    def classify_all(self, accounts: List[StandardizedAccountRecord]) -> List[ClassificationResult]:
        """Classify a list of standardized account records and update in-place."""
        results = []
        for acc in accounts:
            res = self.classify_account(acc)
            acc.line_item_id = res.line_item_id
            acc.note_number = res.note_number
            acc.confidence = res.confidence
            acc.classification_source = res.source
            if res.unclassified_reason:
                acc.adjustment_reason = f"Unclassified: {res.unclassified_reason}"
            results.append(res)
        return results
