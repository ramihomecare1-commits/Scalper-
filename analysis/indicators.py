import pandas as pd
import numpy as np
import ta
from typing import Dict, Optional
from utils.logger import log

class TechnicalIndicators:
    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add all technical indicators to the dataframe"""
        if df.empty:
            return df
            
        try:
            df = df.copy()
            
            # RSI (14 period)
            df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
            
            # Bollinger Bands (20 period, 2 std dev)
            bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
            df['bb_high'] = bb.bollinger_hband()
            df['bb_low'] = bb.bollinger_lband()
            df['bb_mid'] = bb.bollinger_mavg()
            df['bb_width'] = (df['bb_high'] - df['bb_low']) / df['bb_mid']
            
            # Moving Averages
            df['sma_5'] = ta.trend.SMAIndicator(close=df['close'], window=5).sma_indicator()
            df['sma_10'] = ta.trend.SMAIndicator(close=df['close'], window=10).sma_indicator()
            df['ema_9'] = ta.trend.EMAIndicator(close=df['close'], window=9).ema_indicator()
            
            # VWAP (Volume Weighted Average Price)
            # Note: Standard VWAP resets daily. Here we calculate a rolling VWAP for simplicity 
            # or use the library's implementation if available. 
            # ta library vwap is often cumulative. Let's use a rolling approximation for scalping context
            # or standard calculation: cumsum(v*p) / cumsum(v)
            
            # Using a rolling 24h (approx 1440 mins) or session based VWAP is common.
            # For scalping, we might care about the session VWAP.
            # Let's implement a simple rolling VWAP for the window size
            v = df['volume'].values
            tp = (df['high'] + df['low'] + df['close']) / 3
            df['vwap'] = (tp * v).cumsum() / v.cumsum()
            
            return df
            
        except Exception as e:
            log.error(f"Error calculating indicators: {e}")
            return df

    @staticmethod
    def get_latest_indicators(df: pd.DataFrame) -> Dict:
        """Get the latest indicator values"""
        if df.empty:
            return {}
            
        try:
            last_row = df.iloc[-1]
            return {
                "rsi": float(last_row.get('rsi', 50)),
                "bb_position": TechnicalIndicators._get_bb_position(last_row),
                "trend_5_10": "UP" if last_row.get('sma_5', 0) > last_row.get('sma_10', 0) else "DOWN",
                "vwap_dist": (float(last_row['close']) - float(last_row.get('vwap', last_row['close']))) / float(last_row['close']) * 100
            }
        except Exception as e:
            log.error(f"Error getting latest indicators: {e}")
            return {}

    @staticmethod
    def _get_bb_position(row) -> str:
        """Determine price position relative to Bollinger Bands"""
        close = row['close']
        if close > row['bb_high']:
            return "ABOVE_UPPER"
        elif close < row['bb_low']:
            return "BELOW_LOWER"
        elif close > row['bb_mid']:
            return "UPPER_HALF"
        else:
            return "LOWER_HALF"
