"""
Fund Comparison Module

Provides multi-fund comparison (up to 10 funds) including:
- NAV curve overlay
- Return comparison (1M/3M/6M/1Y/3Y)
- Risk metrics comparison (Sharpe/Drawdown/Volatility)
- Top 10 holdings overlap analysis
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict


class FundComparison:
    """
    Multi-fund comparison tool supporting up to 10 funds.
    """

    MAX_FUNDS = 10

    def __init__(self):
        pass

    def compare(self, funds_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compare multiple funds.

        Args:
            funds_data: List of fund data dicts, each containing:
                - code: Fund code
                - name: Fund name
                - nav_history: List of {date, value}
                - holdings: Optional list of top holdings

        Returns:
            Comprehensive comparison results
        """
        if not funds_data:
            return {'error': 'No fund data provided'}

        if len(funds_data) > self.MAX_FUNDS:
            return {'error': f'Maximum {self.MAX_FUNDS} funds allowed for comparison'}

        # Validate data
        valid_funds = []
        for fund in funds_data:
            if fund.get('nav_history') and len(fund['nav_history']) >= 20:
                valid_funds.append(fund)

        if not valid_funds:
            return {'error': 'No valid fund data with sufficient NAV history'}

        # Build comparison results
        result = {
            'funds': [{'code': f['code'], 'name': f['name']} for f in valid_funds],
            'nav_comparison': self._compare_nav_curves(valid_funds),
            'return_comparison': self._compare_returns(valid_funds),
            'risk_comparison': self._compare_risk_metrics(valid_funds),
            'holdings_overlap': self._analyze_holdings_overlap(valid_funds),
            'ranking': self._calculate_ranking(valid_funds),
            'computed_at': datetime.now().isoformat(),
        }

        return result

    def _compare_nav_curves(self, funds: List[Dict]) -> Dict[str, Any]:
        """
        Normalize and compare NAV curves for overlay chart.
        All curves start at 100 for fair comparison.
        """
        curves = {}
        dates_set = set()

        for fund in funds:
            df = pd.DataFrame(fund['nav_history'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna(subset=['value'])

            if len(df) < 20:
                continue

            # Normalize to start at 100
            initial_value = df['value'].iloc[0]
            df['normalized'] = (df['value'] / initial_value) * 100

            # Store curve data
            curve_data = []
            for _, row in df.iterrows():
                date_str = row['date'].strftime('%Y-%m-%d')
                dates_set.add(date_str)
                curve_data.append({
                    'date': date_str,
                    'value': round(row['normalized'], 2),
                    'original_value': round(row['value'], 4)
                })

            curves[fund['code']] = {
                'name': fund['name'],
                'data': curve_data
            }

        # Get common date range
        if dates_set:
            sorted_dates = sorted(dates_set)
            date_range = {
                'start': sorted_dates[0],
                'end': sorted_dates[-1]
            }
        else:
            date_range = None

        return {
            'curves': curves,
            'date_range': date_range,
        }

    def _compare_returns(self, funds: List[Dict]) -> Dict[str, Any]:
        """Compare returns across multiple periods."""
        periods = {
            '1m': 21,     # 1 month (21 trading days)
            '3m': 63,     # 3 months
            '6m': 126,    # 6 months
            '1y': 252,    # 1 year
            '3y': 756,    # 3 years
        }

        comparison = {}

        for fund in funds:
            df = pd.DataFrame(fund['nav_history'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna(subset=['value'])

            if len(df) < 20:
                continue

            fund_returns = {'code': fund['code'], 'name': fund['name']}

            for period_name, days in periods.items():
                if len(df) >= days:
                    ret = (df['value'].iloc[-1] / df['value'].iloc[-days] - 1) * 100
                    fund_returns[period_name] = round(ret, 2)
                else:
                    # Annualize if data is shorter
                    total_return = df['value'].iloc[-1] / df['value'].iloc[0] - 1
                    if period_name == '1y':
                        annualized = (1 + total_return) ** (252 / len(df)) - 1
                        fund_returns[period_name] = round(annualized * 100, 2)
                    else:
                        fund_returns[period_name] = None

            comparison[fund['code']] = fund_returns

        # Calculate period rankings
        rankings = {}
        for period in periods.keys():
            period_data = [
                (code, data.get(period))
                for code, data in comparison.items()
                if data.get(period) is not None
            ]
            sorted_data = sorted(period_data, key=lambda x: x[1], reverse=True)
            rankings[period] = [code for code, _ in sorted_data]

        return {
            'returns': comparison,
            'periods': list(periods.keys()),
            'rankings': rankings,
        }

    def _compare_risk_metrics(self, funds: List[Dict]) -> Dict[str, Any]:
        """Compare risk metrics across funds."""
        comparison = {}

        for fund in funds:
            df = pd.DataFrame(fund['nav_history'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna(subset=['value'])

            if len(df) < 20:
                continue

            df['return'] = df['value'].pct_change()
            daily_returns = df['return'].dropna()

            # Calculate metrics
            annual_return = daily_returns.mean() * 252
            annual_vol = daily_returns.std() * np.sqrt(252)
            sharpe = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0

            cummax = df['value'].cummax()
            drawdown = (df['value'] - cummax) / cummax
            max_drawdown = abs(drawdown.min()) * 100

            calmar = annual_return * 100 / max_drawdown if max_drawdown > 0 else 0

            comparison[fund['code']] = {
                'code': fund['code'],
                'name': fund['name'],
                'sharpe_ratio': round(sharpe, 3),
                'max_drawdown': round(max_drawdown, 2),
                'annual_volatility': round(annual_vol * 100, 2),
                'calmar_ratio': round(calmar, 3),
                'annual_return': round(annual_return * 100, 2),
            }

        # Calculate metric rankings
        rankings = {}
        metrics = ['sharpe_ratio', 'max_drawdown', 'annual_volatility', 'calmar_ratio', 'annual_return']

        for metric in metrics:
            metric_data = [
                (code, data.get(metric))
                for code, data in comparison.items()
                if data.get(metric) is not None
            ]

            # For max_drawdown and volatility, lower is better
            reverse = metric not in ['max_drawdown', 'annual_volatility']
            sorted_data = sorted(metric_data, key=lambda x: x[1], reverse=reverse)
            rankings[metric] = [code for code, _ in sorted_data]

        return {
            'metrics': comparison,
            'rankings': rankings,
        }

    def _analyze_holdings_overlap(self, funds: List[Dict]) -> Dict[str, Any]:
        """Analyze holdings overlap between funds."""
        # Extract holdings for each fund
        fund_holdings = {}
        all_stocks = set()

        for fund in funds:
            holdings = fund.get('holdings', [])
            if not holdings:
                continue

            stock_set = set()
            stock_weights = {}

            for holding in holdings[:10]:  # Top 10 holdings
                stock_code = holding.get('code') or holding.get('stock_code', '')
                stock_name = holding.get('name') or holding.get('stock_name', '')
                weight = holding.get('weight') or holding.get('proportion', 0)

                if stock_code:
                    stock_set.add(stock_code)
                    stock_weights[stock_code] = {
                        'name': stock_name,
                        'weight': float(weight) if weight else 0
                    }
                    all_stocks.add(stock_code)

            fund_holdings[fund['code']] = {
                'stocks': stock_set,
                'weights': stock_weights
            }

        if len(fund_holdings) < 2:
            return {'overlap_matrix': {}, 'common_stocks': [], 'message': 'Need at least 2 funds with holdings data'}

        # Calculate overlap matrix
        overlap_matrix = {}
        fund_codes = list(fund_holdings.keys())

        for i, code1 in enumerate(fund_codes):
            overlap_matrix[code1] = {}
            for j, code2 in enumerate(fund_codes):
                if i == j:
                    overlap_matrix[code1][code2] = 100.0  # Self-overlap
                else:
                    stocks1 = fund_holdings[code1]['stocks']
                    stocks2 = fund_holdings[code2]['stocks']

                    if not stocks1 or not stocks2:
                        overlap_matrix[code1][code2] = 0
                    else:
                        common = len(stocks1 & stocks2)
                        total = len(stocks1 | stocks2)
                        overlap_pct = (common / total) * 100 if total > 0 else 0
                        overlap_matrix[code1][code2] = round(overlap_pct, 1)

        # Find stocks held by multiple funds
        stock_fund_count = defaultdict(list)
        for code, data in fund_holdings.items():
            for stock in data['stocks']:
                stock_fund_count[stock].append(code)

        common_stocks = []
        for stock, fund_codes_list in stock_fund_count.items():
            if len(fund_codes_list) >= 2:
                # Get stock name from any fund that has it
                stock_name = ''
                for fc in fund_codes_list:
                    if stock in fund_holdings[fc]['weights']:
                        stock_name = fund_holdings[fc]['weights'][stock]['name']
                        break

                common_stocks.append({
                    'code': stock,
                    'name': stock_name,
                    'held_by': fund_codes_list,
                    'count': len(fund_codes_list)
                })

        # Sort by count (most common first)
        common_stocks.sort(key=lambda x: x['count'], reverse=True)

        return {
            'overlap_matrix': overlap_matrix,
            'common_stocks': common_stocks[:20],  # Top 20 common stocks
            'total_unique_stocks': len(all_stocks),
        }

    def _calculate_ranking(self, funds: List[Dict]) -> Dict[str, Any]:
        """Calculate overall ranking based on multiple criteria."""
        scores = {}

        for fund in funds:
            df = pd.DataFrame(fund['nav_history'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna(subset=['value'])

            if len(df) < 20:
                continue

            df['return'] = df['value'].pct_change()
            daily_returns = df['return'].dropna()

            # Calculate composite score
            annual_return = daily_returns.mean() * 252
            annual_vol = daily_returns.std() * np.sqrt(252)
            sharpe = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0

            cummax = df['value'].cummax()
            drawdown = (df['value'] - cummax) / cummax
            max_drawdown = abs(drawdown.min())

            # Composite score: weighted average
            # Higher returns, higher sharpe, lower drawdown = better
            score = (
                (annual_return * 100) * 0.3 +  # Return contribution
                sharpe * 20 +                    # Sharpe contribution
                (1 - max_drawdown) * 30         # Drawdown contribution (inverted)
            )

            scores[fund['code']] = {
                'code': fund['code'],
                'name': fund['name'],
                'score': round(score, 2),
                'components': {
                    'return': round(annual_return * 100, 2),
                    'sharpe': round(sharpe, 3),
                    'max_drawdown': round(max_drawdown * 100, 2)
                }
            }

        # Sort by score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)
        ranking_list = []
        for rank, (code, data) in enumerate(sorted_scores, 1):
            data['rank'] = rank
            ranking_list.append(data)

        return {
            'ranking': ranking_list,
            'methodology': 'Composite score based on annual return (30%), Sharpe ratio (40%), and max drawdown (30%)'
        }

    def get_comparison_chart_data(self, funds_data: List[Dict], chart_type: str = 'nav') -> Dict:
        """
        Get data formatted for specific chart types.

        Args:
            funds_data: List of fund data
            chart_type: 'nav' for NAV curves, 'return' for return bars, 'risk' for risk scatter

        Returns:
            Chart-ready data
        """
        if chart_type == 'nav':
            comparison = self._compare_nav_curves(funds_data)
            return {
                'type': 'line',
                'data': comparison['curves'],
                'date_range': comparison['date_range']
            }
        elif chart_type == 'return':
            comparison = self._compare_returns(funds_data)
            return {
                'type': 'bar',
                'data': comparison['returns'],
                'periods': comparison['periods']
            }
        elif chart_type == 'risk':
            comparison = self._compare_risk_metrics(funds_data)
            # Scatter plot data: x=volatility, y=return, size=sharpe
            scatter_data = []
            for code, data in comparison['metrics'].items():
                scatter_data.append({
                    'code': code,
                    'name': data['name'],
                    'x': data['annual_volatility'],
                    'y': data['annual_return'],
                    'size': max(1, data['sharpe_ratio'] * 10)
                })
            return {
                'type': 'scatter',
                'data': scatter_data,
                'x_label': 'Annual Volatility (%)',
                'y_label': 'Annual Return (%)'
            }
        else:
            return {'error': f'Unknown chart type: {chart_type}'}
