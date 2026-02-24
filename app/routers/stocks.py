"""
Stock management endpoints.
"""
from glob import glob
import json
import asyncio
import os
import uuid
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
import akshare as ak
import pandas as pd
from jose import JWTError, jwt

from app.models.stocks import StockItem, StockAnalyzeRequest
from app.models.auth import User
from app.core.dependencies import get_current_user, get_user_report_dir
from app.core.cache import stock_feature_cache
from app.core.utils import sanitize_for_json, sanitize_data
from src.auth import SECRET_KEY, ALGORITHM
from src.storage.db import get_all_stocks, upsert_stock, delete_stock, get_user_by_username
from src.data_sources.akshare_api import (
    get_stock_realtime_quote,
    get_stock_realtime_quote_min,
    get_market_activity,
    get_hot_stocks,
    get_limit_up_pool,
    get_limit_down_pool,
    get_northbound_flow,
)
from src.data_sources.tushare_client import (
    get_financial_indicators, get_income_statement, get_balance_sheet, get_cashflow_statement,
    get_top10_holders, get_shareholder_number,
    get_margin_detail,
    get_forecast, get_share_float, get_dividend,
    get_stock_factors, get_chip_performance,
    _get_tushare_pro
)
from src.data_sources.itick_client import (
    is_itick_enabled,
    infer_region_and_code,
    get_stock_quote as get_itick_stock_quote,
    get_stock_quotes as get_itick_stock_quotes,
    map_quote_to_legacy_fields as map_itick_quote_to_legacy_fields,
)
from src.services.itick_ws_gateway import itick_stock_ws_gateway


def _chunk_list(values: List[str], chunk_size: int) -> List[List[str]]:
    return [values[i:i + chunk_size] for i in range(0, len(values), chunk_size)]


def _apply_itick_watchlist_quotes(stocks: List[Dict[str, Any]]) -> Tuple[List[StockItem], int]:
    grouped_codes: Dict[str, List[str]] = defaultdict(list)
    lookup_key_by_code: Dict[str, Tuple[Optional[str], str]] = {}
    seen_by_region: Dict[str, set] = defaultdict(set)

    for stock in stocks:
        region, symbol = infer_region_and_code(stock.get("code", ""), stock.get("market"))
        lookup_key_by_code[stock["code"]] = (region, symbol)
        if not region or not symbol:
            continue
        if symbol in seen_by_region[region]:
            continue
        seen_by_region[region].add(symbol)
        grouped_codes[region].append(symbol)

    quotes_lookup: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for region, symbols in grouped_codes.items():
        for chunk in _chunk_list(symbols, 60):
            data = get_itick_stock_quotes(region, chunk)
            for symbol, quote in data.items():
                quotes_lookup[(region, symbol)] = quote

    hit_count = 0
    results: List[StockItem] = []
    for stock in stocks:
        item = dict(stock)
        region, symbol = lookup_key_by_code.get(stock["code"], (None, ""))
        if region and symbol:
            quote = quotes_lookup.get((region, symbol))
            if quote:
                hit_count += 1
                if quote.get("ld") is not None:
                    item["price"] = float(quote["ld"])
                if quote.get("chp") is not None:
                    item["change_pct"] = float(quote["chp"])
                if quote.get("v") is not None:
                    item["volume"] = float(quote["v"])
        results.append(StockItem(**item))

    return results, hit_count

router = APIRouter(prefix="/api/stocks", tags=["Stocks"])


def _get_user_from_ws_token(token: str) -> Optional[User]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

    username = payload.get("sub")
    user_id = payload.get("id")
    if not username or not user_id:
        return None

    user_dict = get_user_by_username(username)
    if not user_dict:
        return None

    if int(user_dict.get("id", 0)) != int(user_id):
        return None

    return User(
        id=user_dict["id"],
        username=user_dict["username"],
        email=user_dict.get("email"),
        is_active=bool(user_dict.get("is_active", True)),
    )


async def _stocks_live_sender(websocket: WebSocket, queue: asyncio.Queue) -> None:
    while True:
        event = await queue.get()
        await websocket.send_json(event)


@router.websocket("/live/ws")
async def stocks_live_ws_endpoint(websocket: WebSocket):
    token = (websocket.query_params.get("token") or "").strip()
    current_user = _get_user_from_ws_token(token)
    if not current_user:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    if not is_itick_enabled():
        await websocket.close(code=1013, reason="iTick token not configured")
        return

    await websocket.accept()
    client_id = f"user-{current_user.id}-{uuid.uuid4().hex[:10]}"

    try:
        queue = await itick_stock_ws_gateway.register_client(client_id)
    except Exception as e:
        await websocket.send_json({"type": "system", "event": "error", "message": str(e)})
        await websocket.close(code=1011, reason="Gateway unavailable")
        return

    sender_task = asyncio.create_task(_stocks_live_sender(websocket, queue))
    await websocket.send_json({
        "type": "system",
        "event": "connected",
        "client_id": client_id,
        "ts": int(datetime.now().timestamp() * 1000),
    })

    try:
        while True:
            payload = await websocket.receive_json()
            if not isinstance(payload, dict):
                continue

            action = str(payload.get("ac", "")).strip().lower()
            if action == "ping":
                await websocket.send_json({
                    "type": "system",
                    "event": "pong",
                    "ts": int(datetime.now().timestamp() * 1000),
                })
                continue

            if action not in {"subscribe", "unsubscribe"}:
                await websocket.send_json({
                    "type": "system",
                    "event": "error",
                    "message": "unsupported action",
                })
                continue

            symbol_raw = str(payload.get("symbol") or payload.get("code") or "").strip()
            market_raw = str(payload.get("market") or "").strip()
            region_raw = str(payload.get("region") or "").strip().upper()
            if not symbol_raw:
                await websocket.send_json({
                    "type": "system",
                    "event": "error",
                    "message": "symbol is required",
                })
                continue

            if region_raw:
                symbol = symbol_raw.upper()
                region = region_raw
            else:
                region, symbol = infer_region_and_code(symbol_raw, market_raw)
                symbol = symbol.upper()

            if not region or not symbol:
                await websocket.send_json({
                    "type": "system",
                    "event": "error",
                    "message": "unable to infer symbol region",
                })
                continue

            types = payload.get("types")
            type_list = [str(v) for v in types] if isinstance(types, list) else []
            if action == "subscribe":
                normalized = await itick_stock_ws_gateway.subscribe(client_id, symbol, region, type_list)
                await websocket.send_json({
                    "type": "system",
                    "event": "subscribed",
                    "symbol": symbol,
                    "region": region,
                    "types": normalized,
                })
            else:
                normalized = await itick_stock_ws_gateway.unsubscribe(client_id, symbol, region, type_list)
                await websocket.send_json({
                    "type": "system",
                    "event": "unsubscribed",
                    "symbol": symbol,
                    "region": region,
                    "types": normalized,
                })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"stocks live websocket error: {e}")
    finally:
        sender_task.cancel()
        try:
            await sender_task
        except asyncio.CancelledError:
            pass
        await itick_stock_ws_gateway.remove_client(client_id)


