"""
Risk Metrics Module

Provides comprehensive risk analysis including:
- Sharpe Ratio: Risk-adjusted returns
- Max Drawdown: Historical worst loss
- Annual Volatility: Return variability
- Calmar Ratio: Return / Max Drawdown
- Drawdown History: Detailed drawdown periods analysis
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple


class RiskMetricsCalculator:
    """
    Calculator for fund risk metrics.
    """

    # Risk-free rate (annual, can be configured)
    RISK_FREE_RATE = 0.02  # 2%

    def __init__(self, risk_free_rate: float = 0.02):
        self.risk_free_rate = risk_free_rate

    def calculate_all_metrics(self, nav_history: List[Dict],
                              benchmark_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Calculate all risk metrics for a fund.

        Args:
            nav_history: List of {date, value} NAV history
            benchmark_history: Optional benchmark index history for comparison

        Returns:
            Dictionary with all risk metrics
        """
        if not nav_history or len(nav_history) < 20:
            return self._empty_metrics("Insufficient NAV history data")

        # Convert to DataFrame
        df = pd.DataFrame(nav_history)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(subset=['value'])

        if len(df) < 20:
            return self._empty_metrics("Insufficient valid NAV data")

        # Calculate daily returns
        df['return'] = df['value'].pct_change()
        daily_returns = df['return'].dropna()

        # Calculate metrics
        metrics = {
            'sharpe_ratio': self._calc_sharpe_ratio(daily_returns),
            'max_drawdown': self._calc_max_drawdown(df),
            'annual_volatility': self._calc_annual_volatility(daily_returns),
            'calmar_ratio': None,  # Will be calculated after max_drawdown
            'sortino_ratio': self._calc_sortino_ratio(daily_returns),
            'annual_return': self._calc_annual_return(df),
            'total_return': self._calc_total_return(df),
            'var_95': self._calc_var(daily_returns, 0.95),
            'var_99': self._calc_var(daily_returns, 0.99),
            'win_rate': self._calc_win_rate(daily_returns),
        }

        # Calculate Calmar ratio
        if metrics['max_drawdown']['value'] != 0:
            metrics['calmar_ratio'] = round(
                metrics['annual_return']['value'] / abs(metrics['max_drawdown']['value']),
                2
            )
        else:
            metrics['calmar_ratio'] = None

        # Add period info
        metrics['period'] = {
            'start_date': df['date'].iloc[0].strftime('%Y-%m-%d'),
            'end_date': df['date'].iloc[-1].strftime('%Y-%m-%d'),
            'trading_days': len(df),
        }

        metrics['computed_at'] = datetime.now().isoformat()

        return metrics

    def _calc_sharpe_ratio(self, daily_returns: pd.Series) -> Dict:
        """Calculate annualized Sharpe ratio."""
        try:
            annual_return = daily_returns.mean() * 252
            annual_vol = daily_returns.std() * np.sqrt(252)

            if annual_vol == 0:
                sharpe = 0
            else:
                sharpe = (annual_return - self.risk_free_rate) / annual_vol

            # Rating based on Sharpe
            if sharpe >= 2:
                rating = 'excellent'
            elif sharpe >= 1:
                rating = 'good'
            elif sharpe >= 0.5:
                rating = 'average'
            elif sharpe >= 0:
                rating = 'below_average'
            else:
                rating = 'poor'

            return {
                'value': round(sharpe, 3),
                'rating': rating,
                'description': '夏普比率衡量每单位风险所获得的超额收益'
            }
        except Exception as e:
            return {'value': 0, 'rating': 'unknown', 'error': str(e)}

    def _calc_max_drawdown(self, df: pd.DataFrame) -> Dict:
        """Calculate maximum drawdown."""
        try:
            cummax = df['value'].cummax()
            drawdown = (df['value'] - cummax) / cummax
            max_dd = drawdown.min()
            max_dd_idx = drawdown.idxmin()

            # Find peak before max drawdown
            peak_idx = df.loc[:max_dd_idx, 'value'].idxmax()

            # Find recovery point after max drawdown
            peak_value = df.loc[peak_idx, 'value']
            recovery_idx = None
            if max_dd_idx < len(df) - 1:
                recovery_mask = df.loc[max_dd_idx:, 'value'] >= peak_value
                if recovery_mask.any():
                    recovery_idx = recovery_mask.idxmax()

            recovery_days = None
            if recovery_idx is not None:
                recovery_days = recovery_idx - max_dd_idx

            # Rating based on max drawdown
            max_dd_pct = abs(max_dd) * 100
            if max_dd_pct < 10:
                rating = 'excellent'
            elif max_dd_pct < 20:
                rating = 'good'
            elif max_dd_pct < 30:
                rating = 'average'
            elif max_dd_pct < 40:
                rating = 'below_average'
            else:
                rating = 'poor'

            return {
                'value': round(max_dd_pct, 2),
                'peak_date': df.loc[peak_idx, 'date'].strftime('%Y-%m-%d'),
                'trough_date': df.loc[max_dd_idx, 'date'].strftime('%Y-%m-%d'),
                'recovery_date': df.loc[recovery_idx, 'date'].strftime('%Y-%m-%d') if recovery_idx else None,
                'recovery_days': int(recovery_days) if recovery_days else None,
                'rating': rating,
                'description': '最大回撤是基金历史最大亏损幅度'
            }
        except Exception as e:
            return {'value': 0, 'rating': 'unknown', 'error': str(e)}

    def _calc_annual_volatility(self, daily_returns: pd.Series) -> Dict:
        """Calculate annualized volatility."""
        try:
            annual_vol = daily_returns.std() * np.sqrt(252) * 100

            # Rating based on volatility
            if annual_vol < 10:
                rating = 'excellent'
            elif annual_vol < 15:
                rating = 'good'
            elif annual_vol < 20:
                rating = 'average'
            elif annual_vol < 25:
                rating = 'below_average'
            else:
                rating = 'poor'

            return {
                'value': round(annual_vol, 2),
                'rating': rating,
                'description': '年化波动率衡量基金净值的波动程度'
            }
        except Exception as e:
            return {'value': 0, 'rating': 'unknown', 'error': str(e)}

    def _calc_sortino_ratio(self, daily_returns: pd.Series) -> Dict:
        """Calculate Sortino ratio (only penalizes downside volatility)."""
        try:
            annual_return = daily_returns.mean() * 252
            downside_returns = daily_returns[daily_returns < 0]
            downside_vol = downside_returns.std() * np.sqrt(252)

            if downside_vol == 0:
                sortino = 0
            else:
                sortino = (annual_return - self.risk_free_rate) / downside_vol

            return {
                'value': round(sortino, 3),
                'description': '索提诺比率只考虑下行风险,更适合评估防守能力'
            }
        except Exception as e:
            return {'value': 0, 'error': str(e)}

    def _calc_annual_return(self, df: pd.DataFrame) -> Dict:
        """Calculate annualized return."""
        try:
            total_days = len(df)
            total_return = df['value'].iloc[-1] / df['value'].iloc[0] - 1
            annual_return = (1 + total_return) ** (252 / total_days) - 1

            return {
                'value': round(annual_return * 100, 2),
                'description': '年化收益率是将收益率折算为年度收益'
            }
        except Exception as e:
            return {'value': 0, 'error': str(e)}

    def _calc_total_return(self, df: pd.DataFrame) -> Dict:
        """Calculate total return."""
        try:
            total_return = (df['value'].iloc[-1] / df['value'].iloc[0] - 1) * 100
            return {
                'value': round(total_return, 2),
                'description': '期间总收益率'
            }
        except Exception as e:
            return {'value': 0, 'error': str(e)}

    def _calc_var(self, daily_returns: pd.Series, confidence: float) -> Dict:
        """Calculate Value at Risk."""
        try:
            var = np.percentile(daily_returns, (1 - confidence) * 100) * 100
            return {
                'value': round(var, 3),
                'confidence': confidence,
                'description': f'VaR {int(confidence*100)}%: 有{int(confidence*100)}%概率单日亏损不超过此值'
            }
        except Exception as e:
            return {'value': 0, 'error': str(e)}

    def _calc_win_rate(self, daily_returns: pd.Series) -> Dict:
        """Calculate win rate (positive return days percentage)."""
        try:
            win_rate = (daily_returns > 0).sum() / len(daily_returns) * 100
            return {
                'value': round(win_rate, 2),
                'description': '正收益交易日占比'
            }
        except Exception as e:
            return {'value': 0, 'error': str(e)}

    def _empty_metrics(self, reason: str) -> Dict:
        """Return empty metrics when data is insufficient."""
        return {
            'sharpe_ratio': {'value': None, 'rating': 'unknown'},
            'max_drawdown': {'value': None, 'rating': 'unknown'},
            'annual_volatility': {'value': None, 'rating': 'unknown'},
            'calmar_ratio': None,
            'error': reason,
            'computed_at': datetime.now().isoformat(),
        }


