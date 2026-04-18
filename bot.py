import asyncio
import signal
import sys
import time
from typing import List
from config import Config
from utils.logger import log
from data.okx_websocket import OKXWebSocket
from data.binance_websocket import BinanceWebSocket
from data.multi_timeframe_manager import MultiTimeframeManager
from data.okx_sentiment_client import OKXSentimentClient
from analysis.indicators import TechnicalIndicators
from analysis.orderbook_analyzer import OrderBookAnalyzer
from analysis.regime_detector import MarketRegimeDetector
from analysis.signal_filter import SignalFilter
from ai.decision_engine import DecisionEngine
from trading.order_executor import OrderExecutor
from utils.health_monitor import health_monitor
from utils.circuit_breaker import CircuitBreakerManager

class ScalpingBot:
    def __init__(self):
        self.running = False
        self.ws = OKXWebSocket()
        self.binance_ws = BinanceWebSocket()
        self.mtf_manager = MultiTimeframeManager()
        self.decision_engine = DecisionEngine()
        self.regime_detector = MarketRegimeDetector()
        self.signal_filter = SignalFilter()
        self.executor = OrderExecutor()
        from data.market_scanner import MarketScanner
        scanner = MarketScanner()
        # Fallback to Config.TRADING_PAIRS internally if scanner fails
        self.symbols = scanner.get_top_pairs(30)
        
        # Track active positions to prevent duplicate trades
        self.active_positions = set()  # Set of symbols with open positions
        self.last_trade_time = {}  # Track when we last traded each symbol
        self.last_ai_analysis = {}  # Track when we last analyzed each symbol with AI
        self.instrument_specs = {} # Holds precision specs for OKX
        self.sentiment_client = OKXSentimentClient()
        self.position_check_interval = 300  # Check positions every 5 minutes
        self.ai_analysis_cooldown = 300  # Only analyze with AI every 5 minutes per symbol
        self.sentiment_fetch_interval = 60  # Fetch sentiment data every 60 seconds
        self.rubik_fetch_interval = 300  # Rubik endpoints every 5 min (lower rate limit)
        self.last_sentiment_fetch = 0
        self.last_rubik_fetch = 0
        
        # WebSocket health tracking
        self.ws_last_message_time = 0
        self.ws_reconnect_count = 0
        self.ws_connected = False
        health_monitor.update_connection_status("okx_ws", False)
        health_monitor.update_connection_status("binance_ws", False)
        self.start_time = 0  # Bot start timestamp
        self.recent_errors = []  # Last N errors with timestamps
        self.max_error_history = 20

    async def start(self):
        """Start the bot"""
        import time as _time
        self.running = True
        self.start_time = _time.time()
        log.info("Starting AI Scalping Bot...")
        
        # Import REST client
        from data.okx_rest_client import OKXMarketData
        rest_client = OKXMarketData()
        
        # 1. Fetch initial historical candle data via REST API
        log.info("Fetching initial candle data via REST API...")
        for symbol in self.symbols:
            for tf in Config.TIMEFRAMES:
                candles = rest_client.get_candles(symbol, bar=tf, limit=300)
                if candles:
                    # Populate the multi-timeframe manager with historical data
                    for candle_data in candles:
                        # Convert to OKX WebSocket format
                        candle_list = [
                            str(candle_data['timestamp']),
                            str(candle_data['open']),
                            str(candle_data['high']),
                            str(candle_data['low']),
                            str(candle_data['close']),
                            str(candle_data['volume']),
                            "0", "0", "1"  # volCcy, volCcyQuote, confirm
                        ]
                        self.mtf_manager.update_candle(symbol, tf, candle_list)
                    log.info(f"Loaded {len(candles)} historical candles for {symbol} ({tf})")
                
                # Rate limit protection: OKX allows 20 req / 2s -> 1 req / 0.1s
                await asyncio.sleep(0.15)
                
            # Fetch instrument specifications so we know how to round trade sizes
            try:
                # We need a direct OKXClient instance to fetch specs
                from data.okx_client import OKXClient
                temp_client = OKXClient()
                self.instrument_specs = temp_client.get_instruments_specs(Config.TRADING_MODE)
            except Exception as e:
                log.error(f"Failed to fetch instrument specs, trades might fail rounding rules: {e}")
                
        # 2. Connect to WebSocket for real-time updates
        await self.ws.connect()
        
        # 3. Subscribe to real-time channels
        channels = []
        for symbol in self.symbols:
            # Order book for support/resistance analysis
            channels.append({"channel": "books5", "instId": symbol})
            
            # Ticker for current price
            channels.append({"channel": "tickers", "instId": symbol})
            
            # Live candle updates to keep indicators fresh
            for tf in Config.TIMEFRAMES:
                channels.append({"channel": f"candle{tf}", "instId": symbol})
        
        # Subscribe to liquidation events (market-wide for SWAP)
        if Config.TRADING_MODE == "SWAP":
            channels.append({"channel": "liquidation-orders", "instType": "SWAP"})

        await self.ws.subscribe(channels)
        self.ws_connected = True
        
        # Connect to Binance WebSocket for lead/lag detection
        await self.binance_ws.connect(self.symbols)
        self.binance_ws.add_callback(self._handle_binance_ticker)
        
        # 4. Register callbacks for real-time data
        self.ws.add_callback("books5", None, self._handle_orderbook)
        self.ws.add_callback("tickers", None, self._handle_ticker)
        self.ws.add_callback("candle", None, self._handle_candle)
        self.ws.add_callback("liquidation-orders", None, self._handle_liquidation)

        # 5. Main Loop
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
            error_msg = f"Error handling candle: {e}"
            log.error(error_msg)
            
            # Send Telegram notification for data errors
            try:
                from notifications.telegram_notifier import TelegramNotifier
                notifier = TelegramNotifier()
                await notifier.notify_error(f"Candle data error: {str(e)}")
            except:
                pass

    async def _handle_orderbook(self, msg: dict):
        """Handle orderbook data"""
        import time as _time
        try:
            self.ws_last_message_time = _time.time()
            arg = msg.get("arg", {})
            data = msg.get("data", [])
            symbol = arg.get("instId")
            
            if symbol and data:
                self.mtf_manager.update_orderbook(symbol, data[0])
        except Exception as e:
            log.error(f"Error handling orderbook: {e}")

    async def _handle_ticker(self, msg: dict):
        """Handle OKX ticker data"""
        try:
            arg = msg.get("arg", {})
            data = msg.get("data", [])
            symbol = arg.get("instId")
            
            if symbol and data:
                self.mtf_manager.update_ticker(symbol, data[0])
        except Exception as e:
            log.error(f"Error handling OKX ticker: {e}")

    async def _handle_binance_ticker(self, msg: dict):
        """Handle Binance ticker data for lead/lag detection"""
        try:
            # Map Binance symbol back to OKX format
            binance_symbol = msg.get("s", "")
            base = binance_symbol.replace("USDT", "")
            okx_symbol = f"{base}-USDT-SWAP" if Config.TRADING_MODE == "SWAP" else f"{base}-USDT"
            
            # Update only if it's a symbol we are tracking
            if okx_symbol in self.symbols:
                self.mtf_manager.update_binance_ticker(okx_symbol, msg)
        except Exception as e:
            log.error(f"Error handling Binance ticker: {e}")

    async def _handle_liquidation(self, msg: dict):
        """Handle real-time liquidation events"""
        try:
            data = msg.get("data", [])
            for liq in data:
                inst_id = liq.get("instId", "")
                # Only track liquidations for our watched symbols
                if inst_id in self.symbols:
                    side = liq.get("side", "")  # 'buy' = short liquidated, 'sell' = long liquidated
                    sz = float(liq.get("sz", 0))
                    px = float(liq.get("bkPx", 0))  # bankruptcy price
                    self.mtf_manager.record_liquidation(inst_id, side, sz, px)
        except Exception as e:
            log.error(f"Error handling liquidation: {e}")

    async def _fetch_sentiment_data(self):
        """Periodically fetch sentiment data from OKX REST APIs"""
        current_time = time.time()
        
        # P1 APIs: Funding rate, Open Interest, Mark Price (every 60s)
        if current_time - self.last_sentiment_fetch >= self.sentiment_fetch_interval:
            for symbol in self.symbols:
                try:
                    # Funding Rate
                    funding = self.sentiment_client.get_funding_rate(symbol)
                    if funding:
                        self.mtf_manager.update_sentiment(symbol, "funding_rate", funding)
                    
                    # Open Interest
                    oi = self.sentiment_client.get_open_interest(symbol)
                    if oi:
                        self.mtf_manager.update_sentiment(symbol, "open_interest", oi)
                    
                    # Mark Price
                    mark = self.sentiment_client.get_mark_price(symbol)
                    if mark:
                        self.mtf_manager.update_sentiment(symbol, "mark_price", mark)
                    
                    await asyncio.sleep(0.15)  # Rate limit protection
                except Exception as e:
                    log.error(f"Error fetching sentiment for {symbol}: {e}")
            
            self.last_sentiment_fetch = current_time
            log.info("Sentiment data (funding/OI/mark) refreshed.")
        
        # P2/P3 Rubik APIs: Long/Short Ratio, Taker Volume (every 5 min due to rate limits)
        if current_time - self.last_rubik_fetch >= self.rubik_fetch_interval:
            for symbol in self.symbols:
                try:
                    # Extract base currency from instId (e.g., BTC-USDT-SWAP -> BTC)
                    ccy = symbol.split("-")[0]
                    
                    # Long/Short Ratio
                    ls_ratio = self.sentiment_client.get_long_short_ratio(symbol)
                    if ls_ratio:
                        self.mtf_manager.update_sentiment(symbol, "long_short_ratio", ls_ratio)
                    
                    # Taker Volume
                    taker = self.sentiment_client.get_taker_volume(ccy)
                    if taker:
                        self.mtf_manager.update_sentiment(symbol, "taker_volume", taker)
                        
                    # Options Put/Call Ratio (only relevant for BTC/ETH)
                    if ccy in ["BTC", "ETH"]:
                        pc_ratio = self.sentiment_client.get_options_put_call_ratio(ccy)
                        if pc_ratio:
                            self.mtf_manager.update_sentiment(symbol, "put_call_ratio", pc_ratio)
                    
                    # Recent Trades (whale detection)
                    trades = self.sentiment_client.get_recent_trades(symbol)
                    if trades:
                        self.mtf_manager.update_sentiment(symbol, "recent_trades", trades)
                    
                    await asyncio.sleep(0.5)  # Rubik has 5 req/2s limit
                except Exception as e:
                    log.error(f"Error fetching rubik data for {symbol}: {e}")
            
            self.last_rubik_fetch = current_time
            log.info("Rubik sentiment data (L/S ratio, taker volume, trades) refreshed.")

    async def _main_loop(self):
        """Main analysis loop"""
        last_position_check = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Periodically fetch sentiment data
                await self._fetch_sentiment_data()
                
                # Periodically check existing positions (every 5 minutes)
                if current_time - last_position_check > self.position_check_interval:
                    await self._update_active_positions()
                    last_position_check = current_time
                
                # Check AI analysis cooldown - analyze all symbols together
                should_analyze = False
                for symbol in self.symbols:
                    if symbol not in self.last_ai_analysis:
                        should_analyze = True
                        break
                    time_since_last = current_time - self.last_ai_analysis.get(symbol, 0)
                    if time_since_last >= self.ai_analysis_cooldown:
                        should_analyze = True
                        break
                
                if should_analyze:
                    # Collect data for all symbols
                    symbols_data = {}
                    for symbol in self.symbols:
                        # Skip if already have open position
                        if symbol in self.active_positions:
                            log.debug(f"Skipping {symbol} - already have open position")
                            continue
                        
                        # Skip if traded recently
                        if symbol in self.last_trade_time:
                            time_since_last_trade = current_time - self.last_trade_time[symbol]
                            if time_since_last_trade < 300:  # 5 minutes cooldown
                                continue
                        
                        # Check if data is ready
                        if not self.mtf_manager.is_ready(symbol):
                            continue
                        
                        # Get consolidated state
                        state = self.mtf_manager.get_consolidated_state(symbol)
                        
                        # Primary timeframe for regime and filtering
                        primary_tf = Config.TIMEFRAMES[0] if Config.TIMEFRAMES else "1m"
                        primary_candles = state['candles'].get(primary_tf, [])
                        
                        # 1. Detect Regime (Primary Timeframe)
                        regime = self.regime_detector.identify_regime(primary_candles)
                        state['regime'] = regime

                        # 2. Analyze Orderbook
                        ob_analysis = OrderBookAnalyzer.analyze(state['market_data']['orderbook'])
                        state['market_data']['orderbook_analysis'] = ob_analysis
                        
                        # 3. Apply Signal Filter (Veto)
                        veto_check = self.signal_filter.should_veto(symbol, primary_candles, ob_analysis)
                        if veto_check['veto']:
                            log.debug(f"Vetoed {symbol}: {veto_check['reason']}")
                            continue

                        # 4. Calculate Indicators for all timeframes
                        indicators_by_tf = {}
                        for tf, candles in state['candles'].items():
                            indicators_by_tf[tf] = TechnicalIndicators.analyze_candles(candles)
                        state['indicators'] = indicators_by_tf
                        
                        symbols_data[symbol] = state
                    
                    # If we have symbols to analyze, make one AI call for all
                    if symbols_data:
                        decisions = await self.decision_engine.evaluate_multiple_markets(symbols_data)
                        
                        # Update last analysis time for all symbols
                        for symbol in symbols_data.keys():
                            self.last_ai_analysis[symbol] = current_time
                        
                        # Execute trades for any signals
                        if decisions:
                            for symbol, decision in decisions.items():
                                if decision:
                                    # Enforce maximum concurrent active positions limit
                                    if len(self.active_positions) >= getattr(Config, 'MAX_CONCURRENT_POSITIONS', 5):
                                        log.warning(f"Max active positions ({getattr(Config, 'MAX_CONCURRENT_POSITIONS', 5)}) reached. Ignoring signal for {symbol}.")
                                        continue
                                        
                                    log.info(f"AI Signal for {symbol}: {decision}")
                                    
                                    # Get the specific instrument specs (lotSz, tickSz) for precise rounding
                                    specs = self.instrument_specs.get(symbol, {})
                                    
                                    success = await self.executor.execute_signal_async(decision, symbols_data[symbol], specs)
                                    
                                    if success:
                                        self.active_positions.add(symbol)
                                        self.last_trade_time[symbol] = current_time
                                        log.info(f"Added {symbol} to active positions")

                await asyncio.sleep(1) # 1 second loop

            except Exception as e:
                import time as _time
                error_msg = f"Error in main loop: {e}"
                log.error(error_msg)
                
                # Track error in health monitor
                health_monitor.record_error("main_loop", str(e), critical=True)
                
                # Track error history for dashboard
                self.recent_errors.append({
                    "time": _time.time(),
                    "message": str(e)
                })
                if len(self.recent_errors) > self.max_error_history:
                    self.recent_errors = self.recent_errors[-self.max_error_history:]
                
                # Send Telegram notification for critical errors
                try:
                    from notifications.telegram_notifier import TelegramNotifier
                    notifier = TelegramNotifier()
                    await notifier.notify_error(f"Main loop error: {str(e)}")
                except:
                    pass  # Don't let notification errors crash the bot
                
                await asyncio.sleep(5)
    
    async def _update_active_positions(self):
        """Check OKX for current open positions and update tracking"""
        try:
            log.info("Checking for open positions...")
            positions = self.executor.client.get_positions(instType=Config.TRADING_MODE)
            
            # Clear and rebuild active positions set
            self.active_positions.clear()
            
            for pos in positions:
                inst_id = pos.get('instId')
                pos_size = float(pos.get('pos', 0))
                
                # If position size is not zero, it's an active position
                if pos_size != 0:
                    self.active_positions.add(inst_id)
                    log.info(f"Active position found: {inst_id}, Size: {pos_size}")
            
            log.info(f"Total active positions: {len(self.active_positions)}")
            
        except Exception as e:
            health_monitor.record_error("position_check", str(e))
            log.error(f"Error checking positions: {e}")

    def get_ws_health(self) -> dict:
        """Get WebSocket health metrics for dashboard (delegates to health_monitor)"""
        return health_monitor.get_full_report()

    async def stop(self):
        """Stop the bot"""
        self.running = False
        await self.ws.close()
        await self.binance_ws.close()
        log.info("Bot stopped")


if __name__ == "__main__":
    # Create bot instance only when running directly
    bot_instance = ScalpingBot()
    
    def handle_shutdown(signum, frame):
        log.info("Shutdown signal received")
        asyncio.create_task(bot_instance.stop())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        asyncio.run(bot_instance.start())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.critical(f"Fatal error: {e}")

