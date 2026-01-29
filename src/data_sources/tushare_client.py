"""
TuShare Pro API Client
Provides a wrapper around TuShare Pro API with retry logic, rate limiting, and data normalization.
"""

import time
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from config.settings import TUSHARE_API_TOKEN


def format_date_yyyymmdd(dt: datetime = None) -> str:
    """Format datetime to YYYYMMDD string."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime('%Y%m%d')

# Lazy import to avoid errors if tushare not installed
_tushare_pro = None


def _get_tushare_pro():
    """Lazy initialization of TuShare Pro API client"""
    global _tushare_pro
    if _tushare_pro is None:
        if not TUSHARE_API_TOKEN:
            raise ValueError(
                "TUSHARE_API_TOKEN not configured. Please add it to your .env file.\n"
                "Get your token at: https://tushare.pro/register"
            )
        try:
            import tushare as ts
            _tushare_pro = ts.pro_api(TUSHARE_API_TOKEN)
        except ImportError:
            raise ImportError(
                "tushare not installed. Run: pip install tushare"
            )
    return _tushare_pro


def tushare_call_with_retry(
    api_method: str,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    **kwargs
) -> Optional[pd.DataFrame]:
    """
    Call TuShare API with exponential backoff retry logic and rate limiting.

    Args:
        api_method: API method name (e.g., 'daily', 'moneyflow_hsgt')
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff multiplier
        **kwargs: Parameters to pass to the API method

    Returns:
        DataFrame with results, or None if all retries failed
    """
    # Lazy import to avoid circular dependency
    from src.analysis.recommendation.factor_store.rate_limiter import tushare_rate_limiter

    # Acquire rate limit permission before making API call
    # Pass the interface name for per-interface rate limiting
    tushare_rate_limiter.acquire(interface=api_method)

    pro = _get_tushare_pro()

    for attempt in range(max_retries):
        try:
            # Get the API method and call it
            method = getattr(pro, api_method)
            result = method(**kwargs)

            # Check if result is valid
            if result is not None and not result.empty:
                return result

            # Empty result might be valid (no data for date range)
            return result

        except Exception as e:
            error_msg = str(e)

            # Check for rate limit error
            if "达到每分钟最高限制" in error_msg or "每分钟最多访问该接口" in error_msg or "rate limit" in error_msg.lower():
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    print(f"TuShare rate limit hit for {api_method}. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"TuShare rate limit exhausted for {api_method} after {max_retries} retries")
                    return None

            # Check for authentication error
            if "auth" in error_msg.lower() or "token" in error_msg.lower():
                print(f"TuShare authentication error: {error_msg}")
                return None

            # Other errors
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"TuShare API error: {error_msg}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"TuShare API {api_method} call failed after {max_retries} retries: {error_msg}")
                return None

    return None


def normalize_ts_code(stock_code: str) -> str:
    """
    Convert plain stock code to TuShare format with exchange suffix.

    Examples:
        600000 -> 600000.SH (Shanghai)
        000001 -> 000001.SZ (Shenzhen)
        300750 -> 300750.SZ (ChiNext)
        688001 -> 688001.SH (STAR Market)
        430001 -> 430001.BJ (Beijing)

    Args:
        stock_code: 6-digit stock code or code with suffix

    Returns:
        Stock code with TuShare exchange suffix
    """
    # Extract 6 digits
    code = "".join(ch for ch in str(stock_code) if ch.isdigit())

    if len(code) != 6:
        # If already has suffix, check if valid
        if '.' in stock_code:
            return stock_code.upper()
        return stock_code

    # Determine exchange
    if code.startswith('6'):
        return f"{code}.SH"  # Shanghai Stock Exchange
    elif code.startswith(('0', '3')):
        return f"{code}.SZ"  # Shenzhen Stock Exchange (including ChiNext 3xxxxx)
    elif code.startswith('8') or code.startswith('4'):
        return f"{code}.BJ"  # Beijing Stock Exchange

    return code


def denormalize_ts_code(ts_code: str) -> str:
    """
    Remove TuShare exchange suffix to get plain 6-digit code.

    Examples:
        600000.SH -> 600000
        000001.SZ -> 000001

    Args:
        ts_code: TuShare format code with suffix

    Returns:
        Plain 6-digit stock code
    """
    return ts_code.split('.')[0] if '.' in ts_code else ts_code


def map_tushare_columns_to_akshare(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    """
    Map TuShare column names to AkShare format for compatibility.

    Args:
        df: TuShare DataFrame
        mapping: Dict mapping TuShare column -> AkShare column

    Returns:
        DataFrame with renamed columns
    """
    if df is None or df.empty:
        return df

    # Only rename columns that exist in both mapping and dataframe
    rename_dict = {ts_col: ak_col for ts_col, ak_col in mapping.items() if ts_col in df.columns}

    if rename_dict:
        df = df.rename(columns=rename_dict)

    return df


# ============================================================================
# TuShare API Wrappers - Chinese Market Data
# ============================================================================

def get_stock_daily(ts_code: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
    """
    Get daily stock OHLCV data from TuShare.

    Args:
        ts_code: Stock code in TuShare format (e.g., '600000.SH')
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format

    Returns:
        DataFrame with columns: trade_date, open, high, low, close, vol, amount
    """
    ts_code = normalize_ts_code(ts_code)

    params = {'ts_code': ts_code}
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    df = tushare_call_with_retry('daily', **params)

    if df is not None and not df.empty:
        # Sort by date ascending
        df = df.sort_values('trade_date')

    return df


def get_moneyflow_hsgt(start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
    """
    Get northbound capital flow data (Shanghai/Shenzhen-Hong Kong Stock Connect).

    Args:
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format

    Returns:
        DataFrame with northbound flow data
    """
    params = {}
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    df = tushare_call_with_retry('moneyflow_hsgt', **params)

    return df


def get_index_daily(ts_code: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
    """
    Get daily index data from TuShare.

    Args:
        ts_code: Index code (e.g., '000001.SH' for Shanghai Composite)
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format

    Returns:
        DataFrame with index data
    """
    params = {'ts_code': ts_code}
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    df = tushare_call_with_retry('index_daily', **params)

    if df is not None and not df.empty:
        # Sort by date ascending
        df = df.sort_values('trade_date')

    return df


def get_fund_nav(ts_code: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
    """
    Get fund net asset value (NAV) data.

    Args:
        ts_code: Fund code in TuShare format
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format

    Returns:
        DataFrame with NAV data
    """
    params = {'ts_code': ts_code}
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    df = tushare_call_with_retry('fund_nav', **params)

    return df


def get_fund_portfolio(ts_code: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
    """
    Get fund portfolio holdings data.

    Args:
        ts_code: Fund code in TuShare format
        start_date: Start date in YYYYMMDD format (quarterly)
        end_date: End date in YYYYMMDD format (quarterly)

    Returns:
        DataFrame with portfolio holdings
    """
    params = {'ts_code': ts_code}
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    df = tushare_call_with_retry('fund_portfolio', **params)

    return df


def get_fund_basic(market: str = 'E') -> Optional[pd.DataFrame]:
    """
    Get basic information of all funds.

    Args:
        market: Market type (E=场内, O=场外)

    Returns:
        DataFrame with fund basic info
    """
    df = tushare_call_with_retry('fund_basic', market=market)

    return df


# ============================================================================
# Phase 5: Deep Migration - New APIs
# ============================================================================

def get_announcements_tushare(
    ts_code: str,
    start_date: str = None,
    end_date: str = None
) -> Optional[pd.DataFrame]:
    """
    Get company announcements.

    Requires 5000 points access (user has 5100).
    NOTE: This is an expensive API - use sparingly with aggressive caching!

    Args:
        ts_code: Stock code in TuShare format (e.g., '600000.SH')
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format

    Returns:
        DataFrame with announcement data: ann_date, title, ann_type, etc.
    """
    params = {'ts_code': normalize_ts_code(ts_code)}
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    df = tushare_call_with_retry('anns', **params)
    return df


def get_concept_detail_tushare(
    ts_code: str,
    trade_date: str = None
) -> Optional[pd.DataFrame]:
    """
    Get concept board constituent stocks and their performance.

    Requires 2000 points access (user has 5100).
    Used to analyze industry/sector capital flow.

    Args:
        ts_code: Concept code (e.g., 'BK0436' for semiconductors)
        trade_date: Trading date in YYYYMMDD format

    Returns:
        DataFrame with constituent stocks: ts_code, name, pct_chg, amount, etc.
    """
    params = {'id': ts_code}  # Note: concept_detail uses 'id' not 'ts_code'
    if trade_date:
        params['trade_date'] = trade_date

    df = tushare_call_with_retry('concept_detail', **params)
    return df


def get_ths_index_tushare(
    ts_code: str = None,
    exchange: str = None,
    start_date: str = None,
    end_date: str = None
) -> Optional[pd.DataFrame]:
    """
    Get THS (同花顺) sector index data.

    Requires 2000 points access (user has 5100).

    Args:
        ts_code: THS index code (e.g., '884001.TI' for semiconductors)
        exchange: Exchange code (TI for THS indices)
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format

    Returns:
        DataFrame with index data: trade_date, close, pct_change, etc.
    """
    params = {}
    if ts_code:
        params['ts_code'] = ts_code
    if exchange:
        params['exchange'] = exchange
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    df = tushare_call_with_retry('ths_index', **params)
    return df


def get_fx_daily_tushare(
    ts_code: str,
    start_date: str = None,
    end_date: str = None,
    exchange: str = None
) -> Optional[pd.DataFrame]:
    """
    Get daily foreign exchange rates.

    Requires 100 points access (user has 5100).

    Args:
        ts_code: Currency pair code (e.g., 'USDCNY.FX')
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        exchange: Exchange code (e.g., 'FX' for global, 'CFETS' for onshore)

    Returns:
        DataFrame with FX data: trade_date, open, high, low, close
    """
    params = {'ts_code': ts_code}
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date
    if exchange:
        params['exchange'] = exchange

    df = tushare_call_with_retry('fx_daily', **params)
    return df


def get_latest_trade_date(max_days_back: int = 30, offset: int = 0) -> Optional[str]:
    """
    Get the most recent trading day (for non-trading days).

    This function finds the latest trading day that is <= today.
    For example, if today is Saturday, it returns Friday's date.
    If offset > 0, it returns the trading day N days before the latest.

    Args:
        max_days_back: Maximum days to look back
        offset: Number of trading days to offset from the latest (0 = latest)

    Returns:
        Trade date in YYYYMMDD format, or None if not found
    """
    pro = _get_tushare_pro()

    try:
        today = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=max_days_back)).strftime('%Y%m%d')

        df = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=today)

        if df is not None and not df.empty:
            # Filter for trading days (is_open == 1)
            trade_days = df[df['is_open'] == 1].copy()

            if not trade_days.empty:
                # Sort by date descending to get most recent first
                trade_days = trade_days.sort_values('cal_date', ascending=False)

                # Find all trading days that are <= today
                valid_days = []
                for _, row in trade_days.iterrows():
                    cal_date = str(row['cal_date'])
                    if cal_date <= today:
                        valid_days.append(cal_date)

                if len(valid_days) > offset:
                    return valid_days[offset]

                # If not enough days found but we have some, return the oldest available
                if valid_days:
                    return valid_days[-1]

    except Exception as e:
        print(f"Error fetching latest trade date: {e}")

    return None


def get_moneyflow_ind_ths(
    trade_date: str = None
) -> Optional[pd.DataFrame]:
    """
    Get industry money flow from THS (同花顺行业资金流向).

    This API directly provides industry-level money flow data,
    which is more accurate and efficient than aggregating from stocks.

    Args:
        trade_date: Trade date in YYYYMMDD format (if None, uses latest trade date)

    Returns:
        DataFrame with columns: trade_date, name, pct_change, amount, net_mf_amount, etc.
    """
    # If no trade date provided, get latest trade date
    if not trade_date:
        trade_date = get_latest_trade_date()
        if not trade_date:
            trade_date = format_date_yyyymmdd()

    params = {'trade_date': trade_date}
    df = tushare_call_with_retry('moneyflow_ind_ths', **params)
    return df


def get_moneyflow_cnt_ths(
    trade_date: str = None
) -> Optional[pd.DataFrame]:
    """
    Get concept/sector money flow from THS (同花顺板块资金流向).

    This API directly provides sector/concept-level money flow data.

    Args:
        trade_date: Trade date in YYYYMMDD format (if None, uses latest trade date)

    Returns:
        DataFrame with columns: trade_date, name, pct_change, amount, net_mf_amount, etc.
    """
    # If no trade date provided, get latest trade date
    if not trade_date:
        trade_date = get_latest_trade_date()
        if not trade_date:
            trade_date = format_date_yyyymmdd()

    params = {'trade_date': trade_date}
    df = tushare_call_with_retry('moneyflow_cnt_ths', **params)
    return df


def sync_stock_basic() -> int:
    """
    Sync all A-share stock basic info from TuShare to local database.

    Fetches stock_basic for all exchanges (SSE, SZSE, BSE) and upserts to database.

    Returns:
        Number of stocks synced
    """
    from src.storage.db import upsert_stock_basic_batch

    pro = _get_tushare_pro()

    all_stocks = []

    # Fetch all listed stocks (L = Listed)
    print("Syncing stock basic info from TuShare...")

    try:
        df = pro.stock_basic(
            exchange='',
            list_status='L',
            fields='ts_code,symbol,name,area,industry,market,list_date,list_status'
        )

        if df is not None and not df.empty:
            stocks = df.to_dict('records')
            all_stocks.extend(stocks)
            print(f"  Fetched {len(stocks)} listed stocks")

    except Exception as e:
        print(f"Error fetching stock_basic: {e}")
        return 0

    # Also fetch delisted stocks for reference (optional, can skip if not needed)
    # try:
    #     df_d = pro.stock_basic(exchange='', list_status='D', fields='ts_code,symbol,name,area,industry,market,list_date,list_status')
    #     if df_d is not None and not df_d.empty:
    #         all_stocks.extend(df_d.to_dict('records'))
    # except:
    #     pass

    if not all_stocks:
        print("No stocks fetched from TuShare")
        return 0

    # Upsert to database
    count = upsert_stock_basic_batch(all_stocks)
    print(f"Synced {count} stocks to database")

    return count


def get_stock_basic_from_tushare(symbol: str = None) -> Optional[pd.DataFrame]:
    """
    Get stock basic info from TuShare.

    Args:
        symbol: Optional stock code filter

    Returns:
        DataFrame with stock basic info
    """
    pro = _get_tushare_pro()

    params = {
        'exchange': '',
        'list_status': 'L',
        'fields': 'ts_code,symbol,name,area,industry,market,list_date,list_status'
    }

    if symbol:
        params['ts_code'] = normalize_ts_code(symbol)

    df = tushare_call_with_retry('stock_basic', **params)
    return df


def sync_fund_basic() -> int:
    """
    Sync all fund basic info from TuShare to local database.

    Fetches fund_basic for both 场内(E) and 场外(O) markets and upserts to database.

    Returns:
        Number of funds synced
    """
    from src.storage.db import upsert_fund_basic_batch

    pro = _get_tushare_pro()

    all_funds = []

    print("Syncing fund basic info from TuShare...")

    # Fetch 场内基金 (Exchange-traded: ETF, LOF, etc.)
    try:
        df_e = pro.fund_basic(market='E')
        if df_e is not None and not df_e.empty:
            funds_e = df_e.to_dict('records')
            all_funds.extend(funds_e)
            print(f"  Fetched {len(funds_e)} exchange-traded funds (场内)")
    except Exception as e:
        print(f"Error fetching fund_basic (market=E): {e}")

    # Fetch 场外基金 (OTC: open-end funds)
    try:
        df_o = pro.fund_basic(market='O')
        if df_o is not None and not df_o.empty:
            funds_o = df_o.to_dict('records')
            all_funds.extend(funds_o)
            print(f"  Fetched {len(funds_o)} OTC funds (场外)")
    except Exception as e:
        print(f"Error fetching fund_basic (market=O): {e}")

    if not all_funds:
        print("No funds fetched from TuShare")
        return 0

    # Upsert to database
    count = upsert_fund_basic_batch(all_funds)
    print(f"Synced {count} funds to database")

    return count


# ============================================================================
# Health Check & Testing
# ============================================================================

def test_connection() -> bool:
    """
    Test TuShare API connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        pro = _get_tushare_pro()

        # Try to fetch trade calendar for today
        today = datetime.now().strftime('%Y%m%d')
        df = pro.trade_cal(exchange='SSE', start_date=today, end_date=today)

        if df is not None:
            print("✅ TuShare connection successful!")
            return True
        else:
            print("❌ TuShare connection failed: No data returned")
            return False

    except Exception as e:
        print(f"❌ TuShare connection failed: {e}")
        return False


