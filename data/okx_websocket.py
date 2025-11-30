import asyncio
import json
import time
import websockets
from typing import List, Dict, Callable, Optional
from config import Config
from utils.logger import log

class OKXWebSocket:
    def __init__(self):
        self.url = "wss://wspap.okx.com:8443/ws/v5/public" if Config.OKX_DEMO_TRADING else "wss://ws.okx.com:8443/ws/v5/public"
        self.ws = None
        self.running = False
        self.callbacks: Dict[str, List[Callable]] = {}
        self.subscriptions = []
        self.reconnect_delay = 5

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
                
            asyncio.create_task(self._listen())
            asyncio.create_task(self._ping_loop())
            
        except Exception as e:
            log.error(f"WebSocket connection failed: {e}")
            await self._reconnect()

    async def _reconnect(self):
        """Handle reconnection logic"""
        self.running = False
        if self.ws:
            await self.ws.close()
        
        log.warning(f"Reconnecting in {self.reconnect_delay} seconds...")
        await asyncio.sleep(self.reconnect_delay)
        await self.connect()

    async def subscribe(self, channels: List[Dict]):
        """Subscribe to channels"""
        self.subscriptions.extend(channels)
        if self.running and self.ws:
            await self._subscribe(channels)

    async def _subscribe(self, channels: List[Dict]):
        """Internal subscription method"""
        msg = {
            "op": "subscribe",
            "args": channels
        }
        await self.ws.send(json.dumps(msg))
        log.info(f"Subscribed to {len(channels)} channels")

    async def _listen(self):
        """Listen for messages"""
        while self.running:
            try:
                msg = await self.ws.recv()
                
                # Handle non-JSON messages (like "pong")
                if not msg or not msg.strip().startswith('{'):
                    continue
                
                data = json.loads(msg)
                
                if "event" in data:
                    if data["event"] == "subscribe":
                        log.debug(f"Subscription confirmed: {data.get('arg')}")
                    elif data["event"] == "error":
                        log.error(f"WebSocket error: {data}")
                    continue

                if "data" in data and "arg" in data:
                    channel = data["arg"]["channel"]
                    inst_id = data["arg"]["instId"]
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
