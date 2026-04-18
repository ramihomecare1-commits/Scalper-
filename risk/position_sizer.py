from decimal import Decimal, ROUND_FLOOR
from config import Config
from utils.logger import log

class PositionSizer:
    @staticmethod
    def calculate_position_size(account_equity: float, entry_price: float, symbol: str, specs: dict = None) -> float:
        """
        Calculate OKX-compliant position size based on risk rules and instrument precision.
        Returns exactly the amount expected for the 'sz' field (contracts for SWAP, or tokens for SPOT).
        Uses Decimal for high precision to avoid floating point errors.
        """
        try:
            specs = specs or {}
            # Defaults to 1.0 but should be fetched from public instruments specs
            lotSz = Decimal(str(specs.get('lotSz', '1')))
            minSz = Decimal(str(specs.get('minSz', '1')))
            ctVal = Decimal(str(specs.get('ctVal', '1')))
            
            # Risk Rule: % of total equity per trade
            risk_percent = Decimal(str(getattr(Config, 'POSITION_SIZE_PERCENT', '0.02')))
            position_value_usd = Decimal(str(account_equity)) * risk_percent
            
            # Apply leverage
            leverage = Decimal(str(getattr(Config, 'LEVERAGE', '3')))
            leveraged_value_usd = position_value_usd * leverage
            
            # 1. Calculate raw base currency amount (e.g., 0.5 BTC)
            raw_base_qty = leveraged_value_usd / Decimal(str(entry_price))
            
            # 2. Convert to OKX sizing units
            if getattr(Config, 'TRADING_MODE', 'SWAP') == 'SWAP':
                # Number of contracts = Base Quantity / Contract Value
                raw_size = raw_base_qty / ctVal
            else:
                raw_size = raw_base_qty
                
            # 3. Round to nearest lotSz (downwards for safety)
            # Use ROUND_FLOOR to ensure we don't exceed the intended risk margin
            rounded_size = (raw_size / lotSz).quantize(Decimal('1'), rounding=ROUND_FLOOR) * lotSz
            
            # Ensure it's at least minSz
            final_size = max(minSz, rounded_size)
            
            # Return as float for the SDK
            result = float(final_size)
            
            log.info(f"Sizing [{symbol}]: Equity={account_equity:.2f}, LeveragedValue=${float(leveraged_value_usd):.2f}, RawUnits={float(raw_size):.6f}, OKX Size={result} (lot={lotSz}, ctVal={ctVal})")
            
            return result

        except Exception as e:
            log.error(f"Error calculating position size: {e}")
            return 0.0

    @staticmethod
    def check_max_loss(account_equity: float, entry_price: float, stop_loss: float, quantity: float, ctVal: float = 1.0) -> bool:
        """
        Verify if potential loss exceeds maximum allowed risk
        """
        try:
            potential_loss_per_unit = abs(entry_price - stop_loss)
            total_potential_loss = potential_loss_per_unit * quantity * ctVal
            
            max_allowed_loss = account_equity * Config.MAX_LOSS_PER_TRADE_PERCENT
            
            if total_potential_loss > max_allowed_loss:
                log.warning(f"Risk Check Failed: Potential Loss ${total_potential_loss:.2f} > Max Allowed ${max_allowed_loss:.2f}")
                return False
                
            return True

        except Exception as e:
            log.error(f"Error checking max loss: {e}")
            return False