# ============================================================================
# Stock Professional Features - Financial, Shareholder, Margin, Events, Quant
# ============================================================================

def get_financial_indicators(ts_code: str, periods: int = 8) -> Optional[pd.DataFrame]:
    """
    Get financial indicators (ROE, net profit margin, asset-liability ratio, etc.).

    Requires 2000 points access.

    Args:
        ts_code: Stock code in TuShare format (e.g., '600000.SH')
        periods: Number of periods to fetch (default 8 quarters)

    Returns:
        DataFrame with financial indicators: roe, netprofit_margin, debt_to_assets, grossprofit_margin, etc.
    """
    ts_code = normalize_ts_code(ts_code)

    df = tushare_call_with_retry(
        'fina_indicator',
        ts_code=ts_code,
        fields='ts_code,ann_date,end_date,roe,roe_waa,roa,npta,profit_dedt,op_yoy,ebt_yoy,netprofit_margin,grossprofit_margin,debt_to_assets,current_ratio,quick_ratio,ocfps,bps,cfps,eps'
    )

    if df is not None and not df.empty:
        # Sort by end_date descending and limit to requested periods
        df = df.sort_values('end_date', ascending=False).head(periods)

    return df


def get_income_statement(ts_code: str, periods: int = 4) -> Optional[pd.DataFrame]:
    """
    Get income statement data.

    Requires 5000 points access.

    Args:
        ts_code: Stock code in TuShare format
        periods: Number of periods to fetch (default 4 quarters)

    Returns:
        DataFrame with income statement: revenue, n_income, sell_exp, admin_exp, fin_exp, etc.
    """
    ts_code = normalize_ts_code(ts_code)

    df = tushare_call_with_retry(
        'income',
        ts_code=ts_code,
        fields='ts_code,ann_date,f_ann_date,end_date,report_type,total_revenue,revenue,total_cogs,oper_cost,sell_exp,admin_exp,fin_exp,operate_profit,total_profit,income_tax,n_income,n_income_attr_p'
    )

    if df is not None and not df.empty:
        # Filter for consolidated reports (report_type = 1) and sort by end_date descending
        df = df[df['report_type'] == '1'].sort_values('end_date', ascending=False).head(periods)

    return df


