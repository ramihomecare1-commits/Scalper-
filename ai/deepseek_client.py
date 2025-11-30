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
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
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
                    content = data["choices"][0]["message"]["content"]
                    log.debug(f"AI Response from {model}: {content}")
                    
                    return json.loads(content)
                    
        except aiohttp.ClientError as e:
            log.error(f"DeepSeek API connection error for model {model}: {e}")
            return None
        except asyncio.TimeoutError:
            log.warning(f"DeepSeek API timeout for model {model} (may be thinking) - trying fallback")
            return None
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse AI response as JSON from {model}: {e}")
            return None
        except Exception as e:
            log.error(f"DeepSeek API error for model {model}: {e}")
            return None