@router.get("", response_model=List[StockItem])
async def get_stocks_endpoint(current_user: User = Depends(get_current_user)):
    """Get all stocks for current user with real-time quotes."""
    try:
        stocks = get_all_stocks(user_id=current_user.id)

        if not stocks:
            return []

        # iTick first for low-latency quotes when token is configured.
        if is_itick_enabled():
            try:
                itick_results, hit_count = await asyncio.to_thread(_apply_itick_watchlist_quotes, stocks)
                if hit_count > 0:
                    return itick_results
            except Exception as itick_err:
                print(f"iTick watchlist quote failed, fallback to legacy providers: {itick_err}")

        # Try tushare first, then fall back to akshare
        quotes_lookup = {}
        use_akshare_fallback = False

        try:
            from src.data_sources.tushare_client import get_realtime_quotes

            # Get all stock codes
            stock_codes = [s['code'] for s in stocks]

            # Fetch realtime quotes in batch
            quotes_df = await asyncio.to_thread(get_realtime_quotes, stock_codes)

            # Build a lookup dict for quick access
            if quotes_df is not None and not quotes_df.empty:
                for _, row in quotes_df.iterrows():
                    # The ts_code might have suffix, extract plain code
                    ts_code = str(row.get('ts_code', ''))
                    plain_code = ts_code.split('.')[0] if '.' in ts_code else ts_code
                    quotes_lookup[plain_code] = row

            # If tushare returned no data, use akshare fallback
            if not quotes_lookup:
                use_akshare_fallback = True

        except ImportError:
            # TuShare not installed, use akshare
            use_akshare_fallback = True
        except BaseException:
            # TuShare has known issues, silently fall back to akshare
            use_akshare_fallback = True

        # Use akshare fallback if needed
        if use_akshare_fallback:
            # 预先获取所有股票的昨收价（从 TuShare daily）
            prev_close_map = {}
            try:
                pro = _get_tushare_pro()
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')
                
                def fetch_prev_close(code):
                    ts_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
                    try:
                        df_daily = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                        if df_daily is not None and not df_daily.empty:
                            df_daily = df_daily.sort_values('trade_date', ascending=False)
                            return (code, float(df_daily.iloc[0]['pre_close']))
                    except Exception:
                        pass
                    return (code, None)
                
                # 并行获取昨收
                with ThreadPoolExecutor(max_workers=10) as executor:
                    results_prev = list(executor.map(fetch_prev_close, [s['code'] for s in stocks]))
                    for code, prev_close in results_prev:
                        if prev_close:
                            prev_close_map[code] = prev_close
                            
            except Exception as e:
                print(f"Failed to fetch prev_close from TuShare: {e}")

            def fetch_single_quote(stock):
                item = dict(stock)
                code = stock['code']
                try:
                    # 优先使用分钟线获取最新价（更稳定）
                    quote = get_stock_realtime_quote_min(code)
                    
                    # 如果分钟线没数据，降级到原方法
                    if not quote or not quote.get('最新价'):
                        quote = get_stock_realtime_quote(code)
                    
                    if quote:
                        price = quote.get('最新价')
                        volume = quote.get('成交量')

                        if price is not None:
                            item['price'] = float(price)
                            
                            # 使用预获取的昨收计算涨跌幅
                            prev_close = prev_close_map.get(code)
                            if prev_close and prev_close > 0:
                                change_pct = ((float(price) - prev_close) / prev_close) * 100
                                item['change_pct'] = round(change_pct, 2)
                            elif quote.get('涨跌幅') is not None:
                                item['change_pct'] = float(quote.get('涨跌幅'))
                                
                        if volume is not None:
                            item['volume'] = float(volume)
                except Exception as e:
                    print(f"Error fetching quote for {code}: {e}")
                    import traceback
                    traceback.print_exc()
                return StockItem(**item)

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=10) as executor:
                results = await loop.run_in_executor(None, lambda: list(executor.map(fetch_single_quote, stocks)))

            return results

        # Use tushare data
        results = []
        for stock in stocks:
            item = dict(stock)
            code = stock['code']

            if code in quotes_lookup:
                row = quotes_lookup[code]
                # Map tushare fields to our schema
                price = row.get('price')
                pct_chg = row.get('pct_chg')
                vol = row.get('vol')

                if price is not None and pd.notna(price):
                    item['price'] = float(price)
                if pct_chg is not None and pd.notna(pct_chg):
                    item['change_pct'] = float(pct_chg)
                if vol is not None and pd.notna(vol):
                    # tushare vol is in shares, keep as is
                    item['volume'] = float(vol)

            results.append(StockItem(**item))

        return results

    except Exception as e:
        print(f"Error reading stocks: {e}")
        import traceback
        traceback.print_exc()
        return []