def get_balance_sheet(ts_code: str, periods: int = 4) -> Optional[pd.DataFrame]:
    """
    Get balance sheet data.

    Requires 5000 points access.

    Args:
        ts_code: Stock code in TuShare format
        periods: Number of periods to fetch

    Returns:
        DataFrame with balance sheet: total_assets, total_liab, total_hldr_eqy_exc_min_int, etc.
    """
    ts_code = normalize_ts_code(ts_code)

    df = tushare_call_with_retry(
        'balancesheet',
        ts_code=ts_code,
        fields='ts_code,ann_date,end_date,report_type,total_assets,total_liab,total_hldr_eqy_exc_min_int,cap_rese,undistr_porfit,money_cap,trad_asset,notes_receiv,accounts_receiv,inventories,fix_assets,total_cur_assets,total_cur_liab,total_nca,total_ncl'
    )

    if df is not None and not df.empty:
        df = df[df['report_type'] == '1'].sort_values('end_date', ascending=False).head(periods)

    return df


def get_cashflow_statement(ts_code: str, periods: int = 4) -> Optional[pd.DataFrame]:
    """
    Get cash flow statement data.

    Requires 5000 points access.

    Args:
        ts_code: Stock code in TuShare format
        periods: Number of periods to fetch

    Returns:
        DataFrame with cash flow: n_cashflow_act, n_cashflow_inv_act, n_cash_flows_fnc_act, etc.
    """
    ts_code = normalize_ts_code(ts_code)

    df = tushare_call_with_retry(
        'cashflow',
        ts_code=ts_code,
        fields='ts_code,ann_date,end_date,report_type,n_cashflow_act,n_cashflow_inv_act,n_cash_flows_fnc_act,c_fr_sale_sg,c_pay_for_tax,free_cashflow'
    )

    if df is not None and not df.empty:
        df = df[df['report_type'] == '1'].sort_values('end_date', ascending=False).head(periods)

    return df


