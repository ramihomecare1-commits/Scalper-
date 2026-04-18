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
                "last": float(data.get("last") or 0),
                "bestBid": float(data.get("bidPx") or 0),
                "bestAsk": float(data.get("askPx") or 0),
                "volume24h": float(data.get("vol24h") or 0),
                "timestamp": int(data.get("ts") or 0)
            }
        except Exception as e:
            log.error(f"Error normalizing ticker: {e}")
            return {}

    @staticmethod
    def normalize_orderbook(data: Dict) -> Dict:
        """
        Normalize order book data
        Returns top 20 bids and asks with liquidation data
        OKX format: [price, size, liquidated_orders, num_orders]
        """
        try:
            # Extract full data: [price, size, liquidated_orders, num_orders]
            bids = []
            for b in data.get("bids", [])[:20]:
                # Handle potentially empty values
                price = float(b[0] or 0)
                size = float(b[1] or 0)
                liq = float(b[2] or 0) if len(b) > 2 else 0.0
                orders = int(b[3] or 0) if len(b) > 3 else 0
                bids.append([price, size, liq, orders])

            asks = []
            for a in data.get("asks", [])[:20]:
                price = float(a[0] or 0)
                size = float(a[1] or 0)
                liq = float(a[2] or 0) if len(a) > 2 else 0.0
                orders = int(a[3] or 0) if len(a) > 3 else 0
                asks.append([price, size, liq, orders])
            
            return {
                "instId": data.get("instId"),
                "bids": bids,
                "asks": asks,
                "timestamp": int(data.get("ts", 0))
            }
        except Exception as e:
            log.error(f"Error normalizing orderbook: {e}")
            return {}
