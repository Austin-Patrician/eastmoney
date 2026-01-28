import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import inspect
import time
import threading
from typing import Dict, List, Optional


_A_STOCK_SPOT_CACHE_LOCK = threading.Lock()
_A_STOCK_SPOT_CACHE_FETCHED_AT: float = 0.0
_A_STOCK_SPOT_CACHE_BY_CODE: Optional[Dict[str, Dict]] = None


def _normalize_a_stock_code(stock_code: str) -> str:
    if not stock_code:
        return ""
    stock_code = str(stock_code).strip()
    # Common cases: "600519", "600519.SH", "SZ000001"
    for part in (stock_code.split(".")[0], stock_code):
        digits = "".join(ch for ch in part if ch.isdigit())
        if len(digits) == 6:
            return digits
    return stock_code


def get_all_stock_spot_map(cache_ttl_seconds: int = 30, force_refresh: bool = False) -> Optional[Dict[str, Dict]]:
    """Return a cached mapping {code -> row_dict} built from ak.stock_zh_a_spot_em()."""
    global _A_STOCK_SPOT_CACHE_FETCHED_AT, _A_STOCK_SPOT_CACHE_BY_CODE

    now = time.time()
    with _A_STOCK_SPOT_CACHE_LOCK:
        if (
            not force_refresh
            and _A_STOCK_SPOT_CACHE_BY_CODE is not None
            and (now - _A_STOCK_SPOT_CACHE_FETCHED_AT) < max(cache_ttl_seconds, 1)
        ):
            return _A_STOCK_SPOT_CACHE_BY_CODE

        try:
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty or '代码' not in df.columns:
                # Keep old cache if fetch fails? Or clear? Let's clear to be safe or maybe keep old is better?
                # If fetch fails, returning None lets caller handle it.
                return _A_STOCK_SPOT_CACHE_BY_CODE
            
            # Build once for O(1) lookups during holdings loops
            # Columns usually: 代码, 名称, 最新价, 涨跌幅, ...
            by_code = df.set_index('代码').to_dict('index')
            _A_STOCK_SPOT_CACHE_BY_CODE = by_code
            _A_STOCK_SPOT_CACHE_FETCHED_AT = time.time()
            return by_code
        except Exception as e:
            print(f"Error refreshing stock spot map: {e}")
            return _A_STOCK_SPOT_CACHE_BY_CODE

def get_stock_history(code: str, days: int = 100) -> List[Dict]:
    """
    Fetch daily history for a stock.
    """
    # Use TuShare for stock history
    try:
        from src.data_sources.data_source_manager import get_stock_history_from_tushare
        result = get_stock_history_from_tushare(code, days)
        if result:
                return result
    except Exception as e:
            print(f"TuShare stock history failed, falling back to AkShare: {e}")
    

# ============================================================================
# SECTION 1: 全球宏观市场数据 (Global Macro Data)
# ============================================================================

def get_us_market_overview() -> Dict:
    """
    获取隔夜美股市场概览：三大指数
    Returns: {指数名: {最新价, 涨跌幅, ...}}

    Migration Note: Now uses yFinance as primary source (Phase 3 - US market priority)
    """
    from config.settings import DATA_SOURCE_PROVIDER

    # Use yFinance for US market data (more reliable per Phase 3 priority)
    if DATA_SOURCE_PROVIDER in ('yfinance', 'hybrid'):
        try:
            from src.data_sources.data_source_manager import get_us_market_overview_from_yfinance
            result = get_us_market_overview_from_yfinance()
            if result and '说明' not in result:
                return result
        except Exception as e:
            print(f"yFinance US market fetch failed, falling back to AkShare: {e}")

    # Fallback to AkShare if yFinance fails or provider is 'akshare'
    result = {}
    try:
        # 使用全球指数接口获取美股三大指数
        df = ak.index_global_spot_em()
        if not df.empty:
            # 美股三大指数映射 (Name -> Code for reference, but here we search by Name)
            # Actually index_global_spot_em has '名称' column.
            # We want to match these names:
            target_names = ['道琼斯', '纳斯达克', '标普500']

            # Optimized: Filter dataframe directly
            filtered_df = df[df['名称'].isin(target_names)]

            for _, r in filtered_df.iterrows():
                name = r['名称']
                result[name] = {
                    '最新价': r.get('最新价', 'N/A'),
                    '涨跌额': r.get('涨跌额', 'N/A'),
                    '涨跌幅': f"{r.get('涨跌幅', 0)}%",
                    '开盘价': r.get('开盘价', 'N/A'),
                    '最高价': r.get('最高价', 'N/A'),
                    '最低价': r.get('最低价', 'N/A'),
                    '更新时间': r.get('最新行情时间', 'N/A')
                }
    except Exception as e:
        print(f"Error fetching US market: {e}")

    return result if result else {"说明": "美股数据暂时无法获取"}