@router.post("")
async def save_stocks(stocks: List[StockItem], current_user: User = Depends(get_current_user)):
    """Save multiple stocks."""
    try:
        for stock in stocks:
            stock_dict = stock.model_dump()
            upsert_stock(stock_dict, user_id=current_user.id)
        return {"status": "success"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{code}")
async def upsert_stock_endpoint(code: str, stock: StockItem, current_user: User = Depends(get_current_user)):
    """Create or update a stock."""
    try:
        stock_dict = stock.model_dump()
        upsert_stock(stock_dict, user_id=current_user.id)
        return {"status": "success"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/reports")
async def list_stock_reports(current_user: User = Depends(get_current_user)):
    """List all stock analysis reports for the current user"""
    user_report_dir = get_user_report_dir(current_user.id)
    stocks_dir = os.path.join(user_report_dir, "stocks")
    
    if not os.path.exists(stocks_dir):
        return []

    reports = []
    files = glob(os.path.join(stocks_dir, "*.md"))
    files.sort(key=os.path.getmtime, reverse=True)

    for f in files:
        filename = os.path.basename(f)
        try:
            # Format: YYYY-MM-DD_{mode}_{stock_code}_{stock_name}.md
            name_no_ext = os.path.splitext(filename)[0]
            parts = name_no_ext.split("_")

            if len(parts) >= 4:
                date_str = parts[0]
                mode = parts[1]
                code = parts[2]
                name = "_".join(parts[3:])

                reports.append({
                    "filename": filename,
                    "date": date_str,
                    "mode": mode,
                    "stock_code": code,
                    "stock_name": name
                })
        except Exception as e:
            print(f"Error parsing stock report {filename}: {e}")
            continue

    return reports


# ============================================================================
# Market Data Endpoints (公开接口，无需登录)
# ============================================================================

@router.get("/market/summary")
async def get_market_summary():
    """
    获取市场概览数据：涨跌统计、北向资金等
    """
    try:
        # 并行获取市场活跃度和北向资金
        activity_result = await asyncio.to_thread(get_market_activity)
        northbound_result = await asyncio.to_thread(get_northbound_flow)
        
        return {
            "activity": activity_result,
            "northbound": northbound_result,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"Error fetching market summary: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/hot")
async def get_hot_stocks_endpoint(limit: int = 20):
    """
    获取热门股票排行榜
    """
    try:
        cache_key = f"hot_stocks_{limit}"
        cached = stock_feature_cache.get(cache_key, ttl_minutes=10)
        if cached:
            return cached

        result = await asyncio.to_thread(get_hot_stocks, limit)
        response = {
            "items": result,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        stock_feature_cache.set(cache_key, response)
        return response
    except Exception as e:
        print(f"Error fetching hot stocks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/limit-up")
async def get_limit_up_endpoint(limit: int = 30, date: str = None):
    """
    获取涨停池数据
    """
    try:
        result = await asyncio.to_thread(get_limit_up_pool, date, limit)
        return {
            "items": result,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"Error fetching limit up pool: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/limit-down")
async def get_limit_down_endpoint(limit: int = 30, date: str = None):
    """
    获取跌停池数据
    """
    try:
        result = await asyncio.to_thread(get_limit_down_pool, date, limit)
        return {
            "items": result,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"Error fetching limit down pool: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# AI 市场速览缓存
_ai_brief_cache: Dict[str, Any] = {}
_ai_brief_cache_time: float = 0


@router.get("/market/ai-brief")
async def get_market_ai_brief():
    """
    获取 AI 市场速览，结合热门股票和涨跌停数据生成简短分析
    缓存5分钟
    """
    import time
    global _ai_brief_cache, _ai_brief_cache_time
    
    # 检查缓存 (5分钟)
    cache_ttl = 300
    now = time.time()
    if _ai_brief_cache and (now - _ai_brief_cache_time) < cache_ttl:
        return _ai_brief_cache
    
    try:
        # 并行获取数据
        activity_result = await asyncio.to_thread(get_market_activity)
        hot_result = await asyncio.to_thread(get_hot_stocks, 10)
        limit_up_result = await asyncio.to_thread(get_limit_up_pool, None, 20)
        limit_down_result = await asyncio.to_thread(get_limit_down_pool, None, 10)
        
        # 构建 LLM prompt
        from src.llm.client import get_llm_client
        
        # 统计涨停行业分布
        industry_count = {}
        for stock in limit_up_result:
            ind = stock.get('industry', '其他')
            industry_count[ind] = industry_count.get(ind, 0) + 1
        top_industries = sorted(industry_count.items(), key=lambda x: -x[1])[:5]
        
        hot_names = [f"{s['name']}({s['change_pct']:+.1f}%)" for s in hot_result[:5]]
        limit_up_names = [f"{s['name']}({s['consecutive']}板)" if s['consecutive'] > 1 else s['name'] for s in limit_up_result[:5]]
        limit_down_names = [s['name'] for s in limit_down_result[:5]]
        
        prompt = f"""你是一位专业的A股市场分析师。请根据以下今日市场数据，生成一段简洁的市场速览（2-3句话，不超过100字）。

## 今日市场数据
- 上涨家数：{activity_result.get('上涨', 0)}，下跌家数：{activity_result.get('下跌', 0)}
- 涨停：{activity_result.get('涨停', 0)}只（真实涨停{activity_result.get('真实涨停', 0)}只）
- 跌停：{activity_result.get('跌停', 0)}只（真实跌停{activity_result.get('真实跌停', 0)}只）

## 热门股票 TOP5
{', '.join(hot_names)}

## 涨停行业分布
{', '.join([f"{ind}({cnt}只)" for ind, cnt in top_industries])}

## 部分涨停股
{', '.join(limit_up_names)}

## 部分跌停股
{', '.join(limit_down_names) if limit_down_names else '无'}

请输出：
1. 一句话概括今日市场整体情况（多空态势）
2. 一句话点明今日市场主线/热点板块
3. 如有特别值得关注的个股（如连板股），简要提及

直接输出分析内容，不要包含标题或序号。"""

        llm = get_llm_client()
        brief = await asyncio.to_thread(llm.generate_content, prompt)
        
        result = {
            "brief": brief.strip(),
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "top_industries": [{"name": ind, "count": cnt} for ind, cnt in top_industries],
        }
        
        # 更新缓存
        _ai_brief_cache = result
        _ai_brief_cache_time = now
        
        return result
        
    except Exception as e:
        print(f"Error generating AI market brief: {e}")
        import traceback
        traceback.print_exc()
        # 返回降级内容
        return {
            "brief": "AI 分析暂时不可用，请稍后重试。",
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "top_industries": [],
            "error": True
        }


@router.delete("/{code}")
async def delete_stock_endpoint(code: str, current_user: User = Depends(get_current_user)):
    """Delete a stock."""
    try:
        delete_stock(code, user_id=current_user.id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}/quote")
async def get_stock_quote_endpoint(code: str, current_user: User = Depends(get_current_user)):
    """Get real-time stock quote."""
    try:
        if is_itick_enabled():
            region, symbol = infer_region_and_code(code)
            if region and symbol:
                quote = await asyncio.to_thread(get_itick_stock_quote, region, symbol)
                if quote:
                    return sanitize_data(map_itick_quote_to_legacy_fields(quote, code=symbol))
        data = await asyncio.to_thread(get_stock_realtime_quote, code)
        return sanitize_data(data)
    except Exception as e:
        print(f"Error fetching quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{code}/analyze")
async def analyze_stock_endpoint(
    code: str,
    request: StockAnalyzeRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate AI analysis for a stock."""
    try:
        from src.analysis.stock import StockAnalyst

        analyst = StockAnalyst()
        report = await asyncio.to_thread(
            analyst.analyze,
            stock_code=code,
            mode=request.mode,
            user_id=current_user.id
        )
        return {"status": "success", "report": report}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}/financial-summary")
async def get_stock_financial_summary(code: str, current_user: User = Depends(get_current_user)):
    """Get financial summary from financial indicators."""
    try:
        # Check cache first
        cache_key = f"financial_summary_{code}"
        cached = stock_feature_cache.get(cache_key, ttl_minutes=720)
        if cached:
            return cached

        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, lambda: ak.stock_financial_analysis_indicator(symbol=code))

        if df is None or df.empty:
            return {"message": "No financial data available"}

        df_recent = df.head(5)

        result = {
            "code": code,
            "periods": [],
            "metrics": {}
        }

        key_metrics = [
            "净资产收益率(%)", "总资产报酬率(%)", "资产负债率(%)",
            "流动比率", "速动比率", "存货周转天数(天)",
            "应收账款周转天数(天)", "营业利润率(%)", "净利润率(%)"
        ]

        for col in df_recent.columns:
            if col not in ['日期']:
                result["metrics"][col] = []

        for idx, row in df_recent.iterrows():
            result["periods"].append(str(row.get('日期', idx)))
            for col in df_recent.columns:
                if col not in ['日期'] and col in result["metrics"]:
                    val = row[col]
                    if pd.isna(val):
                        result["metrics"][col].append(None)
                    else:
                        result["metrics"][col].append(float(val))

        stock_feature_cache.set(cache_key, result)
        return sanitize_for_json(result)
    except Exception as e:
        print(f"Error fetching financial summary for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}/shareholders/circulate")
async def get_stock_circulate_shareholders(code: str, current_user: User = Depends(get_current_user)):
    """Get top 10 circulating shareholders (AkShare).

    Note: Kept as a separate endpoint because the main `/shareholders` endpoint
    returns the structured TuShare-based shareholder analysis data used by the UI.
    """
    try:
        cache_key = f"shareholders_circulate_{code}"
        cached = stock_feature_cache.get(cache_key, ttl_minutes=360)
        if cached:
            return cached

        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, lambda: ak.stock_circulate_stock_holder(symbol=code))

        if df is None or df.empty:
            return {"message": "No shareholder data available"}

        latest_date = df['变动日期'].max() if '变动日期' in df.columns else df.iloc[0, 0]
        df_latest = df[df['变动日期'] == latest_date] if '变动日期' in df.columns else df.head(10)

        shareholders = []
        for _, row in df_latest.iterrows():
            shareholders.append({
                "rank": int(row.get('序号', 0)),
                "name": row.get('股东名称', ''),
                "type": row.get('股东性质', ''),
                "shares": float(row.get('持股数量', 0)),
                "ratio": float(row.get('占流通股比例', 0)),
                "change": row.get('变动比例', ''),
            })

        result = {
            "code": code,
            "report_date": str(latest_date),
            "shareholders": shareholders[:10]
        }

        stock_feature_cache.set(cache_key, result)
        return sanitize_for_json(result)
    except Exception as e:
        print(f"Error fetching shareholders for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}/fund-holdings")
async def get_stock_fund_holdings(code: str, current_user: User = Depends(get_current_user)):
    """Get fund holdings for a stock."""
    try:
        cache_key = f"fund_holdings_{code}"
        cached = stock_feature_cache.get(cache_key, ttl_minutes=360)
        if cached:
            return cached

        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, lambda: ak.stock_report_fund_hold_detail(symbol=code))

        if df is None or df.empty:
            return {"message": "No fund holding data available"}

        df_recent = df.head(20)

        holdings = []
        for _, row in df_recent.iterrows():
            holdings.append({
                "fund_code": row.get('基金代码', ''),
                "fund_name": row.get('基金简称', ''),
                "shares": float(row.get('持有股票数', 0)) if row.get('持有股票数') else 0,
                "value": float(row.get('持有股票市值', 0)) if row.get('持有股票市值') else 0,
                "ratio_nav": float(row.get('占基金净值比', 0)) if row.get('占基金净值比') else 0,
                "report_date": str(row.get('报告日期', '')),
            })

        result = {
            "code": code,
            "holdings": holdings
        }

        stock_feature_cache.set(cache_key, result)
        return sanitize_for_json(result)
    except Exception as e:
        print(f"Error fetching fund holdings for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}/quantitative")
async def get_stock_quantitative_indicators(code: str, current_user: User = Depends(get_current_user)):
    """Get quantitative indicators (momentum, volatility, moving averages)."""
    try:
        cache_key = f"quant_{code}"
        cached = stock_feature_cache.get(cache_key, ttl_minutes=30)
        if cached:
            return cached

        loop = asyncio.get_running_loop()

        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        end_date = datetime.now().strftime('%Y%m%d')

        def fetch_hist_df() -> pd.DataFrame:
            """Prefer TuShare daily + adj_factor (qfq), fall back to AkShare if needed."""
            # 1) Try TuShare
            try:
                pro = _get_tushare_pro()
                ts_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"

                daily_df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if daily_df is not None and not daily_df.empty:
                    # TuShare returns newest first; sort ascending for rolling calculations
                    daily_df = daily_df.sort_values('trade_date', ascending=True)

                    # Try qfq adjustment using adj_factor
                    try:
                        adj_df = pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
                        if adj_df is not None and not adj_df.empty and 'adj_factor' in adj_df.columns:
                            adj_df = adj_df.sort_values('trade_date', ascending=True)
                            latest_adj = float(adj_df.iloc[-1]['adj_factor'])
                            merged = daily_df.merge(
                                adj_df[['trade_date', 'adj_factor']],
                                on='trade_date',
                                how='left'
                            )
                            merged['adj_factor'] = pd.to_numeric(merged['adj_factor'], errors='coerce')
                            merged['close'] = pd.to_numeric(merged['close'], errors='coerce')
                            if latest_adj and latest_adj > 0:
                                merged['close_qfq'] = merged['close'] * merged['adj_factor'] / latest_adj
                            else:
                                merged['close_qfq'] = merged['close']
                            close_series = merged['close_qfq']
                        else:
                            close_series = pd.to_numeric(daily_df['close'], errors='coerce')
                    except Exception:
                        close_series = pd.to_numeric(daily_df['close'], errors='coerce')

                    # Normalize to AkShare-like columns for downstream calculations
                    out = pd.DataFrame({
                        '日期': daily_df['trade_date'].astype(str),
                        '收盘': close_series
                    })
                    out = out.dropna(subset=['收盘'])
                    return out
            except Exception:
                pass

            # 2) Fall back to AkShare (may hit EastMoney network/proxy issues)
            return ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                adjust="qfq"
            )

        df = await loop.run_in_executor(None, fetch_hist_df)

        if df is None or df.empty or len(df) < 30:
            return {"message": "Insufficient data for quantitative analysis"}

        # Calculate indicators
        if '收盘' not in df.columns:
            return {"message": "Insufficient data for quantitative analysis"}

        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        df['MA60'] = df['收盘'].rolling(window=60).mean()

        df['RSI'] = _calculate_rsi(df['收盘'], 14)

        df['daily_return'] = df['收盘'].pct_change()
        df['volatility_20d'] = df['daily_return'].rolling(window=20).std() * (252 ** 0.5)

        latest = df.iloc[-1]
        prev_month = df.iloc[-21] if len(df) >= 21 else df.iloc[0]
        prev_3month = df.iloc[-63] if len(df) >= 63 else df.iloc[0]

        result = {
            "code": code,
            "latest_price": float(latest['收盘']),
            "moving_averages": {
                "MA5": float(latest['MA5']) if pd.notna(latest['MA5']) else None,
                "MA20": float(latest['MA20']) if pd.notna(latest['MA20']) else None,
                "MA60": float(latest['MA60']) if pd.notna(latest['MA60']) else None,
            },
            "momentum": {
                "1m_return": float((latest['收盘'] / prev_month['收盘'] - 1) * 100),
                "3m_return": float((latest['收盘'] / prev_3month['收盘'] - 1) * 100),
            },
            "rsi_14": float(latest['RSI']) if pd.notna(latest['RSI']) else None,
            "volatility_20d": float(latest['volatility_20d']) if pd.notna(latest['volatility_20d']) else None,
            "analysis_date": datetime.now().strftime('%Y-%m-%d'),
        }

        # Add signal interpretations
        signals = []
        if result['rsi_14']:
            if result['rsi_14'] > 70:
                signals.append({"type": "warning", "message": "RSI显示超买"})
            elif result['rsi_14'] < 30:
                signals.append({"type": "opportunity", "message": "RSI显示超卖"})

        if result['moving_averages']['MA5'] and result['moving_averages']['MA20']:
            if result['moving_averages']['MA5'] > result['moving_averages']['MA20']:
                signals.append({"type": "bullish", "message": "5日均线在20日均线上方"})
            else:
                signals.append({"type": "bearish", "message": "5日均线在20日均线下方"})

        result['signals'] = signals

        stock_feature_cache.set(cache_key, result)
        return sanitize_for_json(result)
    except Exception as e:
        print(f"Error calculating quant indicators for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _calculate_rsi(prices, period=14):
    """Calculate RSI indicator."""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


@router.get("/{code}/ai-diagnosis")
async def get_stock_ai_diagnosis(
    code: str,
    force_refresh: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Get AI-powered stock diagnosis with five-dimension scoring."""
    try:
        cache_key = f"ai_diagnosis_{code}"
        if not force_refresh:
            cached = stock_feature_cache.get(cache_key, ttl_minutes=60)
            if cached:
                return cached

        # Gather data in parallel, but don't fail the whole endpoint if one data source is down
        financial_task = get_stock_financial_summary(code, current_user)
        quant_task = get_stock_quantitative_indicators(code, current_user)
        financial_result, quant_result = await asyncio.gather(
            financial_task,
            quant_task,
            return_exceptions=True
        )

        financial_data = None if isinstance(financial_result, Exception) else financial_result
        quant_data = None if isinstance(quant_result, Exception) else quant_result

        # Get basic quote
        quote = await asyncio.to_thread(get_stock_realtime_quote, code)

        # Calculate 5-dimension scores
        scores = _calculate_stock_diagnosis_scores(quote, financial_data, quant_data)

        # If quant failed, add a gentle note (common when external data source is unreachable)
        if quant_data is None:
            scores['recommendations'].append("技术面数据获取失败（网络/代理问题），本次评分偏保守")

        total_score = int(scores.get('total', 0))
        grade = _get_grade(total_score)
        if total_score >= 80:
            recommendation = "建议买入"
            action_advice = "可分批布局，设好止损线。"
            key_focus = "关注趋势延续与量能变化"
        elif total_score >= 60:
            recommendation = "建议持有"
            action_advice = "以持有为主，回撤加仓需谨慎。"
            key_focus = "关注业绩兑现与估值变化"
        elif total_score >= 40:
            recommendation = "建议观望"
            action_advice = "等待信号更明确后再介入。"
            key_focus = "关注拐点信号与风险事件"
        else:
            recommendation = "建议减持"
            action_advice = "控制仓位，避免逆势加仓。"
            key_focus = "关注止损纪律与基本面风险"

        highlights: List[str] = []
        risks: List[str] = []
        if scores.get('fundamental', 0) >= 15:
            highlights.append("基本面相对稳健")
        if scores.get('technical', 0) >= 15:
            highlights.append("技术面偏强")
        if scores.get('momentum', 0) >= 15:
            highlights.append("动量较强")
        if not highlights:
            highlights.append("暂无明显强势信号")

        # Reuse recommendations as risks when they look like warnings
        for rec in scores.get('recommendations', []):
            if any(k in rec for k in ["风险", "偏高", "偏低", "谨慎", "走势偏弱", "失败"]):
                risks.append(rec)
        if not risks and total_score < 60:
            risks.append("综合评分一般，注意回撤风险")

        # Match frontend `DiagnosisResponse` schema
        result = {
            "code": code,
            "name": quote.get('name', code) if quote else code,
            "diagnosis": {
                "score": total_score,
                "rating": grade,
                "recommendation": recommendation,
                "highlights": highlights,
                "risks": risks,
                "action_advice": action_advice,
                "key_focus": key_focus,
            },
            "data_timestamp": datetime.now().isoformat(),

            # Extra fields for future UI use (harmless for current frontend)
            "dimensions": [
                {"name": "基本面", "score": scores['fundamental'], "max": 20},
                {"name": "技术面", "score": scores['technical'], "max": 20},
                {"name": "资金面", "score": scores['capital'], "max": 20},
                {"name": "估值", "score": scores['valuation'], "max": 20},
                {"name": "动量", "score": scores['momentum'], "max": 20},
            ],
        }

        stock_feature_cache.set(cache_key, result)
        return sanitize_for_json(result)
    except Exception as e:
        print(f"Error generating AI diagnosis for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _calculate_stock_diagnosis_scores(quote, financial_data, quant_data):
    """Calculate diagnosis scores for a stock."""
    scores = {
        'fundamental': 10,
        'technical': 10,
        'capital': 10,
        'valuation': 10,
        'momentum': 10,
        'recommendations': []
    }

    # Fundamental score based on financial data
    if financial_data and 'metrics' in financial_data:
        metrics = financial_data['metrics']
        roe_vals = metrics.get('净资产收益率(%)', [])
        if roe_vals and roe_vals[0] is not None:
            if roe_vals[0] > 15:
                scores['fundamental'] = 18
            elif roe_vals[0] > 10:
                scores['fundamental'] = 15
            elif roe_vals[0] > 5:
                scores['fundamental'] = 12
            else:
                scores['fundamental'] = 8
                scores['recommendations'].append("ROE偏低，盈利能力待提升")

    # Technical score based on quantitative indicators
    if quant_data and 'rsi_14' in quant_data:
        rsi = quant_data.get('rsi_14')
        if rsi:
            if 40 <= rsi <= 60:
                scores['technical'] = 16
            elif 30 <= rsi <= 70:
                scores['technical'] = 14
            else:
                scores['technical'] = 10
                if rsi > 70:
                    scores['recommendations'].append("RSI偏高，注意回调风险")
                elif rsi < 30:
                    scores['recommendations'].append("RSI偏低，可能存在超卖机会")

    # Valuation score based on PE/PB
    if quote:
        pe = quote.get('pe')
        if pe:
            try:
                pe_val = float(pe)
                if 0 < pe_val < 20:
                    scores['valuation'] = 18
                elif 20 <= pe_val < 40:
                    scores['valuation'] = 14
                elif pe_val >= 40:
                    scores['valuation'] = 8
                    scores['recommendations'].append("PE较高，估值偏贵")
            except:
                pass

    # Momentum score based on return
    if quant_data and 'momentum' in quant_data:
        ret_1m = quant_data['momentum'].get('1m_return', 0)
        if ret_1m > 10:
            scores['momentum'] = 17
        elif ret_1m > 0:
            scores['momentum'] = 14
        elif ret_1m > -10:
            scores['momentum'] = 10
        else:
            scores['momentum'] = 7
            scores['recommendations'].append("近期走势偏弱")

    # Capital score (simplified)
    if quote:
        turnover_rate = quote.get('turnover_rate')
        if turnover_rate:
            try:
                tr = float(turnover_rate)
                if 1 < tr < 5:
                    scores['capital'] = 16
                elif 5 <= tr < 10:
                    scores['capital'] = 13
                else:
                    scores['capital'] = 10
            except:
                pass

    scores['total'] = sum([
        scores['fundamental'], scores['technical'],
        scores['capital'], scores['valuation'], scores['momentum']
    ])

    return scores


def _get_grade(score):
    """Convert score to grade."""
    if score >= 80:
        return "A"
    elif score >= 60:
        return "B"
    elif score >= 40:
        return "C"
    else:
        return "D"


@router.get("/{code}/money-flow")
async def get_stock_money_flow(code: str, current_user: User = Depends(get_current_user)):
    """Get capital flow data for a stock."""
    try:
        cache_key = f"money_flow_{code}"
        cached = stock_feature_cache.get(cache_key, ttl_minutes=15)
        if cached:
            return cached

        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(
            None,
            lambda: ak.stock_individual_fund_flow(stock=code, market="sh" if code.startswith("6") else "sz")
        )

        if df is None or df.empty:
            return {"message": "No money flow data available"}

        df_recent = df.head(20)

        flows = []
        for _, row in df_recent.iterrows():
            flows.append({
                "date": str(row.get('日期', '')),
                "main_in": float(row.get('主力净流入-净额', 0)) if pd.notna(row.get('主力净流入-净额')) else 0,
                "retail_in": float(row.get('小单净流入-净额', 0)) if pd.notna(row.get('小单净流入-净额')) else 0,
                "change_pct": float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅')) else 0,
            })

        result = {
            "code": code,
            "flows": flows
        }

        stock_feature_cache.set(cache_key, result)
        return sanitize_for_json(result)
    except Exception as e:
        print(f"Error fetching money flow for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch-quotes")
async def get_batch_stock_quotes(codes: str, current_user: User = Depends(get_current_user)):
    """Get quotes for multiple stocks at once."""
    try:
        code_list = [c.strip() for c in codes.split(",") if c.strip()]
        if not code_list:
            return {"quotes": []}

        # Limit to prevent abuse
        if len(code_list) > 50:
            code_list = code_list[:50]

        results: List[Dict[str, Any]] = []
        resolved_codes = set()

        # Try iTick batch by inferred market first.
        if is_itick_enabled():
            grouped: Dict[str, List[str]] = defaultdict(list)
            code_map: Dict[Tuple[str, str], str] = {}
            for raw_code in code_list:
                region, symbol = infer_region_and_code(raw_code)
                if not region or not symbol:
                    continue
                grouped[region].append(symbol)
                code_map[(region, symbol)] = raw_code

            for region, symbols in grouped.items():
                for chunk in _chunk_list(symbols, 60):
                    quotes = await asyncio.to_thread(get_itick_stock_quotes, region, chunk)
                    for symbol, quote in quotes.items():
                        legacy = map_itick_quote_to_legacy_fields(quote, code=symbol)
                        original_code = code_map.get((region, symbol), symbol)
                        legacy["代码"] = original_code
                        results.append(legacy)
                        resolved_codes.add(original_code)

        # Fallback for unresolved symbols.
        unresolved = [c for c in code_list if c not in resolved_codes]
        for code in unresolved:
            try:
                quote = await asyncio.to_thread(get_stock_realtime_quote, code)
                if quote:
                    results.append(quote)
            except Exception:
                pass

        return sanitize_data({"quotes": results})
    except Exception as e:
        print(f"Error in batch quotes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# Professional Stock Analysis Endpoints
# ====================================================================

@router.get("/{code}/financials")
async def get_stock_financials(code: str, current_user: User = Depends(get_current_user)):
    """
    Get financial health diagnosis data.

    Cache TTL: 1 day (1440 min)
    """
    cache_key = f"financials_{code}"
    cached = stock_feature_cache.get(cache_key, ttl_minutes=1440)
    if cached:
        return cached

    try:
        result = {
            "code": code,
            "indicators": [],
            "income": [],
            "balance": [],
            "cashflow": [],
            "health_score": None,
            "summary": {}
        }

        # Fetch all financial data in parallel using threads
        loop = asyncio.get_event_loop()

        indicators_task = loop.run_in_executor(None, lambda: get_financial_indicators(code, 8))
        income_task = loop.run_in_executor(None, lambda: get_income_statement(code, 4))
        balance_task = loop.run_in_executor(None, lambda: get_balance_sheet(code, 4))
        cashflow_task = loop.run_in_executor(None, lambda: get_cashflow_statement(code, 4))

        indicators_df, income_df, balance_df, cashflow_df = await asyncio.gather(
            indicators_task, income_task, balance_task, cashflow_task
        )

        # Process indicators
        if indicators_df is not None and not indicators_df.empty:
            result["indicators"] = sanitize_data(indicators_df.to_dict('records'))

            # Calculate health score based on latest indicators
            latest = indicators_df.iloc[0]
            score = 0
            count = 0

            # ROE scoring (higher is better, >15% is good)
            if pd.notna(latest.get('roe')):
                roe = float(latest['roe'])
                if roe > 20: score += 25
                elif roe > 15: score += 20
                elif roe > 10: score += 15
                elif roe > 5: score += 10
                else: score += 5
                count += 1

            # Debt ratio scoring (lower is better, <60% is good)
            if pd.notna(latest.get('debt_to_assets')):
                debt = float(latest['debt_to_assets'])
                if debt < 40: score += 25
                elif debt < 50: score += 20
                elif debt < 60: score += 15
                elif debt < 70: score += 10
                else: score += 5
                count += 1

            # Current ratio (>1.5 is good)
            if pd.notna(latest.get('current_ratio')):
                cr = float(latest['current_ratio'])
                if cr > 2: score += 25
                elif cr > 1.5: score += 20
                elif cr > 1: score += 15
                else: score += 10
                count += 1

            # Gross profit margin (higher is better)
            if pd.notna(latest.get('grossprofit_margin')):
                gpm = float(latest['grossprofit_margin'])
                if gpm > 40: score += 25
                elif gpm > 30: score += 20
                elif gpm > 20: score += 15
                else: score += 10
                count += 1

            if count > 0:
                result["health_score"] = round(score / count, 1)

            result["summary"] = {
                "roe": float(latest.get('roe', 0)) if pd.notna(latest.get('roe')) else None,
                "netprofit_margin": float(latest.get('netprofit_margin', 0)) if pd.notna(latest.get('netprofit_margin')) else None,
                "debt_to_assets": float(latest.get('debt_to_assets', 0)) if pd.notna(latest.get('debt_to_assets')) else None,
                "grossprofit_margin": float(latest.get('grossprofit_margin', 0)) if pd.notna(latest.get('grossprofit_margin')) else None,
                "current_ratio": float(latest.get('current_ratio', 0)) if pd.notna(latest.get('current_ratio')) else None,
                "quick_ratio": float(latest.get('quick_ratio', 0)) if pd.notna(latest.get('quick_ratio')) else None,
                "eps": float(latest.get('eps', 0)) if pd.notna(latest.get('eps')) else None,
                "bps": float(latest.get('bps', 0)) if pd.notna(latest.get('bps')) else None,
            }

        if income_df is not None and not income_df.empty:
            result["income"] = sanitize_data(income_df.to_dict('records'))

        if balance_df is not None and not balance_df.empty:
            result["balance"] = sanitize_data(balance_df.to_dict('records'))

        if cashflow_df is not None and not cashflow_df.empty:
            result["cashflow"] = sanitize_data(cashflow_df.to_dict('records'))

        stock_feature_cache.set(cache_key, result)
        return result

    except Exception as e:
        print(f"Error fetching financial data for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}/shareholders")
async def get_stock_shareholders(code: str, current_user: User = Depends(get_current_user)):
    """
    Get shareholder structure analysis data.

    Cache TTL: 6 hours
    """
    cache_key = f"shareholders_struct_{code}"
    cached = stock_feature_cache.get(cache_key, ttl_minutes=360)
    if cached:
        return cached

    try:
        result = {
            "code": code,
            "top10_holders": [],
            "holder_number_trend": [],
            "concentration_change": None,
            "latest_period": None
        }

        loop = asyncio.get_event_loop()

        holders_task = loop.run_in_executor(None, lambda: get_top10_holders(code, 4))
        number_task = loop.run_in_executor(None, lambda: get_shareholder_number(code, 12))

        holders_df, number_df = await asyncio.gather(holders_task, number_task)

        if holders_df is not None and not holders_df.empty:
            # Group by period
            periods = holders_df['end_date'].unique()
            grouped_holders = []
            for period in sorted(periods, reverse=True):
                period_data = holders_df[holders_df['end_date'] == period].to_dict('records')
                grouped_holders.append({
                    "period": period,
                    "holders": sanitize_data(period_data)
                })
            result["top10_holders"] = grouped_holders

            if len(periods) > 0:
                result["latest_period"] = str(sorted(periods, reverse=True)[0])

        if number_df is not None and not number_df.empty:
            result["holder_number_trend"] = sanitize_data(number_df.to_dict('records'))

            # Calculate concentration change
            if len(number_df) >= 2:
                latest = number_df.iloc[0]
                previous = number_df.iloc[1]
                if pd.notna(latest.get('holder_num')) and pd.notna(previous.get('holder_num')):
                    change = (float(latest['holder_num']) - float(previous['holder_num'])) / float(previous['holder_num']) * 100
                    result["concentration_change"] = {
                        "value": round(change, 2),
                        "trend": "decreasing" if change < 0 else "increasing",
                        "signal": "positive" if change < -5 else ("negative" if change > 5 else "neutral")
                    }

        stock_feature_cache.set(cache_key, result)
        return result

    except Exception as e:
        print(f"Error fetching shareholder data for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}/margin")
async def get_stock_margin(code: str, current_user: User = Depends(get_current_user)):
    """
    Get leverage fund monitoring data.

    Cache TTL: 30 minutes
    """
    cache_key = f"margin_{code}"
    cached = stock_feature_cache.get(cache_key, ttl_minutes=30)
    if cached:
        return cached

    try:
        result = {
            "code": code,
            "margin_data": [],
            "summary": {},
            "sentiment": None
        }

        margin_df = await asyncio.to_thread(get_margin_detail, code, 30)

        if margin_df is not None and not margin_df.empty:
            result["margin_data"] = sanitize_data(margin_df.to_dict('records'))

            # Calculate summary
            latest = margin_df.iloc[0]
            result["summary"] = {
                "rzye": float(latest.get('rzye', 0)) if pd.notna(latest.get('rzye')) else None,
                "rqye": float(latest.get('rqye', 0)) if pd.notna(latest.get('rqye')) else None,
                "rzmre": float(latest.get('rzmre', 0)) if pd.notna(latest.get('rzmre')) else None,
                "rqmcl": float(latest.get('rqmcl', 0)) if pd.notna(latest.get('rqmcl')) else None,
                "trade_date": str(latest.get('trade_date', ''))
            }

            # Calculate financing/lending ratio and sentiment
            rzye = result["summary"]["rzye"]
            rqye = result["summary"]["rqye"]
            if rzye and rqye and rqye > 0:
                ratio = rzye / rqye
                result["sentiment"] = {
                    "financing_ratio": round(ratio, 2),
                    "signal": "bullish" if ratio > 100 else ("neutral" if ratio > 10 else "bearish"),
                    "description": "融资远大于融券，市场看多" if ratio > 100 else ("融资融券相对平衡" if ratio > 10 else "融券相对较多，谨慎")
                }

            # Calculate trend (compare with 5 days ago)
            if len(margin_df) >= 5:
                latest_rzye = float(margin_df.iloc[0].get('rzye', 0)) if pd.notna(margin_df.iloc[0].get('rzye')) else 0
                old_rzye = float(margin_df.iloc[4].get('rzye', 0)) if pd.notna(margin_df.iloc[4].get('rzye')) else 0
                if old_rzye > 0:
                    change = (latest_rzye - old_rzye) / old_rzye * 100
                    result["summary"]["rzye_5d_change"] = round(change, 2)

        stock_feature_cache.set(cache_key, result)
        return result

    except Exception as e:
        print(f"Error fetching margin data for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}/events")
async def get_stock_events(code: str, current_user: User = Depends(get_current_user)):
    """
    Get event-driven calendar data.

    Cache TTL: 1 hour
    """
    cache_key = f"events_{code}"
    cached = stock_feature_cache.get(cache_key, ttl_minutes=60)
    if cached:
        return cached

    try:
        result = {
            "code": code,
            "forecasts": [],
            "share_unlock": [],
            "dividends": [],
            "upcoming_events": []
        }

        loop = asyncio.get_event_loop()

        forecast_task = loop.run_in_executor(None, lambda: get_forecast(code))
        unlock_task = loop.run_in_executor(None, lambda: get_share_float(code))
        dividend_task = loop.run_in_executor(None, lambda: get_dividend(code))

        forecast_df, unlock_df, dividend_df = await asyncio.gather(
            forecast_task, unlock_task, dividend_task
        )

        today = datetime.now().strftime('%Y%m%d')

        if forecast_df is not None and not forecast_df.empty:
            result["forecasts"] = sanitize_data(forecast_df.head(10).to_dict('records'))

            # Add to upcoming events
            for _, row in forecast_df.head(3).iterrows():
                if pd.notna(row.get('ann_date')):
                    result["upcoming_events"].append({
                        "type": "forecast",
                        "date": str(row.get('ann_date', '')),
                        "title": f"业绩预告: {row.get('type', '未知')}",
                        "detail": f"预计变动: {row.get('p_change_min', 'N/A')}% ~ {row.get('p_change_max', 'N/A')}%",
                        "sentiment": "positive" if row.get('type', '') in ['预增', '扭亏', '续盈', '略增'] else "negative"
                    })

        if unlock_df is not None and not unlock_df.empty:
            result["share_unlock"] = sanitize_data(unlock_df.head(10).to_dict('records'))

            # Add future unlocks to upcoming events
            for _, row in unlock_df.iterrows():
                float_date = str(row.get('float_date', ''))
                if float_date >= today:
                    result["upcoming_events"].append({
                        "type": "unlock",
                        "date": float_date,
                        "title": "限售解禁",
                        "detail": f"解禁数量: {row.get('float_share', 'N/A')}万股, 占比: {row.get('float_ratio', 'N/A')}%",
                        "sentiment": "warning"
                    })

        if dividend_df is not None and not dividend_df.empty:
            result["dividends"] = sanitize_data(dividend_df.head(10).to_dict('records'))

            # Add recent/upcoming dividends
            for _, row in dividend_df.head(3).iterrows():
                ex_date = str(row.get('ex_date', ''))
                if ex_date and ex_date >= (datetime.now() - timedelta(days=30)).strftime('%Y%m%d'):
                    cash_div = row.get('cash_div_tax', 0)
                    stk_div = row.get('stk_div', 0)
                    result["upcoming_events"].append({
                        "type": "dividend",
                        "date": ex_date,
                        "title": "分红除权",
                        "detail": f"每股现金: {cash_div}元" + (f", 每股送股: {stk_div}" if stk_div else ""),
                        "sentiment": "positive" if cash_div else "neutral"
                    })

        # Sort upcoming events by date
        result["upcoming_events"].sort(key=lambda x: x["date"], reverse=True)

        stock_feature_cache.set(cache_key, result)
        return result

    except Exception as e:
        print(f"Error fetching event data for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}/quant")
async def get_stock_quant(code: str, current_user: User = Depends(get_current_user)):
    """
    Get quantitative signal dashboard data.

    Cache TTL: 15 minutes
    """
    cache_key = f"quant_{code}"
    cached = stock_feature_cache.get(cache_key, ttl_minutes=15)
    if cached:
        return cached

    try:
        result = {
            "code": code,
            "factors": [],
            "chip_data": [],
            "signals": {},
            "overall_signal": None
        }

        loop = asyncio.get_event_loop()

        factors_task = loop.run_in_executor(None, lambda: get_stock_factors(code, 60))
        chip_task = loop.run_in_executor(None, lambda: get_chip_performance(code))

        factors_df, chip_df = await asyncio.gather(factors_task, chip_task)

        signals = {
            "macd": {"signal": "neutral", "value": None},
            "kdj": {"signal": "neutral", "value": None},
            "rsi": {"signal": "neutral", "value": None},
            "boll": {"signal": "neutral", "value": None}
        }

        if factors_df is not None and not factors_df.empty:
            result["factors"] = sanitize_data(factors_df.to_dict('records'))

            latest = factors_df.iloc[0]

            # MACD signal
            macd = latest.get('macd')
            macd_dif = latest.get('macd_dif')
            macd_dea = latest.get('macd_dea')
            if pd.notna(macd):
                signals["macd"]["value"] = round(float(macd), 4)
                if pd.notna(macd_dif) and pd.notna(macd_dea):
                    if float(macd_dif) > float(macd_dea):
                        signals["macd"]["signal"] = "bullish"
                    else:
                        signals["macd"]["signal"] = "bearish"

            # KDJ signal
            kdj_k = latest.get('kdj_k')
            kdj_d = latest.get('kdj_d')
            kdj_j = latest.get('kdj_j')
            if pd.notna(kdj_j):
                signals["kdj"]["value"] = round(float(kdj_j), 2)
                if float(kdj_j) > 80:
                    signals["kdj"]["signal"] = "overbought"
                elif float(kdj_j) < 20:
                    signals["kdj"]["signal"] = "oversold"
                elif pd.notna(kdj_k) and pd.notna(kdj_d) and float(kdj_k) > float(kdj_d):
                    signals["kdj"]["signal"] = "bullish"
                elif pd.notna(kdj_k) and pd.notna(kdj_d):
                    signals["kdj"]["signal"] = "bearish"

            # RSI signal
            rsi_6 = latest.get('rsi_6')
            if pd.notna(rsi_6):
                signals["rsi"]["value"] = round(float(rsi_6), 2)
                if float(rsi_6) > 70:
                    signals["rsi"]["signal"] = "overbought"
                elif float(rsi_6) < 30:
                    signals["rsi"]["signal"] = "oversold"
                elif float(rsi_6) > 50:
                    signals["rsi"]["signal"] = "bullish"
                else:
                    signals["rsi"]["signal"] = "bearish"

            # BOLL signal
            close = latest.get('close')
            boll_upper = latest.get('boll_upper')
            boll_mid = latest.get('boll_mid')
            boll_lower = latest.get('boll_lower')
            if pd.notna(close) and pd.notna(boll_upper) and pd.notna(boll_lower):
                signals["boll"]["value"] = {
                    "upper": round(float(boll_upper), 2),
                    "mid": round(float(boll_mid), 2) if pd.notna(boll_mid) else None,
                    "lower": round(float(boll_lower), 2),
                    "close": round(float(close), 2)
                }
                if float(close) >= float(boll_upper):
                    signals["boll"]["signal"] = "overbought"
                elif float(close) <= float(boll_lower):
                    signals["boll"]["signal"] = "oversold"
                elif float(close) > float(boll_mid) if pd.notna(boll_mid) else float(boll_upper + boll_lower) / 2:
                    signals["boll"]["signal"] = "bullish"
                else:
                    signals["boll"]["signal"] = "bearish"

        result["signals"] = signals

        # Calculate overall signal
        bullish_count = sum(1 for s in signals.values() if s["signal"] in ["bullish", "oversold"])
        bearish_count = sum(1 for s in signals.values() if s["signal"] in ["bearish", "overbought"])

        if bullish_count >= 3:
            result["overall_signal"] = {"direction": "bullish", "strength": "strong", "score": bullish_count}
        elif bullish_count >= 2:
            result["overall_signal"] = {"direction": "bullish", "strength": "moderate", "score": bullish_count}
        elif bearish_count >= 3:
            result["overall_signal"] = {"direction": "bearish", "strength": "strong", "score": -bearish_count}
        elif bearish_count >= 2:
            result["overall_signal"] = {"direction": "bearish", "strength": "moderate", "score": -bearish_count}
        else:
            result["overall_signal"] = {"direction": "neutral", "strength": "weak", "score": bullish_count - bearish_count}

        # Chip distribution
        if chip_df is not None and not chip_df.empty:
            result["chip_data"] = sanitize_data(chip_df.head(10).to_dict('records'))

            latest_chip = chip_df.iloc[0]
            result["chip_summary"] = {
                "winner_rate": float(latest_chip.get('winner_rate', 0)) if pd.notna(latest_chip.get('winner_rate')) else None,
                "cost_5pct": float(latest_chip.get('cost_5pct', 0)) if pd.notna(latest_chip.get('cost_5pct')) else None,
                "cost_50pct": float(latest_chip.get('cost_50pct', 0)) if pd.notna(latest_chip.get('cost_50pct')) else None,
                "cost_95pct": float(latest_chip.get('cost_95pct', 0)) if pd.notna(latest_chip.get('cost_95pct')) else None,
                "weight_avg": float(latest_chip.get('weight_avg', 0)) if pd.notna(latest_chip.get('weight_avg')) else None,
            }

        stock_feature_cache.set(cache_key, result)
        return result

    except Exception as e:
        print(f"Error fetching quant data for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}/quant/ai-interpret")
async def get_quant_ai_interpretation(code: str, current_user: User = Depends(get_current_user)):
    """
    AI Technical Signal Interpretation - Convert quantitative signals to actionable advice.

    Cache TTL: 15 minutes
    """
    cache_key = f"ai_quant_interpret:{code}"
    cached = stock_feature_cache.get(cache_key, 15)  # 15 minutes
    if cached:
        return cached

    try:
        from src.llm.client import get_llm_client
        from src.llm.stock_diagnosis_prompt import build_quant_interpretation_prompt
        import json
        import re

        # Get quant data
        quant_data = await get_stock_quant(code, current_user)

        # Get current price
        quote = get_stock_realtime_quote(code)
        current_price = None
        if quote:
            current_price = quote.get("最新价")

        # Build prompt
        prompt = build_quant_interpretation_prompt(
            stock_code=code,
            current_price=current_price,
            quant=quant_data
        )

        # Call LLM
        llm = get_llm_client()
        system_prompt = "你是一位专业的技术分析师，擅长解读各类技术指标并给出通俗易懂的操作建议。请用中文回答。"
        full_prompt = f"{system_prompt}\n\n{prompt}"
        response_text = llm.generate_content(full_prompt)

        # Parse JSON response
        interpretation = None
        try:
            interpretation = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to find JSON block
            json_match = re.search(r'\{[^{}]*"pattern"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    interpretation = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

        if not interpretation:
            # Create default if parsing failed
            interpretation = {
                "pattern": "分析中...",
                "interpretation": "AI正在分析技术指标，请稍后重试。",
                "action": "建议等待AI分析完成后再做决策。"
            }

        result = {
            "code": code,
            "interpretation": interpretation,
            "timestamp": datetime.now().isoformat()
        }

        stock_feature_cache.set(cache_key, result)
        return result

    except Exception as e:
        print(f"Error generating AI quant interpretation for {code}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
