import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
from utils.logger import log

class DataProcessor:
    @staticmethod
    def normalize_candle(data: List[str]) -> Dict:
        """
        Normalize OKX candle data to standard format
        OKX format: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        """
        try:
            return {
                "timestamp": int(data[0]),
                "open": float(data[1]),
                "high": float(data[2]),
                "low": float(data[3]),
                "close": float(data[4]),
                "volume": float(data[5]),
                "confirmed": data[8] == "1"
            }
        except Exception as e:
            log.error(f"Error normalizing candle: {e}")
            return {}

    @staticmethod
    def normalize_ticker(data: Dict) -> Dict:
        """Normalize ticker data"""
        try:
            return {
                "instId": data.get("instId"),
                "last": float(data.get("last", 0)),
                "bestBid": float(data.get("bidPx", 0)),
                "bestAsk": float(data.get("askPx", 0)),
                "volume24h": float(data.get("vol24h", 0)),
                "timestamp": int(data.get("ts", 0))
            }
        except Exception as e:
            log.error(f"Error normalizing ticker: {e}")
            return {}

    @staticmethod
    def normalize_orderbook(data: Dict) -> Dict:
        """
        Normalize order book data
        Returns top 20 bids and asks
        """
        try:
            bids = [[float(p), float(s)] for p, s, _ in data.get("bids", [])[:20]]
            asks = [[float(p), float(s)] for p, s, _ in data.get("asks", [])[:20]]
            
            return {
                "instId": data.get("instId"),
                "bids": bids,
                "asks": asks,
                "timestamp": int(data.get("ts", 0))
            }
        except Exception as e:
            log.error(f"Error normalizing orderbook: {e}")
            return {}

    @staticmethod
    def create_dataframe(candles: List[Dict]) -> pd.DataFrame:
        """Convert list of normalized candles to DataFrame"""
        if not candles:
            return pd.DataFrame()
            
        df = pd.DataFrame(candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        return df
