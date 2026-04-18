from typing import Dict, Optional, List
import asyncio
from data.okx_client import OKXClient
from risk.position_sizer import PositionSizer
from risk.stop_loss_manager import StopLossManager
from risk.portfolio_risk import portfolio_risk_manager
from risk.position_monitor import position_monitor
from notifications.telegram_notifier import TelegramNotifier
from config import Config
from utils.logger import log

class OrderExecutor:
    def __init__(self):
        self.client = OKXClient()
        self.telegram = TelegramNotifier()
        self.active_trades = {}  # Local tracking, augmented by position_monitor
        self.monitor_task = None

    def start_monitoring(self):
        """Start the background position monitor."""
        if not self.monitor_task:
            self.monitor_task = asyncio.create_task(position_monitor.monitor_loop())

    async def execute_signal_async(self, signal: Dict, market_data: Dict, specs: Dict = None) -> bool:
        """
        Execute a trade signal with strict risk gatekeeping.
        """
        try:
            symbol = market_data['symbol']
            action = signal['action']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            take_profit = signal['take_profit']
            direction = "LONG" if action == "BUY" else "SHORT"
            
            # 1. Sync Positions and perform Portfolio-Level Risk Check
            current_positions = await position_monitor.sync_positions()
            
            # 2. Get Account Balance
            acct_summary = self.client.get_account_summary()
            equity = acct_summary.get('total_equity', 0)
            
            if equity <= 0:
                error_msg = f"Insufficient equity (${equity}) - blocking {symbol} {action}"
                log.error(error_msg)
                await self.telegram.notify_error(f"⚠️ {error_msg}")
                return False

            # 3. Portfolio Risk Gatekeeper (The Primary Directive)
            can_trade, reason = portfolio_risk_manager.can_open_position(
                symbol=symbol, 
                test_direction=direction, 
                account_equity=equity, 
                current_positions=current_positions
            )
            
            if not can_trade:
                log.warning(f"Portfolio Risk Rejection for {symbol}: {reason}")
                await self.telegram.notify_error(f"🚫 Trade Rejected: {reason}")
                return False

            # 4. Calculate Position Size (OKX Compliant)
            quantity = PositionSizer.calculate_position_size(equity, entry_price, symbol, specs)
            if quantity <= 0:
                log.error(f"Invalid position size calculated for {symbol}")
                return False

            # 5. Trade-Level Max Loss Check
            ctVal = float(specs.get('ctVal', 1)) if specs else 1.0
            if not PositionSizer.check_max_loss(equity, entry_price, stop_loss, float(quantity), ctVal):
                log.warning(f"Trade Risk Rejection for {symbol}: Potential loss too high for account size.")
                return False

            # 6. Set Leverage (for SWAP contracts)
            if Config.TRADING_MODE == "SWAP":
                self._set_leverage(symbol, Config.LEVERAGE)

            # 7. Format Prices based on tickSz
            tickSz = float(specs.get('tickSz', 0.01)) if specs else 0.01
            price_decimals = self._get_decimals(str(tickSz))
            
            formatted_sl = f"{stop_loss:.{price_decimals}f}"
            formatted_tp = f"{take_profit:.{price_decimals}f}"

            # 8. Place Order
            sz = str(quantity)
            if sz.endswith('.0'):
                sz = sz[:-2]
            
            side = "buy" if action == "BUY" else "sell"
            td_mode = "cross" if Config.TRADING_MODE == "SWAP" else "cash"
            
            log.info(f"RISK CHECK PASSED. Executing {direction} {symbol} size {sz}")
            
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
                log.info(f"✅ Order Executed: {order_id}")
                
                trade_data = {
                    'symbol': symbol,
                    'action': action,
                    'direction': direction,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'size': sz,
                    'risk_reward': signal.get('risk_reward', Config.RISK_REWARD_RATIO),
                    'confidence': signal.get('confidence', 'N/A'),
                    'reasoning': signal.get('reasoning', 'AI Risk-Managed Entry')
                }
                
                self.active_trades[order_id] = {
                    **trade_data,
                    'entry_time': asyncio.get_event_loop().time()
                }
                
                await self.telegram.notify_trade_opened(trade_data)
                return True
            else:
                error_code = result.get("code")
                error_msg = result.get("msg", "Unknown error")
                log.error(f"❌ OKX Execution Failed: {error_msg} (Code: {error_code})")
                await self.telegram.notify_error(f"❌ Execution Failure: {symbol} - {error_msg}")
                return False

        except Exception as e:
            log.error(f"Critical error in execution flow: {e}")
            await self.telegram.notify_error(f"⚠️ Critical Execution Error: {str(e)}")
            return False

    def _get_decimals(self, tick_str: str) -> int:
        if "." not in tick_str:
            return 0
        return len(tick_str.rstrip('0').split(".")[1])

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
            
            # Record result in Portfolio Risk Manager for drawdown tracking
            portfolio_risk_manager.record_trade_result(pnl)
            
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