def get_top10_holders(ts_code: str, periods: int = 4) -> Optional[pd.DataFrame]:
    """
    Get top 10 shareholders data.

    Requires 2000 points access.

    Args:
        ts_code: Stock code in TuShare format
        periods: Number of report periods to fetch

    Returns:
        DataFrame with top 10 holders: holder_name, hold_amount, hold_ratio
    """
    ts_code = normalize_ts_code(ts_code)

    df = tushare_call_with_retry(
        'top10_holders',
        ts_code=ts_code
    )

    if df is not None and not df.empty:
        # Get unique end_dates and take latest N periods
        end_dates = df['end_date'].unique()
        end_dates = sorted(end_dates, reverse=True)[:periods]
        df = df[df['end_date'].isin(end_dates)]

    return df


def get_shareholder_number(ts_code: str, periods: int = 12) -> Optional[pd.DataFrame]:
    """
    Get shareholder number trend data.

    Requires 2000 points access.

    Args:
        ts_code: Stock code in TuShare format
        periods: Number of periods to fetch

    Returns:
        DataFrame with shareholder count: end_date, holder_num, holder_num_change
    """
    ts_code = normalize_ts_code(ts_code)

    df = tushare_call_with_retry(
        'stk_holdernumber',
        ts_code=ts_code
    )

    if df is not None and not df.empty:
        df = df.sort_values('end_date', ascending=False).head(periods)
        # Calculate change percentage
        if 'holder_num' in df.columns:
            df['holder_num_pct_change'] = df['holder_num'].pct_change(-1) * 100

    return df


