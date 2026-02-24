"""
iTick stock websocket gateway.

Maintains a single upstream iTick connection and fans out events to many local
websocket clients subscribed by symbol/region/type.
"""
from __future__ import annotations

import asyncio
import json
import ssl
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from websockets.legacy.client import connect as ws_connect

from config.settings import ITICK_CA_BUNDLE, ITICK_SSL_VERIFY, ITICK_STOCK_WS_URL, ITICK_TOKEN


def _normalize_type(raw_type: str) -> str:
    value = (raw_type or "").strip().lower()
    if not value:
        return ""
    if value in {"quote", "tick", "depth"}:
        return value
    if value.startswith("kline@"):
        return value
    return ""


def _normalize_symbol_region(symbol: str, region: str) -> Tuple[str, str]:
    return (symbol or "").strip().upper(), (region or "").strip().upper()


def _topic_key(symbol: str, region: str, event_type: str) -> str:
    return f"{symbol}${region}|{event_type}"


def _topic_to_param_and_type(topic: str) -> Tuple[str, str]:
    param, event_type = topic.split("|", 1)
    return param, event_type


class ItickStockWsGateway:
    def __init__(self) -> None:
        self._ws_url = ITICK_STOCK_WS_URL
        self._token = ITICK_TOKEN
        self._ssl_context = self._build_ssl_context()
        self._connect_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()

        self._runner_task: Optional[asyncio.Task] = None
        self._ws: Any = None
        self._stopping = False
        self._connected = asyncio.Event()

        self._client_queues: Dict[str, asyncio.Queue] = {}
        self._client_topics: Dict[str, Set[str]] = defaultdict(set)
        self._topic_clients: Dict[str, Set[str]] = defaultdict(set)
        self._upstream_topics: Set[str] = set()

    def is_enabled(self) -> bool:
        return bool(self._token)

    async def ensure_running(self) -> None:
        if not self.is_enabled():
            raise RuntimeError("iTick websocket is disabled. Please set ITICK_TOKEN.")

        async with self._connect_lock:
            if self._runner_task and not self._runner_task.done():
                return
            self._stopping = False
            self._runner_task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        self._stopping = True
        task = self._runner_task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self._cleanup_connection()

    async def register_client(self, client_id: str) -> asyncio.Queue:
        await self.ensure_running()
        queue: asyncio.Queue = asyncio.Queue(maxsize=300)
        async with self._state_lock:
            self._client_queues[client_id] = queue
        return queue

    async def remove_client(self, client_id: str) -> None:
        to_unsubscribe: Dict[str, Set[str]] = defaultdict(set)
        async with self._state_lock:
            topics = list(self._client_topics.pop(client_id, set()))
            self._client_queues.pop(client_id, None)
            for topic in topics:
                clients = self._topic_clients.get(topic)
                if not clients:
                    continue
                clients.discard(client_id)
                if clients:
                    continue
                self._topic_clients.pop(topic, None)
                if topic in self._upstream_topics:
                    self._upstream_topics.discard(topic)
                    param, event_type = _topic_to_param_and_type(topic)
                    to_unsubscribe[param].add(event_type)

        await self._send_batch_control("unsubscribe", to_unsubscribe)

    async def subscribe(self, client_id: str, symbol: str, region: str, types: List[str]) -> List[str]:
        symbol, region = _normalize_symbol_region(symbol, region)
        if not symbol or not region:
            return []

        valid_types = [_normalize_type(t) for t in types]
        valid_types = [t for t in valid_types if t]
        if not valid_types:
            valid_types = ["quote", "depth", "tick", "kline@1"]

        to_subscribe: Dict[str, Set[str]] = defaultdict(set)
        async with self._state_lock:
            if client_id not in self._client_queues:
                return []
            for event_type in valid_types:
                topic = _topic_key(symbol, region, event_type)
                if topic in self._client_topics[client_id]:
                    continue
                first_subscriber = not self._topic_clients.get(topic)
                self._client_topics[client_id].add(topic)
                self._topic_clients[topic].add(client_id)
                if first_subscriber and self._connected.is_set():
                    self._upstream_topics.add(topic)
                    param, etype = _topic_to_param_and_type(topic)
                    to_subscribe[param].add(etype)

        await self._send_batch_control("subscribe", to_subscribe)
        return valid_types

    async def unsubscribe(self, client_id: str, symbol: str, region: str, types: List[str]) -> List[str]:
        symbol, region = _normalize_symbol_region(symbol, region)
        if not symbol or not region:
            return []

        valid_types = [_normalize_type(t) for t in types]
        valid_types = [t for t in valid_types if t]
        if not valid_types:
            valid_types = ["quote", "depth", "tick", "kline@1"]

        to_unsubscribe: Dict[str, Set[str]] = defaultdict(set)
        async with self._state_lock:
            if client_id not in self._client_queues:
                return []
            for event_type in valid_types:
                topic = _topic_key(symbol, region, event_type)
                if topic not in self._client_topics[client_id]:
                    continue
                self._client_topics[client_id].discard(topic)
                topic_clients = self._topic_clients.get(topic)
                if not topic_clients:
                    continue
                topic_clients.discard(client_id)
                if topic_clients:
                    continue
                self._topic_clients.pop(topic, None)
                if topic in self._upstream_topics:
                    self._upstream_topics.discard(topic)
                    param, etype = _topic_to_param_and_type(topic)
                    to_unsubscribe[param].add(etype)

        await self._send_batch_control("unsubscribe", to_unsubscribe)
        return valid_types

    async def _run_forever(self) -> None:
        backoff_seconds = 1
        while not self._stopping:
            try:
                await self._run_session()
                backoff_seconds = 1
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"iTick websocket gateway error: {e}")
            finally:
                await self._cleanup_connection()

            if self._stopping:
                break
            await asyncio.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 20)

    async def _run_session(self) -> None:
        ws = await ws_connect(
            self._ws_url,
            ssl=self._ssl_context,
            extra_headers={
                "accept": "application/json",
                "token": self._token,
            },
            ping_interval=None,
            ping_timeout=None,
            open_timeout=12,
            close_timeout=5,
            max_queue=1000,
        )

        async with self._state_lock:
            self._ws = ws
            self._connected.set()
            self._upstream_topics.clear()

        auth_payload = {"ac": "auth", "params": self._token}
        await ws.send(json.dumps(auth_payload, ensure_ascii=False))

        first_msg: Optional[Dict[str, Any]] = None
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=8)
            msg = self._parse_json(raw)
            if msg:
                first_msg = msg
        except asyncio.TimeoutError:
            pass

        if first_msg and first_msg.get("resAc") == "auth" and first_msg.get("code") not in (0, "0", None):
            raise RuntimeError(f"iTick auth failed: {first_msg}")

        await self._resubscribe_all()
        if first_msg and first_msg.get("resAc") != "auth":
            await self._handle_upstream_message(first_msg)

        ping_task = asyncio.create_task(self._ping_loop(ws))
        try:
            while True:
                raw = await ws.recv()
                msg = self._parse_json(raw)
                if msg:
                    await self._handle_upstream_message(msg)
        finally:
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_connection(self) -> None:
        ws = None
        async with self._state_lock:
            if self._ws is not None:
                ws = self._ws
            self._ws = None
            self._connected.clear()
            self._upstream_topics.clear()

        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

    async def _ping_loop(self, ws: Any) -> None:
        while True:
            await asyncio.sleep(25)
            payload = {"ac": "ping", "params": str(int(time.time() * 1000))}
            await ws.send(json.dumps(payload, ensure_ascii=False))

    async def _resubscribe_all(self) -> None:
        desired: Dict[str, Set[str]] = defaultdict(set)
        async with self._state_lock:
            for topic, clients in self._topic_clients.items():
                if not clients:
                    continue
                param, event_type = _topic_to_param_and_type(topic)
                desired[param].add(event_type)

        await self._send_batch_control("subscribe", desired)
        async with self._state_lock:
            for param, types in desired.items():
                for event_type in types:
                    self._upstream_topics.add(f"{param}|{event_type}")

    async def _send_batch_control(self, action: str, grouped_types: Dict[str, Set[str]]) -> None:
        if not grouped_types:
            return

        async with self._state_lock:
            ws = self._ws
            is_connected = self._connected.is_set()
        if ws is None or not is_connected:
            return

        for param, types in grouped_types.items():
            payload = {
                "ac": action,
                "params": [param],
                "types": sorted(types),
            }
            try:
                await ws.send(json.dumps(payload, ensure_ascii=False))
            except Exception as e:
                print(f"iTick websocket {action} failed for {param}: {e}")
                return

    async def _handle_upstream_message(self, message: Dict[str, Any]) -> None:
        data = message.get("data")
        if not isinstance(data, dict):
            return

        event_type = _normalize_type(str(data.get("type") or ""))
        if not event_type:
            return

        symbol = str(data.get("s") or "").upper()
        region = str(data.get("r") or "").upper()
        if not symbol or not region:
            return

        topic = _topic_key(symbol, region, event_type)
        async with self._state_lock:
            client_ids = list(self._topic_clients.get(topic, set()))
            queues = [self._client_queues[cid] for cid in client_ids if cid in self._client_queues]

        if not queues:
            return

        event = {
            "type": event_type,
            "symbol": symbol,
            "region": region,
            "ts": data.get("t") or data.get("tm") or int(time.time() * 1000),
            "data": data,
        }
        for queue in queues:
            try:
                if queue.full():
                    _ = queue.get_nowait()
                queue.put_nowait(event)
            except Exception:
                continue

    @staticmethod
    def _parse_json(raw: Any) -> Optional[Dict[str, Any]]:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        if not isinstance(raw, str):
            return None
        try:
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None

    @staticmethod
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


itick_stock_ws_gateway = ItickStockWsGateway()