def get_a50_futures() -> Dict:
    """
    获取富时A50相关指数数据
    由于直接A50期货数据不稳定，使用全球指数中的新加坡/恒生指数作为亚太市场参考
    """
    result = {}
    try:
        # 方案1：从全球指数获取亚太市场数据
        df = ak.index_global_spot_em()
        if not df.empty:
            # 获取相关亚太指数
            target_names = ['恒生指数', '富时新加坡海峡时报', '日经225']
            
            # Optimized filtering
            filtered_df = df[df['名称'].isin(target_names)]
            
            for _, r in filtered_df.iterrows():
                name = r['名称']
                result[name] = {
                    '最新价': r.get('最新价', 'N/A'),
                    '涨跌幅': r.get('涨跌幅', 'N/A'),
                    '更新时间': r.get('最新行情时间', 'N/A')
                }
    except Exception as e:
        print(f"Error fetching A50/Asia index: {e}")
    
    if not result:
        return {"说明": "A50期货数据暂时无法获取，请关注盘前竞价"}
    return result

def get_forex_rates() -> Dict:
    """
    获取关键汇率：美元/人民币

    Migration Note: Phase 5 - Hybrid strategy
    - TuShare: Daily EOD closing prices (historical data)
    - AkShare: Real-time bid/ask quotes (live data)
    """
    from config.settings import DATA_SOURCE_PROVIDER

    result = {}

    # TuShare for daily historical/EOD data
    if DATA_SOURCE_PROVIDER in ('tushare', 'hybrid'):
        try:
            from src.data_sources.data_source_manager import get_forex_rates_from_tushare
            ts_result = get_forex_rates_from_tushare()
            if ts_result:
                result.update(ts_result)
        except Exception as e:
            print(f"TuShare forex error: {e}")

    # AkShare for real-time bid/ask quotes (complement)
    try:
        df = ak.fx_spot_quote()
        if not df.empty:
            # fx_spot_quote 返回的列是: 货币对, 买报价, 卖报价
            usdcny = df[df['货币对'].str.contains('USD/CNY', na=False, case=False)]
            if not usdcny.empty:
                row = usdcny.iloc[0]
                # If TuShare provided data, augment with real-time prices
                if "美元/人民币" in result:
                    result["美元/人民币"]["实时买入价"] = row.get('买报价', 'N/A')
                    result["美元/人民币"]["实时卖出价"] = row.get('卖报价', 'N/A')
                else:
                    # Otherwise, use AkShare as primary
                    result["美元/人民币"] = {
                        "货币对": row.get('货币对', 'USD/CNY'),
                        "买入价": row.get('买报价', 'N/A'),
                        "卖出价": row.get('卖报价', 'N/A')
                    }

            # 获取其他重要汇率
            eurcny = df[df['货币对'].str.contains('EUR/CNY', na=False, case=False)]
            if not eurcny.empty:
                row = eurcny.iloc[0]
                result["欧元/人民币"] = {
                    "买入价": row.get('买报价', 'N/A'),
                    "卖出价": row.get('卖报价', 'N/A')
                }
    except Exception as e:
        print(f"Error fetching forex from AkShare: {e}")

    # 备选方案：使用百度汇率
    if not result:
        try:
            fx_data = ak.fx_quote_baidu()
            if not fx_data.empty:
                usd = fx_data[fx_data['货币'].str.contains('美元', na=False)]
                if not usd.empty:
                    result["美元/人民币"] = {"最新价": usd.iloc[0].get('现汇买入价', 'N/A')}
        except Exception as e:
            print(f"Baidu forex fallback failed: {e}")

    return result if result else {"说明": "汇率数据暂时无法获取"}

