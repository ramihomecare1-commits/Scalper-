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
        self.base_url = "https://openrouter.ai/api/v1"
        # Fallback model if primary fails
        self.fallback_model = "deepseek/deepseek-chat"

    async def analyze_market(self, prompt: str) -> Optional[Dict]:
        """
        Send market data to DeepSeek for analysis
        Returns trading decision or None
        """
        if not self.api_key:
            log.error("DeepSeek API key not configured")
            return None

        try:
            log.info("Sending analysis request to DeepSeek AI...")
            
            # Try primary model first (R1)
            result = await self._call_api(prompt, self.model, timeout=60)
            if result:
                return result
            
            # If primary fails, try fallback (v3)
            if self.model != self.fallback_model:
                log.warning(f"Primary model {self.model} failed, trying fallback {self.fallback_model}")
                result = await self._call_api(prompt, self.fallback_model, timeout=30)
                if result:
                    return result
            
            return None
            
        except Exception as e:
            log.error(f"DeepSeek API error: {e}")
            return None
    
    async def _call_api(self, prompt: str, model: str, timeout: int = 60) -> Optional[Dict]:
        """Internal method to call the API with a specific model"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system", 
                        "content": (
                            "You are an elite crypto scalping analyst for perpetual futures. "
                            "Your ONLY job is to identify high-probability, short-duration trades (1-15 minute holds). "
                            "TRADING RULES YOU MUST FOLLOW: "
                            "1. NEVER trade against the higher timeframe trend. If 15m and 1H are bearish, do NOT buy even if 1m looks oversold. "
                            "2. Only signal BUY/SELL when at least 2 timeframes agree on direction. "
                            "3. Require volume confirmation: if the latest candle volume is below the previous candle, default to HOLD. "
                            "4. Set stop_loss using ATR: entry ± (1.5 × ATR of the 1m timeframe). For BUY, SL below entry. For SELL, SL above entry. "
                            "5. Set take_profit at minimum 1.5× the stop_loss distance from entry. "
                            "6. Confidence scoring: 90-100 = perfect multi-TF alignment + volume spike. "
                            "75-89 = strong setup with minor concerns. 50-74 = weak/conflicting → HOLD. Below 50 = dangerous → HOLD. "
                            "7. When in doubt, HOLD. Preserving capital beats catching every move. "
                            "8. Orderbook imbalance > 0.3 favors buyers, < -0.3 favors sellers. Use this as confirmation, not primary signal. "
                            "Respond with ONLY valid JSON. No markdown, no explanation outside the JSON object."
                        )
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.3,  # Lower temperature for more consistent JSON output
                "max_tokens": 500    # We only need a small JSON response — prevents 402 credit errors
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        log.error(f"DeepSeek API error ({response.status}) for model {model}: {error_text}")
                        return None
                    
                    data = await response.json()
                    
                    # Check if response has the expected structure
                    if "choices" not in data or not data["choices"]:
                        log.error(f"Unexpected API response structure from {model}: {data}")
                        return None
                    
                    content = data["choices"][0]["message"]["content"]
                    
                    # Log the raw content for debugging
                    if not content or content.strip() == "":
                        log.error(f"Empty response from {model}")
                        return None
                    
                    # Try to extract JSON if wrapped in markdown
                    content = content.strip()
                    if content.startswith("```"):
                        # Remove markdown code blocks
                        lines = content.split("\n")
                        content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
                        content = content.replace("```json", "").replace("```", "").strip()
                    
                    log.debug(f"AI Response from {model}: {content[:200]}...")  # Log first 200 chars
                    
                    # Try to parse JSON
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError as e:
                        log.error(f"Failed to parse AI response as JSON from {model}. Content: {content[:500]}")
                        return None
                    
        except aiohttp.ClientError as e:
            log.error(f"DeepSeek API connection error for model {model}: {e}")
            return None
        except asyncio.TimeoutError:
            log.warning(f"DeepSeek API timeout for model {model} (may be thinking) - trying fallback")
            return None
        except Exception as e:
            log.error(f"DeepSeek API error for model {model}: {e}")
            return None
