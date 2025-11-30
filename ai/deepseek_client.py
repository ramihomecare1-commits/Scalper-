from openai import AsyncOpenAI
import json
from typing import Dict, Optional
from config import Config
from utils.logger import log

class DeepSeekClient:
    def __init__(self):
        self.client = None
        self.model = Config.DEEPSEEK_MODEL

    def _ensure_client(self):
        """Lazy initialization of the client"""
        if self.client is None:
            if not Config.DEEPSEEK_API_KEY:
                log.warning("DEEPSEEK_API_KEY not set - AI features will be disabled")
                return False
            
            try:
                self.client = AsyncOpenAI(
                    api_key=Config.DEEPSEEK_API_KEY,
                    base_url="https://api.deepseek.com/v1"
                )
            except Exception as e:
                log.error(f"Failed to initialize DeepSeek client: {e}")
                return False
        return True

    async def analyze_market(self, prompt: str) -> Optional[Dict]:
        """
        Send market data to DeepSeek R1 for analysis
        """
        if not self._ensure_client():
            log.warning("DeepSeek client not available - skipping AI analysis")
            return None
            
        try:
            log.info("Sending analysis request to DeepSeek AI...")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            log.debug(f"AI Response: {content}")
            
            return json.loads(content)

        except Exception as e:
            log.error(f"DeepSeek API error: {e}")
            return None

    def _get_system_prompt(self) -> str:
        return """You are an expert high-frequency crypto scalping AI. 
Your goal is to identify high-probability scalping opportunities (1-2% moves) with strict risk management.
You will receive multi-timeframe market data, technical indicators, and order book analysis.

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