def get_global_macro_summary() -> Dict:
    """
    汇总全球宏观数据 - 盘前分析核心输入
    """
    return {
        "美股市场": get_us_market_overview(),
        "A50期货": get_a50_futures(),
        "汇率": get_forex_rates()
    }

# ============================================================================
# SECTION 2: 北向资金与资金流向 (Capital Flow)
# ============================================================================

def get_northbound_flow() -> Dict:
    """
    获取北向资金（沪股通+深股通）净流入数据
    使用 TuShare Pro 作为主要数据源，AkShare 作为后备

    Migration Note: Now uses TuShare as primary source (Phase 4)
    """
    from config.settings import DATA_SOURCE_PROVIDER

    # Use TuShare for northbound flow data
    if DATA_SOURCE_PROVIDER in ('tushare', 'hybrid'):
        try:
            from src.data_sources.data_source_manager import get_northbound_flow_from_tushare
            result = get_northbound_flow_from_tushare()
            if result:
                return result
        except Exception as e:
            print(f"TuShare northbound flow failed, falling back to AkShare: {e}")

    # Fallback to AkShare
    result = {}
    try:
        # 方案1：使用实时汇总数据（最可靠）
        df = ak.stock_hsgt_fund_flow_summary_em()
        if not df.empty:
            # 筛选北向资金（沪股通+深股通）
            north = df[df['资金方向'] == '北向']
            if not north.empty:
                total_net = 0
                for _, row in north.iterrows():
                    board = row.get('板块', '')
                    net_buy = row.get('成交净买额', 0)
                    try:
                        net_buy = float(net_buy) if net_buy else 0
                    except:
                        net_buy = 0
                    total_net += net_buy
                    result[board] = {
                        '成交净买额': f"{net_buy:.2f}亿",
                        '交易状态': '交易中' if row.get('交易状态') == 1 else '休市',
                        '相关指数': row.get('相关指数', 'N/A'),
                        '指数涨跌幅': f"{row.get('指数涨跌幅', 0)}%"
                    }
                result['最新净流入'] = f"{total_net:.2f}亿"
                # 确保日期是字符串格式
                trade_date = df.iloc[0].get('交易日', 'N/A')
                if hasattr(trade_date, 'strftime'):
                    trade_date = trade_date.strftime('%Y-%m-%d')
                result['数据日期'] = str(trade_date)

        # 方案2：获取历史数据计算5日累计（如果方案1成功后补充）
        if result:
            try:
                hist_df = ak.stock_hsgt_hist_em(symbol="北向资金")
                if hist_df is not None and not hist_df.empty:
                    # 获取最近有数据的5日
                    # 检查哪个列有净流入数据
                    flow_col = None
                    for col in ['当日成交净买额', '当日资金流入', '资金流入']:
                        if col in hist_df.columns:
                            # 过滤掉NaN值
                            valid = hist_df[hist_df[col].notna()]
                            if not valid.empty:
                                flow_col = col
                                recent = valid.tail(5)
                                try:
                                    total_5d = recent[col].astype(float).sum()
                                    result['5日累计净流入'] = f"{total_5d:.2f}亿"
                                except:
                                    pass
                                break
            except Exception as e:
                print(f"Historical northbound data failed: {e}")

    except Exception as e:
        print(f"Error fetching northbound flow: {e}")

    return result if result else {"说明": "北向资金数据暂时无法获取"}

def get_industry_capital_flow(industry: str = None) -> Dict:
    """
    获取行业资金流向

    Migration Note: Phase 5 - TuShare pro.concept_detail() as primary
    """
    from config.settings import DATA_SOURCE_PROVIDER

    # Try TuShare first (if enabled and industry specified)
    if industry and DATA_SOURCE_PROVIDER in ('tushare', 'hybrid'):
        try:
            from src.data_sources.data_source_manager import get_industry_capital_flow_from_tushare
            result = get_industry_capital_flow_from_tushare(industry)
            if result:
                return result
        except Exception as e:
            print(f"TuShare industry flow error: {e}")

    # Fallback to AkShare
    try:
        df = ak.stock_sector_fund_flow_rank()
        if not df.empty:
            if industry:
                filtered = df[df['名称'].str.contains(industry, na=False, regex=False)]
                if not filtered.empty:
                    return filtered.iloc[0].to_dict()
            # 返回前10行业
            return {"行业资金流向Top10": df.head(10).to_dict('records')}
    except Exception as e:
        print(f"Error fetching industry capital flow: {e}")
    return {}

