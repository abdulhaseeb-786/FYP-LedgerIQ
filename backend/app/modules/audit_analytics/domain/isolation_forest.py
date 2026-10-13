"""Unsupervised Isolation Forest Anomaly Detector for Accounting General Ledgers."""

from typing import List, Dict, Any, Optional
import numpy as np
from app.modules.audit_analytics.domain.models import (
    GLTransactionRecord,
    FlaggedTransaction,
    IsolationForestReport,
)
from app.modules.audit_analytics.domain.feature_extractor import GLFeatureExtractor

DEFAULT_CONTAMINATION = 0.03  # Expect ~3% anomalous or high-risk entries in a standard enterprise ledger


class GLIsolationForestDetector:
    """Detects multi-attribute outliers and fraud patterns in general ledger entries."""

    def __init__(self, contamination: float = DEFAULT_CONTAMINATION, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.feature_extractor = GLFeatureExtractor()

    def detect_anomalies(self, transactions: List[GLTransactionRecord]) -> IsolationForestReport:
        """Fit Isolation Forest on transaction feature matrix and score every transaction."""
        n = len(transactions)
        if n < 10:
            return IsolationForestReport(
                total_evaluated=n,
                total_flagged=0,
                contamination_rate=self.contamination,
                high_risk_entries=[],
                summary_verdict=f"Insufficient transactions ({n}) to train Isolation Forest (minimum 10 required).",
            )

        X, metadata = self.feature_extractor.extract_features(transactions)
        X_arr = np.array(X, dtype=float)

        from sklearn.ensemble import IsolationForest

        # Calibrate contamination rate to dataset size
        effective_contamination = min(max(self.contamination, 0.01), 0.15)
        model = IsolationForest(
            n_estimators=150,
            contamination=effective_contamination,
            random_state=self.random_state,
            n_jobs=-1,
        )
        model.fit(X_arr)

        raw_scores = model.decision_function(X_arr)  # Lower is more anomalous
        preds = model.predict(X_arr)                 # -1 for anomaly, 1 for inlier

        min_s = float(np.min(raw_scores))
        max_s = float(np.max(raw_scores))
        range_s = (max_s - min_s) if (max_s - min_s) > 1e-6 else 1.0

        flagged_entries: List[FlaggedTransaction] = []

        for idx, tx in enumerate(transactions):
            score = raw_scores[idx]
            pred = preds[idx]
            meta = metadata[idx]
            heuristic_tags = meta["tags"]

            # Normalized severity score in [0.0, 1.0] where 1.0 is most anomalous
            severity = (max_s - score) / range_s

            # An entry is anomalous if Isolation Forest explicitly flags it (-1) or has an audit red flag
            has_heuristic_flag = len(heuristic_tags) >= 1
            is_anomaly = (pred == -1) or has_heuristic_flag

            if is_anomaly:
                if (pred == -1 and len(heuristic_tags) >= 2) or (severity >= 0.90 and any("Weekend" in t for t in heuristic_tags)):
                    risk_level = "CRITICAL"
                elif (pred == -1 and has_heuristic_flag) or len(heuristic_tags) >= 2:
                    risk_level = "HIGH"
                elif pred == -1 and severity >= 0.80:
                    risk_level = "MEDIUM"
                else:
                    risk_level = "LOW"

                reasons = list(heuristic_tags)
                if not reasons:
                    reasons.append("Multi-dimensional feature distribution outlier isolated by ML model")

                flagged_entries.append(
                    FlaggedTransaction(
                        row_index=tx.row_index,
                        voucher_no=tx.voucher_no,
                        date=tx.date,
                        account_code=tx.account_code,
                        account_name=tx.account_name,
                        amount=meta["amount"],
                        anomaly_score=round(severity, 3),
                        risk_level=risk_level,
                        reasons=reasons,
                        user_id=tx.user_id,
                    )
                )

        # Sort flagged entries in descending order of severity
        flagged_entries.sort(key=lambda item: item.anomaly_score, reverse=True)

        critical_count = sum(1 for e in flagged_entries if e.risk_level in ("CRITICAL", "HIGH"))
        if critical_count > 0:
            summary = (
                f"Isolation Forest identified {len(flagged_entries)} anomalous transactions "
                f"({critical_count} critical/high risk). Top risks include weekend overrides, "
                f"round-sum management adjustments, and approval-limit smurfing."
            )
        elif len(flagged_entries) > 0:
            summary = (
                f"Identified {len(flagged_entries)} low-to-medium risk postings within normal business tolerances."
            )
        else:
            summary = "No anomalous postings detected. All general ledger entries conform to expected patterns."

        return IsolationForestReport(
            total_evaluated=n,
            total_flagged=len(flagged_entries),
            contamination_rate=effective_contamination,
            high_risk_entries=flagged_entries,
            summary_verdict=summary,
        )
