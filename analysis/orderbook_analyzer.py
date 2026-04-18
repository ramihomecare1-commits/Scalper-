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
            bids = np.array(orderbook['bids']) # [[price, size, liq, orders], ...]
            asks = np.array(orderbook['asks'])

            if len(bids) == 0 or len(asks) == 0:
                return {}

            # Calculate imbalance at multiple depths
            bid_vol_5 = np.sum(bids[:5, 1])
            ask_vol_5 = np.sum(asks[:5, 1])
            imbalance_5 = (bid_vol_5 - ask_vol_5) / (bid_vol_5 + ask_vol_5 + 1e-10)

            bid_vol_10 = np.sum(bids[:10, 1])
            ask_vol_10 = np.sum(asks[:10, 1])
            imbalance_10 = (bid_vol_10 - ask_vol_10) / (bid_vol_10 + ask_vol_10 + 1e-10)

            bid_vol_20 = np.sum(bids[:, 1])
            ask_vol_20 = np.sum(asks[:, 1])
            imbalance_20 = (bid_vol_20 - ask_vol_20) / (bid_vol_20 + ask_vol_20 + 1e-10)

            # Whale Liquidations Track (from OKX data)
            total_bid_liq = np.sum(bids[:, 2])
            total_ask_liq = np.sum(asks[:, 2])
            liq_imbalance = (total_bid_liq - total_ask_liq)

            # Find significant walls (orders > 3x average size)
            avg_bid_size = np.mean(bids[:, 1])
            avg_ask_size = np.mean(asks[:, 1])
            
            bid_walls = bids[bids[:, 1] > avg_bid_size * 3]
            ask_walls = asks[asks[:, 1] > avg_ask_size * 3]

            # Weighted Average Price of top 5 levels (Micro-price)
            # weights = size_at_level / total_size_top5
            wap_bid = np.average(bids[:5, 0], weights=bids[:5, 1])
            wap_ask = np.average(asks[:5, 0], weights=asks[:5, 1])
            micro_price = (wap_bid * ask_vol_5 + wap_ask * bid_vol_5) / (bid_vol_5 + ask_vol_5 + 1e-10)

            # Support/Resistance from walls or top level
            nearest_support = float(bid_walls[0][0]) if len(bid_walls) > 0 else float(bids[0][0])
            nearest_resistance = float(ask_walls[0][0]) if len(ask_walls) > 0 else float(asks[0][0])

            return {
                "imbalance_5": float(imbalance_5),
                "imbalance_10": float(imbalance_10),
                "imbalance_20": float(imbalance_20),
                "bid_volume_top10": float(bid_vol_10),
                "ask_volume_top10": float(ask_vol_10),
                "total_bid_liq": float(total_bid_liq),
                "total_ask_liq": float(total_ask_liq),
                "liq_imbalance": float(liq_imbalance),
                "nearest_support": nearest_support,
                "nearest_resistance": nearest_resistance,
                "spread": float(asks[0][0] - bids[0][0]),
                "spread_pct": float((asks[0][0] - bids[0][0]) / bids[0][0] * 100),
                "micro_price": float(micro_price)
            }

        except Exception as e:
            log.error(f"Error analyzing orderbook: {e}")
            return {}