# ============================================================================
# SECTION 3: 个股深度数据 (Stock Deep Dive)
# ============================================================================

def get_stock_announcement(stock_code: str, stock_name: str) -> List[Dict]:
    """
    获取个股最新公告（巨潮资讯）

    Migration Note: Phase 5 - TuShare pro.anns() as primary, AkShare fallback
    """
    from config.settings import DATA_SOURCE_PROVIDER

    # Try TuShare first (if enabled)
    if DATA_SOURCE_PROVIDER in ('tushare', 'hybrid'):
        try:
            from src.data_sources.data_source_manager import get_stock_announcements_from_tushare
            result = get_stock_announcements_from_tushare(stock_code, limit=5)
            if result:
                return result
        except Exception as e:
            print(f"TuShare announcements error for {stock_name}: {e}")

    # Fallback to AkShare
    announcements = []
    try:
        # 尝试获取公告 - 使用巨潮资讯接口，支持更多市场（包括北交所）
        df = ak.stock_zh_a_disclosure_report_cninfo(symbol=stock_code)
        if df is not None and not df.empty:
            # 按时间倒序排序 (API通常已排序，但也可能未排序)
            if '公告时间' in df.columns:
                 df.sort_values(by='公告时间', ascending=False, inplace=True)

            # 最近5条公告
            recent = df.head(5)
            announcements = recent.to_dict('records')
    except Exception as e:
        print(f"Error fetching announcements for {stock_name} ({stock_code}): {e}")
    return announcements

def get_stock_realtime_quote(
    stock_code: str,
    use_cache: bool = True,
    cache_ttl_seconds: int = 30,
    force_refresh: bool = False,
) -> Dict:
    """
    获取个股实时/最新行情
    Prioritizes cache, then fast single-stock fetch (bid_ask_em), then full market spot.
    """
    try:
        code = _normalize_a_stock_code(stock_code)
        if not code:
            return {}

        
        # 2. Fast Fetch (Single Stock)
        try:
            df = ak.stock_bid_ask_em(symbol=code)
            if not df.empty:
                # df columns: item, value. 
                # Keys: 最新, 涨幅, 总手, 金额, 最高, 最低, 今开, 昨收, 涨跌
                info = dict(zip(df['item'], df['value']))
                
                # Map to standard keys (compatible with stock_zh_a_spot_em)
                return {
                    '代码': code,
                    '名称': '', # Name not available in bid_ask
                    '最新价': info.get('最新'),
                    '涨跌幅': info.get('涨幅'),
                    '涨跌额': info.get('涨跌'),
                    '成交量': float(info.get('总手', 0)) * 100 if info.get('总手') else None,
                    '成交额': info.get('金额'),
                    '最高': info.get('最高'),
                    '最低': info.get('最低'),
                    '今开': info.get('今开'),
                    '昨收': info.get('昨收'),
                    # Extra fields useful for debug
                    '均价': info.get('均价'),
                    '量比': info.get('量比'),
                    '换手': info.get('换手'),
                    '涨停': info.get('涨停'),
                    '跌停': info.get('跌停'),
                    '外盘': info.get('外盘'),
                    '内盘': info.get('内盘'),
                }
        except BaseException as e:
            # print(f"Bid/Ask fetch failed for {code}: {e}") # Debug only
            pass
    except BaseException as e:
        print(f"Error fetching realtime quote for {stock_code}: {e}")
    return {}

