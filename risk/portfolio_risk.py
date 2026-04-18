from typing import List, Dict, Tuple
from config import Config
from utils.logger import log
import time
from datetime import datetime, timezone

class PortfolioRiskManager:
    """
    Centralized Portfolio Risk Manager.
    Prevents catastrophic failures by enforcing portfolio-level limits.
    """
    def __init__(self):
        self.daily_drawdown_usd = 0.0
        self.last_reset_time = self._get_current_utc_date()
        self.max_daily_drawdown_percent = getattr(Config, 'MAX_DAILY_DRAWDOWN_PERCENT', 0.05)
        self.max_same_direction = getattr(Config, 'MAX_SAME_DIRECTION_POSITIONS', 3)
        self.halt_trading_until = 0

    def _get_current_utc_date(self):
        return datetime.now(timezone.utc).date()

    def _check_and_reset_daily(self):
        """Reset daily drawdown if a new UTC day has started."""
        current_date = self._get_current_utc_date()
        if current_date > self.last_reset_time:
            self.daily_drawdown_usd = 0.0
            self.last_reset_time = current_date
            log.info("Daily drawdown reset due to new UTC day")

    def record_trade_result(self, pnl: float):
        """
        Record the PNL of a closed trade to track daily drawdown.
        """
        self._check_and_reset_daily()
        
        # We only track realized losses for daily drawdown
        if pnl < 0:
            self.daily_drawdown_usd += abs(pnl)
            log.info(f"Recorded loss: {abs(pnl):.2f}. Total daily drawdown: {self.daily_drawdown_usd:.2f}")

    def is_trading_halted(self) -> bool:
        """Check if trading is completely halted due to max drawdown."""
        if time.time() < self.halt_trading_until:
            return True
        return False

    def check_portfolio_health(self, total_equity: float, open_positions: List[Dict]) -> Tuple[bool, str]:
        """
        Monitor total unrealized PnL and trigger emergency closure if needed.
        Open positions should be a list of dicts with 'unrealized_pnl' keys.
        """
        total_upl = sum(float(pos.get('unrealized_pnl', 0)) for pos in open_positions)
        portfolio_max_loss_usd = total_equity * getattr(Config, 'PORTFOLIO_MAX_UNREALIZED_LOSS_PERCENT', 0.10) # 10% default

        if total_upl < -portfolio_max_loss_usd:
            self.halt_trading_until = time.time() + (24 * 3600) # Halt for 24 hours
            log.critical(f"PORTFOLIO KILL SWITCH TRIGGERED: Total UPL {total_upl:.2f} < Limit -{portfolio_max_loss_usd:.2f}")
            return False, "Portfolio unrealized loss limit exceeded. Emergency halt."
            
        return True, "Portfolio healthy."

    def can_open_position(self, symbol: str, test_direction: str, account_equity: float, current_positions: List[Dict]) -> Tuple[bool, str]:
        """
        Determine if a new position is allowed to be opened based on portfolio rules.
        """
        self._check_and_reset_daily()

        if self.is_trading_halted():
            return False, "Trading halted due to max daily drawdown exceeded."

        # 1. Max concurrent positions check
        max_concurrent = getattr(Config, 'MAX_CONCURRENT_POSITIONS', 5)
        if len(current_positions) >= max_concurrent:
            return False, f"Max concurrent positions reached ({max_concurrent})."

        # 2. Daily Drawdown check
        max_allowed_drawdown = account_equity * self.max_daily_drawdown_percent
        if self.daily_drawdown_usd >= max_allowed_drawdown:
            # Halt trading for 12 hours
            self.halt_trading_until = time.time() + (12 * 3600)
            return False, f"Max daily drawdown exceeded (${self.daily_drawdown_usd:.2f} >= ${max_allowed_drawdown:.2f}). Trading halted."

        # 3. Already open position on the same symbol
        for pos in current_positions:
            if pos.get('symbol') == symbol:
                return False, f"Position already exists for {symbol}."

        # 4. Correlation / Over-exposure check
        # Simple heuristic: If we have multiple positions in the same direction, 
        # ensure we are not overloading one side heavily if max_concurrent is high.
        # Here we just restrict to max 3 positions in the exact same direction if max_concurrent is 5.
        same_direction_count = sum(1 for p in current_positions if p.get('direction', '').upper() == test_direction.upper())
        if same_direction_count >= self.max_same_direction:
            return False, f"Over-exposure risk: {same_direction_count} positions already open in {test_direction} direction."

        return True, "Passed portfolio risk checks."

# Global singleton instance
portfolio_risk_manager = PortfolioRiskManager()
