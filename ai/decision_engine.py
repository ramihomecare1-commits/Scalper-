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
                return None

            # 3. Validate decision
            if self._validate_decision(decision, market_data):
                return decision
            
            return None

        except Exception as e:
            log.error(f"Error in decision engine: {e}")
            return None

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
