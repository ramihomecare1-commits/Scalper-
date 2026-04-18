from typing import Dict, List
import numpy as np
from analysis.indicators import TechnicalIndicators
from utils.logger import log

class MarketRegimeDetector:
    """
    Classifies the current market state (Strong Trend, Choppy, Mean-Reverting)
    to help Strategy Agent decide on the best approach.
    """
    
    @staticmethod
    def identify_regime(candles: List[Dict]) -> Dict:
        """
        Identify the current market regime based on indicators.
        """
        if not candles or len(candles) < 50:
            return {"regime": "UNKNOWN", "confidence": 0.0}

        try:
            indicators = TechnicalIndicators.analyze_candles(candles)
            if not indicators:
                return {"regime": "UNKNOWN", "confidence": 0.0}

            adx = indicators.get("adx", 0)
            rsi = indicators.get("rsi", 50)
            ema_20 = indicators.get("ema_20", 0)
            ema_50 = indicators.get("ema_50", 0)
            ema_100 = indicators.get("ema_100", 0)
            bb_pct_b = indicators.get("bb_pct_b", 0.5)
            vwap_dist = indicators.get("vwap_dist", 0)
            atr_pct = indicators.get("atr_pct", 0)
            
            # 1. Strong Trend Detection
            # ADX > 25 indicates a strong trend. 
            # EMA stacking (20 > 50 > 100 or 20 < 50 < 100) confirms it.
            is_bullish_stack = ema_20 > ema_50 > ema_100
            is_bearish_stack = ema_20 < ema_50 < ema_100
            
            if adx > 25 and (is_bullish_stack or is_bearish_stack):
                return {
                    "regime": "TRENDING",
                    "sub_type": "BULLISH_TREND" if is_bullish_stack else "BEARISH_TREND",
                    "confidence": float(min(adx / 50, 1.0)),
                    "adx": adx
                }

            # 2. Mean-Reverting / Exhaustion Detection
            # Extreme RSI (>75 or <25) + Extreme BB Position (<0 or >1) + High distance from VWAP
            if (rsi > 75 or rsi < 25) and (bb_pct_b > 1.0 or bb_pct_b < 0.0) and abs(vwap_dist) > 0.5:
                return {
                    "regime": "MEAN_REVERTING",
                    "sub_type": "OVERBOUGHT" if rsi > 70 else "OVERSOLD",
                    "confidence": 0.8,
                    "rsi": rsi,
                    "vwap_dist": vwap_dist
                }

            # 3. Choppy / Range-Bound Detection
            # ADX < 20 or intersecting EMAs
            is_intersecting = not (is_bullish_stack or is_bearish_stack)
            if adx < 20 or (adx < 25 and is_intersecting):
                return {
                    "regime": "CHOPPY",
                    "sub_type": "CONSOLIDATION",
                    "confidence": float(1.0 - (adx / 25)),
                    "adx": adx
                }

            # 4. Volatile / Transitioning
            # High ATR but no clear trend
            if atr_pct > 1.5 and adx < 25:
                 return {
                    "regime": "VOLATILE",
                    "sub_type": "TRANSITION",
                    "confidence": 0.6,
                    "atr_pct": atr_pct
                }

            # Default to Neutral/Trending but weak
            return {
                "regime": "NEUTRAL",
                "sub_type": "SIDEWAYS",
                "confidence": 0.5
            }

        except Exception as e:
            log.error(f"Error detecting market regime: {e}")
            return {"regime": "ERROR", "confidence": 0.0}
