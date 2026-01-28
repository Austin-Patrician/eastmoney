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
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports from project
from src.analysis.pre_market import PreMarketAnalyst
from src.analysis.post_market import PostMarketAnalyst
from src.analysis.sentiment.dashboard import SentimentDashboard
from src.analysis.commodities.gold_silver import GoldSilverAnalyst
from src.analysis.dashboard import DashboardService
from src.analysis.fund import FundDiagnosis, RiskMetricsCalculator, DrawdownAnalyzer, FundComparison, PortfolioAnalyzer
from src.analysis.portfolio import RiskMetricsCalculator as PortfolioRiskMetrics, CorrelationAnalyzer, StressTestEngine, SignalGenerator
from src.analysis.portfolio.stress_test import StressScenario, ScenarioType, PREDEFINED_SCENARIOS
from src.data_sources.akshare_api import search_funds
from src.storage.db import init_db, get_active_funds, get_all_funds, upsert_fund, delete_fund, get_fund_by_code, get_all_stocks, upsert_stock, delete_stock, get_stock_by_code, search_stock_basic, get_stock_basic_count, get_stock_basic_last_updated
from src.storage.db import get_user_positions, get_position_by_id, create_position, update_position, delete_position, get_portfolio_summary, get_diagnosis_cache, save_diagnosis_cache
# New portfolio management imports
from src.storage.db import (
    get_user_portfolios, get_portfolio_by_id, get_default_portfolio, create_portfolio,
    update_portfolio, delete_portfolio, set_default_portfolio as db_set_default_portfolio,
    get_portfolio_positions, get_position_by_asset, get_unified_position_by_id,
    upsert_position, update_position_price, delete_unified_position,
    get_portfolio_transactions, get_position_transactions, get_transaction_by_id,
    create_transaction, delete_transaction, recalculate_position,
    save_portfolio_snapshot, get_portfolio_snapshots, get_latest_snapshot,
    create_alert, get_portfolio_alerts, mark_alert_read, dismiss_alert, get_unread_alert_count,
    delete_dip_plan, execute_dip_plan,
    migrate_fund_positions_to_positions
)
from src.services.news_service import news_service
from src.services.assistant_service import assistant_service
from src.scheduler.manager import scheduler_manager
from src.report_gen import save_report, save_stock_report
# Updated import
from src.data_sources.akshare_api import get_all_fund_list, get_stock_realtime_quote, get_all_stock_spot_map, get_stock_history
import akshare as ak
import pandas as pd
from src.auth import Token, UserCreate, User, create_access_token, get_password_hash, verify_password, get_current_user, create_user, get_user_by_username
from fastapi.security import OAuth2PasswordRequestForm
from openai import OpenAI

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

    # Auto-sync stock basic info if table is empty
    stock_count = get_stock_basic_count()
    if stock_count == 0:
        print("Stock basic table empty, syncing from TuShare...")
        try:
            from src.data_sources.tushare_client import sync_stock_basic
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, sync_stock_basic)
        except Exception as e:
            print(f"Auto-sync stock basic failed: {e}")
    else:
        print(f"Stock basic table has {stock_count} stocks")

    print("Starting Scheduler (Background)...")
    # Run scheduler init in a separate thread so it doesn't block startup
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, scheduler_manager.start)
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

# Static files configuration
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

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
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    tavily_api_key: Optional[str] = None

class ModelListRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    provider: str = "openai"

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


# --- Admin Endpoints for Stock Basic Sync ---

@app.post("/api/admin/sync-stock-basic")
async def sync_stock_basic_endpoint(current_user: User = Depends(get_current_user)):
    """
    Manually trigger sync of stock basic info from TuShare.
    Requires authentication.
    """
    try:
        from src.data_sources.tushare_client import sync_stock_basic
        loop = asyncio.get_running_loop()
        count = await loop.run_in_executor(None, sync_stock_basic)
        return {
            "status": "success",
            "synced": count,
            "message": f"Synced {count} stocks from TuShare"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/api/admin/stock-basic-status")
async def get_stock_basic_status(current_user: User = Depends(get_current_user)):
    """
    Get status of stock basic table.
    Returns count and last update time.
    """
    count = get_stock_basic_count()
    last_updated = get_stock_basic_last_updated()
    return {
        "count": count,
        "last_updated": last_updated
    }

@app.post("/api/llm/models")
async def list_llm_models(request: ModelListRequest, current_user: User = Depends(get_current_user)):
    try:
        # Prioritize request params, then env vars
        api_key = request.api_key or os.getenv("OPENAI_API_KEY")
        base_url = request.base_url or os.getenv("OPENAI_BASE_URL")
        
        if not api_key:
             # Some local servers like Ollama might not require a key if configured loosely, but usually OpenAI client requires something.
             # If using local provider (oobabooga, etc), often "key" can be anything.
             if not base_url: # If no base_url and no key, that's a problem for standard OpenAI
                 pass
             elif "localhost" in base_url or "127.0.0.1" in base_url:
                 if not api_key: api_key = "dummy" 

        if not api_key and not (base_url and ("localhost" in base_url or "127.0.0.1" in base_url)):
             return {"models": [], "warning": "API Key missing"}

        # OpenAI Compatible
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
            
        client = OpenAI(**client_kwargs)
        
        def _fetch():
            return client.models.list()
            
        models_resp = await asyncio.to_thread(_fetch)
        
        # Determine model list based on provider or inspection
        # Standard OpenAI models.list returns a list of objects with .id
        model_names = sorted([m.id for m in models_resp.data])
        
        return {"models": model_names}
    except Exception as e:
        print(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    """
    Get market indices with TuShare + yFinance hybrid approach.

    Migration Note: Phase 5 - Replaced error-prone ak.index_global_spot_em()
    """
    import time
    from datetime import datetime
    from config.settings import DATA_SOURCE_PROVIDER
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

    # Try TuShare first
    if DATA_SOURCE_PROVIDER in ('tushare', 'hybrid'):
        try:
            from src.data_sources.data_source_manager import get_market_indices_from_tushare
            results = get_market_indices_from_tushare()

            if results:
                data = sanitize_data(results)
                _INDICES_CACHE["data"] = data
                _INDICES_CACHE["expiry"] = now_ts + 60  # 60s cache
                return data
        except Exception as e:
            print(f"TuShare indices failed: {e}")

    # Fallback to AkShare
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
        "openai_base_url": env.get("OPENAI_BASE_URL", ""),
        "openai_model": env.get("OPENAI_MODEL", ""),
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
    if settings.openai_base_url is not None:
         updates["OPENAI_BASE_URL"] = settings.openai_base_url
    if settings.openai_model is not None:
         updates["OPENAI_MODEL"] = settings.openai_model
    if settings.tavily_api_key:
        updates["TAVILY_API_KEY"] = settings.tavily_api_key
        
    save_env_file(updates)
    
    # Update runtime env
    for k, v in updates.items():
        if v is not None:
            os.environ[k] = v

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
import uuid

# Global thread pool for background tasks
_recommendation_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="recommend_")

@app.get("/api/stocks", response_model=List[StockItem])
async def get_stocks_endpoint(current_user: User = Depends(get_current_user)):
    try:
        stocks = get_all_stocks(user_id=current_user.id)

        if not stocks:
            return []

        # Batch fetch realtime quotes using tushare (more reliable than akshare)
        try:
            from src.data_sources.tushare_client import get_realtime_quotes

            # Get all stock codes
            stock_codes = [s['code'] for s in stocks]

            # Fetch realtime quotes in batch
            quotes_df = await asyncio.to_thread(get_realtime_quotes, stock_codes)

            # Build a lookup dict for quick access
            quotes_lookup = {}
            if quotes_df is not None and not quotes_df.empty:
                for _, row in quotes_df.iterrows():
                    # The ts_code might have suffix, extract plain code
                    ts_code = str(row.get('ts_code', ''))
                    plain_code = ts_code.split('.')[0] if '.' in ts_code else ts_code
                    quotes_lookup[plain_code] = row

            # Merge quotes with stock data
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
                        # tushare vol is in shares, convert to hands (100 shares = 1 hand)
                        item['volume'] = float(vol)

                results.append(StockItem(**item))

            return results

        except ImportError:
            # Fallback to old akshare method if tushare not available
            print("TuShare not available, falling back to akshare")

            def fetch_single_quote(stock):
                item = dict(stock)
                try:
                    df = ak.stock_bid_ask_em(symbol=stock['code'])
                    if not df.empty:
                        info = dict(zip(df['item'], df['value']))
                        price = info.get('最新') or info.get('最新价')
                        change = info.get('涨幅') or info.get('涨跌幅')
                        vol = info.get('总手') or info.get('成交量')

                        if price is not None and str(price) != '':
                            item['price'] = float(price)
                        if change is not None and str(change) != '':
                            item['change_pct'] = float(change)
                        if vol is not None and str(vol) != '':
                            v = float(vol)
                            if info.get('总手') is not None:
                                v = v * 100
                            item['volume'] = v
                except Exception:
                    pass
                return StockItem(**item)

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=10) as executor:
                results = await loop.run_in_executor(None, lambda: list(executor.map(fetch_single_quote, stocks)))

            return results

    except Exception as e:
        print(f"Error reading stocks: {e}")
        import traceback
        traceback.print_exc()
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
    """
    Search stocks from local database (synced from TuShare stock_basic).
    Returns stocks matching code prefix or name/industry substring.
    """
    # First check if we have data in database
    stock_count = get_stock_basic_count()

    if stock_count > 0:
        # Use database search
        results = search_stock_basic(query, limit=50)
        return results

    # Fallback to old JSON cache method if database is empty
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


# --- Stock Professional Features API ---

from src.data_sources.tushare_client import (
    get_financial_indicators, get_income_statement, get_balance_sheet, get_cashflow_statement,
    get_top10_holders, get_shareholder_number,
    get_margin_detail,
    get_forecast, get_share_float, get_dividend,
    get_stock_factors, get_chip_performance,
    normalize_ts_code,
    search_funds_tushare
)

# In-memory cache for stock professional features
_stock_feature_cache: Dict[str, Dict[str, Any]] = {}

def _get_cached_data(cache_key: str, ttl_minutes: int) -> Optional[Dict]:
    """Get cached data if not expired."""
    if cache_key in _stock_feature_cache:
        cached = _stock_feature_cache[cache_key]
        if datetime.now() - cached['timestamp'] < timedelta(minutes=ttl_minutes):
            return cached['data']
    return None

def _set_cache(cache_key: str, data: Dict):
    """Set cache with timestamp."""
    _stock_feature_cache[cache_key] = {
        'data': data,
        'timestamp': datetime.now()
    }


@app.get("/api/stocks/{code}/financials")
async def get_stock_financials(code: str, current_user: User = Depends(get_current_user)):
    """
    Get financial health diagnosis data.

    Cache TTL: 1 day (86400s / 1440 min)
    """
    cache_key = f"financials:{code}"
    cached = _get_cached_data(cache_key, 1440)  # 1 day
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

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        print(f"Error fetching financial data for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/{code}/shareholders")
async def get_stock_shareholders(code: str, current_user: User = Depends(get_current_user)):
    """
    Get shareholder structure analysis data.

    Cache TTL: 6 hours
    """
    cache_key = f"shareholders:{code}"
    cached = _get_cached_data(cache_key, 360)  # 6 hours
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
                        "trend": "decreasing" if change < 0 else "increasing",  # Fewer holders = more concentrated
                        "signal": "positive" if change < -5 else ("negative" if change > 5 else "neutral")
                    }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        print(f"Error fetching shareholder data for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/{code}/margin")