def get_stock_news_sentiment(stock_name: str) -> List[Dict]:
    """
    获取个股相关新闻（东方财富）

    Migration Note: Phase 5 - Enhanced with web search
    - TuShare has no news API (keep using AkShare)
    - Supplement with web search when data is insufficient
    """
    results = []

    # Primary: AkShare (free and fast)
    try:
        df = ak.stock_news_em(symbol=stock_name)
        if not df.empty:
            for _, row in df.head(5).iterrows():
                results.append({
                    '标题': row.get('新闻标题', row.get('标题', '')),
                    '内容': row.get('新闻内容', row.get('内容', ''))[:200],  # Truncate
                    '发布时间': str(row.get('发布时间', row.get('时间', ''))),
                    '来源': 'AkShare-东方财富',
                    '网址': row.get('新闻链接', '')
                })
    except Exception as e:
        print(f"Error fetching news from AkShare for {stock_name}: {e}")

    # Supplement with web search if insufficient data
    if len(results) < 3:
        try:
            from src.data_sources.web_search import WebSearch
            searcher = WebSearch()

            # Use search_news method for general news
            web_results = searcher.search_news(f"{stock_name} 最新动态", max_results=5)

            for item in web_results:
                # Avoid duplicates
                if any(r.get('标题') == item.get('title') for r in results):
                    continue

                results.append({
                    '标题': item.get('title', ''),
                    '内容': item.get('content', '')[:200],
                    '发布时间': item.get('published_date', ''),
                    '来源': f"Web-{item.get('domain', 'Unknown')}",
                    '网址': item.get('url', '')
                })

                # Stop when we have enough
                if len(results) >= 10:
                    break

        except Exception as e:
            print(f"Web search supplement failed for {stock_name}: {e}")

    return results[:10]  # Max 10 results

# ============================================================================
# SECTION 4: 行业与板块数据 (Sector Data)
# ============================================================================

def get_sector_performance(sector_name: str = None) -> Dict:
    """
    获取板块行情表现
    """
    try:
        df = ak.stock_board_industry_name_em()
        if not df.empty:
            if sector_name:
                filtered = df[df['板块名称'].str.contains(sector_name, na=False, regex=False)]
                if not filtered.empty:
                    return filtered.iloc[0].to_dict()
            return {"板块涨幅榜": df.head(10).to_dict('records')}
    except Exception as e:
        print(f"Error fetching sector performance: {e}")
    return {}

def get_sector_performance_ths(sector_name: str) -> Dict:
    """
    获取同花顺行业板块表现

    Migration Note: Phase 5 - TuShare pro.ths_index() as primary
    """
    from config.settings import DATA_SOURCE_PROVIDER

    # Try TuShare first (if enabled)
    if DATA_SOURCE_PROVIDER in ('tushare', 'hybrid'):
        try:
            from src.data_sources.data_source_manager import get_sector_performance_ths_from_tushare
            result = get_sector_performance_ths_from_tushare(sector_name)
            if result:
                return result
        except Exception as e:
            print(f"TuShare THS index error for {sector_name}: {e}")

    # Fallback to AkShare
    try:
        # 1. Get all board names
        boards = ak.stock_board_industry_name_ths()
        if boards.empty:
            return {}

        target_name = None
        # Simple fuzzy match
        # If input is "半导体", match "半导体"
        # If input is "新能源", match "新能源汽车" or similar?
        # Let's try exact match first, then contains

        # Check if direct match exists
        if sector_name in boards['name'].values:
            target_name = sector_name
        else:
            # Contains
            matches = boards[boards['name'].str.contains(sector_name, na=False, regex=False)]
            if not matches.empty:
                target_name = matches.iloc[0]['name']

        if not target_name:
            return {}

        # 2. Fetch Index Data
        # akshare expects start/end date usually to reduce data
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")

        df = ak.stock_board_industry_index_ths(symbol=target_name, start_date=start_date, end_date=end_date)

        if not df.empty:
            latest = df.iloc[-1]
            # Calculate change
            change_pct = "N/A"
            if len(df) >= 2:
                prev = df.iloc[-2]['收盘价']
                curr = latest['收盘价']
                if prev and float(prev) != 0:
                    pct = ((float(curr) - float(prev)) / float(prev)) * 100
                    change_pct = f"{pct:.2f}"

            return {
                "板块名称": target_name,
                "收盘价": latest['收盘价'],
                "涨跌幅": change_pct,
                "成交量": latest['成交量'],
                "成交额": latest['成交额'],
                "日期": latest['日期']
            }

    except Exception as e:
        print(f"Error fetching THS sector performance for {sector_name}: {e}")
    return {}