def get_margin_detail(ts_code: str, days: int = 30) -> Optional[pd.DataFrame]:
    """
    Get margin trading data (融资融券).

    Requires 2000 points access.

    Args:
        ts_code: Stock code in TuShare format
        days: Number of days to fetch

    Returns:
        DataFrame with margin data: rzye (financing balance), rqye (securities lending balance), etc.
    """
    ts_code = normalize_ts_code(ts_code)

    end_date = format_date_yyyymmdd()
    start_date = format_date_yyyymmdd(datetime.now() - timedelta(days=days + 10))  # Extra buffer for non-trading days

    df = tushare_call_with_retry(
        'margin_detail',
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date
    )

    if df is not None and not df.empty:
        df = df.sort_values('trade_date', ascending=False).head(days)

    return df


def get_forecast(ts_code: str) -> Optional[pd.DataFrame]:
    """
    Get earnings forecast data.

    Requires 2000 points access.

    Args:
        ts_code: Stock code in TuShare format

    Returns:
        DataFrame with forecast: type (预增/预减/续亏/扭亏/etc), p_change_min, p_change_max
    """
    ts_code = normalize_ts_code(ts_code)

    df = tushare_call_with_retry(
        'forecast',
        ts_code=ts_code
    )

    if df is not None and not df.empty:
        df = df.sort_values('ann_date', ascending=False)

    return df


