"""
Fund Performance Factors - Return and ranking metrics for fund recommendation.

Key factors:
- Return rankings (weekly, monthly)
- Risk-adjusted momentum
- Performance consistency
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime, timedelta

from src.data_sources.tushare_client import (
    get_fund_nav,
    format_date_yyyymmdd,
)


class PerformanceFactors:
    """
    Performance factor computation for funds.

    Uses NAV history to compute returns and rankings.
    """

    @classmethod
    def compute(cls, fund_code: str, trade_date: str) -> Dict:
        """
        Compute all performance factors for a fund.

        Args:
            fund_code: Fund code
            trade_date: Trade date in YYYYMMDD format

        Returns:
            Dict with performance factors
        """
        factors = {
            'return_1w': None,
            'return_1m': None,
            'return_3m': None,
            'return_6m': None,
            'return_1y': None,
            'return_rank_1w': None,
            'return_rank_1m': None,
        }

        try:
            # Get NAV data
            end_date = trade_date
            start_date = format_date_yyyymmdd(
                datetime.strptime(trade_date, '%Y%m%d') - timedelta(days=400)
            )

            ts_code = cls._normalize_fund_code(fund_code)
            nav_df = get_fund_nav(ts_code, start_date, end_date)

            if nav_df is None or nav_df.empty:
                return factors

            # Sort by date
            date_col = 'end_date' if 'end_date' in nav_df.columns else 'nav_date'
            nav_df = nav_df.sort_values(date_col)

            # Get NAV column
            nav_col = 'accum_nav' if 'accum_nav' in nav_df.columns else 'unit_nav'
            if nav_col not in nav_df.columns:
                nav_col = 'nav' if 'nav' in nav_df.columns else None

            if nav_col is None or len(nav_df) < 5:
                return factors

            # Current NAV - check for None/NaN
            current_nav_raw = nav_df[nav_col].iloc[-1]
            if current_nav_raw is None or pd.isna(current_nav_raw):
                return factors
            current_nav = float(current_nav_raw)

            # Calculate returns for different periods
            periods = {
                '1w': 5,
                '1m': 22,
                '3m': 66,
                '6m': 132,
                '1y': 252,
            }

            for period_name, days in periods.items():
                if len(nav_df) >= days:
                    past_nav_raw = nav_df[nav_col].iloc[-days]
                    if past_nav_raw is None or pd.isna(past_nav_raw) or past_nav_raw == 0:
                        continue
                    past_nav = float(past_nav_raw)
                    ret = (current_nav - past_nav) / past_nav * 100
                    factors[f'return_{period_name}'] = round(ret, 4)

            # Rankings would need to compare against other funds
            # This is a placeholder - actual ranking needs peer comparison
            factors['return_rank_1w'] = cls._estimate_rank(factors.get('return_1w'))
            factors['return_rank_1m'] = cls._estimate_rank(factors.get('return_1m'))

        except Exception as e:
            print(f"Error computing performance factors for {fund_code}: {e}")

        return factors

    @classmethod
    def _normalize_fund_code(cls, code: str) -> str:
        """Convert fund code to TuShare format."""
        if '.' in code:
            return code

        if code.startswith(('5', '1')):
            return f"{code}.SH"
        elif code.startswith(('15', '16')):
            return f"{code}.SZ"
        else:
            return f"{code}.OF"

    @classmethod
    def _estimate_rank(cls, return_pct: Optional[float]) -> Optional[float]:
        """
        Estimate percentile rank based on return.

        This is a rough estimate - actual ranking needs peer comparison.
        Assumes normal distribution of fund returns.
        """
        if return_pct is None:
            return None

        # Rough percentile mapping based on typical fund return distribution
        # These are approximations
        if return_pct >= 5:
            return 90 + min(10, (return_pct - 5) * 2)
        elif return_pct >= 2:
            return 70 + (return_pct - 2) * 6.67
        elif return_pct >= 0:
            return 50 + return_pct * 10
        elif return_pct >= -2:
            return 30 + (return_pct + 2) * 10
        else:
            return max(0, 30 + return_pct * 5)


def compute_performance_score(factors: Dict) -> float:
    """
    Compute overall performance score.

    Components:
    - 1-week return: 20%
    - 1-month return: 30%
    - 3-month return: 25%
    - Return rank: 25%

    Returns:
        Score 0-100 (higher = better recent performance)
    """
    score = 0
    weights = 0

    # 1-week return (20%)
    ret_1w = factors.get('return_1w')
    if ret_1w is not None:
        # Normalize: -5% = 0, 0% = 50, 5% = 100
        ret_score = 50 + (ret_1w * 10)
        ret_score = max(0, min(100, ret_score))
        score += ret_score * 0.20
        weights += 0.20

    # 1-month return (30%)
    ret_1m = factors.get('return_1m')
    if ret_1m is not None:
        # Normalize: -10% = 0, 0% = 50, 10% = 100
        ret_score = 50 + (ret_1m * 5)
        ret_score = max(0, min(100, ret_score))
        score += ret_score * 0.30
        weights += 0.30

    # 3-month return (25%)
    ret_3m = factors.get('return_3m')
    if ret_3m is not None:
        ret_score = 50 + (ret_3m * 2.5)
        ret_score = max(0, min(100, ret_score))
        score += ret_score * 0.25
        weights += 0.25

    # Return rank (25%)
    rank = factors.get('return_rank_1m')
    if rank is not None:
        score += rank * 0.25
        weights += 0.25

    if weights > 0:
        return round(score / weights * 100, 2)

    return 50.0
