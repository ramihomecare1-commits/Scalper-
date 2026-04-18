import asyncio
import json
import time
import websockets
from typing import Dict, List, Callable
from utils.logger import log
from utils.circuit_breaker import CircuitBreakerManager
from utils.health_monitor import health_monitor

class BinanceWebSocket:
    """
    Connects to Binance WebSocket for spot tickers to feed lead/lag analysis.
    """
    def __init__(self):
        self.base_url = "wss://stream.binance.com:9443/ws"
        self.ws = None
        self.running = False
        self.callbacks: List[Callable] = []
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        self.breaker = CircuitBreakerManager.get_breaker("BINANCE_WS", failure_threshold=3, recovery_timeout=30)
        self.symbols = [] # e.g. ["btcusdt", "ethusdt"]
        self.last_ping = 0

    async def connect(self, okx_symbols: List[str]):
        """
        Convert OKX symbols (BTC-USDT-SWAP) to Binance format (btcusdt)
        and establish connection.
        """
        try:
            self.symbols = []
            for sym in okx_symbols:
                base = sym.split('-')[0].lower()
                self.symbols.append(f"{base}usdt")
                
            # Create stream URL (e.g. wss://stream.binance.com:9443/ws/btcusdt@ticker/ethusdt@ticker)
            streams = "/".join([f"{s}@ticker" for s in self.symbols])
            url = f"{self.base_url}/{streams}"
            
            log.info(f"Connecting to Binance WebSocket for lead/lag: {url}")
            self.ws = await websockets.connect(url)
            self.running = True
            log.info("Connected to Binance WebSocket")
            health_monitor.update_connection_status("binance_ws", True)
            self.breaker.record_success()
            self.reconnect_delay = 5
            
            asyncio.create_task(self._listen())
            asyncio.create_task(self._ping_loop())
            
        except Exception as e:
            log.error(f"Binance WebSocket connection failed: {e}")
            await self._reconnect()

    async def _reconnect(self):
        """Handle reconnection logic with exponential backoff and circuit breaker"""
        self.running = False
        health_monitor.update_connection_status("binance_ws", False)
        self.breaker.record_failure()
        
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
        
        if not self.breaker.can_execute():
            log.warning(f"Binance WS Circuit OPEN. Throttling reconnection attempts.")
            await asyncio.sleep(self.breaker.recovery_timeout)
            
        log.warning(f"Reconnecting Binance WS in {self.reconnect_delay}s...")
        health_monitor.record_reconnect("binance_ws")
        
        await asyncio.sleep(self.reconnect_delay)
        
        # Exponential backoff
        self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
        
        # We need the OKX symbols to reconnect, so we map back from binance symbols
        okx_symbols_mock = [f"{s[:-4].upper()}-USDT-SWAP" for s in self.symbols]
        await self.connect(okx_symbols_mock)

    async def _listen(self):
        """Listen for Binance messages"""
        while self.running:
            try:
                msg = await self.ws.recv()
                data = json.loads(msg)
                self.breaker.record_success() 
                health_monitor.update_latency("binance_ws", 0)
                
                # Binance ticker payload structure:
                # { "e": "24hrTicker", "s": "BTCUSDT", "c": "67000.50", ... }
                if data.get("e") == "24hrTicker":
                    for callback in self.callbacks:
                        await callback(data)
                        
            except websockets.ConnectionClosed:
                log.warning("Binance WebSocket connection closed")
                await self._reconnect()
                break
            except Exception as e:
                log.error(f"Error in Binance WS listener: {e}")
                await asyncio.sleep(1)

    async def _ping_loop(self):
        """Keep connection alive"""
        while self.running:
            try:
                await asyncio.sleep(60)
                if self.ws:
                    pong_waiter = await self.ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=10)
            except Exception as e:
                log.debug(f"Binance ping failed: {e}")
                
    def add_callback(self, callback: Callable):
        """Register a callback for data updates"""
        self.callbacks.append(callback)

    async def close(self):
        """Close connection"""
        self.running = False
        if self.ws:
            await self.ws.close()