def get_concept_board_performance(concept: str = None) -> Dict:
    """
    获取概念板块表现（如：AI、新能源等）
    """
    try:
        df = ak.stock_board_concept_name_em()
        if not df.empty:
            if concept:
                filtered = df[df['板块名称'].str.contains(concept, na=False, regex=False)]
                if not filtered.empty:
                    return filtered.to_dict('records')
            return {"概念板块Top10": df.head(10).to_dict('records')}
    except Exception as e:
        print(f"Error fetching concept board: {e}")
    return {}

# ============================================================================
# SECTION 5: 原有函数（保留并优化）
# ============================================================================

def get_fund_info(fund_code: str):
    """
    Fetch basic fund information and net value history.
    Uses TuShare Pro as primary source, akshare as fallback.

    Migration Note: Now uses TuShare as primary source (Phase 4)
    """
    from config.settings import DATA_SOURCE_PROVIDER

    # Use TuShare for fund info
    if DATA_SOURCE_PROVIDER in ('tushare', 'hybrid'):
        try:
            from src.data_sources.data_source_manager import get_fund_info_from_tushare
            result = get_fund_info_from_tushare(fund_code)
            if result is not None and not result.empty:
                return result
        except Exception as e:
            print(f"TuShare fund info failed, falling back to AkShare: {e}")

    # Fallback to AkShare
    try:
        # Fetching net value history
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")

        if df is None or df.empty:
            return pd.DataFrame()

        # Expected columns: 净值日期, 单位净值, 日增长率
        # NOTE: Some environments may return mojibake column names (encoding issues).
        # To keep downstream logic stable, normalize columns when we can.
        if '净值日期' not in df.columns:
            cols = list(df.columns)
            if len(cols) >= 3:
                df = df.rename(
                    columns={
                        cols[0]: '净值日期',
                        cols[1]: '单位净值',
                        cols[2]: '日增长率',
                    }
                )

        # Sort by date descending so iloc[0] is the latest NAV
        if '净值日期' in df.columns:
            df['净值日期'] = pd.to_datetime(df['净值日期'], errors='coerce')
            df = df.sort_values('净值日期', ascending=False).reset_index(drop=True)
            # Keep a consistent display format
            df['净值日期'] = df['净值日期'].dt.date
        return df
    except Exception as e:
        print(f"Error fetching fund info for {fund_code}: {e}")
        return pd.DataFrame()

def get_fund_holdings(fund_code: str, year: str = None):
    """
    Fetch the latest top 10 holdings for the fund.
    Defaults to the current year if not specified.
    使用 TuShare Pro 作为主要数据源，AkShare 作为后备

    Migration Note: Now uses TuShare as primary source (Phase 4)
    """
    from config.settings import DATA_SOURCE_PROVIDER

    current_year = str(datetime.now().year)
    if not year:
        year = current_year

    # Use TuShare for fund holdings
    if DATA_SOURCE_PROVIDER in ('tushare', 'hybrid'):
        try:
            from src.data_sources.data_source_manager import get_fund_holdings_from_tushare
            result = get_fund_holdings_from_tushare(fund_code, year)
            if result is not None and not result.empty:
                return result
        except Exception as e:
            print(f"TuShare fund holdings failed, falling back to AkShare: {e}")

    # Fallback to AkShare
    try:
        # fund_portfolio_hold_em signature varies by AkShare version.
        # In the installed AkShare (2024/06+), it is: fund_portfolio_hold_em(symbol, date)
        sig = None
        try:
            sig = inspect.signature(ak.fund_portfolio_hold_em)
        except Exception:
            sig = None

        def _call_holdings(target_year: str):
            if sig and "symbol" in sig.parameters:
                return ak.fund_portfolio_hold_em(symbol=fund_code, date=target_year)
            # Fallback for older/newer variants: try positional to avoid keyword mismatches
            try:
                return ak.fund_portfolio_hold_em(fund_code, target_year)
            except TypeError:
                # Last-resort: try legacy keywords if positional fails
                return ak.fund_portfolio_hold_em(code=fund_code, year=target_year)

        # fund_portfolio_hold_em: returns holding details
        df = _call_holdings(year)

        # Fallback to previous year if current year is empty (common in early Jan)
        if df.empty and year == current_year:
            prev_year = str(int(year) - 1)
            print(f"DEBUG: No data for {year}, trying {prev_year}...")
            df = _call_holdings(prev_year)

        # We generally want the latest quarter available
        if not df.empty:
            # Sort by date/quarter to get the latest
            # This API usually returns all quarters for the year.
            # We might need to filter for the latest '季度'
            return df
        return df
    except Exception as e:
        print(f"Error fetching holdings for {fund_code}: {e}")
        return pd.DataFrame()

