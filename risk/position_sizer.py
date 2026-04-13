from config import Config
from utils.logger import log

class PositionSizer:
    @staticmethod
    def calculate_position_size(account_equity: float, entry_price: float, symbol: str, specs: dict = None) -> float:
        """
        Calculate OKX-compliant position size based on risk rules and instrument precision
        Returns exactly the amount expected for the 'sz' field (contracts for SWAP, or tokens for SPOT).
        """
        try:
            specs = specs or {}
            lotSz = float(specs.get('lotSz', 1))
            minSz = float(specs.get('minSz', 1))
            ctVal = float(specs.get('ctVal', 1))
            
            # Rule: 2-3% of total equity per trade
            position_value_usd = account_equity * getattr(Config, 'POSITION_SIZE_PERCENT', 0.02)
            
            # Apply leverage
            leveraged_value_usd = position_value_usd * getattr(Config, 'LEVERAGE', 3)
            
            # 1. Calculate raw base currency amount (e.g., 0.5 BTC)
            raw_base_qty = leveraged_value_usd / entry_price
            
            # 2. Convert to OKX sizing units
            if getattr(Config, 'TRADING_MODE', 'SWAP') == 'SWAP':
                # For SWAP, size is in contracts.
                # Number of contracts = Base Quantity / Contract Value
                raw_size = raw_base_qty / ctVal
            else:
                # For SPOT, size is in base currency
                raw_size = raw_base_qty
                
            # 3. Round mathematically to nearest lotSz
            # Avoid divide by zero if lotSz is somehow 0
            if lotSz > 0:
                rounded_size = max(minSz, round(raw_size / lotSz) * lotSz)
            else:
                rounded_size = raw_size
                
            # Formatting precision based on lotSz decimal places
            # lotSz = 0.01 -> 2 decimals. lotSz = 1 -> 0 decimals.
            str_lot = str(lotSz)
            decimals = len(str_lot.split(".")[1]) if "." in str_lot else 0
            # Remove trailing zeros resulting from float stringification
            if "e" not in str_lot and decimals > 0:
                decimals = len(str_lot.rstrip('0').split(".")[1]) if "." in str_lot.rstrip('0') else 0
            
            # Convert to final float reflecting OKX exact requirement
            final_size = float(f"{rounded_size:.{decimals}f}")
            
            log.info(f"Position Sizing: Equity=${account_equity:.2f}, LeveragedValue=${leveraged_value_usd:.2f}, Raw={raw_size:.4f}, OKX Size={final_size} (lotSz={lotSz}, ctVal={ctVal})")
            
            return final_size

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
