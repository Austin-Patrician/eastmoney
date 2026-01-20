"""
FastAPI 服务 - 提供基金数据接口
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uvicorn

from fund_api import search_funds, get_fund_info

app = FastAPI(title="do-tools Data Service")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "do-tools Data Service", "status": "running"}


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/market/funds")
async def search_market_funds(q: str, limit: Optional[int] = 10):
    """
    搜索基金
    
    Args:
        q: 搜索关键词（基金代码或名称）
        limit: 返回结果数量限制
        
    Returns:
        基金列表
    """
    if not q:
        return []
    
    try:
        results = search_funds(q, limit=limit)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fund/{fund_code}")
async def get_fund_details(fund_code: str):
    """
    获取基金详细信息
    
    Args:
        fund_code: 基金代码
        
    Returns:
        基金详细信息
    """
    try:
        info = get_fund_info(fund_code)
        if not info:
            raise HTTPException(status_code=404, detail="Fund not found")
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