async def get_stock_margin(code: str, current_user: User = Depends(get_current_user)):
    """
    Get leverage fund monitoring data.

    Cache TTL: 30 minutes
    """
    cache_key = f"margin:{code}"
    cached = _get_cached_data(cache_key, 30)
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
                "rzye": float(latest.get('rzye', 0)) if pd.notna(latest.get('rzye')) else None,  # 融资余额
                "rqye": float(latest.get('rqye', 0)) if pd.notna(latest.get('rqye')) else None,  # 融券余额
                "rzmre": float(latest.get('rzmre', 0)) if pd.notna(latest.get('rzmre')) else None,  # 融资买入额
                "rqmcl": float(latest.get('rqmcl', 0)) if pd.notna(latest.get('rqmcl')) else None,  # 融券卖出量
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

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        print(f"Error fetching margin data for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/{code}/events")
async def get_stock_events(code: str, current_user: User = Depends(get_current_user)):
    """
    Get event-driven calendar data.

    Cache TTL: 1 hour
    """
    cache_key = f"events:{code}"
    cached = _get_cached_data(cache_key, 60)
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

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        print(f"Error fetching event data for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/{code}/quant")
async def get_stock_quant(code: str, current_user: User = Depends(get_current_user)):
    """
    Get quantitative signal dashboard data.

    Cache TTL: 15 minutes
    """
    cache_key = f"quant:{code}"
    cached = _get_cached_data(cache_key, 15)
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

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        print(f"Error fetching quant data for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- AI Stock Diagnosis API ---

@app.get("/api/stocks/{code}/ai-diagnosis")
async def get_stock_ai_diagnosis(code: str, current_user: User = Depends(get_current_user)):
    """
    AI One-Click Diagnosis - Generate comprehensive investment diagnosis report.

    Integrates data from:
    - Financial health
    - Shareholder structure
    - Margin/leverage
    - Events
    - Quantitative signals

    Cache TTL: 30 minutes
    """
    cache_key = f"ai_diagnosis:{code}"
    cached = _get_cached_data(cache_key, 30)  # 30 minutes
    if cached:
        return cached

    try:
        from src.llm.client import get_llm_client
        from src.llm.stock_diagnosis_prompt import (
            STOCK_DIAGNOSIS_SYSTEM_PROMPT,
            build_diagnosis_prompt
        )
        import json
        import re

        # Get stock basic info
        stock_info = get_stock_by_code(code)
        stock_name = stock_info.get("name", code) if stock_info else code
        industry = stock_info.get("sector", "") if stock_info else ""

        # Get real-time quote for current price
        quote = get_stock_realtime_quote(code)
        current_price = None
        change_pct = None
        if quote:
            current_price = quote.get("最新价")
            change_pct = quote.get("涨跌幅")

        # Fetch all dimension data in parallel
        loop = asyncio.get_event_loop()

        financials_task = loop.run_in_executor(None, lambda: asyncio.run(get_stock_financials(code, current_user)))
        shareholders_task = loop.run_in_executor(None, lambda: asyncio.run(get_stock_shareholders(code, current_user)))
        margin_task = loop.run_in_executor(None, lambda: asyncio.run(get_stock_margin(code, current_user)))
        events_task = loop.run_in_executor(None, lambda: asyncio.run(get_stock_events(code, current_user)))
        quant_task = loop.run_in_executor(None, lambda: asyncio.run(get_stock_quant(code, current_user)))

        financials, shareholders, margin, events, quant = await asyncio.gather(
            financials_task, shareholders_task, margin_task, events_task, quant_task,
            return_exceptions=True
        )

        # Handle exceptions - use empty dicts if any API failed
        if isinstance(financials, Exception):
            print(f"Financial data fetch failed: {financials}")
            financials = {}
        if isinstance(shareholders, Exception):
            print(f"Shareholders data fetch failed: {shareholders}")
            shareholders = {}
        if isinstance(margin, Exception):
            print(f"Margin data fetch failed: {margin}")
            margin = {}
        if isinstance(events, Exception):
            print(f"Events data fetch failed: {events}")
            events = {}
        if isinstance(quant, Exception):
            print(f"Quant data fetch failed: {quant}")
            quant = {}

        # Build prompt
        prompt = build_diagnosis_prompt(
            stock_code=code,
            stock_name=stock_name,
            current_price=current_price,
            change_pct=change_pct,
            industry=industry,
            financials=financials,
            shareholders=shareholders,
            margin=margin,
            events=events,
            quant=quant
        )

        # Call LLM
        llm = get_llm_client()
        full_prompt = f"{STOCK_DIAGNOSIS_SYSTEM_PROMPT}\n\n{prompt}"
        response_text = llm.generate_content(full_prompt)

        # Parse JSON response
        # Try to extract JSON from response
        diagnosis = None
        try:
            # Try direct JSON parse first
            diagnosis = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to find JSON block in response
            json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    diagnosis = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

        if not diagnosis:
            # Create default diagnosis if parsing failed
            diagnosis = {
                "score": 50,
                "rating": "中等",
                "recommendation": "谨慎持有",
                "highlights": ["数据分析中..."],
                "risks": ["请稍后重试"],
                "action_advice": "AI分析暂时无法完成，请稍后重试",
                "key_focus": "等待AI响应"
            }

        result = {
            "code": code,
            "name": stock_name,
            "diagnosis": diagnosis,
            "data_timestamp": datetime.now().isoformat()
        }

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        print(f"Error generating AI diagnosis for {code}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/{code}/quant/ai-interpret")
async def get_quant_ai_interpretation(code: str, current_user: User = Depends(get_current_user)):
    """
    AI Technical Signal Interpretation - Convert quantitative signals to actionable advice.

    Cache TTL: 15 minutes
    """
    cache_key = f"ai_quant_interpret:{code}"
    cached = _get_cached_data(cache_key, 15)  # 15 minutes
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

        _set_cache(cache_key, result)
        return result

    except Exception as e:
        print(f"Error generating AI quant interpretation for {code}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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


def _run_recommendation_task(task_id: str, mode: str, user_id: int, user_preferences: Optional[Dict] = None):
    """
    Background task worker for generating recommendations.
    Stores progress and results in cache.
    """
    from src.cache import cache_manager

    cache_key = f"recommend_task:{task_id}"

    try:
        # Update status to running
        cache_manager.set(cache_key, {
            "status": "running",
            "progress": "Initializing recommendation engine...",
            "started_at": datetime.now().isoformat(),
            "user_id": user_id,
            "mode": mode
        }, ttl=3600)  # 1 hour TTL

        from src.analysis.recommendation import RecommendationEngine
        from src.llm.client import get_llm_client
        from src.data_sources.web_search import WebSearch

        # Update progress
        cache_manager.set(cache_key, {
            "status": "running",
            "progress": "Screening stocks and funds...",
            "started_at": datetime.now().isoformat(),
            "user_id": user_id,
            "mode": mode
        }, ttl=3600)

        llm_client = get_llm_client()
        web_search = WebSearch()
        engine = RecommendationEngine(
            llm_client=llm_client,
            web_search=web_search,
            cache_manager=cache_manager
        )

        # Generate recommendations
        results = engine.generate_recommendations(
            mode=mode,
            use_llm=True,
            user_preferences=user_preferences
        )

        # Sanitize results
        results = sanitize_for_json(results)

        # Cache the recommendation results
        prefs_hash = "personalized" if user_preferences else "default"
        result_cache_key = f"recommendations:{user_id}:{mode}:{prefs_hash}"
        cache_manager.set(result_cache_key, results, ttl=14400)  # 4 hours

        # Save to database
        from src.storage.db import save_recommendation_report
        save_recommendation_report({
            "mode": mode,
            "recommendations_json": results,
            "market_context": results.get("metadata", {})
        }, user_id=user_id)

        # Update task status to completed
        cache_manager.set(cache_key, {
            "status": "completed",
            "progress": "Recommendations generated successfully!",
            "started_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "user_id": user_id,
            "mode": mode,
            "result": results
        }, ttl=3600)

        print(f"[Task {task_id}] Recommendation generation completed for user {user_id}")

    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()

        # Update task status to failed
        cache_manager.set(cache_key, {
            "status": "failed",
            "progress": f"Error: {error_msg}",
            "error": error_msg,
            "user_id": user_id,
            "mode": mode
        }, ttl=3600)

        print(f"[Task {task_id}] Recommendation generation failed: {error_msg}")


@app.post("/api/recommend/generate")
async def generate_recommendations_endpoint(
    request: RecommendationRequest = None,
    current_user: User = Depends(get_current_user)
):
    """
    Generate AI investment recommendations (runs in background).

    - mode: "short" (7+ days), "long" (3+ months), or "all"
    - force_refresh: Force regenerate even if cached

    Returns a task_id immediately. Use GET /api/recommend/task/{task_id} to poll status.
    """
    mode = request.mode if request else "all"
    force_refresh = request.force_refresh if request else False

    if mode not in ["short", "long", "all"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'short', 'long', or 'all'.")

    try:
        from src.cache import cache_manager
        from src.storage.db import get_user_preferences

        # Load user preferences (if configured)
        user_preferences = None
        try:
            prefs_data = get_user_preferences(current_user.id)
            if prefs_data and prefs_data.get('preferences'):
                user_preferences = prefs_data.get('preferences')
                print(f"Loaded personalized preferences for user {current_user.id}")
        except Exception as e:
            print(f"No user preferences found: {e}")

        # Check cache first (unless force refresh)
        prefs_hash = "personalized" if user_preferences else "default"
        if not force_refresh:
            cache_key = f"recommendations:{current_user.id}:{mode}:{prefs_hash}"
            cached = cache_manager.get(cache_key)
            if cached:
                print(f"Returning cached recommendations for user {current_user.id}")
                return {
                    "status": "completed",
                    "cached": True,
                    "result": sanitize_for_json(cached)
                }

        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # Initialize task status
        cache_manager.set(f"recommend_task:{task_id}", {
            "status": "pending",
            "progress": "Task queued...",
            "user_id": current_user.id,
            "mode": mode
        }, ttl=3600)

        # Submit to background executor
        _recommendation_executor.submit(
            _run_recommendation_task,
            task_id,
            mode,
            current_user.id,
            user_preferences
        )

        print(f"Started recommendation task {task_id} for user {current_user.id}")

        return {
            "status": "started",
            "task_id": task_id,
            "message": "Recommendation generation started. Poll /api/recommend/task/{task_id} for status."
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommend/task/{task_id}")
async def get_recommendation_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get the status of a recommendation generation task.

    Returns:
    - status: "pending", "running", "completed", or "failed"
    - progress: Human-readable progress message
    - result: Full recommendation data (only when status is "completed")
    """
    try:
        from src.cache import cache_manager

        cache_key = f"recommend_task:{task_id}"
        task_data = cache_manager.get(cache_key)

        if not task_data:
            raise HTTPException(status_code=404, detail="Task not found or expired")

        # Security check: ensure task belongs to current user
        if task_data.get("user_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Return task status
        response = {
            "task_id": task_id,
            "status": task_data.get("status"),
            "progress": task_data.get("progress"),
            "mode": task_data.get("mode")
        }

        if task_data.get("status") == "completed":
            response["result"] = task_data.get("result")
            response["completed_at"] = task_data.get("completed_at")

        if task_data.get("status") == "failed":
            response["error"] = task_data.get("error")

        return response

    except HTTPException:
        raise
    except Exception as e:
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


# ====================================================================
# Widget Data API - Configurable Dashboard
# ====================================================================

from src.analysis.widget_service import widget_service, WidgetType


@app.get("/api/widgets/northbound-flow")
async def get_widget_northbound_flow(days: int = 5):
    """Get northbound capital flow data for widget."""
    try:
        data = await asyncio.to_thread(widget_service.get_northbound_flow, days)
        return sanitize_data(data)
    except Exception as e:
        print(f"Error fetching northbound flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/widgets/industry-flow")
async def get_widget_industry_flow(limit: int = 10):
    """Get industry money flow data for widget."""
    try:
        data = await asyncio.to_thread(widget_service.get_industry_flow, limit)
        return sanitize_data(data)
    except Exception as e:
        print(f"Error fetching industry flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/widgets/sector-performance")
async def get_widget_sector_performance(limit: int = 10):
    """Get sector performance data for widget."""
    try:
        data = await asyncio.to_thread(widget_service.get_sector_performance, limit)
        return sanitize_data(data)
    except Exception as e:
        print(f"Error fetching sector performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/widgets/top-list")
async def get_widget_top_list(limit: int = 10):
    """Get dragon tiger list data for widget."""
    try:
        data = await asyncio.to_thread(widget_service.get_top_list, limit)
        return sanitize_data(data)
    except Exception as e:
        print(f"Error fetching top list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/widgets/forex-rates")
async def get_widget_forex_rates():
    """Get forex rates data for widget."""
    try:
        data = await asyncio.to_thread(widget_service.get_forex_rates)
        return sanitize_data(data)
    except Exception as e:
        print(f"Error fetching forex rates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/widgets/watchlist")
async def get_widget_watchlist(current_user: User = Depends(get_current_user)):
    """Get watchlist quotes for widget."""
    try:
        # Get user's stocks
        stocks = get_all_stocks(user_id=current_user.id)
        stock_codes = [s['code'] for s in stocks]

        if not stock_codes:
            return {"stocks": [], "updated_at": datetime.now().isoformat()}

        data = await asyncio.to_thread(widget_service.get_watchlist_quotes, stock_codes)
        return sanitize_data(data)
    except Exception as e:
        print(f"Error fetching watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/widgets/news")
async def get_widget_news(limit: int = 20, src: str = 'sina'):
    """Get news feed for widget."""
    try:
        data = await asyncio.to_thread(widget_service.get_news, limit, src)
        return sanitize_data(data)
    except Exception as e:
        print(f"Error fetching news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/widgets/main-capital-flow")
async def get_widget_main_capital_flow(limit: int = 10):
    """Get main capital flow (top stocks and total) for widget."""
    try:
        data = await asyncio.to_thread(widget_service.get_main_capital_flow, limit)
        return sanitize_data(data)
    except Exception as e:
        print(f"Error fetching main capital flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# Dashboard Layout API
# ====================================================================

from src.storage.db import (
    get_user_layouts,
    get_layout_by_id,
    get_default_layout,
    save_layout,
    update_layout,
    delete_layout,
    set_default_layout,
)


class LayoutCreate(BaseModel):
    name: str
    layout: Dict[str, Any]
    is_default: bool = False


class LayoutUpdate(BaseModel):
    name: Optional[str] = None
    layout: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


# Dashboard layout presets
DASHBOARD_PRESETS = {
    "trader": {
        "name": "交易者视图",
        "name_en": "Trader View",
        "description": "实时异动、北向资金、龙虎榜、行业资金流",
        "widgets": [
            {"id": "abnormal", "type": "abnormal_movements", "position": {"x": 0, "y": 0, "w": 6, "h": 4}},
            {"id": "northbound", "type": "northbound_flow", "position": {"x": 6, "y": 0, "w": 6, "h": 4}},
            {"id": "toplist", "type": "top_list", "position": {"x": 0, "y": 4, "w": 8, "h": 4}},
            {"id": "industry", "type": "industry_flow", "position": {"x": 8, "y": 4, "w": 4, "h": 4}},
        ]
    },
    "investor": {
        "name": "投资者视图",
        "name_en": "Investor View",
        "description": "市场指数、板块涨跌、主力资金、自选股",
        "widgets": [
            {"id": "indices", "type": "market_indices", "position": {"x": 0, "y": 0, "w": 12, "h": 2}},
            {"id": "sectors", "type": "sector_performance", "position": {"x": 0, "y": 2, "w": 6, "h": 4}},
            {"id": "mainflow", "type": "main_capital_flow", "position": {"x": 6, "y": 2, "w": 6, "h": 4}},
            {"id": "watchlist", "type": "watchlist", "position": {"x": 0, "y": 6, "w": 12, "h": 4}},
        ]
    },
    "macro": {
        "name": "宏观视图",
        "name_en": "Macro View",
        "description": "市场指数、外汇汇率、黄金宏观、北向资金",
        "widgets": [
            {"id": "indices", "type": "market_indices", "position": {"x": 0, "y": 0, "w": 10, "h": 2}},
            {"id": "gold", "type": "gold_macro", "position": {"x": 10, "y": 0, "w": 2, "h": 2}},
            {"id": "forex", "type": "forex_rates", "position": {"x": 0, "y": 2, "w": 5, "h": 4}},
            {"id": "northbound", "type": "northbound_flow", "position": {"x": 5, "y": 2, "w": 7, "h": 4}},
        ]
    },
    "compact": {
        "name": "精简视图",
        "name_en": "Compact View",
        "description": "市场指数、市场情绪、主力资金",
        "widgets": [
            {"id": "indices", "type": "market_indices", "position": {"x": 0, "y": 0, "w": 12, "h": 2}},
            {"id": "sentiment", "type": "market_sentiment", "position": {"x": 0, "y": 2, "w": 6, "h": 3}},
            {"id": "mainflow", "type": "main_capital_flow", "position": {"x": 6, "y": 2, "w": 6, "h": 3}},
        ]
    },
}


@app.get("/api/dashboard/layouts")
async def get_dashboard_layouts(current_user: User = Depends(get_current_user)):
    """Get all dashboard layouts for the current user."""
    try:
        layouts = get_user_layouts(user_id=current_user.id)
        return {"layouts": layouts}
    except Exception as e:
        print(f"Error fetching layouts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/layouts/count")
async def get_dashboard_layout_count(current_user: User = Depends(get_current_user)):
    """Get the count of custom dashboard layouts for the current user."""
    try:
        layouts = get_user_layouts(user_id=current_user.id)
        count = len(layouts) if layouts else 0
        return {"count": count, "max": 3}
    except Exception as e:
        print(f"Error fetching layout count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/layouts/default")
async def get_default_dashboard_layout(current_user: User = Depends(get_current_user)):
    """Get the default dashboard layout for the current user."""
    try:
        layout = get_default_layout(user_id=current_user.id)
        if not layout:
            # Return the default preset if no custom layout
            return {"layout": None, "preset": "investor"}
        return {"layout": layout}
    except Exception as e:
        print(f"Error fetching default layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/layouts/{layout_id}")
async def get_dashboard_layout(layout_id: int, current_user: User = Depends(get_current_user)):
    """Get a specific dashboard layout."""
    try:
        layout = get_layout_by_id(layout_id, user_id=current_user.id)
        if not layout:
            raise HTTPException(status_code=404, detail="Layout not found")
        return layout
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dashboard/layouts")
async def create_dashboard_layout(
    layout_data: LayoutCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new dashboard layout."""
    try:
        # Check layout count limit (max 3 custom layouts)
        existing_layouts = get_user_layouts(user_id=current_user.id)
        if existing_layouts and len(existing_layouts) >= 3:
            raise HTTPException(
                status_code=400,
                detail="Maximum number of custom layouts (3) reached. Please delete an existing layout first."
            )

        layout_id = save_layout(
            user_id=current_user.id,
            name=layout_data.name,
            layout=layout_data.layout,
            is_default=layout_data.is_default
        )
        return {"id": layout_id, "message": "Layout created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/dashboard/layouts/{layout_id}")
async def update_dashboard_layout(
    layout_id: int,
    layout_data: LayoutUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update a dashboard layout."""
    try:
        updates = {}
        if layout_data.name is not None:
            updates['name'] = layout_data.name
        if layout_data.layout is not None:
            updates['layout'] = layout_data.layout
        if layout_data.is_default is not None:
            updates['is_default'] = layout_data.is_default

        success = update_layout(layout_id, user_id=current_user.id, updates=updates)
        if not success:
            raise HTTPException(status_code=404, detail="Layout not found")
        return {"message": "Layout updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/dashboard/layouts/{layout_id}")
async def delete_dashboard_layout(layout_id: int, current_user: User = Depends(get_current_user)):
    """Delete a dashboard layout."""
    try:
        success = delete_layout(layout_id, user_id=current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Layout not found")
        return {"message": "Layout deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dashboard/layouts/{layout_id}/set-default")
async def set_default_dashboard_layout(layout_id: int, current_user: User = Depends(get_current_user)):
    """Set a layout as the default."""
    try:
        success = set_default_layout(user_id=current_user.id, layout_id=layout_id)
        if not success:
            raise HTTPException(status_code=404, detail="Layout not found")
        return {"message": "Default layout set successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error setting default layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/presets")
async def get_dashboard_presets():
    """Get predefined dashboard layout presets."""
    return {"presets": DASHBOARD_PRESETS}


# ====================================================================
# News Center API
# ====================================================================

class NewsBookmarkRequest(BaseModel):
    """Request model for bookmarking news"""
    news_title: Optional[str] = None
    news_source: Optional[str] = None
    news_url: Optional[str] = None
    news_category: Optional[str] = None
    bookmarked: Optional[bool] = None  # If None, toggle


class NewsReadRequest(BaseModel):
    """Request model for marking news as read"""
    news_title: Optional[str] = None
    news_source: Optional[str] = None
    news_url: Optional[str] = None
    news_category: Optional[str] = None


@app.get("/api/news/feed")
async def get_news_feed(
    category: str = "all",
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user)
):
    """
    Get personalized news feed.

    Categories: all, flash (自选股快讯), fund (自选基金), announcement (公告),
                research (研报), hot (热门资讯)
    """
    try:
        data = await asyncio.to_thread(
            news_service.get_personalized_feed,
            user_id=current_user.id,
            category=category,
            page=page,
            page_size=page_size
        )
        return sanitize_for_json(data)
    except Exception as e:
        print(f"Error fetching news feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/{news_id}")
async def get_news_detail(
    news_id: str,
    title: str = "",
    content: str = "",
    current_user: User = Depends(get_current_user)
):
    """
    Get news detail with AI analysis.

    Pass title and content as query params for analysis if not cached.
    """
    try:
        # Mark as read
        await asyncio.to_thread(
            news_service.mark_read,
            user_id=current_user.id,
            news_id=news_id,
            news_title=title
        )

        # Get AI analysis
        analysis = await asyncio.to_thread(
            news_service.analyze_news,
            news_id=news_id,
            title=title,
            content=content
        )

        return sanitize_for_json({
            "news_id": news_id,
            "analysis": analysis,
            "is_read": True,
        })
    except Exception as e:
        print(f"Error fetching news detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/news/{news_id}/bookmark")
async def toggle_news_bookmark(
    news_id: str,
    request: NewsBookmarkRequest,
    current_user: User = Depends(get_current_user)
):
    """Toggle or set bookmark status for a news item."""
    try:
        if request.bookmarked is not None:
            # Set explicit bookmark state
            await asyncio.to_thread(
                news_service.set_bookmark,
                user_id=current_user.id,
                news_id=news_id,
                bookmarked=request.bookmarked,
                news_title=request.news_title,
                news_source=request.news_source,
                news_url=request.news_url,
                news_category=request.news_category
            )
            return {"bookmarked": request.bookmarked}
        else:
            # Toggle
            new_state = await asyncio.to_thread(
                news_service.toggle_bookmark,
                user_id=current_user.id,
                news_id=news_id,
                news_title=request.news_title,
                news_source=request.news_source,
                news_url=request.news_url,
                news_category=request.news_category
            )
            return {"bookmarked": new_state}
    except Exception as e:
        print(f"Error toggling bookmark: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/news/{news_id}/read")
async def mark_news_read(
    news_id: str,
    request: NewsReadRequest,
    current_user: User = Depends(get_current_user)
):
    """Mark a news item as read."""
    try:
        await asyncio.to_thread(
            news_service.mark_read,
            user_id=current_user.id,
            news_id=news_id,
            news_title=request.news_title,
            news_source=request.news_source,
            news_url=request.news_url,
            news_category=request.news_category
        )
        return {"success": True, "is_read": True}
    except Exception as e:
        print(f"Error marking news as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/bookmarks")
async def get_news_bookmarks(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Get user's bookmarked news."""
    try:
        bookmarks = await asyncio.to_thread(
            news_service.get_bookmarks,
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        return {"bookmarks": bookmarks, "total": len(bookmarks)}
    except Exception as e:
        print(f"Error fetching bookmarks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/watchlist-summary")
async def get_news_watchlist_summary(current_user: User = Depends(get_current_user)):
    """Get a summary of news related to user's watchlist."""
    try:
        summary = await asyncio.to_thread(
            news_service.get_watchlist_news_summary,
            user_id=current_user.id
        )
        return sanitize_for_json(summary)
    except Exception as e:
        print(f"Error fetching watchlist summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/announcements")
async def get_news_announcements(
    stock_code: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """Get company announcements."""
    try:
        announcements = await asyncio.to_thread(
            news_service.get_announcements,
            stock_code=stock_code,
            limit=limit
        )
        return {"announcements": announcements, "total": len(announcements)}
    except Exception as e:
        print(f"Error fetching announcements: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/research")
async def search_news_research(
    query: str,
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    """Search for research reports via Tavily."""
    try:
        results = await asyncio.to_thread(
            news_service.search_research_reports,
            query=query,
            limit=limit
        )
        return {"results": results, "total": len(results)}
    except Exception as e:
        print(f"Error searching research: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/hot")
async def get_hot_news(limit: int = 30):
    """Get hot/trending news (no auth required for public display)."""
    try:
        news = await asyncio.to_thread(
            news_service.get_hot_news,
            limit=limit
        )
        return {"news": news, "total": len(news)}
    except Exception as e:
        print(f"Error fetching hot news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# AI Assistant API
# ====================================================================

class AssistantChatRequest(BaseModel):
    """Request model for assistant chat."""
    message: str
    context: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, str]]] = None


class AssistantSource(BaseModel):
    """Source item in assistant response."""
    title: str
    url: Optional[str] = None
    source: Optional[str] = None
    type: Optional[str] = None


class AssistantChatResponse(BaseModel):
    """Response model for assistant chat."""
    response: str
    sources: List[AssistantSource] = []
    context_used: Dict[str, Any] = {}
    suggested_questions: Optional[List[str]] = None


@app.post("/api/assistant/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    request: AssistantChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Chat with AI assistant.

    The assistant is context-aware and can:
    - Understand current page context (stocks, funds, news)
    - Search for relevant news and information
    - Provide RAG-enhanced responses
    """
    try:
        context = request.context or {}
        history = request.history or []

        # Call assistant service
        result = await asyncio.to_thread(
            assistant_service.chat,
            message=request.message,
            context=context,
            history=history,
            user_id=current_user.id
        )

        # Get suggested questions for follow-up
        suggestions = assistant_service.get_suggested_questions(context)

        return AssistantChatResponse(
            response=result.get("response", ""),
            sources=[AssistantSource(**s) for s in result.get("sources", [])],
            context_used=result.get("context_used", {}),
            suggested_questions=suggestions
        )
    except Exception as e:
        print(f"Assistant chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/assistant/suggestions")
async def get_assistant_suggestions(
    page: Optional[str] = None,
    stock_code: Optional[str] = None,
    stock_name: Optional[str] = None,
    fund_code: Optional[str] = None,
    fund_name: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get suggested questions based on current context."""
    try:
        context = {"page": page or "dashboard"}
        if stock_code and stock_name:
            context["stock"] = {"code": stock_code, "name": stock_name}
        if fund_code and fund_name:
            context["fund"] = {"code": fund_code, "name": fund_name}

        suggestions = assistant_service.get_suggested_questions(context)
        return {"suggestions": suggestions}
    except Exception as e:
        print(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# Fund Analysis API - Diagnosis, Risk Metrics, Comparison
# ====================================================================

class FundCompareRequest(BaseModel):
    codes: List[str]


class PositionCreate(BaseModel):
    fund_code: str
    fund_name: Optional[str] = None
    shares: float
    cost_basis: float
    purchase_date: str
    notes: Optional[str] = None


class PositionUpdate(BaseModel):
    fund_name: Optional[str] = None
    shares: Optional[float] = None
    cost_basis: Optional[float] = None
    purchase_date: Optional[str] = None
    notes: Optional[str] = None


# ====================================================================
# Portfolio Management Models (New Multi-Portfolio System)
# ====================================================================

class PortfolioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    benchmark_code: Optional[str] = "000300.SH"
    is_default: Optional[bool] = False


class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    benchmark_code: Optional[str] = None
    is_default: Optional[bool] = None


class UnifiedPositionCreate(BaseModel):
    asset_type: str  # 'stock' or 'fund'
    asset_code: str
    asset_name: Optional[str] = None
    total_shares: float
    average_cost: float
    sector: Optional[str] = None
    notes: Optional[str] = None


class UnifiedPositionUpdate(BaseModel):
    asset_name: Optional[str] = None
    total_shares: Optional[float] = None
    average_cost: Optional[float] = None
    sector: Optional[str] = None
    notes: Optional[str] = None


class TransactionCreate(BaseModel):
    asset_type: str  # 'stock' or 'fund'
    asset_code: str
    asset_name: Optional[str] = None
    transaction_type: str  # 'buy', 'sell', 'dividend', 'split', 'transfer_in', 'transfer_out'
    shares: float
    price: float
    total_amount: Optional[float] = None
    fees: Optional[float] = 0
    transaction_date: str
    notes: Optional[str] = None


class DIPPlanCreate(BaseModel):
    asset_type: str  # 'stock' or 'fund'
    asset_code: str
    asset_name: Optional[str] = None
    amount_per_period: float
    frequency: str  # 'daily', 'weekly', 'biweekly', 'monthly'
    execution_day: Optional[int] = None
    start_date: str
    end_date: Optional[str] = None
    is_active: Optional[bool] = True
    notes: Optional[str] = None


class DIPPlanUpdate(BaseModel):
    asset_name: Optional[str] = None
    amount_per_period: Optional[float] = None
    frequency: Optional[str] = None
    execution_day: Optional[int] = None
    end_date: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class AlertMarkReadRequest(BaseModel):
    alert_id: int


class AIRebalanceRequest(BaseModel):
    target_allocation: Optional[Dict[str, float]] = None
    risk_preference: Optional[str] = "moderate"  # conservative, moderate, aggressive


class PortfolioAIChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


@app.get("/api/funds/{code}/diagnosis")
async def get_fund_diagnosis(
    code: str,
    force_refresh: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Get fund diagnosis with five-dimension scoring and radar chart data."""
    try:
        # Check cache first
        if not force_refresh:
            cached = get_diagnosis_cache(code)
            if cached and cached.get('diagnosis'):
                return cached['diagnosis']

        # Fetch NAV history
        loop = asyncio.get_running_loop()
        nav_history = await loop.run_in_executor(None, _get_fund_nav_history, code, 500)

        if not nav_history:
            raise HTTPException(status_code=404, detail=f"No NAV history found for fund {code}")

        # Calculate diagnosis
        diagnoser = FundDiagnosis()
        diagnosis = diagnoser.diagnose(code, nav_history)

        # Cache result (6 hours TTL)
        if diagnosis.get('score', 0) > 0:
            save_diagnosis_cache(code, diagnosis, int(diagnosis['score']), ttl_hours=6)

        return sanitize_for_json(diagnosis)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error calculating fund diagnosis for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/funds/{code}/risk-metrics")
async def get_fund_risk_metrics(
    code: str,
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive risk metrics for a fund."""
    try:
        # Fetch NAV history
        loop = asyncio.get_running_loop()
        nav_history = await loop.run_in_executor(None, _get_fund_nav_history, code, 500)

        if not nav_history:
            raise HTTPException(status_code=404, detail=f"No NAV history found for fund {code}")

        # Calculate risk metrics
        calculator = RiskMetricsCalculator()
        metrics = calculator.calculate_all_metrics(nav_history)

        return sanitize_for_json(metrics)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error calculating risk metrics for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/funds/{code}/drawdown-history")
async def get_fund_drawdown_history(
    code: str,
    threshold: float = 0.05,
    current_user: User = Depends(get_current_user)
):
    """Get detailed drawdown history analysis for a fund."""
    try:
        # Fetch NAV history
        loop = asyncio.get_running_loop()
        nav_history = await loop.run_in_executor(None, _get_fund_nav_history, code, 500)

        if not nav_history:
            raise HTTPException(status_code=404, detail=f"No NAV history found for fund {code}")

        # Analyze drawdowns
        analyzer = DrawdownAnalyzer(threshold=threshold)
        analysis = analyzer.analyze_drawdowns(nav_history)

        return sanitize_for_json(analysis)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error analyzing drawdowns for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/funds/compare")
async def compare_funds_advanced(
    request: FundCompareRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Compare multiple funds (up to 10) with comprehensive analysis.
    Includes NAV curves, returns, risk metrics, and holdings overlap.
    """
    try:
        codes = request.codes

        if len(codes) < 2:
            raise HTTPException(status_code=400, detail="Please select at least 2 funds to compare")
        if len(codes) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 funds allowed for comparison")

        # Fetch NAV history for all funds in parallel
        loop = asyncio.get_running_loop()

        async def fetch_fund_data(code: str):
            nav_history = await loop.run_in_executor(None, _get_fund_nav_history, code, 500)
            fund_info = await loop.run_in_executor(None, _get_fund_basic_info, code)
            holdings = await loop.run_in_executor(None, _get_fund_holdings_list, code)
            return {
                'code': code,
                'name': fund_info.get('name', code) if fund_info else code,
                'nav_history': nav_history,
                'holdings': holdings,
            }

        tasks = [fetch_fund_data(code) for code in codes]
        funds_data = await asyncio.gather(*tasks)

        # Filter out funds with insufficient data
        valid_funds = [f for f in funds_data if f.get('nav_history') and len(f['nav_history']) >= 20]

        if len(valid_funds) < 2:
            raise HTTPException(status_code=400, detail="Not enough funds with valid data for comparison")

        # Perform comparison
        comparator = FundComparison()
        result = comparator.compare(valid_funds)

        return sanitize_for_json(result)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error comparing funds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# Portfolio Management API - Positions CRUD
# ====================================================================

@app.get("/api/portfolio/positions")
async def get_positions(
    current_user: User = Depends(get_current_user)
):
    """Get all fund positions for current user."""
    try:
        positions = get_user_positions(current_user.id)

        # Enrich with current NAV and P&L
        enriched = []
        for pos in positions:
            fund_code = pos['fund_code']

            # Try to get current NAV
            current_nav = None
            try:
                loop = asyncio.get_running_loop()
                nav_history = await loop.run_in_executor(None, _get_fund_nav_history, fund_code, 5)
                if nav_history:
                    current_nav = float(nav_history[-1]['value'])
            except:
                pass

            # Calculate P&L
            shares = float(pos.get('shares', 0))
            cost_basis = float(pos.get('cost_basis', 0))

            position_cost = shares * cost_basis
            position_value = shares * (current_nav or cost_basis)
            pnl = position_value - position_cost
            pnl_pct = (current_nav / cost_basis - 1) * 100 if cost_basis > 0 and current_nav else 0

            enriched.append({
                **pos,
                'current_nav': round(current_nav, 4) if current_nav else None,
                'position_cost': round(position_cost, 2),
                'position_value': round(position_value, 2),
                'pnl': round(pnl, 2),
                'pnl_pct': round(pnl_pct, 2),
            })

        return {"positions": enriched}
    except Exception as e:
        print(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio/positions")
async def create_new_position(
    position: PositionCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new fund position."""
    try:
        position_id = create_position(position.dict(), current_user.id)
        return {"id": position_id, "message": "Position created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error creating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/portfolio/positions/{position_id}")
async def update_existing_position(
    position_id: int,
    updates: PositionUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update an existing position."""
    try:
        # Filter out None values
        update_dict = {k: v for k, v in updates.dict().items() if v is not None}

        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        success = update_position(position_id, current_user.id, update_dict)
        if not success:
            raise HTTPException(status_code=404, detail="Position not found")

        return {"message": "Position updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/portfolio/positions/{position_id}")
async def delete_existing_position(
    position_id: int,
    current_user: User = Depends(get_current_user)
):
    """Delete a position."""
    try:
        success = delete_position(position_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Position not found")

        return {"message": "Position deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/summary")
async def get_portfolio_summary_api(
    current_user: User = Depends(get_current_user)
):
    """Get portfolio summary with total value, P&L, and allocation."""
    try:
        positions = get_user_positions(current_user.id)

        if not positions:
            return {
                "total_value": 0,
                "total_cost": 0,
                "total_pnl": 0,
                "total_pnl_pct": 0,
                "positions": [],
                "allocation": [],
            }

        # Build NAV map
        fund_nav_map = {}
        loop = asyncio.get_running_loop()

        for pos in positions:
            fund_code = pos['fund_code']
            if fund_code not in fund_nav_map:
                try:
                    nav_history = await loop.run_in_executor(None, _get_fund_nav_history, fund_code, 5)
                    if nav_history:
                        fund_nav_map[fund_code] = float(nav_history[-1]['value'])
                except:
                    pass

        # Calculate summary
        analyzer = PortfolioAnalyzer()
        summary = analyzer.calculate_portfolio_summary(positions, fund_nav_map)

        return sanitize_for_json(summary)
    except Exception as e:
        print(f"Error getting portfolio summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/overlap")
async def get_portfolio_overlap(
    current_user: User = Depends(get_current_user)
):
    """Analyze holdings overlap across portfolio funds."""
    try:
        positions = get_user_positions(current_user.id)

        if not positions:
            return {"message": "No positions in portfolio"}

        # Get holdings for each fund
        fund_holdings = {}
        position_weights = {}
        loop = asyncio.get_running_loop()

        # First, calculate total portfolio value for weights
        total_value = 0
        fund_values = {}
        fund_nav_map = {}

        for pos in positions:
            fund_code = pos['fund_code']
            shares = float(pos.get('shares', 0))
            cost_basis = float(pos.get('cost_basis', 1))

            # Get current NAV
            try:
                nav_history = await loop.run_in_executor(None, _get_fund_nav_history, fund_code, 5)
                if nav_history:
                    current_nav = float(nav_history[-1]['value'])
                    fund_nav_map[fund_code] = current_nav
                else:
                    current_nav = cost_basis
            except:
                current_nav = cost_basis

            position_value = shares * current_nav
            fund_values[fund_code] = fund_values.get(fund_code, 0) + position_value
            total_value += position_value

        # Calculate weights and fetch holdings
        for fund_code, value in fund_values.items():
            position_weights[fund_code] = value / total_value if total_value > 0 else 0

            try:
                holdings = await loop.run_in_executor(None, _get_fund_holdings_list, fund_code)
                if holdings:
                    fund_holdings[fund_code] = holdings
            except:
                pass

        if not fund_holdings:
            return {"message": "No holdings data available for portfolio funds"}

        # Analyze overlap
        analyzer = PortfolioAnalyzer()
        overlap = analyzer.analyze_holdings_overlap(fund_holdings, position_weights)

        return sanitize_for_json(overlap)
    except Exception as e:
        print(f"Error analyzing portfolio overlap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# New Multi-Portfolio Management API
# ====================================================================

@app.get("/api/portfolios")
async def list_portfolios(
    current_user: User = Depends(get_current_user)
):
    """Get all portfolios for the current user."""
    try:
        portfolios = get_user_portfolios(current_user.id)
        return {"portfolios": portfolios}
    except Exception as e:
        print(f"Error listing portfolios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolios")
async def create_new_portfolio(
    portfolio: PortfolioCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new portfolio."""
    try:
        portfolio_id = create_portfolio(portfolio.dict(), current_user.id)
        return {"id": portfolio_id, "message": "Portfolio created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error creating portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolios/default")
async def get_user_default_portfolio(
    current_user: User = Depends(get_current_user)
):
    """Get the default portfolio for the current user (creates one if needed)."""
    try:
        portfolio = get_default_portfolio(current_user.id)
        return portfolio
    except Exception as e:
        print(f"Error getting default portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolios/{portfolio_id}")
async def get_portfolio(
    portfolio_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get a specific portfolio by ID."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return portfolio
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/portfolios/{portfolio_id}")
async def update_existing_portfolio(
    portfolio_id: int,
    updates: PortfolioUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update an existing portfolio."""
    try:
        update_dict = {k: v for k, v in updates.dict().items() if v is not None}
        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        success = update_portfolio(portfolio_id, current_user.id, update_dict)
        if not success:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        return {"message": "Portfolio updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/portfolios/{portfolio_id}")
async def delete_existing_portfolio(
    portfolio_id: int,
    current_user: User = Depends(get_current_user)
):
    """Delete a portfolio."""
    try:
        success = delete_portfolio(portfolio_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        return {"message": "Portfolio deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolios/{portfolio_id}/set-default")
async def set_portfolio_as_default(
    portfolio_id: int,
    current_user: User = Depends(get_current_user)
):
    """Set a portfolio as the default."""
    try:
        success = db_set_default_portfolio(current_user.id, portfolio_id)
        if not success:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        return {"message": "Portfolio set as default"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error setting default portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# Unified Positions API (Stocks + Funds)
# ====================================================================

@app.get("/api/portfolios/{portfolio_id}/positions")
async def get_portfolio_positions_api(
    portfolio_id: int,
    asset_type: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get all positions for a portfolio."""
    try:
        # Verify portfolio ownership
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = get_portfolio_positions(portfolio_id, current_user.id, asset_type)

        # Enrich positions with real-time prices
        enriched = await _enrich_positions_with_prices(positions)

        return {"positions": enriched, "portfolio": portfolio}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting portfolio positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _enrich_positions_with_prices(positions: List[Dict]) -> List[Dict]:
    """Enrich positions with current market prices."""
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
                nav_history = await loop.run_in_executor(None, _get_fund_nav_history, asset_code, 5)
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


@app.post("/api/portfolios/{portfolio_id}/positions")
async def create_portfolio_position(
    portfolio_id: int,
    position: UnifiedPositionCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new position directly (without transaction)."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        position_data = position.dict()
        position_data['total_cost'] = position_data['total_shares'] * position_data['average_cost']

        position_id = upsert_position(position_data, portfolio_id, current_user.id)
        return {"id": position_id, "message": "Position created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/portfolios/{portfolio_id}/positions/{position_id}")
async def delete_portfolio_position(
    portfolio_id: int,
    position_id: int,
    current_user: User = Depends(get_current_user)
):
    """Delete a position."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        success = delete_unified_position(position_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Position not found")

        return {"message": "Position deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# Transactions API
# ====================================================================

@app.get("/api/portfolios/{portfolio_id}/transactions")
async def get_portfolio_transactions_api(
    portfolio_id: int,
    asset_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Get all transactions for a portfolio."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        transactions = get_portfolio_transactions(portfolio_id, current_user.id, asset_type, limit, offset)
        return {"transactions": transactions, "portfolio": portfolio}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolios/{portfolio_id}/transactions")
async def create_portfolio_transaction(
    portfolio_id: int,
    transaction: TransactionCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new transaction and update position."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        transaction_id = create_transaction(transaction.dict(), portfolio_id, current_user.id)
        return {"id": transaction_id, "message": "Transaction created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/portfolios/{portfolio_id}/transactions/{transaction_id}")
async def delete_portfolio_transaction(
    portfolio_id: int,
    transaction_id: int,
    current_user: User = Depends(get_current_user)
):
    """Delete a transaction (does not reverse position changes)."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        success = delete_transaction(transaction_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Transaction not found")

        return {"message": "Transaction deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolios/{portfolio_id}/positions/{position_id}/recalculate")
async def recalculate_portfolio_position(
    portfolio_id: int,
    position_id: int,
    current_user: User = Depends(get_current_user)
):
    """Recalculate a position from all its transactions."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        position = get_unified_position_by_id(position_id, current_user.id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")

        updated = recalculate_position(
            portfolio_id, position['asset_type'], position['asset_code'], current_user.id
        )
        return {"position": updated, "message": "Position recalculated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error recalculating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# Portfolio Analysis API
# ====================================================================

@app.get("/api/portfolios/{portfolio_id}/summary")
async def get_portfolio_summary_new(
    portfolio_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive portfolio summary with total value, P&L, and allocation."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = get_portfolio_positions(portfolio_id, current_user.id)

        if not positions:
            return {
                "portfolio": portfolio,
                "total_value": 0,
                "total_cost": 0,
                "total_pnl": 0,
                "total_pnl_pct": 0,
                "positions_count": 0,
                "positions": [],
                "allocation": {"by_type": {}, "by_sector": {}},
            }

        # Enrich positions with prices
        enriched_positions = await _enrich_positions_with_prices(positions)

        # Calculate summary
        total_cost = sum(float(p.get('total_shares', 0) * p.get('average_cost', 0)) for p in enriched_positions)
        total_value = sum(float(p.get('current_value') or p.get('total_shares', 0) * p.get('average_cost', 0)) for p in enriched_positions)
        total_pnl = total_value - total_cost
        total_pnl_pct = ((total_value / total_cost) - 1) * 100 if total_cost > 0 else 0

        # Calculate allocation
        allocation_by_type = {'stock': 0, 'fund': 0}
        allocation_by_sector = {}

        for pos in enriched_positions:
            pos_value = pos.get('current_value') or (pos.get('total_shares', 0) * pos.get('average_cost', 0))
            asset_type = pos.get('asset_type', 'fund')
            sector = pos.get('sector', '未分类')

            allocation_by_type[asset_type] = allocation_by_type.get(asset_type, 0) + pos_value
            allocation_by_sector[sector] = allocation_by_sector.get(sector, 0) + pos_value

        # Convert to percentages
        if total_value > 0:
            allocation_by_type = {k: round(v / total_value * 100, 2) for k, v in allocation_by_type.items()}
            allocation_by_sector = {k: round(v / total_value * 100, 2) for k, v in allocation_by_sector.items()}

        return sanitize_for_json({
            "portfolio": portfolio,
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "positions_count": len(enriched_positions),
            "positions": enriched_positions,
            "allocation": {
                "by_type": allocation_by_type,
                "by_sector": allocation_by_sector,
            },
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting portfolio summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolios/{portfolio_id}/performance")
async def get_portfolio_performance(
    portfolio_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get portfolio performance history (snapshots)."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        snapshots = get_portfolio_snapshots(portfolio_id, start_date, end_date)

        return sanitize_for_json({
            "portfolio": portfolio,
            "snapshots": snapshots,
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting portfolio performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolios/{portfolio_id}/risk-metrics")
async def get_portfolio_risk_metrics_api(
    portfolio_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get portfolio risk metrics including concentration, volatility, etc."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = get_portfolio_positions(portfolio_id, current_user.id)
        enriched = await _enrich_positions_with_prices(positions)

        if not enriched:
            return {"message": "No positions to analyze"}

        # Calculate risk metrics
        total_value = sum(float(p.get('current_value') or p.get('total_shares', 0) * p.get('average_cost', 0)) for p in enriched)

        # Concentration risk
        max_position_pct = 0
        position_values = []
        for pos in enriched:
            pos_value = pos.get('current_value') or (pos.get('total_shares', 0) * pos.get('average_cost', 0))
            pos_pct = (pos_value / total_value * 100) if total_value > 0 else 0
            position_values.append(pos_pct)
            max_position_pct = max(max_position_pct, pos_pct)

        # Herfindahl-Hirschman Index (HHI)
        hhi = sum(pct ** 2 for pct in position_values)
        concentration_level = "低" if hhi < 1500 else ("中" if hhi < 2500 else "高")

        # Diversification score (inverse of HHI, normalized)
        diversification_score = max(0, min(100, 100 - (hhi / 100)))

        # Type concentration
        type_concentration = {}
        for pos in enriched:
            pos_value = pos.get('current_value') or (pos.get('total_shares', 0) * pos.get('average_cost', 0))
            asset_type = pos.get('asset_type', 'fund')
            type_concentration[asset_type] = type_concentration.get(asset_type, 0) + pos_value

        type_concentration = {k: round(v / total_value * 100, 2) for k, v in type_concentration.items()} if total_value > 0 else {}

        return sanitize_for_json({
            "portfolio": portfolio,
            "risk_metrics": {
                "max_single_position_pct": round(max_position_pct, 2),
                "hhi": round(hhi, 2),
                "concentration_level": concentration_level,
                "diversification_score": round(diversification_score, 2),
                "type_concentration": type_concentration,
                "positions_count": len(enriched),
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting portfolio risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolios/{portfolio_id}/benchmark")
async def get_portfolio_benchmark_comparison(
    portfolio_id: int,
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """Compare portfolio performance against benchmark index."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        benchmark_code = portfolio.get('benchmark_code', '000300.SH')

        # Get benchmark data
        loop = asyncio.get_running_loop()
        try:
            benchmark_history = await loop.run_in_executor(
                None, _get_index_history, benchmark_code, days
            )
        except:
            benchmark_history = []

        # Get portfolio snapshots
        snapshots = get_portfolio_snapshots(portfolio_id, limit=days)

        return sanitize_for_json({
            "portfolio": portfolio,
            "benchmark_code": benchmark_code,
            "benchmark_history": benchmark_history,
            "portfolio_history": snapshots,
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting benchmark comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_index_history(index_code: str, days: int = 30) -> List[Dict]:
    """Get index price history."""
    try:
        # Map common index codes
        ak_code = index_code.replace('.SH', '').replace('.SZ', '')
        df = ak.stock_zh_index_daily_em(symbol=f"sh{ak_code}" if 'SH' in index_code else f"sz{ak_code}")

        if df is None or df.empty:
            return []

        df = df.tail(days)
        return [
            {'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
             'close': float(row['close'])}
            for _, row in df.iterrows()
        ]
    except Exception as e:
        print(f"Error fetching index history for {index_code}: {e}")
        return []


# ====================================================================
# Portfolio Alerts API
# ====================================================================

@app.get("/api/portfolios/{portfolio_id}/alerts")
async def get_portfolio_alerts_api(
    portfolio_id: int,
    unread_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get alerts for a portfolio."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        alerts = get_portfolio_alerts(portfolio_id, current_user.id, unread_only, limit)
        unread_count = get_unread_alert_count(current_user.id)

        return {
            "alerts": alerts,
            "unread_count": unread_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts")
async def get_all_user_alerts(
    unread_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get all alerts for the current user across all portfolios."""
    try:
        alerts = get_portfolio_alerts(None, current_user.id, unread_only, limit)
        unread_count = get_unread_alert_count(current_user.id)

        return {
            "alerts": alerts,
            "unread_count": unread_count,
        }
    except Exception as e:
        print(f"Error getting user alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/alerts/{alert_id}/read")
async def mark_alert_as_read(
    alert_id: int,
    current_user: User = Depends(get_current_user)
):
    """Mark an alert as read."""
    try:
        success = mark_alert_read(alert_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")

        return {"message": "Alert marked as read"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error marking alert as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/alerts/{alert_id}/dismiss")
async def dismiss_alert_api(
    alert_id: int,
    current_user: User = Depends(get_current_user)
):
    """Dismiss an alert."""
    try:
        success = dismiss_alert(alert_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")

        return {"message": "Alert dismissed"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error dismissing alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# AI Portfolio Features
# ====================================================================

@app.get("/api/portfolios/{portfolio_id}/ai-diagnosis")
async def get_ai_portfolio_diagnosis(
    portfolio_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get AI-powered portfolio diagnosis with 5-dimension scoring."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = get_portfolio_positions(portfolio_id, current_user.id)
        enriched = await _enrich_positions_with_prices(positions)

        if not enriched:
            return {"message": "No positions to diagnose"}

        # Calculate 5-dimension scores
        total_value = sum(float(p.get('current_value') or p.get('total_shares', 0) * p.get('average_cost', 0)) for p in enriched)

        # 1. Diversification Score (20 points max)
        position_weights = []
        for pos in enriched:
            pos_value = pos.get('current_value') or (pos.get('total_shares', 0) * pos.get('average_cost', 0))
            weight = pos_value / total_value if total_value > 0 else 0
            position_weights.append(weight)

        hhi = sum(w ** 2 for w in position_weights) * 10000  # Scale to traditional HHI
        diversification_score = max(0, min(20, 20 - (hhi / 500)))  # Lower HHI = higher score

        # 2. Risk Efficiency Score (20 points max) - Based on P&L volatility
        pnl_pcts = [p.get('unrealized_pnl_pct', 0) or 0 for p in enriched]
        avg_pnl = sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0
        # Simple scoring based on average performance
        risk_efficiency_score = max(0, min(20, 10 + (avg_pnl / 10)))

        # 3. Allocation Quality Score (20 points max)
        type_counts = {'stock': 0, 'fund': 0}
        for pos in enriched:
            pos_value = pos.get('current_value') or (pos.get('total_shares', 0) * pos.get('average_cost', 0))
            type_counts[pos.get('asset_type', 'fund')] += pos_value

        # Balanced allocation gets higher score
        total = sum(type_counts.values())
        if total > 0:
            balance_ratio = min(type_counts.values()) / max(type_counts.values()) if max(type_counts.values()) > 0 else 0
            allocation_score = 10 + (balance_ratio * 10)  # 10-20 points
        else:
            allocation_score = 10

        # 4. Momentum Score (20 points max)
        positive_positions = sum(1 for p in pnl_pcts if p > 0)
        momentum_score = (positive_positions / len(pnl_pcts)) * 20 if pnl_pcts else 10

        # 5. Valuation Score (20 points max) - Simplified
        # We'd need P/E data for proper valuation, for now use average cost vs current price
        valuation_ratios = []
        for pos in enriched:
            avg_cost = pos.get('average_cost', 1)
            current_price = pos.get('current_price', avg_cost)
            if avg_cost > 0 and current_price:
                ratio = current_price / avg_cost
                valuation_ratios.append(ratio)

        avg_ratio = sum(valuation_ratios) / len(valuation_ratios) if valuation_ratios else 1
        # Ratio > 1.5 might be overvalued, < 0.8 might be oversold
        if avg_ratio > 1.5:
            valuation_score = max(5, 15 - (avg_ratio - 1.5) * 10)
        elif avg_ratio < 0.8:
            valuation_score = max(5, 15 - (0.8 - avg_ratio) * 10)
        else:
            valuation_score = 15 + abs(1 - avg_ratio) * 10

        valuation_score = max(0, min(20, valuation_score))

        total_score = diversification_score + risk_efficiency_score + allocation_score + momentum_score + valuation_score

        # Generate recommendations
        recommendations = []
        if diversification_score < 12:
            recommendations.append("建议增加持仓多样性，当前集中度较高")
        if risk_efficiency_score < 10:
            recommendations.append("组合整体收益偏低，考虑调整持仓结构")
        if allocation_score < 12:
            recommendations.append("资产配置不够均衡，建议增加股票/基金比例")
        if momentum_score < 10:
            recommendations.append("多数持仓处于亏损状态，建议审视持仓策略")
        if valuation_score < 12:
            recommendations.append("部分持仓估值偏离合理区间")

        return sanitize_for_json({
            "portfolio": portfolio,
            "total_score": round(total_score, 1),
            "max_score": 100,
            "grade": "A" if total_score >= 80 else ("B" if total_score >= 60 else ("C" if total_score >= 40 else "D")),
            "dimensions": [
                {"name": "分散化", "score": round(diversification_score, 1), "max": 20},
                {"name": "风险效率", "score": round(risk_efficiency_score, 1), "max": 20},
                {"name": "配置质量", "score": round(allocation_score, 1), "max": 20},
                {"name": "动量", "score": round(momentum_score, 1), "max": 20},
                {"name": "估值", "score": round(valuation_score, 1), "max": 20},
            ],
            "recommendations": recommendations,
            "analyzed_at": datetime.now().isoformat(),
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating AI diagnosis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolios/{portfolio_id}/ai-rebalance")
async def get_ai_rebalance_suggestions(
    portfolio_id: int,
    request: AIRebalanceRequest = Body(default=AIRebalanceRequest()),
    current_user: User = Depends(get_current_user)
):
    """Get AI-powered rebalancing suggestions."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = get_portfolio_positions(portfolio_id, current_user.id)
        enriched = await _enrich_positions_with_prices(positions)

        if not enriched:
            return {"message": "No positions to analyze"}

        total_value = sum(float(p.get('current_value') or p.get('total_shares', 0) * p.get('average_cost', 0)) for p in enriched)

        suggestions = []

        # Analyze each position
        for pos in enriched:
            pos_value = pos.get('current_value') or (pos.get('total_shares', 0) * pos.get('average_cost', 0))
            weight = (pos_value / total_value * 100) if total_value > 0 else 0
            pnl_pct = pos.get('unrealized_pnl_pct', 0) or 0

            # Concentration check
            if weight > 30:
                suggestions.append({
                    "asset_code": pos['asset_code'],
                    "asset_name": pos.get('asset_name', pos['asset_code']),
                    "action": "reduce",
                    "reason": f"仓位占比{weight:.1f}%过高，建议减仓至30%以下",
                    "priority": "high",
                })

            # Loss cutting check
            if pnl_pct < -20:
                suggestions.append({
                    "asset_code": pos['asset_code'],
                    "asset_name": pos.get('asset_name', pos['asset_code']),
                    "action": "review",
                    "reason": f"亏损{abs(pnl_pct):.1f}%，建议审视是否止损",
                    "priority": "medium",
                })

            # Profit taking check
            if pnl_pct > 50:
                suggestions.append({
                    "asset_code": pos['asset_code'],
                    "asset_name": pos.get('asset_name', pos['asset_code']),
                    "action": "consider_reduce",
                    "reason": f"盈利{pnl_pct:.1f}%，可考虑部分止盈",
                    "priority": "low",
                })

        # Type balance check
        type_values = {'stock': 0, 'fund': 0}
        for pos in enriched:
            pos_value = pos.get('current_value') or (pos.get('total_shares', 0) * pos.get('average_cost', 0))
            type_values[pos.get('asset_type', 'fund')] += pos_value

        stock_pct = (type_values['stock'] / total_value * 100) if total_value > 0 else 0
        fund_pct = (type_values['fund'] / total_value * 100) if total_value > 0 else 0

        # Suggest based on risk preference
        if request.risk_preference == "conservative":
            if stock_pct > 40:
                suggestions.append({
                    "asset_code": None,
                    "asset_name": "整体配置",
                    "action": "adjust",
                    "reason": f"股票占比{stock_pct:.1f}%偏高，保守型投资者建议控制在40%以下",
                    "priority": "medium",
                })
        elif request.risk_preference == "aggressive":
            if fund_pct > 60:
                suggestions.append({
                    "asset_code": None,
                    "asset_name": "整体配置",
                    "action": "adjust",
                    "reason": f"基金占比{fund_pct:.1f}%偏高，进取型投资者可增加股票比例",
                    "priority": "low",
                })

        return sanitize_for_json({
            "portfolio": portfolio,
            "current_allocation": {
                "stock": round(stock_pct, 2),
                "fund": round(fund_pct, 2),
            },
            "suggestions": suggestions,
            "generated_at": datetime.now().isoformat(),
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating rebalance suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolios/{portfolio_id}/ai-chat")
async def portfolio_ai_chat(
    portfolio_id: int,
    request: PortfolioAIChatRequest,
    current_user: User = Depends(get_current_user)
):
    """AI chat specifically about the portfolio."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = get_portfolio_positions(portfolio_id, current_user.id)
        enriched = await _enrich_positions_with_prices(positions)

        # Build portfolio context for AI
        total_value = sum(float(p.get('current_value') or p.get('total_shares', 0) * p.get('average_cost', 0)) for p in enriched)
        total_cost = sum(float(p.get('total_shares', 0) * p.get('average_cost', 0)) for p in enriched)
        total_pnl = total_value - total_cost

        portfolio_context = {
            "portfolio_name": portfolio.get('name', '我的组合'),
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round((total_pnl / total_cost * 100) if total_cost > 0 else 0, 2),
            "positions": [
                {
                    "name": p.get('asset_name', p['asset_code']),
                    "type": p['asset_type'],
                    "value": p.get('current_value'),
                    "pnl_pct": p.get('unrealized_pnl_pct'),
                }
                for p in enriched
            ],
        }

        # Use assistant service with portfolio context
        context = {
            "page": "portfolio",
            "portfolio": portfolio_context,
            **(request.context or {}),
        }

        response = await assistant_service.chat(
            message=request.message,
            context=context,
            history=[]  # Could add conversation history if needed
        )

        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in portfolio AI chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# Portfolio Stress Testing & Advanced Analytics API
# ====================================================================

class StressTestRequest(BaseModel):
    """Request model for stress test."""
    scenario: Optional[Dict[str, Any]] = None
    scenario_type: Optional[str] = None


@app.post("/api/portfolios/{portfolio_id}/stress-test")
async def run_portfolio_stress_test(
    portfolio_id: int,
    request: StressTestRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Run stress test on portfolio with macro factor scenarios.

    Can use predefined scenarios (scenario_type) or custom factors (scenario).
    """
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = get_portfolio_positions(portfolio_id, current_user.id)
        enriched = await _enrich_positions_with_prices(positions)

        if not enriched:
            return {"message": "No positions to analyze"}

        # Build current prices map
        current_prices = {}
        for pos in enriched:
            code = pos.get('asset_code')
            price = pos.get('current_price') or pos.get('average_cost', 0)
            current_prices[code] = float(price)

        # Initialize stress test engine
        engine = StressTestEngine()

        # Run stress test
        if request.scenario_type:
            # Use predefined scenario
            try:
                scenario_enum = ScenarioType(request.scenario_type)
                result = engine.run_predefined_scenario(
                    enriched, scenario_enum, current_prices
                )
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Unknown scenario type: {request.scenario_type}")
        elif request.scenario:
            # Use custom scenario
            scenario = StressScenario(
                interest_rate_change_bp=request.scenario.get('interest_rate_change_bp', 0),
                fx_change_pct=request.scenario.get('fx_change_pct', 0),
                index_change_pct=request.scenario.get('index_change_pct', 0),
                oil_change_pct=request.scenario.get('oil_change_pct', 0),
                sector_shocks=request.scenario.get('sector_shocks')
            )
            result = engine.run_stress_test(enriched, scenario, current_prices)
        else:
            # Default: market drop 5%
            scenario = StressScenario(index_change_pct=-5.0)
            result = engine.run_stress_test(enriched, scenario, current_prices)

        return sanitize_for_json(result)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error running stress test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolios/{portfolio_id}/stress-test/scenarios")
async def get_stress_test_scenarios(
    current_user: User = Depends(get_current_user)
):
    """Get available predefined stress test scenarios and factor sliders."""
    return {
        "scenarios": StressTestEngine.get_available_scenarios(),
        "sliders": StressTestEngine.get_factor_sliders()
    }


class AIScenarioRequest(BaseModel):
    """Request model for AI scenario generation."""
    category: str  # monetary_policy, currency, market, sector, commodity


@app.post("/api/portfolios/{portfolio_id}/stress-test/ai-scenarios")
async def generate_ai_stress_scenario(
    portfolio_id: int,
    request: AIScenarioRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate AI-powered stress test scenario based on current market conditions.

    Phase 1 of AI-enhanced stress testing:
    - Takes a category (monetary_policy, currency, market, sector, commodity)
    - Fetches real-time market data
    - Uses LLM to generate realistic scenario parameters
    - Returns scenario with AI reasoning
    """
    try:
        from src.services.ai_scenario_service import ai_scenario_service

        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Generate AI scenario
        result = await ai_scenario_service.generate_scenario(request.category)

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating AI scenario: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class StressTestChatRequest(BaseModel):
    """Request model for stress test chat."""
    message: str
    history: Optional[List[Dict[str, str]]] = None


@app.post("/api/portfolios/{portfolio_id}/stress-test/chat")
async def stress_test_chat(
    portfolio_id: int,
    request: StressTestChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Conversational stress testing interface.

    Phase 2 of AI-enhanced stress testing:
    - User asks questions like "What if rates rise 75bp?"
    - LLM parses intent and extracts parameters
    - Runs stress test if applicable
    - Returns AI interpretation of results
    """
    try:
        from src.services.ai_scenario_service import stress_test_chat_service

        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Get portfolio summary for context
        positions = get_portfolio_positions(portfolio_id, current_user.id)
        enriched = await _enrich_positions_with_prices(positions)

        total_value = sum(float(p.get('current_value') or 0) for p in enriched)
        total_cost = sum(float(p.get('total_cost') or 0) for p in enriched)
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        portfolio_summary = {
            "total_value": total_value,
            "total_cost": total_cost,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "position_count": len(enriched)
        }

        # Get chat response
        chat_result = await stress_test_chat_service.chat(
            message=request.message,
            portfolio_id=portfolio_id,
            portfolio_summary=portfolio_summary,
            history=request.history
        )

        # If chat suggests running stress test, run it
        stress_result = None
        if chat_result.get("should_run_stress_test") and chat_result.get("scenario_params"):
            try:
                # Build current prices map
                current_prices = {}
                for pos in enriched:
                    code = pos.get('asset_code')
                    price = pos.get('current_price') or pos.get('average_cost', 0)
                    current_prices[code] = float(price)

                # Run stress test with extracted parameters
                params = chat_result["scenario_params"]
                scenario = StressScenario(
                    interest_rate_change_bp=params.get('interest_rate_change_bp', 0),
                    fx_change_pct=params.get('fx_change_pct', 0),
                    index_change_pct=params.get('index_change_pct', 0),
                    oil_change_pct=params.get('oil_change_pct', 0)
                )

                engine = StressTestEngine()
                stress_result = engine.run_stress_test(enriched, scenario, current_prices)
                stress_result = sanitize_for_json(stress_result)
            except Exception as e:
                print(f"Stress test execution failed: {e}")

        return {
            "response": chat_result.get("response", ""),
            "stress_result": stress_result,
            "scenario_used": chat_result.get("scenario_params"),
            "suggested_followups": chat_result.get("suggested_followups", [])
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in stress test chat: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolios/{portfolio_id}/correlation")
async def get_portfolio_correlation(
    portfolio_id: int,
    days: int = 90,
    current_user: User = Depends(get_current_user)
):
    """Get correlation matrix for portfolio positions."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = get_portfolio_positions(portfolio_id, current_user.id)
        enriched = await _enrich_positions_with_prices(positions)

        if not enriched or len(enriched) < 2:
            return {"message": "Need at least 2 positions for correlation analysis"}

        # Get price histories for all positions
        loop = asyncio.get_running_loop()
        price_histories = {}

        for pos in enriched:
            code = pos.get('asset_code')
            asset_type = pos.get('asset_type')

            try:
                if asset_type == 'fund':
                    history = await loop.run_in_executor(
                        None, _get_fund_nav_history, code, days
                    )
                    if history:
                        price_histories[code] = [
                            {'date': h['date'], 'price': h['value']}
                            for h in history
                        ]
                else:  # stock
                    history = await loop.run_in_executor(
                        None, _get_stock_price_history, code, days
                    )
                    if history:
                        price_histories[code] = history
            except Exception as e:
                print(f"Error fetching history for {code}: {e}")

        # Calculate correlation matrix
        analyzer = CorrelationAnalyzer(lookback_days=days)
        result = analyzer.calculate_correlation_matrix(enriched, price_histories)

        return sanitize_for_json(result)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error calculating correlation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CorrelationExplainRequest(BaseModel):
    correlation_data: dict


@app.post("/api/portfolios/{portfolio_id}/correlation/explain")
async def explain_portfolio_correlation(
    portfolio_id: int,
    request: CorrelationExplainRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate AI explanation for portfolio correlation matrix."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        correlation_data = request.correlation_data

        # Build the prompt for LLM
        prompt = _build_correlation_explanation_prompt(correlation_data)

        # Get LLM explanation
        loop = asyncio.get_running_loop()
        llm_client = get_llm_client()
        explanation = await loop.run_in_executor(
            None, llm_client.generate_content, prompt
        )

        return {"explanation": explanation}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating correlation explanation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_correlation_explanation_prompt(correlation_data: dict) -> str:
    """Build prompt for explaining correlation matrix."""
    labels = correlation_data.get('labels', [])
    high_correlations = correlation_data.get('high_correlations', [])
    diversification_score = correlation_data.get('diversification_score', 0)
    diversification_status = correlation_data.get('diversification_status', 'unknown')

    # Format high correlation pairs
    high_corr_text = ""
    if high_correlations:
        pairs = []
        for hc in high_correlations[:5]:  # Limit to top 5
            pairs.append(f"- {hc.get('name_a', '')} 与 {hc.get('name_b', '')}: {hc.get('correlation', 0):.2f}")
        high_corr_text = "\n".join(pairs)
    else:
        high_corr_text = "无显著高相关性持仓对"

    prompt = f"""你是一位专业的投资组合分析师。请根据以下持仓相关性数据，用简洁易懂的语言向普通投资者解释：

## 持仓列表
{', '.join(labels) if labels else '暂无持仓'}

## 分散化评分
- 得分: {diversification_score:.0f}/100
- 状态: {diversification_status}

## 高相关性持仓对
{high_corr_text}

请用2-3句话解释：
1. 这个组合的分散化程度如何？
2. 如果有高相关性的持仓，意味着什么风险？
3. 给出一个简短的建议

要求：
- 使用简单易懂的语言，避免专业术语
- 直接给出分析结论，不要重复数据
- 控制在100字以内
- 使用中文回答"""

    return prompt


@app.get("/api/portfolios/{portfolio_id}/signals")
async def get_portfolio_signals(
    portfolio_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get AI smart signals for all positions in portfolio."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = get_portfolio_positions(portfolio_id, current_user.id)
        enriched = await _enrich_positions_with_prices(positions)

        if not enriched:
            return {"signals": [], "message": "No positions to analyze"}

        # Get price histories for technical analysis
        loop = asyncio.get_running_loop()
        price_histories = {}

        for pos in enriched:
            code = pos.get('asset_code')
            asset_type = pos.get('asset_type')

            try:
                if asset_type == 'fund':
                    history = await loop.run_in_executor(
                        None, _get_fund_nav_history, code, 60
                    )
                    if history:
                        price_histories[code] = [
                            {'date': h['date'], 'price': h['value']}
                            for h in history
                        ]
                else:
                    history = await loop.run_in_executor(
                        None, _get_stock_price_history, code, 60
                    )
                    if history:
                        price_histories[code] = history
            except Exception as e:
                print(f"Error fetching history for {code}: {e}")

        # Generate signals
        generator = SignalGenerator()
        signals = generator.generate_signals(
            positions=enriched,
            price_histories=price_histories,
            fund_flows=None,  # Would need fund flow data source
            sentiments=None,  # Would need sentiment data source
            correlations=None,
            news_events=None
        )

        # Count signals by type
        signal_counts = {
            "opportunity": sum(1 for s in signals if s['signal_type'] == 'opportunity'),
            "risk": sum(1 for s in signals if s['signal_type'] == 'risk'),
            "neutral": sum(1 for s in signals if s['signal_type'] == 'neutral')
        }

        return sanitize_for_json({
            "signals": signals,
            "counts": signal_counts,
            "total": len(signals),
            "generated_at": datetime.now().isoformat()
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolios/{portfolio_id}/signals/{asset_code}")
async def get_signal_detail(
    portfolio_id: int,
    asset_code: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed signal analysis for a specific position."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = get_portfolio_positions(portfolio_id, current_user.id)
        enriched = await _enrich_positions_with_prices(positions)

        # Find the specific position
        position = None
        for pos in enriched:
            if pos.get('asset_code') == asset_code:
                position = pos
                break

        if not position:
            raise HTTPException(status_code=404, detail="Position not found")

        # Get price history
        loop = asyncio.get_running_loop()
        asset_type = position.get('asset_type')
        price_history = []

        try:
            if asset_type == 'fund':
                history = await loop.run_in_executor(
                    None, _get_fund_nav_history, asset_code, 60
                )
                if history:
                    price_history = [
                        {'date': h['date'], 'price': h['value']}
                        for h in history
                    ]
            else:
                history = await loop.run_in_executor(
                    None, _get_stock_price_history, asset_code, 60
                )
                if history:
                    price_history = history
        except Exception as e:
            print(f"Error fetching history for {asset_code}: {e}")

        # Generate detailed signal
        generator = SignalGenerator()
        detail = generator.get_signal_detail(
            position=position,
            price_history=price_history,
            fund_flow=None,
            sentiment=None,
            correlation_data=None,
            news_events=None,
            all_positions=enriched
        )

        return sanitize_for_json(detail)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting signal detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolios/{portfolio_id}/risk-summary")
async def get_portfolio_risk_summary(
    portfolio_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive risk summary including Beta, Sharpe, VaR, and Health Score."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = get_portfolio_positions(portfolio_id, current_user.id)
        enriched = await _enrich_positions_with_prices(positions)

        if not enriched:
            return {
                "beta": None,
                "sharpe_ratio": None,
                "var_95": None,
                "health_score": 50,
                "health_grade": "N/A",
                "message": "No positions to analyze"
            }

        # Get price histories
        loop = asyncio.get_running_loop()
        price_histories = {}
        current_prices = {}

        for pos in enriched:
            code = pos.get('asset_code')
            asset_type = pos.get('asset_type')
            current_prices[code] = float(pos.get('current_price') or pos.get('average_cost', 0))

            try:
                if asset_type == 'fund':
                    history = await loop.run_in_executor(
                        None, _get_fund_nav_history, code, 90
                    )
                    if history:
                        price_histories[code] = [
                            {'date': h['date'], 'price': h['value']}
                            for h in history
                        ]
                else:
                    history = await loop.run_in_executor(
                        None, _get_stock_price_history, code, 90
                    )
                    if history:
                        price_histories[code] = history
            except Exception as e:
                print(f"Error fetching history for {code}: {e}")

        # Get benchmark history (Shanghai Composite Index)
        benchmark_code = portfolio.get('benchmark_code', '000300.SH')
        try:
            benchmark_history = await loop.run_in_executor(
                None, _get_index_history, benchmark_code, 90
            )
            benchmark_history = [
                {'date': h['date'], 'price': h['close']}
                for h in benchmark_history
            ] if benchmark_history else []
        except:
            benchmark_history = []

        # Calculate risk metrics
        calculator = PortfolioRiskMetrics()
        result = calculator.calculate_risk_summary(
            positions=enriched,
            price_histories=price_histories,
            benchmark_history=benchmark_history,
            current_prices=current_prices
        )

        return sanitize_for_json(result)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error calculating risk summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolios/{portfolio_id}/sparkline")
async def get_portfolio_sparkline(
    portfolio_id: int,
    days: int = 7,
    current_user: User = Depends(get_current_user)
):
    """Get sparkline data (mini chart) for portfolio value over time."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Get portfolio snapshots
        snapshots = get_portfolio_snapshots(portfolio_id, limit=days + 5)

        if not snapshots:
            # If no snapshots, calculate current value as single point
            positions = get_portfolio_positions(portfolio_id, current_user.id)
            enriched = await _enrich_positions_with_prices(positions)
            total_value = sum(
                float(p.get('current_value') or p.get('total_shares', 0) * p.get('average_cost', 0))
                for p in enriched
            )

            return {
                "portfolio_id": portfolio_id,
                "values": [round(total_value, 2)],
                "dates": [datetime.now().strftime('%Y-%m-%d')],
                "change": 0,
                "change_pct": 0,
                "trend": "flat",
                "days": 1
            }

        # Calculate sparkline data
        calculator = PortfolioRiskMetrics()
        result = calculator.calculate_sparkline_data(portfolio_id, snapshots, days)

        return sanitize_for_json(result)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting sparkline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_stock_price_history(stock_code: str, days: int = 90) -> List[Dict]:
    """Get stock price history."""
    try:
        # get_stock_history returns List[Dict] with keys: date, value, volume
        # We add some buffer to days to ensure we have enough data
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
        print(f"Error in _get_stock_price_history: {e}")
        return []
        print(f"Error fetching stock history for {stock_code}: {e}")
        return []


# ====================================================================
# Data Migration API
# ====================================================================

@app.post("/api/portfolios/{portfolio_id}/migrate-positions")
async def migrate_old_positions(
    portfolio_id: int,
    current_user: User = Depends(get_current_user)
):
    """Migrate old fund_positions to the new positions table."""
    try:
        portfolio = get_portfolio_by_id(portfolio_id, current_user.id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        migrated_count = migrate_fund_positions_to_positions(current_user.id, portfolio_id)
        return {
            "message": f"Successfully migrated {migrated_count} positions",
            "migrated_count": migrated_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error migrating positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# Helper functions for fund data retrieval
# ====================================================================

def _get_fund_nav_history(fund_code: str, days: int = 100) -> List[Dict]:
    """Get fund NAV history."""
    try:
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        if df is None or df.empty:
            return []

        # Normalize column names
        if '净值日期' not in df.columns:
            cols = list(df.columns)
            if len(cols) >= 2:
                df = df.rename(columns={cols[0]: '净值日期', cols[1]: '单位净值'})

        if '净值日期' not in df.columns or '单位净值' not in df.columns:
            return []

        df['净值日期'] = pd.to_datetime(df['净值日期'], errors='coerce')
        df = df.dropna(subset=['净值日期', '单位净值'])
        df = df.sort_values('净值日期').tail(days)

        return [
            {'date': row['净值日期'].strftime('%Y-%m-%d'), 'value': float(row['单位净值'])}
            for _, row in df.iterrows()
        ]
    except Exception as e:
        print(f"Error fetching NAV history for {fund_code}: {e}")
        return []


def _get_fund_basic_info(fund_code: str) -> Optional[Dict]:
    """Get basic fund information."""
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


def _get_fund_holdings_list(fund_code: str) -> List[Dict]:
    """Get fund top holdings as a list."""
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


# ====================================================================
# Static files and SPA routes - MUST be defined AFTER all API routes
# ====================================================================
if os.path.exists(STATIC_DIR):
    # 挂载静态资源目录
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    # 根路径返回前端 index.html
    @app.get("/")
    async def serve_frontend():
        index_file = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "Frontend not built. Please build frontend first."}

    # 处理前端路由，所有非API路径都返回 index.html
    # This catch-all route MUST be last - FastAPI matches routes in order
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # 检查是否是静态资源文件
        static_file = os.path.join(STATIC_DIR, full_path)
        if os.path.exists(static_file) and os.path.isfile(static_file):
            return FileResponse(static_file)

        # 其他路径返回 index.html (SPA路由)
        index_file = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)

        raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="EastMoney API Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    args = parser.parse_args()

    # Need to run init_db if running directly explicitly, but uvicorn.run(app) triggers lifespan
    # so we don't need to manually start scheduler here anymore if using lifespan.
    
    uvicorn.run(app, host=args.host, port=args.port)
