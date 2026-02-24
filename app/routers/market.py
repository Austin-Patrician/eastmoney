"""
Market data endpoints.
"""
import os
import json
import time
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
import akshare as ak
import pandas as pd

from app.core.config import MARKET_FUNDS_CACHE, MARKET_STOCKS_CACHE, CONFIG_DIR
from app.core.cache import indices_cache
from app.core.utils import sanitize_data
from src.data_sources.akshare_api import search_funds, get_stock_realtime_quote, get_stock_realtime_quote_min, get_stock_history
from src.data_sources.itick_client import (
    is_itick_enabled,
    infer_region_and_code,
    get_stock_quote as get_itick_stock_quote,
    get_stock_depth as get_itick_stock_depth,
    map_quote_to_legacy_fields as map_itick_quote_to_legacy_fields,
)
from src.data_sources.tushare_client import search_funds_tushare, _get_tushare_pro
from src.storage.db import search_stock_basic, get_stock_basic_count

router = APIRouter(tags=["Market"])


@router.get("/api/market/funds")
async def search_market_funds(q: str):
    """Search funds by query."""
    if not q:
        return []
    try:
        results = search_funds(q)
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return []


@router.get("/api/market-funds")
async def search_market_funds_alt(query: str = ""):
    """
    Search funds using TuShare data.
    Returns list of funds matching the query by code or name.
    """
    if not query or len(query) < 2:
        return []

    try:
        results = search_funds_tushare(query, limit=50)
        return results
    except Exception as e:
        print(f"TuShare fund search error: {e}")
        # Fallback to cached akshare data if available
        funds = []
        if os.path.exists(MARKET_FUNDS_CACHE):
            try:
                with open(MARKET_FUNDS_CACHE, 'r', encoding='utf-8') as f:
                    funds = json.load(f)
            except Exception as cache_error:
                print(f"Cache read error: {cache_error}")

        if not funds:
            return []

        query_lower = query.lower()
        results = []
        for f in funds:
            f_code = str(f.get('code', ''))
            f_name = str(f.get('name', ''))
            f_pinyin = str(f.get('pinyin', ''))

            if (f_code.startswith(query) or
                query_lower in f_name.lower() or
                query_lower in f_pinyin.lower()):
                results.append(f)
                if len(results) >= 50:
                    break
        return results


@router.get("/api/market/indices")
def get_market_indices():
    """
    Get market indices with TuShare + yFinance hybrid approach.
    """
    from config.settings import DATA_SOURCE_PROVIDER

    now_ts = time.time()
    now_dt = datetime.now()
    current_hm = now_dt.hour * 100 + now_dt.minute

    # Check cache first
    cached = indices_cache.get()
    if cached:
        return cached

    # # Try TuShare first
    # if DATA_SOURCE_PROVIDER in ('tushare', 'hybrid'):
    #     try:
    #         from src.data_sources.data_source_manager import get_market_indices_from_tushare
    #         results = get_market_indices_from_tushare()

    #         if results:
    #             data = sanitize_data(results)
    #             indices_cache.set(data, ttl_seconds=60)
    #             return data
    #     except Exception as e:
    #         print(f"TuShare indices failed: {e}")

    # Fallback to AkShare
    try:
        indices_df = ak.index_global_spot_em()

        target_names = [
            "上证指数", "深证成指", "创业板指",
            "恒生指数", "日经225", "纳斯达克", "标普500"
        ]

        if not indices_df.empty:
            filtered_df = indices_df[indices_df['名称'].isin(target_names)]

            results = []
            for _, row in filtered_df.iterrows():
                results.append({
                    "name": row['名称'],
                    "code": str(row.get('代码', '')),
                    "price": float(row['最新价']),
                    "change_pct": float(row['涨跌幅']),
                    "change_val": float(row['涨跌额'])
                })
        else:
            results = []

        data = sanitize_data(results)

        if data:
            indices_cache.set(data, ttl_seconds=60)

        return data
    except Exception as e:
        print(f"Error fetching indices via index_global_spot_em: {e}")
        cached = indices_cache.get()
        if cached:
            return cached
        return []


