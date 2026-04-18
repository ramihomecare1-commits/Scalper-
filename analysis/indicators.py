import numpy as np
from typing import Dict, List, Optional
from utils.logger import log


class TechnicalIndicators:
    # ──────────────────────────────────────────────────────────────────────────
    # Core building blocks
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
        """RSI via Wilder's smoothed moving average (industry-standard)."""
        if len(prices) < period + 1:
            return 50.0

        deltas = np.diff(prices)
        gains  = np.where(deltas > 0,  deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # Seed with SMA over the first period
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        # Wilder's exponential smoothing
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs  = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    @staticmethod
    def calculate_sma(prices: np.ndarray, period: int) -> float:
        """Simple Moving Average of the last `period` bars."""
        if len(prices) < period:
            return float(prices[-1]) if len(prices) > 0 else 0.0
        return float(np.mean(prices[-period:]))

    @staticmethod
    def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
        """
        Full EMA array seeded with SMA for the first warm-up window.
        Positions before warm-up are backfilled with the seed value so
        downstream callers that consume `ema[-1]` always get a valid number.
        """
        if len(prices) < period:
            return prices.copy().astype(float)

        multiplier = 2.0 / (period + 1)
        ema = np.zeros(len(prices), dtype=float)
        ema[period - 1] = np.mean(prices[:period])          # SMA seed

        for i in range(period, len(prices)):
            ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]

        ema[:period - 1] = ema[period - 1]                  # backfill warm-up
        return ema

    @staticmethod
    def _wilder_rma(x: np.ndarray, n: int) -> np.ndarray:
        """
        Wilder's Running Moving Average (RMA) — also known as SMMA.
        Used internally by ADX and ATR calculations.
        """
        result = np.zeros(len(x), dtype=float)
        result[n - 1] = np.mean(x[:n])
        for i in range(n, len(x)):
            result[i] = (result[i - 1] * (n - 1) + x[i]) / n
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Momentum & trend
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_macd(
        prices: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal_period: int = 9,
    ) -> Dict:
        """MACD line, Signal line, Histogram, and crossover label."""
        if len(prices) < slow + signal_period:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0, "crossover": "NONE"}

        ema_fast = TechnicalIndicators.calculate_ema(prices, fast)
        ema_slow = TechnicalIndicators.calculate_ema(prices, slow)
        macd_line   = ema_fast - ema_slow
        signal_line = TechnicalIndicators.calculate_ema(macd_line, signal_period)
        histogram   = macd_line - signal_line

        crossover = "NONE"
        if len(histogram) >= 2:
            if histogram[-1] > 0 and histogram[-2] <= 0:
                crossover = "BULLISH"
            elif histogram[-1] < 0 and histogram[-2] >= 0:
                crossover = "BEARISH"

        return {
            "macd":      float(macd_line[-1]),
            "signal":    float(signal_line[-1]),
            "histogram": float(histogram[-1]),
            "crossover": crossover,
        }

    @staticmethod
    def calculate_adx(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        period: int = 14,
    ) -> float:
        """Average Directional Index (ADX) — measures trend strength, not direction."""
        if len(highs) < period * 2 + 1:
            return 20.0

        up_move   = highs[1:] - highs[:-1]
        down_move = lows[:-1]  - lows[1:]

        plus_dm  = np.where((up_move > down_move)  & (up_move > 0),   up_move,   0.0)
        minus_dm = np.where((down_move > up_move)  & (down_move > 0), down_move, 0.0)

        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:]  - closes[:-1])
        tr  = np.maximum.reduce([tr1, tr2, tr3])

        atr_rma = TechnicalIndicators._wilder_rma(tr, period)

        with np.errstate(divide="ignore", invalid="ignore"):
            plus_di  = 100 * TechnicalIndicators._wilder_rma(plus_dm, period) / atr_rma
            minus_di = 100 * TechnicalIndicators._wilder_rma(minus_dm, period) / atr_rma
            plus_di  = np.nan_to_num(plus_di)
            minus_di = np.nan_to_num(minus_di)

            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
            dx = np.nan_to_num(dx)

        adx = TechnicalIndicators._wilder_rma(dx, period)
        return float(adx[-1])

    # ──────────────────────────────────────────────────────────────────────────
    # Volatility
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_atr(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        period: int = 14,
    ) -> float:
        """ATR via Wilder's RMA (identical to TradingView default)."""
        if len(highs) < period + 1:
            return 0.0

        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:]  - closes[:-1])
        tr  = np.maximum.reduce([tr1, tr2, tr3])

        atr_arr = TechnicalIndicators._wilder_rma(tr, period)
        return float(atr_arr[-1])

    @staticmethod
    def calculate_bollinger_bands(
        prices: np.ndarray,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> Dict:
        """Bollinger Bands — upper, middle (SMA), lower, bandwidth, %B."""
        if len(prices) < period:
            mid = float(prices[-1]) if len(prices) > 0 else 0.0
            return {
                "upper": mid, "middle": mid, "lower": mid,
                "bandwidth": 0.0, "pct_b": 0.5,
            }

        window = prices[-period:]
        sma    = float(np.mean(window))
        std    = float(np.std(window, ddof=0))   # population std — matches TradingView

        upper = sma + std_dev * std
        lower = sma - std_dev * std
        bw    = (upper - lower) / sma if sma != 0 else 0.0

        price     = float(prices[-1])
        band_rng  = upper - lower
        pct_b     = ((price - lower) / band_rng) if band_rng != 0 else 0.5

        return {
            "upper":     upper,
            "middle":    sma,
            "lower":     lower,
            "bandwidth": float(bw),
            "pct_b":     float(pct_b),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Volume-weighted
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_vwap(prices: np.ndarray, volumes: np.ndarray) -> float:
        """VWAP over supplied bars (session-agnostic rolling VWAP)."""
        total_vol = np.sum(volumes)
        if total_vol == 0:
            return 0.0
        return float(np.sum(prices * volumes) / total_vol)

    # ──────────────────────────────────────────────────────────────────────────
    # Ichimoku Cloud (full, pure Numpy)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_ichimoku(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        tenkan_period: int = 9,
        kijun_period:  int = 26,
        senkou_b_period: int = 52,
    ) -> Dict:
        """
        Full Ichimoku Cloud.

        Returns (all scalars for the *current* bar):
          tenkan_sen   — Conversion Line  (9-period mid-point)
          kijun_sen    — Base Line        (26-period mid-point)
          senkou_a     — Leading Span A   (avg of Tenkan + Kijun, projected +26)
          senkou_b     — Leading Span B   (52-period mid-point, projected +26)
          chikou_span  — Lagging Span     (close shifted -26 into the past)
          cloud_top    — max(senkou_a, senkou_b) at current bar
          cloud_bottom — min(senkou_a, senkou_b) at current bar
          price_vs_cloud — 'ABOVE' | 'INSIDE' | 'BELOW'
          signal       — 'BULLISH' | 'BEARISH' | 'NEUTRAL'
        """
        n = len(closes)
        needed = senkou_b_period
        if n < needed:
            price = float(closes[-1]) if n > 0 else 0.0
            return {
                "tenkan_sen": price, "kijun_sen": price,
                "senkou_a": price,   "senkou_b": price,
                "chikou_span": price,
                "cloud_top": price,  "cloud_bottom": price,
                "price_vs_cloud": "NEUTRAL", "signal": "NEUTRAL",
            }

        def _mid(h, l, period, idx):
            """Highest-high / lowest-low midpoint over last `period` bars ending at `idx`."""
            start = max(0, idx - period + 1)
            return (float(np.max(h[start:idx + 1])) + float(np.min(l[start:idx + 1]))) / 2

        i = n - 1  # latest bar index

        tenkan = _mid(highs, lows, tenkan_period, i)
        kijun  = _mid(highs, lows, kijun_period,  i)

        # Senkou A/B are computed at bar (i - 26) so they "arrive" at the
        # current bar after the 26-bar displacement — exactly how TradingView does it.
        disp = kijun_period  # 26
        if i >= disp:
            j = i - disp
            senkou_a = (_mid(highs, lows, tenkan_period, j) + _mid(highs, lows, kijun_period, j)) / 2
            senkou_b = _mid(highs, lows, senkou_b_period, j)
        else:
            senkou_a = (tenkan + kijun) / 2
            senkou_b = _mid(highs, lows, senkou_b_period, i)

        # Chikou span = today's close plotted 26 bars ago (gives us a simple look-back value)
        chikou_idx   = max(0, i - disp)
        chikou_price = float(closes[chikou_idx])   # the price that the Chikou overlaps

        cloud_top    = max(senkou_a, senkou_b)
        cloud_bottom = min(senkou_a, senkou_b)
        price        = float(closes[-1])

        if price > cloud_top:
            pvcloud = "ABOVE"
        elif price < cloud_bottom:
            pvcloud = "BELOW"
        else:
            pvcloud = "INSIDE"

        # Simple TK cross signal
        if tenkan > kijun and pvcloud == "ABOVE":
            signal = "BULLISH"
        elif tenkan < kijun and pvcloud == "BELOW":
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        return {
            "tenkan_sen":    tenkan,
            "kijun_sen":     kijun,
            "senkou_a":      senkou_a,
            "senkou_b":      senkou_b,
            "chikou_span":   chikou_price,
            "cloud_top":     cloud_top,
            "cloud_bottom":  cloud_bottom,
            "price_vs_cloud": pvcloud,
            "signal":        signal,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Volume analysis helper
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_volume_trend(volumes: np.ndarray, period: int = 20) -> Dict:
        """
        Compare current volume against its SMA to detect volume surges or droughts.
        Returns:
          vol_sma   — simple moving average of volume
          vol_ratio — current / sma (1.0 = average, 2.0 = double)
          label     — 'HIGH' | 'AVERAGE' | 'LOW'
        """
        if len(volumes) < period:
            return {"vol_sma": 0.0, "vol_ratio": 1.0, "label": "AVERAGE"}

        vol_sma   = float(np.mean(volumes[-period:]))
        current   = float(volumes[-1])
        ratio     = (current / vol_sma) if vol_sma > 0 else 1.0

        if ratio > 1.5:
            label = "HIGH"
        elif ratio < 0.6:
            label = "LOW"
        else:
            label = "AVERAGE"

        return {"vol_sma": vol_sma, "vol_ratio": round(ratio, 3), "label": label}

    # ──────────────────────────────────────────────────────────────────────────
    # Master analysis entry-point
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def analyze_candles(candles: List[Dict]) -> Dict:
        """
        Full indicator suite for a list of OHLCV candle dicts.
        Requires at least 52 candles for Ichimoku; returns {} if fewer than 20.
        """
        if not candles or len(candles) < 20:
            return {}

        closes  = np.array([c["close"]  for c in candles], dtype=float)
        volumes = np.array([c["volume"] for c in candles], dtype=float)
        highs   = np.array([c["high"]   for c in candles], dtype=float)
        lows    = np.array([c["low"]    for c in candles], dtype=float)

        typical_prices = (highs + lows + closes) / 3

        # -- Indicators --
        rsi        = TechnicalIndicators.calculate_rsi(closes)
        sma_5      = TechnicalIndicators.calculate_sma(closes, 5)
        sma_10     = TechnicalIndicators.calculate_sma(closes, 10)
        ema_20     = float(TechnicalIndicators.calculate_ema(closes, 20)[-1])
        ema_50     = float(TechnicalIndicators.calculate_ema(closes, 50)[-1])
        ema_100    = float(TechnicalIndicators.calculate_ema(closes, 100)[-1]) if len(closes) >= 100 else ema_50
        adx        = TechnicalIndicators.calculate_adx(highs, lows, closes)
        atr        = TechnicalIndicators.calculate_atr(highs, lows, closes)
        bb         = TechnicalIndicators.calculate_bollinger_bands(closes)
        vwap       = TechnicalIndicators.calculate_vwap(typical_prices, volumes)
        macd       = TechnicalIndicators.calculate_macd(closes)
        ichimoku   = TechnicalIndicators.calculate_ichimoku(highs, lows, closes)
        vol_trend  = TechnicalIndicators.calculate_volume_trend(volumes)

        current_price = float(closes[-1])

        # -- EMA trend label --
        if ema_20 > ema_50 * 1.002 and ema_50 > ema_100 * 1.0005:
            trend = "BULLISH"
        elif ema_20 < ema_50 * 0.998 and ema_50 < ema_100 * 0.9995:
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"

        # -- ATR as % of price --
        atr_pct = (atr / current_price * 100) if current_price > 0 else 0.0

        return {
            # Momentum
            "rsi":                rsi,
            "macd":               macd["macd"],
            "macd_signal":        macd["signal"],
            "macd_histogram":     macd["histogram"],
            "macd_crossover":     macd["crossover"],
            # Trend
            "ema_20":             ema_20,
            "ema_50":             ema_50,
            "ema_100":            ema_100,
            "sma_5":              sma_5,
            "sma_10":             sma_10,
            "adx":                adx,
            "trend":              trend,
            # Volatility
            "atr":                atr,
            "atr_pct":            round(atr_pct, 4),
            "bb_upper":           bb["upper"],
            "bb_middle":          bb["middle"],
            "bb_lower":           bb["lower"],
            "bb_bandwidth":       bb["bandwidth"],
            "bb_pct_b":           bb["pct_b"],
            "bb_position":        TechnicalIndicators._get_bb_position(current_price, bb),
            # Volume-weighted
            "vwap":               vwap,
            "vwap_dist":          round(((current_price - vwap) / current_price * 100), 4) if vwap > 0 else 0.0,
            # Ichimoku
            "ichimoku_tenkan":    ichimoku["tenkan_sen"],
            "ichimoku_kijun":     ichimoku["kijun_sen"],
            "ichimoku_senkou_a":  ichimoku["senkou_a"],
            "ichimoku_senkou_b":  ichimoku["senkou_b"],
            "ichimoku_cloud_top": ichimoku["cloud_top"],
            "ichimoku_cloud_bot": ichimoku["cloud_bottom"],
            "ichimoku_pvcloud":   ichimoku["price_vs_cloud"],
            "ichimoku_signal":    ichimoku["signal"],
            # Volume
            "vol_ratio":          vol_trend["vol_ratio"],
            "vol_label":          vol_trend["label"],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_bb_position(price: float, bb: Dict) -> str:
        """Candle position relative to Bollinger Bands."""
        if price > bb["upper"]:
            return "ABOVE_UPPER"
        elif price < bb["lower"]:
            return "BELOW_LOWER"
        elif price > bb["middle"]:
            return "UPPER_HALF"
        else:
            return "LOWER_HALF"
