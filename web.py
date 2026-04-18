from flask import Flask, jsonify, render_template
import threading
import asyncio
import time
from bot import ScalpingBot
from monitoring.performance_tracker import PerformanceTracker
from config import Config
from utils.logger import log

app = Flask(__name__)
bot = None
bot_thread = None
bot_error = None

# Cached stats to avoid re-reading JSONL every request
_stats_cache = {"data": {}, "timestamp": 0}
_STATS_CACHE_TTL = 30  # seconds


def run_bot():
    """Run the bot in a separate thread"""
    global bot
    try:
        log.info("Starting bot initialization...")
        bot = ScalpingBot()
        log.info("Bot initialized successfully")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        log.info("Event loop created, starting bot...")
        
        loop.run_until_complete(bot.start())
    except Exception as e:
        global bot_error
        import traceback
        bot_error = str(e)
        log.error(f"Bot error: {e}")
        log.error(f"Traceback: {traceback.format_exc()}")

@app.route('/')
def home():
    """Dashboard UI endpoint"""
    return render_template('index.html')

@app.route('/api/bot_status')
def bot_status():
    """Comprehensive real-time bot status — synced with OKX and Health Monitor"""
    global _stats_cache
    
    status = {
        "is_running": False,
        "active_positions": [],
        "tracked_symbols": [],
        "last_analysis_times": {},
        "server_time": time.time(),
        "error": bot_error,
        "recent_errors": [],
        "stats": {},
        # OKX live data
        "account": {},
        "positions_detail": [],
        "open_orders": [],
        "algo_orders": [],
        "recent_fills": [],
        # Sentiment / Market Intelligence
        "sentiment_snapshot": {},
        # System info
        "trading_mode": Config.TRADING_MODE,
        "is_demo": Config.OKX_DEMO_TRADING,
        "is_dry_run": Config.DRY_RUN,
        "leverage_setting": Config.LEVERAGE,
        "max_positions": Config.MAX_CONCURRENT_POSITIONS,
        "ws_health": {},
        "health": {} # New health monitor field
    }
    
    if bot:
        status["is_running"] = bot.running
        status["active_positions"] = list(bot.active_positions)
        status["tracked_symbols"] = bot.symbols
        status["last_analysis_times"] = bot.last_ai_analysis
        status["recent_errors"] = bot.recent_errors[-5:]  # Last 5 for dashboard
        
        # Get full health report
        from utils.health_monitor import health_monitor
        status["health"] = health_monitor.get_full_report()
        status["ws_health"] = status["health"] # Backward compatibility for UI
        
        # Query OKX for live account & position data
        try:
            client = bot.executor.client
            status["account"] = client.get_account_summary("USDT")
            status["positions_detail"] = client.get_detailed_positions(Config.TRADING_MODE)
            status["open_orders"] = client.get_pending_orders(Config.TRADING_MODE)
            status["algo_orders"] = client.get_algo_orders(Config.TRADING_MODE)
            status["recent_fills"] = client.get_recent_fills(Config.TRADING_MODE, limit=10)
        except Exception as e:
            log.debug(f"Error fetching OKX data for dashboard: {e}")
        
        # Sentiment snapshot — top 5 symbols by sentiment data availability
        try:
            sentiment_snap = {}
            for sym in bot.symbols[:10]:
                s = bot.mtf_manager.sentiment.get(sym, {})
                ticker = bot.mtf_manager.tickers.get(sym, {})
                if s or ticker:
                    sentiment_snap[sym] = {
                        "price": ticker.get("last", "0") if ticker else "0",
                        "change_24h": ticker.get("sodUtc8", None) if ticker else None,
                        "last_price": ticker.get("last", None) if ticker else None,
                        "funding_rate": s.get("funding_rate", {}).get("fundingRate") if s.get("funding_rate") else None,
                        "open_interest": s.get("open_interest", {}).get("oiCcy") if s.get("open_interest") else None,
                        "long_pct": s.get("long_short_ratio", {}).get("longPct") if s.get("long_short_ratio") else None,
                        "short_pct": s.get("long_short_ratio", {}).get("shortPct") if s.get("long_short_ratio") else None,
                        "whale_bias": s.get("recent_trades", {}).get("whaleBias") if s.get("recent_trades") else None,
                        "taker_buy_ratio": s.get("taker_volume", {}).get("buyRatio") if s.get("taker_volume") else None,
                    }
            status["sentiment_snapshot"] = sentiment_snap
        except Exception as e:
            log.debug(f"Error building sentiment snapshot: {e}")
            
    
    # Performance stats with caching
    now = time.time()
    if now - _stats_cache["timestamp"] > _STATS_CACHE_TTL:
        try:
            tracker = PerformanceTracker()
            _stats_cache["data"] = tracker.get_stats()
            _stats_cache["timestamp"] = now
        except Exception:
            pass
    status["stats"] = _stats_cache["data"]
        
    return jsonify(status)

@app.route('/health')
def health():
    """Health check for Render"""
    from utils.health_monitor import health_monitor
    report = health_monitor.get_full_report()
    status_code = 200 if report["status"] == "healthy" else 200 # Still return 200 to keep it alive
    return jsonify(report), status_code

@app.route('/stats')
def stats():
    """Get bot statistics"""
    try:
        tracker = PerformanceTracker()
        return jsonify(tracker.get_stats())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Start bot thread when module is loaded (works with gunicorn)
log.info("Initializing bot thread...")
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()
log.info("Bot thread started")

if __name__ == '__main__':
    # This block only runs when executing directly with python web.py
    import os
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
