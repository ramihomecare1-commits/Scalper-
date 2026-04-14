from typing import Dict, Optional
from ai.deepseek_client import DeepSeekClient
from ai.prompts import PromptGenerator
from utils.logger import log
from config import Config
import asyncio
import time

class DecisionEngine:
    def __init__(self):
        self.ai_client = DeepSeekClient()
        self.prompt_generator = PromptGenerator()
        self.loss_cooldowns = {}  # symbol -> timestamp of last loss
        self.LOSS_COOLDOWN_SECONDS = 1800  # 30 minute cooldown after a loss on a symbol

    async def evaluate_market(self, symbol: str, market_data: Dict) -> Optional[Dict]:
        """
        Evaluate market data and generate trade decision
        """
        try:
            # Pre-filter to save AI API costs
            if not self._should_analyze(symbol, market_data):
                return None

            # Check loss cooldown
            if symbol in self.loss_cooldowns:
                elapsed = time.time() - self.loss_cooldowns[symbol]
                if elapsed < self.LOSS_COOLDOWN_SECONDS:
                    remaining = int((self.LOSS_COOLDOWN_SECONDS - elapsed) / 60)
                    log.debug(f"{symbol}: In loss cooldown ({remaining}m remaining). Skipping.")
                    return None
                else:
                    del self.loss_cooldowns[symbol]  # Cooldown expired

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
        Evaluate multiple markets using concurrent single-symbol AI calls.
        More reliable than asking the AI to return a complex nested JSON.
        """
        try:
            if not symbols_data:
                return {}
            
            # Create concurrent tasks — one AI call per symbol
            async def _evaluate_single(symbol: str, market_data: Dict) -> tuple:
                """Wrapper that returns (symbol, decision) tuple"""
                decision = await self.evaluate_market(symbol, market_data)
                return (symbol, decision)
            
            tasks = [
                _evaluate_single(symbol, market_data)
                for symbol, market_data in symbols_data.items()
            ]
            
            # Run all AI calls concurrently
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Build results dict
            results = {}
            for result in results_list:
                if isinstance(result, Exception):
                    log.error(f"Error in concurrent evaluation: {result}")
                    continue
                symbol, decision = result
                results[symbol] = decision
            
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

            # Rule 3: Multi-Timeframe Trend Alignment
            # The higher timeframes (15m, 1H) must not oppose the trade direction
            indicators_by_tf = market_data.get('indicators', {})
            higher_tfs = ['15m', '1H']
            opposing_count = 0
            for tf in higher_tfs:
                tf_ind = indicators_by_tf.get(tf, {})
                if not tf_ind:
                    continue
                trend = tf_ind.get('trend', 'NEUTRAL')
                if action == 'BUY' and trend == 'BEARISH':
                    opposing_count += 1
                elif action == 'SELL' and trend == 'BULLISH':
                    opposing_count += 1
            
            if opposing_count >= 2:
                log.info(f"Signal rejected: Both higher timeframes oppose {action} direction")
                return False

            return True

        except Exception as e:
            log.error(f"Error validating decision: {e}")
            return False

    def _should_analyze(self, symbol: str, market_data: Dict) -> bool:
        """
        Pre-filter to determine if we should spend AI credits on this symbol.
        Requires some form of momentum or setup to be present.
        """
        try:
            indicators_by_tf = market_data.get('indicators', {})
            primary_tf = list(indicators_by_tf.keys())[0] if indicators_by_tf else None
            
            if not primary_tf:
                return True # Default to analyze if data is weird
                
            ind = indicators_by_tf[primary_tf]
            
            # Check RSI for overbought/oversold momentum
            rsi = ind.get('rsi', 50)
            if rsi > 65 or rsi < 35:
                return True
                
            # Check MACD for recent crossovers
            macd_crossover = ind.get('macd_crossover', 'NONE')
            if macd_crossover != 'NONE':
                return True
                
            # Check Bollinger Bands (price near edges)
            bb_pos = ind.get('bb_position', 'LOWER_HALF')
            if bb_pos in ['ABOVE_UPPER', 'BELOW_LOWER']:
                return True

            # Check Volume Spike (latest candle volume > 1.5x previous)
            candles_data = market_data.get('candles', {})
            primary_tf_candles = candles_data.get(primary_tf, []) if candles_data else []
            if len(primary_tf_candles) >= 2:
                last_vol = primary_tf_candles[-1].get('volume', 0)
                prev_vol = primary_tf_candles[-2].get('volume', 1)
                if prev_vol > 0 and (last_vol / prev_vol) > 1.5:
                    log.debug(f"{symbol}: Volume spike detected ({last_vol/prev_vol:.1f}x). Sending to AI.")
                    return True

            log.debug(f"{symbol}: Pre-filter failed (no momentum). Skipping AI analysis to save credits.")
            return False
            
        except Exception as e:
            log.error(f"Error in pre-filter for {symbol}: {e}")
            return True # Fail open to let AI decide

    def register_loss(self, symbol: str):
        """Call this when a trade on a symbol results in a loss to activate cooldown."""
        self.loss_cooldowns[symbol] = time.time()
        log.info(f"{symbol}: Loss cooldown activated for {self.LOSS_COOLDOWN_SECONDS // 60} minutes.")