@router.get("/api/market/stocks")
async def search_market_stocks(query: str = ""):
    """
    Search stocks from local database (synced from TuShare stock_basic).
    """
    stock_count = get_stock_basic_count()

    if stock_count > 0:
        results = search_stock_basic(query, limit=50)
        return results

    # Fallback to old JSON cache method if database is empty
    stocks = []

    if os.path.exists(MARKET_STOCKS_CACHE):
        try:
            mtime = os.path.getmtime(MARKET_STOCKS_CACHE)
            if (datetime.now().timestamp() - mtime) < 86400:
                with open(MARKET_STOCKS_CACHE, 'r', encoding='utf-8') as f:
                    stocks = json.load(f)
        except Exception as e:
            print(f"Stock cache read error: {e}")

    if not stocks:
        print("Fetching fresh stock list from AkShare...")
        try:
            df = ak.stock_info_a_code_name()
            if not df.empty:
                stocks = df.to_dict('records')
                if not os.path.exists(CONFIG_DIR):
                    os.makedirs(CONFIG_DIR)
                with open(MARKET_STOCKS_CACHE, 'w', encoding='utf-8') as f:
                    json.dump(stocks, f, ensure_ascii=False)
        except Exception as e:
            print(f"Error fetching stock list: {e}")

    if not query:
        return stocks[:20]

    query = query.lower()
    results = []
    for s in stocks:
        s_code = str(s.get('code', ''))
        s_name = str(s.get('name', ''))

        if s_code.startswith(query) or query in s_name.lower():
            results.append(s)
            if len(results) >= 50:
                break
    return results


@router.get("/api/market/stocks/{code}/details")
async def get_stock_details_endpoint(code: str):
    """Get stock details including realtime quote and company info."""
    try:
        quote = {}

        # iTick first for low-latency realtime quote.
        if is_itick_enabled():
            region, symbol = infer_region_and_code(code)
            if region and symbol:
                itick_quote = await asyncio.to_thread(get_itick_stock_quote, region, symbol)
                if itick_quote:
                    quote = map_itick_quote_to_legacy_fields(itick_quote, code=symbol)

        # Fallback to current data source chain.
        if not quote or not quote.get('最新价'):
            quote = get_stock_realtime_quote_min(code)
        if not quote or not quote.get('最新价'):
            quote = get_stock_realtime_quote(code)

        info = {}
        
        # 使用 TuShare 日线数据获取昨收（更稳定）
        if quote and not quote.get('昨收'):
            try:
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')
                
                # 转换股票代码为 TuShare 格式
                ts_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
                
                pro = _get_tushare_pro()
                df_daily = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                
                if df_daily is not None and not df_daily.empty:
                    # 按日期排序，取最新的一条
                    df_daily = df_daily.sort_values('trade_date', ascending=False)
                    latest_row = df_daily.iloc[0]
                    prev_close_val = float(latest_row['pre_close'])
                    quote['昨收'] = prev_close_val
                    if quote.get('最新价') and prev_close_val > 0:
                        change = quote['最新价'] - prev_close_val
                        change_pct = (change / prev_close_val) * 100
                        quote['涨跌额'] = round(change, 2)
                        quote['涨跌幅'] = round(change_pct, 2)
            except Exception as daily_err:
                print(f"Failed to get prev close from TuShare: {daily_err}")
        
        # 获取公司信息
        try:
            df = ak.stock_individual_info_em(symbol=code)
            if not df.empty:
                info_map = dict(zip(df['item'], df['value']))
                info = {
                    "industry": info_map.get("行业", ""),
                    "market_cap": info_map.get("总市值", ""),
                    "pe": info_map.get("市盈率", ""),
                    "pb": info_map.get("市净率", "")
                }
        except:
            pass

        return sanitize_data({
            "quote": quote,
            "info": info
        })
    except Exception as e:
        print(f"Error fetching stock details: {e}")
        return {}


@router.get("/api/market/stocks/{code}/depth")
async def get_stock_depth_endpoint(code: str):
    """Get stock order-book depth (iTick)."""
    try:
        if not is_itick_enabled():
            return {"symbol": code, "a": [], "b": [], "source": "disabled"}

        region, symbol = infer_region_and_code(code)
        if not region or not symbol:
            return {"symbol": code, "a": [], "b": [], "source": "unsupported"}

        depth = await asyncio.to_thread(get_itick_stock_depth, region, symbol)
        if not depth:
            return {"symbol": symbol, "a": [], "b": [], "source": "itick"}

        return sanitize_data(depth)
    except Exception as e:
        print(f"Depth error: {e}")
        return {"symbol": code, "a": [], "b": []}


