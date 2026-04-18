import requests
from typing import Dict, List, Optional
from config import Config
from utils.logger import log
from utils.circuit_breaker import with_circuit_breaker_sync


class OKXSentimentClient:
    """
    REST API client for OKX sentiment and market intelligence data.
    Covers: Funding Rate, Open Interest, Long/Short Ratio,
    Taker Volume, Mark Price, and Recent Trades.
    """

    def __init__(self):
        self.base_url = "https://www.okx.com/api/v5"
        self.timeout = 10

    # ------------------------------------------------------------------ #
    #  P1 – Public endpoints (20 req / 2s)
    # ------------------------------------------------------------------ #

    @with_circuit_breaker_sync("OKX_REST")
    def get_funding_rate(self, inst_id: str) -> Optional[Dict]:
        """
        Current funding rate for a perpetual SWAP.
        Positive = longs pay shorts (overleveraged long).
        """
        try:
            url = f"{self.base_url}/public/funding-rate"
            resp = requests.get(url, params={"instId": inst_id}, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "0" or not data.get("data"):
                return None

            item = data["data"][0]
            return {
                "instId": item.get("instId"),
                "fundingRate": float(item.get("fundingRate", 0)),
                "nextFundingRate": float(item.get("nextFundingRate", 0)) if item.get("nextFundingRate") else None,
                "fundingTime": int(item.get("fundingTime", 0)),
                "nextFundingTime": int(item.get("nextFundingTime", 0)) if item.get("nextFundingTime") else None,
            }
        except Exception as e:
            log.error(f"Error fetching funding rate for {inst_id}: {e}")
            return None

    @with_circuit_breaker_sync("OKX_REST")
    def get_open_interest(self, inst_id: str) -> Optional[Dict]:
        """
        Open interest for a SWAP instrument.
        Rising OI + rising price = trend continuation.
        Rising OI + falling price = aggressive shorts building.
        """
        try:
            url = f"{self.base_url}/public/open-interest"
            resp = requests.get(
                url,
                params={"instType": "SWAP", "instId": inst_id},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "0" or not data.get("data"):
                return None

            item = data["data"][0]
            return {
                "instId": item.get("instId"),
                "oi": float(item.get("oi", 0)),          # Open interest in contracts
                "oiCcy": float(item.get("oiCcy", 0)),    # OI in base currency
                "ts": int(item.get("ts", 0)),
            }
        except Exception as e:
            log.error(f"Error fetching open interest for {inst_id}: {e}")
            return None

    @with_circuit_breaker_sync("OKX_REST")
    def get_mark_price(self, inst_id: str) -> Optional[Dict]:
        """
        Mark price used by OKX for liquidations.
        Divergence between last price and mark price predicts forced moves.
        """
        try:
            url = f"{self.base_url}/public/mark-price"
            resp = requests.get(
                url,
                params={"instType": "SWAP", "instId": inst_id},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "0" or not data.get("data"):
                return None

            item = data["data"][0]
            return {
                "instId": item.get("instId"),
                "markPx": float(item.get("markPx", 0)),
                "ts": int(item.get("ts", 0)),
            }
        except Exception as e:
            log.error(f"Error fetching mark price for {inst_id}: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  P2 – Rubik / Trading-data endpoints (5 req / 2s – cache results)
    # ------------------------------------------------------------------ #

    @with_circuit_breaker_sync("OKX_RUBIK")
    def get_long_short_ratio(self, inst_id: str, period: str = "5m") -> Optional[Dict]:
        """
        Long/short account ratio for a SWAP instrument.
        >65% long = crowded long (contrarian short signal).
        >65% short = crowded short (contrarian long signal).
        """
        try:
            url = f"{self.base_url}/rubik/stat/contracts/long-short-account-ratio"
            resp = requests.get(
                url,
                params={"instId": inst_id, "period": period},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "0" or not data.get("data"):
                return None

            # Returns array of [ts, longShortRatio] – take most recent
            item = data["data"][0]
            ratio = float(item[1]) if len(item) > 1 else 1.0
            # OKX returns ratio as long/short (e.g., 2.0 means 2:1 longs to shorts)
            long_pct = (ratio / (1 + ratio)) * 100
            short_pct = 100 - long_pct

            return {
                "instId": inst_id,
                "ratio": ratio,
                "longPct": round(long_pct, 1),
                "shortPct": round(short_pct, 1),
                "ts": int(item[0]) if item else 0,
            }
        except Exception as e:
            log.error(f"Error fetching long/short ratio for {inst_id}: {e}")
            return None

    @with_circuit_breaker_sync("OKX_RUBIK")
    def get_taker_volume(self, ccy: str, inst_type: str = "SWAP", period: str = "5m") -> Optional[Dict]:
        """
        Taker buy vs sell volume.
        Taker buy > sell = aggressive buyers crossing the spread (bullish).
        """
        try:
            url = f"{self.base_url}/rubik/stat/taker-volume"
            resp = requests.get(
                url,
                params={"ccy": ccy, "instType": inst_type, "period": period},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "0" or not data.get("data"):
                return None

            # Returns [ts, sellVol, buyVol]
            item = data["data"][0]
            sell_vol = float(item[1]) if len(item) > 1 else 0
            buy_vol = float(item[2]) if len(item) > 2 else 0
            total = sell_vol + buy_vol

            return {
                "ccy": ccy,
                "sellVol": sell_vol,
                "buyVol": buy_vol,
                "buyRatio": round(buy_vol / total, 3) if total > 0 else 0.5,
                "ts": int(item[0]) if item else 0,
            }
        except Exception as e:
            log.error(f"Error fetching taker volume for {ccy}: {e}")
            return None

    @with_circuit_breaker_sync("OKX_RUBIK")
    def get_options_put_call_ratio(self, base_ccy: str) -> Optional[Dict]:
        """
        Options open interest volume ratio (Put/Call Ratio).
        >1.0 implies bearish hedging by smart money.
        base_ccy must be 'BTC' or 'ETH'.
        """
        try:
            url = f"{self.base_url}/rubik/stat/option/open-interest-volume-ratio"
            resp = requests.get(
                url,
                params={"ccy": base_ccy, "period": "5m"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "0" or not data.get("data"):
                return None

            # Returns [ts, oiRatio, volRatio]
            item = data["data"][0]
            oi_ratio = float(item[1]) if len(item) > 1 else 1.0 # Put/Call ratio
            
            return {
                "ccy": base_ccy,
                "putCallRatio": oi_ratio,
                "ts": int(item[0]) if item else 0,
            }
        except Exception as e:
            log.error(f"Error fetching put/call ratio for {base_ccy}: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  P3 – Recent trades for whale detection
    # ------------------------------------------------------------------ #

    @with_circuit_breaker_sync("OKX_REST")
    def get_recent_trades(self, inst_id: str, limit: int = 100) -> Optional[Dict]:
        """
        Fetch recent individual trades to detect whale activity.
        Returns summary statistics rather than raw trades to save memory.
        """
        try:
            url = f"{self.base_url}/market/trades"
            resp = requests.get(
                url,
                params={"instId": inst_id, "limit": limit},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "0" or not data.get("data"):
                return None

            trades = data["data"]
            if not trades:
                return None

            # Analyze trade flow
            sizes = [float(t.get("sz", 0)) for t in trades]
            buy_vol = sum(float(t.get("sz", 0)) for t in trades if t.get("side") == "buy")
            sell_vol = sum(float(t.get("sz", 0)) for t in trades if t.get("side") == "sell")

            # Whale detection: trades > 3x average size
            avg_size = sum(sizes) / len(sizes) if sizes else 0
            whale_threshold = avg_size * 3
            whale_trades = [t for t in trades if float(t.get("sz", 0)) > whale_threshold]

            whale_buy_vol = sum(float(t.get("sz", 0)) for t in whale_trades if t.get("side") == "buy")
            whale_sell_vol = sum(float(t.get("sz", 0)) for t in whale_trades if t.get("side") == "sell")

            return {
                "instId": inst_id,
                "totalTrades": len(trades),
                "buyVol": buy_vol,
                "sellVol": sell_vol,
                "buyPressure": round(buy_vol / (buy_vol + sell_vol), 3) if (buy_vol + sell_vol) > 0 else 0.5,
                "whaleTradeCount": len(whale_trades),
                "whaleBuyVol": whale_buy_vol,
                "whaleSellVol": whale_sell_vol,
                "whaleBias": "BUY" if whale_buy_vol > whale_sell_vol else ("SELL" if whale_sell_vol > whale_buy_vol else "NEUTRAL"),
                "avgTradeSize": round(avg_size, 4),
                "maxTradeSize": round(max(sizes), 4) if sizes else 0,
            }
        except Exception as e:
            log.error(f"Error fetching recent trades for {inst_id}: {e}")
            return None
