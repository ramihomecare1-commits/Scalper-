from typing import Dict, List, Optional
from collections import deque
from config import Config
from utils.logger import log
from data.data_processor import DataProcessor

class MultiTimeframeManager:
    def __init__(self):
        self.timeframes = Config.TIMEFRAMES
        # Storage for candles: {symbol: {timeframe: deque(maxlen=100)}}
        self.data: Dict[str, Dict[str, deque]] = {}
        # Storage for latest orderbook: {symbol: data}
        self.orderbooks: Dict[str, Dict] = {}
        # Storage for latest ticker: {symbol: data}
        self.tickers: Dict[str, Dict] = {}
        
        self.window_size = 100

    def initialize_symbol(self, symbol: str):
        """Initialize storage for a symbol"""
        if symbol not in self.data:
            self.data[symbol] = {tf: deque(maxlen=self.window_size) for tf in self.timeframes}
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
                "orderbook": self.orderbooks.get(symbol, {})
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