class DrawdownAnalyzer:
    """
    Analyzer for detailed drawdown history.
    """

    def __init__(self, threshold: float = 0.05):
        """
        Initialize with drawdown threshold.

        Args:
            threshold: Minimum drawdown to consider significant (default 5%)
        """
        self.threshold = threshold

    def analyze_drawdowns(self, nav_history: List[Dict]) -> Dict[str, Any]:
        """
        Analyze all significant drawdown periods.

        Args:
            nav_history: List of {date, value} NAV history

        Returns:
            Dictionary with drawdown analysis
        """
        if not nav_history or len(nav_history) < 20:
            return self._empty_analysis("Insufficient NAV history data")

        # Convert to DataFrame
        df = pd.DataFrame(nav_history)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(subset=['value'])

        if len(df) < 20:
            return self._empty_analysis("Insufficient valid NAV data")

        # Calculate drawdown series
        cummax = df['value'].cummax()
        drawdown = (df['value'] - cummax) / cummax
        df['drawdown'] = drawdown

        # Find drawdown periods
        periods = self._find_drawdown_periods(df)

        # Calculate current drawdown
        current_dd = drawdown.iloc[-1]
        current_dd_pct = abs(current_dd) * 100

        # Calculate statistics
        if periods:
            avg_drawdown = np.mean([p['drawdown'] for p in periods])
            avg_duration = np.mean([p['duration'] for p in periods])
            avg_recovery = np.mean([p['recovery_days'] for p in periods if p['recovery_days']])
        else:
            avg_drawdown = 0
            avg_duration = 0
            avg_recovery = 0

        # Find max drawdown period
        max_dd_period = None
        if periods:
            max_dd_period = max(periods, key=lambda x: abs(x['drawdown']))

        return {
            'current_drawdown': round(current_dd_pct, 2),
            'is_in_drawdown': current_dd < -self.threshold,
            'max_drawdown': {
                'value': round(abs(drawdown.min()) * 100, 2),
                'period': max_dd_period
            },
            'periods': periods,
            'statistics': {
                'total_periods': len(periods),
                'avg_drawdown': round(avg_drawdown, 2),
                'avg_duration_days': round(avg_duration, 1),
                'avg_recovery_days': round(avg_recovery, 1) if avg_recovery else None,
            },
            'drawdown_series': self._get_drawdown_series(df),
            'computed_at': datetime.now().isoformat(),
        }

    def _find_drawdown_periods(self, df: pd.DataFrame) -> List[Dict]:
        """Find all significant drawdown periods."""
        periods = []
        in_drawdown = False
        peak_idx = 0
        trough_idx = 0
        trough_value = 0

        for i, row in df.iterrows():
            dd = row['drawdown']

            if not in_drawdown:
                if dd < -self.threshold:
                    # Start of new drawdown period
                    in_drawdown = True
                    # Find peak (last point before drawdown started)
                    peak_idx = df.loc[:i, 'value'].idxmax()
                    trough_idx = i
                    trough_value = dd
                else:
                    # Update potential peak
                    if df.loc[i, 'value'] == df.loc[:i, 'value'].max():
                        peak_idx = i
            else:
                if dd < trough_value:
                    # Deeper drawdown
                    trough_idx = i
                    trough_value = dd
                elif dd >= 0:
                    # Recovered - end of drawdown period
                    recovery_idx = i

                    period = {
                        'start_date': df.loc[peak_idx, 'date'].strftime('%Y-%m-%d'),
                        'trough_date': df.loc[trough_idx, 'date'].strftime('%Y-%m-%d'),
                        'recovery_date': df.loc[recovery_idx, 'date'].strftime('%Y-%m-%d'),
                        'drawdown': round(abs(trough_value) * 100, 2),
                        'duration': int(trough_idx - peak_idx),
                        'recovery_days': int(recovery_idx - trough_idx),
                        'total_days': int(recovery_idx - peak_idx),
                    }
                    periods.append(period)
                    in_drawdown = False
                    peak_idx = i

        # Handle ongoing drawdown
        if in_drawdown:
            period = {
                'start_date': df.loc[peak_idx, 'date'].strftime('%Y-%m-%d'),
                'trough_date': df.loc[trough_idx, 'date'].strftime('%Y-%m-%d'),
                'recovery_date': None,
                'drawdown': round(abs(trough_value) * 100, 2),
                'duration': int(trough_idx - peak_idx),
                'recovery_days': None,
                'total_days': None,
                'is_ongoing': True,
            }
            periods.append(period)

        return periods

    def _get_drawdown_series(self, df: pd.DataFrame, sample_rate: int = 5) -> List[Dict]:
        """Get drawdown series for charting (sampled for performance)."""
        # Sample every N points for large datasets
        if len(df) > 500:
            sampled = df.iloc[::sample_rate].copy()
        else:
            sampled = df.copy()

        return [
            {
                'date': row['date'].strftime('%Y-%m-%d'),
                'drawdown': round(row['drawdown'] * 100, 2),
                'value': round(row['value'], 4)
            }
            for _, row in sampled.iterrows()
        ]

    def _empty_analysis(self, reason: str) -> Dict:
        """Return empty analysis when data is insufficient."""
        return {
            'current_drawdown': 0,
            'is_in_drawdown': False,
            'max_drawdown': {'value': 0, 'period': None},
            'periods': [],
            'statistics': {},
            'drawdown_series': [],
            'error': reason,
            'computed_at': datetime.now().isoformat(),
        }
