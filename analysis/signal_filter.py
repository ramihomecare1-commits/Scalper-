from typing import Dict, List, Optional
import numpy as np
from analysis.indicators import TechnicalIndicators
from analysis.regime_detector import MarketRegimeDetector
from utils.logger import log

class SignalFilter:
    """
    Gatekeeper for AI requests. 
    Vetoes signals if the market is unfavorable, saving API costs and preventing low-quality trades.
    """
    
    def __init__(self):
        self.regime_detector = MarketRegimeDetector()

    def should_veto(self, symbol: str, candles: List[Dict], orderbook: Optional[Dict] = None) -> Dict:
        """
        Evaluate if a signal should be vetoed.
        Returns Check result: {"veto": bool, "reason": str}
        """
        if not candles or len(candles) < 20:
            return {"veto": True, "reason": "Insufficient candle data"}

        try:
            indicators = TechnicalIndicators.analyze_candles(candles)
            regime_data = self.regime_detector.identify_regime(candles)
            
            # 1. Volume Check: Avoid dead zones
            vol_ratio = indicators.get("vol_ratio", 1.0)
            if vol_ratio < 0.5:
                return {"veto": True, "reason": f"Dead volume zone (Ratio: {vol_ratio:.2f})"}

            # 2. Volatility Check: Avoid flat markets
            atr_pct = indicators.get("atr_pct", 0)
            if atr_pct < 0.15: # Less than 0.15% movement per bar is too flat for scalping
                return {"veto": True, "reason": f"Low volatility trap (ATR%: {atr_pct:.2f})"}

            # 3. Regime Check
            regime = regime_data.get("regime", "UNKNOWN")
            if regime == "CHOPPY" and regime_data.get("confidence", 0) > 0.7:
                return {"veto": True, "reason": "High-confidence choppy market regime"}

            # 4. Spread Check (if orderbook provided)
            if orderbook:
                spread_pct = orderbook.get("spread_pct", 1.0)
                if spread_pct > 0.2: # Over 0.2% spread is usually too expensive for fast scalping
                    return {"veto": True, "reason": f"High spread: {spread_pct:.3f}%"}

            # 5. RSI Exhaustion Check (Prevent FOMO at extremes)
            rsi = indicators.get("rsi", 50)
            if rsi > 85 or rsi < 15:
                # Veto if we are at extreme exhaustion which might precede a huge move *against* the trend
                return {"veto": True, "reason": f"Extreme RSI exhaustion: {rsi:.1f}"}

            return {"veto": False, "reason": "Market conditions favorable"}

        except Exception as e:
            log.error(f"Error in signal filtering for {symbol}: {e}")
            return {"veto": True, "reason": f"Filter error: {str(e)}"}