def get_share_float(ts_code: str) -> Optional[pd.DataFrame]:
    """
    Get share unlock (限售解禁) schedule.

    Requires 2000 points access.

    Args:
        ts_code: Stock code in TuShare format

    Returns:
        DataFrame with unlock schedule: ann_date, float_date, float_share, float_ratio
    """
    ts_code = normalize_ts_code(ts_code)

    df = tushare_call_with_retry(
        'share_float',
        ts_code=ts_code
    )

    if df is not None and not df.empty:
        df = df.sort_values('float_date', ascending=False)

    return df


def get_dividend(ts_code: str) -> Optional[pd.DataFrame]:
    """
    Get dividend distribution history.

    Requires 2000 points access.

    Args:
        ts_code: Stock code in TuShare format

    Returns:
        DataFrame with dividend info: end_date, div_proc (实施进度), cash_div_tax (每股现金分红), ex_date, record_date
    """
    ts_code = normalize_ts_code(ts_code)

    df = tushare_call_with_retry(
        'dividend',
        ts_code=ts_code,
        fields='ts_code,end_date,ann_date,div_proc,stk_div,stk_bo_rate,stk_co_rate,cash_div,cash_div_tax,record_date,ex_date,pay_date,div_listdate'
    )

    if df is not None and not df.empty:
        df = df.sort_values('end_date', ascending=False)

    return df