@router.get("/api/market/stocks/{code}/history")
async def get_stock_history_endpoint(code: str):
    """Get stock price history."""
    try:
        data = await asyncio.to_thread(get_stock_history, code)
        return sanitize_data(data)
    except Exception as e:
        print(f"History error: {e}")
        return []


@router.get("/api/market/funds/{code}/details")
async def get_fund_market_details(code: str):
    """Get fund market details (manager, size, performance, holdings)."""
    try:
        info_dict = {"manager": "---", "size": "---", "est_date": "---", "type": "---", "company": "---", "rating": "---", "nav": "---"}
        try:
            df_info = ak.fund_individual_basic_info_xq(symbol=code)
            raw_info = dict(zip(df_info.iloc[:, 0], df_info.iloc[:, 1]))

            def get_val(d, *keys):
                for k in d.keys():
                    for target in keys:
                        if target in str(k):
                            return d[k]
                return "---"

            info_dict = {
                "manager": get_val(raw_info, "经理"),
                "size": get_val(raw_info, "规模"),
                "est_date": get_val(raw_info, "成立"),
                "type": get_val(raw_info, "类型"),
                "company": get_val(raw_info, "公司"),
                "rating": get_val(raw_info, "评级"),
                "nav": get_val(raw_info, "净值", "价格")
            }
        except Exception as info_e:
            print(f"Basic info fetch failed for {code}: {info_e}")
            pass

        if info_dict["nav"] == "---":
            try:
                df_nav = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
                if df_nav is not None and not df_nav.empty:
                    latest_row = df_nav.iloc[-1]
                    nav_col = None
                    for col in df_nav.columns:
                        if '单位净值' in str(col):
                            nav_col = col
                            break
                    if not nav_col:
                        for col in df_nav.columns:
                            if '净值' in str(col):
                                nav_col = col
                                break
                    if not nav_col and len(df_nav.columns) >= 2:
                        nav_col = df_nav.columns[1]

                    if nav_col:
                        info_dict["nav"] = str(latest_row[nav_col])
            except:
                pass

        perf_list = []
        try:
            df_perf = ak.fund_individual_achievement_xq(symbol=code)
            if df_perf is not None and not df_perf.empty:
                for _, row in df_perf.iterrows():
                    perf_list.append({
                        "时间范围": row.get("周期", "---"),
                        "收益率": row.get("本产品区间收益", 0.0),
                        "同类排名": row.get("周期收益同类排名", "---")
                    })
        except:
            pass

        portfolio = []
        try:
            df_hold = ak.fund_portfolio_hold_em(symbol=code)
            if df_hold is not None and not df_hold.empty:
                portfolio = df_hold.head(10).to_dict(orient='records')
        except:
            pass

        return sanitize_data({
            "info": info_dict,
            "performance": perf_list,
            "portfolio": portfolio
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error fetching fund details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/market/funds/{code}/nav")
async def get_fund_nav_history(code: str):
    """Get fund NAV history for charts."""
    try:
        df_nav = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df_nav is not None and not df_nav.empty:
            df_nav = df_nav.tail(100).copy()

            found_date = False
            found_value = False
            for col in df_nav.columns:
                col_str = str(col)
                if '日期' in col_str or 'date' in col_str.lower():
                    df_nav = df_nav.rename(columns={col: 'date'})
                    found_date = True
                if '净值' in col_str or 'value' in col_str.lower():
                    df_nav = df_nav.rename(columns={col: 'value'})
                    found_value = True

            if not found_date and len(df_nav.columns) >= 1:
                df_nav.columns.values[0] = 'date'
            if not found_value and len(df_nav.columns) >= 2:
                df_nav.columns.values[1] = 'value'

            df_nav['value'] = pd.to_numeric(df_nav['value'], errors='coerce')
            df_nav = df_nav.dropna(subset=['value'])

            return sanitize_data(df_nav[['date', 'value']].to_dict(orient='records'))
        return []
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error fetching NAV history: {e}")
        return []
