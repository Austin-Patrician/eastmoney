"""
Data Source Manager - Multi-Source Routing Layer

Routes data requests to appropriate providers:
- TuShare Pro: Chinese market data (stocks, funds, indices)
- yFinance: US market data (Dow, NASDAQ, S&P 500)
- AkShare: Fallback and real-time quotes

Implements caching and fallback logic for reliability.
"""

import time
import pandas as pd
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from config.settings import DATA_SOURCE_PROVIDER, DATA_SOURCE_CACHE_TTL

# Import clients
from src.data_sources import tushare_client, yfinance_client
from src.data_sources.utils import (
    normalize_stock_code,
    add_exchange_suffix,
    remove_exchange_suffix,
    format_date_yyyymmdd,
    get_trading_date_range,
)

# Phase 5: Import rate limiter and circuit breaker
from src.data_sources.rate_limiter import rate_limiter
from src.data_sources.circuit_breaker import circuit_breaker
from src.data_sources.sector_mappings import get_concept_code, get_ths_code

# Simple in-memory cache
_cache = {}
_cache_timestamps = {}


def _get_from_cache(key: str, ttl: int = DATA_SOURCE_CACHE_TTL) -> Optional[any]:
    """Get value from cache if not expired."""
    if key not in _cache:
        return None

    timestamp = _cache_timestamps.get(key, 0)
    if time.time() - timestamp > ttl:
        # Expired
        del _cache[key]
        del _cache_timestamps[key]
        return None

    return _cache[key]


def _set_cache(key: str, value: any):
    """Set value in cache with current timestamp."""
    _cache[key] = value
    _cache_timestamps[key] = time.time()


def _call_with_fallback(
    primary_func: Callable,
    fallback_func: Callable,
    cache_key: str = None,
    use_cache: bool = True,
    **kwargs
) -> any:
    """
    Call primary function, fallback to secondary if it fails.
    Optionally use caching.
    """
    # Try cache first
    if use_cache and cache_key:
        cached = _get_from_cache(cache_key)
        if cached is not None:
            return cached

    # Try primary
    try:
        result = primary_func(**kwargs)
        if result is not None:
            if use_cache and cache_key:
                _set_cache(cache_key, result)
            return result
    except Exception as e:
        print(f"Primary data source failed: {e}")

    # Fallback
    try:
        result = fallback_func(**kwargs)
        if result is not None and use_cache and cache_key:
            _set_cache(cache_key, result)
        return result
    except Exception as e:
        print(f"Fallback data source failed: {e}")
        return None


# ============================================================================
# US Market Data - Route to yFinance (Priority per plan)
# ============================================================================

def get_us_market_overview_from_yfinance() -> Dict:
    """
    Get US market overview (Dow, NASDAQ, S&P 500) from yFinance.
    This is the PRIMARY source for US market data per Phase 3 priority.
    """
    cache_key = "us_market_yfinance"
    cached = _get_from_cache(cache_key, ttl=30)  # 30s cache for real-time data
    if cached:
        return cached

    try:
        result = yfinance_client.get_us_market_data()
        if result:
            _set_cache(cache_key, result)
            return result
    except Exception as e:
        print(f"yFinance US market fetch failed: {e}")

    return {"说明": "美股数据暂时无法获取"}


# ============================================================================
# Chinese Stock Data - TuShare with AkShare Fallback
# ============================================================================

def get_stock_history_from_tushare(code: str, days: int = 100) -> List[Dict]:
    """
    Get stock history from TuShare.

    Args:
        code: Stock code (6 digits)
        days: Number of days to fetch

    Returns:
        List of dicts with date, value, volume
    """
    try:
        ts_code = add_exchange_suffix(code)
        start_date, end_date = get_trading_date_range(days)

        df = tushare_client.get_stock_daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

        if df is None or df.empty:
            return []

        # Convert to AkShare format
        result = []
        for _, row in df.iterrows():
            result.append({
                "date": str(row['trade_date']),
                "value": float(row['close']),
                "volume": float(row['vol'])
            })

        return result

    except Exception as e:
        print(f"TuShare stock history failed for {code}: {e}")
        return []


# ============================================================================
# Northbound Capital Flow - TuShare
# ============================================================================

