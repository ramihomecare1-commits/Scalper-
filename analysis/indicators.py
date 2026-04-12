import numpy as np
from typing import Dict, List
from utils.logger import log

class TechnicalIndicators:
    @staticmethod
    def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI using Wilder's smoothed moving average (correct method)"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Seed with SMA for the first period
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        # Apply Wilder's exponential smoothing for the rest
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
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
    def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average (full array)"""
        if len(prices) < period:
            return prices.copy()
        
        multiplier = 2.0 / (period + 1)
        ema = np.zeros_like(prices, dtype=float)
        ema[period - 1] = np.mean(prices[:period])  # Seed with SMA
        
        for i in range(period, len(prices)):
            ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]
        
        # Fill initial values with the seed
        ema[:period - 1] = ema[period - 1]
        return ema

    @staticmethod
    def calculate_macd(prices: np.ndarray, fast: int = 12, slow: int = 26, signal_period: int = 9) -> Dict:
        """Calculate MACD, Signal line, and Histogram"""
        if len(prices) < slow + signal_period:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0, "crossover": "NONE"}
        
        ema_fast = TechnicalIndicators.calculate_ema(prices, fast)
        ema_slow = TechnicalIndicators.calculate_ema(prices, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.calculate_ema(macd_line, signal_period)
        histogram = macd_line - signal_line
        
        # Detect crossover
        crossover = "NONE"
        if len(histogram) >= 2:
            if histogram[-1] > 0 and histogram[-2] <= 0:
                crossover = "BULLISH"
            elif histogram[-1] < 0 and histogram[-2] >= 0:
                crossover = "BEARISH"
        
        return {
            "macd": float(macd_line[-1]),
            "signal": float(signal_line[-1]),
            "histogram": float(histogram[-1]),
            "crossover": crossover
        }

    @staticmethod
    def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Calculate Average True Range — measures volatility"""
        if len(highs) < period + 1:
            return 0.0
        
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )
        return float(np.mean(tr[-period:]))

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
        macd = TechnicalIndicators.calculate_macd(closes)
        atr = TechnicalIndicators.calculate_atr(highs, lows, closes)
        
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
            "vwap_dist": ((current_price - vwap) / current_price * 100) if vwap > 0 else 0,
            "macd": macd["macd"],
            "macd_signal": macd["signal"],
            "macd_histogram": macd["histogram"],
            "macd_crossover": macd["crossover"],
            "atr": atr
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
