"""
Fund Diagnosis Module

Provides five-dimension scoring and radar chart data for fund analysis.
Dimensions:
1. Profitability (盈利能力): Based on 1Y/3Y returns percentile ranking
2. Risk Resistance (抗风险能力): Based on max drawdown, annual volatility
3. Stability (稳定性): Based on monthly return std dev, Sharpe ratio
4. Timing Ability (择时能力): Bull/bear market relative performance
5. Management Experience (管理经验): Manager tenure, historical fund performance
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json


class FundDiagnosis:
    """
    Fund diagnosis calculator providing five-dimension scoring and radar chart data.
    """

    # Dimension weights (each 20 points, total 100)
    DIMENSION_WEIGHTS = {
        'profitability': 20,      # 盈利能力
        'risk_resistance': 20,    # 抗风险能力
        'stability': 20,          # 稳定性
        'timing_ability': 20,     # 择时能力
        'management_exp': 20,     # 管理经验
    }

    def __init__(self):
        pass

    def diagnose(self, fund_code: str, nav_history: List[Dict],
                 fund_info: Dict = None, manager_info: Dict = None) -> Dict[str, Any]:
        """
        Perform comprehensive fund diagnosis.

        Args:
            fund_code: Fund code
            nav_history: List of {date, value} NAV history (at least 1 year)
            fund_info: Optional fund basic info (type, inception date, etc.)
            manager_info: Optional fund manager info (tenure, historical funds, etc.)

        Returns:
            Dictionary with total score, dimension scores, and radar chart data
        """
        if not nav_history or len(nav_history) < 20:
            return self._empty_diagnosis("Insufficient NAV history data")

        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(nav_history)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(subset=['value'])

        if len(df) < 20:
            return self._empty_diagnosis("Insufficient valid NAV data")

        # Calculate daily returns
        df['return'] = df['value'].pct_change()

        # Calculate dimension scores
        profitability = self._calc_profitability(df)
        risk_resistance = self._calc_risk_resistance(df)
        stability = self._calc_stability(df)
        timing_ability = self._calc_timing_ability(df)
        management_exp = self._calc_management_exp(manager_info, fund_info)

        # Calculate total score
        total_score = (
            profitability + risk_resistance + stability +
            timing_ability + management_exp
        )

        # Build radar chart data
        dimensions = [
            {'name': '盈利能力', 'name_en': 'Profitability', 'score': profitability, 'max': 20},
            {'name': '抗风险能力', 'name_en': 'Risk Resistance', 'score': risk_resistance, 'max': 20},
            {'name': '稳定性', 'name_en': 'Stability', 'score': stability, 'max': 20},
            {'name': '择时能力', 'name_en': 'Timing', 'score': timing_ability, 'max': 20},
            {'name': '管理经验', 'name_en': 'Management', 'score': management_exp, 'max': 20},
        ]

        # Grade based on score
        grade = self._get_grade(total_score)

        return {
            'fund_code': fund_code,
            'score': round(total_score, 1),
            'grade': grade,
            'dimensions': dimensions,
            'radar_data': [d['score'] for d in dimensions],
            'analysis_summary': self._generate_summary(dimensions, total_score),
            'computed_at': datetime.now().isoformat(),
        }

    def _calc_profitability(self, df: pd.DataFrame) -> float:
        """
        Calculate profitability score based on returns.
        Metrics: 1Y return, 3M return, cumulative return
        """
        try:
            total_days = len(df)

            # Calculate returns for different periods
            returns = {}

            # 1 year return (252 trading days)
            if total_days >= 252:
                returns['1y'] = (df['value'].iloc[-1] / df['value'].iloc[-252] - 1) * 100
            elif total_days >= 120:
                # Annualize if less than 1 year
                total_return = (df['value'].iloc[-1] / df['value'].iloc[0] - 1)
                returns['1y'] = total_return * (252 / total_days) * 100
            else:
                returns['1y'] = 0

            # 3 month return (63 trading days)
            if total_days >= 63:
                returns['3m'] = (df['value'].iloc[-1] / df['value'].iloc[-63] - 1) * 100
            else:
                returns['3m'] = (df['value'].iloc[-1] / df['value'].iloc[0] - 1) * 100

            # Score based on returns (normalized to 0-20)
            # Benchmark: 10% annual return = 10 points, 20% = 15 points, 30%+ = 20 points
            score = 0

            # 1Y return contributes 60%
            if returns['1y'] >= 30:
                score += 12
            elif returns['1y'] >= 20:
                score += 10
            elif returns['1y'] >= 10:
                score += 8
            elif returns['1y'] >= 5:
                score += 6
            elif returns['1y'] >= 0:
                score += 4
            else:
                score += max(0, 4 + returns['1y'] / 10)  # Negative returns reduce score

            # 3M return contributes 40%
            if returns['3m'] >= 10:
                score += 8
            elif returns['3m'] >= 5:
                score += 6
            elif returns['3m'] >= 2:
                score += 4
            elif returns['3m'] >= 0:
                score += 2
            else:
                score += max(0, 2 + returns['3m'] / 5)

            return min(20, max(0, round(score, 1)))

        except Exception as e:
            print(f"Error calculating profitability: {e}")
            return 10.0  # Default middle score

    def _calc_risk_resistance(self, df: pd.DataFrame) -> float:
        """
        Calculate risk resistance score.
        Metrics: Max drawdown, annual volatility
        """
        try:
            # Calculate max drawdown
            cummax = df['value'].cummax()
            drawdown = (df['value'] - cummax) / cummax
            max_drawdown = abs(drawdown.min()) * 100

            # Calculate annual volatility
            daily_returns = df['return'].dropna()
            annual_volatility = daily_returns.std() * np.sqrt(252) * 100

            # Score based on metrics
            score = 0

            # Max drawdown (12 points)
            # <10% = 12, <15% = 10, <20% = 8, <30% = 6, <40% = 4, >=40% = 2
            if max_drawdown < 10:
                score += 12
            elif max_drawdown < 15:
                score += 10
            elif max_drawdown < 20:
                score += 8
            elif max_drawdown < 30:
                score += 6
            elif max_drawdown < 40:
                score += 4
            else:
                score += 2

            # Annual volatility (8 points)
            # <15% = 8, <20% = 6, <25% = 4, <30% = 3, >=30% = 2
            if annual_volatility < 15:
                score += 8
            elif annual_volatility < 20:
                score += 6
            elif annual_volatility < 25:
                score += 4
            elif annual_volatility < 30:
                score += 3
            else:
                score += 2

            return min(20, max(0, round(score, 1)))

        except Exception as e:
            print(f"Error calculating risk resistance: {e}")
            return 10.0

    def _calc_stability(self, df: pd.DataFrame) -> float:
        """
        Calculate stability score.
        Metrics: Monthly return std dev, Sharpe ratio, positive return ratio
        """
        try:
            daily_returns = df['return'].dropna()

            # Calculate Sharpe ratio (risk-free rate assumed 2%)
            annual_return = daily_returns.mean() * 252
            annual_vol = daily_returns.std() * np.sqrt(252)
            sharpe = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0

            # Calculate monthly returns std dev
            df_copy = df.copy()
            df_copy.set_index('date', inplace=True)
            monthly_returns = df_copy['value'].resample('M').last().pct_change().dropna()
            monthly_std = monthly_returns.std() * 100 if len(monthly_returns) > 1 else 10

            # Calculate positive return ratio
            positive_ratio = (daily_returns > 0).sum() / len(daily_returns) * 100

            score = 0

            # Sharpe ratio (10 points)
            if sharpe >= 2:
                score += 10
            elif sharpe >= 1.5:
                score += 8
            elif sharpe >= 1:
                score += 6
            elif sharpe >= 0.5:
                score += 4
            elif sharpe >= 0:
                score += 2
            else:
                score += 1

            # Monthly std dev (6 points) - lower is better
            if monthly_std < 3:
                score += 6
            elif monthly_std < 5:
                score += 5
            elif monthly_std < 8:
                score += 4
            elif monthly_std < 12:
                score += 3
            else:
                score += 2

            # Positive return ratio (4 points)
            if positive_ratio >= 55:
                score += 4
            elif positive_ratio >= 52:
                score += 3
            elif positive_ratio >= 50:
                score += 2
            else:
                score += 1

            return min(20, max(0, round(score, 1)))

        except Exception as e:
            print(f"Error calculating stability: {e}")
            return 10.0

    def _calc_timing_ability(self, df: pd.DataFrame) -> float:
        """
        Calculate timing ability score.
        Metrics: Bull/bear market relative performance, recovery speed
        """
        try:
            daily_returns = df['return'].dropna()

            # Identify bull/bear periods (simplified: positive vs negative market days)
            # In reality, should compare with benchmark index
            bull_days = daily_returns[daily_returns > 0]
            bear_days = daily_returns[daily_returns < 0]

            # Calculate capture ratios (simplified)
            upside_capture = bull_days.mean() * 100 if len(bull_days) > 0 else 0
            downside_capture = abs(bear_days.mean()) * 100 if len(bear_days) > 0 else 0

            # Better funds capture more upside and less downside
            capture_ratio = upside_capture / downside_capture if downside_capture > 0 else 1

            # Calculate recovery speed after drawdowns
            cummax = df['value'].cummax()
            drawdown = (df['value'] - cummax) / cummax

            # Find significant drawdown periods (>5%)
            in_drawdown = drawdown < -0.05
            recovery_speeds = []

            drawdown_start = None
            for i, (is_dd, dd_val) in enumerate(zip(in_drawdown, drawdown)):
                if is_dd and drawdown_start is None:
                    drawdown_start = i
                elif not is_dd and drawdown_start is not None:
                    recovery_days = i - drawdown_start
                    recovery_speeds.append(recovery_days)
                    drawdown_start = None

            avg_recovery = np.mean(recovery_speeds) if recovery_speeds else 30

            score = 0

            # Capture ratio (12 points)
            if capture_ratio >= 1.5:
                score += 12
            elif capture_ratio >= 1.2:
                score += 10
            elif capture_ratio >= 1.0:
                score += 8
            elif capture_ratio >= 0.8:
                score += 6
            else:
                score += 4

            # Recovery speed (8 points) - faster is better
            if avg_recovery <= 20:
                score += 8
            elif avg_recovery <= 40:
                score += 6
            elif avg_recovery <= 60:
                score += 4
            elif avg_recovery <= 90:
                score += 3
            else:
                score += 2

            return min(20, max(0, round(score, 1)))

        except Exception as e:
            print(f"Error calculating timing ability: {e}")
            return 10.0

    def _calc_management_exp(self, manager_info: Dict = None, fund_info: Dict = None) -> float:
        """
        Calculate management experience score.
        Metrics: Manager tenure, historical fund performance, fund age
        """
        try:
            score = 10  # Default middle score

            if manager_info:
                # Manager tenure (10 points)
                tenure_years = manager_info.get('tenure_years', 0)
                if tenure_years >= 5:
                    score += 5
                elif tenure_years >= 3:
                    score += 3
                elif tenure_years >= 1:
                    score += 1

                # Historical performance (5 points)
                hist_return = manager_info.get('historical_avg_return', 0)
                if hist_return >= 15:
                    score += 5
                elif hist_return >= 10:
                    score += 3
                elif hist_return >= 5:
                    score += 1

            if fund_info:
                # Fund age (5 points)
                inception_date = fund_info.get('inception_date')
                if inception_date:
                    try:
                        if isinstance(inception_date, str):
                            inception = datetime.strptime(inception_date, '%Y-%m-%d')
                        else:
                            inception = inception_date
                        fund_age = (datetime.now() - inception).days / 365

                        if fund_age >= 5:
                            score += 5
                        elif fund_age >= 3:
                            score += 3
                        elif fund_age >= 1:
                            score += 1
                    except:
                        pass

            return min(20, max(0, round(score, 1)))

        except Exception as e:
            print(f"Error calculating management experience: {e}")
            return 10.0

    def _get_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return 'A+'
        elif score >= 85:
            return 'A'
        elif score >= 80:
            return 'A-'
        elif score >= 75:
            return 'B+'
        elif score >= 70:
            return 'B'
        elif score >= 65:
            return 'B-'
        elif score >= 60:
            return 'C+'
        elif score >= 55:
            return 'C'
        elif score >= 50:
            return 'C-'
        else:
            return 'D'

    def _generate_summary(self, dimensions: List[Dict], total_score: float) -> Dict:
        """Generate analysis summary with strengths and weaknesses."""
        # Find best and worst dimensions
        sorted_dims = sorted(dimensions, key=lambda x: x['score'], reverse=True)

        strengths = [d['name'] for d in sorted_dims[:2] if d['score'] >= 15]
        weaknesses = [d['name'] for d in sorted_dims[-2:] if d['score'] < 12]

        return {
            'strengths': strengths,
            'weaknesses': weaknesses,
            'recommendation': self._get_recommendation(total_score, sorted_dims),
        }

    def _get_recommendation(self, score: float, dims: List[Dict]) -> str:
        """Generate investment recommendation based on diagnosis."""
        if score >= 80:
            return '该基金综合表现优秀,适合作为核心配置'
        elif score >= 70:
            return '该基金表现良好,可作为投资组合的重要组成部分'
        elif score >= 60:
            return '该基金表现中等,建议结合其他基金分散配置'
        elif score >= 50:
            return '该基金表现一般,建议谨慎投资并持续观察'
        else:
            return '该基金综合评分较低,建议优先考虑其他同类基金'

    def _empty_diagnosis(self, reason: str) -> Dict:
        """Return empty diagnosis when data is insufficient."""
        return {
            'fund_code': '',
            'score': 0,
            'grade': 'N/A',
            'dimensions': [],
            'radar_data': [],
            'analysis_summary': {'strengths': [], 'weaknesses': [], 'recommendation': reason},
            'computed_at': datetime.now().isoformat(),
            'error': reason,
        }
