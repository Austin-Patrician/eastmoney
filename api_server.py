import os
import sys
import json
import asyncio
import glob
import threading
import math
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Body, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports from project
from src.analysis.pre_market import PreMarketAnalyst
from src.analysis.post_market import PostMarketAnalyst
from src.analysis.sentiment.dashboard import SentimentDashboard
from src.analysis.commodities.gold_silver import GoldSilverAnalyst
from src.analysis.dashboard import DashboardService
from src.data_sources.akshare_api import search_funds
from src.storage.db import init_db, get_active_funds, get_all_funds, upsert_fund, delete_fund, get_fund_by_code, get_all_stocks, upsert_stock, delete_stock, get_stock_by_code
from src.scheduler.manager import scheduler_manager
from src.report_gen import save_report, save_stock_report
# Updated import
from src.data_sources.akshare_api import get_all_fund_list, get_stock_realtime_quote, get_all_stock_spot_map, get_stock_history
import akshare as ak
import pandas as pd
from src.auth import Token, UserCreate, User, create_access_token, get_password_hash, verify_password, get_current_user, create_user, get_user_by_username
from fastapi.security import OAuth2PasswordRequestForm


def sanitize_for_json(obj):
    """
    Recursively sanitize an object to ensure it's JSON-serializable.
    Converts nan/inf floats to None.
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (int, str, bool, type(None))):
        return obj
    else:
        # Try to convert to string for unknown types
        try:
            return str(obj)
        except:
            return None


# --- Startup/Shutdown ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    print("Starting Scheduler...")
    scheduler_manager.start()
    yield
    # Shutdown logic if needed

app = FastAPI(title="EastMoney Report API", lifespan=lifespan)

# Configure CORS
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/market/funds")
async def search_market_funds(q: str):
    if not q:
        return []
    try:
        results = search_funds(q)
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return []
    


# --- Auth Endpoints ---
@app.post("/api/auth/register", response_model=Token)
async def register(user: UserCreate):
    existing = get_user_by_username(user.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pwd = get_password_hash(user.password)
    try:
        user_id = create_user({
            "username": user.username,
            "email": user.email,
            "hashed_password": hashed_pwd,
            "provider": "local"
        })
        
        # Auto login
        access_token_expires = datetime.utcnow() + timedelta(minutes=60*24*7)
        access_token = create_access_token(
            data={"sub": user.username, "id": user_id},
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user_dict = get_user_by_username(form_data.username)
    if not user_dict or not verify_password(form_data.password, user_dict['hashed_password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user_dict['username'], "id": user_dict['id']}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(BASE_DIR, "reports")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
ENV_FILE = os.path.join(BASE_DIR, ".env")
MARKET_FUNDS_CACHE = os.path.join(CONFIG_DIR, "market_funds_cache.json")
MARKET_STOCKS_CACHE = os.path.join(CONFIG_DIR, "market_stocks_cache.json")

def get_user_report_dir(user_id: int) -> str:
    user_dir = os.path.join(REPORT_DIR, str(user_id))
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return user_dir

# --- Models ---

class ReportSummary(BaseModel):
    filename: str
    date: str
    mode: str # 'pre' or 'post'
    fund_code: Optional[str] = None
    fund_name: Optional[str] = None
    is_summary: bool = True # True if it's a run_all report or Summary

class FundItem(BaseModel):
    code: str
    name: str
    style: Optional[str] = "Unknown"
    focus: Optional[List[str]] = []
    pre_market_time: Optional[str] = None
    post_market_time: Optional[str] = None
    is_active: bool = True

class StockItem(BaseModel):
    code: str
    name: str
    market: Optional[str] = ""
    sector: Optional[str] = ""
    pre_market_time: Optional[str] = "08:30"
    post_market_time: Optional[str] = "15:30"
    is_active: bool = True
    price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None


class StockAnalyzeRequest(BaseModel):
    mode: str = "pre"  # 'pre' or 'post'

class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None

class GenerateRequest(BaseModel):
    fund_code: Optional[str] = None

class CommodityAnalyzeRequest(BaseModel):
    asset: str # "gold" or "silver"

# --- Helpers ---
def sanitize_data(data):
    """Recursively replace NaN/Inf and non-JSON types (like pd.NA) for JSON compliance."""
    import math
    import pandas as pd
    import numpy as np
    
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(v) for v in data]
    elif pd.isna(data): # Handles None, np.nan, pd.NA, pd.NaT
        return None
    elif isinstance(data, (np.float64, np.float32, float)):
        if math.isnan(data) or math.isinf(data):
            return None
        return float(data)
    elif isinstance(data, (np.int64, np.int32, int)):
        return int(data)
    elif isinstance(data, (datetime, pd.Timestamp)):
        return data.strftime('%Y-%m-%d %H:%M:%S')
    return data

def load_env_file():
    env_vars = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

def save_env_file(updates: Dict[str, str]):
    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    
    key_map = {}
    for i, line in enumerate(lines):
        if line.strip() and not line.strip().startswith("#") and "=" in line:
            k = line.split("=", 1)[0].strip()
            key_map[k] = i
    
    for key, value in updates.items():
        if value is None: continue 
        
        new_line = f"{key}={value}\n"
        if key in key_map:
            lines[key_map[key]] = new_line
        else:
            lines.append(new_line)
            
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)

# --- Endpoints ---

from src.llm.client import get_llm_client

@app.post("/api/system/test-llm")
async def test_llm_connection(current_user: User = Depends(get_current_user)):
    try:
        client = get_llm_client()
        # Use asyncio.to_thread for network call
        response = await asyncio.to_thread(client.generate_content, "Ping. Reply with 'Pong'.")
        
        if "Error:" in response:
             return {"status": "error", "message": response}
             
        return {"status": "success", "message": "LLM Connection Verified", "reply": response}
    except Exception as e:
        return {"status": "error", "message": str(e)}

from src.data_sources.web_search import WebSearch

@app.post("/api/system/test-search")
async def test_search_connection(current_user: User = Depends(get_current_user)):
    try:
        searcher = WebSearch()
        # Use asyncio.to_thread for network call
        results = await asyncio.to_thread(searcher.search_news, "Apple stock price", max_results=3)
        
        if not results:
             return {"status": "warning", "message": "Search returned no results (Check API Key limit or network)"}
             
        titles = [r.get("title") for r in results]
        return {"status": "success", "message": "Search Connection Verified", "results": titles}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/dashboard/overview")
async def get_dashboard_overview():
    try:
        service = DashboardService(REPORT_DIR)
        return await asyncio.to_thread(service.get_full_dashboard)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    try:
        user_report_dir = get_user_report_dir(current_user.id)
        service = DashboardService(REPORT_DIR)
        return service.get_system_stats(user_report_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/commodities/analyze")
async def analyze_commodity(request: CommodityAnalyzeRequest, current_user: User = Depends(get_current_user)):
    try:
        analyst = GoldSilverAnalyst()
        report = await asyncio.to_thread(analyst.analyze, request.asset, current_user.id)
        return {"status": "success", "message": f"{request.asset} analysis complete"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reports", response_model=List[ReportSummary])
async def list_reports(current_user: User = Depends(get_current_user)):
    user_report_dir = get_user_report_dir(current_user.id)
    if not os.path.exists(user_report_dir):
        return []
    
    fund_map = {}
    try:
        funds = get_all_funds(user_id=current_user.id)
        for f in funds:
            fund_map[f['code']] = f['name']
    except:
        pass

    reports = []
    files = glob.glob(os.path.join(user_report_dir, "*.md"))
    files.sort(key=os.path.getmtime, reverse=True)
    
    for f in files:
        filename = os.path.basename(f)
        try:
            name_no_ext = os.path.splitext(filename)[0]
            parts = name_no_ext.split("_")
            
            if len(parts) < 2: continue
            
            date_str = parts[0]
            mode = parts[1]
            
            if "SUMMARY" in name_no_ext or (len(parts) > 2 and parts[2] == "report"):
                 reports.append(ReportSummary(
                    filename=filename, 
                    date=date_str, 
                    mode=mode,
                    is_summary=True,
                    fund_name="Market Overview"
                ))
            elif len(parts) >= 3:
                 code = parts[2]
                 extracted_name = "_".join(parts[3:]) if len(parts) > 3 else ""
                 final_name = extracted_name if extracted_name else fund_map.get(code, code)
                 
                 reports.append(ReportSummary(
                    filename=filename, 
                    date=date_str, 
                    mode=mode, 
                    fund_code=code,
                    fund_name=final_name,
                    is_summary=False
                ))
        except Exception as e:
            print(f"Error parsing filename {filename}: {e}")
            continue
            
    return reports

@app.delete("/api/reports/{filename}")
async def delete_report(filename: str, current_user: User = Depends(get_current_user)):
    try:
        if not filename.endswith(".md") or ".." in filename or "/" in filename or "\\" in filename:
             raise HTTPException(status_code=400, detail="Invalid filename")
        
        user_report_dir = get_user_report_dir(current_user.id)
        file_path = os.path.join(user_report_dir, filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            return {"status": "success", "message": f"Deleted {filename}"}
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        print(f"Error deleting report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reports/{filename}")
async def get_report(filename: str, current_user: User = Depends(get_current_user)):
    user_report_dir = get_user_report_dir(current_user.id)
    
    filepath = os.path.join(user_report_dir, filename)
    if not os.path.exists(filepath):
        filepath = os.path.join(user_report_dir, "sentiment", filename)
    
    if not os.path.exists(filepath):
        filepath = os.path.join(user_report_dir, "commodities", filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Report not found")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    return {"content": content}

@app.get("/api/commodities/reports", response_model=List[ReportSummary])
async def list_commodity_reports(current_user: User = Depends(get_current_user)):
    user_report_dir = get_user_report_dir(current_user.id)
    commodities_dir = os.path.join(user_report_dir, "commodities")
    
    if not os.path.exists(commodities_dir):
        return []

    reports = []
    files = glob.glob(os.path.join(commodities_dir, "*.md"))
    files.sort(key=os.path.getmtime, reverse=True)
    
    for f in files:
        filename = os.path.basename(f)
        try:
            name_no_ext = os.path.splitext(filename)[0]
            parts = name_no_ext.split("_")
            
            if len(parts) >= 5 and parts[2] == 'commodities':
                date_str = parts[0]
                time_str = parts[1]
                code = parts[3]
                name = "_".join(parts[4:])
                formatted_date = f"{date_str} {time_str[:2]}:{time_str[2:4]}:{time_str[4:]}"
                
                reports.append(ReportSummary(
                    filename=filename,
                    date=formatted_date,
                    mode="commodities",
                    fund_code=code,
                    fund_name=name,
                    is_summary=False
                ))
            elif len(parts) >= 4 and parts[1] == 'commodities':
                date_str = parts[0]
                code = parts[2]
                name = "_".join(parts[3:])
                
                reports.append(ReportSummary(
                    filename=filename,
                    date=date_str,
                    mode="commodities",
                    fund_code=code,
                    fund_name=name,
                    is_summary=False
                ))
        except Exception as e:
            print(f"Error parsing commodity report {filename}: {e}")
            continue
            
    return reports

@app.delete("/api/commodities/reports/{filename}")
async def delete_commodity_report(filename: str, current_user: User = Depends(get_current_user)):
    try:
        if not filename.endswith(".md") or ".." in filename or "/" in filename or "\\" in filename:
             raise HTTPException(status_code=400, detail="Invalid filename")
             
        user_report_dir = get_user_report_dir(current_user.id)
        commodities_dir = os.path.join(user_report_dir, "commodities")
        file_path = os.path.join(commodities_dir, filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            return {"status": "success", "message": f"Deleted {filename}"}
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        print(f"Error deleting commodity report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market-funds")
async def search_market_funds(query: str = ""):
    funds = []
    
    if os.path.exists(MARKET_FUNDS_CACHE):
        try:
            mtime = os.path.getmtime(MARKET_FUNDS_CACHE)
            if (datetime.now().timestamp() - mtime) < 86400:
                with open(MARKET_FUNDS_CACHE, 'r', encoding='utf-8') as f:
                    funds = json.load(f)
        except Exception as e:
            print(f"Cache read error: {e}")
    
    if not funds:
        print("Fetching fresh fund list from AkShare...")
        funds = get_all_fund_list()
        if funds:
            try:
                if not os.path.exists(CONFIG_DIR):
                    os.makedirs(CONFIG_DIR)
                with open(MARKET_FUNDS_CACHE, 'w', encoding='utf-8') as f:
                    json.dump(funds, f, ensure_ascii=False)
            except Exception as e:
                print(f"Cache write error: {e}")
            
    if not query:
        return funds[:20]
        
    query = query.lower()
    results = []
    for f in funds:
        f_code = str(f.get('code', ''))
        f_name = str(f.get('name', ''))
        f_pinyin = str(f.get('pinyin', ''))
        
        if (f_code.startswith(query) or 
            query in f_name.lower() or 
            query in f_pinyin.lower()):
            results.append(f)
            
            if len(results) >= 50:
                break
                
    return results

@app.post("/api/generate/{mode}")
async def generate_report_endpoint(mode: str, request: GenerateRequest = None, current_user: User = Depends(get_current_user)):
    if mode not in ["pre", "post"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'pre' or 'post'.")
    
    fund_code = request.fund_code if request else None

    try:
        print(f"Generating {mode}-market report for User {current_user.id}... (Fund: {fund_code if fund_code else 'ALL'})")
        
        if fund_code:
            # Run analysis in a thread to avoid blocking the event loop
            # Note: This will still block the HTTP response until completion.
            # For true async (fire-and-forget), use BackgroundTasks.
            # But here the user likely wants to wait for completion? 
            # The current implementation returns a message *after* completion (sync).
            # So we use await asyncio.to_thread to keep server responsive for others.
            await asyncio.to_thread(scheduler_manager.run_analysis_task, fund_code, mode, user_id=current_user.id)
            return {"status": "success", "message": f"Task triggered for {fund_code}"}
        else:
            funds = get_active_funds(user_id=current_user.id)
            results = []
            for fund in funds:
                try:
                    await asyncio.to_thread(scheduler_manager.run_analysis_task, fund['code'], mode, user_id=current_user.id)
                    results.append(fund['code'])
                except:
                    pass
            return {"status": "success", "message": f"Triggered tasks for {len(results)} funds"}
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# --- Cache ---
_INDICES_CACHE = {
    "data": [],
    "expiry": 0
}

@app.get("/api/market/indices")
def get_market_indices():
    import time
    from datetime import datetime
    global _INDICES_CACHE
    
    now_ts = time.time()
    now_dt = datetime.now()
    current_hm = now_dt.hour * 100 + now_dt.minute
    
    # Active Hours: 08:00 - 15:00 OR 21:30 - 05:00
    # Inactive Hours: 15:00 - 21:30 AND 05:00 - 08:00
    
    is_active_session_1 = 800 <= current_hm < 1500
    is_active_session_2 = (2130 <= current_hm) or (current_hm < 500)
    is_active = is_active_session_1 or is_active_session_2

    # If inactive and we have data, use it indefinitely
    if not is_active and _INDICES_CACHE["data"]:
        return _INDICES_CACHE["data"]
    
    # Otherwise (Active OR Empty Cache), check standard expiry
    if _INDICES_CACHE["data"] and now_ts < _INDICES_CACHE["expiry"]:
        return _INDICES_CACHE["data"]

    try:
        import akshare as ak
        indices_df = ak.index_global_spot_em()
        
        target_names = [
            "上证指数", "深证成指", "创业板指",
            "恒生指数", "日经225", "纳斯达克", "标普500"
        ]
        
        # Optimize: Filter dataframe first
        if not indices_df.empty:
            filtered_df = indices_df[indices_df['名称'].isin(target_names)]
            
            # Convert to list of dicts directly
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
            _INDICES_CACHE["data"] = data
            # Cache for 60 seconds during active time
            _INDICES_CACHE["expiry"] = now_ts + 60
            
        return data
    except Exception as e:
        print(f"Error fetching indices via index_global_spot_em: {e}")
        if _INDICES_CACHE["data"]:
            return _INDICES_CACHE["data"]
        return []

@app.get("/api/funds")
async def get_funds_endpoint(current_user: User = Depends(get_current_user)):
    try:
        funds = get_all_funds(user_id=current_user.id)
        result = []
        for f in funds:
            item = dict(f)
            if isinstance(item.get('focus'), str):
                try:
                    item['focus'] = json.loads(item['focus'])
                except:
                    item['focus'] = []
            
            result.append(FundItem(
                code=item['code'],
                name=item['name'],
                style=item.get('style'),
                focus=item['focus'],
                pre_market_time=item.get('pre_market_time'),
                post_market_time=item.get('post_market_time'),
                is_active=bool(item.get('is_active', True))
            ))
        return result
    except Exception as e:
        print(f"Error reading funds: {e}")
        return []

@app.post("/api/funds")
async def save_funds(funds: List[FundItem], current_user: User = Depends(get_current_user)):
    try:
        for fund in funds:
            fund_dict = fund.model_dump()
            upsert_fund(fund_dict, user_id=current_user.id)
        return {"status": "success"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/funds/{code}")
async def upsert_fund_endpoint(code: str, fund: FundItem, current_user: User = Depends(get_current_user)):
    try:
        fund_dict = fund.model_dump()
        upsert_fund(fund_dict, user_id=current_user.id)
        scheduler_manager.add_fund_jobs(fund_dict)
        return {"status": "success"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/funds/{code}")
async def delete_fund_endpoint(code: str, current_user: User = Depends(get_current_user)):
    try:
        delete_fund(code, user_id=current_user.id)
        scheduler_manager.remove_fund_jobs(code)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
async def get_settings():
    env = load_env_file()
    def mask(key):
        val = env.get(key, "")
        if len(val) > 8:
            return val[:4] + "..." + val[-4:]
        return val
    
    return {
        "llm_provider": env.get("LLM_PROVIDER", "gemini"),
        "gemini_api_key_masked": mask("GEMINI_API_KEY"),
        "openai_api_key_masked": mask("OPENAI_API_KEY"),
        "tavily_api_key_masked": mask("TAVILY_API_KEY")
    }

@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    updates = {}
    if settings.llm_provider:
        updates["LLM_PROVIDER"] = settings.llm_provider
    if settings.gemini_api_key:
        updates["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.openai_api_key:
        updates["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.tavily_api_key:
        updates["TAVILY_API_KEY"] = settings.tavily_api_key
        
    save_env_file(updates)
    return {"status": "success"}

@app.post("/api/sentiment/analyze")
async def analyze_sentiment(current_user: User = Depends(get_current_user)):
    try:
        dashboard = SentimentDashboard()
        report = await asyncio.to_thread(dashboard.run_analysis)
        
        user_report_dir = get_user_report_dir(current_user.id)
        sentiment_dir = os.path.join(user_report_dir, "sentiment")
        if not os.path.exists(sentiment_dir):
            os.makedirs(sentiment_dir)
            
        filename = f"sentiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(sentiment_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
            
        return {"report": report, "filename": filename}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sentiment/reports")
async def list_sentiment_reports(current_user: User = Depends(get_current_user)):
    user_report_dir = get_user_report_dir(current_user.id)
    sentiment_dir = os.path.join(user_report_dir, "sentiment")
    
    if not os.path.exists(sentiment_dir):
        return []
    
    reports = []
    files = glob.glob(os.path.join(sentiment_dir, "sentiment_*.md"))
    files.sort(key=os.path.getmtime, reverse=True)
    
    for f in files:
        filename = os.path.basename(f)
        try:
            parts = filename.replace(".md", "").split("_")
            if len(parts) >= 3:
                date_str = parts[1]
                time_str = parts[2]
                formatted_time = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {time_str[:2]}:{time_str[2:4]}"
            elif len(parts) == 2:
                date_str = parts[1]
                formatted_time = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            else:
                continue

            reports.append({
                "filename": filename,
                "date": formatted_time
            })
        except Exception as e:
            print(f"Skipping {filename}: {e}")
            continue
            
    return reports

@app.delete("/api/sentiment/reports/{filename}")
async def delete_sentiment_report(filename: str, current_user: User = Depends(get_current_user)):
    try:
        if not filename.endswith(".md") or ".." in filename or "/" in filename or "\\" in filename:
             raise HTTPException(status_code=400, detail="Invalid filename")
             
        user_report_dir = get_user_report_dir(current_user.id)
        sentiment_dir = os.path.join(user_report_dir, "sentiment")
        file_path = os.path.join(sentiment_dir, filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            return {"status": "success", "message": f"Deleted {filename}"}
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        print(f"Error deleting report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/funds/{code}/details")
async def get_fund_market_details(code: str):
    """获取基金在市场上的详细信息（经理、规模、业绩、持仓等）"""
    try:
        import akshare as ak
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

@app.get("/api/market/funds/{code}/nav")
async def get_fund_nav_history(code: str):
    """获取基金历史净值（用于绘图）"""
    try:
        import akshare as ak
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

# --- Stock API ---

def _enrich_stock_info(stock_dict):
    """Auto-fill sector info if missing"""
    if not stock_dict.get('sector'):
        try:
            # ak.stock_individual_info_em(symbol=code)
            df = ak.stock_individual_info_em(symbol=stock_dict['code'])
            if not df.empty:
                # item, value
                info_map = dict(zip(df['item'], df['value']))
                stock_dict['sector'] = info_map.get('行业', '')
        except Exception as e:
            print(f"Auto-fetch sector failed: {e}")
    return stock_dict

from concurrent.futures import ThreadPoolExecutor

# ... (Previous code)

@app.get("/api/stocks", response_model=List[StockItem])
async def get_stocks_endpoint(current_user: User = Depends(get_current_user)):
    try:
        stocks = get_all_stocks(user_id=current_user.id)
        
        def fetch_single_quote(stock):
            item = dict(stock)
            try:
                # Use stock_bid_ask_em for fast single stock query
                # This returns a DF with [item, value] columns
                df = ak.stock_bid_ask_em(symbol=stock['code'])
                if not df.empty:
                    info = dict(zip(df['item'], df['value']))
                    
                    # Try keys from stock_bid_ask_em (Commonly: 最新, 涨幅, 总手)
                    price = info.get('最新') or info.get('最新价')
                    change = info.get('涨幅') or info.get('涨跌幅')
                    vol = info.get('总手') or info.get('成交量')
                    
                    # Safe conversion
                    if price is not None and str(price) != '': 
                        item['price'] = float(price)
                    if change is not None and str(change) != '': 
                        item['change_pct'] = float(change)
                    if vol is not None and str(vol) != '': 
                        v = float(vol)
                        # If came from '总手' (Hands), convert to shares for consistency
                        if info.get('总手') is not None:
                            v = v * 100
                        item['volume'] = v
            except Exception:
                # Silently fail for individual stock fetch errors to not break the whole list
                pass
            return StockItem(**item)

        # Execute in parallel
        # Note: akshare calls are blocking/sync, so ThreadPool is appropriate
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=10) as executor:
             results = await loop.run_in_executor(None, lambda: list(executor.map(fetch_single_quote, stocks)))
             
        return results
    except Exception as e:
        print(f"Error reading stocks: {e}")
        return []

@app.post("/api/stocks")
async def save_stocks(stocks: List[StockItem], current_user: User = Depends(get_current_user)):
    try:
        for stock in stocks:
            data = stock.model_dump()
            # Run enrichment in thread to avoid blocking
            data = await asyncio.to_thread(_enrich_stock_info, data)
            upsert_stock(data, user_id=current_user.id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/stocks/{code}")
async def upsert_stock_endpoint(code: str, stock: StockItem, current_user: User = Depends(get_current_user)):
    try:
        data = stock.model_dump()
        # Enrich only if sector is empty to allow manual override
        if not data.get('sector'):
             data = await asyncio.to_thread(_enrich_stock_info, data)
        upsert_stock(data, user_id=current_user.id)
        # Update scheduler jobs
        data['user_id'] = current_user.id
        scheduler_manager.add_stock_jobs(data)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/stocks/{code}")
async def delete_stock_endpoint(code: str, current_user: User = Depends(get_current_user)):
    try:
        delete_stock(code, user_id=current_user.id)
        scheduler_manager.remove_stock_jobs(code)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Stock Analysis Endpoints ---

@app.post("/api/stocks/{code}/analyze")
async def analyze_stock_endpoint(code: str, request: StockAnalyzeRequest, current_user: User = Depends(get_current_user)):
    """Trigger stock analysis (pre-market or post-market)"""
    if request.mode not in ["pre", "post"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'pre' or 'post'.")

    try:
        stock = get_stock_by_code(code, user_id=current_user.id)
        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock {code} not found")

        print(f"Triggering {request.mode}-market analysis for stock {code} (User: {current_user.id})")
        await asyncio.to_thread(scheduler_manager.run_stock_analysis_task, code, request.mode, user_id=current_user.id)
        return {"status": "success", "message": f"Stock {request.mode}-market analysis triggered for {code}"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/reports")
async def list_stock_reports(current_user: User = Depends(get_current_user)):
    """List all stock analysis reports for the current user"""
    user_report_dir = get_user_report_dir(current_user.id)
    stocks_dir = os.path.join(user_report_dir, "stocks")

    if not os.path.exists(stocks_dir):
        return []

    reports = []
    files = glob.glob(os.path.join(stocks_dir, "*.md"))
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


@app.get("/api/stocks/reports/{filename}")
async def get_stock_report(filename: str, current_user: User = Depends(get_current_user)):
    """Get the content of a stock analysis report"""
    if not filename.endswith(".md") or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    user_report_dir = get_user_report_dir(current_user.id)
    filepath = os.path.join(user_report_dir, "stocks", filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Report not found")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    return {"content": content}


@app.delete("/api/stocks/reports/{filename}")
async def delete_stock_report(filename: str, current_user: User = Depends(get_current_user)):
    """Delete a stock analysis report"""
    try:
        if not filename.endswith(".md") or ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        user_report_dir = get_user_report_dir(current_user.id)
        file_path = os.path.join(user_report_dir, "stocks", filename)

        if os.path.exists(file_path):
            os.remove(file_path)
            return {"status": "success", "message": f"Deleted {filename}"}
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting stock report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/stocks")
async def search_market_stocks(query: str = ""):
    stocks = []
    
    # Check cache
    if os.path.exists(MARKET_STOCKS_CACHE):
        try:
            mtime = os.path.getmtime(MARKET_STOCKS_CACHE)
            # Cache for 24h
            if (datetime.now().timestamp() - mtime) < 86400:
                with open(MARKET_STOCKS_CACHE, 'r', encoding='utf-8') as f:
                    stocks = json.load(f)
        except Exception as e:
            print(f"Stock cache read error: {e}")
            
    if not stocks:
        print("Fetching fresh stock list from AkShare...")
        try:
            import akshare as ak
            # stock_zh_a_spot_em returns huge dataframe. 
            # Use stock_info_a_code_name() if available for lighter list
            df = ak.stock_info_a_code_name()
            if not df.empty:
                # columns: code, name
                stocks = df.to_dict('records')
                # Save cache
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

@app.get("/api/market/stocks/{code}/details")
async def get_stock_details_endpoint(code: str):
    try:
        # Realtime quote
        quote = get_stock_realtime_quote(code)
        
        # Company Info (Sector/Industry)
        info = {}
        try:
            import akshare as ak
            df = ak.stock_individual_info_em(symbol=code)
            if not df.empty:
                # df columns: item, value
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

@app.get("/api/market/stocks/{code}/history")
async def get_stock_history_endpoint(code: str):
    try:
        data = await asyncio.to_thread(get_stock_history, code)
        return sanitize_data(data)
    except Exception as e:
        print(f"History error: {e}")
        return []


# --- AI Recommendation API ---

class RecommendationRequest(BaseModel):
    mode: str = "all"  # "short", "long", "all"
    force_refresh: bool = False


class RecommendationResponse(BaseModel):
    mode: str
    generated_at: str
    short_term: Optional[Dict[str, Any]] = None
    long_term: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any]


@app.post("/api/recommend/generate")
async def generate_recommendations_endpoint(
    request: RecommendationRequest = None,
    current_user: User = Depends(get_current_user)
):
    """
    Generate AI investment recommendations.

    - mode: "short" (7+ days), "long" (3+ months), or "all"
    - force_refresh: Force regenerate even if cached

    If user has configured investment preferences, recommendations will be
    personalized based on those preferences (risk level, sector preferences, etc.)
    """
    mode = request.mode if request else "all"
    force_refresh = request.force_refresh if request else False

    if mode not in ["short", "long", "all"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'short', 'long', or 'all'.")

    try:
        from src.analysis.recommendation import RecommendationEngine
        from src.llm.client import get_llm_client
        from src.data_sources.web_search import WebSearch
        from src.cache import cache_manager
        from src.storage.db import get_user_preferences

        # Load user preferences (if configured)
        user_preferences = None
        try:
            prefs_data = get_user_preferences(current_user.id)
            if prefs_data and prefs_data.get('preferences'):
                user_preferences = prefs_data.get('preferences')
                print(f"Loaded personalized preferences for user {current_user.id}")
                print(f"  - Risk level: {user_preferences.get('risk_level')}")
                print(f"  - Preferred sectors: {user_preferences.get('preferred_sectors')}")
                print(f"  - Excluded sectors: {user_preferences.get('excluded_sectors')}")
                print(f"  - Preferred fund types: {user_preferences.get('preferred_fund_types')}")
        except Exception as e:
            print(f"No user preferences found: {e}")

        # Check cache first (unless force refresh)
        # Include preferences hash in cache key for personalized results
        prefs_hash = "personalized" if user_preferences else "default"
        if not force_refresh:
            cache_key = f"recommendations:{current_user.id}:{mode}:{prefs_hash}"
            cached = cache_manager.get(cache_key)
            if cached:
                print(f"Returning cached recommendations for user {current_user.id}")
                return sanitize_for_json(cached)

        print(f"Generating {mode} recommendations for user {current_user.id} (personalized: {user_preferences is not None})...")

        # Initialize engine
        llm_client = get_llm_client()
        web_search = WebSearch()
        engine = RecommendationEngine(
            llm_client=llm_client,
            web_search=web_search,
            cache_manager=cache_manager
        )

        # Generate recommendations (run in thread to avoid blocking)
        results = await asyncio.to_thread(
            engine.generate_recommendations,
            mode=mode,
            use_llm=True,
            user_preferences=user_preferences
        )

        # Sanitize results to ensure JSON-serializable
        results = sanitize_for_json(results)

        # Cache results (4 hours)
        cache_key = f"recommendations:{current_user.id}:{mode}:{prefs_hash}"
        cache_manager.set(cache_key, results, ttl=14400)

        # Save to database
        from src.storage.db import save_recommendation_report
        save_recommendation_report({
            "mode": mode,
            "recommendations_json": results,
            "market_context": results.get("metadata", {})
        }, user_id=current_user.id)

        return results

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommend/stocks/short")
async def get_short_term_stock_recommendations(
    limit: int = 10,
    min_score: int = 60,
    current_user: User = Depends(get_current_user)
):
    """Get short-term stock recommendations (7+ days)."""
    try:
        from src.storage.db import get_latest_recommendation_report

        report = get_latest_recommendation_report(user_id=current_user.id, mode="short")
        if not report and (report := get_latest_recommendation_report(user_id=current_user.id, mode="all")):
            pass

        if not report:
            return {"recommendations": [], "message": "No recommendations available. Please generate first."}

        data = report.get("recommendations_json", {})
        short_term = data.get("short_term", {})
        stocks = short_term.get("short_term_stocks", []) if isinstance(short_term, dict) else []

        # Filter by min_score
        filtered = [s for s in stocks if s.get("recommendation_score", 0) >= min_score]

        return {
            "recommendations": filtered[:limit],
            "market_view": short_term.get("market_view", ""),
            "generated_at": report.get("generated_at"),
        }
    except Exception as e:
        print(f"Error: {e}")
        return {"recommendations": [], "error": str(e)}


@app.get("/api/recommend/stocks/long")
async def get_long_term_stock_recommendations(
    limit: int = 10,
    min_score: int = 60,
    current_user: User = Depends(get_current_user)
):
    """Get long-term stock recommendations (3+ months)."""
    try:
        from src.storage.db import get_latest_recommendation_report

        report = get_latest_recommendation_report(user_id=current_user.id, mode="long")
        if not report and (report := get_latest_recommendation_report(user_id=current_user.id, mode="all")):
            pass

        if not report:
            return {"recommendations": [], "message": "No recommendations available. Please generate first."}

        data = report.get("recommendations_json", {})
        long_term = data.get("long_term", {})
        stocks = long_term.get("long_term_stocks", []) if isinstance(long_term, dict) else []

        filtered = [s for s in stocks if s.get("recommendation_score", 0) >= min_score]

        return {
            "recommendations": filtered[:limit],
            "macro_view": long_term.get("macro_view", ""),
            "generated_at": report.get("generated_at"),
        }
    except Exception as e:
        print(f"Error: {e}")
        return {"recommendations": [], "error": str(e)}


@app.get("/api/recommend/funds/short")
async def get_short_term_fund_recommendations(
    limit: int = 5,
    min_score: int = 60,
    current_user: User = Depends(get_current_user)
):
    """Get short-term fund recommendations (7+ days)."""
    try:
        from src.storage.db import get_latest_recommendation_report

        report = get_latest_recommendation_report(user_id=current_user.id, mode="short")
        if not report and (report := get_latest_recommendation_report(user_id=current_user.id, mode="all")):
            pass

        if not report:
            return {"recommendations": [], "message": "No recommendations available. Please generate first."}

        data = report.get("recommendations_json", {})
        short_term = data.get("short_term", {})
        funds = short_term.get("short_term_funds", []) if isinstance(short_term, dict) else []

        filtered = [f for f in funds if f.get("recommendation_score", 0) >= min_score]

        return {
            "recommendations": filtered[:limit],
            "generated_at": report.get("generated_at"),
        }
    except Exception as e:
        print(f"Error: {e}")
        return {"recommendations": [], "error": str(e)}


@app.get("/api/recommend/funds/long")
async def get_long_term_fund_recommendations(
    limit: int = 5,
    min_score: int = 60,
    current_user: User = Depends(get_current_user)
):
    """Get long-term fund recommendations (3+ months)."""
    try:
        from src.storage.db import get_latest_recommendation_report

        report = get_latest_recommendation_report(user_id=current_user.id, mode="long")
        if not report and (report := get_latest_recommendation_report(user_id=current_user.id, mode="all")):
            pass

        if not report:
            return {"recommendations": [], "message": "No recommendations available. Please generate first."}

        data = report.get("recommendations_json", {})
        long_term = data.get("long_term", {})
        funds = long_term.get("long_term_funds", []) if isinstance(long_term, dict) else []

        filtered = [f for f in funds if f.get("recommendation_score", 0) >= min_score]

        return {
            "recommendations": filtered[:limit],
            "generated_at": report.get("generated_at"),
        }
    except Exception as e:
        print(f"Error: {e}")
        return {"recommendations": [], "error": str(e)}


@app.get("/api/recommend/latest")
async def get_latest_recommendations(
    current_user: User = Depends(get_current_user)
):
    """Get the latest recommendation report."""
    try:
        from src.storage.db import get_latest_recommendation_report

        report = get_latest_recommendation_report(user_id=current_user.id)

        if not report:
            return {
                "available": False,
                "message": "No recommendations available. Please generate first using POST /api/recommend/generate"
            }

        return {
            "available": True,
            "data": report.get("recommendations_json", {}),
            "generated_at": report.get("generated_at"),
            "mode": report.get("mode"),
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommend/history")
async def get_recommendation_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """Get historical recommendation reports."""
    try:
        from src.storage.db import get_recommendation_reports

        reports = get_recommendation_reports(user_id=current_user.id, limit=limit)

        # Return summaries without full content
        summaries = []
        for r in reports:
            data = r.get("recommendations_json", {})
            summaries.append({
                "id": r.get("id"),
                "mode": r.get("mode"),
                "generated_at": r.get("generated_at"),
                "short_term_count": len(data.get("short_term", {}).get("short_term_stocks", [])) if data.get("short_term") else 0,
                "long_term_count": len(data.get("long_term", {}).get("long_term_stocks", [])) if data.get("long_term") else 0,
            })

        return {"reports": summaries}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# User Investment Preferences API
# ====================================================================

@app.get("/api/preferences")
async def get_user_preferences_endpoint(
    current_user: User = Depends(get_current_user)
):
    """Get user investment preferences."""
    try:
        from src.storage.db import get_user_preferences
        from src.storage.user_preferences import RISK_LEVEL_PRESETS, RiskLevel

        prefs = get_user_preferences(user_id=current_user.id)

        if not prefs:
            # Return default moderate preferences
            default_prefs = RISK_LEVEL_PRESETS[RiskLevel.MODERATE].to_dict()
            return {
                "exists": False,
                "preferences": default_prefs
            }

        return {
            "exists": True,
            "preferences": prefs.get("preferences", {}),
            "updated_at": prefs.get("updated_at")
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/preferences")
async def save_user_preferences_endpoint(
    preferences: Dict,
    current_user: User = Depends(get_current_user)
):
    """Save user investment preferences."""
    try:
        from src.storage.db import save_user_preferences

        save_user_preferences(user_id=current_user.id, preferences=preferences)

        return {
            "success": True,
            "message": "Investment preferences saved successfully"
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/preferences/presets")
async def get_preference_presets():
    """Get predefined risk level presets."""
    try:
        from src.storage.user_preferences import RISK_LEVEL_PRESETS, RiskLevel

        presets = {}
        for risk_level in RiskLevel:
            presets[risk_level.value] = RISK_LEVEL_PRESETS[risk_level].to_dict()

        return {"presets": presets}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# Stock & Fund Details API
# ====================================================================

@app.get("/api/details/stock/{code}")
async def get_stock_details(
    code: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed stock information."""
    try:
        import akshare as ak

        # Get basic info
        spot_df = ak.stock_zh_a_spot_em()
        stock_info = spot_df[spot_df['代码'] == code]

        if stock_info.empty:
            raise HTTPException(status_code=404, detail="Stock not found")

        stock_data = stock_info.iloc[0].to_dict()

        # Get historical data (last 60 days)
        try:
            hist_df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            if not hist_df.empty:
                hist_df = hist_df.tail(60)
                history = hist_df.to_dict('records')
            else:
                history = []
        except:
            history = []

        # Get financial indicators
        try:
            financial_df = ak.stock_financial_analysis_indicator(symbol=code)
            if not financial_df.empty:
                financial_data = financial_df.iloc[0].to_dict()
            else:
                financial_data = {}
        except:
            financial_data = {}

        return {
            "code": code,
            "name": stock_data.get('名称'),
            "price": stock_data.get('最新价'),
            "change_pct": stock_data.get('涨跌幅'),
            "volume": stock_data.get('成交量'),
            "turnover": stock_data.get('成交额'),
            "pe": stock_data.get('市盈率-动态'),
            "pb": stock_data.get('市净率'),
            "market_cap": stock_data.get('总市值'),
            "history": history,
            "financial": financial_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/details/fund/{code}")
async def get_fund_details(
    code: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed fund information."""
    try:
        import akshare as ak

        # Get fund basic info
        try:
            info_df = ak.fund_individual_basic_info_xq(symbol=code)
            basic_info = info_df.to_dict() if not info_df.empty else {}
        except:
            basic_info = {}

        # Get fund NAV history
        try:
            nav_df = ak.fund_open_fund_info_em(fund=code, indicator="单位净值走势")
            if not nav_df.empty:
                nav_df = nav_df.tail(180)  # Last 180 days
                nav_history = nav_df.to_dict('records')
            else:
                nav_history = []
        except:
            nav_history = []

        # Get fund manager info
        try:
            manager_df = ak.fund_manager_em(fund=code)
            manager_info = manager_df.to_dict('records') if not manager_df.empty else []
        except:
            manager_info = []

        # Get holdings info
        try:
            holdings_df = ak.fund_portfolio_hold_em(symbol=code, date="")
            if not holdings_df.empty:
                holdings = holdings_df.head(10).to_dict('records')  # Top 10 holdings
            else:
                holdings = []
        except:
            holdings = []

        return {
            "code": code,
            "name": basic_info.get('基金简称'),
            "type": basic_info.get('基金类型'),
            "basic_info": basic_info,
            "nav_history": nav_history,
            "manager_info": manager_info,
            "top_holdings": holdings,
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# Comparison API
# ====================================================================

@app.post("/api/compare/stocks")
async def compare_stocks(
    codes: List[str],
    current_user: User = Depends(get_current_user)
):
    """Compare multiple stocks side by side."""
    try:
        import akshare as ak

        if len(codes) < 2 or len(codes) > 5:
            raise HTTPException(status_code=400, detail="Please select 2-5 stocks to compare")

        spot_df = ak.stock_zh_a_spot_em()
        comparisons = []

        for code in codes:
            stock_info = spot_df[spot_df['代码'] == code]
            if not stock_info.empty:
                stock_data = stock_info.iloc[0]
                comparisons.append({
                    "code": code,
                    "name": stock_data.get('名称'),
                    "price": stock_data.get('最新价'),
                    "change_pct": stock_data.get('涨跌幅'),
                    "pe": stock_data.get('市盈率-动态'),
                    "pb": stock_data.get('市净率'),
                    "market_cap": stock_data.get('总市值'),
                    "volume_ratio": stock_data.get('量比'),
                    "turnover_rate": stock_data.get('换手率'),
                    "amplitude": stock_data.get('振幅'),
                })

        if not comparisons:
            raise HTTPException(status_code=404, detail="No valid stocks found")

        return {"stocks": comparisons}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/compare/funds")
async def compare_funds(
    codes: List[str],
    current_user: User = Depends(get_current_user)
):
    """Compare multiple funds side by side."""
    try:
        import akshare as ak

        if len(codes) < 2 or len(codes) > 5:
            raise HTTPException(status_code=400, detail="Please select 2-5 funds to compare")

        comparisons = []

        for code in codes:
            try:
                # Get fund ranking data
                rank_data = None
                for fund_type in ["股票型", "混合型", "指数型"]:
                    try:
                        df = ak.fund_open_fund_rank_em(symbol=fund_type)
                        fund_row = df[df['基金代码'] == code]
                        if not fund_row.empty:
                            rank_data = fund_row.iloc[0]
                            break
                    except:
                        continue

                if rank_data is not None:
                    comparisons.append({
                        "code": code,
                        "name": rank_data.get('基金简称'),
                        "fund_type": fund_type,
                        "nav": rank_data.get('单位净值'),
                        "return_1w": rank_data.get('近1周'),
                        "return_1m": rank_data.get('近1月'),
                        "return_3m": rank_data.get('近3月'),
                        "return_6m": rank_data.get('近6月'),
                        "return_1y": rank_data.get('近1年'),
                        "return_3y": rank_data.get('近3年'),
                    })
            except:
                continue

        if not comparisons:
            raise HTTPException(status_code=404, detail="No valid funds found")

        return {"funds": comparisons}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="EastMoney API Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    args = parser.parse_args()

    # Need to run init_db if running directly without lifespan
    init_db()
    scheduler_manager.start()
    uvicorn.run(app, host=args.host, port=args.port)
