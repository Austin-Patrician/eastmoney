
import sys
import os
import tushare as ts
from config.settings import TUSHARE_API_TOKEN
from src.data_sources import tushare_client, yfinance_client
from datetime import datetime, timedelta



def _safe_float(value, default=0.0) -> float:
    """Safely convert value to float, return default if None or invalid."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
    


def raw_tushare_scan():
    print("=== Raw TuShare Scan ===")
    
    pro = ts.pro_api(TUSHARE_API_TOKEN)
    

    print("Testing moneyflow_hsgt for specific dates...")
    # Try a few dates in 2024
    dates = [ '20260122']



    trade_date = tushare_client.get_latest_trade_date(max_days_back=10)
    if not trade_date:
            print("Could not determine latest trade date")
            return {}

        # Get data for a range ending at the latest trade date
    # Query both Shanghai (1) and Shenzhen (3) Stock Connect
    df_list = []

    print(f"Fetching Stock Connect data for trade date: {trade_date}")
        # 1. Shanghai Stock Connect (沪股通)
    try:
        df_sh = tushare_client.tushare_call_with_retry(
                'hsgt_top10',
                trade_date=trade_date,
                market_type='1'
        )
        if df_sh is not None and not df_sh.empty:
                print("Fetched Shanghai Connect flow",df_sh)
                df_list.append(df_sh)
    except Exception as e:
            print(f"Failed to fetch Shanghai Connect flow: {e}")

    if not df_list:
            return {}
    

    

        # Get latest day
    latest = df.sort_values('trade_date', ascending=False).iloc[0]

        # Safely extract values with None handling
    hgt_buy = _safe_float(latest.get('hgt_buy'))
    hgt_sell = _safe_float(latest.get('hgt_sell'))
    sgt_buy = _safe_float(latest.get('sgt_buy'))
    sgt_sell = _safe_float(latest.get('sgt_sell'))
    north_money = _safe_float(latest.get('north_money'))

    result = {
            '数据日期': str(latest['trade_date']),
            '沪股通': {
                '成交净买额': f"{(hgt_buy - hgt_sell):.2f}亿"
            },
            '深股通': {
                '成交净买额': f"{(sgt_buy - sgt_sell):.2f}亿"
            },
            '最新净流入': f"{north_money:.2f}亿"
    }

        # Calculate 5-day cumulative
    if len(df) >= 5:
            recent_5 = df.sort_values('trade_date', ascending=False).head(5)
            # Handle None values in sum
            total_5d = recent_5['north_money'].fillna(0).sum()
            result['5日累计净流入'] = f"{_safe_float(total_5d):.2f}亿"

    print('result',result)
    for d in dates:
        print(f"\nChecking {d}...")
        try:
            # exchange='FX' might be needed
            df = pro.moneyflow_hsgt(trade_date='20260123')
            if not df.empty:
                print(df.head())
                print("Codes found:", df['ts_code'].unique())
                return
            else:
                print("Empty (FX)")
                
            # Try without exchange
            df = pro.fx_daily(trade_date=d)
            if not df.empty:
                print(df.head())
                print("Codes found:", df['ts_code'].unique())
                return
            else:
                print("Empty (Default)")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    raw_tushare_scan()
