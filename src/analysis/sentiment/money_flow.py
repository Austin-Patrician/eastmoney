import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

class MoneyFlowAnalyst:
    def get_money_flow(self):
        """
        获取全方位的资金流向数据
        """
        data = {
            "north_money": 0.0, # 北向资金
            "institution_buy": [], # 机构龙虎榜
            "sector_inflow": [], # 行业净流入Top
            "sector_outflow": [], # 行业净流出Top
            "etf_active": [], # 活跃ETF
            "market_breadth": {}, # 涨跌家数
            "north_date": None,
            "institution_date": None,
        }
        
        # 1. 市场广度 (Market Breadth)
        try:
            # 使用实时行情概览
            df_spot = ak.stock_zh_a_spot_em()
            if df_spot is not None and not df_spot.empty:
                up_count = len(df_spot[df_spot['涨跌幅'] > 0])
                down_count = len(df_spot[df_spot['涨跌幅'] < 0])
                flat_count = len(df_spot[df_spot['涨跌幅'] == 0])
                limit_up = len(df_spot[df_spot['涨跌幅'] >= 9.8]) # 粗略统计
                limit_down = len(df_spot[df_spot['涨跌幅'] <= -9.8])
                
                data["market_breadth"] = {
                    "up": up_count,
                    "down": down_count,
                    "flat": flat_count,
                    "limit_up": limit_up,
                    "limit_down": limit_down,
                    "ratio": round(up_count / (up_count + down_count + 1) * 100, 1)
                }
        except Exception as e:
            print(f"Market breadth error: {e}")

        # 2. 行业板块资金流向 (Sector Flow)
        try:
            # 获取今日行业资金流排名
            df_flow = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
            if df_flow is not None and not df_flow.empty:
                # 东方财富接口返回列名可能包含：名称, 今日涨跌幅, 今日主力净流入-净额, ...
                
                # 动态查找列名
                flow_col = '今日主力净流入' # Default
                pct_col = '今日涨跌幅' # Default
                name_col = '名称'

                for col in df_flow.columns:
                    if "主力净流入" in col and "净额" in col:
                        flow_col = col
                    elif "涨跌幅" in col and "今日" in col:
                        pct_col = col
                
                if flow_col in df_flow.columns:
                    # 转换净流入为数值 (单位通常是元，转换为亿元)
                    def parse_flow(val):
                        try:
                            if pd.isna(val): return 0.0
                            if isinstance(val, (int, float)):
                                return float(val) / 1e8 # 原始单位是元
                            if isinstance(val, str):
                                val = val.replace('亿', '').replace('万', '')
                                return float(val)
                        except:
                            return 0.0
                        return 0.0

                    # Inflow Top 5
                    # Ensure numeric
                    if df_flow[flow_col].dtype == object:
                         # Try to clean if it's string (though recent akshare returns float)
                         pass

                    # Sort just in case API didn't sort by flow
                    df_flow[flow_col] = pd.to_numeric(df_flow[flow_col], errors='coerce').fillna(0)
                    
                    df_sorted = df_flow.sort_values(by=flow_col, ascending=False)
                    
                    # Top 5 Inflow
                    top_in = df_sorted.head(5)
                    inflow_list = []
                    for _, row in top_in.iterrows():
                        inflow_list.append({
                            "name": row.get(name_col),
                            "pct": row.get(pct_col),
                            "net_in": parse_flow(row.get(flow_col))
                        })
                    data["sector_inflow"] = inflow_list

                    # Top 5 Outflow (Bottom 5 of sorted)
                    top_out = df_sorted.tail(5).sort_values(by=flow_col, ascending=True)
                    outflow_list = []
                    for _, row in top_out.iterrows():
                        outflow_list.append({
                            "name": row.get(name_col),
                            "pct": row.get(pct_col),
                            "net_out": parse_flow(row.get(flow_col))
                        })
                    data["sector_outflow"] = outflow_list
                    
        except Exception as e:
            print(f"Sector flow error: {e}")

        # 3. 热门ETF成交 (ETF Activity)
        try:
            # 获取ETF实时行情，按成交额排序
            df_etf = ak.fund_etf_spot_em()
            if df_etf is not None and not df_etf.empty:
                # 按成交额降序
                df_etf = df_etf.sort_values(by='成交额', ascending=False).head(5)
                etf_list = []
                for _, row in df_etf.iterrows():
                    etf_list.append({
                        "code": row.get('代码'),
                        "name": row.get('名称'),
                        "pct": row.get('涨跌幅'),
                        "turnover": row.get('成交额') # 元
                    })
                data["etf_active"] = etf_list
        except Exception as e:
            print(f"ETF data error: {e}")

        # 4. 北向资金 (Time-based Strategy)
        try:
            current_hour = datetime.now().hour
            use_hist = current_hour >= 15 # After 15:00 use Hist, else Min
            
            df_north_min = None
            hist_df = None
            
            # Helper to parse Hist
            def parse_hist(df):
                if df is None or df.empty: return None, None
                if "日期" in df.columns:
                    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
                    flow_col = next((c for c in ["当日成交净买额", "当日资金流入", "资金流入", "当日净流入"] if c in df.columns), None)
                    if flow_col:
                        df[flow_col] = pd.to_numeric(df[flow_col], errors="coerce")
                        last = df.sort_values("日期").iloc[-1]
                        val = float(last.get(flow_col))
                        return round(val / 1e8 if abs(val) > 10000 else val, 2), last.get("日期").strftime("%Y-%m-%d")
                return None, None

            # Helper to parse Min
            def parse_min(df):
                if df is None or df.empty: return None, None
                north_col = next((c for c in df.columns if "北向" in c), None)
                last_val = 0.0
                if north_col:
                    last_val = pd.to_numeric(df.iloc[-1][north_col], errors='coerce')
                else:
                    sh_col = next((c for c in df.columns if "沪" in c), None)
                    sz_col = next((c for c in df.columns if "深" in c), None)
                    if sh_col and sz_col:
                        v1 = pd.to_numeric(df.iloc[-1][sh_col], errors='coerce')
                        v2 = pd.to_numeric(df.iloc[-1][sz_col], errors='coerce')
                        last_val = (v1 if not pd.isna(v1) else 0) + (v2 if not pd.isna(v2) else 0)
                
                # Assume 0.0 might be invalid if mid-day, but valid if really 0.
                # Unit check
                val = round(last_val / 1e8 if abs(last_val) > 10000 else last_val, 2)
                
                date_col = next((c for c in df.columns if "日期" in c or "date" in c.lower()), None)
                d_str = str(df.iloc[-1][date_col]) if date_col else datetime.now().strftime("%Y-%m-%d")
                return val, d_str

            # Strategy Execution
            if not use_hist:
                # < 15:00: Try Min First
                try:
                    df_north_min = ak.stock_hsgt_fund_min_em(symbol="北向资金")
                except: pass
                
                val, d_str = parse_min(df_north_min)
                if val is not None:
                    data["north_money"] = val
                    data["north_date"] = d_str
                else:
                    # Fallback to Hist
                    try:
                        hist_df = ak.stock_hsgt_hist_em(symbol="北向资金")
                    except: pass
                    val, d_str = parse_hist(hist_df)
                    if val is not None:
                        data["north_money"] = val
                        data["north_date"] = d_str
            else:
                # >= 15:00: Try Hist First
                try:
                    hist_df = ak.stock_hsgt_hist_em(symbol="北向资金")
                except: pass
                
                val, d_str = parse_hist(hist_df)
                if val is not None:
                    data["north_money"] = val
                    data["north_date"] = d_str
                else:
                    # Fallback to Min
                    try:
                        df_north_min = ak.stock_hsgt_fund_min_em(symbol="北向资金")
                    except: pass
                    val, d_str = parse_min(df_north_min)
                    if val is not None:
                        data["north_money"] = val
                        data["north_date"] = d_str

        except Exception as e:
            print(f"North money error: {e}")

        # 5. 机构龙虎榜 (现有逻辑，保留)
        try:
            df_jg = ak.stock_lhb_jgmmtj_em()
            if df_jg is not None and not df_jg.empty:
                date_col = "上榜日期" if "上榜日期" in df_jg.columns else None
                if date_col:
                    df_jg[date_col] = pd.to_datetime(df_jg[date_col], errors="coerce")
                    latest_date = df_jg[date_col].max()
                    data["institution_date"] = latest_date.strftime("%Y-%m-%d")
                    df_jg = df_jg[df_jg[date_col] == latest_date]

                net_buy_col = "净买入额" # Standardize
                for col in df_jg.columns:
                    if "净" in col and "额" in col:
                        net_buy_col = col
                        break
                
                name_col = "名称" if "名称" in df_jg.columns else "股票名称"
                
                if net_buy_col and name_col in df_jg.columns:
                     # Sort by abs value of net buy to see big moves (buy or sell)
                     # Or just top buys
                     df_jg[net_buy_col] = pd.to_numeric(df_jg[net_buy_col], errors="coerce")
                     top_buy = df_jg.sort_values(by=net_buy_col, ascending=False).head(5)
                     
                     res = []
                     for _, row in top_buy.iterrows():
                         val = row.get(net_buy_col)
                         res.append({
                             "name": row.get(name_col),
                             "net_buy": round(val / 1e4, 0) if val else 0 # Show in Wan
                         })
                     data["institution_buy"] = res
        except Exception as e:
            print(f"Institution error: {e}")
            
        return data

if __name__ == "__main__":
    analyst = MoneyFlowAnalyst()
    print(analyst.get_money_flow())