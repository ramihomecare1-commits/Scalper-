import numpy as np
from typing import Dict, List
from utils.logger import log

class TechnicalIndicators:
    @staticmethod
    def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI using numpy"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    @staticmethod
    def calculate_sma(prices: np.ndarray, period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return float(prices[-1]) if len(prices) > 0 else 0.0
        return float(np.mean(prices[-period:]))

    @staticmethod
    def calculate_bollinger_bands(prices: np.ndarray, period: int = 20, std_dev: int = 2) -> Dict:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return {"upper": 0, "middle": 0, "lower": 0}
        
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        return {
            "upper": float(sma + (std_dev * std)),
            "middle": float(sma),
            "lower": float(sma - (std_dev * std))
        }

    @staticmethod
    def calculate_vwap(prices: np.ndarray, volumes: np.ndarray) -> float:
        """Calculate VWAP"""
        if len(prices) == 0 or len(volumes) == 0:
            return 0.0
        
        return float(np.sum(prices * volumes) / np.sum(volumes))

    @staticmethod
    def analyze_candles(candles: List[Dict]) -> Dict:
        """Analyze candles and return indicators"""
        if not candles or len(candles) < 20:
            return {}
        
        closes = np.array([c['close'] for c in candles])
        volumes = np.array([c['volume'] for c in candles])
        highs = np.array([c['high'] for c in candles])
        lows = np.array([c['low'] for c in candles])
        
        # Calculate typical price for VWAP
        typical_prices = (highs + lows + closes) / 3
        
        rsi = TechnicalIndicators.calculate_rsi(closes)
        sma_5 = TechnicalIndicators.calculate_sma(closes, 5)
        sma_10 = TechnicalIndicators.calculate_sma(closes, 10)
        bb = TechnicalIndicators.calculate_bollinger_bands(closes)
        vwap = TechnicalIndicators.calculate_vwap(typical_prices, volumes)
        
        current_price = float(closes[-1])
        
        return {
            "rsi": rsi,
            "sma_5": sma_5,
            "sma_10": sma_10,
            "trend": "UP" if sma_5 > sma_10 else "DOWN",
            "bb_upper": bb["upper"],
            "bb_middle": bb["middle"],
            "bb_lower": bb["lower"],
            "bb_position": TechnicalIndicators._get_bb_position(current_price, bb),
            "vwap": vwap,
            "vwap_dist": ((current_price - vwap) / current_price * 100) if vwap > 0 else 0
        }

    @staticmethod
    def _get_bb_position(price: float, bb: Dict) -> str:
        """Determine price position relative to Bollinger Bands"""
        if price > bb["upper"]:
            return "ABOVE_UPPER"
        elif price < bb["lower"]:
            return "BELOW_LOWER"
        elif price > bb["middle"]:
            return "UPPER_HALF"
        else:
            return "LOWER_HALF"
