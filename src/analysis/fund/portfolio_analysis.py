"""
Portfolio Analysis Module

Provides portfolio-level analysis including:
- Holdings aggregation across funds
- Position overlap analysis
- Concentration warnings
- Portfolio summary with P&L calculation
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict


class PortfolioAnalyzer:
    """
    Portfolio-level analysis tool.
    """

    # Concentration warning threshold (single stock > 5% of portfolio)
    CONCENTRATION_THRESHOLD = 0.05

    def __init__(self, concentration_threshold: float = 0.05):
        self.concentration_threshold = concentration_threshold

    def calculate_portfolio_summary(self, positions: List[Dict],
                                     fund_nav_map: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculate portfolio summary with P&L.

        Args:
            positions: List of position dicts with:
                - fund_code: Fund code
                - fund_name: Fund name
                - shares: Number of shares held
                - cost_basis: Cost per share
                - purchase_date: Purchase date
            fund_nav_map: Dict mapping fund_code to current NAV

        Returns:
            Portfolio summary with total value, P&L, allocation, etc.
        """
        if not positions:
            return {
                'total_value': 0,
                'total_cost': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'positions': [],
                'allocation': [],
                'message': 'No positions'
            }

        position_details = []
        total_value = 0
        total_cost = 0

        for pos in positions:
            fund_code = pos['fund_code']
            shares = float(pos.get('shares', 0))
            cost_basis = float(pos.get('cost_basis', 0))

            # Get current NAV
            current_nav = fund_nav_map.get(fund_code)
            if current_nav is None:
                current_nav = cost_basis  # Fallback to cost if NAV unavailable

            # Calculate position value and P&L
            position_cost = shares * cost_basis
            position_value = shares * current_nav
            pnl = position_value - position_cost
            pnl_pct = (current_nav / cost_basis - 1) * 100 if cost_basis > 0 else 0

            total_value += position_value
            total_cost += position_cost

            position_details.append({
                'fund_code': fund_code,
                'fund_name': pos.get('fund_name', ''),
                'shares': shares,
                'cost_basis': cost_basis,
                'current_nav': current_nav,
                'position_cost': round(position_cost, 2),
                'position_value': round(position_value, 2),
                'pnl': round(pnl, 2),
                'pnl_pct': round(pnl_pct, 2),
                'purchase_date': pos.get('purchase_date'),
            })

        # Calculate total P&L
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0

        # Calculate allocation
        allocation = []
        for pos in position_details:
            weight = (pos['position_value'] / total_value * 100) if total_value > 0 else 0
            allocation.append({
                'fund_code': pos['fund_code'],
                'fund_name': pos['fund_name'],
                'value': pos['position_value'],
                'weight': round(weight, 2)
            })

        # Sort by weight
        allocation.sort(key=lambda x: x['weight'], reverse=True)

        return {
            'total_value': round(total_value, 2),
            'total_cost': round(total_cost, 2),
            'total_pnl': round(total_pnl, 2),
            'total_pnl_pct': round(total_pnl_pct, 2),
            'positions': position_details,
            'allocation': allocation,
            'position_count': len(positions),
            'computed_at': datetime.now().isoformat(),
        }

    def analyze_holdings_overlap(self, fund_holdings: Dict[str, List[Dict]],
                                 position_weights: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Analyze holdings overlap across user's fund portfolio.

        Args:
            fund_holdings: Dict mapping fund_code to list of holdings
                Each holding: {code, name, weight}
            position_weights: Optional dict mapping fund_code to portfolio weight

        Returns:
            Overlap analysis with aggregated holdings and concentration warnings
        """
        if not fund_holdings:
            return {'message': 'No holdings data'}

        # Aggregate stock holdings across funds
        aggregated_holdings = defaultdict(lambda: {
            'name': '',
            'total_weight': 0,
            'fund_sources': [],
        })

        for fund_code, holdings in fund_holdings.items():
            fund_weight = position_weights.get(fund_code, 1.0) if position_weights else 1.0

            for holding in holdings:
                stock_code = holding.get('code') or holding.get('stock_code', '')
                stock_name = holding.get('name') or holding.get('stock_name', '')
                weight = float(holding.get('weight') or holding.get('proportion', 0))

                if stock_code:
                    # Calculate effective weight in portfolio
                    effective_weight = weight * fund_weight / 100

                    aggregated_holdings[stock_code]['name'] = stock_name
                    aggregated_holdings[stock_code]['total_weight'] += effective_weight
                    aggregated_holdings[stock_code]['fund_sources'].append({
                        'fund_code': fund_code,
                        'weight_in_fund': weight,
                        'effective_weight': round(effective_weight * 100, 2)
                    })

        # Convert to list and sort by total weight
        holdings_list = []
        for stock_code, data in aggregated_holdings.items():
            holdings_list.append({
                'stock_code': stock_code,
                'stock_name': data['name'],
                'total_weight': round(data['total_weight'] * 100, 2),
                'fund_count': len(data['fund_sources']),
                'fund_sources': data['fund_sources']
            })

        holdings_list.sort(key=lambda x: x['total_weight'], reverse=True)

        # Identify concentration warnings
        concentration_warnings = []
        for holding in holdings_list:
            if holding['total_weight'] > self.concentration_threshold * 100:
                concentration_warnings.append({
                    'stock_code': holding['stock_code'],
                    'stock_name': holding['stock_name'],
                    'weight': holding['total_weight'],
                    'threshold': self.concentration_threshold * 100,
                    'message': f"{holding['stock_name']} 占组合 {holding['total_weight']:.1f}%,超过警戒线 {self.concentration_threshold*100:.0f}%"
                })

        # Calculate overlap matrix between funds
        overlap_matrix = self._calculate_fund_overlap_matrix(fund_holdings)

        # Industry breakdown
        industry_breakdown = self._calculate_industry_breakdown(holdings_list)

        return {
            'aggregated_holdings': holdings_list[:50],  # Top 50
            'total_unique_stocks': len(holdings_list),
            'concentration_warnings': concentration_warnings,
            'overlap_matrix': overlap_matrix,
            'industry_breakdown': industry_breakdown,
            'computed_at': datetime.now().isoformat(),
        }

    def _calculate_fund_overlap_matrix(self, fund_holdings: Dict[str, List[Dict]]) -> Dict[str, Dict[str, float]]:
        """Calculate pairwise overlap between funds."""
        fund_stocks = {}
        for fund_code, holdings in fund_holdings.items():
            stocks = set()
            for h in holdings:
                stock_code = h.get('code') or h.get('stock_code', '')
                if stock_code:
                    stocks.add(stock_code)
            fund_stocks[fund_code] = stocks

        overlap_matrix = {}
        fund_codes = list(fund_stocks.keys())

        for code1 in fund_codes:
            overlap_matrix[code1] = {}
            for code2 in fund_codes:
                if code1 == code2:
                    overlap_matrix[code1][code2] = 100.0
                else:
                    stocks1 = fund_stocks[code1]
                    stocks2 = fund_stocks[code2]

                    if not stocks1 or not stocks2:
                        overlap_matrix[code1][code2] = 0
                    else:
                        common = len(stocks1 & stocks2)
                        total = len(stocks1 | stocks2)
                        overlap_pct = (common / total) * 100 if total > 0 else 0
                        overlap_matrix[code1][code2] = round(overlap_pct, 1)

        return overlap_matrix

    def _calculate_industry_breakdown(self, holdings_list: List[Dict]) -> List[Dict]:
        """
        Calculate industry breakdown from holdings.
        Note: This is a placeholder - actual implementation needs industry data.
        """
        # In a real implementation, we would look up industry for each stock
        # For now, return empty list as placeholder
        return []

    def calculate_portfolio_risk(self, positions: List[Dict],
                                 fund_nav_histories: Dict[str, List[Dict]],
                                 fund_nav_map: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculate portfolio-level risk metrics.

        Args:
            positions: User positions
            fund_nav_histories: Dict mapping fund_code to NAV history
            fund_nav_map: Current NAV map

        Returns:
            Portfolio risk metrics
        """
        if not positions or not fund_nav_histories:
            return {'message': 'Insufficient data for risk calculation'}

        # Calculate position weights
        total_value = 0
        position_values = {}

        for pos in positions:
            fund_code = pos['fund_code']
            shares = float(pos.get('shares', 0))
            current_nav = fund_nav_map.get(fund_code, float(pos.get('cost_basis', 1)))

            position_value = shares * current_nav
            position_values[fund_code] = position_value
            total_value += position_value

        if total_value == 0:
            return {'message': 'Zero portfolio value'}

        weights = {code: val / total_value for code, val in position_values.items()}

        # Build portfolio return series
        # Find common date range
        date_sets = []
        for fund_code in position_values.keys():
            nav_history = fund_nav_histories.get(fund_code, [])
            if nav_history:
                dates = {h['date'] for h in nav_history}
                date_sets.append(dates)

        if not date_sets:
            return {'message': 'No NAV history available'}

        common_dates = set.intersection(*date_sets) if date_sets else set()
        if len(common_dates) < 20:
            return {'message': 'Insufficient common trading days'}

        # Calculate weighted portfolio returns
        portfolio_returns = []
        sorted_dates = sorted(common_dates)

        for i, date in enumerate(sorted_dates[1:], 1):
            prev_date = sorted_dates[i - 1]
            daily_return = 0

            for fund_code, weight in weights.items():
                nav_history = fund_nav_histories.get(fund_code, [])
                nav_map = {h['date']: h['value'] for h in nav_history}

                current_val = nav_map.get(date)
                prev_val = nav_map.get(prev_date)

                if current_val and prev_val and float(prev_val) > 0:
                    fund_return = (float(current_val) / float(prev_val) - 1)
                    daily_return += fund_return * weight

            portfolio_returns.append(daily_return)

        if not portfolio_returns:
            return {'message': 'Could not calculate portfolio returns'}

        # Calculate portfolio metrics
        returns_array = np.array(portfolio_returns)

        annual_return = returns_array.mean() * 252
        annual_vol = returns_array.std() * np.sqrt(252)
        sharpe = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0

        # Calculate portfolio drawdown
        cumulative = np.cumprod(1 + returns_array)
        cummax = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - cummax) / cummax
        max_drawdown = abs(drawdown.min())

        return {
            'portfolio_sharpe': round(sharpe, 3),
            'portfolio_volatility': round(annual_vol * 100, 2),
            'portfolio_return': round(annual_return * 100, 2),
            'portfolio_max_drawdown': round(max_drawdown * 100, 2),
            'portfolio_calmar': round((annual_return * 100) / (max_drawdown * 100), 3) if max_drawdown > 0 else None,
            'analysis_period_days': len(common_dates),
            'weights': {k: round(v * 100, 2) for k, v in weights.items()},
            'computed_at': datetime.now().isoformat(),
        }

    def get_rebalance_suggestions(self, positions: List[Dict],
                                   target_allocation: Dict[str, float],
                                   fund_nav_map: Dict[str, float]) -> List[Dict]:
        """
        Generate rebalancing suggestions based on target allocation.

        Args:
            positions: Current positions
            target_allocation: Target allocation {fund_code: weight%}
            fund_nav_map: Current NAV map

        Returns:
            List of rebalancing suggestions
        """
        if not positions or not target_allocation:
            return []

        # Calculate current allocation
        current_values = {}
        total_value = 0

        for pos in positions:
            fund_code = pos['fund_code']
            shares = float(pos.get('shares', 0))
            current_nav = fund_nav_map.get(fund_code, float(pos.get('cost_basis', 1)))

            position_value = shares * current_nav
            current_values[fund_code] = position_value
            total_value += position_value

        if total_value == 0:
            return []

        current_allocation = {code: (val / total_value * 100) for code, val in current_values.items()}

        # Calculate differences
        suggestions = []
        for fund_code, target_weight in target_allocation.items():
            current_weight = current_allocation.get(fund_code, 0)
            diff = target_weight - current_weight

            if abs(diff) > 1:  # Only suggest if difference > 1%
                target_value = total_value * target_weight / 100
                current_value = current_values.get(fund_code, 0)
                value_change = target_value - current_value

                suggestions.append({
                    'fund_code': fund_code,
                    'current_weight': round(current_weight, 2),
                    'target_weight': target_weight,
                    'diff': round(diff, 2),
                    'action': 'buy' if diff > 0 else 'sell',
                    'value_change': round(abs(value_change), 2),
                })

        # Sort by absolute difference
        suggestions.sort(key=lambda x: abs(x['diff']), reverse=True)

        return suggestions