def _safe_float(value, default=0.0) -> float:
    """Safely convert value to float, return default if None or invalid."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def get_northbound_flow_from_tushare() -> Dict:
    """
    Get northbound capital flow data from TuShare.

    TuShare moneyflow_hsgt returns columns:
    - trade_date: 交易日期
    - ggt_ss: 港股通(沪)
    - ggt_sz: 港股通(深)
    - hgt: 沪股通(百万元)
    - sgt: 深股通(百万元)
    - north_money: 北向资金(百万元)
    - south_money: 南向资金(百万元)

    Returns:
        Dict with northbound flow summary
    """
    try:
        # Use get_latest_trade_date to ensure we get the correct trading day
        trade_date = tushare_client.get_latest_trade_date(max_days_back=10)
        if not trade_date:
            print("Could not determine latest trade date")
            return {}

        # Get data for a range ending at the latest trade date
        end_date = trade_date
        # Calculate start_date as 10 days before end_date
        from datetime import datetime, timedelta
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        start_date = (end_dt - timedelta(days=10)).strftime('%Y%m%d')

        df = tushare_client.get_moneyflow_hsgt(
            start_date=start_date,
            end_date=end_date
        )

        if df is None or df.empty:
            return {}

        # Get latest day
        latest = df.sort_values('trade_date', ascending=False).iloc[0]

        # Safely extract values with None handling
        # Values are in 百万元 (millions), convert to 亿 (100 millions)
        hgt = _safe_float(latest.get('hgt')) / 100  # 沪股通 (百万 -> 亿)
        sgt = _safe_float(latest.get('sgt')) / 100  # 深股通 (百万 -> 亿)
        north_money = _safe_float(latest.get('north_money')) / 100  # 北向资金 (百万 -> 亿)

        result = {
            '数据日期': str(latest['trade_date']),
            '沪股通': {
                '成交净买额': f"{hgt:.2f}亿"
            },
            '深股通': {
                '成交净买额': f"{sgt:.2f}亿"
            },
            '最新净流入': f"{north_money:.2f}亿"
        }

        # Calculate 5-day cumulative
        if len(df) >= 5:
            recent_5 = df.sort_values('trade_date', ascending=False).head(5)
            # Handle None values in sum, convert from 百万 to 亿
            total_5d = recent_5['north_money'].fillna(0).sum() / 100
            result['5日累计净流入'] = f"{_safe_float(total_5d):.2f}亿"

        return result

    except Exception as e:
        print(f"TuShare northbound flow failed: {e}")
        import traceback
        traceback.print_exc()
        return {}


# ============================================================================
# Market Indices - TuShare (Dict format for internal use)
# ============================================================================

def _get_market_indices_dict_from_tushare() -> Dict:
    """
    Get Chinese market indices from TuShare (internal Dict format).

    Returns:
        Dict mapping index name to market data
    """
    indices = {
        "000001.SH": "上证指数",
        "399006.SZ": "创业板指数",
    }

    market_data = {}

    try:
        # Use get_latest_trade_date to get correct trading day
        trade_date = tushare_client.get_latest_trade_date(max_days_back=10)
        if not trade_date:
            return {}

        # Get a few days of data for change calculation
        end_dt = datetime.strptime(trade_date, '%Y%m%d')
        start_date = (end_dt - timedelta(days=5)).strftime('%Y%m%d')
        end_date = trade_date

        for ts_code, name in indices.items():
            df = tushare_client.get_index_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

            if df is None or df.empty:
                continue

            # Sort by date and get latest
            df_sorted = df.sort_values('trade_date', ascending=True)
            latest = df_sorted.iloc[-1]

            pct_change = None
            if len(df_sorted) >= 2:
                prev = df_sorted.iloc[-2]
                try:
                    pct_change = (_safe_float(latest['close']) / _safe_float(prev['close']) - 1.0) * 100.0
                except:
                    pass

            market_data[name] = {
                '日期': str(latest['trade_date']),
                '收盘': _safe_float(latest['close']),
                '涨跌幅': round(pct_change, 2) if pct_change is not None else 'N/A',
            }

        return market_data

    except Exception as e:
        print(f"TuShare market indices failed: {e}")
        import traceback
        traceback.print_exc()
        return {}


# ============================================================================
# Fund Data - TuShare
# ============================================================================

def get_fund_info_from_tushare(fund_code: str) -> pd.DataFrame:
    """
    Get fund NAV (net asset value) history from TuShare.

    Args:
        fund_code: Fund code (6 digits)

    Returns:
        DataFrame with NAV history
    """
    try:
        # TuShare fund codes need suffix.
        # If 6 digits, assume .OF (Open Fund) as default for funds.
        # Some ETFs might use .SH/.SZ, but this function is often used for open funds.
        # Check if already has suffix
        if len(fund_code) == 6 and fund_code.isdigit():
             ts_code = f"{fund_code}.OF"
        else:
             ts_code = fund_code

        end_date = format_date_yyyymmdd()
        start_date = format_date_yyyymmdd(datetime.now() - timedelta(days=365))

        df = tushare_client.get_fund_nav(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        
        # If .OF failed, maybe it's an ETF? Try without suffix (let tushare_client.normalize handle it if it was a stock, but get_fund_nav expects specific fund code)
        # Actually tushare_client.get_fund_nav just passes ts_code.
        # If it failed (empty), we could try other suffixes, but let's stick to .OF first.
        
        if df is None or df.empty:
             # Try .SH or .SZ if .OF failed?
             # But for now, just return empty if failed.
             pass

        if df is None or df.empty:
            return pd.DataFrame()

        # Map TuShare columns to AkShare format
        # TuShare: nav_date (not end_date), unit_nav, accum_nav
        # AkShare: 净值日期, 单位净值, 日增长率

        df = df.rename(columns={
            'nav_date': '净值日期',
            'unit_nav': '单位净值',
        })

        # Calculate daily change rate
        if '单位净值' in df.columns:
            # Sort by date ascending to calculate pct_change correctly
            df = df.sort_values('净值日期', ascending=True)
            df['日增长率'] = df['单位净值'].pct_change() * 100

        # Sort by date descending for return
        df = df.sort_values('净值日期', ascending=False).reset_index(drop=True)

        return df[['净值日期', '单位净值', '日增长率']]

    except Exception as e:
        print(f"TuShare fund info failed for {fund_code}: {e}")
        return pd.DataFrame()


def get_fund_holdings_from_tushare(fund_code: str, year: str = None) -> pd.DataFrame:
    """
    Get fund holdings from TuShare.

    Args:
        fund_code: Fund code (6 digits)
        year: Year (YYYY format), defaults to current year

    Returns:
        DataFrame with holdings data
    """
    try:
        if not year:
            year = str(datetime.now().year)

        # TuShare uses quarterly dates (YYYYMMDD format for quarter end)
        # Q1: 0331, Q2: 0630, Q3: 0930, Q4: 1231
        end_date = f"{year}1231"
        start_date = f"{year}0101"

        df = tushare_client.get_fund_portfolio(
            ts_code=fund_code,
            start_date=start_date,
            end_date=end_date
        )

        if df is None or df.empty:
            # Try previous year if current year is empty
            if year == str(datetime.now().year):
                prev_year = str(int(year) - 1)
                return get_fund_holdings_from_tushare(fund_code, prev_year)

        return df

    except Exception as e:
        print(f"TuShare fund holdings failed for {fund_code}: {e}")
        return pd.DataFrame()


# ============================================================================
# Phase 5: Deep Migration Functions
# ============================================================================

def get_stock_announcements_from_tushare(stock_code: str, limit: int = 5) -> List[Dict]:
    """
    Get company announcements from TuShare with rate limiting and caching.

    EXPENSIVE API: 5000 points (but points are access level, not consumable).
    Real concern: rate limiting (120 calls/min).

    Strategy:
    - Cache for 2 hours (announcements don't change frequently)
    - Batch fetch last 30 days per call
    - Rate limiting with circuit breaker
    - Fallback to AkShare on any failure

    Args:
        stock_code: Stock code (6 digits)
        limit: Number of announcements to return

    Returns:
        List of announcement dicts
    """
    from src.cache.cache_manager import cache_manager

    # Cache key (2 hour granularity to reduce API calls)
    now = datetime.now()
    cache_key = f"anns:{stock_code}:{now.strftime('%Y%m%d_%H')}"

    # Try cache first
    try:
        cached = cache_manager.get(cache_key)
        if cached:
            return cached[:limit]
    except Exception as e:
        print(f"Cache read error: {e}")

    # Check circuit breaker
    if circuit_breaker.is_open('anns'):
        print("⚠️  Circuit breaker OPEN for anns API, using fallback")
        return []

    # Rate limiting (non-blocking check)
    if not rate_limiter.acquire('anns'):
        print("⚠️  Rate limit reached for anns API, using fallback")
        return []

    try:
        # Batch fetch last 30 days
        end_date = format_date_yyyymmdd()
        start_date = format_date_yyyymmdd(datetime.now() - timedelta(days=30))

        df = tushare_client.get_announcements_tushare(
            stock_code,
            start_date=start_date,
            end_date=end_date
        )

        if df is None or df.empty:
            circuit_breaker.record_failure('anns')
            return []

        circuit_breaker.record_success('anns')

        # Map to AkShare-compatible format
        result = []
        for _, row in df.sort_values('ann_date', ascending=False).iterrows():
            result.append({
                '公告时间': str(row['ann_date']),
                '公告标题': row.get('title', ''),
                '公告类型': row.get('ann_type', ''),
                '网址': f"http://www.cninfo.com.cn/new/disclosure/detail?stockCode={stock_code}"
            })

        # Cache for 2 hours
        try:
            cache_manager.set(cache_key, result, ttl=7200)
        except Exception as e:
            print(f"Cache write error: {e}")

        return result[:limit]

    except Exception as e:
        print(f"TuShare announcements failed for {stock_code}: {e}")
        circuit_breaker.record_failure('anns')
        return []


def get_industry_capital_flow_from_tushare(industry: str = None) -> Dict:
    """
    Get industry capital flow using TuShare moneyflow_ind_ths API (同花顺行业资金流向).

    This API directly provides industry-level money flow data,
    which is more accurate and efficient than aggregating from stocks.

    Strategy:
    - Use moneyflow_ind_ths API for direct industry flow data
    - Automatically handles non-trading days (gets latest trade date)
    - Cache for 1 hour
    - Fallback to AkShare if API fails

    Args:
        industry: Industry name in Chinese (e.g., "半导体", "新能源车")

    Returns:
        Dict with industry flow data
    """
    from src.cache.cache_manager import cache_manager

    if not industry:
        return {}

    # Cache key (1 hour granularity)
    now = datetime.now()
    cache_key = f"industry_flow_ths:{industry}:{now.strftime('%Y%m%d_%H')}"

    # Try cache
    try:
        cached = cache_manager.get(cache_key)
        if cached:
            return cached
    except Exception as e:
        print(f"Cache read error: {e}")

    # Check circuit breaker
    if circuit_breaker.is_open('moneyflow_ind_ths'):
        return {}

    # Rate limiting
    if not rate_limiter.acquire('moneyflow_ind_ths'):
        print("⚠️  Rate limit reached for moneyflow_ind_ths API")
        return {}

    try:
        # Get industry flow data (automatically gets latest trade date)
        df = tushare_client.get_moneyflow_ind_ths()

        if df is None or df.empty:
            circuit_breaker.record_failure('moneyflow_ind_ths')
            return {}

        # Find the requested industry
        industry_row = df[df['name'].str.contains(industry, na=False, regex=False)]

        if industry_row.empty:
            # Try fuzzy match if exact match fails
            print(f"Industry '{industry}' not found, trying fallback...")
            circuit_breaker.record_success('moneyflow_ind_ths')
            return {}

        circuit_breaker.record_success('moneyflow_ind_ths')

        # Get the first match
        row = industry_row.iloc[0]

        # Build result
        result = {
            '行业名称': row['name'],
            '涨跌幅': f"{_safe_float(row.get('pct_change')):.2f}%",
            '净流入': f"{_safe_float(row.get('net_mf_amount')) / 100000000:.2f}亿元",
            '成交额': f"{_safe_float(row.get('amount')) / 100000000:.2f}亿元",
            '交易日期': str(row.get('trade_date', '')),
        }

        # Cache for 1 hour
        try:
            cache_manager.set(cache_key, result, ttl=3600)
        except Exception as e:
            print(f"Cache write error: {e}")

        return result

    except Exception as e:
        print(f"TuShare moneyflow_ind_ths failed for {industry}: {e}")
        circuit_breaker.record_failure('moneyflow_ind_ths')
        return {}


def get_sector_performance_ths_from_tushare(sector_name: str) -> Dict:
    """
    Get THS (同花顺) sector/concept performance using moneyflow_cnt_ths API (同花顺板块资金流向).

    This API directly provides sector-level money flow and performance data,
    which is more accurate and efficient than using index data.

    Strategy:
    - Use moneyflow_cnt_ths API for direct sector flow data
    - Automatically handles non-trading days (gets latest trade date)
    - Cache for 30 minutes
    - Fallback to AkShare if API fails

    Args:
        sector_name: Sector name in Chinese (e.g., "半导体", "新能源车")

    Returns:
        Dict with sector performance data
    """
    from src.cache.cache_manager import cache_manager

    if not sector_name:
        return {}

    # Cache key (30 minute granularity for frequent updates)
    now = datetime.now()
    cache_key = f"sector_flow_ths:{sector_name}:{now.strftime('%Y%m%d_%H%M')[:-1]}0"  # Round to 10 min

    # Try cache
    try:
        cached = cache_manager.get(cache_key)
        if cached:
            return cached
    except Exception as e:
        print(f"Cache read error: {e}")

    # Check circuit breaker
    if circuit_breaker.is_open('moneyflow_cnt_ths'):
        return {}

    # Rate limiting
    if not rate_limiter.acquire('moneyflow_cnt_ths'):
        print("⚠️  Rate limit reached for moneyflow_cnt_ths API")
        return {}

    try:
        # Get sector flow data (automatically gets latest trade date)
        df = tushare_client.get_moneyflow_cnt_ths()

        if df is None or df.empty:
            circuit_breaker.record_failure('moneyflow_cnt_ths')
            return {}

        # Find the requested sector
        sector_row = df[df['name'].str.contains(sector_name, na=False, regex=False)]

        if sector_row.empty:
            # Try fuzzy match if exact match fails
            print(f"Sector '{sector_name}' not found, trying fallback...")
            circuit_breaker.record_success('moneyflow_cnt_ths')
            return {}

        circuit_breaker.record_success('moneyflow_cnt_ths')

        # Get the first match
        row = sector_row.iloc[0]

        # Build result
        result = {
            '板块名称': row['name'],
            '涨跌幅': f"{_safe_float(row.get('pct_change')):.2f}%",
            '净流入': f"{_safe_float(row.get('net_mf_amount')) / 100000000:.2f}亿元",
            '成交额': f"{_safe_float(row.get('amount')) / 100000000:.2f}亿元",
            '交易日期': str(row.get('trade_date', '')),
        }

        # Cache for 30 minutes
        try:
            cache_manager.set(cache_key, result, ttl=1800)
        except Exception as e:
            print(f"Cache write error: {e}")

        return result

    except Exception as e:
        print(f"TuShare moneyflow_cnt_ths failed for {sector_name}: {e}")
        circuit_breaker.record_failure('moneyflow_cnt_ths')
        return {}
        return {}


def get_forex_rates_from_tushare() -> Dict:
    """
    Get forex rates from TuShare (daily EOD data).

    Requires 100 points access (user has 5100).

    Strategy:
    - Fetch latest 2 days to ensure we get recent data
    - Use for historical/EOD rates
    - Complement with AkShare for real-time bid/ask
    - Cache for 1 hour

    Returns:
        Dict with forex rates (EOD closing prices)
    """
    from src.cache.cache_manager import cache_manager

    # Cache key
    now = datetime.now()
    cache_key = f"fx_daily:{now.strftime('%Y%m%d_%H')}"

    # Try cache
    try:
        cached = cache_manager.get(cache_key)
        if cached:
            return cached
    except Exception as e:
        print(f"Cache read error: {e}")

    # Check circuit breaker
    if circuit_breaker.is_open('fx_daily'):
        return {}

    # Rate limiting
    if not rate_limiter.acquire('fx_daily'):
        return {}

    try:
        # Fetch USD/CNY
        end_date = format_date_yyyymmdd()
        start_date = format_date_yyyymmdd(datetime.now() - timedelta(days=2))

        df_usd = tushare_client.get_fx_daily_tushare(
            ts_code='USDCNY.FX',
            start_date=start_date,
            end_date=end_date
        )

        if df_usd is None or df_usd.empty:
            circuit_breaker.record_failure('fx_daily')
            return {}

        circuit_breaker.record_success('fx_daily')

        # Get latest
        latest = df_usd.sort_values('trade_date', ascending=False).iloc[0]

        result = {
            "美元/人民币": {
                "日期": str(latest['trade_date']),
                "收盘价": float(latest['close']),
                "开盘价": float(latest['open']) if 'open' in latest else None,
            }
        }

        # Cache for 1 hour
        try:
            cache_manager.set(cache_key, result, ttl=3600)
        except Exception as e:
            print(f"Cache write error: {e}")

        return result

    except Exception as e:
        print(f"TuShare forex failed: {e}")
        circuit_breaker.record_failure('fx_daily')
        return {}


def get_market_indices_from_tushare() -> List[Dict]:
    """
    Get market indices from TuShare + yFinance.

    Strategy:
    - Chinese indices: TuShare (上证、深证、创业板)
    - US indices: yFinance (纳斯达克、标普500)
    - HK/Asia indices: TuShare (恒生、日经)
    - Cache for 1 minute during trading hours

    Returns:
        List of index dictionaries with name, code, price, change_pct
    """
    from src.cache.cache_manager import cache_manager

    # Cache key
    now = datetime.now()
    cache_key = f"market_indices:{now.strftime('%Y%m%d_%H%M')}"

    # Try cache
    try:
        cached = cache_manager.get(cache_key)
        if cached:
            return cached
    except Exception as e:
        print(f"Cache read error: {e}")

    results = []

    # Chinese indices from TuShare
    chinese_indices = {
        "000001.SH": "上证指数",
        "399001.SZ": "深证成指",
        "399006.SZ": "创业板指",
    }

    # Rate limiting check
    if not rate_limiter.acquire('index_daily'):
        print("⚠️  Rate limit reached for index_daily")
        return []

    try:
        # Use get_latest_trade_date for correct trading day
        trade_date = tushare_client.get_latest_trade_date(max_days_back=10)
        if not trade_date:
            return []

        end_dt = datetime.strptime(trade_date, '%Y%m%d')
        start_date = (end_dt - timedelta(days=5)).strftime('%Y%m%d')
        end_date = trade_date

        for ts_code, name in chinese_indices.items():
            try:
                df = tushare_client.get_index_daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )

                if df is not None and not df.empty:
                    # Get latest and previous for change calculation
                    df_sorted = df.sort_values('trade_date', ascending=False)
                    latest = df_sorted.iloc[0]

                    # Calculate change with safe float conversion
                    pct_change = _safe_float(latest.get('pct_chg', 0))
                    close = _safe_float(latest['close'])
                    change_val = close * (pct_change / 100)

                    results.append({
                        "name": name,
                        "code": ts_code,
                        "price": close,
                        "change_pct": pct_change,
                        "change_val": change_val
                    })
            except Exception as e:
                print(f"Failed to fetch {name}: {e}")
                continue

        circuit_breaker.record_success('index_daily')

    except Exception as e:
        print(f"TuShare index fetch failed: {e}")
        circuit_breaker.record_failure('index_daily')

    # US indices from yFinance (already implemented)
    try:
        us_data = yfinance_client.get_us_market_data()
        if us_data:
            # Map to standard format
            index_mapping = {
                "纳斯达克": "nasdaq",
                "标普500": "sp500"
            }

            for cn_name, en_key in index_mapping.items():
                if en_key in us_data:
                    idx_data = us_data[en_key]
                    results.append({
                        "name": cn_name,
                        "code": idx_data.get('symbol', ''),
                        "price": idx_data.get('最新价', 0),
                        "change_pct": float(str(idx_data.get('涨跌幅', '0%')).replace('%', '')),
                        "change_val": idx_data.get('涨跌额', 0)
                    })
    except Exception as e:
        print(f"yFinance US indices failed: {e}")

    # Cache for 1 minute
    try:
        cache_manager.set(cache_key, results, ttl=60)
    except Exception as e:
        print(f"Cache write error: {e}")

    return results


def get_top_money_flow_from_tushare(limit: int = 10) -> List[Dict]:
    """
    Get top stocks by money flow from TuShare using Northbound flow (沪深港通资金流).

    Strategy:
    - Use hsgt_top10 API for Shanghai and Shenzhen Stock Connect
    - Query both markets (market_type=1 for Shanghai, market_type=3 for Shenzhen)
    - Merge and sort by net_amount
    - Automatically handles non-trading days
    - Cache for 5 minutes
    - Fallback to AkShare if API fails

    Args:
        limit: Number of top stocks to return

    Returns:
        List of dicts with stock code, name, net_buy, change_pct
    """
    from src.cache.cache_manager import cache_manager

    # Cache key (5 minute granularity)
    now = datetime.now()
    cache_key = f"top_moneyflow_hsgt:{limit}:{now.strftime('%Y%m%d_%H%M')[:-1]}0"

    # Try cache
    try:
        cached = cache_manager.get(cache_key)
        if cached:
            return cached
    except Exception as e:
        print(f"Cache read error: {e}")

    # Check circuit breaker
    if circuit_breaker.is_open('moneyflow_hsgt'):
        print("ℹ️  Circuit breaker open for moneyflow_hsgt, using AkShare fallback")
        return []

    # Rate limiting
    if not rate_limiter.acquire('moneyflow_hsgt'):
        print("⚠️  Rate limit reached for moneyflow_hsgt")
        return []

    try:
        # TuShare hsgt_top10 data is usually available for the previous trading day
        # especially when called during or shortly after trading hours.
        # Use offset=1 to get the trading day before the latest one.
        trade_date = tushare_client.get_latest_trade_date(offset=1)
        
        if not trade_date:
            # Fallback to latest if offset=1 fails
            trade_date = tushare_client.get_latest_trade_date(offset=0)
            
        if not trade_date:
            trade_date = format_date_yyyymmdd()

        # Query both Shanghai (1) and Shenzhen (3) Stock Connect
        df_list = []

        # 1. Shanghai Stock Connect (沪股通)
        try:
            df_sh = tushare_client.tushare_call_with_retry(
                'hsgt_top10',
                trade_date=trade_date,
                market_type='1'
            )
            if df_sh is not None and not df_sh.empty:
                df_list.append(df_sh)
        except Exception as e:
            print(f"Failed to fetch Shanghai Connect flow: {e}")

        # 2. Shenzhen Stock Connect (深股通)
        try:
            df_sz = tushare_client.tushare_call_with_retry(
                'hsgt_top10',
                trade_date=trade_date,
                market_type='3'
            )
            if df_sz is not None and not df_sz.empty:
                df_list.append(df_sz)
        except Exception as e:
            print(f"Failed to fetch Shenzhen Connect flow: {e}")

        # Merge results
        if not df_list:
            print("ℹ️  No TuShare northbound data available (both markets empty)")
            # Don't trip breaker immediately, just return empty to trigger AkShare fallback in caller
            return []

        import pandas as pd
        df = pd.concat(df_list, ignore_index=True)

        circuit_breaker.record_success('moneyflow_hsgt')

        # Process results - sort by net_amount (净买入额)
        df_sorted = df.sort_values('net_amount', ascending=False)

        results = []
        seen_codes = set()

        for _, row in df_sorted.iterrows():
            # Get stock code
            ts_code = row.get('ts_code', '')
            if not ts_code or ts_code in seen_codes:
                continue
            seen_codes.add(ts_code)

            # Denormalize code (remove exchange suffix)
            plain_code = tushare_client.denormalize_ts_code(ts_code)

            # Get net buy amount (in 亿元)
            # TuShare returns in 元, convert to 亿元
            net_buy = _safe_float(row.get('net_amount')) / 100000000

            # Get change percentage
            change_pct = _safe_float(row.get('change'))

            results.append({
                "code": plain_code,
                "name": row.get('name', ''),
                "net_buy": round(net_buy, 2),
                "change_pct": round(change_pct, 2)
            })

            if len(results) >= limit:
                break

        # Cache for 5 minutes
        try:
            cache_manager.set(cache_key, results, ttl=300)
        except Exception as e:
            print(f"Cache write error: {e}")

        return results

    except Exception as e:
        print(f"TuShare northbound flow failed: {e}")
        circuit_breaker.record_failure('moneyflow_hsgt')
        return []


# Original implementation (kept for reference, but disabled)
def _get_top_money_flow_from_tushare_original(limit: int = 10) -> List[Dict]:
    """
    Original implementation - DISABLED due to instability.

    Issues:
    - top_list (龙虎榜) data not available every day
    - Causes circuit breaker to open frequently
    - AkShare fallback is more reliable
    """
    from src.cache.cache_manager import cache_manager

    # Cache key (5 minute granularity)
    now = datetime.now()
    cache_key = f"top_flow:{now.strftime('%Y%m%d_%H%M')[:-1]}0"

    # Try cache
    try:
        cached = cache_manager.get(cache_key)
        if cached:
            return cached
    except Exception as e:
        print(f"Cache read error: {e}")

    # Check circuit breaker
    if circuit_breaker.is_open('moneyflow'):
        return []

    # Rate limiting
    if not rate_limiter.acquire('moneyflow'):
        print("⚠️  Rate limit reached for moneyflow")
        return []

    try:
        # Get today's date
        trade_date = format_date_yyyymmdd()

        # Call TuShare moneyflow API
        # Note: This requires iterating through stocks or using top_list
        # Since moneyflow() requires ts_code, we'll use a different approach:
        # Use index constituent stocks and aggregate

        # Alternative: Use top_list API (龙虎榜 - free, no points required)
        df = tushare_client.tushare_call_with_retry(
            'top_list',
            trade_date=trade_date
        )

        if df is None or df.empty:
            circuit_breaker.record_failure('moneyflow')
            return []

        circuit_breaker.record_success('moneyflow')

        # Process results
        results = []
        seen_codes = set()

        for _, row in df.iterrows():
            code = row['ts_code']
            if code in seen_codes:
                continue
            seen_codes.add(code)

            # Get stock name and basic info
            plain_code = tushare_client.denormalize_ts_code(code)

            results.append({
                "code": plain_code,
                "name": row.get('name', ''),
                "net_buy": round(_safe_float(row.get('amount')) / 100000000, 2),  # Convert to 亿
                "change_pct": _safe_float(row.get('pct_change'))
            })

            if len(results) >= limit:
                break

        # Cache for 5 minutes
        try:
            cache_manager.set(cache_key, results, ttl=300)
        except Exception as e:
            print(f"Cache write error: {e}")

        return results

    except Exception as e:
        print(f"TuShare top flow failed: {e}")
        circuit_breaker.record_failure('moneyflow')
        return []


# ============================================================================
# Provider Selection Logic
# ============================================================================

def should_use_tushare() -> bool:
    """Check if TuShare should be used based on configuration."""
    return DATA_SOURCE_PROVIDER in ('tushare', 'hybrid')


def should_use_yfinance() -> bool:
    """Check if yFinance should be used based on configuration."""
    return DATA_SOURCE_PROVIDER in ('yfinance', 'hybrid')


def get_active_provider() -> str:
    """Get the active data provider."""
    return DATA_SOURCE_PROVIDER


# ============================================================================
# Testing & Health Check
# ============================================================================

def test_all_connections() -> Dict[str, bool]:
    """
    Test all data source connections.

    Returns:
        Dict mapping provider name to connection status
    """
    results = {}

    print("Testing TuShare connection...")
    results['tushare'] = tushare_client.test_connection()

    print("\nTesting yFinance connection...")
    results['yfinance'] = yfinance_client.test_yfinance_connection()

    print("\nTesting AkShare connection...")
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        results['akshare'] = not df.empty
        print(f"✅ AkShare connection successful! Fetched {len(df)} stocks")
    except Exception as e:
        results['akshare'] = False
        print(f"❌ AkShare connection failed: {e}")

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("Data Source Manager - Connection Test")
    print("=" * 60)

    print(f"\nActive Provider: {get_active_provider()}")
    print(f"Cache TTL: {DATA_SOURCE_CACHE_TTL}s")

    print("\n" + "=" * 60)
    print("Testing All Data Sources")
    print("=" * 60)

    results = test_all_connections()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for provider, status in results.items():
        status_str = "✅ Connected" if status else "❌ Failed"
        print(f"{provider.ljust(15)}: {status_str}")