def get_stock_factors(ts_code: str, days: int = 60) -> Optional[pd.DataFrame]:
    """
    Get technical factors (MACD, KDJ, RSI, BOLL).

    Requires 5000 points access.

    Args:
        ts_code: Stock code in TuShare format
        days: Number of trading days to fetch

    Returns:
        DataFrame with factors: macd_dif, macd_dea, macd, kdj_k, kdj_d, kdj_j, rsi_6, rsi_12, rsi_24, boll_upper, boll_mid, boll_lower
    """
    ts_code = normalize_ts_code(ts_code)

    end_date = format_date_yyyymmdd()
    start_date = format_date_yyyymmdd(datetime.now() - timedelta(days=days + 20))

    df = tushare_call_with_retry(
        'stk_factor',
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields='ts_code,trade_date,close,macd_dif,macd_dea,macd,kdj_k,kdj_d,kdj_j,rsi_6,rsi_12,rsi_24,boll_upper,boll_mid,boll_lower'
    )

    if df is not None and not df.empty:
        df = df.sort_values('trade_date', ascending=False).head(days)

    return df


def get_chip_performance(ts_code: str) -> Optional[pd.DataFrame]:
    """
    Get chip distribution and cost analysis (筹码成本分析).

    Requires 5000 points access.

    Args:
        ts_code: Stock code in TuShare format

    Returns:
        DataFrame with chip performance: his_low, his_high, cost_5pct, cost_15pct, cost_50pct, cost_85pct, cost_95pct, weight_avg, winner_rate
    """
    ts_code = normalize_ts_code(ts_code)

    end_date = format_date_yyyymmdd()
    start_date = format_date_yyyymmdd(datetime.now() - timedelta(days=30))

    df = tushare_call_with_retry(
        'cyq_perf',
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date
    )

    if df is not None and not df.empty:
        df = df.sort_values('trade_date', ascending=False)

    return df


def get_realtime_quotes(ts_codes: list) -> Optional[pd.DataFrame]:
    """
    Get real-time stock quotes for multiple stocks.

    This uses tushare's realtime quote API which provides current market data.

    Args:
        ts_codes: List of stock codes (can be plain codes like '600519' or with suffix like '600519.SH')

    Returns:
        DataFrame with realtime data: ts_code, name, price, pct_chg, vol, amount, etc.
    """
    import tushare as ts

    if not ts_codes:
        return None

    # Explicitly set token to avoid "Please set tushare pro token credentials" error
    # even though realtime_quote is technically a legacy API.
    if TUSHARE_API_TOKEN:
        try:
            ts.set_token(TUSHARE_API_TOKEN)
        except Exception:
            pass

    # Normalize codes - tushare realtime needs plain codes without suffix
    plain_codes = []
    for code in ts_codes:
        plain_code = denormalize_ts_code(code)
        plain_codes.append(plain_code)

    try:
        # Use tushare's realtime_quote function (free API, no points required)
        # This returns DataFrame with columns: TS_CODE, NAME, PRICE, PCT_CHG, VOL, etc.
        df = ts.realtime_quote(ts_code=','.join(plain_codes))

        if df is not None and not df.empty:
            # Normalize column names to lowercase for consistency
            df.columns = [col.lower() for col in df.columns]
            return df

        return df

    except BaseException as e:
        print(f"Error fetching realtime quotes: {e}")
        return None


