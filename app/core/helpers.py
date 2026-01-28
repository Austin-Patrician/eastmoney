"""
Data retrieval helper functions for funds, stocks, and portfolios.
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Any
import pandas as pd
import akshare as ak

from src.data_sources.akshare_api import get_all_fund_list, get_stock_realtime_quote, get_stock_history
from src.data_sources.data_source_manager import get_fund_info_from_tushare


def get_fund_nav_history(fund_code: str, days: int = 100) -> List[Dict]:
    """
    Get fund NAV (Net Asset Value) history.

    Args:
        fund_code: The fund code
        days: Number of days of history to retrieve

    Returns:
        List of dicts with 'date' and 'value' keys
    """
    try:
        # Use TuShare via data_source_manager
        df = get_fund_info_from_tushare(fund_code)
        
        if df is None or df.empty:
            return []

        # Data from data_source_manager already has standard columns:
        # '净值日期' (YYYYMMDD string), '单位净值' (float)

        if '净值日期' not in df.columns or '单位净值' not in df.columns:
            return []

        df['净值日期'] = pd.to_datetime(df['净值日期'], errors='coerce')
        df = df.dropna(subset=['净值日期', '单位净值'])
        
        # Sort by date ascending to get chronological order
        df = df.sort_values('净值日期')
        
        # Take the last 'days' entries
        df = df.tail(days)

        return [
            {'date': row['净值日期'].strftime('%Y-%m-%d'), 'value': float(row['单位净值'])}
            for _, row in df.iterrows()
        ]
    except Exception as e:
        print(f"Error fetching NAV history for {fund_code}: {e}")
        return []


def get_fund_basic_info(fund_code: str) -> Optional[Dict]:
    """
    Get basic fund information (name, type, etc.)

    Args:
        fund_code: The fund code

    Returns:
        Dict with fund info or None
    """
    try:
        # Try to get from fund name list first
        all_funds = get_all_fund_list()
        for fund in all_funds:
            if fund.get('code') == fund_code:
                return {'code': fund_code, 'name': fund.get('name', ''), 'type': fund.get('type', '')}
        return None
    except Exception as e:
        print(f"Error fetching fund info for {fund_code}: {e}")
        return None


def get_fund_holdings_list(fund_code: str) -> List[Dict]:
    """
    Get fund top holdings as a list.

    Args:
        fund_code: The fund code

    Returns:
        List of dicts with holding information
    """
    try:
        year = str(datetime.now().year)
        df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)

        if df is None or df.empty:
            # Try previous year
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date=str(int(year) - 1))

        if df is None or df.empty:
            return []

        # Get latest quarter data
        if '季度' in df.columns:
            latest_quarter = df['季度'].max()
            df = df[df['季度'] == latest_quarter]

        holdings = []
        for _, row in df.head(10).iterrows():
            holdings.append({
                'code': row.get('股票代码', ''),
                'name': row.get('股票名称', ''),
                'weight': float(row.get('占净值比例', 0)) if row.get('占净值比例') else 0,
            })

        return holdings
    except Exception as e:
        print(f"Error fetching holdings for {fund_code}: {e}")
        return []


def get_stock_price_history(stock_code: str, days: int = 90) -> List[Dict]:
    """
    Get stock price history.

    Args:
        stock_code: The stock code
        days: Number of days of history

    Returns:
        List of dicts with 'date' and 'price' keys
    """
    try:
        # get_stock_history returns List[Dict] with keys: date, value, volume
        history = get_stock_history(stock_code, days=days + 30)

        if not history:
            return []

        # Sort by date to be sure
        history.sort(key=lambda x: x['date'])

        # Take the requested number of days
        recent_history = history[-days:]

        return [
            {
                'date': item['date'],
                'price': item['value']
            }
            for item in recent_history
        ]
    except Exception as e:
        print(f"Error fetching stock history for {stock_code}: {e}")
        return []


def get_index_history(index_code: str, days: int = 30) -> List[Dict]:
    """
    Get index price history.

    Args:
        index_code: Index code like '000300.SH'
        days: Number of days

    Returns:
        List of dicts with 'date' and 'close' keys
    """
    try:
        # Map common index codes
        ak_code = index_code.replace('.SH', '').replace('.SZ', '')
        df = ak.stock_zh_index_daily_em(
            symbol=f"sh{ak_code}" if 'SH' in index_code else f"sz{ak_code}"
        )

        if df is None or df.empty:
            return []

        df = df.tail(days)
        return [
            {
                'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
                'close': float(row['close'])
            }
            for _, row in df.iterrows()
        ]
    except Exception as e:
        print(f"Error fetching index history for {index_code}: {e}")
        return []


async def enrich_positions_with_prices(positions: List[Dict]) -> List[Dict]:
    """
    Enrich portfolio positions with current market prices.

    Args:
        positions: List of position dicts

    Returns:
        Enriched positions with current_price, current_value, unrealized_pnl
    """
    loop = asyncio.get_running_loop()
    enriched = []

    for pos in positions:
        asset_type = pos['asset_type']
        asset_code = pos['asset_code']
        total_shares = float(pos.get('total_shares', 0))
        average_cost = float(pos.get('average_cost', 0))
        total_cost = total_shares * average_cost

        current_price = None
        current_value = None
        unrealized_pnl = None
        unrealized_pnl_pct = None

        try:
            if asset_type == 'fund':
                nav_history = await loop.run_in_executor(None, get_fund_nav_history, asset_code, 5)
                if nav_history:
                    current_price = float(nav_history[-1]['value'])
            else:  # stock
                quote = await loop.run_in_executor(None, get_stock_realtime_quote, asset_code)
                if quote and quote.get('price'):
                    current_price = float(quote['price'])
        except Exception as e:
            print(f"Error fetching price for {asset_type}/{asset_code}: {e}")

        if current_price:
            current_value = total_shares * current_price
            unrealized_pnl = current_value - total_cost
            unrealized_pnl_pct = ((current_price / average_cost) - 1) * 100 if average_cost > 0 else 0

        enriched.append({
            **pos,
            'current_price': round(current_price, 4) if current_price else None,
            'current_value': round(current_value, 2) if current_value else None,
            'unrealized_pnl': round(unrealized_pnl, 2) if unrealized_pnl is not None else None,
            'unrealized_pnl_pct': round(unrealized_pnl_pct, 2) if unrealized_pnl_pct is not None else None,
        })

    return enriched
