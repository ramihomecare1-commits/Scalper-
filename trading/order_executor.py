from typing import Dict, Optional
import asyncio
from data.okx_client import OKXClient
from risk.position_sizer import PositionSizer
from risk.stop_loss_manager import StopLossManager
from notifications.telegram_notifier import TelegramNotifier
from config import Config
from utils.logger import log

class OrderExecutor:
    def __init__(self):
        self.client = OKXClient()
        self.telegram = TelegramNotifier()
        self.active_trades = {}  # Track active trades for close notifications

    async def execute_signal_async(self, signal: Dict, market_data: Dict, specs: Dict = None) -> bool:
        """
        Execute a trade signal (async version for Telegram)
        """
        try:
            symbol = market_data['symbol']
            action = signal['action']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            take_profit = signal['take_profit']
            
            # 1. Get Account Balance
            equity = self.client.get_balance("USDT")
            if equity <= 0:
                error_msg = "Insufficient equity - balance check failed"
                log.error(error_msg)
                # Send Telegram notification
                try:
                    await self.telegram.notify_error(f"⚠️ {error_msg}")
                except:
                    pass
                return False

            # 2. Calculate Position Size
            quantity = PositionSizer.calculate_position_size(equity, entry_price, symbol, specs)
            if quantity <= 0:
                log.error("Invalid position size")
                return False

            # 3. Risk Check (Risk check uses raw size calculation, we pass it quantity which is now base coin or contracts)
            # if not PositionSizer.check_max_loss(equity, entry_price, stop_loss, quantity):
            #     log.warning("Trade rejected by risk manager")
            #     return False

            # 4. Set Leverage (for SWAP contracts)
            if Config.TRADING_MODE == "SWAP":
                self._set_leverage(symbol, Config.LEVERAGE)

            # 5. Format Prices based on tickSz
            tickSz = float(specs.get('tickSz', 0.01)) if specs else 0.01
            str_tick = str(tickSz)
            price_decimals = len(str_tick.split(".")[1]) if "." in str_tick else 0
            if "e" not in str_tick and price_decimals > 0:
                price_decimals = len(str_tick.rstrip('0').split(".")[1]) if "." in str_tick.rstrip('0') else 0
                
            formatted_sl = f"{stop_loss:.{price_decimals}f}"
            formatted_tp = f"{take_profit:.{price_decimals}f}"

            # 6. Place Order
            sz = str(quantity)
            if sz.endswith('.0'):
                sz = sz[:-2] # Clean whole numbers like "10.0" -> "10"
            
            side = "buy" if action == "BUY" else "sell"
            td_mode = "cross" if Config.TRADING_MODE == "SWAP" else "cash"
            
            result = self.client.place_order(
                instId=symbol,
                tdMode=td_mode,
                side=side,
                ordType="market",
                sz=sz,
                slTriggerPx=formatted_sl,
                tpTriggerPx=formatted_tp
            )

            if result.get("code") == "0":
                order_id = result['data'][0]['ordId']
                log.info(f"Trade executed: {action} {symbol} @ {entry_price}, Qty: {sz}, SL: {stop_loss}, TP: {take_profit}")
                
                # Send Telegram notification
                trade_data = {
                    'symbol': symbol,
                    'action': action,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'size': sz,
                    'risk_reward': signal.get('risk_reward', Config.RISK_REWARD_RATIO),
                    'confidence': signal.get('confidence', 'N/A'),
                    'reasoning': signal.get('reasoning', 'AI-based decision')
                }
                
                # Store trade for later close notification
                self.active_trades[order_id] = {
                    **trade_data,
                    'entry_time': asyncio.get_event_loop().time()
                }
                
                await self.telegram.notify_trade_opened(trade_data)
                return True
            
            return False

        except Exception as e:
            log.error(f"Error executing signal: {e}")
            await self.telegram.notify_error(f"Trade execution error: {str(e)}")
            return False

    def execute_signal(self, signal: Dict, market_data: Dict) -> bool:
        """
        Synchronous wrapper for execute_signal_async
        """
        try:
            # Get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a task
                task = asyncio.create_task(self.execute_signal_async(signal, market_data))
                # We can't wait for it in sync context, so return True optimistically
                # The actual result will be logged by the async function
                return True
            else:
                # If no loop is running, run it
                return loop.run_until_complete(self.execute_signal_async(signal, market_data))
        except Exception as e:
            log.error(f"Error in execute_signal wrapper: {e}")
            return False

    async def close_position_async(self, order_id: str, exit_price: float, pnl: float, pnl_percent: float):
        """Notify when a position is closed"""
        if order_id in self.active_trades:
            trade = self.active_trades[order_id]
            entry_time = trade.get('entry_time', 0)
            current_time = asyncio.get_event_loop().time()
            duration_seconds = int(current_time - entry_time)
            duration = f"{duration_seconds // 60} minutes" if duration_seconds >= 60 else f"{duration_seconds} seconds"
            
            close_data = {
                **trade,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_percent': pnl_percent,
                'duration': duration,
                'total_trades': 'N/A',  # Can be populated from performance tracker
                'win_rate': 'N/A'
            }
            
            await self.telegram.notify_trade_closed(close_data)
            del self.active_trades[order_id]

    def _set_leverage(self, inst_id: str, leverage: int):
        """Set leverage for a trading pair"""
        try:
            if Config.DRY_RUN:
                log.info(f"DRY RUN: Would set leverage to {leverage}x for {inst_id}")
                return
            
            # OKX API to set leverage
            result = self.client.accountAPI.set_leverage(
                instId=inst_id,
                lever=str(leverage),
                mgnMode="cross"
            )
            
            if result.get("code") == "0":
                log.info(f"Leverage set to {leverage}x for {inst_id}")
            else:
                log.warning(f"Failed to set leverage: {result}")
                
        except Exception as e:
            log.error(f"Error setting leverage: {e}")
