from flask import Flask, jsonify, render_template
import threading
import asyncio
from bot import ScalpingBot
from monitoring.performance_tracker import PerformanceTracker
from utils.logger import log

app = Flask(__name__)
bot = None
bot_thread = None

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
        import traceback
        log.error(f"Bot error: {e}")
        log.error(f"Traceback: {traceback.format_exc()}")

@app.route('/')
def home():
    """Dashboard UI endpoint"""
    return render_template('index.html')

@app.route('/api/bot_status')
def bot_status():
    """Real-time bot status"""
    import time
    
    thread_alive = bot_thread.is_alive() if bot_thread else False
    
    status = {
        "is_running": False,
        "thread_alive": thread_alive,
        "active_positions": [],
        "tracked_symbols": [],
        "last_analysis_times": {},
        "server_time": time.time(),
        "stats": {}
    }
    
    if bot:
        status["is_running"] = bot.running and thread_alive
        status["active_positions"] = list(bot.active_positions)
        status["tracked_symbols"] = bot.symbols
        status["last_analysis_times"] = bot.last_ai_analysis
    
    try:
        tracker = PerformanceTracker()
        status["stats"] = tracker.get_stats()
    except Exception:
        pass
        
    return jsonify(status)

@app.route('/health')
def health():
    """Health check for Render"""
    return jsonify({"status": "healthy"}), 200

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

