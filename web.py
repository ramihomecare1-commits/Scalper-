from flask import Flask, jsonify
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
    bot = ScalpingBot()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot.start())
    except Exception as e:
        log.error(f"Bot error: {e}")

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "service": "AI Crypto Scalping Bot",
        "message": "Bot is running in the background"
    })

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

if __name__ == '__main__':
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    log.info("Bot thread started")
    
    # Start Flask web server for Render
    import os
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
