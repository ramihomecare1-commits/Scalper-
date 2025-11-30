from config import Config
from utils.logger import log

class PositionSizer:
    @staticmethod
    def calculate_position_size(account_equity: float, entry_price: float, symbol: str) -> float:
        """
        Calculate position size based on risk rules
        Returns quantity in base currency (e.g., BTC, ETH)
        """
        try:
            # Rule: 2-3% of total equity per trade
            position_value_usd = account_equity * Config.POSITION_SIZE_PERCENT
            
            # Apply leverage
            leveraged_value_usd = position_value_usd * Config.LEVERAGE
            
            # Calculate quantity
            quantity = leveraged_value_usd / entry_price
            
            # TODO: Add symbol-specific precision rounding / min size checks here
            # For now, return raw quantity
            
            log.info(f"Position Sizing: Equity=${account_equity:.2f}, Size=${position_value_usd:.2f}, Lev=${leveraged_value_usd:.2f}, Qty={quantity:.6f}")
            
            return quantity

        except Exception as e:
            log.error(f"Error calculating position size: {e}")
            return 0.0

    @staticmethod
    def check_max_loss(account_equity: float, entry_price: float, stop_loss: float, quantity: float) -> bool:
        """
        Verify if potential loss exceeds maximum allowed risk
        """
        try:
            potential_loss_per_unit = abs(entry_price - stop_loss)
            total_potential_loss = potential_loss_per_unit * quantity
            
            max_allowed_loss = account_equity * Config.MAX_LOSS_PER_TRADE_PERCENT
            
            if total_potential_loss > max_allowed_loss:
                log.warning(f"Risk Check Failed: Potential Loss ${total_potential_loss:.2f} > Max Allowed ${max_allowed_loss:.2f}")
                return False
                
            return True

        except Exception as e:
            log.error(f"Error checking max loss: {e}")
            return False
