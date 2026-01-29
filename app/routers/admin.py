"""
Admin and system endpoints.
"""
import os
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from openai import OpenAI

from app.models.settings import ModelListRequest
from app.models.auth import User
from app.core.dependencies import get_current_user
from src.llm.client import get_llm_client
from src.data_sources.web_search import WebSearch
from src.storage.db import (
    get_stock_basic_count,
    get_stock_basic_last_updated,
    get_fund_basic_count,
    get_fund_basic_last_updated,
)

router = APIRouter(tags=["Admin"])


@router.post("/api/system/test-llm")
async def test_llm_connection(current_user: User = Depends(get_current_user)):
    """Test LLM connection."""
    try:
        client = get_llm_client()
        response = await asyncio.to_thread(client.generate_content, "Ping. Reply with 'Pong'.")

        if "Error:" in response:
            return {"status": "error", "message": response}

        return {"status": "success", "message": "LLM Connection Verified", "reply": response}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/api/system/test-search")
async def test_search_connection(current_user: User = Depends(get_current_user)):
    """Test web search connection."""
    try:
        searcher = WebSearch()
        results = await asyncio.to_thread(searcher.search_news, "Apple stock price", max_results=3)

        if not results:
            return {"status": "warning", "message": "Search returned no results (Check API Key limit or network)"}

        titles = [r.get("title") for r in results]
        return {"status": "success", "message": "Search Connection Verified", "results": titles}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/api/admin/sync-stock-basic")
async def sync_stock_basic_endpoint(current_user: User = Depends(get_current_user)):
    """Manually trigger sync of stock basic info from TuShare."""
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


@router.get("/api/admin/stock-basic-status")
async def get_stock_basic_status(current_user: User = Depends(get_current_user)):
    """Get status of stock basic table."""
    count = get_stock_basic_count()
    last_updated = get_stock_basic_last_updated()
    return {
        "count": count,
        "last_updated": last_updated
    }


@router.post("/api/admin/sync-fund-basic")
async def sync_fund_basic_endpoint(current_user: User = Depends(get_current_user)):
    """Manually trigger sync of fund basic info from TuShare (场内+场外基金)."""
    try:
        from src.data_sources.tushare_client import sync_fund_basic
        loop = asyncio.get_running_loop()
        count = await loop.run_in_executor(None, sync_fund_basic)
        return {
            "status": "success",
            "synced": count,
            "message": f"Synced {count} funds from TuShare"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/api/admin/fund-basic-status")
async def get_fund_basic_status(current_user: User = Depends(get_current_user)):
    """Get status of fund basic table (全市场基金列表)."""
    count_all = get_fund_basic_count()
    count_otc = get_fund_basic_count(market='O')
    count_etf = get_fund_basic_count(market='E')
    last_updated = get_fund_basic_last_updated()
    return {
        "total": count_all,
        "otc_funds": count_otc,
        "etf_funds": count_etf,
        "last_updated": last_updated
    }


@router.post("/api/llm/models")
async def list_llm_models(request: ModelListRequest, current_user: User = Depends(get_current_user)):
    """List available LLM models from OpenAI-compatible API."""
    try:
        api_key = request.api_key or os.getenv("OPENAI_API_KEY")
        base_url = request.base_url or os.getenv("OPENAI_BASE_URL")

        if not api_key:
            if base_url and ("localhost" in base_url or "127.0.0.1" in base_url):
                api_key = "dummy"

        if not api_key and not (base_url and ("localhost" in base_url or "127.0.0.1" in base_url)):
            return {"models": [], "warning": "API Key missing"}

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)

        def _fetch():
            return client.models.list()

        models_resp = await asyncio.to_thread(_fetch)
        model_names = sorted([m.id for m in models_resp.data])

        return {"models": model_names}
    except Exception as e:
        print(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))
