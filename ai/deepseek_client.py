import aiohttp
import asyncio
import json
from typing import Dict, Optional
from config import Config
from utils.logger import log

class DeepSeekClient:
    def __init__(self):
        self.api_key = Config.DEEPSEEK_API_KEY
        self.model = Config.DEEPSEEK_MODEL
        # Use OpenRouter endpoint instead of DeepSeek direct

Output your decision in the following JSON format ONLY:
{
    "action": "BUY" | "SELL" | "HOLD",
    "confidence": 0-100,
    "reasoning": "Brief explanation of the trade rationale",
    "entry_price": float (limit price),
    "stop_loss": float,
    "take_profit": float,
    "timeframe_confluence": ["1m", "5m", "10m", "1h"],
    "risk_level": "LOW" | "MEDIUM" | "HIGH"
}

Rules:
1. Only trade if confidence > 75.
2. Ensure Risk/Reward ratio is at least 1.5:1.
3. Confirm signals across at least 2 timeframes.
4. Respect support/resistance levels from the order book.
"""

