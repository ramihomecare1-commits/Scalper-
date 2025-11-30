import aiohttp
from typing import Optional, Dict
from config import Config
from utils.logger import log
import html

def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram"""
    if not text:
        return ""
    return html.escape(str(text))

class TelegramNotifier:
    """Send trade notifications via Telegram"""
    
    def __init__(self):
        self.bot_token = Config.TELEGRAM_BOT_TOKEN if hasattr(Config, 'TELEGRAM_BOT_TOKEN') else None
        self.chat_id = Config.TELEGRAM_CHAT_ID if hasattr(Config, 'TELEGRAM_CHAT_ID') else None
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            log.warning("Telegram notifications disabled - TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
    
    async def send_message(self, text: str) -> bool:
        """Send a message to Telegram"""
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        log.debug("Telegram notification sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        log.error(f"Telegram API error ({response.status}): {error_text}")
                        return False
                        
        except Exception as e:
            log.error(f"Failed to send Telegram notification: {e}")
            return False
    
    async def notify_trade_opened(self, trade_data: Dict) -> bool:
        """Send notification when a trade is opened"""
        try:
            side_emoji = "📈" if trade_data['action'] == 'BUY' else "📉"
            
            # Escape all dynamic content
            symbol = escape_html(trade_data['symbol'])
            action = escape_html(trade_data['action'])
            size = escape_html(str(trade_data.get('size', 'N/A')))
            risk_reward = escape_html(str(trade_data.get('risk_reward', 'N/A')))
            confidence = escape_html(str(trade_data.get('confidence', 'N/A')))
            reasoning = escape_html(trade_data.get('reasoning', 'AI-based decision'))
            
            message = f"""🤖 <b>SCALPER BOT</b>
🚀 <b>TRADE OPENED</b>

<b>Pair:</b> {symbol}
<b>Side:</b> {action} {side_emoji}
<b>Entry:</b> ${trade_data['entry_price']:.2f}
<b>Stop Loss:</b> ${trade_data['stop_loss']:.2f}
<b>Take Profit:</b> ${trade_data['take_profit']:.2f}
<b>Size:</b> {size}
<b>Risk/Reward:</b> {risk_reward}:1
<b>Confidence:</b> {confidence}%

<i>Reasoning:</i> {reasoning}
"""
            
            return await self.send_message(message)
            
        except Exception as e:
            log.error(f"Error formatting trade opened notification: {e}")
            return False
    
    async def notify_trade_closed(self, trade_data: Dict) -> bool:
        """Send notification when a trade is closed"""
        try:
            pnl = trade_data.get('pnl', 0)
            pnl_pct = trade_data.get('pnl_percent', 0)
            
            # Determine emoji based on profit/loss
            if pnl > 0:
                status_emoji = "✅"
                status_text = "PROFIT"
            elif pnl < 0:
                status_emoji = "❌"
                status_text = "LOSS"
            else:
                status_emoji = "⚪"
                status_text = "BREAKEVEN"
            
            # Escape dynamic content
            symbol = escape_html(trade_data['symbol'])
            action = escape_html(trade_data['action'])
            duration = escape_html(str(trade_data.get('duration', 'N/A')))
            total_trades = escape_html(str(trade_data.get('total_trades', 'N/A')))
            win_rate = escape_html(str(trade_data.get('win_rate', 'N/A')))
            
            message = f"""🤖 <b>SCALPER BOT</b>
{status_emoji} <b>TRADE CLOSED - {status_text}</b>

<b>Pair:</b> {symbol}
<b>Side:</b> {action}
<b>Entry:</b> ${trade_data['entry_price']:.2f}
<b>Exit:</b> ${trade_data['exit_price']:.2f}
<b>P&L:</b> ${pnl:+.2f} ({pnl_pct:+.2f}%)
<b>Duration:</b> {duration}

<b>Total Trades:</b> {total_trades}
<b>Win Rate:</b> {win_rate}%
"""
            
            return await self.send_message(message)
            
        except Exception as e:
            log.error(f"Error formatting trade closed notification: {e}")
            return False
    
    async def notify_error(self, error_message: str) -> bool:
        """Send error notification"""
        message = f"""🤖 <b>SCALPER BOT</b>
⚠️ <b>BOT ERROR</b>

{error_message}
"""
        return await self.send_message(message)