def get_realtime_quote_single(stock_code: str) -> Optional[Dict[str, Any]]:
    """
    Get real-time quote for a single stock.

    Args:
        stock_code: Stock code (plain or with suffix)

    Returns:
        Dict with quote data: price, pct_chg, vol, amount, open, high, low, pre_close
    """
    df = get_realtime_quotes([stock_code])

    if df is None or df.empty:
        return None

    row = df.iloc[0]

    return {
        'ts_code': row.get('ts_code', ''),
        'name': row.get('name', ''),
        'price': float(row.get('price', 0)) if pd.notna(row.get('price')) else None,
        'pct_chg': float(row.get('pct_chg', 0)) if pd.notna(row.get('pct_chg')) else None,
        'vol': float(row.get('vol', 0)) if pd.notna(row.get('vol')) else None,
        'amount': float(row.get('amount', 0)) if pd.notna(row.get('amount')) else None,
        'open': float(row.get('open', 0)) if pd.notna(row.get('open')) else None,
        'high': float(row.get('high', 0)) if pd.notna(row.get('high')) else None,
        'low': float(row.get('low', 0)) if pd.notna(row.get('low')) else None,
        'pre_close': float(row.get('pre_close', 0)) if pd.notna(row.get('pre_close')) else None,
    }


# Fund search cache
_fund_basic_cache: Optional[pd.DataFrame] = None
_fund_basic_cache_time: Optional[datetime] = None


def get_all_funds_tushare(market: str = 'E') -> Optional[pd.DataFrame]:
    """
    Get all fund basic info from TuShare with caching.

    Args:
        market: Market type (E=场内ETF/LOF, O=场外)

    Returns:
        DataFrame with fund basic info: ts_code, name, management, type, etc.
    """
    global _fund_basic_cache, _fund_basic_cache_time

    # Check cache (valid for 24 hours)
    if _fund_basic_cache is not None and _fund_basic_cache_time is not None:
        cache_age = (datetime.now() - _fund_basic_cache_time).total_seconds()
        if cache_age < 86400:  # 24 hours
            return _fund_basic_cache

    try:
        pro = _get_tushare_pro()

        # Fetch both on-exchange (E) and off-exchange (O) funds
        dfs = []

        for m in ['E', 'O']:
            try:
                df = pro.fund_basic(
                    market=m,
                    fields='ts_code,name,management,custodian,fund_type,found_date,due_date,list_date,issue_date,delist_date,issue_amount,m_fee,c_fee,duration,min_amount,exp_return,benchmark,status,invest_type,type,trustee,purc_startdate,redm_startdate,market'
                )
                if df is not None and not df.empty:
                    dfs.append(df)
            except Exception as e:
                print(f"Failed to fetch fund_basic for market {m}: {e}")

        if dfs:
            _fund_basic_cache = pd.concat(dfs, ignore_index=True)
            _fund_basic_cache_time = datetime.now()
            return _fund_basic_cache

        return None

    except Exception as e:
        print(f"Error fetching fund basic: {e}")
        return None


def search_funds_tushare(query: str, limit: int = 50) -> list:
    """
    Search funds by code or name using TuShare data.

    Args:
        query: Search query (fund code or name)
        limit: Maximum number of results

    Returns:
        List of fund dicts with code, name, type fields
    """
    if not query or len(query) < 2:
        return []

    df = get_all_funds_tushare()

    if df is None or df.empty:
        return []

    query_lower = query.lower()
    results = []

    for _, row in df.iterrows():
        ts_code = str(row.get('ts_code', ''))
        name = str(row.get('name', ''))
        fund_type = str(row.get('fund_type', '')) or str(row.get('type', ''))

        # Extract plain code (remove .OF/.SH/.SZ suffix)
        plain_code = ts_code.split('.')[0] if '.' in ts_code else ts_code

        # Match by code prefix or name contains
        if plain_code.startswith(query) or query_lower in name.lower():
            results.append({
                'code': plain_code,
                'name': name,
                'type': fund_type,
                'ts_code': ts_code,
            })

            if len(results) >= limit:
                break

    return results


if __name__ == "__main__":
    # Test the connection
    print("Testing TuShare Pro connection...")
    test_connection()

    # Test stock data fetch
    print("\nTesting stock data fetch (600000.SH - 浦发银行)...")
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')

    df = get_stock_daily('600000', start_date=start_date, end_date=end_date)
    if df is not None and not df.empty:
        print(f"✅ Fetched {len(df)} days of data")
        print(df.head())
    else:
        print("❌ Failed to fetch stock data")
