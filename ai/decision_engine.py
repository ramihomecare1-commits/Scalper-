from typing import Dict, Optional
from ai.deepseek_client import DeepSeekClient
from ai.prompts import PromptGenerator
from utils.logger import log
from config import Config

class DecisionEngine:
    def __init__(self):
        self.ai_client = DeepSeekClient()
        self.prompt_generator = PromptGenerator()

    async def evaluate_market(self, symbol: str, market_data: Dict) -> Optional[Dict]:
        """
        Evaluate market data and generate trade decision
        """
        try:
            # 1. Format data for AI
            prompt = self.prompt_generator.format_market_data(symbol, market_data)
            
            # 2. Get AI analysis
            decision = await self.ai_client.analyze_market(prompt)
            
            if not decision:
                log.debug(f"{symbol}: No decision from AI")
                return None
            
            # Log the AI's decision before validation
            log.info(f"{symbol}: AI Decision - Action: {decision.get('action')}, Confidence: {decision.get('confidence')}%, Reasoning: {decision.get('reasoning', 'N/A')[:100]}")

            # 3. Validate decision
            if self._validate_decision(decision, market_data):
                return decision
            
            return None

        except Exception as e:
            log.error(f"Error in decision engine: {e}")
            return None
    
    async def evaluate_multiple_markets(self, symbols_data: Dict) -> Dict[str, Optional[Dict]]:
        """
        Evaluate multiple markets in a single AI call
        Returns dict of {symbol: decision}
        """
        try:
            if not symbols_data:
                return {}
            
            # Format data for all symbols
            combined_prompt = "Analyze the following markets and provide trading decisions for each:\n\n"
            for symbol, market_data in symbols_data.items():
                combined_prompt += f"\n=== {symbol} ===\n"
                combined_prompt += self.prompt_generator.format_market_data(symbol, market_data)
                combined_prompt += "\n"
            
            combined_prompt += "\n\nRespond with a JSON object where keys are symbols and values are decision objects:"
            combined_prompt += '\n{"BTC-USDT-SWAP": {"action":"BUY","confidence":80,...}, "ETH-USDT-SWAP": {"action":"HOLD",...}}'
            
            # Get AI analysis for all symbols
            decisions_dict = await self.ai_client.analyze_market(combined_prompt)
            
            if not decisions_dict:
                return {}
            
            # Validate each decision
            results = {}
            for symbol, decision in decisions_dict.items():
                if decision and symbol in symbols_data:
                    # Log the AI's decision
                    log.info(f"{symbol}: AI Decision - Action: {decision.get('action')}, Confidence: {decision.get('confidence')}%, Reasoning: {decision.get('reasoning', 'N/A')[:100]}")
                    
                    # Validate
                    if self._validate_decision(decision, symbols_data[symbol]):
                        results[symbol] = decision
                    else:
                        results[symbol] = None
                else:
                    results[symbol] = None
            
            return results
            
        except Exception as e:
            log.error(f"Error in multi-market evaluation: {e}")
            return {}

    def _validate_decision(self, decision: Dict, market_data: Dict) -> bool:
        """
        Validate AI decision against hard rules
        """
        try:
            action = decision.get("action", "").upper()
            
            if action == "HOLD":
                return False

            # Rule 1: Confidence Check
            if decision.get("confidence", 0) < 75:
                log.info(f"Signal rejected: Low confidence ({decision.get('confidence')})")
                return False

            # Rule 2: Risk/Reward Check
            entry = decision.get("entry_price")
            sl = decision.get("stop_loss")
            tp = decision.get("take_profit")

            if not all([entry, sl, tp]):
                return False

            risk = abs(entry - sl)
            reward = abs(tp - entry)
            
            if risk == 0:
                return False
                
            rr_ratio = reward / risk
            if rr_ratio < Config.RISK_REWARD_RATIO:
                log.info(f"Signal rejected: Low R/R ratio ({rr_ratio:.2f})")
                return False

            return True

        except Exception as e:
            log.error(f"Error validating decision: {e}")
            return False
