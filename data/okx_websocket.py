import asyncio
import json
import time
import websockets
from typing import List, Dict, Callable, Optional
from config import Config
from utils.logger import log
from utils.circuit_breaker import CircuitBreakerManager
from utils.health_monitor import health_monitor

class OKXWebSocket:
    def __init__(self):
        # Always use the mainnet WebSocket for public data (tickers, books). 
        # The demo websocket restricts many tokens from the top 100 list which causes "doesn't exist" errors.
        self.url = "wss://ws.okx.com:8443/ws/v5/public"
        self.ws = None
        self.running = False
        self.callbacks: Dict[str, List[Callable]] = {}
        self.subscriptions = []
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        self.breaker = CircuitBreakerManager.get_breaker("OKX_WS", failure_threshold=3, recovery_timeout=30)

    async def connect(self):
        """Establish WebSocket connection"""
        try:
            log.info(f"Connecting to OKX WebSocket: {self.url}")
            self.ws = await websockets.connect(self.url)
            self.running = True
            log.info("Connected to OKX WebSocket")
            
            # Resubscribe if we have existing subscriptions
            if self.subscriptions:
                await self._subscribe(self.subscriptions)
                
            health_monitor.update_connection_status("okx_ws", True)
            self.breaker.record_success()
            self.reconnect_delay = 5 # Reset delay on success
            
            asyncio.create_task(self._listen())
            asyncio.create_task(self._ping_loop())
            
        except Exception as e:
            error_msg = f"WebSocket connection failed: {e}"
            log.error(error_msg)
            
            # Send Telegram notification for connection errors
            try:
                import aiohttp
                from config import Config
                if hasattr(Config, 'TELEGRAM_BOT_TOKEN') and Config.TELEGRAM_BOT_TOKEN:
                    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
                    payload = {
                        "chat_id": Config.TELEGRAM_CHAT_ID,
                        "text": f"🤖 <b>SCALPER BOT</b>\n⚠️ <b>CONNECTION ERROR</b>\n\n{error_msg}",
                        "parse_mode": "HTML"
                    }
                    async with aiohttp.ClientSession() as session:
                        await session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5))
            except:
                pass
            
            await self._reconnect()

    async def _reconnect(self):
        """Handle reconnection logic with exponential backoff and circuit breaker"""
        self.running = False
        health_monitor.update_connection_status("okx_ws", False)
        self.breaker.record_failure()
        
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
        
        if not self.breaker.can_execute():
            log.warning(f"OKX WS Circuit OPEN. Throttling reconnection attempts.")
            await asyncio.sleep(self.breaker.recovery_timeout)
            
        log.warning(f"Reconnecting OKX WebSocket in {self.reconnect_delay} seconds...")
        health_monitor.record_reconnect("okx_ws")
        
        await asyncio.sleep(self.reconnect_delay)
        
        # Exponential backoff
        self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
        
        await self.connect()

    async def subscribe(self, channels: List[Dict]):
        """Subscribe to channels"""
        self.subscriptions.extend(channels)
        if self.running and self.ws:
            await self._subscribe(channels)

    async def _subscribe(self, channels: List[Dict]):
        """Internal subscription method with chunking to avoid OKX limits"""
        chunk_size = 30
        for i in range(0, len(channels), chunk_size):
            chunk = channels[i:i + chunk_size]
            msg = {
                "op": "subscribe",
                "args": chunk
            }
            if self.ws:
                await self.ws.send(json.dumps(msg))
            log.info(f"Subscribed to chunk of {len(chunk)} channels")
            await asyncio.sleep(0.5) # Slight delay between chunks

    async def _listen(self):
        """Listen for messages"""
        while self.running:
            try:
                msg = await self.ws.recv()
                
                # Handle non-JSON messages (like "pong")
                if not msg or not msg.strip().startswith('{'):
                    continue
                
                data = json.loads(msg)
                
                # Update health monitor
                health_monitor.update_latency("okx_ws", 0) # Base update
                self.breaker.record_success() 
                
                if "event" in data:
                    if data["event"] == "subscribe":
                        log.debug(f"Subscription confirmed: {data.get('arg')}")
                    elif data["event"] == "error":
                        log.error(f"WebSocket error: {data}")
                    continue

                if "data" in data and "arg" in data:
                    channel = data["arg"].get("channel", "")
                    inst_id = data["arg"].get("instId", "")
                    # Dispatch to callbacks
                    key = f"{channel}:{inst_id}"
                    
                    # Pass full data context including 'arg' so we know the channel
                    if key in self.callbacks:
                        for callback in self.callbacks[key]:
                            await callback(data)
                    
                    # Also dispatch to general channel callbacks
                    if channel in self.callbacks:
                        for callback in self.callbacks[channel]:
                            await callback(data)
                    
                    # Dispatch to general 'candle' callback if it's a candle channel
                    if channel.startswith("candle"):
                        if "candle" in self.callbacks:
                            for callback in self.callbacks["candle"]:
                                await callback(data)

            except websockets.ConnectionClosed:
                log.warning("WebSocket connection closed")
                await self._reconnect()
                break
            except json.JSONDecodeError:
                # Ignore non-JSON messages (like "pong")
                continue
            except Exception as e:
                log.error(f"Error in listener: {e}")
                await asyncio.sleep(1)

    async def _ping_loop(self):
        """Keep connection alive"""
        while self.running:
            try:
                await asyncio.sleep(20)
                if self.ws:
                    await self.ws.send("ping")
            except Exception as e:
                log.error(f"Ping failed: {e}")
                break

    def add_callback(self, channel: str, inst_id: Optional[str], callback: Callable):
        """Register a callback for data updates"""
        key = f"{channel}:{inst_id}" if inst_id else channel
        if key not in self.callbacks:
            self.callbacks[key] = []
        self.callbacks[key].append(callback)

    async def close(self):
        """Close connection"""
        self.running = False
        if self.ws:
            await self.ws.close()
