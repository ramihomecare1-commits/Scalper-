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
    def check_trailing_stop(current_price: float, entry_price: float, side: str, current_sl: float) -> Optional[float]:
        """
        Calculate new trailing stop level if applicable
        """
        try:
            trailing_percent = 0.005 # 0.5% trailing
            
            if side == "BUY":
                if current_price > entry_price * (1 + trailing_percent):
                    new_sl = current_price * (1 - trailing_percent)
                    if new_sl > current_sl:
                        return new_sl
                        
            elif side == "SELL":
                if current_price < entry_price * (1 - trailing_percent):
                    new_sl = current_price * (1 + trailing_percent)
                    if new_sl < current_sl:
                        return new_sl
                        
            return None

        except Exception as e:
            log.error(f"Error checking trailing stop: {e}")
            return None
