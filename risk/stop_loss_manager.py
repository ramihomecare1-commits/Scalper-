from typing import Dict, Optional
from config import Config
from utils.logger import log

class StopLossManager:
    @staticmethod
    def calculate_dynamic_sl_tp(entry_price: float, side: str, atr: float, support_resistance: Dict) -> Dict:
        """
        Calculate SL/TP based on ATR and Support/Resistance
        """
        try:
            # Basic ATR multiplier strategy if no clear S/R
            atr_multiplier_sl = 1.5
            atr_multiplier_tp = 2.5
            
            sl_price = 0.0
            tp_price = 0.0
            
            if side == "BUY":
                # SL below support or ATR
                support = support_resistance.get('nearest_support')
                if support and support < entry_price:
                    sl_price = min(support * 0.999, entry_price - (atr * atr_multiplier_sl))
                else:
                    sl_price = entry_price - (atr * atr_multiplier_sl)
                    
                # TP at resistance or ATR
                resistance = support_resistance.get('nearest_resistance')
                if resistance and resistance > entry_price:
                    tp_price = max(resistance * 0.999, entry_price + (atr * atr_multiplier_tp))
                else:
                    tp_price = entry_price + (atr * atr_multiplier_tp)
                    
            elif side == "SELL":
                # SL above resistance or ATR
                resistance = support_resistance.get('nearest_resistance')
                if resistance and resistance > entry_price:
                    sl_price = max(resistance * 1.001, entry_price + (atr * atr_multiplier_sl))
                else:
                    sl_price = entry_price + (atr * atr_multiplier_sl)
                    
                # TP at support or ATR
                support = support_resistance.get('nearest_support')
                if support and support < entry_price:
                    tp_price = min(support * 1.001, entry_price - (atr * atr_multiplier_tp))
                else:
                    tp_price = entry_price - (atr * atr_multiplier_tp)

            return {
                "stop_loss": sl_price,
                "take_profit": tp_price
            }

        except Exception as e:
            log.error(f"Error calculating SL/TP: {e}")
            return {}

    @staticmethod
    def check_trailing_stop(current_price: float, entry_price: float, side: str, current_sl: float, atr: float = 0.0) -> Optional[float]:
        """
        Calculate new trailing stop level if applicable.
        Includes a minimum move threshold (0.1% or 0.2*ATR) to prevent over-frequent API calls.
        """
        try:
            # Configurable trailing parameters
            trailing_percent = float(getattr(Config, 'TRAILING_STOP_PERCENT', 0.005)) # 0.5%
            min_update_percent = 0.001 # 0.1% minimum move before updating SL again
            
            # Use ATR for a more dynamic move threshold if available
            if atr > 0:
                move_threshold = max(current_price * min_update_percent, atr * 0.2)
            else:
                move_threshold = current_price * min_update_percent

            if side == "BUY":
                # Only trail if price is above entry
                if current_price > entry_price:
                    # Calculate potential new SL
                    potential_new_sl = current_price * (1 - trailing_percent)
                    
                    # Only move SL up, and only if it's a significant move
                    if potential_new_sl > current_sl + move_threshold:
                        log.debug(f"Trailing SL Up: {current_sl} -> {potential_new_sl}")
                        return potential_new_sl
                        
            elif side == "SELL":
                # Only trail if price is below entry
                if current_price < entry_price:
                    # Calculate potential new SL
                    potential_new_sl = current_price * (1 + trailing_percent)
                    
                    # Only move SL down, and only if it's a significant move
                    if potential_new_sl < current_sl - move_threshold:
                        log.debug(f"Trailing SL Down: {current_sl} -> {potential_new_sl}")
                        return potential_new_sl
                        
            return None

        except Exception as e:
            log.error(f"Error checking trailing stop: {e}")
            return None
