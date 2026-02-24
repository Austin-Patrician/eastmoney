"""
iTick stock realtime client.

Docs:
- GET /stock/quote
- GET /stock/quotes
- GET /stock/depth
"""
from __future__ import annotations

import json
import ssl
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config.settings import (
    ITICK_CA_BUNDLE,
    ITICK_SSL_VERIFY,
    ITICK_STOCK_API_BASE,
    ITICK_TIMEOUT_SECONDS,
    ITICK_TOKEN,
)


def _build_ssl_context() -> ssl.SSLContext:
    if not ITICK_SSL_VERIFY:
        return ssl._create_unverified_context()

    if ITICK_CA_BUNDLE:
        return ssl.create_default_context(cafile=ITICK_CA_BUNDLE)

    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


ITICK_SSL_CONTEXT = _build_ssl_context()


def is_itick_enabled() -> bool:
    return bool(ITICK_TOKEN)


def normalize_code(raw_code: str) -> str:
    code = (raw_code or "").strip().upper()
    if not code:
        return ""

    # Common forms: SH600519 / SZ000001 / 600519.SH
    if "." in code:
        left, right = code.split(".", 1)
        if right in {"SH", "SZ", "HK", "US"}:
            code = left
    if code.startswith(("SH", "SZ", "HK", "US")) and len(code) > 2:
        code = code[2:]
    return code


def infer_region_and_code(stock_code: str, market: Optional[str] = None) -> Tuple[Optional[str], str]:
    code = normalize_code(stock_code)
    market_norm = (market or "").strip().upper()

    market_map = {
        "SH": "SH",
        "SSE": "SH",
        "SZ": "SZ",
        "SZSE": "SZ",
        "HK": "HK",
        "HKG": "HK",
        "US": "US",
        "NASDAQ": "US",
        "NYSE": "US",
    }
    if market_norm in market_map:
        return market_map[market_norm], code

    if code.isdigit() and len(code) == 6:
        if code.startswith("6"):
            return "SH", code
        if code.startswith(("0", "3")):
            return "SZ", code

    # Hong Kong symbols are usually numeric and <= 5 digits.
    if code.isdigit() and len(code) <= 5:
        return "HK", code

    # US tickers are usually alphabetic.
    if code and code[0].isalpha():
        return "US", code

    return None, code


def _http_get(path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not is_itick_enabled():
        return None

    query = urlencode(params)
    url = f"{ITICK_STOCK_API_BASE}{path}?{query}"
    headers = {
        "accept": "application/json",
        "token": ITICK_TOKEN,
    }
    req = Request(url=url, headers=headers, method="GET")

    try:
        with urlopen(req, timeout=ITICK_TIMEOUT_SECONDS, context=ITICK_SSL_CONTEXT) as resp:
            payload = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(payload)
            if isinstance(data, dict):
                return data
            return None
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"iTick request failed {url}: {e}")
        return None


def get_stock_quote(region: str, code: str) -> Optional[Dict[str, Any]]:
    result = _http_get("/quote", {"region": region, "code": code})
    if not result:
        return None
    if result.get("code") == 0:
        data = result.get("data")
        return data if isinstance(data, dict) else None
    return None


def get_stock_quotes(region: str, codes: List[str]) -> Dict[str, Dict[str, Any]]:
    if not codes:
        return {}
    result = _http_get("/quotes", {"region": region, "codes": ",".join(codes)})
    if not result:
        return {}
    if result.get("code") != 0:
        return {}

    data = result.get("data")
    if not isinstance(data, dict):
        return {}

    normalized: Dict[str, Dict[str, Any]] = {}
    for k, v in data.items():
        if isinstance(v, dict):
            normalized[str(k)] = v
    return normalized


def get_stock_depth(region: str, code: str) -> Optional[Dict[str, Any]]:
    result = _http_get("/depth", {"region": region, "code": code})
    if not result:
        return None
    if result.get("code") == 0:
        data = result.get("data")
        return data if isinstance(data, dict) else None
    return None


def map_quote_to_legacy_fields(quote: Dict[str, Any], code: str = "") -> Dict[str, Any]:
    ts = quote.get("t")
    data_time = ts
    try:
        if isinstance(ts, (int, float)):
            data_time = datetime.fromtimestamp(float(ts) / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        data_time = ts

    return {
        "代码": quote.get("s") or code,
        "名称": "",
        "最新价": quote.get("ld"),
        "涨跌幅": quote.get("chp"),
        "涨跌额": quote.get("ch"),
        "成交量": quote.get("v"),
        "成交额": quote.get("tu"),
        "最高": quote.get("h"),
        "最低": quote.get("l"),
        "今开": quote.get("o"),
        "昨收": quote.get("p"),
        "数据时间": data_time,
        "交易状态": quote.get("ts"),
    }
