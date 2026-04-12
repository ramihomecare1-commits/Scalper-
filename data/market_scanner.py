import requests
from typing import List
from config import Config
from utils.logger import log

class MarketScanner:
    """Scans OKX for top liquid instruments dynamically"""
    
    def __init__(self):
        self.base_url = "https://www.okx.com/api/v5"
        # Coins we don't want to trade. We ignore stablecoins as base currencies, 
        # fiat-pegged tokens, and wrapped pairs with low volatility.
        self.EXCLUDED_BASE_COINS = {
            "USDC", "USDE", "FDUSD", "DAI", "TUSD", "BUSD", "USDD", 
            "EURT", "EUR", "GBP", "JPY", "WETH", "WBTC", "WSOL"
        }

    def get_top_pairs(self, limit: int = 100, inst_type: str = None) -> List[str]:
        """
        Fetch top pairs by 24h volume.
        """
        inst_type = inst_type or Config.TRADING_MODE
        log.info(f"Scanning OKX for top {limit} {inst_type} pairs by volume...")
        
        try:
            url = f"{self.base_url}/market/tickers"
            params = {"instType": inst_type}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") != "0":
                log.error(f"OKX API error fetching tickers: {data.get('msg')}")
                return []
            
            valid_pairs = []
            
            for ticker in data.get("data", []):
                inst_id = ticker.get("instId", "")
                
                # We only want pairs quoted in USDT for simplicity and liquidity
                if "-USDT" not in inst_id:
                    continue
                
                # Extract the base coin (e.g. BTC from BTC-USDT-SWAP)
                base_coin = inst_id.split("-")[0]
                if base_coin in self.EXCLUDED_BASE_COINS:
                    continue
                
                vol24h = float(ticker.get("volCcy24h", 0))
                
                valid_pairs.append({
                    "instId": inst_id,
                    "vol": vol24h
                })
            
            # Sort by 24h quote currency volume descending
            valid_pairs.sort(key=lambda x: x["vol"], reverse=True)
            
            # Take the top 'limit' pairs
            top_symbols = [p["instId"] for p in valid_pairs[:limit]]
            
            log.info(f"Successfully found top {len(top_symbols)} liquid symbols.")
            return top_symbols
            
        except Exception as e:
            log.error(f"Error scanning markets: {e}")
            # Fallback to configured default pairs if scanning fails
            return Config.TRADING_PAIRS

