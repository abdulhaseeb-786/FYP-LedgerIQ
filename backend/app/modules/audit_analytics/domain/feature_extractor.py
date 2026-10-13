"""Feature Extraction Pipeline for Machine Learning Anomaly Detection on GL Transactions."""

import math
from typing import List, Dict, Any, Tuple
from datetime import datetime
from app.modules.audit_analytics.domain.models import GLTransactionRecord

# Standard accounting threshold boundaries (internal audit authorization limits)
APPROVAL_THRESHOLDS = [25000.0, 50000.0, 100000.0, 500000.0]


class GLFeatureExtractor:
    """Converts raw accounting transactions into numerical feature matrices for Isolation Forest."""

    FEATURE_NAMES = [
        "log_amount",
        "is_round_1k",
        "is_round_10k",
        "is_weekend",
        "is_month_end",
        "is_off_hours",
        "threshold_proximity_score",
        "is_suspense_account",
        "is_admin_override",
    ]

    def extract_features(self, transactions: List[GLTransactionRecord]) -> Tuple[List[List[float]], List[Dict[str, Any]]]:
        """
        Transforms transactions into a 2D numerical matrix and metadata descriptions.

        Returns:
            matrix: 2D list of floats of shape (n_transactions, n_features)
            heuristics_metadata: list of dicts capturing raw heuristic indicators for explainability
        """
        matrix: List[List[float]] = []
        heuristics_metadata: List[Dict[str, Any]] = []

        for tx in transactions:
            amt = abs(tx.net_amount) if tx.net_amount != 0.0 else max(tx.debit, tx.credit)
            dt = tx.date if isinstance(tx.date, datetime) else datetime.now()

            # 1. Log-magnitude
            log_amt = math.log(amt + 1.0) if amt > 0 else 0.0

            # 2. Round numbers
            is_round_1k = 1.0 if (amt >= 1000.0 and abs(amt % 1000.0) < 0.01) else 0.0
            is_round_10k = 1.0 if (amt >= 10000.0 and abs(amt % 10000.0) < 0.01) else 0.0

            # 3. Temporal indicators
            is_weekend = 1.0 if dt.weekday() in (5, 6) else 0.0
            is_month_end = 1.0 if dt.day >= 28 else 0.0
            has_explicit_time = (dt.hour != 0 or dt.minute != 0 or dt.second != 0)
            is_off_hours = 1.0 if (has_explicit_time and (dt.hour < 8 or dt.hour >= 19)) else 0.0

            # 4. Approval threshold proximity (smurfing / invoice splitting within 5% below limits)
            prox_score = 0.0
            for thresh in APPROVAL_THRESHOLDS:
                if 0.95 * thresh <= amt < thresh:
                    prox_score = 1.0 - ((thresh - amt) / (0.05 * thresh))
                    break

            # 5. Account nature & User roles
            name_lower = (tx.account_name or "").lower()
            code_lower = str(tx.account_code or "").lower()
            is_suspense = 1.0 if any(k in name_lower for k in ["suspense", "clearing", "adjustment", "unallocated"]) or code_lower in ["9999", "9998"] else 0.0
            
            user_lower = (tx.user_id or "").lower()
            is_admin = 1.0 if any(k in user_lower for k in ["mgr", "admin", "director", "override", "root"]) else 0.0

            row_features = [
                log_amt,
                is_round_1k,
                is_round_10k,
                is_weekend,
                is_month_end,
                is_off_hours,
                prox_score,
                is_suspense,
                is_admin,
            ]
            matrix.append(row_features)

            # Heuristics tags for auditor explainability
            tags = []
            if is_round_10k > 0 and amt >= 50000.0:
                tags.append("Large Round Amount (multiple of 10,000)")
            elif is_round_1k > 0 and amt >= 25000.0 and (is_weekend > 0 or is_off_hours > 0):
                tags.append("Round Amount Posted Outside Normal Hours")
            if is_weekend > 0:
                tags.append("Weekend Posting (Saturday/Sunday)")
            if is_off_hours > 0:
                tags.append("Off-Hours Posting (outside 8 AM - 7 PM)")
            if prox_score > 0:
                tags.append("Proximity to Internal Approval Limit (Potential Splitting)")
            if is_suspense > 0:
                tags.append("Posting to Suspense / Clearing Account")
            if is_admin > 0 and (is_weekend > 0 or is_off_hours > 0):
                tags.append("Off-Hours Override by Administrative Account")

            heuristics_metadata.append({
                "tags": tags,
                "amount": amt,
                "date": dt,
            })

        return matrix, heuristics_metadata
