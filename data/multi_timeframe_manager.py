from typing import Dict, List, Optional
from collections import deque
from config import Config
from utils.logger import log
from data.data_processor import DataProcessor
import pandas as pd

class MultiTimeframeManager:
    def __init__(self):
        self.timeframes = Config.TIMEFRAMES
        # Storage for candles: {symbol: {timeframe: deque(maxlen=100)}}
        self.data: Dict[str, Dict[str, deque]] = {}
        # Storage for latest orderbook: {symbol: data}
        self.orderbooks: Dict[str, Dict] = {}
        # Storage for latest ticker: {symbol: data}
        self.tickers: Dict[str, Dict] = {}
        # Storage for sentiment data: {symbol: {metric_type: data}}
        self.sentiment: Dict[str, Dict] = {}
        # Storage for recent liquidations: {symbol: deque(maxlen=50)}
        self.liquidations: Dict[str, deque] = {}
        
        self.window_size = 100

    def initialize_symbol(self, symbol: str):
        """Initialize storage for a symbol"""
        if symbol not in self.data:
            self.data[symbol] = {tf: deque(maxlen=self.window_size) for tf in self.timeframes}
            self.sentiment[symbol] = {}
            self.liquidations[symbol] = deque(maxlen=50)
            log.info(f"Initialized data storage for {symbol}")

    def update_candle(self, symbol: str, timeframe: str, raw_candle: List[str]):
        """Update candle data"""
        if symbol not in self.data:
            self.initialize_symbol(symbol)
            
        candle = DataProcessor.normalize_candle(raw_candle)
        if not candle:
            return

        dq = self.data[symbol][timeframe]
        
        if len(dq) > 0 and dq[-1]['timestamp'] == candle['timestamp']:
            dq[-1] = candle
        else:
            dq.append(candle)

    def update_orderbook(self, symbol: str, raw_data: Dict):
        """Update orderbook snapshot"""
        self.orderbooks[symbol] = DataProcessor.normalize_orderbook(raw_data)

    def update_ticker(self, symbol: str, raw_data: Dict):
        """Update ticker data"""
        self.tickers[symbol] = DataProcessor.normalize_ticker(raw_data)

    def update_binance_ticker(self, symbol: str, data: Dict):
        """Update Binance ticker data for lead/lag (symbol is OKX format, e.g., BTC-USDT-SWAP)"""
        if symbol not in self.sentiment:
            self.initialize_symbol(symbol)
            
        try:
            last_price = float(data.get("c", 0))
            self.sentiment[symbol]["binance_ticker"] = {
                "last": last_price,
                "ts": int(data.get("E", 0))
            }
        except Exception as e:
            log.error(f"Error updating Binance ticker: {e}")

    def update_sentiment(self, symbol: str, metric_type: str, data: Dict):
        """Update sentiment data"""
        if symbol not in self.sentiment:
            self.initialize_symbol(symbol)
        self.sentiment[symbol][metric_type] = data
        
    def record_liquidation(self, symbol: str, side: str, sz: float, px: float):
        """Record a liquidation event"""
        import time
        if symbol not in self.liquidations:
            self.initialize_symbol(symbol)
        self.liquidations[symbol].append({
            "side": side,
            "sz": sz,
            "px": px,
            "ts": int(time.time() * 1000)
        })


    def get_as_df(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Get candle data as a pandas DataFrame"""
        if symbol not in self.data or timeframe not in self.data[symbol]:
            return pd.DataFrame()
            
        candles = list(self.data[symbol][timeframe])
        if not candles:
            return pd.DataFrame()
            
        df = pd.DataFrame(candles)
        # Convert numeric columns
        cols = ['open', 'high', 'low', 'close', 'volume']
        df[cols] = df[cols].apply(pd.to_numeric)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        return df

    def get_consolidated_state(self, symbol: str) -> Dict:
        """
        Get consolidated state for AI analysis
        Returns a dictionary containing lists of candles for all timeframes + current market state
        """
        if symbol not in self.data:
            return {}

        state = {
            "symbol": symbol,
            "market_data": {
                "ticker": self.tickers.get(symbol, {}),
                "orderbook": self.orderbooks.get(symbol, {}),
                "sentiment": self.sentiment.get(symbol, {}),
                "liquidations": list(self.liquidations.get(symbol, []))
            },
            "candles": {}
        }

        for tf in self.timeframes:
            candles_list = list(self.data[symbol][tf])
            state["candles"][tf] = candles_list

        return state

    def is_ready(self, symbol: str) -> bool:
        """Check if we have enough data for analysis"""
        if symbol not in self.data:
            return False
            
        # Check if we have minimum candles for all timeframes
        min_candles = 20 # Minimum required for indicators
        for tf in self.timeframes:
            if len(self.data[symbol][tf]) < min_candles:
                return False
                
        return True
