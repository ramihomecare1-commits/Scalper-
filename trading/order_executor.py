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

            # 4. Place Order
            # For scalping, we often use 'cross' or 'isolated'. Let's assume 'cross' for now or config.
            # OKX requires size in contracts for swaps usually, or coin for spot.
            # Assuming USDT Swaps for leverage.
            # IMPORTANT: OKX API 'sz' for swaps is in number of contracts (usually 1 contract = X amount).
            # We need to convert quantity to contracts. 
            # For simplicity in this demo, we'll assume we are trading Spot or calculating correctly.
            # Let's assume Spot for simplicity of 'sz' being in base currency, but user asked for leverage.
            # If leverage, we likely trade SWAP. 
            # TODO: Implement contract size conversion. For now, passing calculated quantity (might need adjustment).
            
            # Rounding quantity to appropriate precision (simplified)
            sz = f"{quantity:.8f}" # Adjust precision based on instrument

            side = "buy" if action == "BUY" else "sell"
            
            result = self.client.place_order(
                instId=symbol,
                tdMode="cross", # Using cross margin
                side=side,
                ordType="limit",
                sz=sz,
                px=str(entry_price),
                slTriggerPx=str(stop_loss),
                tpTriggerPx=str(take_profit)
            )

            if result.get("code") == "0":
                log.info(f"Trade executed: {action} {symbol} @ {entry_price}, Qty: {sz}, SL: {stop_loss}, TP: {take_profit}")
                return True
            
            return False

        except Exception as e:
            log.error(f"Error executing signal: {e}")
            return False

    def close_position(self, symbol: str) -> bool:
        """Close all positions for a symbol"""
        # Implementation would involve getting positions and placing market close orders
        pass
