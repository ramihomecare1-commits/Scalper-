from typing import Dict, List, Tuple
import numpy as np
from utils.logger import log

class OrderBookAnalyzer:
    @staticmethod
    def analyze(orderbook: Dict) -> Dict:
        """
        Analyze order book for support/resistance and imbalance
        """
        if not orderbook or 'bids' not in orderbook or 'asks' not in orderbook:
            return {}

        try:
            bids = np.array(orderbook['bids']) # [[price, size], ...]
            asks = np.array(orderbook['asks'])

            if len(bids) == 0 or len(asks) == 0:
                return {}

            # Calculate imbalance
            # Volume of top 10 levels
            bid_vol = np.sum(bids[:10, 1])
            ask_vol = np.sum(asks[:10, 1])
            
            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol) # Range -1 to 1

            # Find significant walls (orders > 2x average size)
            avg_bid_size = np.mean(bids[:, 1])
            avg_ask_size = np.mean(asks[:, 1])
            
            bid_walls = bids[bids[:, 1] > avg_bid_size * 2]
            ask_walls = asks[asks[:, 1] > avg_ask_size * 2]

            # Weighted Average Price of top 5 levels
            wap_bid = np.average(bids[:5, 0], weights=bids[:5, 1])
            wap_ask = np.average(asks[:5, 0], weights=asks[:5, 1])

            return {
                "imbalance": float(imbalance),
                "bid_volume_top10": float(bid_vol),
                "ask_volume_top10": float(ask_vol),
                "nearest_support": float(bid_walls[0][0]) if len(bid_walls) > 0 else float(bids[0][0]),
                "nearest_resistance": float(ask_walls[0][0]) if len(ask_walls) > 0 else float(asks[0][0]),
                "spread": float(asks[0][0] - bids[0][0]),
                "micro_price": (wap_bid + wap_ask) / 2
            }

        except Exception as e:
            log.error(f"Error analyzing orderbook: {e}")
            return {}
