import asyncio
import signal
import sys
from typing import List
from config import Config
from utils.logger import log
from data.okx_websocket import OKXWebSocket
from data.multi_timeframe_manager import MultiTimeframeManager
from analysis.indicators import TechnicalIndicators
from analysis.orderbook_analyzer import OrderBookAnalyzer
from ai.decision_engine import DecisionEngine
from trading.order_executor import OrderExecutor

class ScalpingBot:
    def __init__(self):
        self.running = False
        self.ws = OKXWebSocket()
        self.mtf_manager = MultiTimeframeManager()
        self.decision_engine = DecisionEngine()
        self.executor = OrderExecutor()
        self.symbols = Config.TRADING_PAIRS

    async def start(self):
        """Start the bot"""
        self.running = True
        log.info("Starting AI Scalping Bot...")
        
        # 1. Connect to WebSocket
        await self.ws.connect()
        
        # 2. Subscribe to channels
        channels = []
        for symbol in self.symbols:
            # Candles for all timeframes
            for tf in Config.TIMEFRAMES:
                channels.append({"channel": f"candle{tf}", "instId": symbol})
            
            # Orderbook (Books-5 is lighter, Books-l2-tgn is full)
            # Using books5 for speed/simplicity in this demo, or books for full depth
            channels.append({"channel": "books5", "instId": symbol})
            
            # Ticker
            channels.append({"channel": "tickers", "instId": symbol})

        await self.ws.subscribe(channels)
        
        # 3. Register callbacks
        self.ws.add_callback("candle", None, self._handle_candle)
        self.ws.add_callback("books5", None, self._handle_orderbook)
        self.ws.add_callback("tickers", None, self._handle_ticker)

        # 4. Main Loop
        await self._main_loop()

    async def _handle_candle(self, msg: dict):
        """Handle incoming candle data"""
        try:
            arg = msg.get("arg", {})
            data = msg.get("data", [])
            
            channel = arg.get("channel", "")
            symbol = arg.get("instId")
            
            # Extract timeframe from channel (e.g., "candle1m" -> "1m")
            timeframe = channel.replace("candle", "")
            
            if symbol and timeframe and data:
                for candle in data:
                    self.mtf_manager.update_candle(symbol, timeframe, candle)
                    
        except Exception as e:
            log.error(f"Error handling candle: {e}")

    async def _handle_orderbook(self, msg: dict):
        """Handle orderbook data"""
        try:
            arg = msg.get("arg", {})
            data = msg.get("data", [])
            symbol = arg.get("instId")
            
            if symbol and data:
                self.mtf_manager.update_orderbook(symbol, data[0])
        except Exception as e:
            log.error(f"Error handling orderbook: {e}")

    async def _handle_ticker(self, msg: dict):
        """Handle ticker data"""
        try:
            arg = msg.get("arg", {})
            data = msg.get("data", [])
            symbol = arg.get("instId")
            
            if symbol and data:
                self.mtf_manager.update_ticker(symbol, data[0])
        except Exception as e:
            log.error(f"Error handling ticker: {e}")

    async def _main_loop(self):
        """Main analysis loop"""
        while self.running:
            try:
                for symbol in self.symbols:
                    # 1. Check if data is ready
                    if not self.mtf_manager.is_ready(symbol):
                        continue

                    # 2. Get Consolidated State
                    state = self.mtf_manager.get_consolidated_state(symbol)
                    
                    # 3. Add Indicators for each timeframe
                    indicators_by_tf = {}
                    for tf, candles in state['candles'].items():
                        indicators_by_tf[tf] = TechnicalIndicators.analyze_candles(candles)
                    
                    state['indicators'] = indicators_by_tf
                    
                    # 4. Analyze Orderbook
                    state['market_data']['orderbook_analysis'] = OrderBookAnalyzer.analyze(state['market_data']['orderbook'])

                    # 5. AI Decision
                    decision = await self.decision_engine.evaluate_market(symbol, state)
                    
                    if decision:
                        log.info(f"AI Signal: {decision}")
                        # 6. Execute Trade
                        self.executor.execute_signal(decision, state)

                await asyncio.sleep(1) # 1 second loop

            except Exception as e:
                log.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        """Stop the bot"""
        self.running = False
        await self.ws.close()
        log.info("Bot stopped")

# Global instance for signal handling
bot = ScalpingBot()

def handle_shutdown(signum, frame):
    log.info("Shutdown signal received")
    asyncio.create_task(bot.stop())
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.critical(f"Fatal error: {e}")