def get_market_indices():
    """
    Fetch key market indices for context (A50, Shanghai Composite, etc.)
    使用 TuShare Pro 作为主要数据源，AkShare 作为后备

    Migration Note: Now uses TuShare as primary source (Phase 4)
    """
    from config.settings import DATA_SOURCE_PROVIDER

    # Use TuShare for market indices
    if DATA_SOURCE_PROVIDER in ('tushare', 'hybrid'):
        try:
            from src.data_sources.data_source_manager import get_market_indices_from_tushare
            result = get_market_indices_from_tushare()
            if result:
                return result
        except Exception as e:
            print(f"TuShare market indices failed, falling back to AkShare: {e}")

    # Fallback to AkShare
    indices = {
        "sh000001": "上证指数",
        "sz399006": "创业板指数",
    }

    market_data: Dict[str, Dict] = {}
    try:
        for symbol, name in indices.items():
            # stock_zh_index_daily_em returns historical data
            df = ak.stock_zh_index_daily_em(symbol=symbol)
            if not df.empty:
                # Get the last row (most recent trading day)
                latest_row = df.iloc[-1]
                close = latest_row.get('close', None)
                trade_date = latest_row.get('date', None)

                pct_change = None
                if len(df) >= 2:
                    prev_close = df.iloc[-2].get('close', None)
                    try:
                        if prev_close not in (None, 0) and close is not None:
                            pct_change = (float(close) / float(prev_close) - 1.0) * 100.0
                    except Exception:
                        pct_change = None

                # Normalize fields to what the analyst code expects
                market_data[name] = {
                    '日期': trade_date,
                    '收盘': close,
                    '涨跌幅': (round(pct_change, 2) if pct_change is not None else 'N/A'),
                }
        return market_data
    except Exception as e:
        print(f"Error fetching market indices: {e}")
        return {}

def get_all_fund_list() -> List[Dict]:

    """

    获取全市场所有基金列表

    Returns: List of dicts with 'code', 'name', 'type', etc.

    """

    try:

        # fund_name_em returns: 基金代码, 基金简称, 基金类型, 拼音缩写

        df = ak.fund_name_em()

        if not df.empty:

            # Rename columns for consistency

            # 基金代码 -> code, 基金简称 -> name, 基金类型 -> type, 拼音缩写 -> pinyin

            df = df.rename(columns={

                '基金代码': 'code',

                '基金简称': 'name',

                '基金类型': 'type',

                '拼音缩写': 'pinyin'

            })

            return df[['code', 'name', 'type', 'pinyin']].to_dict('records')

    except Exception as e:

        print(f"Error fetching all fund list: {e}")

    return []



def search_funds(query: str, limit: int = 10) -> List[Dict]:

    """

    Search funds by code or name (fuzzy matching)

    """

    query = query.strip().lower()

    if not query:

        return []



    all_funds = get_all_fund_list()

    results = []

    

    # Priority 1: Exact Code Match

    for fund in all_funds:

        if fund['code'] == query:

            results.append(fund)

    

    # Priority 2: Code Starts With

    for fund in all_funds:

        if fund['code'].startswith(query) and fund not in results:

            results.append(fund)

            

    # Priority 3: Name Contains

    for fund in all_funds:

        if query in fund['name'].lower() and fund not in results:

            results.append(fund)

            

    # Priority 4: Pinyin Contains

    for fund in all_funds:

        if 'pinyin' in fund and query in str(fund['pinyin']).lower() and fund not in results:

            results.append(fund)

            

    return results[:limit]
