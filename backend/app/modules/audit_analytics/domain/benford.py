"""ISA 240 Benford's Law First-Digit Distribution Engine.

Implements Nigrini standards for forensic accounting:
- Logarithmic probability distribution: P(d) = log10(1 + 1/d)
- Mean Absolute Deviation (MAD) conformity rating
- Pearson Chi-Square goodness-of-fit test (df = 8)
- Z-score per digit with continuity correction
"""

import math
from typing import List, Dict, Tuple, Optional
from app.modules.audit_analytics.domain.models import BenfordDigitStat, BenfordAnalysisResult

# Benford's Law theoretical first-digit distribution
BENFORD_THEORETICAL: Dict[int, float] = {
    d: math.log10(1.0 + 1.0 / d) for d in range(1, 10)
}

# Nigrini First-Digit Test MAD Thresholds
MAD_CLOSE_CONFORMITY = 0.006
MAD_ACCEPTABLE = 0.012
MAD_MARGINAL = 0.015


def extract_leading_digit(amount: float) -> Optional[int]:
    """Extract first non-zero leading digit from a positive numerical amount."""
    val = abs(amount)
    if val <= 0.0001 or math.isnan(val) or math.isinf(val):
        return None
    
    # Scale to single-digit integer range [1, 9]
    s = f"{val:.12f}".replace(".", "").lstrip("0")
    if not s:
        return None
    digit = int(s[0])
    return digit if 1 <= digit <= 9 else None


class BenfordAnalyzer:
    """Forensic Benford's Law distribution evaluator."""

    def __init__(self, critical_z_threshold: float = 2.576):
        """
        Args:
            critical_z_threshold: Critical value for individual digit flagging (default 2.576 = 99% confidence).
        """
        self.critical_z_threshold = critical_z_threshold

    def analyze(self, amounts: List[float]) -> BenfordAnalysisResult:
        """Run full Benford first-digit test on a collection of amounts."""
        counts = {d: 0 for d in range(1, 10)}
        total_valid = 0
        excluded = 0

        for a in amounts:
            digit = extract_leading_digit(a)
            if digit is not None:
                counts[digit] += 1
                total_valid += 1
            else:
                excluded += 1

        if total_valid < 50:
            # Below minimum sample size for reliable Benford statistical power
            stats = [
                BenfordDigitStat(
                    digit=d,
                    observed_count=counts[d],
                    observed_freq=(counts[d] / total_valid) if total_valid > 0 else 0.0,
                    expected_freq=BENFORD_THEORETICAL[d],
                    difference=0.0,
                    z_score=0.0,
                    is_anomaly=False,
                )
                for d in range(1, 10)
            ]
            return BenfordAnalysisResult(
                total_evaluated=len(amounts),
                excluded_zeros_or_negatives=excluded,
                mad=0.0,
                conformity_status="Sample Too Small",
                chi_square_stat=0.0,
                p_value=1.0,
                digits=stats,
                is_suspicious=False,
                summary=f"Sample size ({total_valid}) is too small for Benford distribution verification (minimum 50 required).",
            )

        n = float(total_valid)
        digit_stats: List[BenfordDigitStat] = []
        abs_diff_sum = 0.0
        chi_square_stat = 0.0
        flagged_digits = []

        for d in range(1, 10):
            obs_cnt = counts[d]
            obs_freq = obs_cnt / n
            exp_freq = BENFORD_THEORETICAL[d]
            diff = obs_freq - exp_freq
            abs_diff_sum += abs(diff)

            # Chi-square component: (O - E)^2 / E
            exp_cnt = n * exp_freq
            chi_square_stat += ((obs_cnt - exp_cnt) ** 2) / exp_cnt

            # Z-Score with continuity correction: (|obs_freq - exp_freq| - 1/(2N)) / sqrt(P*(1-P)/N)
            std_err = math.sqrt((exp_freq * (1.0 - exp_freq)) / n)
            continuity = 1.0 / (2.0 * n)
            num = max(0.0, abs(diff) - continuity)
            z_score = num / std_err if std_err > 0 else 0.0

            is_anomaly = (z_score >= self.critical_z_threshold) and (diff > 0)
            if is_anomaly:
                flagged_digits.append(d)

            digit_stats.append(
                BenfordDigitStat(
                    digit=d,
                    observed_count=obs_cnt,
                    observed_freq=round(obs_freq, 5),
                    expected_freq=round(exp_freq, 5),
                    difference=round(diff, 5),
                    z_score=round(z_score, 3),
                    is_anomaly=is_anomaly,
                )
            )

        mad = abs_diff_sum / 9.0

        # P-value calculation via scipy chi2 survival function
        try:
            from scipy.stats import chi2
            p_val = float(chi2.sf(chi_square_stat, df=8))
        except Exception:
            # Fallback approximation for chi2 p-value at df=8
            p_val = 0.001 if chi_square_stat > 26.12 else (0.05 if chi_square_stat > 15.51 else 0.50)

        # Conformity rating according to Nigrini standards
        if mad <= MAD_CLOSE_CONFORMITY:
            conformity = "Close Conformity"
            is_suspicious = False
        elif mad <= MAD_ACCEPTABLE:
            conformity = "Acceptable Conformity"
            is_suspicious = False
        elif mad <= MAD_MARGINAL:
            conformity = "Marginally Non-Conforming"
            is_suspicious = True
        else:
            conformity = "Non-Conforming (Audit Alert)"
            is_suspicious = True

        if flagged_digits:
            summary = (
                f"Ledger exhibits {conformity} (MAD = {mad:.4f}). "
                f"Significant unnatural upward spikes detected on digit(s): {flagged_digits} "
                f"(Chi^2 = {chi_square_stat:.2f}, p = {p_val:.4f})."
            )
        else:
            summary = (
                f"Ledger exhibits {conformity} (MAD = {mad:.4f}, Chi^2 = {chi_square_stat:.2f}, "
                f"p = {p_val:.4f}). Distribution aligns with natural accounting operations."
            )

        return BenfordAnalysisResult(
            total_evaluated=len(amounts),
            excluded_zeros_or_negatives=excluded,
            mad=round(mad, 5),
            conformity_status=conformity,
            chi_square_stat=round(chi_square_stat, 3),
            p_value=round(p_val, 5),
            digits=digit_stats,
            is_suspicious=is_suspicious,
            summary=summary,
        )
