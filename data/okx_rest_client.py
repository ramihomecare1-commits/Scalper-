import requests
from typing import List, Dict, Optional
from config import Config
from utils.logger import log

class OKXMarketData:
    """REST API client for OKX market data"""
    
    def __init__(self):
        # Use demo URL if in demo mode
        self.base_url = "https://www.okx.com/api/v5" if not Config.OKX_DEMO_TRADING else "https://www.okx.com/api/v5"
        
    def get_candles(self, inst_id: str, bar: str = "1m", limit: int = 100) -> List[Dict]:
        """
        Get historical candle data via REST API
        
        Args:
            inst_id: Instrument ID (e.g., BTC-USDT, BTC-USDT-SWAP)
            bar: Timeframe (1m, 5m, 15m, 1H, 4H, 1D)
            limit: Number of candles (max 100)
        
        Returns:
            List of candle dictionaries
        """
        try:
            url = f"{self.base_url}/market/candles"
            params = {
                "instId": inst_id,
                "bar": bar,
                "limit": limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("code") != "0":
                log.error(f"OKX API error: {data.get('msg')}")
                return []
            
            # Convert OKX format to our standard format
            candles = []
            for candle_data in data.get("data", []):
                # OKX format: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
                candles.append({
                    "timestamp": int(candle_data[0]),
                    "open": float(candle_data[1]),
                    "high": float(candle_data[2]),
                    "low": float(candle_data[3]),
                    "close": float(candle_data[4]),
                    "volume": float(candle_data[5]),
                    "confirmed": candle_data[8] == "1"
                })
            
            log.info(f"Fetched {len(candles)} candles for {inst_id} ({bar})")
            return candles
            
        except Exception as e:
            log.error(f"Error fetching candles: {e}")
            return []
    
    def get_available_instruments(self, inst_type: str = "SPOT") -> List[str]:
        """
        Get list of available instruments
        
        Args:
            inst_type: SPOT, SWAP, FUTURES, OPTION
        
        Returns:
            List of instrument IDs
        """
        try:
            url = f"{self.base_url}/public/instruments"
            params = {"instType": inst_type}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("code") != "0":
                log.error(f"OKX API error: {data.get('msg')}")
                return []
            
            instruments = [inst["instId"] for inst in data.get("data", [])]
            log.info(f"Found {len(instruments)} {inst_type} instruments")
            
            return instruments
            
        except Exception as e:
            log.error(f"Error fetching instruments: {e}")
            return []
