import akshare as ak
import pandas as pd
import yfinance as yf
import os
import glob
from datetime import datetime, timedelta
from typing import Dict, Any, List
import time
import threading

# Cache Setup
_DASHBOARD_CACHE = {}
_DASHBOARD_CACHE_LOCK = threading.Lock()
_DEFAULT_CACHE_TTL = 300  # 5 minutes

class DashboardService:
    def __init__(self, report_dir: str):
        self.report_dir = report_dir

    def _get_cached_data(self, key: str):
        with _DASHBOARD_CACHE_LOCK:
            if key in _DASHBOARD_CACHE:
                data, expiry = _DASHBOARD_CACHE[key]
                if time.time() < expiry:
                    return data
                else:
                    del _DASHBOARD_CACHE[key]
        return None

    def _set_cached_data(self, key: str, data: Any, duration: int = _DEFAULT_CACHE_TTL):
        with _DASHBOARD_CACHE_LOCK:
            _DASHBOARD_CACHE[key] = (data, time.time() + duration)

    def get_market_overview(self) -> Dict[str, Any]:
        """Section 1: Market Breadth, Indices, Turnover"""
        cache_key = "market_overview"
        cached = self._get_cached_data(cache_key)
        if cached: return cached

        data = {
            "indices": [],
            "breadth": {"up": 0, "down": 0, "flat": 0, "limit_up": 0, "limit_down": 0},
            "turnover": {"total": 0, "change_pct": 0, "change_amt": 0},
            "main_flow": 0
        }

        try:
            # 1. Indices (Global Spot - Faster)
            # Replaces stock_zh_index_spot_em which fetches ALL indices (slow)
            try:
                global_df = ak.index_global_spot_em()
            except Exception as e:
                print(f"Global indices error: {e}")
                global_df = pd.DataFrame()

            targets = ["上证指数", "深证成指", "纳斯达克"]
            
            if not global_df.empty:
                for name in targets:
                    # Find by Name
                    row = global_df[global_df['名称'] == name]
                    if not row.empty:
                        r = row.iloc[0]
                        data["indices"].append({
                            "name": name,
                            "price": float(r['最新价']),
                            "change": float(r['涨跌幅'])
                        })
            
            # 2. Turnover & Breadth
            # Breadth via Legu (Fast)
            try:
                # legu_df = ak.stock_market_activity_legu()
                # if not legu_df.empty:
                #     # Convert to dict {item: value}
                #     legu_map = dict(zip(legu_df['item'], legu_df['value']))
                #     data["breadth"] = {
                #         "up": int(float(legu_map.get("上涨", 0))),
                #         "down": int(float(legu_map.get("下跌", 0))),
                #         "flat": int(float(legu_map.get("平盘", 0))),
                #         "limit_up": int(float(legu_map.get("涨停", 0))),
                #         "limit_down": int(float(legu_map.get("跌停", 0)))
                #     }
                
                df_spot = ak.stock_zh_a_spot_em()
                if df_spot is not None and not df_spot.empty:
                    up_count = len(df_spot[df_spot['涨跌幅'] > 0])
                    down_count = len(df_spot[df_spot['涨跌幅'] < 0])
                    flat_count = len(df_spot[df_spot['涨跌幅'] == 0])
                    limit_up = len(df_spot[df_spot['涨跌幅'] >= 9.8]) # 粗略统计
                    limit_down = len(df_spot[df_spot['涨跌幅'] <= -9.8])

                    data["breadth"] = {
                        "up": up_count,
                        "down": down_count,
                        "flat": flat_count,
                        "limit_up": limit_up,
                        "limit_down": limit_down
                    }
            except Exception as e:
                print(f"stock_zh_a_spot_em fetch failed: {e}")

            # Turnover via Specific Daily Indices (SH Composite + SZ Composite)
            # Much faster than fetching all spot indices
            try:
                # sh000001 = SH Composite, sz399106 = SZ Composite
                sh_df = ak.stock_zh_index_daily_em(symbol="sh000001")
                sz_df = ak.stock_zh_index_daily_em(symbol="sz399106")
                
                total_to = 0
                if not sh_df.empty:
                    total_to += float(sh_df.iloc[-1]['amount'])
                if not sz_df.empty:
                    total_to += float(sz_df.iloc[-1]['amount'])
                
                if total_to > 0:
                     # Convert to Billions (Yi)
                    data["turnover"]["total"] = round(total_to / 100000000, 2)
            except Exception as e:
                print(f"Turnover fetch failed: {e}")
                
            # 3. Main Capital Flow
            # stock_individual_fund_flow_rank gives individual flows, sum top?
            # Or market level flow: stock_market_fund_flow
            try:
                flow_df = ak.stock_market_fund_flow()
                if not flow_df.empty:
                    # Usually returns historical data. Get last row
                    last = flow_df.iloc[-1]
                    data["main_flow"] = round(float(last.get('主力净流入-净额', 0)) / 100000000, 2)
            except:
                pass
                
        except Exception as e:
            print(f"Error fetching market overview: {e}")

        self._set_cached_data(cache_key, data)
        return data

    def get_gold_macro(self) -> Dict[str, Any]:
        """Section 2: Gold & Macro (YFinance)"""
        cache_key = "gold_macro"
        cached = self._get_cached_data(cache_key)
        if cached: return cached
        
        data = {"symbol": "GC=F", "price": 0, "change_pct": 0, "dxy": 0}
        try:
            # Gold
            gold = yf.Ticker("GC=F")
            hist = gold.history(period="2d")
            if not hist.empty:
                last = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else last
                data["price"] = round(last['Close'], 2)
                data["change_pct"] = round(((last['Close'] - prev['Close']) / prev['Close']) * 100, 2)
            
            # DXY
            dxy = yf.Ticker("DX-Y.NYB")
            hist_dxy = dxy.history(period="1d")
            if not hist_dxy.empty:
                data["dxy"] = round(hist_dxy.iloc[-1]['Close'], 2)
                
        except Exception as e:
            print(f"Error fetching gold/macro: {e}")
            
        self._set_cached_data(cache_key, data)
        return data

    def get_sectors(self) -> Dict[str, List]:
        """Section 3: Sector Performance"""
        cache_key = "sectors"
        cached = self._get_cached_data(cache_key)
        if cached: return cached
        
        result = {"gainers": [], "losers": []}
        try:
            df = ak.stock_board_industry_name_em()
            if not df.empty:
                # Sort by change
                sorted_df = df.sort_values(by='涨跌幅', ascending=False)
                
                # Top 10 Gainers
                for _, row in sorted_df.head(10).iterrows():
                    result["gainers"].append({
                        "name": row['板块名称'],
                        "change": row['涨跌幅'],
                        "flow": 0 # EM name API doesn't have flow, need merge or ignore
                    })
                
                # Top 10 Losers
                for _, row in sorted_df.tail(10).iterrows():
                    result["losers"].append({
                        "name": row['板块名称'],
                        "change": row['涨跌幅'],
                        "flow": 0
                    })
        except Exception as e:
            print(f"Error fetching sectors: {e}")
            
        self._set_cached_data(cache_key, result)
        return result

    def get_abnormal_movements(self) -> List[Dict]:
        """Section 4: Abnormal Movements (Stock Level Feed)"""
        cache_key = "abnormal_feed"
        cached = self._get_cached_data(cache_key)
        if cached: return cached
        
        moves = []
        try:
            # Fetch various types of real-time signals
            # Rocket (Rapid Rise), Dive (Rapid Fall), Limit Up, Limit Down
            targets = [
                ("火箭发射", "🚀 拉升"), 
                ("高台跳水", "📉 跳水"),
                ("封涨停板", "🔴 封涨停"),
                ("封跌停板", "🟢 封跌停")
            ]
            
            for symbol, label in targets:
                try:
                    df = ak.stock_changes_em(symbol=symbol)
                    if not df.empty:
                        # Normalize columns if needed, usually they are consistent
                        for _, row in df.head(10).iterrows(): # Take top 10 of each type
                            moves.append({
                                "time": str(row.get('时间', '')),
                                "name": row.get('名称', ''),
                                "type": label,
                                "info": f"Code: {row.get('代码')}"
                            })
                except Exception as sub_e:
                    print(f"Failed to fetch {symbol}: {sub_e}")

            # Sort by time descending (HH:MM:SS)
            # Filter out empty times just in case
            moves = [m for m in moves if m['time']]
            moves.sort(key=lambda x: x['time'], reverse=True)
            
        except Exception as e:
            print(f"Error fetching abnormal movements: {e}")
            
        # Cache for 30 seconds
        result = moves[:30]
        self._set_cached_data(cache_key, result, duration=30)
        return result

    def get_top_holdings_changes(self) -> List[Dict]:
        """Section 5: Top Capital Flow Stocks"""
        cache_key = "top_flow"
        cached = self._get_cached_data(cache_key)
        if cached: return cached
        
        stocks = []
        try:
            # Main capital flow rank
            df = ak.stock_individual_fund_flow_rank(indicator="今日")
            if not df.empty:
                # Top 10 inflow
                for _, row in df.head(10).iterrows():
                    stocks.append({
                        "code": str(row.get('代码')),
                        "name": row.get('名称'),
                        "net_buy": round(float(row.get('今日主力净流入-净额', 0)) / 100000000, 2), # Billions? usually units vary
                        "change_pct": row.get('今日涨跌幅')
                    })
        except Exception as e:
            print(f"Error flow: {e}")
            
        self._set_cached_data(cache_key, stocks)
        return stocks

    def get_system_stats(self, user_report_dir: str = None) -> Dict[str, Any]:
        """Section 6: Report Generation Stats (Today) - User Specific"""
        # If no user_report_dir provided, use default (but this should be avoided for multi-tenant)
        target_dir = user_report_dir if user_report_dir else self.report_dir
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        stats = {
            "total": 0,
            "breakdown": {"pre": 0, "post": 0, "commodity": 0, "sentiment": 0},
            "latest": None
        }
        
        # Recursive search for .md files
        # Directories: reports/, reports/commodities/, reports/sentiment/
        # Pattern: YYYY-MM-DD*.md
        
        all_files = []
        
        if os.path.exists(target_dir):
            # Root reports (Pre/Post)
            root_files = glob.glob(os.path.join(target_dir, f"{today_str}*.md"))
            all_files.extend([(f, 'root') for f in root_files])
            
            # Commodity
            comm_files = glob.glob(os.path.join(target_dir, "commodities", f"{today_str}*.md"))
            all_files.extend([(f, 'commodity') for f in comm_files])
            
            # Sentiment (Format: sentiment_YYYYMMDD...)
            sent_date = datetime.now().strftime("%Y%m%d")
            sent_files = glob.glob(os.path.join(target_dir, "sentiment", f"sentiment_{sent_date}*.md"))
            all_files.extend([(f, 'sentiment') for f in sent_files])
        
        stats["total"] = len(all_files)
        
        # Sort by mtime
        if all_files:
            all_files.sort(key=lambda x: os.path.getmtime(x[0]), reverse=True)
            stats["latest"] = os.path.basename(all_files[0][0])
            
            for f, loc in all_files:
                fname = os.path.basename(f)
                if loc == 'commodity':
                    stats["breakdown"]["commodity"] += 1
                elif loc == 'sentiment':
                    stats["breakdown"]["sentiment"] += 1
                elif "_pre_" in fname:
                    stats["breakdown"]["pre"] += 1
                elif "_post_" in fname:
                    stats["breakdown"]["post"] += 1
                    
        return stats

    def get_full_dashboard(self) -> Dict[str, Any]:
        """Aggregate all GLOBAL data"""
        return {
            "market_overview": self.get_market_overview(),
            "gold_macro": self.get_gold_macro(),
            "sectors": self.get_sectors(),
            "abnormal_movements": self.get_abnormal_movements(),
            "top_flows": self.get_top_holdings_changes(),
            # System stats removed from global cache
        }
