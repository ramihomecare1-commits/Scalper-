from typing import Dict, Optional
from data.okx_client import OKXClient
from risk.position_sizer import PositionSizer
from risk.stop_loss_manager import StopLossManager
from config import Config
from utils.logger import log

class OrderExecutor:
    def __init__(self):
        self.client = OKXClient()

    def execute_signal(self, signal: Dict, market_data: Dict) -> bool:
        """
        Execute a trade signal
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
                log.error("Insufficient equity")
                return False

            # 2. Calculate Position Size
            quantity = PositionSizer.calculate_position_size(equity, entry_price, symbol)
            if quantity <= 0:
                log.error("Invalid position size")
                return False

            # 3. Risk Check
            if not PositionSizer.check_max_loss(equity, entry_price, stop_loss, quantity):
                log.warning("Trade rejected by risk manager")
                return False

            # 4. Set Leverage (for SWAP contracts)
            if Config.TRADING_MODE == "SWAP":
                self._set_leverage(symbol, Config.LEVERAGE)

            # 5. Place Order
            # For SWAP contracts, size is in number of contracts
            # 1 contract = 1 USD for BTC-USDT-SWAP, ETH-USDT-SWAP
            # So we need to convert our quantity to contracts
            
            # For USDT-margined swaps: contracts = notional_value / contract_value
            # Contract value is typically 1 USD per contract
            notional_value = quantity * entry_price
            sz = str(int(notional_value))  # Number of contracts
            
            side = "buy" if action == "BUY" else "sell"
            
            # Use 'cross' margin mode for SWAP
            td_mode = "cross" if Config.TRADING_MODE == "SWAP" else "cash"
            
            result = self.client.place_order(
                instId=symbol,
                tdMode=td_mode,
                side=side,
                ordType="limit",
                sz=sz,
                px=str(entry_price),
                slTriggerPx=str(stop_loss),
                tpTriggerPx=str(take_profit)
            )

            if result.get("code") == "0":
                log.info(f"Trade executed: {action} {symbol} @ {entry_price}, Qty: {sz} contracts, SL: {stop_loss}, TP: {take_profit}")
                return True
            
            return False

        except Exception as e:
            log.error(f"Error executing signal: {e}")
            return False

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
